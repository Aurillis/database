'use strict';
// =====================================================================
// 腾讯云 SCF (云函数) 上传后端 —— 用于 report-portal 的网页上传功能
//
// 安全模型(和原 Vercel 版本一致):
//   GitHub 令牌 (GITHUB_TOKEN) 只存在本函数的环境变量里,永远不会进浏览器。
//   浏览器只发一个上传密钥 (UPLOAD_SECRET=admin123),拿到它最多只能上传,
//   拿不到 GitHub 令牌,也动不了你的 GitHub 账号。
//
// 入口: exports.main_handler (腾讯云事件函数 + 函数 URL / Function URL 触发器)
// 依赖: 仅 Node 内置模块 (https / Buffer),无需安装任何 npm 包。
//
// 部署方式见同目录 TENCENT_SCF_DEPLOY.md
// =====================================================================

const https = require('https');

// 不限制上传的文件后缀——支持任意文件类型。
// 真正的保护是下方的「文件名安全过滤」(防路径穿越),而不是后缀白名单。
// const ALLOWED_EXT = /\.(html?|css|js|png|jpe?g|gif|svg)$/i;  // 已放开:允许所有类型

function env(name, def) {
  return process.env[name] !== undefined ? process.env[name] : def;
}

// ---------- GitHub REST 调用(用内置 https,兼容 Node 12/16/18/20) ----------
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

// ---------- 统一返回 API 网关兼容的响应结构 ----------
function send(statusCode, obj, origin) {
  return {
    statusCode: statusCode,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Access-Control-Allow-Origin': origin || '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, x-upload-secret',
    },
    isBase64Encoded: false,
    body: JSON.stringify(obj),
  };
}

// ---------- 主处理函数 ----------
exports.main_handler = async (event, context) => {
  const origin = (event.headers &&
    (event.headers.origin || event.headers.Origin)) || '*';

  // API 网关通常会自己处理 OPTIONS 预检(CORS 开启后);这里也兜底处理一下
  if (event.httpMethod === 'OPTIONS') return send(204, {}, origin);
  if (event.httpMethod !== 'POST') return send(405, { error: 'Method not allowed' }, origin);

  // 1. 校验上传密钥(浏览器发的是 UPLOAD_SECRET)
  const secret = event.headers &&
    (event.headers['x-upload-secret'] || event.headers['X-Upload-Secret']);
  if (!secret || secret !== env('UPLOAD_SECRET', 'admin123')) {
    return send(401, { error: '未授权：上传密码错误' }, origin);
  }

  // 2. 解析请求体(API 网关可能把 body 以 base64 传过来)
  let body;
  try {
    let raw = event.body || '';
    if (event.isBase64Encoded) raw = Buffer.from(raw, 'base64').toString('utf8');
    body = JSON.parse(raw);
  } catch (e) {
    return send(400, { error: '请求格式错误' }, origin);
  }

  const { filename, content, category } = body || {};
  if (!filename || !content) {
    return send(400, { error: '缺少 filename 或 content' }, origin);
  }

  // 3. 文件名安全过滤(防路径穿越) —— 允许任意文件类型
  const safeName = String(filename)
    .replace(/[^\w.\-\u4e00-\u9fa5 ()]/g, '_')  // 保留字母数字、点、横杠、中文、空格、括号
    .replace(/^\.+/, '')                         // 不允许开头是点
    .slice(0, 200);
  // 不再限制扩展名:支持所有文件类型上传(保护靠上面的安全过滤即可)

  const branch = env('GITHUB_BRANCH', 'main');
  const filePath = '/contents/reports/' + encodeURIComponent(safeName);

  try {
    // 4. 上传文件到 reports/(新建或更新)
    const head = await ghRequest('GET', filePath + '?ref=' + branch);
    const sha = (head.json && head.json.sha) || null;

    const putBody = { message: 'upload: ' + safeName, content: content, branch: branch };
    if (sha) putBody.sha = sha;
    const putRes = await ghRequest('PUT', filePath, putBody);
    if (putRes.status >= 300) {
      const msg = (putRes.json && putRes.json.message) || putRes.status;
      return send(500, { error: 'GitHub 写入失败: ' + msg }, origin);
    }

    // 5. 更新 manifest.json,让门户重建后能看到新文件
    const man = await ghRequest('GET', '/contents/manifest.json?ref=' + branch);
    if (man.status !== 200) {
      return send(200, { ok: true, note: '文件已上传，但 manifest 未更新（稍后重新部署即可）' }, origin);
    }
    let manifest = [];
    try { manifest = JSON.parse(Buffer.from(man.json.content, 'base64').toString('utf8')); } catch (e) { /* ignore */ }
    manifest = manifest.filter((f) => f.filename !== safeName);
    // 根据 base64 长度估算解码后字节数
    const decodedSize = Math.max(0, Math.floor(content.length * 3 / 4)
      - (content.endsWith('==') ? 2 : content.endsWith('=') ? 1 : 0));
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
};
