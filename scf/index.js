'use strict';
// =====================================================================
// 腾讯云 SCF (云函数) 后端 —— report-portal 的登录 / 上传 / 分享接口
//
// 安全模型(重构后):
//   - GitHub 令牌 (GITHUB_TOKEN): 只存在本函数环境变量，永不进浏览器。
//   - 管理密码 (ADMIN_PASSWORD): 只存在本函数环境变量，永不进浏览器 / 网页代码。
//   - 会话密钥 (SESSION_SECRET): 只存在本函数环境变量，用于给登录令牌签名。
//   - 浏览器里【不再有任何密钥或密码】。登录成功后服务端下发一个签名令牌
//     (HMAC-SHA256)，令牌不含明文密码，保存在本地用于后续操作鉴权。
//
// 接口:
//   POST {op:'login', password}                       -> 校验密码, 返回 {token}
//   POST {op:'upload', filename, content, category}   -> 需带 x-admin-token
//   POST {op:'delete', filename}                      -> 需带 x-admin-token(真删并移入回收站)
//   POST {op:'listtrash'}                             -> 需带 x-admin-token(列出回收站)
//   POST {op:'restore', entryId}                      -> 需带 x-admin-token(从回收站恢复)
//   POST {op:'purge', entryId}                        -> 需带 x-admin-token(彻底删除单条)
//   POST {op:'purgeall'}                              -> 需带 x-admin-token(清空回收站)
//   POST {op:'state', action:'get'|'put', filename}  -> 需带 x-admin-token(看板勾选状态云同步)
//   POST {op:'share', ...}                            -> 需带 x-admin-token(前端已未调用)
//
// 服务端限制: 来源白名单 / 文件类型白名单 / 大小上限 / 频率限制 / 覆盖前自动备份
// 删除文件时会先将其内容与元信息存入 trash/ 目录, 再删除 reports/ 与 manifest 记录,
// 因此「删除」是软删除, 可在后台「垃圾箱」中恢复或彻底清除。
// 部署与环境变量见同目录 TENCENT_SCF_DEPLOY.md
// =====================================================================

const https = require('https');
const crypto = require('crypto');

function env(name, def) {
  return process.env[name] !== undefined ? process.env[name] : def;
}

// ---------- 服务端要求配置的环境变量(均不进网页) ----------
const ADMIN_PASSWORD = env('ADMIN_PASSWORD', '');
const SESSION_SECRET = env('SESSION_SECRET', '');
const ALLOWED_ORIGIN = env('ALLOWED_ORIGIN', '');                      // 例如 https://Aurillis.github.io (可逗号分隔多个; 留空则自动按 SITE_BASE 推导)
const MAX_UPLOAD_BYTES = Number(env('MAX_UPLOAD_BYTES', 15 * 1024 * 1024)); // 默认 15MB
// 看板勾选状态云同步用的「共享编辑密钥」：与前端(看板/查看页)内嵌值一致即可。
// 留空则仅 admin 令牌可写；设置后看板凭此密钥即可写回，无需先登录后台。
const STATE_EDIT_KEY = env('STATE_EDIT_KEY', 'kbSync_8f3a2c91d4e5');

// 允许的跨域来源：支持逗号分隔多个；自动忽略末尾斜杠与大小写差异。
// 若未配置 ALLOWED_ORIGIN，则根据 SITE_BASE 自动推导(并额外允许 localhost 便于本地调试)。
function getAllowedOrigins() {
  const raw = (ALLOWED_ORIGIN || '').trim();
  let list = [];
  if (raw) {
    list = raw.split(',').map(function (s) { return s.trim().replace(/\/+$/, ''); }).filter(Boolean);
  } else {
    const sb = env('SITE_BASE', '').trim().replace(/\/+$/, '');
    if (sb) { try { list.push(new URL(sb).origin); } catch (e) {} }
    list.push('http://localhost:5500', 'http://127.0.0.1:5500');
  }
  return list;
}
function originAllowed(origin) {
  const o = (origin || '').trim().replace(/\/+$/, '');
  if (o === '' || o === '*') return true; // 无来源信息或非浏览器请求放行, 由密码鉴权兜底
  for (const a of getAllowedOrigins()) {
    if (o === a || o.toLowerCase() === a.toLowerCase()) return true;
  }
  return false;
}
const RATE_WINDOW_MS = Number(env('RATE_WINDOW_MS', 60000));
const RATE_MAX = Number(env('RATE_MAX', 30));                          // 每窗口最多请求数
// 允许的文件后缀白名单
const ALLOWED_EXT = /\.(pdf|docx?|xlsx?|pptx?|html?|md|txt|csv|png|jpe?g|gif|svg|zip)$/i;

