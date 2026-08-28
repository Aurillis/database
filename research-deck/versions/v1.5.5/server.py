#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调研台 ResearchDeck · A2 本地后端
- 纯标准库，零依赖，可直接 `python3 server.py` 运行
- 提供：
    GET  /            静态前端 index.html
    GET  /api/status  返回当前模式（demo / live）与可用维度
    POST /api/research 接收 {topic, dims[]}，返回结构化报告 JSON
- AI 接入（可选）：设置环境变量后自动切换为 live 模式
    OPENAI_API_KEY  或  ANTHROPIC_API_KEY
    OPENAI_BASE_URL（默认 https://api.openai.com/v1，可指向任意 OpenAI 兼容端点）
    OPENAI_MODEL    （默认 gpt-4o-mini）
- 未设置 key 时自动进入 demo 模式：用通用结构骨架生成（不含任何固定产品数据），
  所有数字标注「待核验/示意」，符合数据诚实性原则。
"""

import http.server
import socketserver
import json
import os
import urllib.request
import urllib.error
import datetime
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", "8765"))

# 北京时间（UTC+8）：所有报告/任务时间统一用北京时间，不随服务器时区漂移
BEIJING_TZ = datetime.timezone(datetime.timedelta(hours=8))

def now_beijing():
    """返回北京时间的字符串（YYYY-MM-DD HH:MM）。"""
    return datetime.datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M")

LLM_KEY = os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
LLM_BASE = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
LLM_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
MODE = "live" if LLM_KEY else "demo"

# ---------------------------------------------------------------------------
# 维度元信息（与前端一致，单一事实源）
# ---------------------------------------------------------------------------
DIMS = {
    "mkt":  {"title": "市场调研", "icon": "📊", "badge": "SellerSprite 地面真值"},
    "usr":  {"title": "用户研究", "icon": "👥", "badge": "Reddit / Facebook 社群"},
    "prod": {"title": "产品调研", "icon": "🔬", "badge": "型号拆解 / 参数盘点"},
    "comp": {"title": "竞品分析", "icon": "⚔️", "badge": "定位 / 定价 / 功能"},
    "tech": {"title": "技术研究", "icon": "⚙️", "badge": "方案对标 / 工程能力"},
    "reg":  {"title": "合规审计", "icon": "🛡️", "badge": "FDA 510k / NMPA 交叉验证"},
    "amz_us": {"title": "亚马逊美国·机会评分看板", "icon": "🇺🇸",
               "badge": "看板结构 · 卖家精灵 MCP", "template": True},
    "amz_eu": {"title": "亚马逊欧洲·市场看板", "icon": "🇪🇺",
               "badge": "看板结构 · 卖家精灵 MCP", "template": True},
}

# ---------------------------------------------------------------------------
# 看板结构模板（Amazon US / EU 市场看板方法论）
# 这两条维度的输出结构被固定，不随主题漂移。见 AMZ_US_TEMPLATE / AMZ_EU_TEMPLATE
# ---------------------------------------------------------------------------
# 亚马逊站看板结构模板（方法论参考框架）
# 这两条维度按「亚马逊机会评分看板」方法论提炼的通用结构产出，
# 对任意主题生效：LLM 按此结构实时生成，数据由卖家精灵 MCP 抓取，不写死任何品类。
# ---------------------------------------------------------------------------
AMZ_US_TEMPLATE = """【亚马逊美国站 · 机会评分看板】针对用户给定主题的类目，按以下标准看板结构产出（结构与「Bladder Control Devices 机会评分看板」方法论一致）：
必须严格按以下模块结构产出，不得增删模块、不得改变表头顺序：

· KPI（8 个，顺序固定）：机会评分 / 风险评分 / 候选ASIN→核心ASIN / 样本月销量(件) / 样本月销售额 / 加权成交价 / Top类型 / Top品牌

· 表1「核心指标」表头：核心指标 | 数值 | 说明
  行（固定）：候选→核心产品(ASIN数) / 样本月销量·销售额 / 加权成交价 / Top 类型 / Top 品牌 / Top5 品牌销售额占比(含销量占比) / 平均评分 / 新品(数量·均销额) / Amazon 自营参与

· 表2「产品类型销售额结构」表头：产品类型 | ASIN数 | 销量 | 销售额 | 均价 | 评分
  行（按销售额降序，覆盖该类目全部产品类型，由 MCP 数据决定；每行填真实类型名）

· 表3「品牌销售额 Top10」表头：品牌 | ASIN数 | 销量 | 销售额 | 均价
  行（按销售额降序，固定 10 行，由 MCP 数据决定）

· 表4「头部品牌产品路线」表头：品牌 | 主打类型 | 价格带 | 打法
  行（覆盖该类目头部品牌策略，由 MCP 数据决定）

· 表5「关键词市场需求」表头：关键词 | 分类 | 月搜索 | 月购买 | 购买率 | 竞价 | 供需比 | 垄断点击率
  行（覆盖五类）：核心需求词 / 细分品类词 / 场景/功效词 / 人群词 / 品牌·产品词

