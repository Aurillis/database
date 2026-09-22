# Portal v2.3.2 归档

发布日期：2026-09-22
类型：PATCH（主站前端修复）
部署方式：将根 `index.html` 推送到 `main` 即由 GitHub Pages 自动生效（约 1–2 分钟）。
后端 SCF（`report-portal-upload`）本次未改动，**无需重传**。

## 修复内容
1. `makeCatId`：名称含中文（非 ASCII）时改走 `autoCatId` 追加唯一后缀，
   根治「FDA合规」「FDA目录」等含中文不同名塌缩成同一 `fda` 而撞车的问题。
   - 验证：`FDA合规`→`fda-xxxx`、`FDA目录`→`fda-yyyy`（不同 ID，可共存）
   - 纯英文/数字分类（如 `lactation`、`FDA`）仍保持干净 slug 不变
2. `addCategory`：撞车报错由裸 ID（"分类ID已存在：fda"）改为显示已存在
   分类名+位置（如「分类「FDA合规」（位于：盆底肌修复仪 下）已存在，无法重复创建」）。

## 文件
- `index.html`：主站前端（已修复）
- `index.js`：SCF 上传函数快照（本次未改动，仅供回滚参考）
