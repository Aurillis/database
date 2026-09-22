# Portal v2.3.5 — 紧急回归修复

## 触发
用户反馈：升级 v2.3.4 后「现在全部的文件夹都看不到了」。

## 根因
v2.3.4 重写侧边栏分类树渲染块（`nav-item` / `nav-children`）时，把
`cat.children.forEach(function(child) {` 这一行**循环开头漏写**，
仅保留了循环体内的 `var count = ...` 与闭合的 `});`。导致：

- `child` 变量从未声明；
- 第 1136 行 `});` 成为悬空闭合括号，树遍历回调出现悬空 `else`；
- 整段内联 `<script>` 抛出 `SyntaxError: Unexpected token ')'`；
- 侧边栏分类渲染函数崩溃 → **全部文件夹不显示**。

## 修复
在第 1130 行注释之后、`var count = ...` 之前补回循环开头：

```js
cat.children.forEach(function(child) {
```

功能意图不变：移除「直属文件」虚拟分组 + 父分类名可点击进入其下全部文件视图（直属+各子类）。

## 验证
- `new Function(code)` 对内联脚本做语法检查：修复前 `SYNTAX_ERROR: Unexpected token ')'`，修复后 `SYNTAX_OK`。
- `cat.children.forEach` 配对计数恢复为 1。

## 影响范围
纯前端（根 `index.html`）。GitHub Pages 自动生效（约 1–2 分钟）；SCF 未改动、无需重传。
