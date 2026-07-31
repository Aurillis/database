import json, os, datetime

BASE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE, "reports_meta.json"), "r", encoding="utf-8") as f:
    reports = json.load(f)

# Categorize
def categorize(title, filename):
    t = (title + " " + filename).lower()
    if "飞书云文档" in t or "feishu" in t:
        return "飞书文档"
    if "机会评分" in t or "opportunity" in t:
        return "机会评分看板"
    if "类目看板" in t or "category" in t:
        return "类目看板"
    if "评论分析" in t or "review" in t or "评价" in t:
        return "评论分析"
    if "技术" in t or "disclosure" in t or "tech" in t or "工程" in t:
        return "技术报告"
    if "历史" in t or "historical" in t or "销售数据" in t:
        return "历史数据"
    if "市场" in t or "调研" in t or "研究" in t or "market" in t:
        return "市场调研"
    return "其他"

for r in reports:
    r["category"] = categorize(r["title"], r["filename"])
    dt = datetime.datetime.fromtimestamp(r["mtime"])
    r["date_str"] = dt.strftime("%Y-%m-%d")
    r["size_str"] = f"{r['size']/1024:.0f} KB" if r["size"] < 1024*1024 else f"{r['size']/1024/1024:.1f} MB"

# Sort by date descending
reports.sort(key=lambda x: x["mtime"], reverse=True)

# Get unique categories
categories = []
seen = set()
for r in reports:
    if r["category"] not in seen:
        categories.append(r["category"])
        seen.add(r["category"])

# Category colors
cat_colors = {
    "机会评分看板": "#236b6f",
    "市场调研": "#245f93",
    "技术报告": "#a76508",
    "类目看板": "#534AB7",
    "评论分析": "#a83b35",
    "飞书文档": "#087f79",
    "历史数据": "#62707c",
    "其他": "#888780",
}

reports_json = json.dumps(reports, ensure_ascii=False)
categories_json = json.dumps(categories, ensure_ascii=False)
cat_colors_json = json.dumps(cat_colors, ensure_ascii=False)

html_content = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>调研报告中心</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
:root {{
  --bg: #f5f6f7;
  --card-bg: #ffffff;
  --ink: #1a1a1a;
  --muted: #6b7280;
  --line: #e5e7eb;
  --accent: #236b6f;
  --accent-light: #eef7f5;
  --radius: 12px;
  --shadow: 0 1px 3px rgba(0,0,0,.08), 0 1px 2px rgba(0,0,0,.04);
  --shadow-hover: 0 8px 25px rgba(0,0,0,.12);
}}
html {{ scroll-behavior: smooth; }}
body {{
  font-family: -apple-system, "Segoe UI", "Microsoft YaHei", Roboto, sans-serif;
  background: var(--bg);
  color: var(--ink);
  min-height: 100vh;
  font-size: 14px;
  line-height: 1.6;
}}

/* Header */
.header {{
  background: #fff;
  border-bottom: 1px solid var(--line);
  padding: 20px 0;
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: 0 1px 3px rgba(0,0,0,.04);
}}
.header-inner {{
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}}
.logo {{
  display: flex;
  align-items: center;
  gap: 10px;
}}
.logo-icon {{
  width: 36px; height: 36px;
  background: var(--accent);
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-size: 18px; font-weight: 800;
}}
.logo-text h1 {{
  font-size: 18px; font-weight: 700; color: var(--ink);
}}
.logo-text p {{
  font-size: 12px; color: var(--muted); margin-top: 1px;
}}
.stats {{
  display: flex; gap: 16px;
}}
.stat {{
  text-align: center;
}}
.stat b {{
  font-size: 22px; font-weight: 700; color: var(--accent);
  display: block;
}}
.stat span {{
  font-size: 11px; color: var(--muted);
}}

/* Main */
.main {{
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}}

/* Toolbar */
.toolbar {{
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
  align-items: center;
}}
.search-box {{
  flex: 1;
  min-width: 240px;
  position: relative;
}}
.search-box input {{
  width: 100%;
  padding: 11px 16px 11px 40px;
  border: 1px solid var(--line);
  border-radius: 8px;
  font-size: 14px;
  background: #fff;
  transition: border-color .2s;
  font-family: inherit;
}}
.search-box input:focus {{
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(35,107,111,.1);
}}
.search-box svg {{
  position: absolute;
  left: 13px; top: 50%;
  transform: translateY(-50%);
  color: var(--muted);
}}
.sort-select {{
  padding: 11px 14px;
  border: 1px solid var(--line);
  border-radius: 8px;
  font-size: 13px;
  background: #fff;
  cursor: pointer;
  font-family: inherit;
  color: var(--ink);
}}

/* Category chips */
.categories {{
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}}
.chip {{
  padding: 7px 14px;
  border-radius: 20px;
  border: 1px solid var(--line);
  background: #fff;
  font-size: 13px;
  cursor: pointer;
  transition: all .15s;
  color: var(--muted);
  white-space: nowrap;
  font-weight: 500;
}}
.chip:hover {{
  border-color: var(--accent);
  color: var(--accent);
}}
.chip.active {{
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}}
.chip .count {{
  font-size: 11px;
  opacity: .7;
  margin-left: 4px;
}}

