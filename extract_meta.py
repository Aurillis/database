import os, re, json

REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
output = []

for fname in sorted(os.listdir(REPORTS_DIR)):
    if not fname.lower().endswith(".html"):
        continue
    fpath = os.path.join(REPORTS_DIR, fname)
    fsize = os.path.getsize(fpath)
    mtime = os.path.getmtime(fpath)

    title = ""
    try:
        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(20000)
        m = re.search(r"<title[^>]*>(.*?)</title>", content, re.DOTALL | re.IGNORECASE)
        if m:
            title = m.group(1).strip()
    except:
        pass

    if not title:
        title = os.path.splitext(fname)[0]

    title = re.sub(r"\s+", " ", title).strip()
    if len(title) > 120:
        title = title[:117] + "..."

    output.append({
        "filename": fname,
        "title": title,
        "size": fsize,
        "mtime": mtime
    })

out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports_meta.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"Extracted metadata for {len(output)} reports")
for r in output:
    print(f"  [{r['size']//1024:>6}KB] {r['title'][:70]}")
