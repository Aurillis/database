# ResearchDeck v2.3.0 开发报告 · 动态 Research Creation Model

> 版本：`v2.3.0` ｜ 日期：2026-09-02 ｜ 模式：问题驱动研究（Question → Scope → Plan → Research）
> 配套产物：`researchdeck_deploy_v2.3.0.zip`（待重传 SCF）｜ 回归测试：`test_v230_dynamic.py`（27/27 PASS）

---

## 一、架构变化（Architecture Change）

从「**选固定模板 → 填固定报告目录**」升级为「**Research Question → Research Context → AI 判断 Research Scope → Method + Sources → Research Plan → 确认 → 执行**」。

核心原则：**Research Question 决定 Research Scope，而不是固定模板决定研究范围。**

| 维度 | v2.2.4 及之前 | v2.3.0 |
|---|---|---|
| 创建入口 | 标准/专题/综合立项（固定模板） | 问题驱动研究（推荐）+ 旧模板保留为可选 |
| 报告结构 | 固定 5 维（市场/电商/竞品/用户/技术） | 由 Research Plan 动态决定，Scope 即章节 |
| FDA/法规/专利/供应链 | 全部作为固定维度可选 | **条件动态能力**：仅相关时进入 core，否则 skip |
| 模板 | `RESEARCH_TYPES` / `DIM_PROMPTS` 固定目录 | `RESEARCH_RECIPES`（研究策略模板，非固定目录）+ `RESEARCH_SCOPES`（动态能力目录） |
| 后端生成 | `build_report` 标准/专题/综合路 | 新增 `mode='dynamic'` → `build_dynamic_report` |
| Library 分类 | 按 `research_type` 单类 | 多维度：`dimensions[]`（一份研究可出现在多个分类） |

> 关键红线（#27）：动态 Scope **真正驱动 AI prompt**——后端 `build_dynamic_report` 把 Question/Context/Goal/Scope/子问题/Method/Source/Expected Output 全部注入大模型，报告结构跟随研究计划，**不是**前端切了 UI、后端仍调旧固定模板的「假升级」。

---

## 二、Research Object Schema（研究对象结构）

动态研究报告在云端归档记录（`_auto_archive`）新增字段，旧字段全部保留：

```jsonc
{
  "id": "r_xxx",
  "topic": "<研究问题>",
  "research_type": "dynamic",          // 新：标记动态研究
  "research_mode": "dynamic",          // 新：生成模式
  "research_question": "这次想解决什么问题？",
  "context": {
    "markets": ["US","EU"],
    "product_stage": "产品定义",
    "channels": ["Amazon","DTC"],
    "background": "已有 EMS 样机…",
    "product_type": "盆底肌康复仪",
    "product_claims": "用于盆底肌训练"
  },
  "scopes": [                          // 新：动态 Scope 对象（带入选程度与原因）
    {"id":"tech","name":"技术","level":"core","reason":"…"},
    {"id":"clinical","name":"临床证据","level":"core","reason":"…"}
  ],
  "dimensions": ["tech","clinical","fda","reg"],  // 新：多维度归属（驱动 Library 分类）
  "primary_dimension": "技术",
  "research_plan": {                   // 新：研究计划（AI 建议 + 用户编辑）
    "goal": "确定刺激参数",
    "questions": ["频率多少？","脉宽多少？"],
    "scopes": ["tech","clinical","fda","reg"],
    "methods": ["参数 Benchmark"],
    "sources": ["FDA 数据库","PubMed"],
    "expected_outputs": ["参数建议表"]
  },
  "recipe_id": "parameter_definition", // 新：所用研究策略模板
  "product_id": "p_xxx"               // 绑定产品（旧能力保留）
}
```

`dimensions` 优先级（前端 `researchCats` / 后端 `_auto_archive` 一致）：
1. `r.dimensions`（动态 Scope 数组）→ 多维度
2. 否则 `r.scopes[].id`（动态对象）
3. 否则 `legacy_dimensions(r.research_type)`（旧 `research_type` 运行时映射，不物理迁移）

---

## 三、Creation Flow（创建主流程 · 五步）

入口：`s1` 顶部「🧭 问题驱动研究 · 推荐」CTA（独立自由研究）｜产品主页「＋ 继续研究这个产品」｜Overview 的 Gap / Hypothesis「继续研究」。三者统一路由到 `openDynamicResearch(p, presetQuestion)`。

