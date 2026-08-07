// Vercel Serverless Function — handles file uploads for the report portal.
// The GitHub token lives ONLY here (as an env var), never in the frontend.
//
// Required environment variables (set in Vercel dashboard):
//   GITHUB_TOKEN   — fine-grained PAT with Contents: Read/Write on the repo
//   GITHUB_REPO    — e.g. chenbiyin1770/report-portal
//   GITHUB_BRANCH  — main
//   UPLOAD_SECRET  — a password the frontend must send to be allowed to upload
//
// Endpoint: POST /api/upload
// Body: { filename, content (base64, no data-URL prefix), category }

export default async function handler(req, res) {
  // CORS: echo the caller's origin so the browser never blocks the response.
  // Security is NOT provided by CORS — it's enforced by the x-upload-secret check below.
  const reqOrigin = req.headers.origin;
  res.setHeader('Access-Control-Allow-Origin', reqOrigin || '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, x-upload-secret');
  res.setHeader('Vary', 'Origin');

  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  // 1. Verify upload secret (the frontend sends the admin password as this).
  const secret = req.headers['x-upload-secret'];
  if (!secret || secret !== process.env.UPLOAD_SECRET) {
    return res.status(401).json({ error: '未授权：上传密码错误' });
  }

  // 2. Parse body (Vercel may give an object or a raw string).
  let body = req.body;
  if (typeof body === 'string') {
    try { body = JSON.parse(body); } catch (e) { return res.status(400).json({ error: '请求格式错误' }); }
  }
  const { filename, content, category } = body || {};
  if (!filename || !content) {
    return res.status(400).json({ error: '缺少 filename 或 content' });
  }

  // 3. Sanitize filename (block path traversal, enforce extension).
  const safeName = String(filename)
    .replace(/[^\w.\-\u4e00-\u9fa5 ()]/g, '_')  // keep word chars, dot, dash, CJK, spaces, parens
    .replace(/^\.+/, '')                         // no leading dots
    .slice(0, 200);
  if (!safeName.match(/\.(html?|css|js|png|jpe?g|gif|svg)$/i)) {
    return res.status(400).json({ error: '不支持的文件格式' });
  }

  const token = process.env.GITHUB_TOKEN;
  const repo = process.env.GITHUB_REPO || 'chenbiyin1770/database';
  const branch = process.env.GITHUB_BRANCH || 'main';
  const apiBase = 'https://api.github.com/repos/' + repo;
  const ghHeaders = {
    'Authorization': 'Bearer ' + token,
    'Accept': 'application/vnd.github+json',
    'Content-Type': 'application/json',
    'X-GitHub-Api-Version': '2022-11-28',
    'User-Agent': 'report-portal-upload',
  };

  try {
    // 4. Upload the file into reports/ (create or update).
    const filePath = 'reports/' + encodeURIComponent(safeName);
    const head = await fetch(apiBase + '/contents/' + filePath + '?ref=' + branch, { headers: ghHeaders });
    let sha = null;
    if (head.status === 200) { const j = await head.json(); sha = j.sha; }

    const putBody = { message: 'upload: ' + safeName, content: content, branch: branch };
    if (sha) putBody.sha = sha;
    const putRes = await fetch(apiBase + '/contents/' + filePath, {
      method: 'PUT', headers: ghHeaders, body: JSON.stringify(putBody),
    });
    if (putRes.status >= 300) {
      const err = await putRes.json().catch(() => ({}));
      return res.status(500).json({ error: 'GitHub 写入失败: ' + (err.message || putRes.status) });
    }

    // 5. Update manifest.json so the portal shows the new file after rebuild.
    const manRes = await fetch(apiBase + '/contents/manifest.json?ref=' + branch, { headers: ghHeaders });
    if (manRes.status !== 200) {
      return res.status(200).json({ ok: true, note: '文件已上传，但 manifest 未更新（稍后重新部署即可）' });
    }
    const manJ = await manRes.json();
    let manifest = [];
    try { manifest = JSON.parse(Buffer.from(manJ.content, 'base64').toString('utf8')); } catch (e) {}
    manifest = manifest.filter((f) => f.filename !== safeName);
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
    await fetch(apiBase + '/contents/manifest.json', {
      method: 'PUT', headers: ghHeaders,
      body: JSON.stringify({
        message: 'manifest: add ' + safeName,
        content: newContent, sha: manJ.sha, branch: branch,
      }),
    });

    return res.status(200).json({ ok: true });
  } catch (err) {
    return res.status(500).json({ error: '服务器错误: ' + (err.message || err) });
  }
}
