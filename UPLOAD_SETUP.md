# 上传功能后端部署指南（方案 B：安全后端代理）

本目录下的 `api/upload.js` 是一个 Vercel Serverless Function，负责把网页上传的文件写回 GitHub 仓库。
**GitHub 令牌只存在于服务端环境变量中，永远不进网页源码。**

## 第一步：准备 GitHub 令牌（细粒度，只授权本仓库）

1. 打开 https://github.com/settings/tokens?type=beta
2. Generate new token → Fine-grained token
3. Name: `database-upload`
4. Expiration: 选最长（1 年）
5. Resource owner: `Aurillis`
6. Repository access: Only select repositories → 勾选 `database`
7. Permissions → Repository permissions → **Contents** → Read and write
8. Generate token → **复制 `github_pat_...` 令牌**

## 第二步：部署到 Vercel

1. 打开 https://vercel.com ，用 GitHub 账号登录（免费）
2. Add New Project → 选择导入 `database` 仓库
   - Framework Preset 选 **Other** 或不选
   - Vercel 会自动把 `api/upload.js` 识别为服务端函数
3. 先点 Deploy（先不填环境变量也能部署成功，只是上传还不能用）
4. 部署完成后，进入项目 Settings → Environment Variables，添加：
   | 名称 | 值 |
   |------|-----|
   | `GITHUB_TOKEN` | 第一步复制的 `github_pat_...` 令牌 |
   | `GITHUB_REPO` | `Aurillis/database` |
   | `GITHUB_BRANCH` | `main` |
   | `UPLOAD_SECRET` | 一个上传密码（建议和网站管理密码 `admin123` 设为相同，方便记忆） |
5. 改完环境变量后，回到 Deployments 页面 **Redeploy**（让环境变量生效）
6. 记下你的函数地址，格式类似：
   `https://database-xxxxxxxx.vercel.app/api/upload`

## 第三步：把函数地址填进网站

把上面得到的 `/api/upload` 完整地址告诉 AI（或自己改 `gen_kb.py` 里的 `UPLOAD_API_PLACEHOLDER`），
AI 会重新生成 `index.html` 并发到 GitHub Pages。

## 验证

1. 打开 https://Aurillis.github.io/database/
2. 点右上角齿轮 → 输入管理密码登录 → 文件上传
3. 选一个 .html 文件上传
4. 约 1 分钟后刷新页面，新文件应出现在对应分类下

## 安全说明

- GitHub 令牌只在 Vercel 服务端，网页源码里看不到
- 上传需要 `UPLOAD_SECRET`（即管理密码），陌生人不知道密码就无法上传
- 令牌权限被锁死在 `database` 这一个仓库，动不了你 GitHub 其他东西
- 单文件大小建议 < 4 MB（Vercel 函数请求体限制）