```
Step 1 问题  → 填写 Research Question + 选 Recipe（可选）
   ↓
Step 2 背景  → 目标市场(多选) / 产品阶段 / 渠道(多选) / 背景说明（继承产品 Profile）
   ↓
Step 3 范围  → 调 POST /api/research/suggest-scope
              AI 返回 Scope 列表（core/optional/skip + 推荐原因）
              用户可：改 level（核心/可选/暂不建议）、移除、自定义添加
   ↓
Step 4 计划  → Goal / 子问题(增删) / Methods / Sources / Expected Outputs（均可编辑）
   ↓
Step 5 确认  → 汇总预览 → 「✅ 确认并开始研究」
              → POST /api/research (mode:'dynamic') → SCF 生成 → 归档
```

> Gap / Hypothesis 续研：不进入固定专题模板，而是生成对应问题后带入 `openDynamicResearch`，由 AI 重新判断 Scope（满足「Gap→继续研究闭环」「Hypothesis 验证闭环」）。

---

## 四、Dynamic Scope Logic（动态范围逻辑）

### 能力目录 `RESEARCH_SCOPES`（28 项，后端下发，前端不写死）
市场 / 用户 / 产品 / 竞品 / 技术 / 临床证据 / 科学证据 / 法规 / FDA / 专利 / 供应链 / BOM成本 / 材料 / 安全 / 风险 / 渠道 / 定价 / 商业模式 / 品牌 / 趋势 / 行业 / 政策 / 售后 / 制造 / 可持续 / 其他。
每项含：`title / icon / desc / methods / sources / trigger[] / medical? / parent?`。

### 双路推荐
- **离线启发式 `_suggest_scope_heuristic`**（无需 LLM，始终可用）：
  - 基础 core：市场/用户/竞品/产品/技术
  - 关键词命中 `trigger` → 加入对应 Scope
  - `_scope_conditions` 条件标志：`medical_or_health_claim` / `medical_market_us` / `medical_market_eu` / `innovation_tech` / `go_to_mass_production` / `not_ecom_product`
  - 条件规则：医疗/健康宣称 →（**clinical + reg** 为 core，US 再加 **fda** core）；创新/专利词 → **patent** optional；量产词 → **supply/bom/mfg/safety** core；非医疗 → **fda/reg** skip；非创新 → **patent** skip；非量产 → **supply** skip
- **在线 LLM `_suggest_scope_llm`**（配置了 Key 时优先）：从完整能力目录挑选真正相关的 Scope，FDA/法规/专利/供应链仅在确实相关时进 core；返回 scopes + methods + sources + research_plan（结构化）。

> 修复记录：首版 heuristic 对医疗产品漏了 `clinical`，已补 `clinical` 为 medical core（Case 1 验证）。

### 用户可编辑
每项的 `level` 可切 core / optional / skip；可移除；可「＋ 添加范围」自定义（id=`custom_<ts>`）。确认时仅 `level!=='skip'` 的 Scope 进入研究与报告。

---

## 五、Recipe Logic（研究策略模板）

`RESEARCH_RECIPES`（6 个，**非固定报告目录**，仅表达「面对某类任务通常该考虑哪些 Scope/Method/Source/Output」+ 条件判断）：

| recipe_id | 标题 | 默认 Scope | 条件 add / remove |
|---|---|---|---|
| `new_opportunity` | 新产品机会研究 | market/user/comp/product/tech | 医疗+clinical/reg；创新+patent；量产+supply/bom/mfg；非电商−channel |
| `parameter_definition` | 参数/技术方案定义 | tech/clinical/comp | 美市+**fda**/reg；创新+patent |
| `user_pain` | 用户痛点/差评研究 | user/comp | 医疗+clinical |
| `supply_massprod` | 供应链/量产研究 | tech/bom/supply/mfg/safety | 医疗+reg/material |
| `patent_landscape` | 专利布局研究 | patent/tech/comp | — |
| `free` | 自由研究（完全交给 AI） | （空） | — |

前端选 Recipe 后：①`openDynamicResearch` 渲染下拉；②AI 建议 Scope 后，前端把 Recipe 的 `default_scopes` 补齐到结果（缺则补、带原因「来自研究策略模板」）。Recipe 只影响「初始建议」，最终 Scope 由用户在 Step 3 拍板，不强制任何目录。

