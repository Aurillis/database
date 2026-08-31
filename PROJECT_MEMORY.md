# report-portal 项目记忆（云端对话版）

> 本文件是云端对话的持续记忆。**现已移入 git 仓库根目录并 commit+push 到 GitHub**，因此换沙箱/换对话均可 `git clone Aurillis/database` 后直接读取，不会因对话丢失。
> 配套完整设计规格见同目录 **`DESIGN.md`**（架构/数据模型/页面/功能/API/红线/版本全在其中）。
> **新对话接续方式**：把本文件 + `DESIGN.md` 内容发给助手，并指向仓库 `Aurillis/database` 的 `research-deck/` 目录即可。
> 由本地对话迁移：2026-08-26。工作基地：云端沙箱 `/workspace/report-portal/`。

## 基本信息
- 知识库门户站点：GitHub Pages `https://Aurillis.github.io/database/` + 腾讯云 SCF `report-portal-upload`（函数地址 `https://1461447139-m5rkq2fg8n.ap-guangzhou.tencentscf.com`，POST JSON，GET 返回 405 属正常）。
- 仓库 `Aurillis/database` 分支 `main`，云端工作区 `/workspace/report-portal/`。
- 唯一持续修改文件：`index.html`（前端）；后端 `scf/index.js`。

## 云端环境要点（2026-08-26 实测）
- **GitHub 直连不通**（github.com / api.github.com / raw / pages 全部超时），走镜像：
  - 克隆/拉取：`https://gh-proxy.com/https://github.com/Aurillis/database.git`（快，约 0.6s）或 `https://ghproxy.net/...`
  - 读单文件：`https://gh-proxy.com/https://raw.githubusercontent.com/Aurillis/database/main/<path>`
  - 网页信息核对：用内置 WebFetch 工具直访 github.com（该通道不受限）。
- **腾讯云 SCF 直连正常**（实测 `op:getmanifest` 返回 ok）。
- 沙箱无用户本地代理（旧记忆里的 `http://127.0.0.1:7897` 仅适用于用户本地机器，云端忽略）。

## 云端 git 推送通道（2026-08-26 已配置并验证）
- **PAT 已配置**：用户提供的 Fine-grained token（授权 `database` 仓库 Contents 读写）。已通过 `git ls-remote` + `push --dry-run` 验证认证与写权限均有效。
- **实现方式**（沙箱全局 `~/.gitconfig` + `~/.git-credentials`）：
  - `url."https://gh-proxy.com/https://github.com/".insteadOf "https://github.com/"` —— 所有 github.com 访问走 gh-proxy 镜像。
  - `credential.helper store` + `~/.git-credentials` 存 `https://x-access-token:<PAT>@gh-proxy.com`（token 不进仓库 config，不进 /workspace 任何文件）。
  - remote `origin` = `https://github.com/Aurillis/database.git`（被 insteadOf 重写走镜像）。
  - 已设 `user.name=Aurillis`、`user.email=aurillis@users.noreply.github.com`、`http.sslVerify=false`。
- **日常用法**：直接 `git fetch` / `git pull --rebase origin main` / `git push origin main` 即可，无需手动带 token。
- ⚠️ **token 过期提醒**：GitHub Fine-grained token 必有过期日（无真正永久）。过期后 push 会失败（fetch 仍可能匿名限速）。届时需用户重新生成 PAT 发予助手，重跑本段配置即可。助手应在到期前主动提醒。本地工作区与记忆不存明文 token。

## 调研台模块 ResearchDeck（2026-08-29 新增）
- **位置**：仓库 `research-deck/`（`index.html` 前端 + `server.py` 后端 + `DEPLOY.md` 部署指南）。独立于现有知识库，不碰 `index.html`/`scf/index.js`/数据。
- **用户需求**：把调研台挂上网站，让别人能用它调研。结论：能做「别人能用调研台」，但不能做「别人登录数据库」（那等于暴露仓库/Key，不安全）。
- **形态**：独立调研台页面（GitHub Pages 子路径）+ 新建 Python SCF 函数 `researchdeck`。
- **安全底线（用户强调：Key 绝不能泄漏）**：
  - 前端已**移除 DeepSeek Key 输入框**；后端 `server.py` 强制只用服务端 `LLM_KEY` 环境变量，**完全忽略前端传入的 `llm.key`**（即便手搓请求也只用自己的 Key）。
  - Key 仅存 SCF 环境变量，不进网页、不进仓库。
  - **Token 限定**：设 `RD_TOKEN` 后 `/api/research` 必须带 token（401 否则）；前端侧边栏 token 输入 + 401 引导。