/* Grid */
.grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 16px;
}}
.card {{
  background: var(--card-bg);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 18px 20px;
  cursor: pointer;
  transition: all .2s ease;
  display: flex;
  flex-direction: column;
  gap: 10px;
  position: relative;
  overflow: hidden;
}}
.card:hover {{
  box-shadow: var(--shadow-hover);
  transform: translateY(-2px);
  border-color: #d1d5db;
}}
.card::before {{
  content: '';
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 4px;
  background: var(--cat-color, var(--accent));
}}
.card-badge {{
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 4px;
  background: var(--cat-bg, var(--accent-light));
  color: var(--cat-color, var(--accent));
  width: fit-content;
}}
.card-title {{
  font-size: 15px;
  font-weight: 600;
  color: var(--ink);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}}
.card-meta {{
  display: flex;
  gap: 14px;
  font-size: 12px;
  color: var(--muted);
  align-items: center;
  margin-top: auto;
}}
.card-meta span {{
  display: flex;
  align-items: center;
  gap: 4px;
}}
.card-footer {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 8px;
  border-top: 1px solid #f3f4f6;
}}
.card-open {{
  font-size: 12px;
  font-weight: 600;
  color: var(--accent);
  display: flex;
  align-items: center;
  gap: 4px;
}}

/* Empty state */
.empty {{
  text-align: center;
  padding: 60px 20px;
  color: var(--muted);
}}
.empty svg {{
  margin-bottom: 12px;
  opacity: .3;
}}
.empty p {{
  font-size: 15px;
}}

/* Modal viewer */
.modal-overlay {{
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,.5);
  z-index: 1000;
  backdrop-filter: blur(2px);
}}
.modal-overlay.active {{
  display: block;
}}
.modal {{
  position: fixed;
  inset: 0;
  z-index: 1001;
  display: flex;
  flex-direction: column;
}}
.modal-header {{
  background: #1a1a1a;
  padding: 10px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-shrink: 0;
}}
.modal-header .title {{
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}}
.modal-actions {{
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}}
.modal-btn {{
  padding: 6px 14px;
  border-radius: 6px;
  border: none;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  font-family: inherit;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  transition: opacity .15s;
}}
.modal-btn:hover {{ opacity: .85; }}
.modal-btn-open {{
  background: #236b6f;
  color: #fff;
}}
.modal-btn-close {{
  background: #444;
  color: #fff;
}}
.modal-body {{
  flex: 1;
  background: #fff;
  overflow: hidden;
  position: relative;
}}
.modal-body iframe {{
  width: 100%;
  height: 100%;
  border: none;
}}

/* Responsive */
@media (max-width: 768px) {{
  .grid {{ grid-template-columns: 1fr; }}
  .header-inner {{ flex-direction: column; align-items: flex-start; }}
  .stats {{ width: 100%; justify-content: flex-start; }}
}}
</style>
</head>
<body>

<div class="header">
  <div class="header-inner">
    <div class="logo">
      <div class="logo-icon">R</div>
      <div class="logo-text">
        <h1>调研报告中心</h1>
        <p>Research Report Portal</p>
      </div>
    </div>
    <div class="stats">
      <div class="stat"><b id="totalCount">0</b><span>报告总数</span></div>
      <div class="stat"><b id="shownCount">0</b><span>当前显示</span></div>
    </div>
  </div>
</div>

<div class="main">
  <div class="toolbar">
    <div class="search-box">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
      <input type="text" id="searchInput" placeholder="搜索报告标题..." autocomplete="off">
    </div>
    <select class="sort-select" id="sortSelect">
      <option value="date-desc">最新优先</option>
      <option value="date-asc">最早优先</option>
      <option value="name-asc">名称 A-Z</option>
      <option value="name-desc">名称 Z-A</option>
      <option value="size-desc">文件最大</option>
      <option value="size-asc">文件最小</option>
    </select>
  </div>

  <div class="categories" id="categoryChips"></div>

  <div class="grid" id="reportGrid"></div>

  <div class="empty" id="emptyState" style="display:none;">
    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
    <p>没有找到匹配的报告</p>
  </div>
</div>

<div class="modal-overlay" id="modalOverlay" onclick="closeModal(event)"></div>
<div class="modal" id="modal" style="display:none;">
  <div class="modal-header">
    <span class="title" id="modalTitle">报告标题</span>
    <div class="modal-actions">
      <a class="modal-btn modal-btn-open" id="modalOpenNew" href="#" target="_blank" rel="noopener">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
        新标签打开
      </a>
      <button class="modal-btn modal-btn-close" onclick="closeModal()">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        关闭
      </button>
    </div>
  </div>
  <div class="modal-body">
    <iframe id="modalFrame" src="" sandbox="allow-same-origin allow-scripts allow-popups allow-forms"></iframe>
  </div>
