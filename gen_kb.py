#!/usr/bin/env python3
"""Knowledge Base Portal Generator
Generates a complete single-page application for browsing HTML research reports.
"""
import json, pathlib, re

BASE = pathlib.Path(__file__).parent
META = json.loads((BASE / 'reports_meta.json').read_text(encoding='utf-8'))

# Vercel serverless function URL (set empty; fill after deploying upload-api).
# The GitHub token lives ONLY on that server — never embedded in this page.
UPLOAD_API_PLACEHOLDER = 'https://report-portal-m2lnxphol-chenbiyin1770-5040s-projects.vercel.app/api/upload'

# ===== CATEGORY TREE =====
TREE = [
    {"id": "product", "name": "产品研究", "icon": "fas fa-box", "children": [
        {"id": "product-pelvic", "name": "盆底肌训练器", "icon": "fas fa-flask"},
        {"id": "product-lactation", "name": "哺乳按摩器", "icon": "fas fa-baby"},
        {"id": "product-pump", "name": "乳房泵", "icon": "fas fa-heartbeat"},
        {"id": "product-sterilizer", "name": "奶瓶消毒器", "icon": "fas fa-shield-alt"},
        {"id": "product-warmer", "name": "暖奶器", "icon": "fas fa-mug-hot"},
        {"id": "product-muscle", "name": "肌肉刺激器", "icon": "fas fa-bolt"},
        {"id": "product-sinus", "name": "鼻腔药品", "icon": "fas fa-pills"},
    ]},
    {"id": "market", "name": "市场分析", "icon": "fas fa-chart-bar"},
    {"id": "tech", "name": "技术研究", "icon": "fas fa-cogs"},
    {"id": "review", "name": "评论分析", "icon": "fas fa-comments"},
    {"id": "history", "name": "历史数据", "icon": "fas fa-history"},
    {"id": "feishu", "name": "飞书文档", "icon": "fas fa-file-alt"},
    {"id": "other", "name": "其他", "icon": "fas fa-folder"},
]

def categorize(filename, title):
    f = filename.lower()
    t = title.lower()
    c = f + " " + t
    if "飞书云文档" in c: return "feishu"
    if "review" in f or "评价" in c: return "review"
    if "bladder" in f or "盆底肌" in c or "pelvic" in c: return "product-pelvic"
    if "breast_pump" in f or "electric_breast_pumps" in f: return "product-pump"
    if "bottle sterilizer" in f: return "product-sterilizer"
    if "bottle warmer" in f or "bottle%20warmers" in f: return "product-warmer"
    if "muscle stimulator" in f: return "product-muscle"
    if "sinus" in f: return "product-sinus"
    if "哺乳" in c or "lactation" in c: return "product-lactation"
    if "历史" in c or "销售数据" in c: return "history"
    if "技术" in c or "disclosure" in c or "工程" in c or "插头" in c: return "tech"
    if "市场" in c or "调研" in c or "研究" in c: return "market"
    return "other"

# Process files
files = []
for r in META:
    title = r['title']
    title = re.sub(r'\.html\s*-\s*飞书云文档.*$', '', title, flags=re.IGNORECASE)
    title = title.replace('&amp;', '&')
    cat = categorize(r['filename'], title)
    files.append({
        "filename": r['filename'],
        "title": title,
        "size": r['size'],
        "mtime": r['mtime'],
        "category": cat,
        "isUploaded": False,
    })

files_json = json.dumps(files, ensure_ascii=False)
tree_json = json.dumps(TREE, ensure_ascii=False)

# ===== MANIFEST (dynamic file list, updated by serverless upload) =====
# Stored at repo root so the portal can fetch it (same origin on GitHub Pages).
# The serverless upload function also rewrites this file after each upload.
manifest = []
local_names = set(f["filename"] for f in files)
# Preserve remote-only entries (e.g. files uploaded via the website that are not
# present locally) so a local regen + push never drops web-uploaded reports.
existing = {}
mp = BASE / 'manifest.json'
if mp.exists():
    try:
        for e in json.loads(mp.read_text(encoding='utf-8')):
            existing[e["filename"]] = e
    except Exception:
        pass
for f in files:
    manifest.append({
        "filename": f["filename"],
        "title": f["title"],
        "size": f["size"],
        "mtime": f["mtime"],
        "category": f["category"],
    })
for e in existing.values():
    if e["filename"] not in local_names:
        manifest.append(e)
(BASE / 'manifest.json').write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'Generated manifest.json: {len(manifest)} files ({len(local_names)} local)')

