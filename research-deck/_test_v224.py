# -*- coding: utf-8 -*-
"""ResearchDeck v2.2.4 闭环集成测试（后端：桩 GitHub 存储 + 桩 LLM）。"""
import json, os, sys, time, urllib.request, urllib.error, subprocess, tempfile, shutil

BASE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="rd224_")
REPORTS = os.path.join(TMP, "reports.json")
PRODUCTS = os.path.join(TMP, "products.json")
OVERVIEWS = os.path.join(TMP, "overviews.json")

# 历史数据：一份只有 id、没有 research_id 的旧报告（Test 10 兼容）
open(REPORTS, "w", encoding="utf-8").write(json.dumps([
    {"id": "r_old_legacy", "topic": "旧报告（无 research_id）", "generatedAt": "2026-01-01",
     "product_id": "p_pelvic", "research_id": None, "research_type": "market",
     "research_mode": "standard", "status": "completed", "data": {"topic": "旧报告（无 research_id）", "sections": {}}}
], ensure_ascii=False))
open(PRODUCTS, "w", encoding="utf-8").write(json.dumps([
    {"product_id": "p_pelvic", "name": "盆底肌训练器", "name_en": "Pelvic Trainer",
     "category": "康复器械", "target_market": ["美国"], "research_goal": "验证产品定义"}
], ensure_ascii=False))
open(OVERVIEWS, "w", encoding="utf-8").write("{}")

# 桩：让 server 用本地临时文件代替 GitHub，用桩 LLM 代替 DeepSeek
patch = r'''
import json, os, sys
sys.path.insert(0, '.')
import server as S

def _get(p, default):
    try:
        with open(p, encoding='utf-8') as f: return json.load(f), 'sha'
    except FileNotFoundError: return default, None
def _save(p, c, s):
    with open(p, 'w', encoding='utf-8') as f: json.dump(c, f, ensure_ascii=False, indent=1)

S.gh_get_json = lambda p: _get(p, {})
S.gh_save_json = lambda p, c, s: _save(p, c, s)
S.gh_get_report_file = lambda: _get(S.REPORTS_PATH, [])
S.gh_save_report_file = lambda c, s: _save(S.REPORTS_PATH, c, s)

# 桩 build_report 维度生成（避免真实 LLM）
S.call_llm_dim = lambda topic, dim, llm: {
    "note": "", "kpis": [], "tables": [], "callouts": ["提示：桩数据"],
    "summary": "%s-%s 桩摘要" % (topic, dim)
}

# 桩 analyze_overview：返回覆盖所有类型的 pending（含 hypothesis / conflict / modify）
def fake_analyze(product, overview, researches, llm):
    rid = (researches[0].get("research_id") or researches[0].get("id")) if researches else "r_test01"
    src = [rid]
    return [
        {"id":"pu1","type":"add","target":"finding","payload":{"dim":"mkt","kind":"FACT","text":"市场规模约 X 亿元（桩）"},"source_research_ids":src,"created_at":"t","status":"pending"},
        {"id":"pu2","type":"add","target":"opportunity","payload":{"title":"机会A","description":"desc","confidence":"Medium","related_dimensions":["mkt"],"status":"待验证"},"source_research_ids":src,"created_at":"t","status":"pending"},
        {"id":"pu3","type":"add","target":"risk","payload":{"title":"风险A","description":"desc","severity":"High","status":"待验证"},"source_research_ids":src,"created_at":"t","status":"pending"},
        {"id":"pu4","type":"add","target":"gap","payload":{"title":"FDA Predicate 尚未完整梳理","description":"why","dimension":"reg","priority":"High","status":"未研究"},"source_research_ids":src,"created_at":"t","status":"pending"},
        {"id":"pu5","type":"add","target":"hypothesis","payload":{"title":"自动推荐刺激强度可能降低使用门槛","content":"基于痛点推测，但仍需验证","dimension":"usr","confidence":"Medium","status":"待验证"},"source_research_ids":src,"created_at":"t","status":"pending"},
        {"id":"pu6","type":"conflict","target":"finding","payload":{"target_id":"__FID__","new_claim":"另一种口径","note":"年份差异","suggest_gap":"规模口径需核实"},"source_research_ids":src,"created_at":"t","status":"pending"},
        {"id":"pu7","type":"modify","target":"finding","payload":{"target_id":"__FID__","new_text":"修订后结论（桩）","reason":"更新"},"source_research_ids":src,"created_at":"t","status":"pending"},
    ]
S.analyze_overview = fake_analyze

from socketserver import TCPServer
TCPServer.allow_reuse_address = True
with TCPServer(("0.0.0.0", 9166), S.Handler) as httpd:
    print("TEST_READY")
    httpd.serve_forever()
'''
open(os.path.join(BASE, "_test_srv.py"), "w", encoding="utf-8").write(patch)