---

## 六、Historical Compatibility（历史兼容）

- **不物理迁移**：旧报告 `research_type`（market/ecom/comp/user/tech/reg/patent/sc/other/comprehensive）通过 `legacy_dimensions(rt)` 运行时映射到 `dimensions`，显示层 `researchCats` → `catLabel` 一致呈现。
- **旧创建入口保留**：standard / topic / comprehensive 模板仍可用（s1 表单），只是不再是唯一/强制路径；若用户走旧路，后端仍走原 `build_report` 标准/专题/综合分支（本次**未改动**）。
- **Overview / Gap / Hypothesis 不受影响**：Overview 读取、Pending Updates、确认更新 API 全部保留；Gap/Hypothesis 的「继续研究」改为先问问题（动态流程），但其写入 Overview、关联产品等旧能力不变。
- **Library 多维度**：旧单类报告继续按 legacy 维度显示；新动态报告按 `dimensions[]` 同时出现在多个分类，数据库仅一份（见 Case 8）。
- **`/api/status`**：新增 `researchScopes` + `researchRecipes`；旧字段 `researchTypes` / `dims` 仍返回，旧前端无感。

---

## 七、Modified Files（修改文件）

| 文件 | 变更 |
|---|---|
| `research-deck/server.py` | +`RESEARCH_SCOPES`(28) / +`RESEARCH_RECIPES`(6) / +`_scope_conditions` / +`_suggest_scope_heuristic` / +`_suggest_scope_llm` / +`_call_llm_json`(统一 JSON 调用) / +`build_dynamic_report` / +`legacy_dimensions` +`RTYPE_TO_DIM_LEGACY`；`build_report` 扩展签名 + `mode='dynamic'` 分支；`/api/research` 读取并转发全部动态字段；`/api/research/suggest-scope` 新端点（401 校验 + 启发式/LLM + research_plan 补全）；`/api/status` 暴露 `researchScopes`/`researchRecipes`；`_auto_archive` 存 `research_question/context/scopes/dimensions/primary_dimension/research_plan/recipe_id` |
| `research-deck/index.html` | `APP_VERSION`→v2.3.0；s1 顶部新增「问题驱动研究」CTA + `.dyn-entry` CSS；新增 `s10` 五步屏 + 全量 `dyn*` JS；`researchCats`/`catLabel`/`LEGACY_DIM` 多维度分类；`startResearchForProduct`/`continueFromGap`/`continueFromHypothesis` 改路由 `openDynamicResearch`；`bootStatus` 补 `window.__researchScopes`/`window.__researchRecipes` 赋值（修复 Recipe 下拉为空、动态分类显示 raw id 的 bug） |
| `research-deck/versions/v2.3.0/` | 归档（不覆盖旧版）：index.html / server.py / scf_bootstrap / test_v230_dynamic.py / DEPLOY.md / VERSIONING.md |
| `research-deck/researchdeck_deploy_v2.3.0.zip` | 部署包：scf_bootstrap(0o755,LF,0 CRLF) + server.py(0o644)，平铺根目录 |
| `.gitattributes` | 沿用（强制 scf_bootstrap/server.py LF） |

---

## 八、API Changes（接口变更）

### 新增
- `POST /api/research/suggest-scope`
  - 入参：`{ question, context{ markets, product_stage, channels, background, product_type, product_claims }, recipe_id }`
  - 出参：`{ scopes:[{id,name,level,reason}], methods:[{scope,name}], sources:[{name,priority}], expected_outputs:[], research_plan:{goal,questions,scopes,methods,sources,expected_outputs}, recipe_id }`
  - 鉴权：与 `/api/research` 同（设了 `RD_TOKEN` 则须 `Authorization: Bearer` 或 `?token=`）
  - 逻辑：有 LLM Key 走 `_suggest_scope_llm`，否则启发式；`research_plan` 缺省字段自动补全

### 修改
- `POST /api/research`：新增可选字段 `research_question / context / scopes / methods / sources / expected_outputs / research_plan / recipe_id / dimensions / primary_dimension / research_mode`；`mode` 新增 `'dynamic'`（走 `build_dynamic_report`）。旧字段 `topic/dims/source/mode(standard|topic|comprehensive|advanced)` 行为不变。
- `GET /api/status`：新增 `researchScopes`（filtered title/icon/desc/methods/sources）、`researchRecipes`（title/default_scopes/conditions）。

