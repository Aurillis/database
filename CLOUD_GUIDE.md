# report-portal / database — 云端恢复指南（CLOUD_GUIDE）

> 本文件是「换设备也能立刻接手」的唯一真相源。它汇总了项目坐标、架构、SCF 配置、本地开发/部署流程与历史事故。
> 最后更新：2026-08-14

---

## 一、当前坐标

| 项 | 值 |
|----|----|
| GitHub 仓库 | `Aurillis/database`（`https://github.com/Aurillis/database`） |
| 站点（GitHub Pages） | `https://Aurillis.github.io/database/` |
| 后端函数（腾讯云 SCF） | `https://1461447139-m5rkq2fg8n.ap-guangzhou.tencentscf.com` |
| 默认分支 | `main` |
| 前端形态 | 静态 SPA，`gen_kb.py` 生成 `index.html`；按 `location.href` 动态推导仓库名，**换域名/路径无需改前端** |

> 历史改名：`chenbiyin1770/report-portal` → `chenbiyin1770/database` → `Aurillis/database`。前端动态适配，后端默认值与 SCF 环境变量需同步。

---

## 二、架构

- **前端**：GitHub Pages 静态托管（`index.html` 由 `gen_kb.py` 生成，`viewer.html` 独立）。
- **后端**：腾讯云 SCF（Node，`scf/index.js`）暴露 Function URL，做令牌鉴权。
  - 登录令牌：HMAC-SHA256 签名，`24h` 过期。
  - 能力：上传、删除（真删 git）、回收站（list/restore/purge/purgeall）、云同步 `meta.json`、分享（已休眠，前端不调用）。
- **存储**：GitHub Contents API（单文件 **1MB 硬限**，仓库 ~1GB 上限）。
  - 关键路径：`reports/`、`manifest.json`、`meta.json`、`trash/`、`backups/`、`shares/`（已弃用）。
- **云同步**：分类/标签存 `meta.json`（last-write-wins）；收藏/最近留浏览器 localStorage。

---

## 三、SCF 环境变量（控制台「函数配置 → 环境变量」）

**必填（缺了登录/上传直接失败）：**
| 变量 | 说明 |
|------|------|
| `ADMIN_PASSWORD` | 门户查看/管理密码（强密码，别用默认） |
| `SESSION_SECRET` | 随机串，令牌签名盐 |
| `GITHUB_TOKEN` | fine-grained PAT，仅授权 `Aurillis/database` 仓库的 Contents 读写 |

**选填（有默认值兜底，一般不用动）：**
| 变量 | 默认值 | 备注 |
|------|--------|------|
| `GITHUB_REPO` | `Aurillis/database` | 改名后已改对 |
| `GITHUB_BRANCH` | `main` | |
| `SITE_BASE` | `https://Aurillis.github.io/database` | 生成分享链接前缀，代码自动去尾斜杠 |
| `ALLOWED_ORIGIN` | 留空 | **留空 = 自动从 `SITE_BASE` 推导**允许的 origin；或显式填 `https://Aurillis.github.io`（已容错尾斜杠/大小写/多来源逗号分隔） |
| `MAX_UPLOAD_BYTES` | `15728640`（15MB） | 但 GitHub 实际只吃 1MB |
| `RATE_*` | 留空默认 | 频率限制 |

> 安全纪律：GitHub Token **只在 SCF 环境变量**，绝不进代码/聊天/截图明文。

---

## 四、重部署 SCF（改 `scf/index.js` 后必须做）

1. 腾讯云 SCF 控制台 → 进入函数 → **函数代码**。
2. 用「**上传文件**」按钮选本地 `scf/index.js`（**千万别贴 GitHub 网页 HTML**，也别手贴——大文件易截断导致 `Unexpected end of input`）。
3. 切「函数配置 → 环境变量」按上表填（尤其 `ALLOWED_ORIGIN` 留空最稳）。
4. 点「**保存并部署**」，等约 1 分钟生效。
5. **部署后自查**（本地 curl，绕过浏览器）：
   - `OPTIONS` 预检应返回 `204` 且带 `Access-Control-Allow-Origin: https://Aurillis.github.io`
   - `POST {op:"login",password:"x"}` 应返回 `401 {"error":"密码错误"}`（连通正常的标志）

---

## 五、本地开发 / 维护流程

