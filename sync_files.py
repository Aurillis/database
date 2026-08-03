import shutil, json, re
from pathlib import Path

SRC = Path(r"C:\Users\cbbyy\Downloads\网站文件")
REP = Path(r"C:\Users\cbbyy\WorkBuddy\2026-07-31-10-29-29\report-portal\reports")
BASE = REP.parent

# 文件夹名 -> 网站分类 id（与 gen_kb.py 的 TREE 对应）
CAT_MAP = {
    "哺乳按摩器": "product-lactation",
    "痛经缓解产品": "product-dysmenorrhea",
    "盆底肌修复仪": "product-pelvic",
}

# 1) 清空 reports 现有文件（保留目录本身）
deleted = 0
for f in REP.glob("*"):
    if f.is_file():
        f.unlink()
        deleted += 1
print(f"已清空 reports/ 现有文件: {deleted} 个")

# 2) 复制源文件并生成预置 manifest（带正确 category）
manifest = []
conflicts = []
for folder, cat_id in CAT_MAP.items():
    src_folder = SRC / folder
    if not src_folder.exists():
        print(f"警告: 源文件夹不存在 {folder}")
        continue
    for p in sorted(src_folder.iterdir()):
        if not p.is_file():
            continue
        if p.name.lower() == "desktop.ini":
            continue
        fn = p.name
        target = REP / fn
        if target.exists():
            # 跨文件夹同名: 加分类后缀区分，两份各归其类
            new_fn = f"{p.stem}_{folder}{p.suffix}"
            target = REP / new_fn
            fn = new_fn
            conflicts.append((p.name, folder))
        shutil.copy2(p, target)
        title = re.sub(r'\.[^.]+$', '', fn)
        manifest.append({
            "filename": fn,
            "title": title,
            "size": p.stat().st_size,
            "mtime": int(p.stat().st_mtime),
            "category": cat_id,
        })

manifest.sort(key=lambda x: x["filename"])
(BASE / "manifest.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"已复制 {len(manifest)} 个文件到 reports/")
print(f"同名冲突处理: {conflicts}")