- **数据源**：`template`（离线卖家精灵快照）/ `llm`（后端 DeepSeek 实时，Key 由站长统一管控）。LLM 提供方：用户选 **DeepSeek**（`OPENAI_BASE_URL=https://api.deepseek.com/v1`，`OPENAI_MODEL=deepseek-chat`）。
- **状态：已全部上线并验证通过（2026-08-29）**：
  - ✅ SCF Web 函数 `researchdeck_web`（Python 3.9）公网 URL：`https://1461447139-ds1sdwfe7p.ap-guangzhou.tencentscf.com`（函数名 `researchdeck_web`）
  - ✅ 环境变量已配：`OPENAI_API_KEY`（DeepSeek）、`OPENAI_BASE_URL`、`OPENAI_MODEL=deepseek-chat`、`RD_TOKEN=au.26611`
  - ✅ 真实 AI 调研验证通过（DeepSeek 生成完整报告，30s 超时内返回）
  - ✅ Token 鉴权验证：无 token 401、错误 token 401、正确 token 通过
  - ✅ 首页已加入口（commit `3ff6fa1`，v1.3.0）：header「调研台」按钮 → `research-deck/index.html?backend=<SCF公网URL>`
- **⚠️ 部署关键坑（腾讯云 Web 函数，务必遵守）**：
  1. **scf_bootstrap 启动命令必须用绝对路径**：Python 3.9 = `/var/lang/python39/bin/python3.9 server.py`；裸 `python`（指向 py2）会报 f-string SyntaxError，裸 `python3` 可能不在 PATH 致实例起不来（000）
  2. **必须监听 9000 端口**：`export PORT=9000`（server.py 已支持从 PORT 环境变量读取）
  3. **bootstrap 需 755 权限 + LF 结尾**
  4. **SCF 执行超时需调到 ≥30s**（默认 3s 会让 DeepSeek 调研超时 433）
  5. 运行环境创建后**无法修改**（选 Python 3.9 就锁死 3.9）

## 当前状态基线（2026-08-31 更新）
- **report-portal 知识库：v2.0.1 已部署验证通过；v2.0.2（云端同步状态可见）已推 Pages**。
- **调研台 ResearchDeck：v2.1.1（体验修复）已推 GitHub（commit `da1e862`），部署包 `researchdeck_deploy_v211.zip` 待用户上传 SCF**。本期修复：① 已登录隐藏访问令牌输入框（仅留「⚙ 令牌设置」入口）；② 修报告删除 bug（云端报告未标 cloud 导致删不掉，现已修复且删除走云端）；③ 新增产品删除（产品卡+主页删除按钮 + 后端 DELETE /api/products）。⚠️ 部署后云端产品删除才生效；之前验证产生的测试产品残留（_测试产品_验证用）部署 v2.1.1 后可用产品删除按钮或 cleanup 脚本清。
- **v2.1.0 核心链路（E2E 已过）**：产品研究库（s8）→ 创建产品（product_id 唯一）→ 产品主页 →【＋继续研究这个产品】自动绑定 product_id（研究横幅提示，专题调研可选手研分类）→ 3 种调研形式照旧 → 报告自动归档该产品对应分类 → 独立研究（s9，product_id=null）→ 历史报告兼容。
- **v2.0.2**（纯前端，commit `0e50770`）：saveReport 云端推送原来**静默失败**（用户做专题调研后云端没有）——现加同步状态反馈（成功 toast「已同步云端」/ 失败 toast + 报告卡「⚠️ 未同步云端 · 点此重试」）+ `retryCloudSync(id)` 手动重试。Pages 自动生效。
- ⚠️ **部署坑（累计）**：① bootstrap 绝对路径+PORT=9000；② GITHUB_TOKEN/RD_TOKEN 填反；③ 超时 300s；④ amz 方法论非死数据；⑤ 本地测试用 ?backend= 覆盖；⑥ tech/reg/prod 提示词写死技术名词（v1.6.1）；⑦ 改后端必须重部署 SCF；⑧ **Python .format() 与未转义 {topic} 命名占位符冲突（v2.0.1 修复）**；⑨ **前端云端推送静默失败（v2.0.2 修复：可见+可重试）**；⑩ **v2.1.0 改 server.py（/api/products），必须重部署 SCF + 配 GITHUB_TOKEN（否则产品云端同步 500）**。
- 版本管理 + 无死数据红线：`check_no_dead_data.sh` 黑名单 17 词，提交前必跑（当前 PASS）。