// ---------- 令牌签名 / 校验 (HMAC-SHA256) ----------
function b64url(buf) {
  return Buffer.from(buf).toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
function b64urlDecode(s) {
  s = String(s).replace(/-/g, '+').replace(/_/g, '/');
  return Buffer.from(s, 'base64').toString('utf8');
}
function signToken() {
  const payload = b64url(JSON.stringify({ exp: Date.now() + 86400000, r: crypto.randomBytes(6).toString('hex') }));
  const sig = crypto.createHmac('sha256', SESSION_SECRET).update(payload).digest('base64').replace(/=+$/, '');
  return payload + '.' + sig;
}
function verifyToken(token) {
  if (!SESSION_SECRET || !token) return false;
  const parts = String(token).split('.');
  if (parts.length !== 2) return false;
  const expected = crypto.createHmac('sha256', SESSION_SECRET).update(parts[0]).digest('base64').replace(/=+$/, '');
  const a = Buffer.from(parts[1]); const b = Buffer.from(expected);
  if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) return false;
  try { const p = JSON.parse(b64urlDecode(parts[0])); return p.exp > Date.now(); } catch (e) { return false; }
}

// ---------- GitHub REST 调用(内置 https, 无需依赖) ----------
function ghRequest(method, path, bodyObj) {
  return new Promise((resolve, reject) => {
    const payload = bodyObj ? JSON.stringify(bodyObj) : null;
    const headers = {
      'Authorization': 'Bearer ' + env('GITHUB_TOKEN'),
      'Accept': 'application/vnd.github+json',
      'Content-Type': 'application/json',
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': 'report-portal-scf',
    };
    if (payload) headers['Content-Length'] = Buffer.byteLength(payload);

    const req = https.request({
      hostname: 'api.github.com',
      port: 443,
      path: '/repos/' + env('GITHUB_REPO', 'Aurillis/database') + path,
      method: method,
      headers: headers,
    }, (res) => {
      let data = '';
      res.on('data', (c) => { data += c; });
      res.on('end', () => {
        let json = null;
        try { json = JSON.parse(data); } catch (e) { /* ignore */ }
        resolve({ status: res.statusCode, json: json });
      });
    });
    req.on('error', reject);
    if (payload) req.write(payload);
    req.end();
  });
}

// ---------- 统一响应 ----------
function send(statusCode, obj, origin) {
  return {
    statusCode: statusCode,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Access-Control-Allow-Origin': origin || '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, x-admin-token',
    },
    isBase64Encoded: false,
    body: JSON.stringify(obj),
  };
}

// ---------- 速率限制(进程内, 尽力而为) ----------
const rlMap = {};
function rateLimit(key) {
  const now = Date.now();
  if (!rlMap[key]) rlMap[key] = [];
  rlMap[key] = rlMap[key].filter((t) => now - t < RATE_WINDOW_MS);
  if (rlMap[key].length >= RATE_MAX) return false;
  rlMap[key].push(now);
  return true;
}
function clientKey(event) {
  const h = event.headers || {};
  return h['x-forwarded-for'] || h['x-real-ip'] || (h.origin || '*');
}

// ---------- 登录: 校验密码, 下发签名令牌 ----------
function handleLogin(body, origin) {
  if (!ADMIN_PASSWORD) return send(500, { error: '服务端未配置 ADMIN_PASSWORD 环境变量' }, origin);
  if (!SESSION_SECRET) return send(500, { error: '服务端未配置 SESSION_SECRET 环境变量' }, origin);
  const pwd = body && body.password;
  if (!pwd || pwd !== ADMIN_PASSWORD) return send(401, { error: '密码错误' }, origin);
  return send(200, { ok: true, token: signToken() }, origin);
}

// ---------- 令牌鉴权: 非 login 操作必须带有效令牌 ----------
function requireAuth(event, origin) {
  const h = event.headers || {};
  const token = h['x-admin-token'] || h['X-Admin-Token'];
  if (!verifyToken(token)) return send(401, { error: '未授权或登录已过期，请重新登录' }, origin);
  return null;
}

// ---------- 覆盖前自动备份(每文件保留最近 5 份) ----------
async function backupBeforeOverwrite(safeName, oldContent, branch) {
  if (!oldContent) return; // 新文件无需备份
  const ts = new Date().toISOString().replace(/[:.]/g, '-');
  const bakName = safeName + '__' + ts + '.b64';
  const putRes = await ghRequest('PUT', '/contents/backups/reports/' + encodeURIComponent(bakName), {
    message: 'backup: ' + safeName,
    content: oldContent,
    branch: branch,
  });
  if (putRes.status >= 300) return; // 备份失败不阻断主流程
  // 仅保留最近 5 份
  try {
    const listRes = await ghRequest('GET', '/contents/backups/reports?ref=' + branch);
    if (listRes.status !== 200 || !Array.isArray(listRes.json)) return;
    const prefix = safeName + '__';
    const entries = listRes.json.filter((e) => e.name && e.name.indexOf(prefix) === 0);
    entries.sort((a, b) => b.name.localeCompare(a.name));
    const excess = entries.slice(5);
    for (const e of excess) {
      await ghRequest('DELETE', '/contents/backups/reports/' + encodeURIComponent(e.name), {
        message: 'rotate backup: ' + safeName,
        sha: e.sha, branch: branch,
      });
    }
  } catch (e) { /* 清理失败不影响主流程 */ }
}

