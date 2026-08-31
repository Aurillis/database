# 调研台 ResearchDeck · 完整设计文档

> 本文件是项目的**权威设计规格**，与 `PROJECT_MEMORY.md`（对话记忆）配套使用。
> 用途：**无论当前对话是否可用，本项目全部设计、架构、数据模型、功能逻辑都保留在此 + GitHub 仓库**，新对话 clone 仓库即可完整接续。
> 维护规则：每次改动设计 → 更新本文件对应章节；每次操作 → 在文末「操作日志」追加一条。最后 `git add` 并 `git push origin main`。
> 最后更新：2026-08-31（v2.1.1 之后）

---

## 0. 一句话定位

调研台是 `report-portal` 知识库站点的**独立子模块**，把"零散报告管理"升级为"**以产品为中心的研究管理**"：用户持续研究某个产品，产品下不断沉淀市场/Amazon/竞品/用户/技术/法规/专利/供应链等研究，自动归档、按类查看。

- 前端：`research-deck/index.html`（单文件，原生 JS，无框架）
- 后端：`research-deck/server.py`（Python 3.9，腾讯云 SCF Web 函数）
- 在线地址：`https://Aurillis.github.io/database/research-deck/?backend=https://1461447139-ds1sdwfe7p.ap-guangzhou.tencentscf.com`
- 代码仓库：`Aurillis/database` 分支 `main`，子目录 `research-deck/`

---

## 1. 架构总览

```
浏览器 (index.html, GitHub Pages)
   │  fetch
   ▼
SCF Web 函数 researchdeck_web (server.py, Python3.9)
   ├─ /api/research   → 调 DeepSeek 实时生成报告（服务端 Key，强制）
   ├─ /api/reports    → 报告读写（localStorage 本地 + GitHub saved/reports.json 云端）
   ├─ /api/products   → 产品读写（GitHub saved/products.json 云端）
   └─ /api/status     → 后端能力/鉴权状态
```

### 1.1 关键约束（部署铁律）
- **SCF 启动**：`scf_bootstrap` 必须用绝对路径 `/var/lang/python39/bin/python3.9 server.py` + `export PORT=9000`，755 权限，LF 结尾。
- **SCF 超时**：≥30s（DeepSeek 生成慢）。
- **改了 `server.py` 必须重新上传部署包到 SCF**，否则后端跑旧逻辑。
- **前端改动**：`git push` 后 GitHub Pages 自动构建（约 1–2 分钟生效），无需重部署 SCF。
- **Key 安全**：DeepSeek Key 只存 SCF 环境变量 `OPENAI_API_KEY`，后端**强制忽略**前端传入的 `llm.key`；绝不进网页/仓库。
- **令牌**：设 `RD_TOKEN` 后 `/api/research` 必须带 token（否则 401）。

### 1.2 后端环境变量（SCF 控制台）
| 变量 | 值 | 说明 |
|------|-----|------|
| `OPENAI_API_KEY` | DeepSeek Key | 服务端统一管控 |
| `OPENAI_BASE_URL` | `https://api.deepseek.com/v1` | |
| `OPENAI_MODEL` | `deepseek-chat` | |
| `RD_TOKEN` | `au.26611` | 调研接口鉴权令牌 |
| `GITHUB_TOKEN` | Fine-grained PAT（database 仓库 Contents 读写） | 云端报告/产品同步；缺则云端同步 500 |
| `GITHUB_REPO` | `Aurillis/database` | 默认，可覆盖 |
| `RD_REPORTS_PATH` | `research-deck/saved/reports.json` | 默认 |

---

## 2. 数据模型（核心）

> 设计原则：**复用现有字段，不重复建表**；`product_id` 是唯一关联键（不靠产品名字符串匹配）。