## 版本基线
- **v2.1.1**（2026-08-31，commit `da1e862`）—— 体验修复（Patch）：① 已登录隐藏访问令牌输入框（refreshTokenUI 在 bootStatus/saveToken/gateLogin 调用，仅留「⚙ 令牌设置」入口）；② 修报告删除 bug（renderReports 合并云端报告显式标 cloud:true，修复原 cloud 标记丢失致跳过云端 DELETE 删不掉；delReport 改为配后端+token 即发 DELETE 且完成后才重渲染）；③ 新增产品删除（产品卡+产品主页删除按钮 + delProduct 删本地+云端产品及其全部报告；后端 do_DELETE 扩展支持 DELETE /api/products?id=）。E2E 全过（令牌隐藏/删除按钮渲染/报告删除/产品删除/无 JS 错误）。**需重部署 SCF**（部署包 `researchdeck_deploy_v211.zip`）。
- **v2.1.0**（2026-08-31，commit `b421069`）—— 调研台产品研究空间（Major）：以产品为中心管理研究。新增「产品研究」一级模块（导航+s8 页面）：产品卡片（名称/英文/类别/研究数/最近研究/更新时间/创建时间）+【＋创建产品研究】表单（必填产品名称，选填英文/类别/目标市场/目标渠道/研究目的/备注，生成唯一 product_id）；产品主页（s8 内嵌）：基本信息可编辑 + 研究统计（按类型动态）+ 研究分类 Tab（全部/市场/电商/竞品/用户/技术/法规/专利/供应链/其他，可扩展）+ 最近研究列表 + 主按钮【＋继续研究这个产品】；继续研究自动绑定 product_id（研究横幅「正在研究：<产品名>」，专题调研新增研究分类下拉）；报告保存自动携带 product_id/research_id/research_type/research_mode/status/created_at/completed_at；「独立研究」s9（product_id=null 报告 + 历史报告，不强制归属）；后端 /api/products GET/POST（GitHub `research-deck/saved/products.json`，token 鉴权）、/api/reports 支持 ?product_id= 过滤、gh 读写函数参数化（reports/products 通用）。**E2E 测试 A-D 全过**（产品创建/继续研究横幅/自动归档/技术分类/电商分类/独立研究/历史兼容，无 JS 错误，死数据 PASS）。**需重部署 SCF**（部署包 `researchdeck_deploy_v210.zip`）。
- **v2.0.2**（2026-08-29，commit `0e50770`）—— 云端同步状态可见+失败重试（feat，纯前端）：saveReport 推送成功/失败均 toast 提示；失败报告卡显示「⚠️ 未同步云端 · 点此重试」；新增 `retryCloudSync(id)` 手动补同步。**无需重部署 SCF**。
- **v2.0.1**（2026-08-29，commit `fd01566`）—— v2.0 两处 bug 修复（fix）：① `_extract_json` 升级三级兜底（整体解析→截取对象→截取数组），专题调研研究计划正常生成 3-5 个点（原只 1 个）；② `decision_prompt` 的「{topic}」改「{}」位置占位，综合立项决策面板不再报错。**已部署 SCF 并验证**。
- **v2.0.0**（2026-08-29，commit `8412cad`）—— 调研台架构重构（Major）：按产品经理工作流组织。**3 种调研形式**（标准/专题/综合立项）+ **5 类调研类型**（市场机会/电商市场/竞品研究/用户研究/技术研究，含固定研究骨架与维度映射）+ 高级模式（9 维度自由勾选，折叠入口）。专题调研=LLM 生成研究计划→并行执行；综合立项=串联 5 类+5 段式决策面板（市场成立/用户需求/竞争机会/技术可行/产品定义）。**需重部署 SCF**。
- **v1.9.0**（2026-08-29，commit `1fc932e`）—— 调研台门禁（feat）：后端 `/api/status` 加 `authValid` 字段；前端全屏门禁遮罩（未验证前内容不可见），输错提示+抖动、输对存 token 放行、已存 token 刷新自动进入、失效回退门禁。E2E 全通过。**需重部署 SCF**。
- **v1.8.0**（2026-08-29，commit `2cb4b7e`）—— 代码审查 13 项修复（feat）：XSS 转义；fetch 超时；进度动画真实化；8→9 维度文案；previewTemplate 纯本地；死代码清理；Blob revoke；meta/aria-label；alert→toast；目录吸顶高亮；KPI 移动端 2 列；历史单条删除；维度启用/停用开关。