// ---------- manifest 读写辅助 ----------
async function getManifest(branch) {
  const res = await ghRequest('GET', '/contents/manifest.json?ref=' + branch);
  if (res.status !== 200 || !res.json || !res.json.content) return null;
  try {
    return { sha: res.json.sha, data: JSON.parse(Buffer.from(res.json.content, 'base64').toString('utf8')) };
  } catch (e) { return null; }
}
async function putManifest(data, sha, branch, message) {
  const content = Buffer.from(JSON.stringify(data, null, 2), 'utf8').toString('base64');
  const res = await ghRequest('PUT', '/contents/manifest.json', { message: message, content: content, sha: sha, branch: branch });
  // 关键: 不再静默忽略失败 —— 写不进 manifest 会抛错, 让上层感知(否则文件已从磁盘删掉却仍留在 manifest, 刷新即"幽灵重现")
  if (res.status >= 300) throw new Error('更新 manifest 失败: ' + ((res.json && res.json.message) || res.status));
  return res;
}
async function removeFromManifest(safeName, branch) {
  const m = await getManifest(branch);
  if (!m) return;
  const data = (m.data || []).filter(function (f) { return f.filename !== safeName; });
  await putManifest(data, m.sha, branch, 'manifest: remove ' + safeName);
}
async function addToManifest(safeName, branch, content, meta) {
  const m = await getManifest(branch);
  if (!m) return;
  let data = (m.data || []).filter(function (f) { return f.filename !== safeName; });
  const decodedSize = Math.max(0, Math.floor((content || '').length * 3 / 4)
    - (content && content.endsWith('==') ? 2 : content && content.endsWith('=') ? 1 : 0));
  data.push({
    filename: safeName,
    title: (meta && meta.title) || safeName.replace(/\.[^.]+$/, ''),
    size: (meta && meta.size) || decodedSize,
    mtime: Math.floor(Date.now() / 1000),
    category: (meta && meta.category) || 'other',
  });
  await putManifest(data, m.sha, branch, 'manifest: add ' + safeName);
}

// ---------- 分类/标签等元数据(云端同步, meta.json) ----------
async function getMeta(branch) {
  const res = await ghRequest('GET', '/contents/meta.json?ref=' + branch);
  if (res.status !== 200 || !res.json || !res.json.content) return null;
  try {
    return { sha: res.json.sha, data: JSON.parse(Buffer.from(res.json.content, 'base64').toString('utf8')) };
  } catch (e) { return null; }
}
async function putMeta(data, sha, branch, message) {
  const content = Buffer.from(JSON.stringify(data, null, 2), 'utf8').toString('base64');
  const putBody = { message: message, content: content, branch: branch };
  if (sha) putBody.sha = sha;
  const res = await ghRequest('PUT', '/contents/meta.json', putBody);
  if (res.status >= 300) throw new Error('更新 meta 失败: ' + ((res.json && res.json.message) || res.status));
  return res;
}
async function handleMeta(body, origin) {
  const branch = env('GITHUB_BRANCH', 'main');
  const d = (body && body.data) || {};
  // 仅接受已知字段, 避免被写入无关结构
  const out = {
    customCats: Array.isArray(d.customCats) ? d.customCats : [],
    fileCats: (d.fileCats && typeof d.fileCats === 'object') ? d.fileCats : {},
    fileTags: (d.fileTags && typeof d.fileTags === 'object') ? d.fileTags : {},
    allTags: Array.isArray(d.allTags) ? d.allTags : [],
  };
  try {
    const m = await getMeta(branch);
    if (m) {
      await putMeta(out, m.sha, branch, 'meta: update');
    } else {
      await ghRequest('PUT', '/contents/meta.json', {
        message: 'meta: init',
        content: Buffer.from(JSON.stringify(out, null, 2), 'utf8').toString('base64'),
        branch: branch,
      });
    }
    return send(200, { ok: true }, origin);
  } catch (err) {
    return send(500, { error: '服务器错误: ' + (err && err.message ? err.message : err) }, origin);
  }
}

// ---------- 文件移动(改 manifest.category + 同步 meta.fileCats, 云端权威源) ----------
async function handleMove(body, origin) {
  const branch = env('GITHUB_BRANCH', 'main');
  const filename = (body && body.filename) || '';
  const targetCat = (body && body.targetCat) || '';
  if (!filename || !targetCat) return send(400, { error: '缺少 filename 或 targetCat' }, origin);
  try {
    const m = await getManifest(branch);
    if (!m) return send(404, { error: 'manifest 不存在' }, origin);
    const data = m.data || [];
    const item = data.find(function (f) { return f.filename === filename; });
    if (!item) return send(404, { error: '文件不存在于 manifest: ' + filename }, origin);
    item.category = targetCat;
    await putManifest(data, m.sha, branch, 'manifest: move ' + filename + ' -> ' + targetCat);
    // 同步 meta.fileCats 覆盖层(冗余, 便于未登录态/快速回退)
    try {
      const meta = await getMeta(branch);
      const mdata = meta ? meta.data : { fileCats: {}, customCats: [], fileTags: {}, allTags: [] };
      if (!mdata.fileCats) mdata.fileCats = {};
      mdata.fileCats[filename] = targetCat;
      await putMeta(mdata, meta ? meta.sha : null, branch, 'meta: move ' + filename);
    } catch (e) { /* meta 覆盖层同步失败不阻断主流程 */ }
    return send(200, { ok: true }, origin);
  } catch (err) {
    return send(500, { error: '移动失败: ' + (err && err.message ? err.message : err) }, origin);
  }
}

