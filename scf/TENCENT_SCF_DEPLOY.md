# 腾讯云 SCF 部署指南（database 登录 / 上传后端）

> 对应源码：`scf/index.js`
> 安全模型（重构后）：网页里**不再有任何密钥或密码**。登录密码与 GitHub 令牌都只存在于腾讯云函数环境变量。
> 前端 `index.html` 第 431 行的 `UPLOAD_API` 已是你的函数 URL，**更新代码不会改变该地址，前端无需改动**。

---

## 一、准备工作（只需做一次）

### 1. 拿到你的 GitHub 令牌（PAT）
- GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
- `Generate new token (classic)`，勾选 `repo`
- 生成后立刻复制 `ghp_xxx...`（只显示一次）
- ⚠️ 令牌只粘进下面「步骤三」的环境变量，**不要写进任何文件或聊天**

### 2. 准备两个新密钥（自己生成，不要复用旧 admin123）
- **管理密码 `ADMIN_PASSWORD`**：你自己定的强密码（例如 16 位随机串）。它就是门户查看密码 + 后台登录密码，以后只在腾讯云配，不在网页里。
- **会话密钥 `SESSION_SECRET`**：用于给登录令牌签名，随便一段足够随机的字符串（例如 `openssl rand -hex 32` 的输出）。

> 生成随机串（任选其一）：
> - `openssl rand -hex 32`
> - 或在线/本地随机密码生成器取 32 位十六进制

### 3. 确认仓库里已有这些文件
- `manifest.json`（文件清单，上传时自动维护）
- `reports/`（上传文件存放处）

---

## 二、打开腾讯云函数控制台

1. [腾讯云控制台](https://console.cloud.tencent.com/) → 搜索「云函数」→ `https://console.cloud.tencent.com/scf`
2. 左侧「函数管理」→ 找到你的函数（函数名应含 `1461447139`）
3. 点函数名进入详情页

---

## 三、更新函数代码 + 环境变量（核心步骤）

1. 函数详情页点 **「函数代码」** 标签
2. 运行时选 **Node.js 16 / 18 / 20**（任选，仅用内置模块）
3. **清空**编辑器里原有 `index.js`，把本项目 `scf/index.js` 完整内容**整段粘贴**（或点「上传」选本地 `scf/index.js`）
4. **不要急着部署**——先配好环境变量（见下），再一起部署

### 配置环境变量（同页下方「环境变量」区）
点「编辑」→「新增变量」，逐条添加（值不要带引号）：

| 变量名 | 值 | 说明 |
|--------|-----|------|
| `GITHUB_TOKEN` | `ghp_xxx...你的令牌` | 从「一.1」复制，**只在此处填写** |
| `ADMIN_PASSWORD` | `你自己定的强密码` | **新增**：门户查看密码 + 后台登录密码，取代旧 admin123。务必改成强密码 |
| `SESSION_SECRET` | `一段随机串` | **新增**：令牌签名密钥，用「一.2」生成的随机串 |
| `GITHUB_REPO` | `Aurillis/database` | 仓库名 |
| `GITHUB_BRANCH` | `main` | 部署分支 |
| `ALLOWED_ORIGIN` | `https://Aurillis.github.io` | **推荐**：限定请求来源，挡掉其它站点调用 |
| `MAX_UPLOAD_BYTES` | `15728640` | 可选，上传大小上限（默认 15MB，单位字节） |

> ⚠️ **不再需要 `UPLOAD_SECRET` 变量**——新后端已废弃它，改用 `ADMIN_PASSWORD` + 令牌鉴权。
> ⚠️ 若 `ADMIN_PASSWORD` 或 `SESSION_SECRET` 为空，登录会返回 500，请务必填好。

---

## 四、部署并开启 Function URL

1. 配好代码和环境变量后，点右上角 **「部署」**（Deploy）
2. 部署成功后切到 **「触发管理」** 标签 → **「创建触发方式」**
   - 触发类型：选 **Function URL**（或「API 网关 / URL 路径」）
   - 鉴权方法：**「免鉴权」**（前端浏览器直接 POST，必须免鉴权；真正保护靠 `ADMIN_PASSWORD` / 令牌 与 GitHub 令牌不出后端）
   - 勾选支持 `POST`
3. 得到 URL：`https://1461447139-m5rkq2fg8n.ap-guangzhou.tencentscf.com`
   - **应和前端 `index.html` 第 431 行 `UPLOAD_API` 一致** → 不用改前端
   - 若地址变了，把新地址粘回 `index.html` 第 431 行并重新推送（见第五步）

---

## 五、（仅当 URL 变化时才需要）同步前端

```bash
# 编辑 index.html 第 431 行： var UPLOAD_API = '新的函数URL';
git add index.html
git commit -m "update UPLOAD_API to new SCF url"
git push origin main
```

> 本次只是更新代码，URL 通常不变，**这步可跳过**。

---

## 六、验证是否生效

1. 打开线上门户 `https://Aurillis.github.io/database/`
2. 查看闸门输入**新的 `ADMIN_PASSWORD`** 解锁（不再是 admin123）
3. 右上角点「管理员」→ 用同一密码登录后台
4. 在后台「上传文件」选一个文件上传 → 应提示上传成功，约 1 分钟后列表中可见
5. 上传失败看控制台：401=密码错/未登录；500=环境变量没配齐（`ADMIN_PASSWORD`/`SESSION_SECRET`）

---

## 常见问题

**Q：解锁/登录都失败，控制台报 500「未配置 ADMIN_PASSWORD」？**
- 环境变量 `ADMIN_PASSWORD` 没填或留空。去腾讯云控制台填上你定的强密码，重新「部署」。

**Q：上传报 401「未授权」？**
- 多半是 `ADMIN_PASSWORD` 与你在门户输入的密码不一致，或登录已过期（令牌 24 小时有效）。重新登录后台即可。

**Q：函数 URL 必须免鉴权吗？**
- 必须。前端浏览器直接 POST，开启鉴权会挡掉正常上传。安全性靠三点保证：
  1. 密码 `ADMIN_PASSWORD` 只在腾讯云环境变量，**不进网页源码**；
  2. 登录成功后端下发签名令牌（HMAC-SHA256，含 `SESSION_SECRET` 签名、24h 过期），网页只存令牌不存密码；
  3. `GITHUB_TOKEN` 永远只在函数环境变量，绝不进浏览器。
- 任何拿到函数 URL 的人，没有正确密码拿不到令牌，也就无法上传或读取任何东西。

**Q：想换管理密码 / GitHub 令牌怎么办？**
- 只在腾讯云控制台改 `ADMIN_PASSWORD` 或 `GITHUB_TOKEN` 环境变量 → 重新「部署」即可，前端不用动。
- 改 `ADMIN_PASSWORD` 后，旧的登录令牌立即失效，所有人需重新输入新密码。

**Q：令牌会过期吗？**
- 会，默认 24 小时。过期后上传/后台操作返回 401，重新登录即可刷新令牌。