# ===== CSS =====
CSS = r"""
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#f8f9fa;--sidebar-bg:#fff;--card-bg:#fff;
  --ink:#1a1a2e;--muted:#6b7280;--light:#9ca3af;
  --line:#e5e7eb;--hover:#f3f4f6;--hover2:#eef2f7;
  --accent:#236b6f;--accent-light:#e8f4f3;--accent-dark:#1a5559;
  --danger:#e53e3e;--warning:#d97706;
  --radius:8px;--radius-lg:12px;
  --shadow:0 1px 3px rgba(0,0,0,.06);
  --shadow-md:0 4px 12px rgba(0,0,0,.08);
  --shadow-lg:0 8px 30px rgba(0,0,0,.12);
  --sidebar-w:280px;
}
html{scroll-behavior:smooth}
body{
  font-family:-apple-system,"Segoe UI","Microsoft YaHei",Roboto,sans-serif;
  background:var(--bg);color:var(--ink);font-size:14px;line-height:1.6;
  -webkit-font-smoothing:antialiased;
}
a{color:inherit;text-decoration:none}
button{font-family:inherit;cursor:pointer;border:none;background:none}
input,select{font-family:inherit}

/* ===== HEADER ===== */
.header{
  background:#fff;border-bottom:1px solid var(--line);
  height:56px;display:flex;align-items:center;
  padding:0 24px;gap:16px;position:sticky;top:0;z-index:100;
  box-shadow:0 1px 2px rgba(0,0,0,.04);
}
.logo{display:flex;align-items:center;gap:8px;flex-shrink:0}
.logo-icon{
  width:32px;height:32px;background:var(--accent);
  border-radius:7px;display:flex;align-items:center;justify-content:center;
  color:#fff;font-size:16px;
}
.logo-text{font-size:16px;font-weight:700;color:var(--ink)}
.search-bar{flex:1;max-width:500px;position:relative}
.search-bar input{
  width:100%;padding:8px 12px 8px 36px;
  border:1px solid var(--line);border-radius:var(--radius);
  font-size:13px;background:var(--bg);transition:all .2s;
}
.search-bar input:focus{outline:none;border-color:var(--accent);background:#fff;box-shadow:0 0 0 3px rgba(35,107,111,.1)}
.search-bar i{position:absolute;left:12px;top:50%;transform:translateY(-50%);color:var(--light);font-size:13px}
.header-right{display:flex;align-items:center;gap:8px;margin-left:auto}
.icon-btn{
  width:36px;height:36px;border-radius:var(--radius);
  display:flex;align-items:center;justify-content:center;
  color:var(--muted);transition:all .15s;
}
.icon-btn:hover{background:var(--hover);color:var(--ink)}
.icon-btn.active{background:var(--accent-light);color:var(--accent)}
.badge{
  background:var(--danger);color:#fff;font-size:10px;font-weight:700;
  padding:1px 5px;border-radius:8px;position:absolute;top:4px;right:4px;
}

/* ===== LAYOUT ===== */
.layout{display:flex;min-height:calc(100vh - 56px)}

/* ===== SIDEBAR ===== */
.sidebar{
  width:var(--sidebar-w);background:var(--sidebar-bg);
  border-right:1px solid var(--line);padding:12px 0;
  overflow-y:auto;position:sticky;top:56px;
  height:calc(100vh - 56px);flex-shrink:0;
}
.sidebar-section{padding:0 8px;margin-bottom:8px}
.sidebar-label{font-size:11px;font-weight:600;color:var(--light);text-transform:uppercase;letter-spacing:.5px;padding:8px 12px 4px}
.nav-item{
  display:flex;align-items:center;gap:8px;
  padding:7px 12px;border-radius:var(--radius);
  font-size:13px;font-weight:500;color:var(--ink);
  cursor:pointer;transition:all .12s;user-select:none;
}
.nav-item:hover{background:var(--hover)}
.nav-item.active{background:var(--accent-light);color:var(--accent)}
.nav-item i{width:16px;text-align:center;font-size:13px;color:var(--muted)}
.nav-item.active i{color:var(--accent)}
.nav-item .count{margin-left:auto;font-size:11px;color:var(--light)}
.nav-children{padding-left:12px}
.nav-child{
  display:flex;align-items:center;gap:8px;
  padding:5px 12px 5px 36px;border-radius:6px;
  font-size:12px;color:var(--muted);cursor:pointer;
  transition:all .12s;
}
.nav-child:hover{background:var(--hover);color:var(--ink)}
.nav-child.active{color:var(--accent);font-weight:600}
.nav-child .count{margin-left:auto;font-size:10px;color:var(--light)}
.tree-chevron{font-size:10px;transition:transform .2s;color:var(--light)}
.tree-chevron.open{transform:rotate(90deg)}
.sidebar-add{
  margin:8px 12px;padding:8px;border:1px dashed var(--line);
  border-radius:var(--radius);text-align:center;font-size:12px;
  color:var(--muted);cursor:pointer;transition:all .15s;
}
.sidebar-add:hover{border-color:var(--accent);color:var(--accent);background:var(--accent-light)}

/* ===== MAIN CONTENT ===== */
.main{flex:1;padding:24px;overflow-x:hidden;min-width:0}
.main-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;gap:12px;flex-wrap:wrap}
.main-title{font-size:20px;font-weight:700}
.main-tools{display:flex;gap:8px;align-items:center}
.sort-select{
  padding:6px 12px;border:1px solid var(--line);border-radius:6px;
  font-size:12px;background:#fff;color:var(--ink);cursor:pointer;
}
.view-btn{
  width:32px;height:32px;border-radius:6px;
  display:flex;align-items:center;justify-content:center;
  color:var(--muted);transition:all .15s;
}
.view-btn:hover,.view-btn.active{background:var(--hover);color:var(--accent)}

/* ===== FILE GRID ===== */
.file-grid{
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(280px,1fr));
  gap:14px;
}
.file-card{
  background:var(--card-bg);border:1px solid var(--line);
  border-radius:var(--radius-lg);padding:16px;
  cursor:pointer;transition:all .2s;position:relative;
  display:flex;flex-direction:column;gap:8px;
}
.file-card:hover{box-shadow:var(--shadow-md);transform:translateY(-2px);border-color:#d1d5db}
.file-card-top{display:flex;align-items:flex-start;gap:10px}
.file-card-icon{
  width:36px;height:36px;border-radius:8px;flex-shrink:0;
  display:flex;align-items:center;justify-content:center;
  font-size:16px;
}
.file-card-body{flex:1;min-width:0}
.file-card-title{
  font-size:14px;font-weight:600;line-height:1.4;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;
  overflow:hidden;
}
.file-card-cat{font-size:11px;color:var(--light);margin-top:3px}
.file-card-tags{display:flex;flex-wrap:wrap;gap:4px}
.file-tag{
  font-size:10px;padding:2px 7px;border-radius:4px;
  background:#f0f0f0;color:var(--muted);
}
.file-card-footer{
  display:flex;align-items:center;justify-content:space-between;
  padding-top:8px;border-top:1px solid #f5f5f5;
  font-size:11px;color:var(--light);
}
.file-card-footer .left{display:flex;gap:10px;align-items:center}
.fav-btn{
  width:28px;height:28px;border-radius:6px;
  display:flex;align-items:center;justify-content:center;
  color:var(--light);transition:all .15s;flex-shrink:0;
}
.fav-btn:hover{background:var(--hover);color:var(--warning)}
.fav-btn.active{color:var(--warning)}

/* ===== FILE LIST VIEW ===== */
.file-list{display:flex;flex-direction:column;gap:2px}
.list-item{
  display:flex;align-items:center;gap:12px;
  padding:10px 14px;border-radius:var(--radius);cursor:pointer;
  transition:all .12s;
}
.list-item:hover{background:var(--hover)}
.list-item .li-icon{width:28px;height:28px;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:13px;flex-shrink:0}
.list-item .li-title{flex:1;font-size:13px;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.list-item .li-cat{font-size:11px;color:var(--light);flex-shrink:0}
.list-item .li-date{font-size:11px;color:var(--light);flex-shrink:0;width:80px}
.list-item .li-size{font-size:11px;color:var(--light);flex-shrink:0;width:60px;text-align:right}

/* ===== EMPTY ===== */
.empty-state{text-align:center;padding:80px 20px;color:var(--light)}
.empty-state i{font-size:48px;margin-bottom:16px;opacity:.3}
.empty-state p{font-size:14px}

/* ===== ADMIN PANEL ===== */
.admin-overlay{
  position:fixed;inset:0;background:rgba(0,0,0,.4);z-index:200;
  backdrop-filter:blur(4px);display:none;
}
.admin-overlay.show{display:flex;align-items:center;justify-content:center}
.admin-box{
  background:#fff;border-radius:var(--radius-lg);width:420px;
  padding:32px;box-shadow:var(--shadow-lg);
}
.admin-box h2{font-size:18px;margin-bottom:8px;text-align:center}
.admin-box p{font-size:12px;color:var(--muted);text-align:center;margin-bottom:20px}
.admin-box input{
  width:100%;padding:10px 14px;border:1px solid var(--line);
  border-radius:var(--radius);font-size:14px;margin-bottom:12px;
}
.admin-box input:focus{outline:none;border-color:var(--accent)}
.admin-box .btn{
  width:100%;padding:10px;border-radius:var(--radius);
  font-size:14px;font-weight:600;transition:all .15s;
}
.btn-primary{background:var(--accent);color:#fff}
.btn-primary:hover{background:var(--accent-dark)}
.admin-error{color:var(--danger);font-size:12px;text-align:center;min-height:18px}

/* ===== ADMIN VIEW ===== */
.admin-view{padding:24px}
.admin-header{
  display:flex;align-items:center;justify-content:space-between;
  margin-bottom:20px;
}
.admin-tabs{display:flex;gap:2px;background:var(--hover);padding:3px;border-radius:8px;margin-bottom:20px}
.admin-tab{
  padding:7px 16px;border-radius:6px;font-size:13px;font-weight:500;
  color:var(--muted);cursor:pointer;transition:all .15s;
}
.admin-tab.active{background:#fff;color:var(--ink);box-shadow:var(--shadow)}
.admin-section{display:none}
.admin-section.show{display:block}

/* Upload area */
.upload-zone{
  border:2px dashed var(--line);border-radius:var(--radius-lg);
  padding:40px;text-align:center;cursor:pointer;transition:all .2s;
  margin-bottom:16px;
}
.upload-zone:hover,.upload-zone.dragover{border-color:var(--accent);background:var(--accent-light)}
.upload-zone i{font-size:36px;color:var(--light);margin-bottom:12px}
.upload-zone p{font-size:13px;color:var(--muted)}
.upload-zone .hint{font-size:11px;color:var(--light);margin-top:4px}

/* Admin file table */
.admin-table{width:100%;border-collapse:collapse;font-size:13px}
.admin-table th{
  text-align:left;padding:8px 12px;border-bottom:1px solid var(--line);
  font-size:11px;font-weight:600;color:var(--light);text-transform:uppercase;
}
.admin-table td{padding:8px 12px;border-bottom:1px solid #f5f5f5}
.admin-table tr:hover{background:var(--hover)}
.admin-table .actions{display:flex;gap:4px}
.admin-table .act-btn{
  width:28px;height:28px;border-radius:5px;
  display:flex;align-items:center;justify-content:center;
  color:var(--muted);transition:all .15s;
}
.admin-table .act-btn:hover{background:var(--hover2)}
.admin-table .act-btn.danger:hover{background:#fee;color:var(--danger)}

/* Category editor */
.cat-editor{display:flex;flex-direction:column;gap:8px}
.cat-row{
  display:flex;align-items:center;gap:8px;
  padding:8px 12px;border:1px solid var(--line);border-radius:var(--radius);
}
.cat-row .cat-name{flex:1;font-size:13px;font-weight:500}
.cat-row .cat-id{font-size:11px;color:var(--light);font-family:monospace}
.cat-row .act-btn{width:28px;height:28px;border-radius:5px;display:flex;align-items:center;justify-content:center;color:var(--muted);transition:all .15s}
.cat-row .act-btn:hover{background:var(--hover2)}

/* Tag editor */
.tag-editor{display:flex;flex-wrap:wrap;gap:6px;padding:12px;border:1px solid var(--line);border-radius:var(--radius);min-height:48px}
.tag-chip{
  display:inline-flex;align-items:center;gap:6px;
  padding:4px 10px;border-radius:6px;background:var(--accent-light);
  color:var(--accent);font-size:12px;font-weight:500;
}
.tag-chip .remove{cursor:pointer;opacity:.6}
.tag-chip .remove:hover{opacity:1}
.tag-input-row{display:flex;gap:8px;margin-top:8px}
.tag-input-row input{flex:1;padding:8px 12px;border:1px solid var(--line);border-radius:var(--radius);font-size:13px}

/* ===== MODAL ===== */
.modal-overlay{
  position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:300;
  display:none;align-items:center;justify-content:center;
}
.modal-overlay.show{display:flex}
.modal-box{
  background:#fff;border-radius:var(--radius-lg);
  width:90%;max-width:500px;box-shadow:var(--shadow-lg);
  overflow:hidden;
}
.modal-header{
  padding:16px 20px;border-bottom:1px solid var(--line);
  display:flex;align-items:center;justify-content:space-between;
}
.modal-header h3{font-size:15px;font-weight:600}
.modal-body{padding:20px}
.modal-body input,.modal-body select{
  width:100%;padding:8px 12px;border:1px solid var(--line);
  border-radius:var(--radius);font-size:13px;margin-bottom:10px;
}
.modal-body input:focus,.modal-body select:focus{outline:none;border-color:var(--accent)}
.modal-footer{padding:12px 20px;border-top:1px solid var(--line);display:flex;justify-content:flex-end;gap:8px}
.btn-sm{padding:6px 14px;border-radius:6px;font-size:12px;font-weight:600}
.btn-ghost{background:var(--hover);color:var(--ink)}
.btn-ghost:hover{background:var(--hover2)}

/* ===== PREVIEW MODAL ===== */
.preview-overlay{
  position:fixed;inset:0;z-index:400;display:none;
  flex-direction:column;background:#fff;
}
.preview-overlay.show{display:flex}
.preview-header{
  background:#1a1a2e;padding:10px 16px;
  display:flex;align-items:center;justify-content:space-between;gap:12px;
}
.preview-title{color:#fff;font-size:13px;font-weight:600;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.preview-actions{display:flex;gap:6px}
.preview-btn{
  padding:5px 12px;border-radius:5px;font-size:12px;font-weight:600;
  transition:opacity .15s;
}
.preview-btn:hover{opacity:.85}
.preview-btn-open{background:var(--accent);color:#fff}
.preview-btn-close{background:#444;color:#fff}
.preview-body{flex:1;overflow:hidden;position:relative}
.preview-body iframe{width:100%;height:100%;border:none}

/* ===== TOAST ===== */
.toast{
  position:fixed;bottom:24px;left:50%;transform:translateX(-50%);
  background:#1a1a2e;color:#fff;padding:10px 20px;border-radius:8px;
  font-size:13px;z-index:500;box-shadow:var(---shadow-lg);
  opacity:0;transition:opacity .3s,bottom .3s;pointer-events:none;
}
.toast.show{opacity:1;bottom:32px}

/* ===== RESPONSIVE ===== */
@media(max-width:900px){
  .sidebar{position:fixed;left:-280px;z-index:99;transition:left .2s}
  .sidebar.show{left:0}
  .main{padding:16px}
  .file-grid{grid-template-columns:1fr}
}
"""