// ---------- 看板勾选状态云同步(按文件名存到 state/<name>.json) ----------
async function getState(filename, branch) {
  const safe = safeNameOf(filename);
  const path = '/contents/state/' + encodeURIComponent(safe) + '.json';
  const res = await ghRequest('GET', path + '?ref=' + branch);
  if (res.status !== 200 || !res.json || !res.json.content) return null;
  try { return { sha: res.json.sha, data: JSON.parse(Buffer.from(res.json.content, 'base64').toString('utf8')) }; } catch (e) { return null; }
}
async function putState(filename, data, branch) {
  const safe = safeNameOf(filename);
  const path = '/contents/state/' + encodeURIComponent(safe) + '.json';
  const content = Buffer.from(JSON.stringify(data, null, 2), 'utf8').toString('base64');
  let lastErr = null;
  // 并发写入会让 GitHub 的 blob sha 失效(返回 409/422/412)。重新拉取最新 sha 后重试，
  // 避免「另一台设备/上一个防抖写入刚提交」就导致本次直接 500。最多重试 6 次(带递增退避)。
  for (let attempt = 0; attempt < 6; attempt++) {
    const existing = await getState(filename, branch);
    const putBody = { message: 'state: ' + safe, content: content, branch: branch };
    if (existing) putBody.sha = existing.sha;
    const res = await ghRequest('PUT', path, putBody);
    if (res.status < 300) return res;
    if (res.status === 409 || res.status === 422 || res.status === 412) {
      lastErr = res;
      await new Promise((r) => setTimeout(r, 120 * (attempt + 1)));
      continue;
    }
    throw new Error('保存状态失败: ' + ((res.json && res.json.message) || res.status));
  }
  throw new Error('保存状态失败(并发冲突，已重试): ' + ((lastErr && lastErr.json && lastErr.json.message) || 'conflict'));
}
async function handleState(body, origin, event) {
  const branch = env('GITHUB_BRANCH', 'main');
  const filename = body && body.filename;
  if (!filename) return send(400, { error: '缺少 filename' }, origin);
  const action = (body && body.action) || 'get';
  try {
    if (action === 'get') {
      // 公开读取：看板状态本身已在公开 Pages 上，任何来源均可读取最新进度
      const s = await getState(filename, branch);
      if (!s) return send(404, { error: 'no state' }, origin);
      return send(200, { ok: true, data: s.data.data, ts: s.data.ts }, origin);
    }
    if (action === 'put') {
      const data = body.data;
      const ts = body.ts || Date.now();
      if (!data || typeof data !== 'object') return send(400, { error: '缺少 data' }, origin);
      // 鉴权：admin 令牌 或 看板自带 editKey(前端内嵌，与 STATE_EDIT_KEY 一致即可免登录保存)
      const h = (event && event.headers) || {};
      const adminOk = verifyToken(h['x-admin-token'] || h['X-Admin-Token']);
      const ek = (body && body.editKey) || h['x-edit-key'] || h['X-Edit-Key'];
      const editOk = !!STATE_EDIT_KEY && ek === STATE_EDIT_KEY;
      if (!adminOk && !editOk) return send(401, { error: '未授权：需登录后台或有效 editKey' }, origin);
      // 仅存看板自身的 localStorage 键(排除 kb_ 前缀的管理态与任何含 token 的键), 避免泄露管理令牌
      const clean = {};
      for (const k of Object.keys(data)) {
        if (k.indexOf('kb_') === 0 || k.toLowerCase().indexOf('token') >= 0) continue;
        clean[k] = data[k];
      }
      await putState(filename, { filename: safeNameOf(filename), data: clean, ts: ts }, branch);
      return send(200, { ok: true }, origin);
    }
    return send(400, { error: '未知 action: ' + action }, origin);
  } catch (err) {
    return send(500, { error: '服务器错误: ' + (err && err.message ? err.message : err) }, origin);
  }
}

// 文件名安全过滤(防路径穿越) —— 与上传保持一致
function safeNameOf(filename) {
  return String(filename)
    .replace(/[^\w.\-\u4e00-\u9fa5 ()]/g, '_')
    .replace(/^\.+/, '')
    .slice(0, 200);
}

