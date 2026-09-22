# 主站 Portal v2.3.4 — 侧边栏移除「直属文件」分组

> 类型：PATCH（前端 UX 修复）｜组件：主站 Portal（根 `index.html`）｜部署：推 GitHub Pages 自动生效，SCF 无需重传

## 背景
用户在父级分类「新品调研」下新建子分类「FDA代码库」后，侧边栏展开「新品调研」会显示一个「直属文件」虚拟分组（= 直接挂在父级、未归进任何子类的文件）。
v2.3.3 把旧名「未归类」改成「直属文件」后仍显眼；用户反馈**门户不能批量移动文件**，逐个改分类不现实，因此不想要这个分组。

## 改动
1. **移除「直属文件」虚拟分组渲染**（原 `renderSidebar` 中 `if (catFiles > 0)` 块）。侧边栏父分类下只列子分类，不再单列"直属文件"。
2. **父分类名可点击查看全部文件**：父分类 `nav-item` 改为拆分交互——箭头 `toggleCat` 负责展开/收起；分类名/图标 `selectCat(cat.id)` 进入该父分类文件视图。
3. **`getFilteredFiles` 父分类含子类**：当 `S.cat` 是父分类时，过滤条件扩展为 `getFileCat===S.cat || 属于该父分类的某个子类`，即点父分类名看到**直属 + 各子类全部文件**，文件不丢。

## 验证
- 复刻 `getFilteredFiles` 逻辑：父分类点击返回 `[直属a, 子类b, 子类c]`，不含 other；子类点击仍仅返回自身文件。
- grep 确认侧边栏无「直属文件」UI 字符串；父分类名 `selectCat` + 箭头 `toggleCat` 均就位。

## 文件
- `index.html`（改动：1055-1062 `getFilteredFiles`；1115-1128 `renderSidebar` 父分类渲染）
- `index.js`（SCF 快照，本次未改动，仅随版本归档）

## 回滚
将 `portal/versions/v2.3.3/index.html` 复制回根目录 → 推 GitHub Pages 即回退到"直属文件分组存在"状态。