## 版本基线
- **v1.6.1**（2026-08-29，commit `ee664fa`）—— 清除 tech/reg/prod 残留技术名词（Patch）：用户反馈调研「拖把」出现 EMG/EMS——tech 提示词写死 Peltier TEC/EMG/EMS-TENS、reg 写死 FDA 510k/NMPA、prod 写死传感/加热/电机。全部改为"按品类实际判断，勿预设"；前端 DIMS/META/DIM_STRUCT 同步；检查脚本黑名单扩展（EMG/EMS-TENS/Peltier/510k/NMPA）。**线上实测拖把 4 维度全干净**。**已部署 SCF**。
- **v1.6.0**（2026-08-29，commit `12c1b08`）—— 调研台 5 项优化（feat）：① 🔴 token 安全（localStorage 编码存储、输入框不回显明文、保存后清空）；② 🟠 云端合并（reportId 加毫秒时间戳防覆盖、云端+本地合并去重显示）；③ 🟠 删除功能（后端 DELETE /api/reports?id= + 前端删除按钮/清空全部）；④ 🟠 生成等待提示（live 显示"调用 DeepSeek 10-30s"+20s 超时提醒）；⑤ 🟡 401 引导（滚动到 token 框高亮+保存后自动重试）。E2E 全通过。**需重部署 SCF**。
- 远端 main HEAD：随 SCF 自动 meta 提交持续前进（推送前需 `git pull --rebase`）。
- 已验证：amz_us 新模板线上实测 10 表 + 8 KPI + 6 callouts；`/api/status` 返回 `cloudReports: true`；鉴权 `au.26611` 正常。

