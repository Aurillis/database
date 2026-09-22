# 变更记录与版本标准（CHANGELOG）

> **本文件是项目版本号的唯一事实源（single source of truth）。**
> 作用：让任意新对话 / 新环境 `git clone Aurillis/database` 后，无需翻聊天记录即可知道当前版本、改动内容与如何回滚。
> 配套权威记忆：`PROJECT_MEMORY.md`（架构/红线/部署）+ `DESIGN.md`（设计规格）。
> **新对话接续方式**：读 `PROJECT_MEMORY.md` + `DESIGN.md` + 本文件即可。

---

## 一、版本标准（Versioning Standard）

项目含 **两条互不干扰的独立版本线**，各自升号、各自归档：

| 组件 | 范围 | 版本变量 | 归档目录 | 部署包命名 |
|------|------|----------|----------|------------|
| **主站 Portal** | 根 `index.html` + `scf/index.js`（知识库门户 + `report-portal-upload` 云函数） | `PORTAL_VERSION`（页脚/常量） | `portal/versions/vX.Y.Z/` | `portal/scf_upload_deploy_vX.Y.Z.zip` |
| **调研台 ResearchDeck** | `research-deck/index.html` + `research-deck/server.py`（`researchdeck_web` 云函数） | `APP_VERSION`（页脚/常量） | `research-deck/versions/vX.Y.Z/` | `researchdeck_deploy_vX.Y.Z.zip` |

**语义 `vMAJOR.MINOR.PATCH`**（沿用项目约定，2026-08-20 确认）：
- **MAJOR**：架构级 / 不兼容变更（如固定模板 → 动态 Research Creation Model）。
- **MINOR**：新增向后兼容功能（如新增上传重试、新增 `suggest-scope` 接口）。
- **PATCH**：修复 / 小调整（如上传超时降往返、CRLF 铁律扩展）。

### 每次改动必须执行的闭环（不可省略任一步）

1. **升版本号**：改对应组件的 `APP_VERSION` / `PORTAL_VERSION` 常量 + 页脚文案。
2. **归档**：按组件新建 `versions/vX.Y.Z/`，存入本次改动文件 + 部署包 +（可选）回归测试。
3. **出部署包**：
   - 主站（Node 函数）：zip 仅需平铺 `index.js`（已 LF 归一，无需 `scf_bootstrap`）。
   - 调研台（Python Web 函数）：zip 需 `server.py` + `scf_bootstrap`（绝对路径启动 + `PORT=9000` + 755 权限 + LF 结尾）。
4. **推 git**：提交到 `Aurillis/database` `main`（⚠️ 本仓库**禁止本地 `git rebase`**，用「重克隆 + 仅 overlay 本次改动 + 单提交」法，避免 `.git` 损坏）。
5. **记 CHANGELOG.md**：在下方「变更记录」表**追加一行**（版本/日期/组件/类型/摘要/部署包/备注）。
6. **同步本地记忆**：更新 `~/.workbuddy/.../MEMORY.md` 的「最新状态」版本号（本工作区自动注入，供本机后续对话快速参考）。
7. **部署生效**：改了后端逻辑必须重传部署包到对应 SCF 函数；前端 Pages 自动生效（约 1–2 分钟）。

> **永久红线（与版本无关，但每次改动都须遵守）**：
> 1. **主站隔离**——调研台改动只动 `research-deck/`；主站文件改动须先单独征得同意。
> 2. **无死数据**——模板/维度禁止写死固定产品真实数据（品牌/销量/份额），只允 LLM 实时生成或通用骨架。
> 3. **版本不覆盖**——旧版本先归档再出新版本，部署包按版本号命名。

---

## 二、最新状态（2026-09-22）

| 组件 | 当前版本 | 部署状态 | 备注 |
|------|----------|----------|------|
| 主站 Portal | **v2.3.4** | 代码已推 `main`；前端 Pages 自动生效（约 1–2 分钟）；SCF（`report-portal-upload`）未改动、无需重传 | 侧边栏 UX：移除「直属文件」虚拟分组，父分类名可直接点击查看其下全部文件（直属+各子类）；空子分类仍显示 |
| 调研台 ResearchDeck | **v2.3.0** | 代码已推 `main`；SCF 部署包 `researchdeck_deploy_v2.3.0.zip` 待用户重传 | 动态 Research Creation Model |

