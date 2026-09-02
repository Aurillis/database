import os, shutil, zipfile, stat

ROOT = r"C:\Users\cbbyy\WorkBuddy\researchdeck_clone\research-deck"
VER = "v2.2.4"
VERDIR = os.path.join(ROOT, "versions", VER)

# 1) Ensure scf_bootstrap is LF (Windows CRLF -> LF)
sb = os.path.join(ROOT, "scf_bootstrap")
raw = open(sb, "rb").read()
lf = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
open(sb, "wb").write(lf)
print("scf_bootstrap CRLF->LF done, bytes:", len(lf))

# 2) Archive v2.2.4 (do not overwrite existing; only create)
os.makedirs(VERDIR, exist_ok=True)
for fn in ["index.html", "server.py", "scf_bootstrap", "_test_v224.py"]:
    src = os.path.join(ROOT, fn)
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(VERDIR, fn))
        print("archived", fn, "->", os.path.join(VERDIR, fn))
# copy DEPLOY.md/VERSIONING.md as version docs too
for fn in ["DEPLOY.md", "VERSIONING.md"]:
    src = os.path.join(ROOT, fn)
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(VERDIR, fn))
        print("archived doc", fn)

# 3) Clean scratch debug files from root (safe via Python)
scratch = [
    "_dbg.py", "_dbg2.py", "_dbg_srv.py", "_dbg_srv2.py",
    "_dbg_out.txt", "_d.txt", "_test_srv.py",
]
for fn in scratch:
    p = os.path.join(ROOT, fn)
    if os.path.exists(p):
        os.remove(p)
        print("removed scratch", fn)
pyc = os.path.join(ROOT, "__pycache__")
if os.path.isdir(pyc):
    shutil.rmtree(pyc)
    print("removed __pycache__")

# 4) Build deploy zip: server.py + scf_bootstrap flat at root, LF + 755
zipname = os.path.join(ROOT, f"researchdeck_deploy_{VER}.zip")
if os.path.exists(zipname):
    os.remove(zipname)
with zipfile.ZipFile(zipname, "w", zipfile.ZIP_DEFLATED) as z:
    # server.py: 0o644
    z.write(os.path.join(ROOT, "server.py"), "server.py",
            compress_type=zipfile.ZIP_DEFLATED)
    # fix external attr for server.py
    info = z.getinfo("server.py")
    info.create_system = 3
    info.external_attr = 0o644 << 16
    # scf_bootstrap: 0o755, LF
    sb_lf = open(os.path.join(ROOT, "scf_bootstrap"), "rb").read()
    zi = zipfile.ZipInfo("scf_bootstrap")
    zi.create_system = 3
    zi.external_attr = 0o755 << 16
    zi.compress_type = zipfile.ZIP_DEFLATED
    z.writestr(zi, sb_lf)
print("built", zipname)

# 5) verify zip perms + line endings
with zipfile.ZipFile(zipname) as z:
    for i in z.infolist():
        mode = (i.external_attr >> 16) & 0o7777
        print(f"  {i.filename}: mode={oct(mode)} compress={i.compress_type}")
    sb_bytes = z.read("scf_bootstrap")
    print("  scf_bootstrap CRLF in zip:", sb_bytes.count(b'\r\n'), "LF-only:", sb_bytes.count(b'\n')-sb_bytes.count(b'\r\n'))