· 表6「关键词趋势与 PPC」表头：关键词 | 分类 | 最新搜索 | 同比趋势 | PPC竞价
  行：核心词历史搜索趋势（标注增长/下降 %）

· 表7「价格带销售额」表头：价格带 | ASIN数 | 销量 | 销售额
  行（固定五档）：<$30 / $30-60 / $60-120 / $120-200 / $200+

· 表8「目标场景 / 核心痛点」表头：目标场景 | 覆盖产品类型 | 核心痛点 | ASIN数 | 销量 | 销售额
  行（覆盖该类目主要使用场景与痛点，由 MCP 数据决定）

· 表9「功能/属性热度」表头：功能/属性 | 涉及ASIN数 | 说明
  行（覆盖该类目关键功能/属性，由 MCP 数据决定）

· 表10「十维机会评分」表头：十维机会评分 | 分数 | 要点
  行（固定十个维度，顺序不可变）：市场容量 / 增长想象空间 / 竞争集中度 / 价格承接 / 评分壁垒 / 产品差异化 / 进入门槛 / 内容教育价值 / 复购组合 / 综合机会

· callouts（固定五条线索）：①关键词市场解读 ②价格与销售额机会矩阵 ③产品定义启发（优先/可测/谨慎）④最终建议与验证清单 ⑤机会点 / 主要风险 / 进入建议。结尾附加数据诚实声明（区分卖家精灵实测字段 vs 语义分类字段）"""

AMZ_EU_TEMPLATE = """【亚马逊欧洲站 EU5 · 市场看板】针对用户给定主题的类目，按以下标准看板结构产出（结构按亚马逊 EU5 市场看板方法论）：
必须严格按以下模块结构产出，不得增删模块、不得改变表头顺序：

· KPI（4 个，顺序固定）：机会评分 / 风险评分 / 五国月销量(件) / 总销售额

· 表1「核心指标」表头：核心指标 | 数值 | 说明
  行（固定）：五国月销量·销售额 / 平均售价 / ASIN数(去重) / Top5 品牌(销量·销售额占比) / 最大国家 / 最大细分

· 表2「五国概览」表头：五国概览 | ASIN | 销量占比 | 销售额占比 | 均价
  行（固定五国，按销量降序）：德国 / 英国 / 法国 / 西班牙 / 意大利

· 表3「产品类型」表头：产品类型 | 销量 | 占比 | ASIN数 | 销售额
  行（覆盖该类目全部产品类型，由 MCP 数据决定；每行填真实类型名）

· 表4「价格带」表头：价格带 | ASIN | 销量占比 | 销售额占比 | 均价
  行（固定五档）：0–20 / 20–40 / 40–70 / 70–120 / 120+

· callouts（固定四条线索）：①欧洲整体市场(全渠道)规模与 CAGR ②关键词热度与 PPC（各国核心词）③MDR/医疗宣称合规风险 ④结论（进入 / 观望 / 放弃）"""

# 各维度提示词（与「维度模板」一致，{topic} 占位）
DIM_PROMPTS = {
    "mkt": "你是市场调研分析师。针对「{topic}」，用真实数据（若有 SellerSprite/卖家精灵等导出数据优先标注来源）产出：①品类规模与增长 ②集中度 CR5/CR10、头部品牌份额 ③价格带分布 ④月度/年度趋势（标注数据缺口）⑤供需结构。每条数字标注来源；拿不到写「未获取」。",
    "usr": "你是用户研究分析师。针对「{topic}」目标人群，在 Reddit、X、Facebook、Quora 检索真实讨论，产出：①核心痛点（高频）②使用场景 ③未被满足的需求 ④可拓展人群/场景。每条附社区名/帖子标题或 URL，标注信号强度（强/中/弱）。",
    "prod": "你是产品拆解分析师。针对「{topic}」覆盖的主要型号/SKU，产出硬件/功能参数横向对比：形态、核心器件（传感/加热/电机）、续航、材质、防水、软件。基于真实型号参数；无法查证的标「待核验」。",
    "comp": "你是竞品分析师。针对「{topic}」头部与典型玩家，产出：定位、定价、功能矩阵、优势、明显弱点（引评论/评测）、给我们的「可乘之机」。标注信息来源。",
    "tech": "你是技术对标分析师。针对「{topic}」涉及的关键技术路线（如 Peltier TEC、生物反馈 EMG、电刺激 EMS/TENS 等），产出各路线代表方案、适用场景、迁移难度、对本品的壁垒意义。引来源。",
    "reg": "你是合规审计分析师。针对「{topic}」所属监管类目（FDA 510k / NMPA / CE），检索数据库与文献，产出：监管路径判定（治疗模式 vs 美容/消费模式）、所需资质/备案、红线措辞、对我们的启示。强调「禁止无依据宣称医疗功效」。",
    "amz_us": (
        "你是亚马逊美国站市场分析师。调研主题：{topic}\n\n"
        "【数据源铁律】凡涉及亚马逊类目容量、品牌份额、价格带、销量、销售额、评论、BSR、关键词 PPC，"
        "一律调用卖家精灵 MCP（SellerSprite）抓取，并标注「来源：卖家精灵」；"
        "MCP 未覆盖到的写「未获取」，禁止用平台宣传口径或主观估算填补。\n\n"
        + AMZ_US_TEMPLATE +
        "\n\n【口径】机会评分/风险评分均 0–100 取整数；加权成交价 = 销售额 ÷ 销量；"
        "样本必须说明「候选 ASIN → 核心产品 ASIN」的过滤逻辑与去重方式。"
    ),
    "amz_eu": (
        "你是亚马逊欧洲站（EU5：德/英/法/西/意）市场分析师。调研主题：{topic}\n\n"
        "【数据源铁律】凡涉及亚马逊类目容量、品牌份额、价格带、销量、销售额、评论、BSR、关键词 PPC，"
        "一律调用卖家精灵 MCP（SellerSprite）抓取，并标注「来源：卖家精灵」；"
        "MCP 未覆盖到的写「未获取」，禁止用平台宣传口径或主观估算填补。\n\n"
        + AMZ_EU_TEMPLATE +
        "\n\n【口径】机会评分/风险评分均 0–100 取整数；销售额 = price × totalUnits（若 totalAmount 未返回需注明）；"
        "样本必须说明「候选 ASIN → 保留 → 去重」的过滤逻辑。"
    ),
}

# ---------------------------------------------------------------------------
# 实时生成模式：调用 OpenAI 兼容端点（DeepSeek / OpenAI / 任意兼容）
# ---------------------------------------------------------------------------
NO_MCP_CAVEAT = (
    "\n注意：本次未连接卖家精灵 MCP，无法实时抓取亚马逊数据。"
    "请基于你的训练知识给出方向性估算，并明确标注「LLM 估算·待 SellerSprite 核验」；"
    "禁止编造精确到个位的销量/销售额，可给区间与排序，精确数字写「未获取」。"
    "固定模板结构保持不变。"
)

def _extract_json(content):
    """从 LLM 返回中稳健解析 JSON：兼容纯 JSON / ```json 代码块 / 前后缀噪声。"""
    if not isinstance(content, str):
        content = str(content)
    s = content.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s[3:]
        if s.endswith("```"):
            s = s[:-3]
        s = s.strip()
    start, end = s.find("{"), s.rfind("}")
    if start != -1 and end != -1 and end > start:
        s = s[start:end + 1]
    return json.loads(s)