# ===== HTML BODY =====
HTML = r"""
<!-- Font Awesome -->
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">

<!-- Header -->
<div class="header">
  <div class="logo">
    <div class="logo-icon"><i class="fas fa-book-open"></i></div>
    <span class="logo-text">我的研究知识库</span>
  </div>
  <div class="search-bar">
    <i class="fas fa-search"></i>
    <input type="text" id="searchInput" placeholder="搜索文件名、标签、分类..." autocomplete="off">
  </div>
  <div class="header-right">
    <button class="icon-btn" id="favBtn" title="收藏夹"><i class="fas fa-star"></i></button>
    <button class="icon-btn" id="recentBtn" title="最近访问"><i class="fas fa-clock-rotate-left"></i></button>
    <button class="icon-btn" id="adminBtn" title="管理后台"><i class="fas fa-gear"></i></button>
  </div>
</div>

<!-- Layout -->
<div class="layout">
  <!-- Sidebar -->
  <div class="sidebar" id="sidebar"></div>
  <!-- Main -->
  <div class="main" id="main"></div>
</div>

<!-- Admin Login -->
<div class="admin-overlay" id="adminLogin">
  <div class="admin-box">
    <h2><i class="fas fa-lock"></i> 管理员登录</h2>
    <p>请输入管理密码访问后台</p>
    <input type="password" id="adminPwdInput" placeholder="管理密码" autofocus>
    <div class="admin-error" id="adminError"></div>
    <button class="btn btn-primary" id="adminLoginBtn">登录</button>
    <p style="margin-top:12px;font-size:11px;color:var(--light)">默认密码: admin123</p>
  </div>
</div>

<!-- Admin Panel -->
<div class="admin-view" id="adminPanel" style="display:none"></div>

<!-- Generic Modal -->
<div class="modal-overlay" id="modal">
  <div class="modal-box">
    <div class="modal-header">
      <h3 id="modalTitle">标题</h3>
      <button class="icon-btn" onclick="closeModal()"><i class="fas fa-times"></i></button>
    </div>
    <div class="modal-body" id="modalBody"></div>
    <div class="modal-footer" id="modalFooter"></div>
  </div>
</div>

<!-- Preview Modal -->
<div class="preview-overlay" id="preview">
  <div class="preview-header">
    <span class="preview-title" id="previewTitle">报告预览</span>
    <div class="preview-actions">
      <a class="preview-btn preview-btn-open" id="previewOpen" href="#" target="_blank">
        <i class="fas fa-external-link-alt"></i> 新标签打开
      </a>
      <button class="preview-btn preview-btn-close" onclick="closePreview()">
        <i class="fas fa-times"></i> 关闭
      </button>
    </div>
  </div>
  <div class="preview-body">
    <iframe id="previewFrame" src=""></iframe>
  </div>
</div>

<!-- Toast -->
<div class="toast" id="toast"></div>
"""

