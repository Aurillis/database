import json, pathlib

base = pathlib.Path(r'C:\Users\cbbyy\WorkBuddy\2026-07-31-10-29-29\report-portal')
data_json = (base / 'reports_meta.json').read_text(encoding='utf-8')

html_template = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>调研报告中心</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#f5f6f7;--card-bg:#fff;--ink:#1a1a1a;--muted:#6b7280;
  --line:#e5e7eb;--accent:#236b6f;--accent-light:#eef7f5;
  --hover:#f0f7f6;--radius:10px;
}
html{scroll-behavior:smooth}
body{font-family:-apple-system,"Segoe UI","Microsoft YaHei",Roboto,sans-serif;background:var(--bg);color:var(--ink);min-height:100vh;font-size:14px;line-height:1.6}

.header{background:#fff;border-bottom:1px solid var(--line);padding:16px 0;position:sticky;top:0;z-index:100;box-shadow:0 1px 3px rgba(0,0,0,.04)}
.header-inner{max-width:1100px;margin:0 auto;padding:0 24px;display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap}
.logo{display:flex;align-items:center;gap:10px}
.logo-icon{width:36px;height:36px;background:var(--accent);border-radius:8px;display:flex;align-items:center;justify-content:center;color:#fff;font-size:18px;font-weight:800}
.logo-text h1{font-size:18px;font-weight:700}
.logo-text p{font-size:12px;color:var(--muted);margin-top:1px}
.stats{display:flex;gap:20px}
.stat{text-align:center}
.stat b{font-size:22px;font-weight:700;color:var(--accent);display:block}
.stat span{font-size:11px;color:var(--muted)}

.main{max-width:1100px;margin:0 auto;padding:24px}
.toolbar{display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap;align-items:center}
.search-box{flex:1;min-width:240px;position:relative}
.search-box input{width:100%;padding:10px 16px 10px 40px;border:1px solid var(--line);border-radius:8px;font-size:14px;background:#fff;font-family:inherit}
.search-box input:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px rgba(35,107,111,.1)}
.search-box svg{position:absolute;left:13px;top:50%;transform:translateY(-50%);color:var(--muted)}

.toolbar-actions{display:flex;gap:8px}
.btn{padding:10px 16px;border:1px solid var(--line);border-radius:8px;font-size:13px;background:#fff;cursor:pointer;font-family:inherit;color:var(--ink);transition:all .15s}
.btn:hover{border-color:var(--accent);color:var(--accent)}

.folders{display:flex;flex-direction:column;gap:10px}
.folder{background:var(--card-bg);border:1px solid var(--line);border-radius:var(--radius);overflow:hidden}
.folder-header{display:flex;align-items:center;gap:10px;padding:14px 18px;cursor:pointer;user-select:none;transition:background .15s}
.folder-header:hover{background:var(--hover)}
.folder-chevron{width:18px;height:18px;color:var(--muted);transition:transform .2s;flex-shrink:0}
.folder.open .folder-chevron{transform:rotate(90deg)}
.folder-icon{width:22px;height:22px;flex-shrink:0}
.folder-name{font-size:15px;font-weight:600;flex:1}
.folder-count{font-size:12px;color:var(--muted);background:#f3f4f6;padding:2px 8px;border-radius:10px}
.folder-color-bar{width:4px;height:20px;border-radius:2px;flex-shrink:0}

.file-list{display:none;padding:4px 0 8px 0}
.folder.open .file-list{display:block}
.file-item{display:flex;align-items:center;gap:10px;padding:10px 18px 10px 52px;cursor:pointer;transition:background .12s;text-decoration:none;color:inherit;border-left:3px solid transparent}
.file-item:hover{background:var(--hover);border-left-color:var(--accent)}
.file-icon{width:18px;height:18px;flex-shrink:0;color:var(--muted)}
.file-name{flex:1;font-size:13px;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.file-meta{font-size:12px;color:var(--muted);display:flex;gap:12px;flex-shrink:0;white-space:nowrap}
.file-ext{font-size:10px;font-weight:600;padding:2px 6px;border-radius:3px;background:#eef7f5;color:var(--accent);flex-shrink:0}

.empty{text-align:center;padding:60px 20px;color:var(--muted)}
.empty p{font-size:15px;margin-top:12px}

@media(max-width:768px){
  .header-inner{flex-direction:column;align-items:flex-start}
  .stats{width:100%}
  .file-item{padding-left:32px}
  .file-meta{display:none}
}
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
      <div class="stat"><b id="folderCount">0</b><span>分类文件夹</span></div>
    </div>
  </div>
</div>

<div class="main">
  <div class="toolbar">
    <div class="search-box">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
      <input type="text" id="searchInput" placeholder="搜索报告..." autocomplete="off">
    </div>
    <div class="toolbar-actions">
      <button class="btn" id="expandAll">展开全部</button>
      <button class="btn" id="collapseAll">收起全部</button>
    </div>
  </div>
  <div class="folders" id="folders"></div>
  <div class="empty" id="emptyState" style="display:none;">
    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
    <p>没有找到匹配的报告</p>
  </div>
</div>

<script>
var RAW=__DATA__;
var CAT_COLORS={"机会评分看板":"#236b6f","市场调研":"#245f93","技术报告":"#a76508","类目看板":"#534AB7","评论分析":"#a83b35","飞书文档":"#087f79","历史数据":"#62707c","其他":"#888780"};
var CAT_ORDER=["机会评分看板","市场调研","技术报告","类目看板","评论分析","飞书文档","历史数据","其他"];

function categorize(t,f){var s=(t+" "+f).toLowerCase();if(s.indexOf("飞书云文档")>=0||s.indexOf("feishu")>=0)return"飞书文档";if(s.indexOf("机会评分")>=0||s.indexOf("opportunity")>=0)return"机会评分看板";if(s.indexOf("类目看板")>=0||s.indexOf("category")>=0)return"类目看板";if(s.indexOf("评论分析")>=0||s.indexOf("review")>=0||s.indexOf("评价")>=0)return"评论分析";if(s.indexOf("技术")>=0||s.indexOf("disclosure")>=0||s.indexOf("tech")>=0||s.indexOf("工程")>=0)return"技术报告";if(s.indexOf("历史")>=0||s.indexOf("historical")>=0||s.indexOf("销售数据")>=0)return"历史数据";if(s.indexOf("市场")>=0||s.indexOf("调研")>=0||s.indexOf("研究")>=0||s.indexOf("market")>=0)return"市场调研";return"其他"}
function escapeHtml(s){var d=document.createElement("div");d.textContent=s;return d.innerHTML}
function formatDate(ts){var d=new Date(ts*1000);return d.getFullYear()+"-"+String(d.getMonth()+1).padStart(2,"0")+"-"+String(d.getDate()).padStart(2,"0")}
function formatSize(b){if(b<1048576)return Math.round(b/1024)+" KB";return(b/1048576).toFixed(1)+" MB"}
function cleanTitle(t){t=t.replace(/\.html\s*-\s*飞书云文档.*$/i,"");t=t.replace(/&amp;/g,"&");return t}

var REPORTS=[];var FOLDERS={};var searchQuery="";

function processData(){
  REPORTS=RAW.map(function(r){
    var title=cleanTitle(r.title);var cat=categorize(title,r.filename);
    return{filename:r.filename,title:title,size:r.size,mtime:r.mtime,category:cat,date_str:formatDate(r.mtime),size_str:formatSize(r.size)};
  });
  REPORTS.sort(function(a,b){return b.mtime-a.mtime});
  FOLDERS={};CAT_ORDER.forEach(function(c){FOLDERS[c]=[]});
  REPORTS.forEach(function(r){if(!FOLDERS[r.category])FOLDERS[r.category]=[];FOLDERS[r.category].push(r)});
}

function render(){
  var container=document.getElementById("folders");var empty=document.getElementById("emptyState");
  var q=searchQuery.toLowerCase();var hasAny=false;var html="";
  CAT_ORDER.forEach(function(cat){
    var files=FOLDERS[cat]||[];
    var filtered=files.filter(function(r){
      if(!q)return true;
      return r.title.toLowerCase().indexOf(q)>=0||r.filename.toLowerCase().indexOf(q)>=0||r.category.toLowerCase().indexOf(q)>=0;
    });
    if(filtered.length===0)return;hasAny=true;
    var color=CAT_COLORS[cat]||"#888";
    html+='<div class="folder open" data-cat="'+escapeHtml(cat)+'">';
    html+='<div class="folder-header">';
    html+='<svg class="folder-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>';
    html+='<div class="folder-color-bar" style="background:'+color+'"></div>';
    html+='<svg class="folder-icon" viewBox="0 0 24 24" fill="'+color+'" stroke="'+color+'" stroke-width="1.5"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>';
    html+='<span class="folder-name">'+escapeHtml(cat)+'</span>';
    html+='<span class="folder-count">'+filtered.length+'</span>';
    html+='</div><div class="file-list">';
    filtered.forEach(function(r){
      var url="reports/"+encodeURIComponent(r.filename);
      html+='<a class="file-item" href="'+url+'" target="_blank" rel="noopener">';
      html+='<svg class="file-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>';
      html+='<span class="file-name">'+escapeHtml(r.title)+'</span>';
      html+='<span class="file-ext">HTML</span>';
      html+='<span class="file-meta"><span class="file-date">'+r.date_str+'</span><span class="file-size">'+r.size_str+'</span></span>';
      html+='</a>';
    });
    html+='</div></div>';
  });
  if(!hasAny){container.innerHTML="";empty.style.display="block"}else{empty.style.display="none";container.innerHTML=html}
  container.querySelectorAll(".folder-header").forEach(function(h){
    h.addEventListener("click",function(){this.parentElement.classList.toggle("open")});
  });
}

document.getElementById("searchInput").addEventListener("input",function(e){searchQuery=e.target.value;render()});
document.getElementById("expandAll").addEventListener("click",function(){document.querySelectorAll(".folder").forEach(function(f){f.classList.add("open")})});
document.getElementById("collapseAll").addEventListener("click",function(){document.querySelectorAll(".folder").forEach(function(f){f.classList.remove("open")})});

processData();
document.getElementById("totalCount").textContent=REPORTS.length;
var catCount=CAT_ORDER.filter(function(c){return(FOLDERS[c]||[]).length>0}).length;
document.getElementById("folderCount").textContent=catCount;
render();
</script>
</body>
</html>'''

html = html_template.replace('__DATA__', data_json)
(base / 'index.html').write_text(html, encoding='utf-8')
print('Done - new index.html written, size:', len(html), 'bytes')