def call_llm_dim(topic, dim_key, llm):
    """调用 LLM 生成单个维度的结构化结果，返回 dict（见 schema）。llm={key,base,model}"""
    prompt = DIM_PROMPTS[dim_key].format(topic=topic)
    if dim_key in ("amz_us", "amz_eu"):
        prompt += NO_MCP_CAVEAT
    fixed_template_hint = ""
    if dim_key in ("amz_us", "amz_eu"):
        fixed_template_hint = (
            "\n\n【结构铁律】本维度为「固定模板」维度，输出必须严格遵循上方模板的"
            "模块顺序与表头，不得增删模块、不得改变表头顺序。即使拿不到实时数据，"
            "也必须保留模板骨架，缺失字段填「未获取」。"
        )
    sysmsg = (
        "你是「调研台 ResearchDeck」的研究员。严格按照用户指令产出研究内容，"
        "数据诚实：能用真实数据源就标注来源，拿不到的明确写「未获取」。\n"
        "你必须只输出一个 JSON 对象（不要任何解释文字、不要 markdown 代码块），结构如下：\n"
        "{\n"
        '  "note": "本维度的研究方法论说明（一句话）",\n'
        '  "kpis": [{"v":"指标值","l":"指标含义"}]  // 0-4 个，可选\n'
        '  "tables": [{"head":["列1","列2","列3"], "rows":[["单元格","单元格","单元格"]]}],  // 1-3 张\n'
        '  "callouts": ["关键事实核查或提示（一句话）"],  // 可选\n'
        '  "summary": "本维度一句话结论"\n'
        "}\n"
        "单元格文本中可用 (t)高 (w)中 (r)风险 (b)信息 这类简短标记表示状态，但尽量用纯文本。"
        + fixed_template_hint
    )
    payload = {
        "model": llm["model"],
        "messages": [
            {"role": "system", "content": sysmsg},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
    }
    # 仅对明确支持 json_object 模式的端点（OpenAI 官方）开启；DeepSeek 等靠 _extract_json 兜底
    if llm.get("base", "").rstrip("/").endswith("openai.com/v1") or llm.get("supports_json_mode"):
        payload["response_format"] = {"type": "json_object"}
    req = urllib.request.Request(
        llm["base"].rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + llm["key"],
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        j = json.loads(resp.read().decode("utf-8"))
    content = j["choices"][0]["message"]["content"]
    try:
        return _extract_json(content)
    except Exception:
        return {
            "note": "该维度模型返回无法解析为 JSON，已降级为结构骨架。",
            "kpis": [],
            "tables": [],
            "callouts": ["⚠️ 模型返回格式异常，建议重试或检查模型是否支持结构化输出。"],
            "summary": "生成失败（JSON 解析）",
        }


# ---------------------------------------------------------------------------
# Demo 模式：内置真实数据 + 通用骨架
# ---------------------------------------------------------------------------
def demo_generic(topic):
    """通用骨架：任何主题都返回结构完整、但明确标注「待核验/示意」的报告。"""
    summary = (
        "「" + str(topic) + "」的自动调研报告（<b>demo 模式·示意数据</b>）。当前未接入在线大模型，"
        "以下内容为平台输出<b>结构骨架</b>，所有量化数字标注「待核验」。接入 LLM API 后将由研究 agent 实时生成并填入真实数据。"
    )
    sections = {}
    for k in DIMS:
        sections[k] = {
            "note": "demo 模式：以下为结构示意，接入在线模型后由对应维度研究员实时生成。",
            "kpis": [],
            "tables": [{
                "head": ["维度", "主流方案", "缺口 / 机会"],
                "rows": [
                    ["（示例）形态", "待核验", "待核验"],
                    ["（示例）核心器件", "待核验", "待核验"],
                    ["（示例）渠道/价格", "待核验", "待核验"],
                ],
            }],
            "callouts": ["⚠️ demo 模式：此模块为结构示意。配置 OPENAI_API_KEY 后，本模块将由 AI 研究员基于真实数据源生成。"],
            "summary": "（待接入模型后生成）",
        }
    return {"summary": summary, "kpis": [], "sections": sections}


def demo_amz_us(topic=""):
    """亚马逊美国站·机会评分看板（结构骨架版）。
    模板模式：按「机会评分看板」方法论输出完整结构骨架，数据标注「待实时生成」，
    不写死任何品类——大模型模式下由 LLM 按同一结构对任意主题实时生成。"""
    t = (topic or "该品类").strip() or "该品类"
    return {
        "note": "【看板结构·示意】本维度按「亚马逊美国站机会评分看板」方法论产出（KPI → 核心指标 → 产品类型结构 → 品牌Top10 → 头部品牌路线 → 关键词市场 → 关键词趋势PPC → 价格带 → 目标场景/痛点 → 功能热度 → 十维机会评分 → callouts）。当前为结构骨架（数据待实时生成）；选择「大模型实时生成」后，将由 LLM 对「{}」按此结构产出真实数据。数据源：卖家精灵 MCP（SellerSprite）。".format(t),
        "kpis": [
            {"v": "—", "l": "机会评分"},
            {"v": "—", "l": "风险评分"},
            {"v": "—", "l": "候选→核心 ASIN"},
            {"v": "—", "l": "样本月销量(件)"},
            {"v": "—", "l": "样本月销售额"},
            {"v": "—", "l": "加权成交价"},
            {"v": "—", "l": "Top 类型"},
            {"v": "—", "l": "Top 品牌"},
        ],
        "tables": [
            {"head": ["核心指标", "数值", "说明"], "rows": [
                ["候选→核心产品", "待生成", "MCP 语义筛选"],
                ["样本月销量 / 销售额", "待生成", "卖家精灵 抓取月"],
                ["加权成交价", "待生成", "销售额 / 销量"],
                ["Top 类型 / Top 品牌", "待生成", "销售额维度"],
                ["Top5 品牌销售额占比", "待生成", "含销量占比"],
                ["平均评分 / 新品均销额", "待生成", "核心样本"],
                ["Amazon 自营", "待生成", "平台参与度"],
            ]},
            {"head": ["产品类型", "ASIN数", "销量", "销售额", "均价", "评分"], "rows": [
                ["（类型1，MCP 决定）", "—", "—", "—", "—", "—"],
                ["（类型2，MCP 决定）", "—", "—", "—", "—", "—"],
                ["（类型3，MCP 决定）", "—", "—", "—", "—", "—"],
            ]},
            {"head": ["品牌销售额 Top10", "ASIN数", "销量", "销售额", "均价"], "rows": [
                ["（品牌1）", "—", "—", "—", "—"],
                ["（品牌2）", "—", "—", "—", "—"],
            ]},
            {"head": ["头部品牌产品路线", "主打类型", "价格带", "打法"], "rows": [
                ["（品牌）", "待生成", "待生成", "待生成"],
            ]},
            {"head": ["关键词", "分类", "月搜索", "月购买", "购买率", "竞价", "供需比", "垄断点击率"], "rows": [
                ["（核心词）", "核心需求词", "—", "—", "—", "—", "—", "—"],
            ]},
            {"head": ["关键词趋势与 PPC", "分类", "最新搜索", "同比趋势", "PPC竞价"], "rows": [
                ["（核心词）", "—", "—", "—", "—"],
            ]},
            {"head": ["价格带", "ASIN数", "销量", "销售额"], "rows": [
                ["<$30", "—", "—", "—"],
                ["$30-60", "—", "—", "—"],
                ["$60-120", "—", "—", "—"],
                ["$120-200", "—", "—", "—"],
                ["$200+", "—", "—", "—"],
            ]},
            {"head": ["目标场景", "覆盖产品类型", "核心痛点", "ASIN数", "销量", "销售额"], "rows": [
                ["（场景1）", "待生成", "待生成", "—", "—", "—"],
            ]},
            {"head": ["功能/属性热度", "涉及ASIN数", "说明"], "rows": [
                ["（功能1）", "—", "待生成"],
            ]},
            {"head": ["十维机会评分", "分数", "要点"], "rows": [
                ["市场容量", "—", "待生成"],
                ["增长想象空间", "—", "待生成"],
                ["竞争集中度", "—", "待生成"],
                ["价格承接", "—", "待生成"],
                ["评分壁垒", "—", "待生成"],
                ["产品差异化", "—", "待生成"],
                ["进入门槛", "—", "待生成"],
                ["内容教育价值", "—", "待生成"],
                ["复购/组合", "—", "待生成"],
                ["综合机会", "—", "待生成"],
            ]},
        ],
        "callouts": [
            "本维度为「机会评分看板」结构骨架（数据待生成）。选择「大模型实时生成」数据源后，由 LLM 对「{}」按此结构实时产出真实数据。".format(t),
            "看板方法论：市场容量/增长/集中度/价格承接/评分壁垒/差异化/门槛/教育价值/复购组合/综合机会 十维评分 + 关键词市场 + 场景痛点 + 功能热度交叉验证。",
            "数据诚实：LLM 生成时，销量/销售额/价格/评分/评论/BSR 来自卖家精灵 MCP；产品类型与功能为基于标题的语义分类。",
        ],
        "summary": "「{}」亚马逊美国站机会评分看板：结构骨架已就绪，选择大模型实时生成获取真实数据与评分。".format(t),
    }


def demo_amz_eu(topic=""):
    """亚马逊欧洲站（EU5）·市场看板（结构骨架版）。
    模板模式：按「欧洲市场看板」方法论输出完整结构骨架，数据标注「待实时生成」，
    不写死任何品类——大模型模式下由 LLM 按同一结构对任意主题实时生成。"""
    t = (topic or "该品类").strip() or "该品类"
    return {
        "note": "【看板结构·示意】本维度按「亚马逊欧洲站 EU5 市场看板」方法论产出（KPI → 核心指标 → 五国概览 → 产品类型 → 价格带 → 市场CAGR/关键词PPC/MDR合规/结论）。当前为结构骨架（数据待实时生成）；选择「大模型实时生成」后，将由 LLM 对「{}」按此结构产出真实数据。数据源：卖家精灵 MCP（SellerSprite）Amazon EU5。".format(t),
        "kpis": [
            {"v": "—", "l": "机会评分"},
            {"v": "—", "l": "风险评分"},
            {"v": "—", "l": "五国月销量(件)"},
            {"v": "—", "l": "总销售额"},
        ],
        "tables": [
            {"head": ["核心指标", "数值", "说明"], "rows": [
                ["五国月销量 / 销售额", "待生成", "price×totalUnits"],
                ["平均售价", "待生成", "抓取价算术平均"],
                ["ASIN 数(去重)", "待生成", "五国"],
                ["Top5 品牌", "待生成", "头部集中度"],
                ["最大国家 / 最大细分", "待生成", "销量主战场"],
            ]},
            {"head": ["五国概览", "ASIN", "销量占比", "销售额占比", "均价"], "rows": [
                ["德国", "—", "—", "—", "—"],
                ["英国", "—", "—", "—", "—"],
                ["法国", "—", "—", "—", "—"],
                ["西班牙", "—", "—", "—", "—"],
                ["意大利", "—", "—", "—", "—"],
            ]},
            {"head": ["产品类型", "销量", "占比", "ASIN数", "销售额"], "rows": [
                ["（类型1，MCP 决定）", "—", "—", "—", "—"],
                ["（类型2，MCP 决定）", "—", "—", "—", "—"],
            ]},
            {"head": ["价格带", "ASIN", "销量占比", "销售额占比", "均价"], "rows": [
                ["0–20", "—", "—", "—", "—"],
                ["20–40", "—", "—", "—", "—"],
                ["40–70", "—", "—", "—", "—"],
                ["70–120", "—", "—", "—", "—"],
                ["120+", "—", "—", "—", "—"],
            ]},
        ],
        "callouts": [
            "本维度为「欧洲市场看板」结构骨架（数据待生成）。选择「大模型实时生成」数据源后，由 LLM 对「{}」按此结构实时产出真实数据。".format(t),
            "看板方法论：五国概览（德/英/法/西/意）+ 产品类型 + 价格带 + 市场CAGR + 关键词PPC + MDR 合规交叉验证。",
            "风险中心：尿失禁/治疗/医疗器械/TENS 等表述需按各国 MDR 与平台政策分别核查（风险评分偏高时优先）。",
            "数据诚实：LLM 生成时，销量/销售额/价格/评分来自卖家精灵 MCP；产品类型与功能为基于标题的语义分类。",
        ],
        "summary": "「{}」亚马逊欧洲站 EU5 市场看板：结构骨架已就绪，选择大模型实时生成获取真实数据与评分。".format(t),
    }


# ---------------------------------------------------------------------------
# 报告组装
# ---------------------------------------------------------------------------
def build_report(topic, dims, source="template", llm=None):
    topic = (topic or "").strip() or "未命名调研主题"
    dims = [d for d in dims if d in DIMS]
    if not dims:
        dims = list(DIMS.keys())

    # —— 实时生成（大模型）模式 ——
    if source == "llm" and llm and llm.get("key"):
        # v1.5.2：并行调用各维度（多维度同时请求 DeepSeek），总耗时从 串行 n×20s 降到 ~20-40s，
        # 避免多维度在 SCF 超时（30s）内跑不完导致 Failed to fetch。
        import concurrent.futures
        sections_out = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, len(dims))) as ex:
            fut = {ex.submit(call_llm_dim, topic, k, llm): k for k in dims}
            for f in concurrent.futures.as_completed(fut):
                k = fut[f]
                try:
                    res = f.result()
                    # 规整字段
                    res.setdefault("note", "")
                    res.setdefault("kpis", [])
                    res.setdefault("tables", [])
                    res.setdefault("callouts", [])
                    res.setdefault("summary", "")
                    sections_out[k] = res
                except Exception as e:
                    sections_out[k] = {
                        "note": "该维度生成失败：{}".format(e),
                        "kpis": [], "tables": [], "callouts": ["⚠️ 调用模型出错，请检查 API Key / Base URL / 网络。"],
                        "summary": "生成失败",
                    }
        # 顶部摘要：拼接各维度 summary；顶部 KPI 聚合各维度 kpis（amz 维度有真实 KPI）
        summary_parts = ["{}：{}".format(DIMS[k]['title'], sections_out[k].get('summary','')) for k in sections_out]
        summary = "「" + str(topic) + "」自动调研（大模型实时生成）。" + "；".join(summary_parts)
        top_kpis = []
        for k in sections_out:
            for kp in sections_out[k].get("kpis", []) or []:
                top_kpis.append(kp)
        return {
            "topic": topic,
            "mode": "live",
            "generatedAt": now_beijing(),
            "summary": summary,
            "kpis": top_kpis,
            "sections": sections_out,
        }

    # —— 模板数据（离线·卖家精灵快照 / 示意）模式 ——
    # 模板模式：统一走通用骨架（v1.5.4 起不再有任何固定产品死数据）
    data = demo_generic(topic)
    sections_out = {}
    amz_summaries = []
    for k in dims:
        if k == "amz_us":
            sections_out[k] = demo_amz_us(topic); amz_summaries.append("【亚马逊美国·机会评分看板】" + sections_out[k]["summary"])
        elif k == "amz_eu":
            sections_out[k] = demo_amz_eu(topic); amz_summaries.append("【亚马逊欧洲·市场看板】" + sections_out[k]["summary"])
        elif k in data["sections"]:
            sections_out[k] = data["sections"][k]
    # 摘要拼接
    base_dims = [k for k in dims if k in ("mkt", "usr", "prod", "comp", "tech", "reg")]
    if amz_summaries and base_dims:
        summary = data["summary"] + " " + " ".join(amz_summaries)
    elif amz_summaries:
        summary = " ".join(amz_summaries)
    else:
        summary = data["summary"]
    return {
        "topic": topic,
        "mode": "template",
        "generatedAt": now_beijing(),
        "summary": summary,
        "kpis": data.get("kpis", []) if base_dims else [],
        "sections": sections_out,
    }