## 版本基线
- **v1.5.3**（2026-08-29，commit `1b4cdf8`）—— amz 维度改为看板方法论·任意主题实时生成（feat）：**用户澄清**美/欧报告是维度参考框架而非本地死数据。AMZ_US/EU_TEMPLATE 泛化（去掉写死盆底肌类型/场景，改由 MCP 数据决定）；demo_amz_us/eu 改结构骨架版（数据标"待实时生成"）；前端 DIMS/META/DIM_STRUCT 同步。**线上已验证**：非盆底肌主题「宠物智能饮水机」10 表结构完整、内容为该主题（含"盆底肌"=False）。**已部署 SCF**。
- **v1.5.2**（2026-08-29，commit `3fc745d`）—— 多维度 LLM 并行生成（feat）：LLM 模式 6 维度**串行**调 DeepSeek（90-180s）远超 SCF 30s 超时 → 后端被掐断 → 选 6 个调研维度 Failed to fetch（固定模板 2 维度因本地数据秒出不受影响）。修复：`ThreadPoolExecutor(max_workers=min(6,len(dims)))` 并行调用，实测 6 维度 **9.8s** 全部成功。**需重部署 SCF + 超时调 300s**（用户已操作，已验证通过）。
- **v1.5.1**（2026-08-29，commit `18eb098`）—— 调研台后端地址兜底（Patch）：直开 `research-deck/`（无 `?backend=` 参数且 localStorage 无值）时 BACKEND_URL 为空 → api() 返回相对路径打到 GitHub Pages → Failed to fetch。修复：内置默认 SCF 地址 `DEFAULT_BACKEND` 兜底写入 localStorage；新增后端连接状态徽章。**纯前端，无需重部署 SCF**。
- **v1.5.0**（2026-08-29，commit `a852105`）—— 我的报告/历史任务云端同步（Minor）：后端新增 GET/POST `/api/reports`，报告存 GitHub `research-deck/saved/reports.json`（Contents API，纯 urllib）；需 `GITHUB_TOKEN` 环境变量；前端 saveReport 自动同步云端，renderReports/renderHistory 云端优先+本地回退，卡片带 ☁️ 标记。**需重部署 SCF + 配 GITHUB_TOKEN**。
- **v1.4.0**（2026-08-29，commit `d279609`）—— amz_us 模板严格对齐「US Bladder Control Devices 盆底肌训练器机会评分看板」（Minor）：`AMZ_US_TEMPLATE`（LLM 提示词）扩展为 KPI(8) + 10 表 + callouts；`demo_amz_us()` 用看板真实数据重写（产品类型结构/品牌Top10/品牌路线/关键词市场/趋势PPC/价格带/场景痛点/功能热度/十维评分）；前端 DIMS/DIM_STRUCT 同步。**需重部署 SCF**。
- **v1.3.1**（2026-08-29，commit `d26fedf`）—— 调研台移动端适配（Patch）：研究台页无 `@media`，手机端 `.side` 固定 230px 挤压主区、`.search` 横向 flex 致「下一步」按钮不可见。修复：侧边栏改顶部水平导航，搜索框纵向堆叠、按钮全宽，数据源分段/维度网格/Token 框全部适配 ≤768px。
- **v1.3.0**（2026-08-29，commit `3ff6fa1`）—— 新增「调研台」入口（Minor）：首页 header 加「调研台」按钮链接 `research-deck/?backend=<SCF公网URL>`；调研台 SCF 后端部署成功（修复 bootstrap 启动命令：绝对路径 + PORT=9000；server.py 去 f-string 兼容 py3.9）。
- **v1.2.4**（2026-08-25，commit `d491a8a`）—— 回收站加载修复 + 架构优化：新增 `trash/index.json` 单文件索引，`listtrash` 优先读它（1 次 GitHub 调用）；回退分支仅列目录+写索引(2 次)；新增 `rebuildTrashIndex` 接口（需 SCF 超时 60s）；前端错误态透明化 + 重试即时反馈 + 「重建索引」按钮。
- **v1.2.3**（2026-08-25，commit `a0e77f5`）—— 「已删除」列表状态透明化：新增 `_trashState`(init/loading/ok/unauthorized/error)，未授权显示 🔒，`openTrashLogin()` 强制置顶登录框。实测数据层 trash/meta 11 个条目完好。
- **v1.2.2**（2026-08-25，commit `8103fa1`）—— 401 空缓存污染修复：401/失败绝不写缓存，401 立即 `onTokenExpired()` 弹登录框。
- **v1.2.1**（2026-08-25，commit `a488e37`）—— adminApi 透出 status，401 统一弹登录框 + toast「后台登录已过期」(8s 防抖)。
- **v1.2.0**（2026-08-25，commit `49a6c57`）—— 文件管理列表按修改时间倒序。
- **v1.1.3**（2026-08-25，commit `eebf901`）—— 上传同名重复/404 修复：前端新增与后端一致的 `safeNameOf`，双重去重 + `pruneGhostUploads()` 自愈。
- **v1.1.2**（2026-08-25，commit `c0cd213`）—— 文件管理打开慢：先同步渲染在线文件、回收站异步补齐 + 60s 缓存 + 5s 超时兜底。
- v1.1.1（2026-08-21，commit `f851f3f`）—— 上传大文件客户端 4MB 前置检查 + 报错文案优化。
- **v1.1.0**（2026-08-20，commit `93c87f8`）—— 后台「文件管理」合并在线+已删除，筛选标签，移除独立垃圾箱 tab。
- v1.0.1（2026-08-20，commit `c0ce04c`）—— 删除/恢复后首页不刷新修复。
- v1.0.0（2026-08-20，commit `21b8387`）—— 稳定基线。
- 递增规则（用户 2026-08-20 确认，助手自动递增）：新增功能/界面→Minor；修 bug→Patch；不兼容/架构变更→Major。每次修改后助手自行升级版本号、更新本基线、记入当日日志。
- **版本管理约定（用户 2026-08-29 要求，永久生效）**：修改 bug/功能时**绝不覆盖旧版本**——先归档当前版本到 `research-deck/versions/<版本号>/`，再生成新版本；部署包命名 `researchdeck_deploy_v<版本号>.zip`；详见 `research-deck/VERSIONING.md`。
- **模板无死数据红线（用户 2026-08-29 要求，永久生效，优先级最高）**：无论新增任何调研维度/模板，**一律禁止写死固定产品的真实数据**（如盆底肌、哺乳按摩器、Momcozy 等具体品牌/销量/份额）。所有维度只允许两种形态：①「大模型模式」= LLM 按结构对用户输入主题实时生成真实数据；②「模板模式」= 主题驱动的通用结构骨架，数据标注「待实时生成/待核验」。任何含固定产品数据的 demo 函数、提示词、前端文案均属违规，发现即删。**每次新增模板必须过此检查**（grep 固定产品名 + 人工核对）。
- **主站隔离红线（用户 2026-08-29 要求，永久生效，优先级最高）**：**调研台的一切改动只允许在 `research-deck/` 目录内**，**绝不触碰数据库主站文件**（根目录 `index.html`、`manifest.json`、`meta.json`、`api/`、`scf/`、`reports/`、`backups/` 等）。背景：2026-08-29 曾为修加载慢改动根目录 index.html 的 manifest/meta 加载逻辑（v1.9.1/v1.9.2），用户将"动主站文件"与"数据库加载变慢"关联，明确要求以后调研台迭代不得动主站。**主站文件需要任何改动（即使只是优化）必须先用 AskUserQuestion 单独征得用户同意，获准后才动**。