### 2.1 Product（产品研究空间）
```jsonc
{
  "product_id": "pelvic_floor_trainer_abc123",  // 唯一，前端生成（slug + 随机）
  "name": "盆底肌训练器",
  "name_en": "Pelvic Floor Trainer",
  "category": "智能硬件",
  "target_market": ["美国", "欧洲"],            // 逗号分隔输入 → 数组
  "target_channel": ["Amazon US"],
  "research_goal": "验证市场机会",
  "description": "备注",
  "created_at": "2026-08-31 10:00",
  "updated_at": "2026-08-31 10:00"
}
```
- **存储**：本地 `localStorage['rd_products']` + 云端 `research-deck/saved/products.json`（GitHub Contents API，token 鉴权）。
- **关联**：所有 Research/Report 通过 `product_id` 绑定，不依赖名称。

### 2.2 Research（研究，概念层，由报告继承）
```jsonc
{
  "research_id": "r_xxx",          // 研究开始即生成
  "product_id": "pelvic_floor_trainer_abc123",
  "research_type": "tech",         // 见 §4 分类
  "research_mode": "topic",        // standard/topic/comprehensive
  "title": "不同尿失禁类型 EMS 刺激参数研究",
  "status": "completed",
  "created_at": "2026-08-31 10:05",
  "completed_at": "2026-08-31 10:08"
}
```

### 2.3 Report（报告记录）
```jsonc
{
  "id": "报告标题|2026-08-31 10:08",   // reportId：标题 + 时间戳（含毫秒防覆盖）
  "topic": "报告标题",
  "generatedAt": "2026-08-31 10:08",
  "_ts": "2026-08-31 10:08-ab12",
  "mode": "live",                      // live/template
  "dims": ["t_技术"],                  // 维度 key 列表
  "data": { "topic": "...", "summary": "...", "sections": {...} },  // 报告正文
  "cloud": false,                      // false / true / "fail"（同步状态）
  // —— 归属字段（v2.1.0 新增，自动归档用）——
  "product_id": "pelvic_floor_trainer_abc123",  // 独立研究 = null
  "research_id": "r_xxx",
  "research_type": "tech",
  "research_mode": "topic",
  "status": "completed",
  "created_at": "2026-08-31 10:05",
  "completed_at": "2026-08-31 10:08"
}
```
- **存储**：本地 `localStorage['rd_reports']`（上限 50 条）+ 云端 `research-deck/saved/reports.json`。
- 历史报告（v2.1.0 前无 `product_id`）→ 显示为"独立研究/未归属"，**不强制归属**。

### 2.4 三者关系
```
Product (product_id)
  └─ Research (research_id + product_id + research_type + research_mode + status)
       └─ Report (id + product_id + research_id)
```
从产品入口发起时请求携带 `product_id`；`saveReport` 把归属字段一并持久化 —— **全程不用用户再选文件夹**。

---

## 3. 页面与导航

### 3.1 侧边栏导航（当前顺序）
| 图标 | 名称 | 屏幕 |
|------|------|------|
| ① | 新建调研 | s1 |
| 📦 | 产品研究 | s8（列表/主页两态） |
| ▤ | 全部报告 | s5 |
| 📂 | 独立研究 | s9 |
| ⚙ | 维度模板 | s6 |
| ◷ | 历史任务 | s7 |

> 令牌输入：已登录后**隐藏**整个令牌框，仅留「⚙ 令牌设置」小入口（v2.1.1）。

### 3.2 屏幕清单（s1–s9）
| 屏 | 用途 |
|----|------|
| s1 | 新建调研：输入主题 → 选调研形式 |
| s2 | 选择维度（标准调研的维度勾选） |
| s3 | 生成中（真实进度，DeepSeek 实时） |
| s4 | 报告查看（沿用既有 HTML 渲染，**不重做阅读器**） |
| s5 | 全部报告：云端+本地合并去重，可删除 |
| s6 | 维度模板 |
| s7 | 历史任务时间线 |
| s8 | **产品研究**：列表态（产品库）/ 主页态（某产品空间），由 `_productView` 切换 |
| s9 | 独立研究：未归属报告（product_id=null 或历史无归属） |