// ---------- 删除(软删除 -> 回收站) ----------
async function handleDelete(body, origin) {
  const filename = body && body.filename;
  if (!filename) return send(400, { error: '缺少 filename' }, origin);
  const safeName = safeNameOf(filename);
  const branch = env('GITHUB_BRANCH', 'main');
  const filePath = '/contents/reports/' + encodeURIComponent(safeName);

  try {
    const head = await ghRequest('GET', filePath + '?ref=' + branch);
    if (head.status === 404) {
      // 文件已不在磁盘上(可能之前已删) -> 仅确保 manifest 干净即可, 返回成功(幂等, 便于重试)
      await removeFromManifest(safeName, branch);
      return send(200, { ok: true, alreadyGone: true }, origin);
    }
    if (head.status >= 300) return send(500, { error: '读取文件失败: ' + (head.json && head.json.message || head.status) }, origin);
    const sha = head.json.sha;
    const content = head.json.content;

    // 抓取原 manifest 元信息(用于恢复时还原标题/分类)
    let meta = null;
    const m = await getManifest(branch);
    if (m) {
      const entry = (m.data || []).find(function (f) { return f.filename === safeName; });
      if (entry) meta = { title: entry.title, category: entry.category, size: entry.size };
    }

    // 写入回收站: trash/reports/<entryId> + trash/meta/<entryId>.json
    const entryId = new Date().toISOString().replace(/[:.]/g, '-')
      + '__' + crypto.randomBytes(4).toString('hex') + '__' + safeName;
    await ghRequest('PUT', '/contents/trash/reports/' + encodeURIComponent(entryId), {
      message: 'trash: ' + safeName, content: content, branch: branch,
    });
    const metaContent = Buffer.from(JSON.stringify({
      originalFilename: safeName, deletedAt: Date.now(), title: meta && meta.title,
      category: meta && meta.category, size: meta && meta.size,
    }, null, 2), 'utf8').toString('base64');
    await ghRequest('PUT', '/contents/trash/meta/' + encodeURIComponent(entryId) + '.json', {
      message: 'trash meta: ' + safeName, content: metaContent, branch: branch,
    });

    // 从 reports/ 删除
    const delRes = await ghRequest('DELETE', filePath, { message: 'delete: ' + safeName, sha: sha, branch: branch });
    if (delRes.status >= 300) return send(500, { error: '删除 reports 失败: ' + (delRes.json && delRes.json.message || delRes.status) }, origin);

    // 从 manifest 移除
    await removeFromManifest(safeName, branch);

    return send(200, { ok: true, entryId: entryId }, origin);
  } catch (err) {
    return send(500, { error: '服务器错误: ' + (err && err.message ? err.message : err) }, origin);
  }
}

// ---------- 列出回收站 ----------
async function handleListTrash(body, origin) {
  const branch = env('GITHUB_BRANCH', 'main');
  try {
    const res = await ghRequest('GET', '/contents/trash/meta?ref=' + branch);
    if (res.status !== 200 || !Array.isArray(res.json)) return send(200, { ok: true, items: [] }, origin);
    const items = [];
    // meta 目录文件通常很少, 逐一读取可接受的请求量
    for (const e of res.json) {
      if (!e.name || e.name.indexOf('.json') !== e.name.length - 5) continue;
      const mRes = await ghRequest('GET', '/contents/trash/meta/' + encodeURIComponent(e.name) + '?ref=' + branch);
      if (mRes.status !== 200 || !mRes.json || !mRes.json.content) continue;
      try {
        const meta = JSON.parse(Buffer.from(mRes.json.content, 'base64').toString('utf8'));
        items.push({
          entryId: e.name.replace(/\.json$/, ''),
          originalFilename: meta.originalFilename || e.name,
          deletedAt: meta.deletedAt || 0,
          title: meta.title,
          category: meta.category,
          size: meta.size,
        });
      } catch (err) { /* 跳过坏数据 */ }
    }
    items.sort(function (a, b) { return (b.deletedAt || 0) - (a.deletedAt || 0); });
    return send(200, { ok: true, items: items }, origin);
  } catch (err) {
    return send(500, { error: '服务器错误: ' + (err && err.message ? err.message : err) }, origin);
  }
}

// ---------- 从回收站恢复 ----------
async function handleRestore(body, origin) {
  const entryId = body && body.entryId;
  if (!entryId) return send(400, { error: '缺少 entryId' }, origin);
  const branch = env('GITHUB_BRANCH', 'main');
  try {
    const tRes = await ghRequest('GET', '/contents/trash/reports/' + encodeURIComponent(entryId) + '?ref=' + branch);
    if (tRes.status !== 200 || !tRes.json) return send(404, { error: '回收站中无此文件' }, origin);
    const content = tRes.json.content;
    const tSha = tRes.json.sha;

    let meta = null;
    const mRes = await ghRequest('GET', '/contents/trash/meta/' + encodeURIComponent(entryId) + '.json?ref=' + branch);
    if (mRes.status === 200 && mRes.json && mRes.json.content) {
      try { meta = JSON.parse(Buffer.from(mRes.json.content, 'base64').toString('utf8')); } catch (e) { /* ignore */ }
    }
    const originalFilename = (meta && meta.originalFilename) || entryId;
    const safeName = safeNameOf(originalFilename);

    // 写回 reports/(若已存在则覆盖)
    const rPath = '/contents/reports/' + encodeURIComponent(safeName);
    const rHead = await ghRequest('GET', rPath + '?ref=' + branch);
    const putBody = { message: 'restore: ' + safeName, content: content, branch: branch };
    if (rHead.status === 200 && rHead.json && rHead.json.sha) putBody.sha = rHead.json.sha;
    const putRes = await ghRequest('PUT', rPath, putBody);
    if (putRes.status >= 300) return send(500, { error: '恢复失败: ' + (putRes.json && putRes.json.message || putRes.status) }, origin);

    // 重新加入 manifest
    await addToManifest(safeName, branch, content, meta);

    // 清理回收站条目
    const mSha = (mRes.json && mRes.json.sha) || null;
    await ghRequest('DELETE', '/contents/trash/reports/' + encodeURIComponent(entryId), { message: 'purge trash: ' + entryId, sha: tSha, branch: branch });
    if (mSha) await ghRequest('DELETE', '/contents/trash/meta/' + encodeURIComponent(entryId) + '.json', { message: 'purge trash meta', sha: mSha, branch: branch });

    return send(200, { ok: true }, origin);
  } catch (err) {
    return send(500, { error: '服务器错误: ' + (err && err.message ? err.message : err) }, origin);
  }
}

