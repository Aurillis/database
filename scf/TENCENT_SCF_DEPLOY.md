# 腾讯云 SCF 部署指南（report-portal 上传/分享后端）

> 本文件对应的源码：`scf/index.js`
> 本次更新重点：`op:'share'` 改为每篇独立写入 `shares/<token>.json`（避免通过全局 shares.json 反查其他分享）。
> 前端 `index.html` 第 431 行的 `UPLOAD_API` 已是你的函数 URL，**本次更新代码不会改变该地址，前端无需改动**。

---

## 一、准备工作（只需做一次）

### 1. 拿到你的 GitHub 令牌（PAT）
- 打开 GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
- 点 `Generate new token (classic)`
- 勾选 `repo`（整库读写权限）
- 生成后**立刻复制**那一串 `ghp_xxx...`（只显示这一次，关掉就没了）
- ⚠️ 令牌只粘进下面「步骤三」的腾讯云环境变量里，**不要写进任何文件或聊天**

### 2. 确认仓库里已有这些文件
前端上传/分享依赖仓库根目录的：
- `manifest.json`（文件清单，上传时自动维护）
- `reports/`（上传文件存放处）
- `shares/`（本次新增：每篇分享独立存放，**首次部署前可先建一个空的 `shares/` 目录并提交**，否则第一篇文章会由函数自动创建）

> 小技巧：在 GitHub 网页上 `shares/` 目录里随便传一个 `.gitkeep` 空文件即可创建该目录。

---

## 二、打开腾讯云函数控制台

1. 登录 [腾讯云控制台](https://console.cloud.tencent.com/) → 搜索「云函数」或直接访问
   `https://console.cloud.tencent.com/scf`
2. 左侧「函数管理」→ 找到你已有的函数（函数名里应含 `1461447139` 或你当初起的名）
3. 点函数名进入详情页

---

## 三、更新函数代码（核心步骤）

1. 在函数详情页点 **「函数代码」** 标签
2. 运行时请选 **Node.js 16 / 18 / 20**（任选，本代码仅用内置模块，都兼容）
3. **清空**编辑器里原有的 `index.js` 内容
4. 把本项目 `scf/index.js` 的完整内容**整段复制粘贴**进去
   - 也可以点「上传」直接选本地 `scf/index.js` 文件
5. **不要急着保存**——先去配环境变量（见下一步），再一起部署

### 配置环境变量（同一页面下方「环境变量」区）
点「编辑」→「新增变量」，逐条添加（值不要带引号）：

| 变量名 | 值 | 说明 |
|--------|-----|------|
| `GITHUB_TOKEN` | `ghp_xxx...你的令牌` | 从第「一.1」步复制，**只在此处填写** |
| `UPLOAD_SECRET` | `admin123` | 前端上传密码，须与前端一致 |
| `GITHUB_REPO` | `chenbiyin1770/report-portal` | 你的仓库名 |
| `GITHUB_BRANCH` | `main` | 部署分支 |
| `SITE_BASE` | `https://chenbiyin1770.github.io/report-portal` | 分享链接域名前缀 |

> 其余变量用代码里的默认值即可，不必全配。

---

## 四、部署并开启 Function URL

1. 配好代码和环境变量后，点页面右上角 **「部署」**（Deploy）
2. 部署成功后，切换到 **「触发管理」** 标签
3. 点 **「创建触发方式」**
   - 触发类型：选 **API 网关 / 函数 URL**（不同版本叫法不同，认 `Function URL` 或「URL 路径」）
   - 鉴权方法：选 **「免鉴权」**（前端浏览器要直接 POST，必须免鉴权；真正的保护靠 `UPLOAD_SECRET` 和 GitHub 令牌不出后端）
   - 勾选支持 `POST`（分享/上传都是 POST）
4. 创建后会得到一个 URL，形如：
   `https://1461447139-m5rkq2fg8n.ap-guangzhou.tencentscf.com`
   - **它应该和你前端 `index.html` 第 431 行的 `UPLOAD_API` 一致** → 不用改前端
   - 如果地址变了，把新地址粘回 `index.html` 第 431 行并重新推送（见第五步）

---

## 五、（仅当 URL 变化时才需要）同步前端

```bash
# 编辑 index.html 第 431 行：
#   var UPLOAD_API = '新的函数URL';
# 然后：
git add index.html
git commit -m "update UPLOAD_API to new SCF url"
git push origin main
```

> 本次只是更新代码，URL 通常不变，**这步可跳过**。

---

## 六、验证是否生效

1. 打开线上门户 `https://chenbiyin1770.github.io/report-portal/` → 输入密码 `admin123` 解锁
2. 任意文件卡片点 **📤 分享** → 选有效期 → 点「生成链接」
3. 复制 `share.html?t=xxxx` 链接，用无痕窗口打开
4. 应只看到**这一篇**文件，且页面没有任何「回到网站」出口
5. 回到 GitHub 仓库，应能看到 `shares/<token>.json` 这个新文件被自动创建（证明独立存放已生效）

---

## 常见问题

**Q：点「生成链接」报错 / 401？**
- 多半是 `UPLOAD_SECRET` 没配或值和前端不一致（必须都是 `admin123`）。
- 也可能是 `GITHUB_TOKEN` 失效/权限不足，重新生成一个 `repo` 权限的 PAT 填进环境变量并重新部署。

**Q：分享链接打开是空白/加载失败？**
- 确认 `shares/` 目录已在仓库存在（见准备二.2）；第一篇文章会自动创建，但保险起见先建好。
- 硬刷新（Ctrl+Shift+R）排除缓存。

**Q：函数 URL 必须免鉴权吗？**
- 必须。前端浏览器直接 POST，若开启鉴权会挡掉正常上传/分享。安全性靠两点保证：
  1. `UPLOAD_SECRET` 只在请求头 `x-upload-secret` 里出现，且后端只认它来上传；
  2. `GITHUB_TOKEN` 永远只在函数环境变量里，绝不进浏览器。
- 任何拿到函数 URL 的人最多只能「上传文件」和「生成分享」，拿不到你的 GitHub 账号控制权。

**Q：想换 GitHub 令牌怎么办？**
- 只在腾讯云控制台改 `GITHUB_TOKEN` 环境变量 → 重新「部署」即可，前端不用动。