env = dict(os.environ)
env["RD_REPORTS_PATH"] = REPORTS
env["RD_PRODUCTS_PATH"] = PRODUCTS
env["RD_OVERVIEWS_PATH"] = OVERVIEWS
env["RD_TOKEN"] = "test"
env["GITHUB_TOKEN"] = "dummy"
env["OPENAI_API_KEY"] = "dummy"
env["LLM_BASE"] = "https://api.deepseek.com/v1"
env["LLM_MODEL"] = "deepseek-chat"
env["PORT"] = "9166"

proc = subprocess.Popen([sys.executable, os.path.join(BASE, "_test_srv.py")], cwd=os.path.dirname(BASE),
                        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
base = "http://127.0.0.1:9166"
H = {"Content-Type": "application/json", "Authorization": "Bearer test"}

def wait_ready():
    for _ in range(60):
        try:
            urllib.request.urlopen(base + "/api/status?cb=1", timeout=2); return
        except Exception: time.sleep(0.2)
    raise RuntimeError("server not ready")

def req(method, path, body=None):
    r = urllib.request.Request(base + path, data=(json.dumps(body).encode() if body is not None else None),
                               method=method, headers=H)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())

results = []
def check(name, cond, extra=""):
    results.append((name, cond, extra))
    print(("PASS " if cond else "FAIL ") + name + (("  -- " + extra) if extra else ""))