# ---------------------------------------------------------------------------
# HTTP 处理器
# ---------------------------------------------------------------------------
class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8", cors=True):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False)
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        if cors:
            # 允许 GitHub Pages 等前端跨域调用；生产可改为具体域名
            self.send_header("Access-Control-Allow-Origin", os.environ.get("RD_CORS_ORIGIN", "*"))
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        # 预检请求（CORS）
        self._send(204, "", cors=True)

    def do_GET(self):
        _path = self.path.split("?")[0]
        if _path in ("/", "/index.html"):
            try:
                with open(os.path.join(BASE, "index.html"), "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            except FileNotFoundError:
                self._send(404, "index.html not found")
        elif _path == "/api/status":
            self._send(200, {
                "mode": MODE,
                "backendMode": MODE,
                "llm": bool(LLM_KEY),
                "model": LLM_MODEL if LLM_KEY else None,
                "llmConfigurable": False,
                "defaultBase": "https://api.deepseek.com/v1",
                "defaultModel": "deepseek-chat",
                "sources": ["template", "llm"],
                "dims": list(DIMS.keys()),
                "dimsMeta": DIMS,
                "cloudReports": bool(os.environ.get("GITHUB_TOKEN")),
            })
        elif _path == "/api/reports":
            # 云端报告列表（需 token；未配 GITHUB_TOKEN 时返回空列表，前端回退本地）
            rd_token = os.environ.get("RD_TOKEN")
            if rd_token:
                auth = self.headers.get("Authorization", "")
                q_token = ""
                if "?" in self.path:
                    from urllib.parse import parse_qs
                    q_token = parse_qs(self.path.split("?", 1)[1]).get("token", [""])[0]
                if auth.replace("Bearer ", "") != rd_token and q_token != rd_token:
                    self._send(401, {"error": "未授权：缺少有效 token。请在请求头带 Authorization: Bearer <RD_TOKEN>，或部署时移除 RD_TOKEN 关闭鉴权。"})
                    return
            try:
                content, _sha = gh_get_report_file()
            except Exception as e:
                self._send(500, {"error": "读取云端报告失败: {}".format(e)})
                return
            self._send(200, {"reports": content if content else []})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        _path = self.path.split("?")[0]
        if _path == "/api/research":
            # —— 极简 token 鉴权（公网暴露前必须开启）——
            rd_token = os.environ.get("RD_TOKEN")
            if rd_token:
                auth = self.headers.get("Authorization", "")
                q_token = ""
                if "?" in self.path:
                    from urllib.parse import parse_qs
                    q_token = parse_qs(self.path.split("?", 1)[1]).get("token", [""])[0]
                if auth.replace("Bearer ", "") != rd_token and q_token != rd_token:
                    self._send(401, {"error": "未授权：缺少有效 token。请在请求头带 Authorization: Bearer <RD_TOKEN>，或部署时移除 RD_TOKEN 关闭鉴权。"})
                    return
            try:
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length)
                payload = json.loads(raw.decode("utf-8"))
            except Exception as e:
                self._send(400, {"error": "bad request: {}".format(e)})
                return
            topic = payload.get("topic", "")
            dims = payload.get("dims", [])
            if not isinstance(dims, list):
                dims = []
            source = payload.get("source", "template")
            # 安全约定：Key 只能来自服务端环境变量，绝不接受前端传入的 llm.key，
            # 防止访客用自己的 Key 绕过额度管控或冒用他人 Key。前端已移除填 Key 入口。
            key = LLM_KEY
            base = LLM_BASE
            model = LLM_MODEL
            llm = {"key": key, "base": base, "model": model}
            # 仅保留已知维度；为空则默认全选
            dims = [d for d in dims if d in DIMS]
            if not dims:
                dims = list(DIMS.keys())
            if source == "llm" and not key:
                self._send(400, {"error": "后端未配置 LLM Key（OPENAI_API_KEY/ANTHROPIC_API_KEY 环境变量）。请联系站长。"})
                return
            result = build_report(topic, dims, source=source, llm=llm)
            self._send(200, result)
        elif _path == "/api/reports":
            # 保存报告到云端（需 token + GITHUB_TOKEN）
            rd_token = os.environ.get("RD_TOKEN")
            if rd_token:
                auth = self.headers.get("Authorization", "")
                q_token = ""
                if "?" in self.path:
                    from urllib.parse import parse_qs
                    q_token = parse_qs(self.path.split("?", 1)[1]).get("token", [""])[0]
                if auth.replace("Bearer ", "") != rd_token and q_token != rd_token:
                    self._send(401, {"error": "未授权：缺少有效 token。请在请求头带 Authorization: Bearer <RD_TOKEN>，或部署时移除 RD_TOKEN 关闭鉴权。"})
                    return
            try:
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length)
                payload = json.loads(raw.decode("utf-8"))
            except Exception as e:
                self._send(400, {"error": "bad request: {}".format(e)})
                return
            if not os.environ.get("GITHUB_TOKEN"):
                self._send(500, {"error": "后端未配置 GITHUB_TOKEN（环境变量）。请联系站长开启云端报告。"})
                return
            report = payload.get("report")
            if not report or not isinstance(report, dict) or not report.get("topic"):
                self._send(400, {"error": "缺少 report 对象（需含 topic）"})
                return
            try:
                content, sha = gh_get_report_file()
                if content is None:
                    content = []
                if not isinstance(content, list):
                    content = []
                # 同 topic+generatedAt 去重替换（避免重复保存同一份）
                rid = report.get("id") or (report.get("topic", "") + "|" + report.get("generatedAt", ""))
                kept = [r for r in content if r.get("id") != rid]
                kept.insert(0, report)
                content = kept[:200]  # 上限 200 份，防仓库膨胀
                gh_save_report_file(content, sha)
            except Exception as e:
                self._send(500, {"error": "保存云端报告失败: {}".format(e)})
                return
            self._send(200, {"ok": True, "id": rid, "count": len(content)})
        else:
            self._send(404, {"error": "not found"})

    def log_message(self, *args):
        pass  # 静默日志


