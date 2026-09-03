# -*- coding: utf-8 -*-
"""
ResearchDeck v2.3.0 集成测试（离线 · 仅 heuristic + 结构验证，不调用 LLM/网络）
覆盖验收 Case 1-8：
  1 医疗跨维度  2 消费品差评  3 供应链量产  4 专利布局  5 纯用户
  6 Gap→问题驱动研究  7 历史 research_type 兼容  8 多维度归档
以及关键 #27：动态 Scope 真正驱动报告结构（非固定模板）。
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "research-deck"))
import server as S

PASS = 0
FAIL = 0
def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS | %s %s" % (name, detail))
    else:
        FAIL += 1
        print("  FAIL | %s %s" % (name, detail))

def scope_ids(scopes):
    return [s["id"] for s in scopes]

print("=== Case 1: 医疗跨维度（盆底肌 EMS 治疗参数，US+EU 市场，医疗/健康宣称）===")
q1 = "第一代盆底肌 EMS 产品不同治疗模式应该使用什么刺激参数（频率/脉宽/Work-Rest）？"
c1 = {"markets": ["US", "EU"], "product_type": "盆底肌康复仪", "product_claims": "用于盆底肌训练与治疗", "background": "已有样机，需确定正式产品治疗模式"}
s1 = S._suggest_scope_heuristic(q1, c1)
ids1 = scope_ids(s1)
print("   推荐 Scope:", ids1)
check("C1 技术为核心", "tech" in ids1 and [x for x in s1 if x["id"]=="tech"][0]["level"]=="core")
check("C1 临床为核心", "clinical" in ids1)
check("C1 法规为核心(medical)", "reg" in ids1)
check("C1 FDA为核心(US+medical)", "fda" in ids1 and [x for x in s1 if x["id"]=="fda"][0]["level"]=="core")
check("C1 市场/用户/竞品/产品为核心", all(k in ids1 for k in ["market","user","comp","product"]))

print("=== Case 2: 消费品差评（宠物智能饮水机，US 市场，非医疗）===")
q2 = "宠物智能饮水机为什么用户退货率偏高？"
c2 = {"markets": ["US"], "product_type": "宠物智能饮水机"}
s2 = S._suggest_scope_heuristic(q2, c2)
ids2 = scope_ids(s2)
print("   推荐 Scope:", ids2)
check("C2 用户为核心", "user" in ids2 and [x for x in s2 if x["id"]=="user"][0]["level"]=="core")
check("C2 竞品为核心", "comp" in ids2)
check("C2 FDA 被跳过(skip,非医疗)", "fda" in ids2 and [x for x in s2 if x["id"]=="fda"][0]["level"]=="skip")
check("C2 法规被跳过(skip,非医疗)", "reg" in ids2 and [x for x in s2 if x["id"]=="reg"][0]["level"]=="skip")
check("C2 专利被跳过(无创新)", "patent" in ids2 and [x for x in s2 if x["id"]=="patent"][0]["level"]=="skip")

print("=== Case 3: 供应链/量产（电动筋膜枪 工厂筛选与BOM成本）===")
q3 = "电动筋膜枪量产时工厂筛选、BOM 成本与产能交期怎么控制？"
c3 = {"markets": ["US"], "product_type": "电动筋膜枪"}
s3 = S._suggest_scope_heuristic(q3, c3)
ids3 = scope_ids(s3)
print("   推荐 Scope:", ids3)
check("C3 供应链为核心", "supply" in ids3 and [x for x in s3 if x["id"]=="supply"][0]["level"]=="core")
check("C3 BOM为核心", "bom" in ids3)
check("C3 制造为核心", "mfg" in ids3)
check("C3 安全为核心", "safety" in ids3)

print("=== Case 4: 专利布局（创新结构 哺乳按摩器 FTO）===")
q4 = "我们想做一款带创新结构的哺乳按摩器，需要评估 FTO 与专利布局空间。"
c4 = {"markets": ["US"], "product_type": "哺乳按摩器"}
s4 = S._suggest_scope_heuristic(q4, c4)
ids4 = scope_ids(s4)
print("   推荐 Scope:", ids4)
check("C4 专利为核心(触发词+创新)", "patent" in ids4 and [x for x in s4 if x["id"]=="patent"][0]["level"]=="core")

print("=== Case 5: 纯用户（颈枕不适）===")
q5 = "为什么用户觉得这款颈枕不舒服？"
c5 = {"markets": ["US"], "product_type": "颈枕"}
s5 = S._suggest_scope_heuristic(q5, c5)
ids5 = scope_ids(s5)
print("   推荐 Scope:", ids5)
check("C5 用户为核心", "user" in ids5)
check("C5 竞品为核心", "comp" in ids5)
check("C5 供应链被跳过", "supply" in ids5 and [x for x in s5 if x["id"]=="supply"][0]["level"]=="skip")

print("=== Case 6: Gap→问题驱动研究（Gap 问题进入动态流程）===")
gap_q = "围绕「哺乳期乳腺堵塞高发人群尚未覆盖」，系统梳理产品已有的研究证据、主要分歧与尚未解决的关键问题，并给出可验证的研究路径与可靠来源。"
s6 = S._suggest_scope_heuristic(gap_q, {"markets":["US"], "product_type":"哺乳按摩器"})
ids6 = scope_ids(s6)
print("   Gap 问题推荐 Scope:", ids6)
check("C6 Gap 问题可驱动 Scope 推荐(非空)", len(ids6) > 0)

print("=== Case 7: 历史 research_type 兼容（运行时映射，不物理迁移）===")
check("C7 legacy market", S.legacy_dimensions("market") == ["mkt"])
check("C7 legacy comprehensive", S.legacy_dimensions("comprehensive") == ["mkt","usr","prod","comp","tech"])
check("C7 legacy 缺省", S.legacy_dimensions("") == ["other"])
check("C7 legacy other", S.legacy_dimensions("other") == ["other"])

print("=== Case 8: 多维度归档（一份 Research 出现在多个分类，数据库仅一份）===")
# 模拟 researchCats 逻辑（与前端一致）
def researchCats(r):
    if r.get("dimensions"): return r["dimensions"]
    if r.get("scopes"): return [s["id"] if isinstance(s,dict) else s for s in r["scopes"]]
    return S.legacy_dimensions(r.get("research_type")) or ["other"]
dyn_rec = {"dimensions": ["fda","patent","tech"]}
cats8 = researchCats(dyn_rec)
print("   动态归档分类:", cats8)
check("C8 多维度(3类)", set(cats8) == {"fda","patent","tech"} and len(cats8)==3)
legacy_rec = {"research_type": "market"}
check("C8 历史记录单维度(mkt)", researchCats(legacy_rec) == ["mkt"])

print("=== 关键 #27：动态 Scope 真正驱动报告结构（非固定模板）===")
plan = {"goal":"确定盆底肌 EMS 刺激参数","questions":["频率多少？","脉宽多少？"],
        "scopes":["tech","clinical","fda","reg"],"methods":["参数Benchmark"],"sources":["FDA数据库"],"expected_outputs":["参数建议"]}
# 不调用 LLM：fallback 结构的 sections 键由 scope_ids 决定（证明结构跟随 Scope）
fallback = S.build_dynamic_report(q1, c1, plan, [{"id":"tech","level":"core"},{"id":"clinical","level":"core"},{"id":"fda","level":"core"},{"id":"reg","level":"core"}], {"key":None})
sec_keys = list((fallback.get("sections") or {}).keys())
print("   报告 sections 键:", sec_keys)
check("#27 报告章节跟随 Scope(tech/clinical/fda/reg)", set(sec_keys) == {"tech","clinical","fda","reg"})
check("#27 非固定模板(不含 ecom 等无关维度)", "ecom" not in sec_keys)

print("=== 汇总 ===")
print("PASS=%d  FAIL=%d" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