try:
    wait_ready()
    # ---- Test 1：Research 自动归档到 Product ----
    body = {"topic": "盆底肌训练器市场规模", "dims": ["mkt"], "source": "template", "mode": "standard",
            "product_id": "p_pelvic", "research_id": "r_test01", "research_type": "market", "research_mode": "standard",
            "created_at": "2026-09-02T10:00:00"}
    st, out = req("POST", "/api/research", body)
    recs = json.load(open(REPORTS, encoding="utf-8"))
    archived = [r for r in recs if r.get("research_id") == "r_test01"]
    check("Test1 自动归档", st == 200 and len(archived) == 1 and archived[0].get("product_id") == "p_pelvic" and archived[0].get("draft") is True,
          "status=%s recs=%d" % (st, len(recs)))

    # ---- Test 2：Pending Update 生成 ----
    st, out = req("POST", "/api/overview/suggest", {"product_id": "p_pelvic"})
    print("DEBUG suggest status=%s body=%s" % (st, json.dumps(out, ensure_ascii=False)[:600]))
    ov = json.load(open(OVERVIEWS, encoding="utf-8")).get("p_pelvic", {})
    pending = ov.get("pending_updates", [])
    types = {u.get("type") + "/" + u.get("target") for u in pending}
    check("Test2 Pending生成(含hypothesis)",
          out.get("ok") and out.get("added", 0) >= 5 and "add/hypothesis" in types and "conflict/finding" in types,
          "added=%s types=%s" % (out.get("added"), types))

    # ---- Test 5：source_research_ids 来自 research_id ----
    src_ok = all(u.get("source_research_ids") == ["r_test01"] for u in pending)
    check("Test5 source_research_ids=research_id", src_ok, str([u.get("source_research_ids") for u in pending[:2]]))

    # ---- Test 3：Accept finding → 写入 findings + 来源 ----
    st, out = req("POST", "/api/overview/confirm", {"product_id": "p_pelvic", "update_id": "pu1", "action": "accept"})
    ov = json.load(open(OVERVIEWS, encoding="utf-8")).get("p_pelvic", {})
    mkt = ov.get("findings", {}).get("mkt", [])
    fid = mkt[0]["id"] if mkt else None
    check("Test3 Accept finding", st == 200 and out.get("applied") and len(mkt) == 1 and mkt[0].get("source_research_ids") == ["r_test01"],
          "fid=%s src=%s" % (fid, mkt[0].get("source_research_ids") if mkt else None))

    # ---- Test 4：Ignore risk → 不写入 ----
    st, out = req("POST", "/api/overview/confirm", {"product_id": "p_pelvic", "update_id": "pu3", "action": "ignore"})
    ov = json.load(open(OVERVIEWS, encoding="utf-8")).get("p_pelvic", {})
    check("Test4 Ignore risk", st == 200 and out.get("status") == "ignored" and len(ov.get("risks", [])) == 0,
          "risks=%d" % len(ov.get("risks", [])))

    # ---- Test 7：Accept hypothesis → 写入 hypotheses ----
    st, out = req("POST", "/api/overview/confirm", {"product_id": "p_pelvic", "update_id": "pu5", "action": "accept"})
    ov = json.load(open(OVERVIEWS, encoding="utf-8")).get("p_pelvic", {})
    hs = ov.get("hypotheses", [])
    check("Test7 Accept hypothesis", st == 200 and out.get("applied") and len(hs) == 1 and hs[0].get("title")
          and hs[0].get("content") and hs[0].get("dimension") == "usr",
          "hyp=%s" % (hs[0].get("title") if hs else None))

    # 回填冲突/修订的 target_id 为真实 finding id
    ovf = json.load(open(OVERVIEWS, encoding="utf-8"))
    for u in ovf["p_pelvic"]["pending_updates"]:
        if u.get("payload", {}).get("target_id") == "__FID__":
            u["payload"]["target_id"] = fid
    json.dump(ovf, open(OVERVIEWS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # ---- Test 8：Conflict（不覆盖旧结论，保留冲突 + 生成 Gap）----
    st, out = req("POST", "/api/overview/confirm", {"product_id": "p_pelvic", "update_id": "pu6", "action": "accept"})
    ov = json.load(open(OVERVIEWS, encoding="utf-8")).get("p_pelvic", {})
    conflicts = ov.get("findings", {}).get("mkt", [{}])[0].get("conflicts", [])
    gaps_after = ov.get("research_gaps", [])
    check("Test8 Conflict处理", st == 200 and len(conflicts) == 1 and any(g.get("title") == "规模口径需核实" for g in gaps_after),
          "conflicts=%d gaps=%d" % (len(conflicts), len(gaps_after)))

    # ---- Test 8b：Modify（修订旧结论文本 + 合并来源）----
    st, out = req("POST", "/api/overview/confirm", {"product_id": "p_pelvic", "update_id": "pu7", "action": "accept"})
    ov = json.load(open(OVERVIEWS, encoding="utf-8")).get("p_pelvic", {})
    f0 = ov.get("findings", {}).get("mkt", [{}])[0]
    check("Test8b Modify修订", st == 200 and f0.get("text") == "修订后结论（桩）" and "r_test01" in (f0.get("source_research_ids") or []),
          "text=%s" % f0.get("text"))

    # ---- Test 9：删除 Product → 清理 Overview（仅该产品）----
    # 先造另一个产品的总览，验证不被误删
    ovf = json.load(open(OVERVIEWS, encoding="utf-8"))
    ovf["p_other"] = {"product_id": "p_other", "findings": {}, "pending_updates": []}
    json.dump(ovf, open(OVERVIEWS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    st, out = req("DELETE", "/api/overview?id=p_pelvic")
    ovf = json.load(open(OVERVIEWS, encoding="utf-8"))
    check("Test9 删除Overview(只删该产品)", st == 200 and "p_pelvic" not in ovf and "p_other" in ovf,
          "keys=%s" % list(ovf.keys()))

    # ---- Test 10：历史报告（只有 id 无 research_id）来源可解析 ----
    recs = json.load(open(REPORTS, encoding="utf-8"))
    legacy = [r for r in recs if r.get("id") == "r_old_legacy"][0]
    # 模拟前端 openReportById 查找逻辑：r.id===rid || r.research_id===rid
    found = next((r for r in recs if r.get("id") == "r_old_legacy" or r.get("research_id") == "r_old_legacy"), None)
    check("Test10 旧报告兼容(research_id缺失仍能按id定位)", found is not None and found.get("id") == "r_old_legacy",
          "found=%s" % (found.get("id") if found else None))

    passed = sum(1 for _, c, _ in results if c)
    print("\n===== v2.2.4 后端闭环测试结果：%d/%d PASS =====" % (passed, len(results)))
    for n, c, e in results:
        if not c: print("  ✗ " + n + " :: " + e)
finally:
    proc.terminate()
    for f in (REPORTS, PRODUCTS, OVERVIEWS, os.path.join(BASE, "_test_srv.py")):
        try: os.remove(f)
        except: pass
    shutil.rmtree(TMP, ignore_errors=True)
sys.exit(0 if all(c for _, c, _ in results) else 1)