</div>

<script>
const REPORTS = {reports_json};
const CATEGORIES = {categories_json};
const CAT_COLORS = {cat_colors_json};

let activeCategory = 'all';
let searchQuery = '';
let sortBy = 'date-desc';

function init() {{
  document.getElementById('totalCount').textContent = REPORTS.length;
  renderCategories();
  renderGrid();
}}

function renderCategories() {{
  const container = document.getElementById('categoryChips');
  let html = '<div class="chip active" data-cat="all" onclick="selectCategory(\'all\')">全部<span class="count">(' + REPORTS.length + ')</span></div>';
  CATEGORIES.forEach(cat => {{
    const count = REPORTS.filter(r => r.category === cat).length;
    html += '<div class="chip" data-cat="' + cat + '" onclick="selectCategory(\\'' + cat + '\\')">' + cat + '<span class="count">(' + count + ')</span></div>';
  }});
  container.innerHTML = html;
}}

function selectCategory(cat) {{
  activeCategory = cat;
  document.querySelectorAll('.chip').forEach(c => {{
    c.classList.toggle('active', c.dataset.cat === cat);
  }});
  renderGrid();
}}

function getFilteredReports() {{
  let filtered = REPORTS.filter(r => {{
    const catMatch = activeCategory === 'all' || r.category === activeCategory;
    const q = searchQuery.toLowerCase();
    const searchMatch = !q || r.title.toLowerCase().includes(q) || r.filename.toLowerCase().includes(q) || r.category.toLowerCase().includes(q);
    return catMatch && searchMatch;
  }});

  filtered.sort((a, b) => {{
    switch(sortBy) {{
      case 'date-desc': return b.mtime - a.mtime;
      case 'date-asc': return a.mtime - b.mtime;
      case 'name-asc': return a.title.localeCompare(b.title, 'zh');
      case 'name-desc': return b.title.localeCompare(a.title, 'zh');
      case 'size-desc': return b.size - a.size;
      case 'size-asc': return a.size - b.size;
      default: return 0;
    }}
  }});

  return filtered;
}}

function renderGrid() {{
  const filtered = getFilteredReports();
  document.getElementById('shownCount').textContent = filtered.length;
  const grid = document.getElementById('reportGrid');
  const empty = document.getElementById('emptyState');

  if (filtered.length === 0) {{
    grid.innerHTML = '';
    empty.style.display = 'block';
    return;
  }}
  empty.style.display = 'none';

  grid.innerHTML = filtered.map(r => {{
    const color = CAT_COLORS[r.category] || '#888';
    const colorBg = color + '15';
    return '<div class="card" style="--cat-color:' + color + ';--cat-bg:' + colorBg + '" onclick="openReport(\\'' + encodeURIComponent(r.filename) + '\\', ' + JSON.stringify(r.title).replace(/'/g, "\\'") + ')">' +
      '<div class="card-badge">' + r.category + '</div>' +
      '<div class="card-title">' + escapeHtml(r.title) + '</div>' +
      '<div class="card-meta">' +
        '<span><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>' + r.date_str + '</span>' +
        '<span><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>' + r.size_str + '</span>' +
      '</div>' +
      '<div class="card-footer">' +
        '<span style="font-size:11px;color:#bbb;font-family:monospace;">' + escapeHtml(r.filename.length > 40 ? '...' + r.filename.slice(-37) : r.filename) + '</span>' +
        '<span class="card-open">点击查看 <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg></span>' +
      '</div>' +
    '</div>';
  }}).join('');
}}

function escapeHtml(str) {{
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}}

function openReport(filename, title) {{
  const modal = document.getElementById('modal');
  const overlay = document.getElementById('modalOverlay');
  const frame = document.getElementById('modalFrame');
  const titleEl = document.getElementById('modalTitle');
  const openNew = document.getElementById('modalOpenNew');

  const url = 'reports/' + filename;
  frame.src = url;
  titleEl.textContent = title;
  openNew.href = url;
  modal.style.display = 'flex';
  overlay.classList.add('active');
  document.body.style.overflow = 'hidden';
}}

function closeModal(e) {{
  if (e && e.target !== document.getElementById('modalOverlay')) return;
  const modal = document.getElementById('modal');
  const overlay = document.getElementById('modalOverlay');
  const frame = document.getElementById('modalFrame');
  modal.style.display = 'none';
  overlay.classList.remove('active');
  frame.src = '';
  document.body.style.overflow = '';
}}

document.addEventListener('keydown', (e) => {{
  if (e.key === 'Escape') closeModal();
}});

document.getElementById('searchInput').addEventListener('input', (e) => {{
  searchQuery = e.target.value;
  renderGrid();
}});

document.getElementById('sortSelect').addEventListener('change', (e) => {{
  sortBy = e.target.value;
  renderGrid();
}});

init();
</script>
</body>
</html>'''

out_path = os.path.join(BASE, "index.html")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"Generated index.html with {len(reports)} reports across {len(categories)} categories")
print(f"Categories: {', '.join(categories)}")