---

## 4. 研究分类（可扩展配置）

产品主页"研究分类"Tab（数据结构化，新增类型 = 改配置，不改代码）：
```
全部 | 市场(market) | 电商(ecom) | 竞品(comp) | 用户(user) |
技术(tech) | 法规(reg) | 专利(patent) | 供应链(supply) | 其他(other)
```
统计按 `research_type` 动态聚合；分类与具体提示词/维度映射在 `META`/`DIM_STRUCT` 配置中。

---

## 5. 核心功能设计

### 5.1 三种调研形式（沿用，不重做）
1. **标准调研**：5 类（市场机会/电商市场/竞品/用户/技术）+ 高级模式（9 维度自由勾选）。
2. **专题调研**：LLM 生成研究计划 → 并行执行；**新增"研究分类"下拉**（默认按问题智能归类）。
3. **综合立项研究**：串联 5 类 + 5 段式决策面板（市场成立/用户需求/竞争机会/技术可行/产品定义）。

### 5.2 产品研究库（s8 列表态）
- 产品卡片显示：名称、英文名、类别、研究数、最近研究、更新时间、创建时间。
- 按钮：【进入产品】、【＋创建产品研究】。
- 创建产品表单：必填产品名称；选填英文/类别/目标市场/目标渠道/研究目的/备注 → 生成 `product_id`。

### 5.3 产品主页（s8 主页态）
- 顶部：产品名 + 英文名 + 研究数/最近研究/最后更新。
- **主按钮【＋继续研究这个产品】**（置顶、明显）。
- 产品基础信息（可编辑：名称/英文/类别/目标市场/目标渠道/备注）。
- 研究统计（按类型动态）。
- 研究分类 Tab（§4）。
- 最近研究列表（标题/类型/形式/创建/完成/状态/查看报告）。
- **删除产品**按钮（v2.1.1，删本地+云端产品及其全部报告）。

### 5.4 「继续研究这个产品」（最重要交互）
```
点击按钮 → 顶部横幅「正在研究：<产品名>」（自动绑定 product_id）
→ 进入现有 3 种调研形式
→ 生成报告 → saveReport 自动带 product_id + research_id
→ 自动回到产品主页 → 报告出现在对应分类
```
**不再询问"属于哪个产品"**，不要求用户事后手动归类。

### 5.5 自动归档逻辑
`saveReport` 一处改动：记录写入 `product_id` + `research_id` + `research_type` + `research_mode` + `status` + `created_at` + `completed_at`。产品主页按 `product_id + research_type` 过滤渲染。

### 5.6 独立研究 / 历史兼容
- 独立创建（不选产品）→ `product_id=null` → 归入 s9「独立研究」。
- 历史报告（无 `product_id`）→ s5「全部报告」照常显示 + s9「独立研究」归类；打开走既有阅读器，零改动。
- **不强制自动判断归属**，后期再做批量归档。

### 5.7 云端同步状态（v2.0.2）
- 保存成功 → toast「已同步云端 ✓」；失败 → 红色提示 + 报告卡「⚠️ 未同步云端 · 点此重试」+ `retryCloudSync(id)`。

---