## 架构要点
- 文件索引 `manifest.json`（GitHub 权威源）；分类/标签 `meta.json`；经 SCF 写 GitHub。
- 前端读取层：`FILES`（manifest）+ `S.uploaded`（本地兜底）+ `S.customCats/S.allTags` 等（localStorage）。
- `getAllFiles()` = manifest 与本地兜底「云端优先 + 原始名/安全名(safeNameOf)双重去重」合并。
- 上传可靠性三防线：本地兜底写入 + SCF 中继读 manifest/meta（op:getmanifest/getmeta）+ 后端 manifest 写入失败报错。

## 删除机制
- 软删除：`op:'delete'` 存 `trash/` 备份 → 删 `reports/` → 从 manifest 移除。物理仍在 `trash/`（不公开）。
- 回收站索引（v1.2.4 起）：`trash/index.json` 由 SCF 在 delete/restore/purge 时维护，`listtrash` 优先读它。
- 后台统一列表：合并在线与已删除，筛选标签 全部/在线/已删除，恢复/彻底删/清空回收站。
- 删/恢复/彻底删成功回调须调 `renderAdminFiles()` 刷新。
- 性能：`renderAdminFiles` 先同步 `paintAdminFiles()`（在线文件即点即现），`loadTrashItems()` 异步补齐（`_trashCache` 60s + 5s 超时兜底），登录成功预热。