# ===== JAVASCRIPT =====
JS = r"""
// ===== CONFIG =====
// Vercel serverless function URL that handles uploads (set during deploy).
// The GitHub token lives ONLY on that server, never in this page.
var UPLOAD_API = '__UPLOAD_API__';

// Upload secret sent to the Vercel function as the x-upload-secret header.
// This is INDEPENDENT of the admin login password (S.adminPwd) — changing the
// admin password must NOT break uploads. It must match the Vercel env var
// UPLOAD_SECRET. Keep the two in sync if you ever change it.
var UPLOAD_SECRET = 'admin123';

var FILES = __FILES_JSON__;
var TREE = __TREE_JSON__;

// Load the dynamic manifest (rewritten by the upload function after each upload).
// Falls back to the embedded data if the manifest can't be fetched.
(function loadManifest() {
  // cache-buster (changes every minute) so newly uploaded files appear after rebuild
  var url = 'manifest.json?t=' + Math.floor(Date.now() / 60000);
  fetch(url).then(function(r) { return r.json(); }).then(function(d) {
    if (Array.isArray(d) && d.length) { FILES = d; renderSidebar(); renderMain(); }
  }).catch(function() { /* keep embedded fallback */ });
})();

var S = {
  view: 'browser',      // 'browser' | 'admin'
  cat: 'all',
  search: '',
  sort: 'date-desc',
  gridView: true,
  isAdmin: false,
  showFav: false,
  showRecent: false,
  expanded: {},
  // localStorage data
  favorites: LS('kb_favorites', []),
  recent: LS('kb_recent', []),
  fileTags: LS('kb_fileTags', {}),
  allTags: LS('kb_allTags', []),
  customCats: LS('kb_customCats', []),
  uploaded: LS('kb_uploaded', []),
  adminPwd: localStorage.getItem('kb_adminPwd') || 'admin123',
  fileCats: LS('kb_fileCats', {}),  // custom category overrides
};

function LS(k, def) {
  try { var v = JSON.parse(localStorage.getItem(k)); return v || def; } catch(e) { return def; }
}
function Save() {
  localStorage.setItem('kb_favorites', JSON.stringify(S.favorites));
  localStorage.setItem('kb_recent', JSON.stringify(S.recent));
  localStorage.setItem('kb_fileTags', JSON.stringify(S.fileTags));
  localStorage.setItem('kb_allTags', JSON.stringify(S.allTags));
  localStorage.setItem('kb_customCats', JSON.stringify(S.customCats));
  localStorage.setItem('kb_uploaded', JSON.stringify(S.uploaded));
  localStorage.setItem('kb_fileCats', JSON.stringify(S.fileCats));
  if (S.adminPwd) localStorage.setItem('kb_adminPwd', S.adminPwd);
}

// ===== UTILS =====
function esc(s) { var d=document.createElement('div'); d.textContent=s; return d.innerHTML; }
function fmtDate(ts) { var d=new Date(ts*1000); return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0'); }
function fmtSize(b) { if(b<1048576) return Math.round(b/1024)+' KB'; return (b/1048576).toFixed(1)+' MB'; }
function toast(msg) { var t=document.getElementById('toast'); t.textContent=msg; t.classList.add('show'); setTimeout(function(){t.classList.remove('show')},2500); }

function getAllFiles() {
  var uploaded = S.uploaded.map(function(f) {
    return {filename:f.name, title:f.title||f.name, size:f.size, mtime:f.mtime, category:f.category||'other', isUploaded:true, data:f.data};
  });
  return FILES.concat(uploaded);
}

function getFileCat(filename) {
  if (S.fileCats[filename]) return S.fileCats[filename];
  var f = getAllFiles().find(function(f) { return f.filename === filename; });
  return f ? f.category : 'other';
}

function getTree() { return TREE.concat(S.customCats); }

function catName(catId) {
  for (var i=0; i<TREE.length; i++) {
    if (TREE[i].id === catId) return TREE[i].name;
    if (TREE[i].children) {
      for (var j=0; j<TREE[i].children.length; j++) {
        if (TREE[i].children[j].id === catId) return TREE[i].children[j].name;
      }
    }
  }
  for (var k=0; k<S.customCats.length; k++) {
    if (S.customCats[k].id === catId) return S.customCats[k].name;
  }
  return catId;
}

function catIcon(catId) {
  for (var i=0; i<TREE.length; i++) {
    if (TREE[i].id === catId) return TREE[i].icon||'fas fa-folder';
    if (TREE[i].children) {
      for (var j=0; j<TREE[i].children.length; j++) {
        if (TREE[i].children[j].id === catId) return TREE[i].children[j].icon||'fas fa-file';
      }
    }
  }
  for (var k=0; k<S.customCats.length; k++) {
    if (S.customCats[k].id === catId) return S.customCats[k].icon||'fas fa-folder';
  }
  return 'fas fa-folder';
}

function catColor(catId) {
  var colors = {
    'product':'#236b6f','product-pelvic':'#236b6f','product-lactation':'#e6783c',
    'product-pump':'#534AB7','product-sterilizer':'#087f79','product-warmer':'#a76508',
    'product-muscle':'#6366f1','product-sinus':'#0891b2','market':'#245f93',
    'tech':'#a76508','review':'#a83b35','history':'#62707c','feishu':'#087f79',
    'other':'#888780'
  };
  return colors[catId] || '#888780';
}

function getFilteredFiles() {
  var all = getAllFiles();
  var filtered = all;

  if (S.showFav) {
    filtered = filtered.filter(function(f) { return S.favorites.indexOf(f.filename) >= 0; });
  } else if (S.showRecent) {
    filtered = S.recent.map(function(fn) { return all.find(function(f) { return f.filename === fn; }); }).filter(Boolean);
  } else if (S.cat !== 'all') {
    filtered = filtered.filter(function(f) { return getFileCat(f.filename) === S.cat; });
  }

  if (S.search) {
    var q = S.search.toLowerCase();
    filtered = filtered.filter(function(f) {
      if (f.title.toLowerCase().indexOf(q) >= 0) return true;
      if (f.filename.toLowerCase().indexOf(q) >= 0) return true;
      if (catName(getFileCat(f.filename)).toLowerCase().indexOf(q) >= 0) return true;
      var tags = S.fileTags[f.filename] || [];
      for (var i=0; i<tags.length; i++) { if (tags[i].toLowerCase().indexOf(q) >= 0) return true; }
      return false;
    });
  }

  filtered.sort(function(a,b) {
    switch(S.sort) {
      case 'date-desc': return b.mtime - a.mtime;
      case 'date-asc': return a.mtime - b.mtime;
      case 'name-asc': return a.title.localeCompare(b.title, 'zh');
      case 'name-desc': return b.title.localeCompare(a.title, 'zh');
      case 'size-desc': return b.size - a.size;
      case 'size-asc': return a.size - b.size;
    }
    return 0;
  });
  return filtered;
}

// ===== RENDER SIDEBAR =====
function renderSidebar() {
  var sb = document.getElementById('sidebar');
  var all = getAllFiles();
  var html = '';

  html += '<div class="sidebar-section">';
  html += '<div class="sidebar-label">浏览</div>';
  html += '<div class="nav-item' + (S.cat==='all' && !S.showFav && !S.showRecent ? ' active' : '') + '" onclick="selectCat(\'all\')">';
  html += '<i class="fas fa-folder-open"></i> 全部文件 <span class="count">'+all.length+'</span></div>';
  html += '<div class="nav-item' + (S.showFav ? ' active' : '') + '" onclick="showFavorites()">';
  html += '<i class="fas fa-star"></i> 收藏 <span class="count">'+S.favorites.length+'</span></div>';
  html += '<div class="nav-item' + (S.showRecent ? ' active' : '') + '" onclick="showRecent()">';
  html += '<i class="fas fa-clock-rotate-left"></i> 最近访问 <span class="count">'+S.recent.length+'</span></div>';
  html += '</div>';

  // Category tree
  html += '<div class="sidebar-section">';
  html += '<div class="sidebar-label">分类目录</div>';

  getTree().forEach(function(cat) {
    if (cat.children) {
      var isExp = S.expanded[cat.id] !== false;
      var childCount = cat.children.reduce(function(acc, c) {
        return acc + all.filter(function(f) { return getFileCat(f.filename) === c.id; }).length;
      }, 0);
      var catFiles = all.filter(function(f) { return getFileCat(f.filename) === cat.id; }).length;
      var totalCount = childCount + catFiles;

      html += '<div class="nav-item" onclick="toggleCat(\''+cat.id+'\')">';
      html += '<i class="fas fa-chevron-right tree-chevron'+(isExp?' open':'')+'"></i>';
      html += '<i class="'+(cat.icon||'fas fa-folder')+'"></i> '+esc(cat.name);
      html += '<span class="count">'+totalCount+'</span></div>';

      if (isExp) {
        html += '<div class="nav-children">';
        // Parent category files
        if (catFiles > 0) {
          html += '<div class="nav-child'+(S.cat===cat.id?' active':'')+'" onclick="event.stopPropagation();selectCat(\''+cat.id+'\')">';
          html += '<i class="fas fa-dot-circle"></i> 其他 <span class="count">'+catFiles+'</span></div>';
        }
        cat.children.forEach(function(child) {
          var count = all.filter(function(f) { return getFileCat(f.filename) === child.id; }).length;
          if (count === 0) return;
          html += '<div class="nav-child'+(S.cat===child.id?' active':'')+'" onclick="event.stopPropagation();selectCat(\''+child.id+'\')">';
          html += '<i class="'+(child.icon||'fas fa-file')+'"></i> '+esc(child.name)+' <span class="count">'+count+'</span></div>';
        });
        html += '</div>';
      }
    } else {
      var count = all.filter(function(f) { return getFileCat(f.filename) === cat.id; }).length;
      if (count === 0 && cat.id === 'other') return;
      html += '<div class="nav-item'+(S.cat===cat.id?' active':'')+'" onclick="selectCat(\''+cat.id+'\')">';
      html += '<i class="'+(cat.icon||'fas fa-folder')+'"></i> '+esc(cat.name)+' <span class="count">'+count+'</span></div>';
    }
  });

  html += '</div>';

  // Tags section
  if (S.allTags.length > 0) {
    html += '<div class="sidebar-section">';
    html += '<div class="sidebar-label">标签</div>';
    S.allTags.slice(0, 15).forEach(function(tag) {
      html += '<div class="nav-item" onclick="searchTag(\''+esc(tag)+'\')" style="font-size:12px">';
      html += '<i class="fas fa-tag" style="font-size:10px"></i> #'+esc(tag)+'</div>';
    });
    html += '</div>';
  }

  // Add category button (admin only)
  if (S.isAdmin) {
    html += '<div class="sidebar-add" onclick="addCategoryModal()">';
    html += '<i class="fas fa-plus"></i> 新增分类</div>';
  }

  sb.innerHTML = html;
}

function toggleCat(id) {
  S.expanded[id] = S.expanded[id] === false ? true : false;
  renderSidebar();
}

function selectCat(id) {
  S.cat = id; S.showFav = false; S.showRecent = false;
  renderSidebar(); renderMain();
}

function showFavorites() {
  S.showFav = true; S.showRecent = false; S.cat = 'all';
  renderSidebar(); renderMain();
}

function showRecent() {
  S.showRecent = true; S.showFav = false; S.cat = 'all';
  renderSidebar(); renderMain();
}

function searchTag(tag) {
  document.getElementById('searchInput').value = tag;
  S.search = tag;
  renderMain();
}

// ===== RENDER MAIN =====
function renderMain() {
  var main = document.getElementById('main');
  var files = getFilteredFiles();
  var title = '';

  if (S.showFav) title = '收藏夹';
  else if (S.showRecent) title = '最近访问';
  else if (S.cat === 'all') title = '全部文件';
  else title = catName(S.cat);

  var html = '';
  html += '<div class="main-header">';
  html += '<div class="main-title">'+esc(title)+' <span style="font-size:14px;color:var(--light);font-weight:400">('+files.length+')</span></div>';
  html += '<div class="main-tools">';
  html += '<select class="sort-select" id="sortSelect">';
  html += '<option value="date-desc"'+(S.sort==='date-desc'?' selected':'')+'>最新优先</option>';
  html += '<option value="date-asc"'+(S.sort==='date-asc'?' selected':'')+'>最早优先</option>';
  html += '<option value="name-asc"'+(S.sort==='name-asc'?' selected':'')+'>名称 A-Z</option>';
  html += '<option value="name-desc"'+(S.sort==='name-desc'?' selected':'')+'>名称 Z-A</option>';
  html += '<option value="size-desc"'+(S.sort==='size-desc'?' selected':'')+'>文件最大</option>';
  html += '<option value="size-asc"'+(S.sort==='size-asc'?' selected':'')+'>文件最小</option>';
  html += '</select>';
  html += '<button class="view-btn'+(S.gridView?' active':'')+'" onclick="setView(true)" title="卡片视图"><i class="fas fa-grip"></i></button>';
  html += '<button class="view-btn'+(!S.gridView?' active':'')+'" onclick="setView(false)" title="列表视图"><i class="fas fa-list"></i></button>';
  html += '</div></div>';

  if (files.length === 0) {
    html += '<div class="empty-state"><i class="fas fa-folder-open"></i><p>没有找到匹配的文件</p></div>';
  } else if (S.gridView) {
    html += '<div class="file-grid">';
    files.forEach(function(f) {
      var cat = getFileCat(f.filename);
      var color = catColor(cat);
      var tags = S.fileTags[f.filename] || [];
      var isFav = S.favorites.indexOf(f.filename) >= 0;

      html += '<div class="file-card" onclick="openFile(\''+esc(f.filename)+'\',\''+esc(f.title)+'\')">';
      html += '<div class="file-card-top">';
      html += '<div class="file-card-icon" style="background:'+color+'15"><i class="fas fa-file-lines" style="color:'+color+'"></i></div>';
      html += '<div class="file-card-body">';
      html += '<div class="file-card-title">'+esc(f.title)+'</div>';
      html += '<div class="file-card-cat"><i class="'+catIcon(cat)+'"></i> '+esc(catName(cat))+'</div>';
      html += '</div>';
      html += '<button class="fav-btn'+(isFav?' active':'')+'" onclick="event.stopPropagation();toggleFav(\''+esc(f.filename)+'\')"><i class="fas fa-star"></i></button>';
      html += '</div>';

      if (tags.length > 0) {
        html += '<div class="file-card-tags">';
        tags.slice(0,4).forEach(function(t) { html += '<span class="file-tag">'+esc(t)+'</span>'; });
        html += '</div>';
      }

      html += '<div class="file-card-footer">';
      html += '<div class="left"><span><i class="far fa-calendar"></i> '+fmtDate(f.mtime)+'</span><span><i class="fas fa-weight-hanging"></i> '+fmtSize(f.size)+'</span></div>';
      html += '<span style="color:var(--accent);font-weight:600">打开 <i class="fas fa-arrow-right"></i></span>';
      html += '</div></div>';
    });
    html += '</div>';
  } else {
    html += '<div class="file-list">';
    files.forEach(function(f) {
      var cat = getFileCat(f.filename);
      var color = catColor(cat);
      var isFav = S.favorites.indexOf(f.filename) >= 0;
      html += '<div class="list-item" onclick="openFile(\''+esc(f.filename)+'\',\''+esc(f.title)+'\')">';
      html += '<div class="li-icon" style="background:'+color+'15"><i class="fas fa-file-lines" style="color:'+color+'"></i></div>';
      html += '<span class="li-title">'+esc(f.title)+'</span>';
      html += '<span class="li-cat">'+esc(catName(cat))+'</span>';
      html += '<span class="li-date">'+fmtDate(f.mtime)+'</span>';
      html += '<span class="li-size">'+fmtSize(f.size)+'</span>';
      html += '<button class="fav-btn'+(isFav?' active':'')+'" style="width:24px;height:24px" onclick="event.stopPropagation();toggleFav(\''+esc(f.filename)+'\')"><i class="fas fa-star"></i></button>';
      html += '</div>';
    });
    html += '</div>';
  }

  main.innerHTML = html;

  document.getElementById('sortSelect').onchange = function(e) {
    S.sort = e.target.value; renderMain();
  };
}

function setView(grid) { S.gridView = grid; renderMain(); }

// ===== FILE OPERATIONS =====
function openFile(filename, title) {
  // Add to recent
  S.recent = [filename].concat(S.recent.filter(function(f) { return f !== filename; })).slice(0, 20);
  Save();

  var file = getAllFiles().find(function(f) { return f.filename === filename; });
  if (!file) return;

  if (file.isUploaded && file.data) {
    // Open from base64
    var parts = file.data.split(',');
    var mime = parts[0].match(/:(.*?);/)[1];
    var bstr = atob(parts[1]);
    var n = bstr.length;
    var u8 = new Uint8Array(n);
    while (n--) u8[n] = bstr.charCodeAt(n);
    var blob = new Blob([u8], {type: mime});
    var url = URL.createObjectURL(blob);
    window.open(url, '_blank');
  } else {
    var url = 'reports/' + encodeURIComponent(filename);
    window.open(url, '_blank');
  }
  renderSidebar();
}

function toggleFav(filename) {
  var idx = S.favorites.indexOf(filename);
  if (idx >= 0) { S.favorites.splice(idx, 1); toast('已取消收藏'); }
  else { S.favorites.push(filename); toast('已收藏'); }
  Save(); renderSidebar(); renderMain();
}

// ===== SEARCH =====
document.getElementById('searchInput').addEventListener('input', function(e) {
  S.search = e.target.value; renderMain();
});

// ===== HEADER BUTTONS =====
document.getElementById('favBtn').addEventListener('click', function() {
  S.showFav = !S.showFav; S.showRecent = false;
  this.classList.toggle('active', S.showFav);
  document.getElementById('recentBtn').classList.remove('active');
  renderSidebar(); renderMain();
});

document.getElementById('recentBtn').addEventListener('click', function() {
  S.showRecent = !S.showRecent; S.showFav = false;
  this.classList.toggle('active', S.showRecent);
  document.getElementById('favBtn').classList.remove('active');
  renderSidebar(); renderMain();
});

document.getElementById('adminBtn').addEventListener('click', function() {
  if (S.isAdmin) { showAdminPanel(); }
  else { document.getElementById('adminLogin').classList.add('show'); document.getElementById('adminPwdInput').focus(); }
});

// ===== ADMIN LOGIN =====
document.getElementById('adminLoginBtn').addEventListener('click', function() {
  var pwd = document.getElementById('adminPwdInput').value;
  if (pwd === S.adminPwd) {
    S.isAdmin = true;
    document.getElementById('adminLogin').classList.remove('show');
    document.getElementById('adminPwdInput').value = '';
    document.getElementById('adminError').textContent = '';
    showAdminPanel();
  } else {
    document.getElementById('adminError').textContent = '密码错误，请重试';
  }
});

document.getElementById('adminPwdInput').addEventListener('keydown', function(e) {
  if (e.key === 'Enter') document.getElementById('adminLoginBtn').click();
});

// ===== ADMIN PANEL =====
function showAdminPanel() {
  var panel = document.getElementById('adminPanel');
  var main = document.getElementById('main');
  var sidebar = document.getElementById('sidebar');

  main.style.display = 'none';
  sidebar.style.display = 'none';
  panel.style.display = 'block';

  panel.innerHTML = `
    <div class="admin-header">
      <h2 style="font-size:20px;font-weight:700"><i class="fas fa-gear"></i> 管理后台</h2>
      <div style="display:flex;gap:8px">
        <button class="btn btn-sm btn-ghost" onclick="exitAdmin()"><i class="fas fa-arrow-left"></i> 返回</button>
      </div>
    </div>
    <div class="admin-tabs">
      <div class="admin-tab active" onclick="switchAdminTab('upload',this)">文件上传</div>
      <div class="admin-tab" onclick="switchAdminTab('files',this)">文件管理</div>
      <div class="admin-tab" onclick="switchAdminTab('cats',this)">分类管理</div>
      <div class="admin-tab" onclick="switchAdminTab('tags',this)">标签管理</div>
      <div class="admin-tab" onclick="switchAdminTab('settings',this)">设置</div>
    </div>
    <div id="adminContent"></div>
  `;
  renderAdminUpload();
}

function exitAdmin() {
  document.getElementById('adminPanel').style.display = 'none';
  document.getElementById('main').style.display = '';
  document.getElementById('sidebar').style.display = '';
  renderSidebar(); renderMain();
}

function switchAdminTab(tab, el) {
  document.querySelectorAll('.admin-tab').forEach(function(t) { t.classList.remove('active'); });
  el.classList.add('active');
  if (tab === 'upload') renderAdminUpload();
  else if (tab === 'files') renderAdminFiles();
  else if (tab === 'cats') renderAdminCats();
  else if (tab === 'tags') renderAdminTags();
  else if (tab === 'settings') renderAdminSettings();
}

function renderAdminUpload() {
  var c = document.getElementById('adminContent');
  c.innerHTML = `
    <div style="background:var(--accent-light);border:1px solid #cfe8e3;border-radius:12px;padding:18px;margin-bottom:18px">
      <h3 style="font-size:16px;font-weight:700;margin-bottom:6px">📤 上传文件到知识库</h3>
      <p style="font-size:13px;color:var(--muted);line-height:1.9">
        ① 点击下方「选择文件」按钮，或直接把文件拖到下方虚线框　② 选择归属分类　③ 自动上传到服务器<br>
        支持 <b>.html .htm .css .js .png .jpg .gif .svg</b>（可一次选多个）。<br>
        上传成功后文件会出现在对应分类，刷新页面约 1 分钟即可见。
      </p>
    </div>
    <button class="btn btn-primary" id="uploadPickBtn" style="margin-bottom:14px"><i class="fas fa-folder-open"></i> 选择文件上传</button>
    <div class="upload-zone" id="uploadZone">
      <i class="fas fa-cloud-arrow-up"></i>
      <p style="font-weight:600">点击选择文件，或拖拽到此处</p>
      <p class="hint">支持 .html .htm .css .js .png .jpg .gif .svg（可多选）</p>
    </div>
    <input type="file" id="fileInput" multiple accept=".html,.htm,.css,.js,.png,.jpg,.jpeg,.gif,.svg" style="display:none">
    <div id="uploadCatSelect" style="margin:16px 0 12px">
      <label style="font-size:12px;color:var(--muted)">上传到分类:</label>
      <select id="uploadCat" class="sort-select" style="width:100%;margin-top:4px;padding:8px"></select>
    </div>
    <div id="uploadResult"></div>
  `;

  // Populate category select
  var sel = document.getElementById('uploadCat');
  var opts = '<option value="other">默认分类</option>';
  getTree().forEach(function(cat) {
    if (cat.children) {
      opts += '<optgroup label="'+esc(cat.name)+'">';
      cat.children.forEach(function(ch) { opts += '<option value="'+ch.id+'">'+esc(ch.name)+'</option>'; });
      opts += '</optgroup>';
    } else {
      opts += '<option value="'+cat.id+'">'+esc(cat.name)+'</option>';
    }
  });
  sel.innerHTML = opts;
  sel.value = S.cat === 'all' ? 'other' : S.cat;

  var zone = document.getElementById('uploadZone');
  var input = document.getElementById('fileInput');

  document.getElementById('uploadPickBtn').onclick = function() { input.click(); };
  zone.onclick = function() { input.click(); };

  zone.ondragover = function(e) { e.preventDefault(); this.classList.add('dragover'); };
  zone.ondragleave = function() { this.classList.remove('dragover'); };
  zone.ondrop = function(e) {
    e.preventDefault(); this.classList.remove('dragover');
    handleUpload(e.dataTransfer.files);
  };
  input.onchange = function() { handleUpload(this.files); };
}

function handleUpload(fileList) {
  var cat = document.getElementById('uploadCat').value;
  var result = document.getElementById('uploadResult');

  var files = Array.from(fileList).filter(function(f) {
    return f.name.match(/\.(html?|css|js|png|jpe?g|gif|svg)$/i);
  });
  var bad = Array.from(fileList).filter(function(f) {
    return !f.name.match(/\.(html?|css|js|png|jpe?g|gif|svg)$/i);
  });

  if (files.length === 0) {
    result.innerHTML = '<p style="color:var(--danger)">没有支持的文件格式</p>';
    return;
  }
  if (!UPLOAD_API) {
    result.innerHTML = '<p style="color:var(--danger)">上传功能未配置：缺少服务端地址（UPLOAD_API）</p>';
    return;
  }

  result.innerHTML = '<p style="color:var(--muted)">正在上传 ' + files.length + ' 个文件到服务器...</p>';
  var done = 0, ok = 0, fail = [];

  files.forEach(function(file) {
    var reader = new FileReader();
    reader.onload = function(e) {
      var dataUrl = e.target.result;
      var base64 = dataUrl.split(',')[1] || '';
      fetch(UPLOAD_API, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-upload-secret': UPLOAD_SECRET },
        body: JSON.stringify({ filename: file.name, content: base64, category: cat })
      })
      .then(function(r) { return r.json().then(function(j) { return { ok: r.ok, j: j }; }); })
      .then(function(resp) {
        done++;
        if (resp.ok) ok++;
        else fail.push(file.name + ' (' + (resp.j.error || '失败') + ')');
        if (done === files.length) finishUpload(result, ok, fail, bad);
      })
      .catch(function(e) {
        done++;
        var msg = (e && e.message) ? e.message : '无法连接服务端';
        fail.push(file.name + ' (网络错误：' + msg + '｜多为 Vercel 登录墙未关 或 浏览器连不上 vercel.app)');
        if (done === files.length) finishUpload(result, ok, fail, bad);
      });
    };
    reader.readAsDataURL(file);
  });
}

function finishUpload(result, ok, fail, bad) {
  var html = '';
  if (ok > 0) html += '<p style="color:var(--accent)">✓ 成功上传 ' + ok + ' 个文件到服务器</p>';
  fail.forEach(function(n) { html += '<p style="color:var(--danger)">✗ ' + esc(n) + '</p>'; });
  bad.forEach(function(f) { html += '<p style="color:var(--warning)">⚠ ' + esc(f.name) + ' - 不支持的格式</p>'; });
  html += '<p style="font-size:12px;color:var(--muted);margin-top:8px">文件已保存到 GitHub 仓库，约 1 分钟后刷新页面即可在列表中看到。</p>';
  result.innerHTML = html;
  renderSidebar();
  toast('上传完成');
}

function renderAdminFiles() {
  var c = document.getElementById('adminContent');
  var all = getAllFiles();
  var html = '<table class="admin-table"><thead><tr><th>文件名</th><th>分类</th><th>大小</th><th>日期</th><th>操作</th></tr></thead><tbody>';

  all.forEach(function(f) {
    var cat = getFileCat(f.filename);
    html += '<tr>';
    html += '<td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'+esc(f.title)+'</td>';
    html += '<td>'+esc(catName(cat))+'</td>';
    html += '<td>'+fmtSize(f.size)+'</td>';
    html += '<td>'+fmtDate(f.mtime)+'</td>';
    html += '<td><div class="actions">';
    html += '<button class="act-btn" title="打开" onclick="openFile(\''+esc(f.filename)+'\',\''+esc(f.title)+'\')"><i class="fas fa-external-link-alt"></i></button>';
    html += '<button class="act-btn" title="移动分类" onclick="moveFileModal(\''+esc(f.filename)+'\')"><i class="fas fa-folder-tree"></i></button>';
    html += '<button class="act-btn" title="编辑标签" onclick="editTagsModal(\''+esc(f.filename)+'\')"><i class="fas fa-tag"></i></button>';
    if (f.isUploaded) {
      html += '<button class="act-btn danger" title="删除" onclick="deleteFile(\''+esc(f.filename)+'\')"><i class="fas fa-trash"></i></button>';
    }
    html += '</div></td>';
    html += '</tr>';
  });
  html += '</tbody></table>';
  c.innerHTML = html;
}

function renderAdminCats() {
  var c = document.getElementById('adminContent');
  var html = '<div style="margin-bottom:16px"><button class="btn btn-sm btn-primary" onclick="addCategoryModal()"><i class="fas fa-plus"></i> 新增分类</button></div>';
  html += '<div class="cat-editor">';

  getTree().forEach(function(cat) {
    html += '<div class="cat-row">';
    html += '<i class="'+(cat.icon||'fas fa-folder')+'" style="color:'+catColor(cat.id)+'"></i>';
    html += '<span class="cat-name">'+esc(cat.name)+'</span>';
    html += '<span class="cat-id">'+cat.id+'</span>';
    if (cat.id !== 'other') {
      html += '<button class="act-btn" title="编辑" onclick="editCategoryModal(\''+cat.id+'\')"><i class="fas fa-edit"></i></button>';
      if (S.customCats.find(function(c){return c.id===cat.id})) {
        html += '<button class="act-btn danger" title="删除" onclick="deleteCategory(\''+cat.id+'\')"><i class="fas fa-trash"></i></button>';
      }
    }
    html += '</div>';
    if (cat.children) {
      cat.children.forEach(function(ch) {
        html += '<div class="cat-row" style="margin-left:20px">';
        html += '<i class="'+(ch.icon||'fas fa-file')+'" style="color:'+catColor(ch.id)+'"></i>';
        html += '<span class="cat-name">'+esc(ch.name)+'</span>';
        html += '<span class="cat-id">'+ch.id+'</span>';
        html += '<button class="act-btn" title="编辑" onclick="editCategoryModal(\''+ch.id+'\')"><i class="fas fa-edit"></i></button>';
        html += '</div>';
      });
    }
  });
  html += '</div>';
  c.innerHTML = html;
}

function renderAdminTags() {
  var c = document.getElementById('adminContent');
  var html = '<p style="font-size:13px;color:var(--muted);margin-bottom:8px">所有标签 (点击移除)</p>';
  html += '<div class="tag-editor">';
  if (S.allTags.length === 0) {
    html += '<span style="color:var(--light)">暂无标签，请在文件管理中为文件添加标签</span>';
  }
  S.allTags.forEach(function(tag) {
    html += '<span class="tag-chip">#'+esc(tag)+' <span class="remove" onclick="removeTag(\''+esc(tag)+'\')"><i class="fas fa-times"></i></span></span>';
  });
  html += '</div>';
  html += '<div class="tag-input-row"><input type="text" id="newTagInput" placeholder="输入新标签..." onkeydown="if(event.key===\'Enter\')addTag()"><button class="btn btn-sm btn-primary" onclick="addTag()">添加</button></div>';
  c.innerHTML = html;
}

function renderAdminSettings() {
  var c = document.getElementById('adminContent');
  c.innerHTML = `
    <div style="max-width:400px">
      <h3 style="font-size:14px;margin-bottom:8px">修改管理密码</h3>
      <input type="password" id="newPwd" placeholder="新密码" style="width:100%;padding:8px 12px;border:1px solid var(--line);border-radius:var(--radius);margin-bottom:8px">
      <button class="btn btn-sm btn-primary" onclick="changePwd()">修改密码</button>
      <hr style="margin:24px 0;border:none;border-top:1px solid var(--line)">
      <h3 style="font-size:14px;margin-bottom:8px">数据管理</h3>
      <p style="font-size:12px;color:var(--muted);margin-bottom:8px">导出所有数据（收藏、标签、上传文件等）</p>
      <button class="btn btn-sm btn-ghost" onclick="exportData()"><i class="fas fa-download"></i> 导出数据</button>
      <hr style="margin:24px 0;border:none;border-top:1px solid var(--line)">
      <h3 style="font-size:14px;margin-bottom:8px;color:var(--danger)">重置</h3>
      <p style="font-size:12px;color:var(--muted);margin-bottom:8px">清除所有本地数据（不影响服务器上的文件）</p>
      <button class="btn btn-sm" style="background:#fee;color:var(--danger)" onclick="resetData()"><i class="fas fa-trash"></i> 清除所有数据</button>
    </div>
  `;
}

function changePwd() {
  var pwd = document.getElementById('newPwd').value;
  if (!pwd) { toast('请输入新密码'); return; }
  S.adminPwd = pwd; Save();
  document.getElementById('newPwd').value = '';
  toast('密码已修改');
}

function exportData() {
  var data = { favorites: S.favorites, recent: S.recent, fileTags: S.fileTags, allTags: S.allTags, customCats: S.customCats, fileCats: S.fileCats };
  var blob = new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'});
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url; a.download = 'kb_export.json'; a.click();
  URL.revokeObjectURL(url);
}

function resetData() {
  if (!confirm('确定要清除所有本地数据吗？此操作不可撤销。')) return;
  localStorage.removeItem('kb_favorites');
  localStorage.removeItem('kb_recent');
  localStorage.removeItem('kb_fileTags');
  localStorage.removeItem('kb_allTags');
  localStorage.removeItem('kb_customCats');
  localStorage.removeItem('kb_uploaded');
  localStorage.removeItem('kb_fileCats');
  location.reload();
}

// ===== MODAL FUNCTIONS =====
function addCategoryModal() {
  showModal('新增分类', `
    <input type="text" id="catNameInput" placeholder="分类名称" autofocus>
    <input type="text" id="catIdInput" placeholder="分类ID（英文，如 market-research）">
    <select id="catParentInput">
      <option value="">无（顶级分类）</option>
    </select>
  `, [
    {text:'取消', cls:'btn-ghost', action:'closeModal()'},
    {text:'创建', cls:'btn-primary', action:'addCategory()'}
  ]);
  // populate parent options
  var sel = document.getElementById('catParentInput');
  getTree().forEach(function(cat) {
    if (cat.id === 'other') return;
    sel.innerHTML += '<option value="'+cat.id+'">'+esc(cat.name)+'</option>';
  });
}

function addCategory() {
  var name = document.getElementById('catNameInput').value.trim();
  var id = document.getElementById('catIdInput').value.trim() || 'cat_'+Date.now();
  var parent = document.getElementById('catParentInput').value;
  if (!name) { toast('请输入分类名称'); return; }
  S.customCats.push({id:id, name:name, icon:'fas fa-folder', parentId:parent||null});
  Save(); closeModal(); renderAdminCats(); renderSidebar();
  toast('分类已创建');
}

function editCategoryModal(catId) {
  var cat = getTree().find(function(c){return c.id===catId});
  if (!cat) return;
  // Check if it's a child
  getTree().forEach(function(c) {
    if (c.children) {
      var ch = c.children.find(function(ch){return ch.id===catId});
      if (ch) cat = ch;
    }
  });

  showModal('编辑分类', `
    <input type="text" id="editCatName" value="${esc(cat.name)}">
    <input type="text" id="editCatIcon" value="${cat.icon||'fas fa-folder'}" placeholder="Font Awesome 图标类名">
  `, [
    {text:'取消', cls:'btn-ghost', action:'closeModal()'},
    {text:'保存', cls:'btn-primary', action:'saveCategoryEdit("'+catId+'")'}
  ]);
}

function saveCategoryEdit(catId) {
  var name = document.getElementById('editCatName').value.trim();
  var icon = document.getElementById('editCatIcon').value.trim();
  if (!name) { toast('请输入名称'); return; }
  // Find and update in customCats or TREE
  var custom = S.customCats.find(function(c){return c.id===catId});
  if (custom) {
    custom.name = name; custom.icon = icon;
  } else {
    // It's a built-in category, add as override
    S.customCats.push({id:catId+'_override', name:name, icon:icon, parentId:catId});
    // Actually, let's just add to a overrides map
    // For simplicity, we won't allow editing built-in categories
    toast('内置分类不支持修改，请创建新分类');
    return;
  }
  Save(); closeModal(); renderAdminCats(); renderSidebar();
  toast('分类已更新');
}

function deleteCategory(catId) {
  if (!confirm('确定删除此分类？文件不会被删除，将归入"其他"分类。')) return;
  S.customCats = S.customCats.filter(function(c){return c.id!==catId});
  // Move files to 'other'
  Object.keys(S.fileCats).forEach(function(fn) {
    if (S.fileCats[fn] === catId) delete S.fileCats[fn];
  });
  Save(); renderAdminCats(); renderSidebar();
  toast('分类已删除');
}

function moveFileModal(filename) {
  var opts = '<option value="other">默认分类</option>';
  getTree().forEach(function(cat) {
    if (cat.children) {
      opts += '<optgroup label="'+esc(cat.name)+'">';
      cat.children.forEach(function(ch) { opts += '<option value="'+ch.id+'"'+(getFileCat(filename)===ch.id?' selected':'')+'>'+esc(ch.name)+'</option>'; });
      opts += '</optgroup>';
    } else {
      opts += '<option value="'+cat.id+'"'+(getFileCat(filename)===cat.id?' selected':'')+'>'+esc(cat.name)+'</option>';
    }
  });
  showModal('移动文件', `
    <p style="font-size:13px;margin-bottom:8px">${esc(filename)}</p>
    <select id="moveCatSelect" style="width:100%;padding:8px;border:1px solid var(--line);border-radius:var(--radius)">${opts}</select>
  `, [
    {text:'取消', cls:'btn-ghost', action:'closeModal()'},
    {text:'移动', cls:'btn-primary', action:'moveFile("'+esc(filename)+'")'}
  ]);
}

function moveFile(filename) {
  var cat = document.getElementById('moveCatSelect').value;
  S.fileCats[filename] = cat;
  Save(); closeModal(); renderAdminFiles(); renderSidebar();
  toast('已移动到: '+catName(cat));
}

function editTagsModal(filename) {
  var tags = S.fileTags[filename] || [];
  var tagHtml = tags.map(function(t) {
    return '<span class="tag-chip" id="tag_'+esc(t)+'">#'+esc(t)+' <span class="remove" onclick="removeFileTag(\''+esc(filename)+'\',\''+esc(t)+'\')"><i class="fas fa-times"></i></span></span>';
  }).join('');
  showModal('编辑标签', `
    <p style="font-size:13px;margin-bottom:8px">${esc(filename)}</p>
    <div class="tag-editor" id="fileTagEditor">${tagHtml || '<span style="color:var(--light)">暂无标签</span>'}</div>
    <div class="tag-input-row">
      <input type="text" id="newFileTag" placeholder="输入标签后回车..." onkeydown="if(event.key===\'Enter\')addFileTag('${esc(filename)}')">
      <button class="btn btn-sm btn-primary" onclick="addFileTag('${esc(filename)}')">添加</button>
    </div>
  `, [
    {text:'完成', cls:'btn-primary', action:'closeModal()'}
  ]);
}

function addFileTag(filename) {
  var tag = document.getElementById('newFileTag').value.trim();
  if (!tag) return;
  if (!S.fileTags[filename]) S.fileTags[filename] = [];
  if (S.fileTags[filename].indexOf(tag) >= 0) { toast('标签已存在'); return; }
  S.fileTags[filename].push(tag);
  if (S.allTags.indexOf(tag) < 0) S.allTags.push(tag);
  Save();
  document.getElementById('newFileTag').value = '';
  editTagsModal(filename);
  renderSidebar(); renderMain();
}

function removeFileTag(filename, tag) {
  S.fileTags[filename] = (S.fileTags[filename]||[]).filter(function(t){return t!==tag});
  Save(); editTagsModal(filename); renderSidebar(); renderMain();
}

function deleteFile(filename) {
  if (!confirm('确定删除文件: '+filename+'?')) return;
  S.uploaded = S.uploaded.filter(function(f){return f.name !== filename});
  S.favorites = S.favorites.filter(function(f){return f !== filename});
  S.recent = S.recent.filter(function(f){return f !== filename});
  delete S.fileTags[filename];
  delete S.fileCats[filename];
  Save(); renderAdminFiles(); renderSidebar();
  toast('文件已删除');
}

function addTag() {
  var tag = document.getElementById('newTagInput').value.trim();
  if (!tag) return;
  if (S.allTags.indexOf(tag) >= 0) { toast('标签已存在'); return; }
  S.allTags.push(tag); Save();
  renderAdminTags(); renderSidebar();
  toast('标签已添加');
}

function removeTag(tag) {
  S.allTags = S.allTags.filter(function(t){return t!==tag});
  Object.keys(S.fileTags).forEach(function(fn) {
    S.fileTags[fn] = S.fileTags[fn].filter(function(t){return t!==tag});
  });
  Save(); renderAdminTags(); renderSidebar();
  toast('标签已移除');
}

// ===== MODAL =====
function showModal(title, body, footer) {
  document.getElementById('modalTitle').textContent = title;
  document.getElementById('modalBody').innerHTML = body;
  var f = document.getElementById('modalFooter');
  f.innerHTML = '';
  footer.forEach(function(btn) {
    f.innerHTML += '<button class="btn btn-sm '+btn.cls+'" onclick="'+btn.action+'">'+btn.text+'</button>';
  });
  document.getElementById('modal').classList.add('show');
}

function closeModal() { document.getElementById('modal').classList.remove('show'); }

// ===== KEYBOARD =====
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    closeModal();
    document.getElementById('adminLogin').classList.remove('show');
  }
  if (e.key === '/' && document.activeElement.tagName !== 'INPUT') {
    e.preventDefault();
    document.getElementById('searchInput').focus();
  }
});

// ===== INIT =====
renderSidebar();
renderMain();
"""

# ===== GENERATE HTML =====
html = '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="UTF-8">\n'
html += '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
html += '<title>我的研究知识库</title>\n'
html += '<style>' + CSS + '</style>\n</head>\n<body>\n'
html += HTML
html += '<script>\n'
html += JS.replace('__FILES_JSON__', files_json).replace('__TREE_JSON__', tree_json).replace('__UPLOAD_API__', UPLOAD_API_PLACEHOLDER)
html += '\n</script>\n</body>\n</html>'

(BASE / 'index.html').write_text(html, encoding='utf-8')
print(f'Generated index.html: {len(html)} bytes, {len(files)} files, {len(TREE)} top-level categories')