---

## 三、变更记录（Changelog）

> 格式：`版本 | 日期 | 组件 | 类型 | 摘要 | 部署包 | 备注`
> 历史版本（v1.0.0–v2.2.x）逐版明细见 `PROJECT_MEMORY.md` 的「版本基线」章节；下表为统一标准后的正式记录起点。

| 版本 | 日期 | 组件 | 类型 | 摘要 | 部署包 | 备注 |
|------|------|------|------|------|--------|------|
| **v2.3.4** | 2026-09-22 | 主站 Portal | PATCH | 侧边栏分类 UX Ⅱ：移除「直属文件」虚拟分组（原 `if(catFiles>0)` 渲染块）；父分类名点击改为 `selectCat(cat.id)` 进入该父分类**全部文件**视图（含直属+各子类，`getFilteredFiles` 父分类匹配其 children id），箭头仍 `toggleCat` 展开；用户不能批量移动文件、不想要该分组，故去掉 | 前端改动，无 SCF 部署包（推 GitHub Pages 即生效） | 根因：v2.3.3 把"未归类"改"直属文件"后仍显眼；用户反馈无法批量移动文件、不想要此分组；属主站改动（用户授权） |
| **v2.3.3** | 2026-09-22 | 主站 Portal | PATCH | 侧边栏分类 UX：①子分类 0 文件时不再隐藏（原 `count===0 return` 导致新建空子分类"凭空消失"，用户误以为变成了未归类）②父分类直属文件标签「未归类」改为「直属文件」，消除"分类变成未归类"的误解 | 前端改动，无 SCF 部署包（推 GitHub Pages 即生效） | 根因场景：用户在父级「新品调研」下新建「FDA代码库」，空分类被隐藏 + 直属文件叫"未归类"造成误会；属主站改动（用户授权） |
| **v2.3.2** | 2026-09-22 | 主站 Portal | PATCH | 分类 ID 生成修复：`makeCatId` 名称含中文时改走 `autoCatId` 追加唯一后缀，根治「FDA合规」「FDA目录」等含中文不同名塌缩成同一 `fda` 而撞车；`addCategory` 撞车报错改为显示已存在分类名+位置（如「FDA合规」（位于：盆底肌修复仪 下）已存在） | 前端改动，无 SCF 部署包（推 GitHub Pages 即生效） | 纯英文/数字分类仍保持干净 slug 不变；属主站改动（用户授权） |
| **v2.3.1** | 2026-09-07 | 主站 Portal | PATCH | 上传稳定性：新文件先 `PUT`(无 sha) 仅 3 次 GitHub 往返（原 5 次）；前端 `uploadOneFile` 网络错误自动重试 1 次；降低偶发 `Failed to fetch` | `portal/scf_upload_deploy_v2.3.1.zip` | 配合用户控制台把 `report-portal-upload` 函数+网关超时调 30s 方基本消除超时；属主站改动（用户授权） |
| **v2.3.0** | 2026-09-02 | 调研台 ResearchDeck | MAJOR | 动态 Research Creation Model：Question→Context→AI Scope→Plan→Research；FDA/法规/专利/供应链改为条件动态能力；`mode='dynamic'` + `POST /api/research/suggest-scope`；Recipe 替代固定模板；多维度 Library；历史 `research_type` 运行时兼容；集成测试 27/27 PASS | `researchdeck_deploy_v2.3.0.zip` | 取消所有固定模板强制性；红线：不开发 Evidence Center/AI Q&A 等下一阶段功能 |

---

## 四、回滚方式

- **主站前端**：把 `portal/versions/<旧版本>/index.html` 复制回根目录 → 推 GitHub Pages。
- **主站后端**：把 `portal/versions/<旧版本>/index.js` 重新上传到 `report-portal-upload` SCF 函数。
- **调研台前端**：把 `research-deck/versions/<旧版本>/index.html` 复制回 `research-deck/` → 推 Pages。
- **调研台后端**：把 `research-deck/versions/<旧版本>/server.py` + `scf_bootstrap` 重新打包 → 上传 `researchdeck_web` SCF 函数。
