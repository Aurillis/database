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
//   POST {op:'share', ...}                            -> 需带 x-admin-token(前端已未调用)
//
// 服务端限制: 来源白名单 / 文件类型白名单 / 大小上限 / 频率限制 / 覆盖前自动备份
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
const ALLOWED_ORIGIN = env('ALLOWED_ORIGIN', '');                      // 例如 https://chenbiyin1770.github.io
const MAX_UPLOAD_BYTES = Number(env('MAX_UPLOAD_BYTES', 15 * 1024 * 1024)); // 默认 15MB
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
      path: '/repos/' + env('GITHUB_REPO', 'chenbiyin1770/report-portal') + path,
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

// ---------- 上传 ----------
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
  const base = env('SITE_BASE', 'https://chenbiyin1770.github.io/report-portal').replace(/\/$/, '');
  return send(200, { ok: true, token, url: base + '/share.html?t=' + token }, origin);
}

// ---------- 主处理函数 ----------
exports.main_handler = async (event, context) => {
  const h = event.headers || {};
  const origin = h.origin || h.Origin || '*';

  if (event.httpMethod === 'OPTIONS') return send(204, {}, origin);
  if (event.httpMethod !== 'POST') return send(405, { error: 'Method not allowed' }, origin);

  // 来源白名单(可选, 配置 ALLOWED_ORIGIN 后生效)
  if (ALLOWED_ORIGIN && origin !== ALLOWED_ORIGIN) {
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

  // 其余操作必须令牌鉴权
  const authErr = requireAuth(event, origin);
  if (authErr) return authErr;

  if (op === 'upload') return await handleUpload(body, origin);
  if (op === 'share') return await handleShare(body, origin);
  return send(400, { error: '未知操作: ' + op }, origin);
};
