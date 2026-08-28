# 调研台 ResearchDeck · 部署指南（腾讯云 SCF + GitHub Pages）

> 本文档配套 `research-deck/`（前端 `index.html` + 后端 `server.py`）。
> 目标：在您现有 report-portal 网站基础上，新增一个**独立调研台页面**，访客凭 Token 使用、Key 由站长统一管控（不泄漏给访客）。

## 安全模型（务必读完）
- **LLM Key 只在后端**：`OPENAI_API_KEY` 等只存在于 SCF 环境变量，前端已移除填 Key 入口，后端也完全忽略前端传来的 `llm.key`。访客拿不到任何 Key。
- **Token 限定**：设置 `RD_TOKEN` 后，所有 `/api/research` 调用必须带此 token，否则返回 401。适合把 token 发给指定的人使用。
- 如果您不设置 `RD_TOKEN`，则完全不鉴权（公网任何人可用，**Live 模式下会刷您的 LLM 额度，不建议**）。

## 第一步：部署后端到腾讯云 SCF（Python 运行时）

1. 登录[腾讯云云函数控制台](https://console.cloud.tencent.com/scf)，地域选 **广州**（与现有 `report-portal-upload` 一致）。
2. 新建函数：
   - 函数类型：**Web 函数**（或「事件函数 + API 网关」均可；`server.py` 已含 `main_handler` 适配）
   - 函数名称：`researchdeck`
   - 运行环境：**Python 3.10**（或 3.9+）
   - 提交方法：**本地上传 zip** 或在线编辑
3. 上传内容：把 `server.py` 作为入口文件（保证函数根目录有 `server.py`，且 `main_handler` 可被调用）。
   - 若是「Web 函数」：`scf_bootstrap` 可写 `python server.py`（走内置 http.server 端口 8765），或用 `main_handler` 集成响应模式。
   - 若是「事件函数 + API 网关」：API 网关后端指向 `main_handler`，集成响应开启。
4. 配置**环境变量**（函数配置 → 环境变量）：

   | 键 | 值 | 说明 |
   |---|---|---|
   | `OPENAI_API_KEY` | 您的 DeepSeek / OpenAI Key | **必填**（Live 模式） |
   | `OPENAI_BASE_URL` | `https://api.deepseek.com/v1` | DeepSeek 填这个 |
   | `OPENAI_MODEL` | `deepseek-chat` | 模型名 |
   | `RD_TOKEN` | 您自定的访问令牌，如 `rd_xxxx1234` | Token 限定必需 |
   | `PORT` | `8765` | 本地/Web 函数监听端口（可选） |

   > 用 OpenAI 官方时：`OPENAI_BASE_URL` 留空（默认 `https://api.openai.com/v1`），`OPENAI_MODEL` 如 `gpt-4o-mini`。
5. 保存并**部署**。记录函数的**访问路径 / API 网关 URL**，形如：
   `https://<your-api-id>.apigw.tencentcs.com/release/`（或 `.tencentscf.com`）。

## 第二步：配置前端指向后端

前端 `index.html` 通过 `?backend=` 参数连接后端。两种用法：

- **手动**：访客打开 `https://Aurillis.github.io/database/research-deck/index.html?backend=https://<您的SCF网关>`。
- **固定（推荐）**：在您网站首页/导航增加一个入口链接，直接带好 backend 参数，访客无需手动填。

> 注意：GitHub Pages 是静态托管，`research-deck/index.html` 在仓库 `research-deck/` 目录下；推送后约 1~2 分钟即可通过 `https://Aurillis.github.io/database/research-deck/index.html` 访问。

## 第三步：访客使用流程

1. 访客打开链接 → 左侧「访问令牌」框输入您发给他的 `RD_TOKEN` → 保存。
2. 输入主题、勾选维度 → 选「模板数据」（离线快照）或「大模型实时生成（DeepSeek）」。
3. 点生成 → 后端用自己的 Key 调 LLM → 返回报告。访客全程不接触 Key。

## 验证清单
- [ ] SCF 函数状态「正常」，环境变量已填（尤其 `OPENAI_API_KEY`、`RD_TOKEN`）。
- [ ] `GET <网关>/api/status` 返回 `backendMode: "live"`、`llm: true`。
- [ ] 不带 token 调 `/api/research` 返回 **401**（确认 Token 限定生效）。
- [ ] 带正确 token 调 `/api/research` 返回报告 JSON。
- [ ] 浏览器开发者工具 Network 中，**请求体不再含 `llm.key` 字段**（确认 Key 不外泄）。

## 与现有 report-portal 的关系
- 本调研台是**独立模块**：新增 `research-deck/` 目录，不动现有 `index.html` / `scf/index.js` / 知识库数据。
- 后端是**新的 Python SCF 函数** `researchdeck`，与现有 Node.js 函数 `report-portal-upload` 互不干扰。
- 复用同一 GitHub Pages 站点，仅多一个子路径页面。
