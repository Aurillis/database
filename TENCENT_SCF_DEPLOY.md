# 迁移上传后端到腾讯云 SCF（不用 VPN 也能上传）

本指引把 report-portal 的「网页上传」后端从 Vercel（国内常被墙）迁到**腾讯云 SCF 云函数 + 函数 URL（Function URL）触发器**。

- 优点：国内直连、**不用 VPN**、免费额度足够、安全架构不变（GitHub 令牌只在服务器端）。
- 前提：有腾讯云账号并完成**实名认证**（国内云平台必做，几分钟）。

---

## 第 1 步：准备函数代码

本仓库 `scf/index.js` 就是函数代码（已写好，直接复制即可）。
要点：
- 入口 `exports.main_handler(event, context)`；
- 仅用 Node 内置模块，无需 `npm install`；
- 运行时选 **Node.js 18 / 20** 任一都行（建议 18 或 20）。

---

## 第 2 步：创建云函数

1. 打开 https://console.cloud.tencent.com/scf （云函数 SCF 控制台）。
2. 左上角**地域**选一个离你近的，例如「广州」或「上海」。
3. 点 **新建**（或「函数服务」→「新建函数」）。
4. 创建方式：**从头开始 / 空白函数**。
5. 函数名称：`report-portal-upload`（随便起）。
6. 运行环境：**Node.js 18.15 / 20**（选一个）。
7. 函数类型：**事件函数**（不要选 Web 函数，我们用函数 URL 触发器）。
8. 提交后进入函数详情 → **函数代码**：
   - 把默认的 `index.js` 内容**全部删掉**，粘贴本仓库 `scf/index.js` 的内容。
   - 点**保存并部署**。

---

## 第 3 步：配置环境变量（关键）

在函数详情页切到 **函数配置** → **环境变量**，点「编辑」，添加以下 4 项：

| 键 | 值 | 说明 |
|----|----|------|
| `GITHUB_TOKEN` | 你的 fine-grained PAT | 细粒度令牌，仅授权 `report-portal` 仓库的 Contents: Read/Write。建议勾「加密存储」。 |
| `GITHUB_REPO` | `chenbiyin1770/report-portal` | 仓库名（用户名/仓库名）。 |
| `GITHUB_BRANCH` | `main` | 分支。 |
| `UPLOAD_SECRET` | `admin123` | 上传密钥，必须和前端一致（前端固定发这个值）。 |

> 如果之前 Vercel 用的就是同一个 fine-grained 令牌，这里**直接复用**即可，不用重新生成。
> 若令牌已失效/泄露，去 GitHub → Settings → Developer settings → Personal access tokens → fine-grained 重新生成一个，只勾 `report-portal` 仓库、Contents 读写权限。

保存后**重新部署**（函数配置页右上角「部署」或代码页「保存并部署」）。

---

## 第 4 步：开启函数 URL（拿到公网地址）

> ⚠️ **重要**：函数 URL **不是**「创建触发器」下拉框里的选项（那个下拉只有定时/COS/Kafka/CLS/MPS/CLB/MQTT/TDMQ 等事件触发器）。函数 URL 在**另一个入口**，见下面。

1. 进入函数详情页，在**左侧菜单**找 **「函数 URL」** 或 **「访问服务」**（有的控制台版本叫"访问服务"，点进去就能看到"函数 URL"）。
   - 如果左侧没有，就点 **触发管理**，页面里通常会有一个 **「函数 URL」子标签**（和"触发器"并列），切过去。
2. 点 **创建 / 启用函数 URL**：
   - **鉴权方式**：选 **不校验（PUBLIC）**——因为我们的密码校验写在代码里（`UPLOAD_SECRET`），不用云平台的鉴权再挡一层。
   - 其余默认，提交。