## 部署惯例（重要）
- **远端常被用户活动推进**：SCF `handleMeta` 自动提交 `meta.json`（"meta: update" 系列），推前先 `git fetch`（走镜像）看分叉；若远端只动 meta.json 不冲突则 rebase 后快进推送，勿盲目强推。
- SCF 改动需用户在腾讯云控制台重部署才生效。**改了后端逻辑必须重部署 SCF**，否则后端仍跑旧逻辑。
- GitHub Pages 构建约 1~2 分钟；验证以 GitHub API/git tree 为准（raw CDN 偶发陈旧）——云端用镜像读 + WebFetch 核对。
- 云端验证白屏类问题：提取 index.html 全部 `<script>` 块逐个 `node --check`。

## 上传大文件 / `Failed to fetch` 根因（重要）
- 根因：API 网关默认请求体约 6MB + 云函数默认超时 3s。大 HTML（内嵌图片的调研报告）base64 后超限 → 传输层掐断且无 CORS 头 → 浏览器 `Failed to fetch`。
- SCF 内 `MAX_UPLOAD_BYTES = 15MB`（scf/index.js:40）但检查在网关之后。
- 已加客户端 4MB 前置检查（v1.1.1）。
- **彻底解决需用户在腾讯云控制台调高**：① API 网关请求体(建议 20MB)；② 云函数超时(建议 60~120s)；③ 网关超时同步调高。改完无需动代码。（截至 2026-08-26 未见用户确认已调整，`rebuildTrashIndex` 依赖 60s 超时是否已调待确认。）

## 待办 / 悬而未决
- [x] 用户提供 GitHub PAT → 已配置云端 push 凭据并通过认证+写权限验证（见「云端 git 推送通道」）。⚠️ token 有过期日，到期前需提醒用户重生成。
- [x] 调研台 ResearchDeck 上线（2026-08-29 完成，见模块章节）
- [x] 调研台云端报告同步（v1.5.0，2026-08-29 部署完成并验证通过）
- [x] amz_us 模板对齐机会评分看板（v1.4.0，2026-08-29 部署完成并验证通过）
- [ ] 确认用户是否已在腾讯云控制台调高网关 6MB / 函数 3s 限制（影响大文件上传与重建索引）——调研台函数超时已调 30s，知识库主函数 `report-portal-upload` 是否调整待确认。
- [ ] （可选）本地 .git 反复损坏问题在云端不存在，旧惯例仅作历史参考。

## 日志
- 2026-08-26 10:15：本地对话迁移至云端。重建环境：镜像克隆仓库，核实线上 v1.2.5 正常（用户登录确认白屏修复、无欠费），index.html 脚本语法验证通过，SCF getmanifest 实测健康。
- 2026-08-26 10:43：用户提供 GitHub PAT（Fine-grained，database 仓库 Contents 读写）。配置镜像重写 + credential helper，并经 `ls-remote` 与 `push --dry-run` 验证认证/写权限均有效；`git fetch/pull/push` 现已全通。工作区 fast-forward 至远端最新 `e9bdf8c`（meta update），状态干净。提醒：token 非真正永久，过期需重配。
- 2026-08-29：调研台部署攻坚（腾讯云 Web 函数 Python3.9）：
  - 公网 URL `https://1461447139-ds1sdwfe7p.ap-guangzhou.tencentscf.com` 确认（`researchdeck_web` 函数，内网地址 `.in.` 变体不可用）。
  - 排障 3 轮：① 裸 `python server.py` → 指向 py2 → f-string SyntaxError（322 行）；② 裸 `python3 server.py` → 不在 PATH → 实例起不来 HTTP 000；③ 官方绝对路径 `/var/lang/python39/bin/python3.9` + `export PORT=9000` → 部署成功 HTTP 200。
  - 附加坑：SCF 默认超时 3s 致 DeepSeek 调研 433 超时 → 用户调至 30s 后验证通过。
  - 安全验证：无 token 401、错误 token 401、正确 token（`au.26611`）完整链路通过；source=llm 真实报告生成成功。
  - 首页加入口（v1.3.0，commit `3ff6fa1`），Pages 构建 built，推送远端成功。