## 6. 后端 API 清单（server.py）

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/api/status` | 返回 `{backendMode, researchTypes, cloudReports, cloudProducts, authValid}` | 否 |
| POST | `/api/research` | 调 DeepSeek 生成报告 | **需 `RD_TOKEN`** |
| GET | `/api/reports` | 列表；`?product_id=` 按产品过滤 | 需 token |
| POST | `/api/reports` | 保存报告到云端 | 需 token |
| DELETE | `/api/reports?id=` | 删除云端报告 | 需 token |
| GET | `/api/products` | 产品列表 | 需 token |
| POST | `/api/products` | 创建产品（body 须含 `product_id`） | 需 token |
| DELETE | `/api/products?id=` | 删除产品 + 其全部报告 | 需 token |

GitHub 读写函数 `gh_get_json` / `gh_save_json` 参数化（reports / products 通用，纯 urllib）。

---

## 7. 永久红线（优先级最高，违反即拦）

1. **无死数据红线**：禁止写死固定产品真实数据（品牌/销量/份额）；只允 LLM 实时生成或通用骨架。
2. **主站隔离红线**：调研台改动**只在 `research-deck/`**，**绝不碰**主站（`index.html` 根/`manifest.json`/`meta.json`/`api/`/`scf/`/`reports/`/`backups/`）。主站文件任何改动须先单独征求用户同意。
3. **版本管理红线**：改动不覆盖旧版 → 先归档 `research-deck/versions/<ver>/`，部署包命名 `researchdeck_deploy_v<ver>.zip`。
4. **不动用户数据库主站**：用户明确要求调研台迭代不得影响主站加载速度。

---

## 8. 版本基线（摘要，详见 PROJECT_MEMORY.md）

| 版本 | 日期 | 要点 |
|------|------|------|
| v2.1.1 | 2026-08-31 | 令牌 UI 隐藏 / 报告删除 bug 修复 / 产品删除（需重部署 SCF） |
| v2.1.0 | 2026-08-31 | **产品研究空间**：产品→继续研究→自动归档→分类查看（需重部署 SCF） |
| v2.0.2 | 2026-08-29 | 云端同步状态可见 + 失败重试（纯前端） |
| v2.0.1 | 2026-08-29 | 专题研究计划 1 点 bug / 决策面板报错（已部署验证） |
| v2.0.0 | 2026-08-29 | 架构重构：3 形式 + 5 类型 + 高级模式 |
| v1.9.0 | 2026-08-29 | 门禁（token 鉴权） |
| v1.5.0 | 2026-08-29 | 报告云端同步（GitHub） |
| v1.3.0 | 2026-08-29 | 调研台入口 + SCF 部署 |

---

## 9. 当前待办 / 瞬时状态（写文件时一并更新）

- [ ] **v2.1.1 部署包 `researchdeck_deploy_v211.zip` 已生成，待用户上传 SCF 重部署**（上传后产品删除云端生效）。
- [ ] 云端测试产品残留 `_测试产品_验证用`（v2.1.0 验证时产生）待清：部署 v2.1.1 后点删除按钮，或跑 `cleanup_researchdeck_test.sh`（需用户自有 GITHUB_TOKEN）。
- [ ] 确认腾讯云是否已调高网关 6MB / 函数超时（影响大文件上传与重建索引）。

---

## 10. 操作日志（每次操作追加一条，含具体细节）

### 2026-08-31 10:37 — 建立"设计全保留"机制
- **动机**：用户要求"每做一个操作都把具体细节写到文件，项目全部设计保留，对话不可用也不丢"。
- **问题定位**：原 `MEMORY.md` 在 `/workspace/MEMORY.md`（**仓库外**），`git push` 不带它 → 新沙箱/新对话拿不到。
- **动作**：
  1. 新建本文件 `DESIGN.md`（仓库内）— 完整设计规格（架构/数据模型/页面/功能/API/红线/版本）。
  2. 把记忆文件搬入仓库：`/workspace/MEMORY.md` → `/workspace/report-portal/PROJECT_MEMORY.md`（重命名定位，内容延续，加"现已入库可 clone 接续"说明）。
  3. 确立规矩：每次操作 → 更新本文件对应章节 + 文末追加日志条目 → `git add` + `git push origin main`。
- **产出文件**：`/workspace/report-portal/DESIGN.md`、`/workspace/report-portal/PROJECT_MEMORY.md`。
- **下一步**：`git commit` + `git push`，使两文件上 GitHub 持久化。
- **验证**：`git ls-files` 确认两文件被跟踪；`git push` 后 GitHub 可见。