3. 启用后会出现一个公网地址，形如：
   ```
   https://你的函数ID.scf.tencentcs.com
   ```
   或
   ```
   https://1234567890-gz-xxx.gz.tencentscf.com
   ```
   **把这个完整 URL 复制下来发给我**（后面要填进前端）。

> 函数 URL 直接就是一个公网 HTTP(S) 地址，**不需要再配置 API 网关**，也不在那堆事件触发器里。
> 本函数**不需要路径后缀**，直接把请求 POST 到这个 URL 即可，所以请把**原样 URL**发我。

---

## 第 5 步：CORS 跨域（已在代码里处理）

前端页面在 `chenbiyin1770.github.io` 下，浏览器会因跨域拦截响应。

本函数代码已经自动返回以下 CORS 响应头：
```
Access-Control-Allow-Origin: https://chenbiyin1770.github.io
Access-Control-Allow-Methods: POST, OPTIONS
Access-Control-Allow-Headers: Content-Type, x-upload-secret
```

**你不需要额外配置 CORS**，只要函数 URL 触发器创建成功即可。

（如果控制台有「函数 URL CORS」配置项，可以顺手把允许域名填成 `https://chenbiyin1770.github.io`，但不填也不影响，代码会兜底。）

---

## 第 6 步：先用 curl 自测（不用浏览器）

把下面命令里的 `<函数URL>` 换成第 4 步拿到的地址，在**任意有网的机器/你本机**跑：

```bash
curl -X POST "<函数URL>" \
  -H "Content-Type: application/json" \
  -H "x-upload-secret: admin123" \
  -d '{"filename":"scf_test.html","content":"PGh0bWw+SGVsbG88L2h0bWw+","category":"other"}'
```

- `content` 是 `<html>Hello</html>` 的 base64。
- 期望返回：`{"ok":true}`
- 若返回 `{"error":"未授权：上传密码错误"}` → 检查 `UPLOAD_SECRET` 环境变量是否 = `admin123`。
- 若返回 `{"error":"GitHub 写入失败..."}` → 检查 `GITHUB_TOKEN` / `GITHUB_REPO` / `GITHUB_BRANCH`。
- 若连不上 / 超时 → 检查函数是否部署成功、函数 URL 触发器是否启用。

自测通过后，去 GitHub 仓库 `reports/` 目录应该能看到 `scf_test.html`，`manifest.json` 也会被追加一条。
（自测文件可删，不影响。）

---

## 第 7 步：把地址发给我，我改前端并推送

把第 4 步的 **函数 URL** 发给我。我会：
1. 把前端 `UPLOAD_API` 改成腾讯云地址；
2. 顺手把上传错误提示里的「Vercel」字样去掉（改成通用提示）；
3. 重新生成 `index.html` 并推送到 GitHub Pages；
4. 约 1 分钟后你硬刷新 `https://chenbiyin1770.github.io/report-portal/`，齿轮 → `admin123` 登录 → 文件上传 → 选文件，**不用 VPN 即可上传成功**。

---

## 常见问题

**Q：腾讯云 SCF 收费吗？**
A：函数每月 100 万次调用 + 40 万 GBs 资源用量免费；函数 URL 本身按调用次数计费，也有免费额度。你这用量基本**永远免费**。

**Q：国内云平台必须实名吗？**
A：是的，腾讯云/阿里云都需要绑身份证或企业认证，一次性，几分钟。

**Q：函数能访问 GitHub 吗？**
A：能。腾讯云函数出网访问 `api.github.com` 正常（和住宅网络被墙 vercel 不同，云厂商出网不走那套墙）。

**Q：为什么不用 API 网关？**
A：腾讯云 API 网关已停止服务、不再支持新建触发器。函数 URL 是 SCF 原生的 HTTP 入口，更简单、更稳、免费额度足够。

**Q：以后令牌泄露了怎么办？**
A：去 GitHub 撤销/重新生成 fine-grained 令牌，只改 SCF 的 `GITHUB_TOKEN` 环境变量即可，前端不用动。