# ---------------------------------------------------------------------------
# 云端报告存储（GitHub Contents API）
# 报告保存到仓库 research-deck/saved/reports.json，任何设备登录后可见。
# 需要环境变量 GITHUB_TOKEN（fine-grained PAT，仓库 Contents 读写）。
# ---------------------------------------------------------------------------
REPORTS_PATH = os.environ.get("RD_REPORTS_PATH", "research-deck/saved/reports.json")
GITHUB_API = "https://api.github.com"
GITHUB_REPO = os.environ.get("GITHUB_REPO", "Aurillis/database")


def _gh_headers():
    tok = os.environ.get("GITHUB_TOKEN", "")
    return {
        "Authorization": "Bearer " + tok,
        "Accept": "application/vnd.github+json",
        "User-Agent": "researchdeck-scf",
    }


def gh_get_report_file():
    """读取远端 reports.json，返回 (content_json, sha)；不存在返回 (None, None)。"""
    tok = os.environ.get("GITHUB_TOKEN", "")
    if not tok:
        return None, None
    url = "{}/repos/{}/contents/{}".format(GITHUB_API, GITHUB_REPO, REPORTS_PATH)
    req = urllib.request.Request(url, headers=_gh_headers())
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
            import base64
            content = json.loads(base64.b64decode(data.get("content", "")).decode("utf-8"))
            return content, data.get("sha")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None, None
        raise


