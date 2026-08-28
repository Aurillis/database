# 调研台版本管理约定（用户要求 2026-08-29 起生效）

> 规则：**修改 bug / 新增功能时，绝不覆盖旧版本；先归档当前版本，再生成新版本。**

## 操作流程（每次发版必须遵守）

1. **归档**：发布新版本前，把当前 `index.html`、`server.py`、`scf_bootstrap` 复制到
   `versions/<当前版本号>/` 目录（如 `versions/v1.5.1/`）。
2. **修改**：在新版本号下修改主文件（`index.html` / `server.py`），同时更新页面内版本标识。
3. **打包**：生成带版本号的部署包 `researchdeck_deploy_v<版本号>.zip`（放沙箱 `/workspace/`）。
4. **提交**：git commit 信息包含版本号，推送 main。
5. **记录**：更新 `MEMORY.md` 版本基线 + 日志；归档文件随仓库长期保留。

## 版本号规则（沿用项目约定）

- 新增功能/界面 → Minor（v1.5.0 → v1.6.0）
- 修 bug → Patch（v1.5.1 → v1.5.2）
- 不兼容/架构变更 → Major

## 归档目录结构

```
research-deck/versions/
├── v1.5.0/          # SCF 当前部署的后端（server.py + scf_bootstrap）
│   ├── server.py
│   └── scf_bootstrap
└── v1.5.1/          # 线上前端（index.html）
    └── index.html
```

## 回滚方式

- **前端**：把 `versions/<旧版本>/index.html` 复制回根目录 → 推 GitHub Pages。
- **后端**：把 `versions/<旧版本>/server.py` + `scf_bootstrap` 重新打包 → 上传腾讯云 SCF 部署。

## 注意

- `versions/` 目录属于仓库，正常提交保留（不进 .gitignore）。
- 部署包 zip 不放仓库（沙箱 `/workspace/` 保留），避免仓库膨胀。