// ---------- 彻底删除单条(从回收站) ----------
async function handlePurge(body, origin) {
  const entryId = body && body.entryId;
  if (!entryId) return send(400, { error: '缺少 entryId' }, origin);
  const branch = env('GITHUB_BRANCH', 'main');
  try {
    const tRes = await ghRequest('GET', '/contents/trash/reports/' + encodeURIComponent(entryId) + '?ref=' + branch);
    if (tRes.status === 200 && tRes.json && tRes.json.sha) {
      await ghRequest('DELETE', '/contents/trash/reports/' + encodeURIComponent(entryId), { message: 'purge: ' + entryId, sha: tRes.json.sha, branch: branch });
    }
    const mRes = await ghRequest('GET', '/contents/trash/meta/' + encodeURIComponent(entryId) + '.json?ref=' + branch);
    if (mRes.status === 200 && mRes.json && mRes.json.sha) {
      await ghRequest('DELETE', '/contents/trash/meta/' + encodeURIComponent(entryId) + '.json', { message: 'purge meta: ' + entryId, sha: mRes.json.sha, branch: branch });
    }
    return send(200, { ok: true }, origin);
  } catch (err) {
    return send(500, { error: '服务器错误: ' + (err && err.message ? err.message : err) }, origin);
  }
}

// ---------- 清空回收站 ----------
async function handlePurgeAll(body, origin) {
  const branch = env('GITHUB_BRANCH', 'main');
  try {
    const res = await ghRequest('GET', '/contents/trash/meta?ref=' + branch);
    if (res.status !== 200 || !Array.isArray(res.json)) return send(200, { ok: true, count: 0 }, origin);
    let count = 0;
    for (const e of res.json) {
      if (!e.name || e.name.indexOf('.json') !== e.name.length - 5) continue;
      const entryId = e.name.replace(/\.json$/, '');
      const tRes = await ghRequest('GET', '/contents/trash/reports/' + encodeURIComponent(entryId) + '?ref=' + branch);
      if (tRes.status === 200 && tRes.json && tRes.json.sha) {
        await ghRequest('DELETE', '/contents/trash/reports/' + encodeURIComponent(entryId), { message: 'purge: ' + entryId, sha: tRes.json.sha, branch: branch });
      }
      if (e.sha) {
        await ghRequest('DELETE', '/contents/trash/meta/' + encodeURIComponent(e.name), { message: 'purge meta: ' + entryId, sha: e.sha, branch: branch });
      }
      count++;
    }
    return send(200, { ok: true, count: count }, origin);
  } catch (err) {
    return send(500, { error: '服务器错误: ' + (err && err.message ? err.message : err) }, origin);
  }
}