def gh_save_report_file(content, sha):
    """把整个 reports.json 写回远端（带 sha 条件更新）。返回 True/抛异常。"""
    tok = os.environ.get("GITHUB_TOKEN", "")
    import base64
    body = {
        "message": "researchdeck: update saved reports",
        "content": base64.b64encode(json.dumps(content, ensure_ascii=False).encode("utf-8")).decode("ascii"),
    }
    if sha:
        body["sha"] = sha
    url = "{}/repos/{}/contents/{}".format(GITHUB_API, GITHUB_REPO, REPORTS_PATH)
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers=_gh_headers(), method="PUT")
    with urllib.request.urlopen(req, timeout=20) as r:
        r.read()
    return True


# ---------------------------------------------------------------------------
# 腾讯云 SCF 入口（API 网关触发，集成响应）
# 本地 python3 server.py 行为不变；部署到 SCF 时由 main_handler 接管
# ---------------------------------------------------------------------------
def main_handler(event, context):
    """SCF + API 网关入口。
    event 结构（API 网关集成响应）：
      { "httpMethod": "GET/POST", "path": "/api/...", "headers": {...},
        "body": "<raw string>", "queryString": {...}, "isBase64Encoded": bool }
    返回需含 statusCode / headers / body（集成响应模式）。
    """
    method = (event.get("httpMethod") or "GET").upper()
    path = event.get("path") or "/"
    # 兼容 API 网关前缀（如 /research/api/status）→ 剥到 /api 或 /
    prefix = os.environ.get("RD_PATH_PREFIX", "")
    if prefix and path.startswith(prefix):
        path = path[len(prefix):] or "/"
    elif "/api/" in path and not path.startswith("/api"):
        path = path[path.index("/api"):]
    elif not path.startswith("/api") and (path.endswith("/api/status") or path.endswith("/api/research")):
        path = "/" + path.rsplit("/", 1)[-1]
    headers = event.get("headers") or {}
    # 兼容 API 网关把 query 拼到 path 的情况
    qs = event.get("queryString") or {}
    if "?" in path and not qs:
        from urllib.parse import urlsplit, parse_qs
        parsed = urlsplit(path)
        qs = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        path = parsed.path
    # token 经 query 传入时，注入到 Authorization 头，统一走 Bearer 鉴权
    if qs.get("token") and "Authorization" not in headers:
        headers = dict(headers)
        headers["Authorization"] = "Bearer " + qs["token"]
    body_raw = event.get("body") or ""
    if event.get("isBase64Encoded") and body_raw:
        import base64
        body_raw = base64.b64decode(body_raw).decode("utf-8")

    # 复用 Handler 的响应逻辑：捕获 _send 输出
    captured = {}

    class _SCFHandler(Handler):
        def _send(self, code, body, ctype="application/json; charset=utf-8", cors=True):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False)
            if isinstance(body, str):
                body = body.encode("utf-8")
            captured["code"] = code
            captured["headers"] = {
                "Content-Type": ctype,
                "Access-Control-Allow-Origin": os.environ.get("RD_CORS_ORIGIN", "*"),
                "Access-Control-Allow-Headers": "Content-Type, Authorization",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            }
            captured["body"] = body.decode("utf-8") if isinstance(body, bytes) else body

        def do_OPTIONS(self):
            self._send(204, "")

        def _read_post(self):
            return body_raw

    h = _SCFHandler
    # 模拟一次请求分派
    fake = _SCFHandler.__new__(_SCFHandler)
    fake.path = path
    _hl = len(body_raw.encode("utf-8"))

    class _Headers:
        def get(self, k, d=None):
            if k == "Content-Length":
                return str(_hl)
            return headers.get(k, d)
    class _RFile:
        def read(self, n=None):
            return body_raw.encode("utf-8")
    fake.headers = _Headers()
    fake.rfile = _RFile()
    try:
        if method == "GET":
            fake.do_GET()
        elif method == "POST":
            fake.do_POST()
        elif method == "OPTIONS":
            fake.do_OPTIONS()
        else:
            fake._send(405, {"error": "method not allowed"})
    except Exception as e:
        captured["code"] = 500
        captured["headers"] = {"Content-Type": "application/json; charset=utf-8"}
        captured["body"] = json.dumps({"error": "internal: {}".format(e)}, ensure_ascii=False)
    return {
        "statusCode": captured.get("code", 500),
        "headers": captured.get("headers", {"Content-Type": "application/json"}),
        "body": captured.get("body", ""),
    }


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", PORT), Handler) as httpd:
        print("调研台 ResearchDeck (A2) 已启动 → http://localhost:{}  [mode={}]".format(PORT, MODE))
        if MODE == "demo":
            print("提示：默认「模板数据」模式。在网页端可选择「大模型实时生成」并填 DeepSeek Key 测试（无需重启）。")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止。")