### 未变
- `/api/overviews`、`/api/reports`、`/api/products`、`/api/status` 既有字段与 Overview/Gap/Hypothesis 相关端点全部保留。

---

## 九、Test Results（验收 Case 1–8 + #27）

> 运行：`python test_v230_dynamic.py`（离线，仅 heuristic + 结构断言，不调用 LLM/网络）｜结果：**27/27 PASS**

| Case | 场景 | 断言 | 结果 |
|---|---|---|---|
| 1 | 医疗跨维度（盆底肌 EMS 参数，US+EU，医疗宣称） | tech/clinical/reg/fda(US) 均为 core；market/user/comp/product core | ✅ |
| 2 | 消费品差评（宠物饮水机退货，US，非医疗） | user/comp core；**fda/reg/patent 均 skip**（条件动态生效） | ✅ |
| 3 | 供应链量产（筋膜枪工厂/BOM/产能） | supply/bom/mfg/safety 均 core | ✅ |
| 4 | 专利布局（创新结构哺乳按摩器 FTO） | patent core（触发词+创新） | ✅ |
| 5 | 纯用户（颈枕不适） | user/comp core；supply skip | ✅ |
| 6 | Gap→问题驱动研究 | Gap 生成问题可驱动 Scope 推荐（非空） | ✅ |
| 7 | 历史 `research_type` 兼容 | `legacy_dimensions('market')==['mkt']`、`comprehensive`→5 维、缺省→`['other']` | ✅ |
| 8 | 多维度归档 | 动态报告 `dimensions:['fda','patent','tech']` → 同时出现在 3 类；旧 `research_type:'market'` → `['mkt']` 单类 | ✅ |
| #27 | 动态 Scope 真正驱动结构 | `build_dynamic_report` fallback 的 `sections` 键 = Scope 集（tech/clinical/fda/reg），**不含** ecom 等无关固定维度 | ✅ |

前端语法：`node --check` 主脚本 ✅；后端：`py_compile server.py` ✅。

---

## 十、Known Issues（已知问题）

1. **LLM 路径依赖 Key**：`suggest-scope` 与动态报告生成仅在 `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` 配置时启用 AI 精调；未配置回退启发式（可用，但 Scope 不带 AI 语义、报告走 fallback 结构）。线上 SCF 已配 LLM（v2.2.4 指纹确认 `llm:true`、`model:deepseek-chat`）。
2. **前端动态目录依赖后端版本**：`window.__researchScopes` 来自 `/api/status` 的 `researchScopes`；若连旧版后端（不返回该字段），动态分类标签降级为 legacy `RESEARCH_CATS`，Recipe 下拉为空。升级后端后自愈。
3. **未开发项（按用户要求本轮停止）**：Evidence Center、Insight Library、AI Chat/Q&A、PRD、PPT、新 Agent、知识图谱、自动产品定义、复杂 PM、协作工具——均未实现。
4. **待用户操作**：需将 `researchdeck_deploy_v2.3.0.zip` 重传至 SCF Web 函数（改 `server.py` 必重部署）；SCF 超时建议 300s；重传后用真实产品跑完整闭环（尤其 LLM 路径）验收。
5. **评分说明**：Case 1–8 为后端逻辑/结构断言；前端交互（s10 五步、拖拽编辑）为静态语法 + 逻辑核对，未在真实浏览器跑端到端（本环境无 GUI 浏览器）。

---

## 附：本轮交付清单
- `research-deck/server.py`（v2.3.0 后端，py_compile PASS）
- `research-deck/index.html`（v2.3.0 前端，node --check PASS）
- `research-deck/researchdeck_deploy_v2.3.0.zip`（部署包，LF+755）
- `research-deck/versions/v2.3.0/`（归档，不覆盖）
- `research-deck/test_v230_dynamic.py`（回归测试，27/27 PASS）
- `research-deck/DEV_REPORT_v2.3.0.md`（本报告）

> 按用户指令「本轮完成后停止，不要自行开发 Evidence Center、AI Q&A 或其他下一阶段功能。」开发已停止，待重传与验收。