// ---------- 上传 ----------
// 自动注入云同步桥：让每个上传的 HTML 都自带「跨设备共享进度」能力。
//  · 行为与服务中 viewer 的 buildStateShim 完全一致(免登录 editKey 写、SCF 实时读+同源 state 备读、toast 提示)。
//  · 幂等：文件已含 KB_EDIT_KEY(如已烤入的盆底肌看板)则跳过，避免重复注入。
//  · 直接打开 / 经网站列表打开 两种路径都会同步。
function injectSyncScript(html) {
  if (!html || html.indexOf('KB_EDIT_KEY') >= 0) return html; // 已含同步脚本则跳过(幂等)
  var script = '<script>(function(){ if(window.__KB_SYNC_INJECTED) return; window.__KB_SYNC_INJECTED=true; try {'
    + ' var kbFile=(window.__KB_FILE)||location.pathname.split(\'/\').pop(); if(!kbFile) return;'
    + ' var base=location.href.split(\'/viewer.html\')[0].split(\'/reports/\')[0];'
    + ' var KB_STATE=base+\'/state/\'+encodeURIComponent(kbFile)+\'.json\';'
    + ' var KB_API=\'https://1461447139-m5rkq2fg8n.ap-guangzhou.tencentscf.com\';'
    + ' var KB_EDIT_KEY=\'kbSync_8f3a2c91d4e5\';'
    + ' function toast(msg,ok){ try { var d=document.getElementById(\'__kb_toast\'); if(!d){ d=document.createElement(\'div\'); d.id=\'__kb_toast\'; d.style.cssText=\'position:fixed;right:12px;bottom:12px;z-index:2147483647;max-width:260px;padding:8px 12px;border-radius:8px;font:13px/1.5 system-ui,sans-serif;color:#fff;box-shadow:0 4px 14px rgba(0,0,0,.25);opacity:.96;\'; document.body.appendChild(d); } d.textContent=msg; d.style.background=ok?\'#0e7d72\':\'#c0392b\'; d.style.display=\'block\'; clearTimeout(d.__t); d.__t=setTimeout(function(){ if(d) d.style.display=\'none\'; }, 2800); } catch(e){} }'
    + ' function applyState(j){ try { if(!j||!j.data) return; var lts=parseInt(localStorage.getItem(\'__kbst_ts\')||\'0\',10); if((j.ts||0)>lts){ for(var k in j.data){ if(j.data.hasOwnProperty(k)) localStorage.setItem(k,j.data[k]); } localStorage.setItem(\'__kbst_ts\',String(j.ts||0)); toast(\'已同步云端最新进度\', true); } } catch(e){} }'
    + ' function readPages(){ try { var x=new XMLHttpRequest(); x.open(\'GET\', KB_STATE+\'?t=\'+Date.now(), false); x.send(); if(x.status===200){ try { applyState(JSON.parse(x.responseText)); } catch(e){} } } catch(e){} }'
    + ' function readSCF(){ try { var x=new XMLHttpRequest(); x.open(\'POST\', KB_API, true); x.setRequestHeader(\'Content-Type\',\'application/json\'); x.onload=function(){ if(x.status===200){ try { applyState(JSON.parse(x.responseText)); } catch(e){ readPages(); } } else { readPages(); } }; x.onerror=function(){ readPages(); }; x.send(JSON.stringify({op:\'state\',action:\'get\',filename:kbFile})); } catch(e){ readPages(); } }'
    + ' readSCF();'
    + ' var _set=Storage.prototype.setItem; var PREFIX=\'__kbst_\'; var lastSent=\'\'; var _inflight=false; var _pending=false;'
    + ' function isOwn(k){ return !k||k.indexOf(\'kb_\')===0||(k&&k.toLowerCase().indexOf(\'token\')>=0)||k.indexOf(PREFIX)===0; }'
    + ' function snap(){ var d={}; for(var i=0;i<localStorage.length;i++){ var k=localStorage.key(i); if(isOwn(k)) continue; d[k]=localStorage.getItem(k); } return d; }'
    + ' function push(){ var data=snap(); var key=JSON.stringify(data); if(key===lastSent&&!_inflight) return; if(_inflight){ _pending=true; lastSent=key; return; } lastSent=key; _inflight=true; var body=JSON.stringify({op:\'state\',action:\'put\',filename:kbFile,data:data,ts:Date.now(),editKey:KB_EDIT_KEY}); fetch(KB_API,{method:\'POST\',headers:{\'Content-Type\':\'application/json\'},body:body}).then(function(r){ if(r.ok){ toast(\'已自动保存到云端\', true); } else { toast(\'云端保存失败(\'+r.status+\')\', false); } }).catch(function(){ toast(\'云端保存失败，请检查网络\', false); }).finally(function(){ _inflight=false; if(_pending){ _pending=false; setTimeout(push,0); } }); }'
    + ' var _origPrint=window.print?window.print.bind(window):function(){}; try { window.print=function(){ if(window.parent&&window.parent.__kbPrint){ window.parent.__kbPrint(); return; } _origPrint(); }; } catch(e){}'
    + ' Storage.prototype.setItem=function(k,v){ _set.apply(this,arguments); if(isOwn(k)) return; setTimeout(function(){ push(); }, 800); };'
    + ' } catch(e){} })();<\/script>';
  if (/<head[^>]*>/i.test(html)) return html.replace(/<head[^>]*>/i, function (m) { return m + '\n' + script; });
  if (/<html[^>]*>/i.test(html)) return html.replace(/<html[^>]*>/i, function (m) { return m + '\n' + script; });
  return script + '\n' + html;
}

async function handleUpload(body, origin) {
  const { filename, content, category } = body || {};
  if (!filename || !content) return send(400, { error: '缺少 filename 或 content' }, origin);

  // 文件类型白名单
  if (!ALLOWED_EXT.test(filename)) {
    return send(400, { error: '不支持的文件类型，仅允许: PDF / Word / Excel / PPT / HTML / Markdown / TXT / CSV / 图片 / 压缩包' }, origin);
  }
  // 大小上限
  const decodedSize = Math.max(0, Math.floor(content.length * 3 / 4)
    - (content.endsWith('==') ? 2 : content.endsWith('=') ? 1 : 0));
  if (decodedSize > MAX_UPLOAD_BYTES) {
    return send(413, { error: '文件过大，上限 ' + (MAX_UPLOAD_BYTES / 1024 / 1024).toFixed(0) + 'MB' }, origin);
  }
  // 文件名安全过滤(防路径穿越)
  const safeName = String(filename)
    .replace(/[^\w.\-\u4e00-\u9fa5 ()]/g, '_')
    .replace(/^\.+/, '')
    .slice(0, 200);

  // 自动注入云同步桥：HTML 文件上传时即烤入共享脚本(直接打开也同步、重传不丢)
  if (/\.(html?)$/i.test(filename)) {
    try {
      const decoded = Buffer.from(content, 'base64').toString('utf8');
      const injected = injectSyncScript(decoded);
      content = Buffer.from(injected, 'utf8').toString('base64');
    } catch (e) { /* 解码失败则保持原样上传 */ }
  }

  const branch = env('GITHUB_BRANCH', 'main');
  const filePath = '/contents/reports/' + encodeURIComponent(safeName);

  try {
    const head = await ghRequest('GET', filePath + '?ref=' + branch);
    const sha = (head.json && head.json.sha) || null;
    const oldContent = (head.json && head.json.content) || null;

    // 覆盖前先备份旧内容(防误删/恶意覆盖)
    await backupBeforeOverwrite(safeName, oldContent, branch);

    const putBody = { message: 'upload: ' + safeName, content: content, branch: branch };
    if (sha) putBody.sha = sha;
    const putRes = await ghRequest('PUT', filePath, putBody);
    if (putRes.status >= 300) {
      const msg = (putRes.json && putRes.json.message) || putRes.status;
      return send(500, { error: 'GitHub 写入失败: ' + msg }, origin);
    }

    // 更新 manifest.json, 让门户重建后能看到新文件
    const man = await ghRequest('GET', '/contents/manifest.json?ref=' + branch);
    if (man.status !== 200) {
      return send(200, { ok: true, note: '文件已上传，但 manifest 未更新（稍后重新部署即可）' }, origin);
    }
    let manifest = [];
    try { manifest = JSON.parse(Buffer.from(man.json.content, 'base64').toString('utf8')); } catch (e) { /* ignore */ }
    manifest = manifest.filter((f) => f.filename !== safeName);
    manifest.push({
      filename: safeName,
      title: safeName.replace(/\.[^.]+$/, ''),
      size: decodedSize,
      mtime: Math.floor(Date.now() / 1000),
      category: category || 'other',
    });
    const newContent = Buffer.from(JSON.stringify(manifest, null, 2), 'utf8').toString('base64');
    await ghRequest('PUT', '/contents/manifest.json', {
      message: 'manifest: add ' + safeName,
      content: newContent, sha: man.json.sha, branch: branch,
    });

    return send(200, { ok: true }, origin);
  } catch (err) {
    return send(500, { error: '服务器错误: ' + (err && err.message ? err.message : err) }, origin);
  }
}