```bash
# 1. 克隆（任意设备）
git clone https://github.com/Aurillis/database.git
cd database

# 2. 改前端逻辑 → 改生成器并重生成（保持 gen_kb.py 与 index.html 一致）
python gen_kb.py

# 3. 改后端 → 先语法校验再上传部署
node --check scf/index.js

# 4. 推送（本项目走代理）
git -c http.proxy=http://127.0.0.1:7897 push origin main
```

**分支冲突处理（关键坑）：**
- SCF 上传/删除会经 GitHub API 产生 commit，本地易与远端 divergence。
- 推送前先 `git pull --no-rebase origin main`（**用 merge 不要用 rebase**，rebase 在 Windows Git Bash 下易损坏 `.git`）。
- **本地 `.git` 损坏时**（症状：`git log` 报 `main has no commits`、`not a valid object`）：不要删 `.git`、不要移动整目录，直接
  ```bash
  git -c http.proxy=http://127.0.0.1:7897 fetch origin
  git reset --hard origin/main
  ```
  即可就地修复，工作区文件不动。

---

## 六、已实现功能清单

- ✅ 主页查看密码闸门（未解锁只见密码框）
- ✅ 令牌鉴权上传 / 删除（真删 GitHub 文件 + 写回 manifest）
- ✅ 回收站：查看 / 恢复 / 彻底删除 / 清空（删除前自动备份 `backups/reports/`）
- ✅ 分类/标签云同步（`meta.json`，换设备不丢）
- ✅ 移动端抽屉 + 汉堡菜单；`viewer.html`「关闭」按钮
- ✅ 上传日期显示到分钟（`YYYY-MM-DD HH:MM`，浏览器本地时区）
- ✅ 3 个真实分类：哺乳按摩器 / 痛经缓解产品 / 盆底肌修复仪；无分类文件统一显示「未分类」
- ✅ SCF 来源白名单归一化（去尾斜杠/大小写、多来源、留空自动推导）

---

## 七、已知限制 / 待办（按需推进）

- ⚠️ **隐私**：文件仍在公开 GitHub Pages，知道 `reports/<文件名>` 地址可直取；密码闸门只挡「友好浏览列表」。治本方案 = 私有存储 + 签名 URL（Cloudflare R2 方案）。
- ⚠️ **容量**：单文件 1MB 硬限（GitHub Contents API）；大文件需改用 Git Data API（100MB）。
- ⬜ 内容搜索（仅搜文件名/标题/分类/本机标签）未实现。
- ⬜ Office 文件在线预览 / 详情页未实现（之前选只做云同步，暂缓）。
- ⬜ 分享功能已移除（以密码闸门兜底），如要恢复需重新设计单篇隔离。

---

## 八、历史关键事故（排查速查）

| 现象 | 根因 | 解决 |
|------|------|------|
| 登录「无法连接服务端」 | SCF 部署的代码是坏 JS（先贴成 GitHub 网页 HTML，后贴截断） | 用「上传文件」部署正确的 `scf/index.js` |
| 登录「来源不被允许」403 | `ALLOWED_ORIGIN` 精确匹配，填成带尾斜杠 `https://Aurillis.github.io/` 不符 | 改归一化匹配 + 留空从 `SITE_BASE` 自动推导 |
| 上传后约 1 分钟才显示 | 旧逻辑读 Pages 构建后的 manifest | 改读 `raw.githubusercontent.com/.../manifest.json` 直读 |
| 删除后刷新又出现 | 误以为只清本地；真因 SCF 未部署带 `op:delete` 的版本 | 部署新 `scf/index.js`（真删 git） |
| 本地 `.git` 损坏 | rebase 中断遗留 | `fetch + reset --hard origin/main` 就地修复 |
| 上传下拉出现两个「其他」 | 代码硬编码「默认分类」+ 用户自建同名分类 | 去掉硬编码 + 清空 `meta.json` 的 `customCats` |

---

## 九、换设备恢复清单（checklist）

1. `git clone https://github.com/Aurillis/database.git`
2. 打开 `https://Aurillis.github.io/database/` 验证站点在线
3. 若后端异常 → 按「四、重部署 SCF」重新上传 `scf/index.js` 并核对环境变量
4. 本地改代码按「五」流程；改完推 `main`
5. 本对话已在 WorkBuddy 云端（同账号任意设备可见），历史上下文可用对话检索找回