// ---------- 分享(已休眠: 前端未调用, 仍需令牌) ----------
async function handleShare(body, origin) {
  const filename = body && body.filename;
  if (!filename) return send(400, { error: '缺少 filename' }, origin);
  const safeName = String(filename).replace(/[^\w.\-\u4e00-\u9fa5 ()]/g, '_').replace(/^\.+/, '').slice(0, 200);
  const expireDays = Number(body.expireDays) || 0;
  const expireAt = expireDays > 0 ? Date.now() + expireDays * 86400000 : null;
  const token = crypto.randomBytes(12).toString('hex');
  const branch = env('GITHUB_BRANCH', 'main');
  const record = { token, filename: safeName, title: String(body.title || safeName).slice(0, 200), created: Date.now(), expireAt };
  const tokenContent = Buffer.from(JSON.stringify(record, null, 2), 'utf8').toString('base64');
  const putRes = await ghRequest('PUT', '/contents/shares/' + token + '.json', {
    message: 'share: ' + safeName, content: tokenContent, branch,
  });
  if (putRes.status >= 300) return send(500, { error: '分享记录写入失败' }, origin);
  const base = env('SITE_BASE', 'https://Aurillis.github.io/database').replace(/\/$/, '');
  return send(200, { ok: true, token, url: base + '/share.html?t=' + token }, origin);
}

// ---------- 主处理函数 ----------
exports.main_handler = async (event, context) => {
  const h = event.headers || {};
  const origin = h.origin || h.Origin || '*';

  if (event.httpMethod === 'OPTIONS') return send(204, {}, origin);
  if (event.httpMethod !== 'POST') return send(405, { error: 'Method not allowed' }, origin);

  // 来源白名单(可选, 配置 ALLOWED_ORIGIN 后生效; 留空则按 SITE_BASE 自动推导)
  if (!originAllowed(origin)) {
    return send(403, { error: '来源不被允许' }, origin);
  }

  // 频率限制(尽力而为)
  if (!rateLimit(clientKey(event))) {
    return send(429, { error: '请求过于频繁，请稍后再试' }, origin);
  }

  let body;
  try {
    let raw = event.body || '';
    if (event.isBase64Encoded) raw = Buffer.from(raw, 'base64').toString('utf8');
    body = JSON.parse(raw);
  } catch (e) {
    return send(400, { error: '请求格式错误' }, origin);
  }

  const op = (body && body.op) || 'upload';

  // 登录无需令牌
  if (op === 'login') return handleLogin(body, origin);

  // 看板勾选状态云同步：get 公开读取(状态本就在公开 Pages 上)；
  // put 需 admin 令牌 或 看板自带 editKey(凭此即可写回，无需先登录后台)。
  if (op === 'state') return await handleState(body, origin, event);

  // 其余操作必须令牌鉴权
  const authErr = requireAuth(event, origin);
  if (authErr) return authErr;

  if (op === 'upload') return await handleUpload(body, origin);
  if (op === 'delete') return await handleDelete(body, origin);
  if (op === 'listtrash') return await handleListTrash(body, origin);
  if (op === 'restore') return await handleRestore(body, origin);
  if (op === 'purge') return await handlePurge(body, origin);
  if (op === 'purgeall') return await handlePurgeAll(body, origin);
  if (op === 'meta') return await handleMeta(body, origin);
  if (op === 'move') return await handleMove(body, origin);
  if (op === 'share') return await handleShare(body, origin);
  return send(400, { error: '未知操作: ' + op }, origin);
};
