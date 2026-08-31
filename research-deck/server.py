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

# v1.7.0：简单限流（进程内滑动窗口）。防止 token 泄露后被高频滥用。
# 每 key（token 或 IP）每 RATE_WINDOW 秒最多 RATE_LIMIT 次 /api/research。
# 注：SCF 多实例下为近似值；更严格限速请用腾讯云控制台配额（QPS）。
import time as _time
_RATE_WINDOW = int(os.environ.get("RD_RATE_WINDOW", "60"))   # 秒
_RATE_LIMIT = int(os.environ.get("RD_RATE_LIMIT", "10"))     # 窗口内次数
_rate_hits = {}  # key -> [ts, ts, ...]

def _check_rate(key):
    if not key:
        return True
    now = _time.time()
    hits = [t for t in _rate_hits.get(key, []) if now - t < _RATE_WINDOW]
    if len(hits) >= _RATE_LIMIT:
        _rate_hits[key] = hits
        return False
    hits.append(now)
    _rate_hits[key] = hits
    return True

# ---------------------------------------------------------------------------
# 维度元信息（与前端一致，单一事实源）
# ---------------------------------------------------------------------------
DIMS = {
    "mkt":  {"title": "市场调研", "icon": "📊", "badge": "规模 / 集中度 / 机会矩阵"},
    "usr":  {"title": "用户研究", "icon": "👥", "badge": "痛点 / 场景 / 信号强度"},
    "prod": {"title": "产品调研", "icon": "🔬", "badge": "型号拆解 / 参数盘点"},
    "comp": {"title": "竞品分析", "icon": "⚔️", "badge": "定位 / 卡位矩阵 / 空位"},
    "tech": {"title": "技术研究", "icon": "⚙️", "badge": "方案对标 / 工程能力"},
    "reg":  {"title": "合规审计", "icon": "🛡️", "badge": "监管路径 / 合规边界"},
    "sc":   {"title": "供应链/成本", "icon": "📦", "badge": "成本结构 / 供应链 / 降本"},
    "amz_us": {"title": "亚马逊美国·机会评分看板", "icon": "🇺🇸",
               "badge": "看板结构 · 卖家精灵 MCP", "template": True},
    "amz_eu": {"title": "亚马逊欧洲·市场看板", "icon": "🇪🇺",
               "badge": "看板结构 · 卖家精灵 MCP", "template": True},
}

# ---------------------------------------------------------------------------
# 5 类调研类型（v2.0：产品经理视角的调研工作台）
# 每类调研 = 固定研究骨架（模块清单） + 维度映射（复用现有 9 维度）
# 三种形式：standard（标准）/ topic（专题）/ comprehensive（综合立项）
# ---------------------------------------------------------------------------
RESEARCH_TYPES = {
    "market": {
        "title": "市场机会研究",
        "icon": "📊",
        "desc": "这个赛道值不值得做？",
        "dims": ["mkt", "reg"],
        "modules": "市场定义 → 市场规模 → 增长趋势 → 区域结构 → 用户规模 → 增长驱动 → 抑制因素 → 政策/社会/技术趋势 → 竞争格局 → 市场成熟度 → 机会方向 → 进入判断",
        "prompt": "你是市场机会研究分析师。针对「{topic}」，产出完整市场机会研究报告：①市场定义与边界 ②市场规模与增长(CAGR) ③区域结构 ④用户规模与画像 ⑤增长驱动因素 ⑥抑制/风险因素 ⑦政策/社会/技术趋势 ⑧竞争格局与集中度 ⑨市场成熟度判断 ⑩机会方向 ⑪进入时机判断(早/中/晚/不宜)。每条数字标注来源；拿不到写「未获取」。",
    },
    "ecom": {
        "title": "电商市场研究",
        "icon": "🛒",
        "desc": "Amazon 等渠道有没有生意机会？",
        "dims": ["amz_us", "amz_eu"],
        "modules": "市场容量 → 销售趋势 → 品牌结构 → 卖家结构 → 价格带 → 新品表现 → Top ASIN → 产品细分 → 关键词 → 流量结构 → 评论 → 用户痛点 → 竞争强度 → 机会评分 → 产品建议",
        "prompt": "你是电商市场研究分析师。针对「{topic}」在亚马逊渠道的市场机会，产出：①市场容量与销售趋势 ②品牌结构(CR5/CR10) ③卖家结构(自营vs第三方) ④价格带分布 ⑤新品表现 ⑥Top ASIN ⑦产品细分 ⑧核心关键词与流量 ⑨评论洞察与用户痛点 ⑩竞争强度 ⑪机会评分(0-100) ⑫产品进入建议。数据优先来自卖家精灵 MCP；拿不到写「未获取」。",
    },
    "comp": {
        "title": "竞品研究",
        "icon": "⚔️",
        "desc": "市面上的产品怎么做？哪里还有空位？",
        "dims": ["comp", "prod"],
        "modules": "竞品池 → 品牌定位 → 产品线 → 价格 → 用户 → 场景 → 功能 → 参数 → 结构 → 材质 → 操作交互 → 软件/App → 技术方案 → 合规 → 评论表现 → 优势 → 缺点 → 产品空白",
        "prompt": "你是竞品研究分析师。针对「{topic}」的竞品格局，产出：①竞品池与分类 ②品牌定位与产品线 ③价格-功能卡位矩阵 ④用户与场景 ⑤功能/参数/结构/材质横向对比 ⑥操作交互与软件App ⑦技术方案 ⑧合规情况 ⑨评论表现(评分/口碑) ⑩各自优势与缺点 ⑪产品空白与差异化机会。基于真实产品信息；无法查证的标「待核验」。",
    },
    "user": {
        "title": "用户研究",
        "icon": "👥",
        "desc": "谁在用？为什么买？哪里不满意？",
        "dims": ["usr"],
        "modules": "用户分群 → 触发问题 → 使用场景 → 当前解决方案 → 购买动机 → 决策因素 → 使用流程 → 满意点 → 痛点 → 差评 → 放弃/退货原因 → 替代方案 → 未满足需求 → 用户原话 → 需求优先级",
        "prompt": "你是用户研究分析师。针对「{topic}」的目标用户，在 Reddit、X、Facebook、Quora、亚马逊评论等检索真实讨论，产出：①用户分群 ②触发问题(什么情境下需要) ③使用场景 ④当前解决方案 ⑤购买动机 ⑥决策因素 ⑦使用流程 ⑧满意点 ⑨痛点(带提及频率) ⑩差评与退货原因 ⑪替代方案 ⑫未满足需求 ⑬用户原话(附来源) ⑭需求优先级。标注信号强度(强/中/弱)。",
    },
    "tech": {
        "title": "技术研究",
        "icon": "⚙️",
        "desc": "这个产品怎么实现？哪条技术路线最好？",
        "dims": ["tech", "sc"],
        "modules": "需求 → 技术原理 → 技术路线 → 方案对比 → 核心器件 → 系统架构 → 参数 → 性能边界 → 成熟度 → 成本 → 供应链 → 专利 → 法规标准 → 安全风险 → 技术难点 → 推荐方案",
        "prompt": "你是技术研究分析师。针对「{topic}」的实现技术，产出：①技术需求拆解 ②技术原理 ③技术路线对比(按品类实际路线，勿预设) ④方案优劣对比 ⑤核心器件/组件 ⑥系统架构 ⑦关键参数 ⑧性能边界 ⑨技术成熟度 ⑩成本结构 ⑪供应链 ⑫专利情况 ⑬法规标准 ⑭安全风险 ⑮技术难点 ⑯推荐方案。基于公开资料；无法查证的标「待核验」。",
    },
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
    "mkt": "你是市场调研分析师。针对「{topic}」，用真实数据（若有 SellerSprite/卖家精灵等导出数据优先标注来源）产出：①品类规模与增长 ②集中度 CR5/CR10、头部品牌份额 ③价格带分布 ④月度/年度趋势（标注数据缺口）⑤供需结构 ⑥市场机会矩阵（高需求×低竞争=优先机会；高需求×高竞争=红海谨慎；低需求=观望），并给出「进入时机」判断（早/中/晚/不宜）。每条数字标注来源；拿不到写「未获取」。",
    "usr": "你是用户研究分析师。针对「{topic}」目标人群，在 Reddit、X、Facebook、Quora、亚马逊评论等检索真实讨论，产出：①核心痛点（高频，附提及频率估算）②使用场景 ③未被满足的需求 ④可拓展人群/场景。每条附社区名/帖子标题或 URL，标注信号强度（强/中/弱）与出现频率（高频/中频/低频）；如可统计，给出痛点提及占比表（痛点|提及次数估算|信号强度）。",
    "prod": "你是产品拆解分析师。针对「{topic}」覆盖的主要型号/SKU，产出硬件/功能参数横向对比：形态结构、核心器件/组件、关键性能参数、材质、规格、软件/智能功能（按品类实际涉及的维度组织，勿预设固定组件）。基于真实型号参数；无法查证的标「待核验」。",
    "comp": "你是竞品分析师。针对「{topic}」头部与典型玩家，产出：①定位 ②定价 ③功能矩阵 ④优势 ⑤明显弱点（引评论/评测）⑥「价格-功能卡位矩阵」（表：品牌|价格带|功能档位|卡位结论：性价比/高端/细分/空白），标注哪些价位-功能组合尚未被占领（即机会空位）。标注信息来源。",
    "tech": "你是技术对标分析师。针对「{topic}」实际涉及的核心技术与工程方案（根据该品类真实情况自行判断：如动力/加热/传感/材料/软件/连接等，勿预设技术路线），产出：各技术路线的代表方案、适用场景、实现难度、对本品差异化的壁垒意义。基于公开资料；无法查证的标「待核验」。",
    "reg": "你是合规审计分析师。针对「{topic}」所属监管类目（按品类实际适用的法规体系判断：消费品 / 电器 / 医疗器械 / 食品接触 / 化妆品等，勿预设特定体系），检索数据库与文献，产出：监管路径判定、所需资质/备案、红线措辞、对我们的启示。强调「禁止无依据宣称功效」。",
    "sc": "你是供应链与成本分析师。针对「{topic}」该类目，基于公开信息与行业常识（勿编造具体厂商报价），产出：①成本结构拆解（物料/制造/物流/平台费用占比，标注估算）②关键供应链环节（核心材料/元器件/代工厂/认证）③起订量/模具/开发门槛 ④成本优化空间与降本路径 ⑤采购与库存建议。每条标注「估算/公开信息/待核验」。",
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
    """从 LLM 返回中稳健解析 JSON：兼容纯 JSON / ```json 代码块 / 前后缀噪声 / 对象或数组。

    v2.0.1：三级兜底——先整体解析；失败再截取 {...} 对象；再失败截取 [...] 数组
    （研究计划是 JSON 数组，旧版只认对象导致解析失败走 fallback 只剩 1 个研究点）。
    """
    if not isinstance(content, str):
        content = str(content)
    s = content.strip()
    # 去掉 markdown 代码块围栏
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s[3:]
        if s.endswith("```"):
            s = s[:-3]
        s = s.strip()
    # 1) 整体解析
    try:
        return json.loads(s)
    except Exception:
        pass
    # 2) 截取对象 {...}
    start, end = s.find("{"), s.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(s[start:end + 1])
        except Exception:
            pass
    # 3) 截取数组 [...]
    start, end = s.find("["), s.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(s[start:end + 1])
        except Exception:
            pass
    raise ValueError("无法从 LLM 输出中解析 JSON: " + s[:80])


def _norm_sec(d):
    """v2.2.2：LLM 返回的 section 字段归一化——callouts/kpis/tables 必须是数组，
    模型偶发返回字符串/对象时转成单元素数组，避免前端 .forEach 崩溃。"""
    if not isinstance(d, dict):
        return d
    for k in ("callouts", "kpis", "tables"):
        v = d.get(k)
        if v is None:
            d[k] = []
        elif not isinstance(v, list):
            d[k] = [v]
    return d


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
        return _norm_sec(_extract_json(content))
    except Exception:
        return _norm_sec({
            "note": "该维度模型返回无法解析为 JSON，已降级为结构骨架。",
            "kpis": [],
            "tables": [],
            "callouts": ["⚠️ 模型返回格式异常，建议重试或检查模型是否支持结构化输出。"],
            "summary": "生成失败（JSON 解析）",
        })


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
def _auto_archive(payload, report):
    """v2.2.1 断点保护：把刚生成完成的报告自动归档为「草稿」(draft:true)。
    前端正常拿到结果后会以同 id 覆盖为正式记录；若前端刷新/断线，草稿留在云端，
    前端下次启动检测到后提示「恢复并正式归档」。失败静默（不影响主响应）。"""
    if not isinstance(report, dict) or not report.get("topic") or not report.get("generatedAt"):
        return
    try:
        rid = report.get("id") or (report.get("topic", "") + "|" + report.get("generatedAt", ""))
        rec = {
            "id": rid,
            "topic": report.get("topic", ""),
            "generatedAt": report.get("generatedAt", ""),
            "_ts": report.get("_ts") or (report.get("generatedAt", "") + "-auto"),
            "mode": report.get("mode", ""),
            "dims": list((report.get("sections") or {}).keys()),
            "data": report,
            "product_id": (payload or {}).get("product_id"),
            "research_id": (payload or {}).get("research_id"),
            "research_type": (payload or {}).get("research_type") or "other",
            "research_mode": (payload or {}).get("research_mode") or report.get("mode") or "standard",
            "status": "completed",
            "created_at": (payload or {}).get("created_at"),
            "completed_at": None,
            "cloud": True,
            "draft": True,
        }
        content, sha = gh_get_report_file()
        if content is None or not isinstance(content, list):
            content = []
        content = [r for r in content if r.get("id") != rid]
        content.insert(0, rec)
        gh_save_report_file(content[:200], sha)
    except Exception:
        pass


def build_report(topic, dims, source="template", llm=None, mode="standard", question=""):
    # v2.2.3：专题调研(topic 模式)下 topic 可能为空(前端只填了问题)，优先用 question 兜底，避免归档成「未命名调研主题」
    topic = (topic or "").strip() or (question or "").strip() or "未命名调研主题"
    dims = [d for d in dims if d in DIMS]
    if not dims:
        dims = list(DIMS.keys())

    # —— v2.0 综合立项研究：串联 5 类调研 + 决策面板 ——
    if mode == "comprehensive" and source == "llm" and llm and llm.get("key"):
        return _build_comprehensive(topic, llm)

    # —— v2.0 专题调研：按问题生成研究计划并执行 ——
    if mode == "topic" and source == "llm" and llm and llm.get("key"):
        return _build_topic(topic, question or topic, llm)

    # —— 标准调研：按研究类型解析维度，走原有维度逻辑 ——
    rtype = None
    if mode != "advanced":
        # mode 传研究类型 id（如 market/ecom/comp/user/tech），映射到维度
        if mode in RESEARCH_TYPES:
            rtype = RESEARCH_TYPES[mode]
            dims = rtype["dims"]
        elif mode == "standard":
            pass  # 使用传入 dims

    # —— 实时生成（大模型）模式 ——
    if source == "llm" and llm and llm.get("key"):
        # v1.5.2：并行调用各维度（多维度同时请求 DeepSeek），总耗时从 串行 n×20s 降到 ~20-40s，
        # 避免多维度在 SCF 超时（30s）内跑不完导致 Failed to fetch。
        # v1.7.0：单维度失败自动重试 1 次（网络抖动/限流容错）。
        import concurrent.futures

        def _call_once(k):
            return call_llm_dim(topic, k, llm)

        def _call_with_retry(k):
            try:
                return _call_once(k)
            except Exception:
                # 重试 1 次
                return _call_once(k)

        sections_out = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, len(dims))) as ex:
            fut = {ex.submit(_call_with_retry, k): k for k in dims}
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
    base_dims = [k for k in dims if k in ("mkt", "usr", "prod", "comp", "tech", "reg", "sc")]
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
# v2.0 综合立项研究：并联 5 类调研 + 决策面板
# ---------------------------------------------------------------------------
def _build_comprehensive(topic, llm):
    import concurrent.futures
    types = ["market", "ecom", "comp", "user", "tech"]
    results = {}

    def _run(tid):
        rt = RESEARCH_TYPES[tid]
        # 复用 call_llm_dim（带品类提示词），返回维度结果
        dim_results = {}
        for k in rt["dims"]:
            try:
                dim_results[k] = call_llm_dim(topic, k, llm)
            except Exception as e:
                dim_results[k] = {"note": "生成失败：{}".format(e), "kpis": [], "tables": [], "callouts": [], "summary": "生成失败"}
        return rt, dim_results

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        futs = {ex.submit(_run, tid): tid for tid in types}
        for f in concurrent.futures.as_completed(futs):
            tid = futs[f]
            try:
                rt, dim_results = f.result()
                results[tid] = {"meta": {k: rt[k] for k in ("title", "icon", "desc")}, "dims": dim_results}
            except Exception as e:
                results[tid] = {"meta": {"title": tid, "icon": "❓", "desc": ""}, "dims": {}, "error": str(e)}

    # 汇总各维度 summary 供决策
    def _sum(tid):
        parts = []
        for k, v in results.get(tid, {}).get("dims", {}).items():
            s = (v.get("summary") or "").strip()
            if s and s != "生成失败":
                parts.append(s)
        return "；".join(parts[:3])

    # 决策面板：基于 5 类调研结果由 LLM 汇总成 5 段式结论
    decision = {}
    try:
        digest = "\n".join("【{}】{}".format(tid, _sum(tid)) for tid in types if _sum(tid))
        decision_prompt = (
            "你是产品立项评审专家。基于以下针对「{}」的5类调研摘要，输出产品立项决策JSON：\n"
            "{{\"market\":\"市场是否成立？结论+关键依据(2-3句)\",\"user\":\"用户核心需求是什么？(3-5条，用顿号分隔)\","
            "\"opp\":\"竞争机会在哪？(空位/差异化机会，2-3句)\",\"tech\":\"技术是否可行？结论+关键风险点(2-3句)\","
            "\"define\":\"产品应该怎么定义？一句话定位+3条关键建议\"}}\n"
            "只输出JSON对象，不要解释。\n\n调研摘要：\n{}".format(topic, digest)
        )
        payload = {
            "model": llm["model"],
            "messages": [
                {"role": "system", "content": "你是产品立项评审专家，输出严格 JSON。"},
                {"role": "user", "content": decision_prompt},
            ],
            "temperature": 0.3,
        }
        req = urllib.request.Request(
            llm["base"].rstrip("/") + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": "Bearer " + llm["key"], "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            content = json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"]
        decision = _extract_json(content) or {}
    except Exception as e:
        decision = {"error": str(e)}

    # sections 组装（与旧报告结构兼容：把 5 类研究作为 sections，键名带前缀）
    sections_out = {}
    for tid in types:
        rt = results.get(tid, {})
        for k, v in rt.get("dims", {}).items():
            sections_out[k] = v
        # 补充研究类型说明
        if rt.get("meta"):
            sections_out.setdefault("rt_" + tid, {
                "note": "【{}】{} {}".format(rt["meta"]["title"], rt["meta"]["desc"], RESEARCH_TYPES[tid]["modules"]),
                "kpis": [], "tables": [], "callouts": [], "summary": _sum(tid),
            })
    summary = "「{}」综合立项研究：市场是否成立见决策面板。".format(topic)
    return {
        "topic": topic,
        "mode": "comprehensive",
        "generatedAt": now_beijing(),
        "summary": summary,
        "decision": decision,
        "researchTypes": [{"id": tid, "title": RESEARCH_TYPES[tid]["title"]} for tid in types],
        "kpis": [],
        "sections": sections_out,
    }


# ---------------------------------------------------------------------------
# v2.0 专题调研：按问题生成研究计划 → 并行执行
# ---------------------------------------------------------------------------
def _build_topic(topic, question, llm):
    import concurrent.futures
    # 1. LLM 生成研究计划（3-5 个研究点）
    plan = []
    try:
        plan_prompt = (
            "针对问题「{q}」，制定一个聚焦的研究计划，输出 JSON 数组，3-5 个研究点，每项含 title(10字内) 和 focus(具体要查什么，30字内)：\n"
            "[{{\"title\":\"...\",\"focus\":\"...\"}}]\n只输出 JSON 数组。".format(q=question)
        )
        payload = {
            "model": llm["model"],
            "messages": [
                {"role": "system", "content": "你是研究规划专家，输出严格 JSON 数组。"},
                {"role": "user", "content": plan_prompt},
            ],
            "temperature": 0.3,
        }
        req = urllib.request.Request(
            llm["base"].rstrip("/") + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": "Bearer " + llm["key"], "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            content = json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"]
        plan = _extract_json(content) or []
        if not isinstance(plan, list) or not plan:
            plan = [{"title": "核心问题", "focus": question}]
    except Exception:
        plan = [{"title": "核心问题", "focus": question}]

    # 2. 并行执行每个研究点
    def _run(p):
        pid = p.get("title", "研究点")
        focus = p.get("focus", question)
        prompt = "你是专题研究员。针对问题「{}」，研究子项「{}：{}」，产出结构化发现：\n".format(question, pid, focus) + (
            "{{\"note\":\"研究方法(一句)\",\"kpis\":[{{\"v\":\"值\",\"l\":\"含义\"}}],"
            "\"tables\":[{{\"head\":[\"发现\",\"详情\",\"来源/依据\"],\"rows\":[[\"...\",\"...\",\"...\"]]}}],"
            "\"callouts\":[\"关键结论或风险(一句)\"],\"summary\":\"本子项一句话结论\"}}\n"
            "只输出 JSON 对象，数据诚实，拿不到写「未获取」。"
        )
        sysmsg = "你是「调研台 ResearchDeck」专题研究员。数据诚实：能用真实数据源就标注来源，拿不到的明确写「未获取」。"
        payload = {
            "model": llm["model"],
            "messages": [{"role": "system", "content": sysmsg}, {"role": "user", "content": prompt}],
            "temperature": 0.3,
        }
        req = urllib.request.Request(
            llm["base"].rstrip("/") + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": "Bearer " + llm["key"], "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            content = json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"]
        try:
            res = _extract_json(content)
        except Exception:
            res = {}
        res.setdefault("note", "")
        res.setdefault("kpis", [])
        res.setdefault("tables", [])
        res.setdefault("callouts", [])
        res.setdefault("summary", "")
        return pid, res

    sections_out = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(5, len(plan))) as ex:
        futs = {ex.submit(_run, p): p for p in plan}
        for f in concurrent.futures.as_completed(futs):
            try:
                pid, res = f.result()
                sections_out["t_" + pid] = res
            except Exception as e:
                sections_out["t_" + str(futs[f].get("title", "点"))] = {"note": "失败：{}".format(e), "kpis": [], "tables": [], "callouts": [], "summary": "生成失败"}

    summary = "「{}」专题调研：{}".format(topic, question)
    return {
        "topic": topic,
        "mode": "topic",
        "generatedAt": now_beijing(),
        "summary": summary,
        "plan": plan,
        "question": question,
        "kpis": [],
        "sections": sections_out,
    }


# ---------------------------------------------------------------------------
# v2.2.0 产品综合研究总览 Product Research Overview
# 定位：不是再生成一份综合报告，而是每个产品主页里「持续更新的研究驾驶舱」。
# 铁律：新 Research 完成后 → 报告照旧自动归档 → AI 只产出「更新建议」(pending_updates)
#       → 用户确认后才写入 findings / opportunities / risks / research_gaps。
# ---------------------------------------------------------------------------
# 总览结论按领域分组（与前端展示顺序一致）
OVERVIEW_DIMS = [
    ("mkt", "市场判断"), ("ecom", "电商判断"), ("usr", "用户判断"),
    ("comp", "竞品判断"), ("tech", "技术判断"), ("reg", "法规判断"),
    ("sc", "供应链判断"), ("other", "其他"),
]
OVERVIEW_DIM_KEYS = [d for d, _ in OVERVIEW_DIMS]
# 研究类型 → 结论领域
RTYPE_TO_DIM = {
    "market": "mkt", "ecom": "ecom", "comp": "comp", "user": "usr",
    "tech": "tech", "reg": "reg", "sc": "sc",
    "patent": "other", "other": "other", "comprehensive": "other",
}
OVERVIEW_CONFIDENCE = ("High", "Medium", "Low")
OVERVIEW_SEVERITY = ("High", "Medium", "Low")
OVERVIEW_PRIORITY = ("High", "Medium", "Low")
GAP_STATUS = ("未研究", "研究中", "已解决")
RISK_STATUS = ("待验证", "已验证", "已解决")


def _uid(prefix):
    """生成带时间前缀的唯一 id（同一毫秒内靠随机后缀区分）。"""
    import random
    import string
    return "{}_{}{}".format(
        prefix,
        datetime.datetime.now(BEIJING_TZ).strftime("%y%m%d%H%M%S"),
        "".join(random.choice(string.ascii_lowercase) for _ in range(3)),
    )


def overview_skeleton(pid):
    """产品的空总览结构（所有内容必须与 product_id 绑定）。"""
    return {
        "product_id": pid,
        "findings": {},          # {dim: [{id, kind, text, source_research_ids, created_at, updated_at}]}
        "opportunities": [],     # [{id, title, description, source_research_ids, related_dimensions, confidence, status, created_at, updated_at}]
        "risks": [],             # [{id, title, description, severity, source_research_ids, status, created_at, updated_at}]
        "hypotheses": [],        # [{id, text, source_research_ids, status, created_at, updated_at}]
        "research_gaps": [],     # [{gap_id, title, description, dimension, priority, status, source_research_ids, created_at, updated_at}]
        "pending_updates": [],   # 待用户确认的更新建议
        "updated_at": None,
    }


def _report_digest(rec, max_chars=1500):
    """把一份 Research 压缩成给 LLM 的摘要文本（控制 token，避免超时/截断）。"""
    d = rec.get("data") or {}
    if not isinstance(d, dict):
        d = {}
    lines = [
        "【Research】id={}".format(rec.get("research_id") or rec.get("id") or ""),
        "主题：{}".format(rec.get("topic") or ""),
        "类型：{}｜形式：{}｜完成时间：{}".format(
            rec.get("research_type") or "other",
            rec.get("research_mode") or "standard",
            rec.get("generatedAt") or ""),
    ]
    s = (d.get("summary") or "").strip()
    if s:
        lines.append("摘要：" + s[:500])
    secs = d.get("sections") or {}
    if isinstance(secs, dict):
        for k, v in list(secs.items())[:14]:
            if not isinstance(v, dict):
                continue
            bit = "- {}：{}".format(k, (v.get("summary") or "").strip()[:180])
            for tb in (v.get("tables") or [])[:1]:
                head = tb.get("head") or []
                rows = (tb.get("rows") or [])[:3]
                if head and rows:
                    bit += " 表[{}] {}".format(
                        "|".join(str(h)[:12] for h in head[:5]),
                        " ; ".join(" / ".join(str(c)[:22] for c in row[:5]) for row in rows))
            for c in (v.get("callouts") or [])[:2]:
                bit += " ｜提示：" + str(c)[:110]
            lines.append(bit)
    return "\n".join(lines)[:max_chars]


def analyze_overview(product, overview, researches, llm):
    """基于若干份真实 Research，产出「综合总览更新建议」（不直接改写总览）。

    返回 pending_updates 列表：每项含 type(add/modify/conflict) + target + payload
    + source_research_ids，等待用户在产品主页确认后才写入正式内容。
    """
    import random

    pid = (product or {}).get("product_id", "")
    ov = overview if isinstance(overview, dict) else overview_skeleton(pid)
    ov.setdefault("findings", {})
    ov.setdefault("opportunities", [])
    ov.setdefault("risks", [])
    ov.setdefault("research_gaps", [])

    # —— 已有总览（供 LLM 判断重复/修改/冲突）——
    exist_lines = []
    for dim in OVERVIEW_DIM_KEYS:
        for f in (ov.get("findings") or {}).get(dim, []) or []:
            exist_lines.append("- [{}] id={} {}：{}".format(
                dim, f.get("id", ""), f.get("kind", "INSIGHT"), (f.get("text") or "")[:130]))
    exist_txt = "\n".join(exist_lines) if exist_lines else "（暂无已有结论）"
    eopp = "\n".join("- id={} {}".format(o.get("id", ""), (o.get("title") or "")[:80]) for o in (ov.get("opportunities") or [])) or "（暂无）"
    erisk = "\n".join("- id={} {}".format(r.get("id", ""), (r.get("title") or "")[:80]) for r in (ov.get("risks") or [])) or "（暂无）"
    egap = "\n".join("- id={} [{}/{}] {}".format(
        g.get("gap_id", ""), g.get("dimension", "other"), g.get("status", "未研究"), (g.get("title") or "")[:80])
        for g in (ov.get("research_gaps") or [])) or "（暂无）"

    rid_list, digests = [], []
    for rec in researches or []:
        rid_list.append(rec.get("research_id") or rec.get("id") or "")
        digests.append(_report_digest(rec))
    digests_txt = "\n\n".join(digests)
    if len(digests_txt) > 11000:
        digests_txt = digests_txt[:11000]

    prompt = (
        "你是「产品研究总览」分析助手。\n"
        "产品：{name}（{en}）\n类别：{cat}｜目标市场：{mkt}｜研究目的：{goal}\n产品说明：{desc}\n\n"
        "【已有综合总览·当前结论】\n{exist}\n\n"
        "【已有机会】\n{eopp}\n\n【已有风险】\n{erisk}\n\n【已有待验证问题】\n{egap}\n\n"
        "【本次纳入分析的 Research（共 {n} 份，research_id：{ids}）】\n{digests}\n\n"
        "请基于上述 Research 的真实内容，产出「综合总览更新建议」JSON（只提建议，不要直接改写总览）：\n"
        "{{\n"
        "  \"findings\":[{{\"dim\":\"mkt|ecom|usr|comp|tech|reg|sc|other\",\"kind\":\"FACT|INSIGHT\",\"text\":\"一条真正重要的结论（20-60字）\"}}],\n"
        "  \"finding_modifications\":[{{\"target_id\":\"已有结论id\",\"new_text\":\"修改后的结论\",\"reason\":\"修改原因\"}}],\n"
        "  \"conflicts\":[{{\"target_id\":\"已有结论id\",\"new_claim\":\"新研究中的说法\",\"note\":\"可能的差异原因（年份/统计口径/市场定义/数据源）\",\"suggest_gap\":\"建议新增的待验证问题标题\"}}],\n"
        "  \"opportunities\":[{{\"title\":\"机会标题\",\"description\":\"机会描述1-3句，说明依据\",\"confidence\":\"High|Medium|Low\",\"related_dimensions\":[\"tech\",\"usr\"]}}],\n"
        "  \"risks\":[{{\"title\":\"风险标题\",\"description\":\"风险描述1-3句\",\"severity\":\"High|Medium|Low\"}}],\n"
        "  \"research_gaps\":[{{\"title\":\"还没研究清楚的问题\",\"description\":\"为什么重要1-2句\",\"dimension\":\"mkt|ecom|usr|comp|tech|reg|sc|other\",\"priority\":\"High|Medium|Low\"}}]\n"
        "}}\n"
        "硬性规则：\n"
        "1. 只基于上面提供的 Research 内容，禁止编造数据；证据不足时不要硬写结论，改为写进 research_gaps。\n"
        "2. findings 每个领域最多 3-5 条，只写真正重要的，不要把所有报告压缩成长摘要。\n"
        "3. 与已有结论重复的不要重复提；需要修正的放 finding_modifications；明显矛盾的放 conflicts（不得直接覆盖旧结论）。\n"
        "4. FACT = 研究中可直接引用的事实/数据；INSIGHT = 基于研究的判断/推论，推论必须能被上面的内容支撑。\n"
        "5. confidence/severity/priority 只能取 High/Medium/Low，证据不足一律 Low。\n"
        "6. 只输出 JSON 对象，不要解释文字、不要 markdown 代码块。\n"
    ).format(
        name=(product or {}).get("name") or "该产品",
        en=(product or {}).get("name_en") or "",
        cat=(product or {}).get("category") or "未填写",
        mkt="、".join((product or {}).get("target_market") or []) or "未填写",
        goal=(product or {}).get("research_goal") or "未填写",
        desc=(product or {}).get("description") or "无",
        exist=exist_txt, eopp=eopp, erisk=erisk, egap=egap,
        n=len(researches or []), ids=",".join(rid_list), digests=digests_txt,
    )

    payload = {
        "model": llm["model"],
        "messages": [
            {"role": "system", "content": "你是产品研究总览分析助手，输出严格 JSON。数据诚实：只基于给定研究内容，禁止编造。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    req = urllib.request.Request(
        llm["base"].rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": "Bearer " + llm["key"], "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        content = json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"]
    res = _extract_json(content)
    if not isinstance(res, dict):
        res = {}

    now = now_beijing()
    pending = []

    def _push(t, target, payload_obj):
        pending.append({
            "id": _uid("pu"), "type": t, "target": target, "payload": payload_obj,
            "source_research_ids": list(rid_list), "created_at": now, "status": "pending",
        })

    for f in (res.get("findings") or [])[:24]:
        dim = f.get("dim") if f.get("dim") in OVERVIEW_DIM_KEYS else "other"
        text = (f.get("text") or "").strip()
        if not text:
            continue
        kind = (f.get("kind") or "INSIGHT").upper()
        if kind not in ("FACT", "INSIGHT"):
            kind = "INSIGHT"
        _push("add", "finding", {"dim": dim, "kind": kind, "text": text})

    for m in (res.get("finding_modifications") or [])[:12]:
        if not m.get("target_id") or not (m.get("new_text") or "").strip():
            continue
        _push("modify", "finding", {
            "target_id": m.get("target_id"),
            "new_text": (m.get("new_text") or "").strip(),
            "reason": (m.get("reason") or "").strip(),
        })

    for c in (res.get("conflicts") or [])[:12]:
        if not c.get("target_id"):
            continue
        _push("conflict", "finding", {
            "target_id": c.get("target_id"),
            "new_claim": (c.get("new_claim") or "").strip(),
            "note": (c.get("note") or "").strip(),
            "suggest_gap": (c.get("suggest_gap") or "").strip(),
        })

    for o in (res.get("opportunities") or [])[:10]:
        title = (o.get("title") or "").strip()
        if not title:
            continue
        conf = o.get("confidence") if o.get("confidence") in OVERVIEW_CONFIDENCE else "Low"
        dims = [d for d in (o.get("related_dimensions") or []) if d in OVERVIEW_DIM_KEYS][:4]
        _push("add", "opportunity", {
            "title": title, "description": (o.get("description") or "").strip(),
            "confidence": conf, "related_dimensions": dims, "status": "待验证",
        })

    for r in (res.get("risks") or [])[:10]:
        title = (r.get("title") or "").strip()
        if not title:
            continue
        sev = r.get("severity") if r.get("severity") in OVERVIEW_SEVERITY else "Low"
        _push("add", "risk", {
            "title": title, "description": (r.get("description") or "").strip(),
            "severity": sev, "status": "待验证",
        })

    for g in (res.get("research_gaps") or [])[:12]:
        title = (g.get("title") or "").strip()
        if not title:
            continue
        dim = g.get("dimension") if g.get("dimension") in OVERVIEW_DIM_KEYS else "other"
        pri = g.get("priority") if g.get("priority") in OVERVIEW_PRIORITY else "Low"
        _push("add", "gap", {
            "title": title, "description": (g.get("description") or "").strip(),
            "dimension": dim, "priority": pri, "status": "未研究",
        })
    return pending


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
            self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        # 预检请求（CORS）
        self._send(204, "", cors=True)

    def _token_valid(self):
        """校验请求携带的 token 是否有效（Authorization Bearer 或 ?token=）。"""
        rd_token = os.environ.get("RD_TOKEN")
        if not rd_token:
            return True  # 未启用鉴权时视为有效
        try:
            auth = self.headers.get("Authorization", "")
            q_token = ""
            if "?" in self.path:
                from urllib.parse import parse_qs
                q_token = parse_qs(self.path.split("?", 1)[1]).get("token", [""])[0]
            if auth.replace("Bearer ", "") == rd_token or q_token == rd_token:
                return True
        except Exception:
            pass
        return False

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
                "researchTypes": {k: {"title": v["title"], "icon": v["icon"], "desc": v["desc"], "modules": v["modules"], "dims": v["dims"]} for k, v in RESEARCH_TYPES.items()},
                "cloudReports": bool(os.environ.get("GITHUB_TOKEN")),
                "cloudProducts": bool(os.environ.get("GITHUB_TOKEN")),
                # v1.9.0：门禁验证——请求带有效 token 时为 true（供前端登录墙判断）
                "authValid": self._token_valid(),
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
            # v2.1.0：支持 ?product_id=xxx 过滤（产品主页按产品拉报告）
            from urllib.parse import parse_qs, urlsplit
            pid = parse_qs(urlsplit(self.path).query).get("product_id", [""])[0]
            if pid:
                content = [r for r in (content or []) if r.get("product_id") == pid]
            self._send(200, {"reports": content if content else []})
        elif _path == "/api/products":
            # 产品研究库列表（需 token；未配 GITHUB_TOKEN 时返回空列表，前端回退本地）
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
                content, _sha = gh_get_json(PRODUCTS_PATH)
            except Exception as e:
                self._send(500, {"error": "读取云端产品失败: {}".format(e)})
                return
            self._send(200, {"products": content if content else []})
        elif _path == "/api/overviews":
            # v2.2.0：产品综合研究总览（按 product_id 一份）
            if not self._token_valid():
                self._send(401, {"error": "未授权：缺少有效 token。"})
                return
            try:
                content, _sha = gh_get_json(OVERVIEWS_PATH)
            except Exception as e:
                self._send(500, {"error": "读取云端总览失败: {}".format(e)})
                return
            ovs = content if isinstance(content, dict) else {}
            from urllib.parse import parse_qs, urlsplit
            pid = parse_qs(urlsplit(self.path).query).get("product_id", [""])[0]
            if pid:
                self._send(200, {"overview": ovs.get(pid) or overview_skeleton(pid)})
            else:
                self._send(200, {"overviews": ovs})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        _path = self.path.split("?")[0]
        if _path == "/api/research":
            # —— 极简 token 鉴权（公网暴露前必须开启）——
            rd_token = os.environ.get("RD_TOKEN")
            auth_key = None
            if rd_token:
                auth = self.headers.get("Authorization", "")
                q_token = ""
                if "?" in self.path:
                    from urllib.parse import parse_qs
                    q_token = parse_qs(self.path.split("?", 1)[1]).get("token", [""])[0]
                if auth.replace("Bearer ", "") != rd_token and q_token != rd_token:
                    self._send(401, {"error": "未授权：缺少有效 token。请在请求头带 Authorization: Bearer <RD_TOKEN>，或部署时移除 RD_TOKEN 关闭鉴权。"})
                    return
                auth_key = "tok:" + rd_token
            # v1.7.0：限流（token 维度 + IP 兜底）
            ip_key = "ip:" + (self.headers.get("X-Forwarded-For", "").split(",")[0].strip() or "unknown")
            if not _check_rate(auth_key or ip_key):
                self._send(429, {"error": "请求过于频繁，请稍后再试（限流保护）。"})
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
            mode = payload.get("mode", "standard")   # v2.0: standard/topic/comprehensive/advanced/研究类型id
            question = payload.get("question", "")   # v2.0: 专题调研问题
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
            result = build_report(topic, dims, source=source, llm=llm, mode=mode, question=question)
            # v2.2.1 断点保护：生成完成后自动归档为「草稿」（draft:true）。
            # 前端正常收到结果后 saveReport 会以同 id 覆盖为正式记录；若前端刷新/断线，
            # 草稿留在云端，下次打开调研台由前端检测并提示「恢复并正式归档」。
            if isinstance(result, dict):
                try:
                    _auto_archive(payload, result)
                except Exception:
                    pass
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
            # v1.7.0：大体积报告自动精简（>80KB 只存摘要/维度/KPI，防仓库膨胀）
            MAX_DATA = int(os.environ.get("RD_MAX_REPORT_KB", "80")) * 1024
            data = report.get("data")
            if isinstance(data, dict):
                raw_size = len(json.dumps(data, ensure_ascii=False).encode("utf-8"))
                if raw_size > MAX_DATA:
                    trimmed = {
                        "topic": data.get("topic", report.get("topic")),
                        "mode": data.get("mode"),
                        "generatedAt": data.get("generatedAt"),
                        "summary": data.get("summary", ""),
                        "kpis": data.get("kpis", [])[:8],
                        "trimmed": True,
                        "sections": {k: {"summary": v.get("summary", ""), "kpis": (v.get("kpis") or [])[:4]}
                                     for k, v in (data.get("sections") or {}).items()},
                    }
                    report["data"] = trimmed
                    report["trimmed"] = True
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
        elif _path == "/api/products":
            # 保存/更新产品（v2.1.0：按 product_id upsert）
            rd_token = os.environ.get("RD_TOKEN")
            if rd_token:
                auth = self.headers.get("Authorization", "")
                q_token = ""
                if "?" in self.path:
                    from urllib.parse import parse_qs
                    q_token = parse_qs(self.path.split("?", 1)[1]).get("token", [""])[0]
                if auth.replace("Bearer ", "") != rd_token and q_token != rd_token:
                    self._send(401, {"error": "未授权：缺少有效 token。"})
                    return
            if not os.environ.get("GITHUB_TOKEN"):
                self._send(500, {"error": "后端未配置 GITHUB_TOKEN（环境变量）。请联系站长开启云端产品库。"})
                return
            try:
                length = int(self.headers.get("Content-Length", 0) or 0)
                body = self.rfile.read(length) if length else b"{}"
                payload = json.loads(body.decode("utf-8"))
            except Exception as e:
                self._send(400, {"error": "bad request: {}".format(e)})
                return
            product = payload.get("product")
            if not product or not isinstance(product, dict) or not product.get("product_id") or not product.get("name"):
                self._send(400, {"error": "缺少 product 对象（需含 product_id 与 name）"})
                return
            try:
                content, sha = gh_get_json(PRODUCTS_PATH)
                if content is None or not isinstance(content, list):
                    content = []
                pid = product.get("product_id")
                content = [p for p in content if p.get("product_id") != pid]
                content.insert(0, product)
                content = content[:200]
                gh_save_json(PRODUCTS_PATH, content, sha)
            except Exception as e:
                self._send(500, {"error": "保存云端产品失败: {}".format(e)})
                return
            self._send(200, {"ok": True, "id": product.get("product_id"), "count": len(content)})
        elif _path == "/api/overviews":
            # v2.2.0：保存产品综合研究总览（按 product_id upsert）
            if not self._token_valid():
                self._send(401, {"error": "未授权：缺少有效 token。"})
                return
            if not os.environ.get("GITHUB_TOKEN"):
                self._send(500, {"error": "后端未配置 GITHUB_TOKEN（环境变量）。请联系站长开启云端总览。"})
                return
            try:
                length = int(self.headers.get("Content-Length", 0) or 0)
                body = self.rfile.read(length) if length else b"{}"
                payload = json.loads(body.decode("utf-8"))
            except Exception as e:
                self._send(400, {"error": "bad request: {}".format(e)})
                return
            ov = payload.get("overview")
            if not ov or not isinstance(ov, dict) or not ov.get("product_id"):
                self._send(400, {"error": "缺少 overview 对象（需含 product_id）"})
                return
            try:
                content, sha = gh_get_json(OVERVIEWS_PATH)
                if not isinstance(content, dict):
                    content = {}
                pid = ov.get("product_id")
                ov = dict(ov)
                ov["updated_at"] = now_beijing()
                content[pid] = ov
                gh_save_json(OVERVIEWS_PATH, content, sha)
            except Exception as e:
                self._send(500, {"error": "保存云端总览失败: {}".format(e)})
                return
            self._send(200, {"ok": True, "id": pid, "count": len(content)})
        elif _path == "/api/overview/suggest":
            # v2.2.0：分析 Research → 生成「综合总览更新建议」（不直接改总览，等用户确认）
            if not self._token_valid():
                self._send(401, {"error": "未授权：缺少有效 token。"})
                return
            if not os.environ.get("GITHUB_TOKEN"):
                self._send(500, {"error": "后端未配置 GITHUB_TOKEN（环境变量）。"})
                return
            if not LLM_KEY:
                self._send(400, {"error": "后端未配置 LLM Key，无法生成总览建议。"})
                return
            try:
                length = int(self.headers.get("Content-Length", 0) or 0)
                body = self.rfile.read(length) if length else b"{}"
                payload = json.loads(body.decode("utf-8"))
            except Exception as e:
                self._send(400, {"error": "bad request: {}".format(e)})
                return
            pid = payload.get("product_id") or ""
            if not pid:
                self._send(400, {"error": "缺少 product_id"})
                return
            only_ids = payload.get("research_ids") or []
            try:
                products, _ps = gh_get_json(PRODUCTS_PATH)
                reports, _rs = gh_get_report_file()
                ovs, osha = gh_get_json(OVERVIEWS_PATH)
            except Exception as e:
                self._send(500, {"error": "读取云端数据失败: {}".format(e)})
                return
            product = None
            for p in (products or []):
                if isinstance(p, dict) and p.get("product_id") == pid:
                    product = p
                    break
            if not product:
                self._send(404, {"error": "未找到该产品：{}".format(pid)})
                return
            ovs = ovs if isinstance(ovs, dict) else {}
            overview = ovs.get(pid) or overview_skeleton(pid)
            # 该产品下的 Research（可限定只分析新完成的几份）
            rs = [r for r in (reports or []) if isinstance(r, dict) and r.get("product_id") == pid]
            if only_ids:
                rs = [r for r in rs if (r.get("research_id") or r.get("id")) in only_ids]
            if not rs:
                self._send(400, {"error": "该产品下还没有可分析的 Research。"})
                return
            llm = {"key": LLM_KEY, "base": LLM_BASE, "model": LLM_MODEL}
            try:
                pending = analyze_overview(product, overview, rs, llm)
            except Exception as e:
                self._send(500, {"error": "生成总览建议失败: {}".format(e)})
                return
            # 去重：同 target + 同内容 且仍为 pending 的建议不重复加入
            exist = [u for u in (overview.get("pending_updates") or []) if u.get("status") == "pending"]
            def _key(u):
                p = u.get("payload") or {}
                return (u.get("type"), u.get("target"), str(p.get("text") or p.get("new_text") or p.get("title") or p.get("new_claim") or ""))
            known = set(_key(u) for u in exist)
            added = []
            for u in pending:
                if _key(u) in known:
                    continue
                known.add(_key(u))
                added.append(u)
            overview = dict(overview)
            overview["pending_updates"] = exist + added
            overview["updated_at"] = now_beijing()
            ovs[pid] = overview
            try:
                gh_save_json(OVERVIEWS_PATH, ovs, osha)
            except Exception as e:
                self._send(500, {"error": "保存待确认更新失败: {}".format(e)})
                return
            self._send(200, {"ok": True, "added": len(added), "pending": overview["pending_updates"]})
        elif _path == "/api/overview/confirm":
            # v2.2.0：用户确认/忽略一条「综合总览更新建议」（accept → 写入正式内容；ignore → 丢弃）
            if not self._token_valid():
                self._send(401, {"error": "未授权：缺少有效 token。"})
                return
            if not os.environ.get("GITHUB_TOKEN"):
                self._send(500, {"error": "后端未配置 GITHUB_TOKEN（环境变量）。"})
                return
            try:
                length = int(self.headers.get("Content-Length", 0) or 0)
                body = self.rfile.read(length) if length else b"{}"
                payload = json.loads(body.decode("utf-8"))
            except Exception as e:
                self._send(400, {"error": "bad request: {}".format(e)})
                return
            pid = payload.get("product_id") or ""
            uid = payload.get("update_id") or ""
            action = payload.get("action") or "accept"   # accept / ignore
            if not pid or not uid:
                self._send(400, {"error": "缺少 product_id 或 update_id"})
                return
            try:
                ovs, osha = gh_get_json(OVERVIEWS_PATH)
            except Exception as e:
                self._send(500, {"error": "读取云端总览失败: {}".format(e)})
                return
            ovs = ovs if isinstance(ovs, dict) else {}
            ov = ovs.get(pid)
            if not isinstance(ov, dict):
                self._send(404, {"error": "该产品还没有综合总览。"})
                return
            updates = ov.get("pending_updates") or []
            upd = next((u for u in updates if u.get("id") == uid), None)
            if not upd:
                self._send(404, {"error": "未找到该更新建议（可能已被处理）。"})
                return
            if upd.get("status") != "pending":
                self._send(400, {"error": "该建议已处理（status={}）。".format(upd.get("status"))})
                return
            now = now_beijing()
            src_ids = list(upd.get("source_research_ids") or [])
            p = upd.get("payload") or {}
            applied = False
            note = ""
            if action == "ignore":
                upd["status"] = "ignored"
                upd["decided_at"] = now
                note = "已忽略"
            else:
                t, target = upd.get("type"), upd.get("target")
                if t == "add":
                    if target == "finding":
                        dim = p.get("dim") if p.get("dim") in OVERVIEW_DIM_KEYS else "other"
                        arr = ov.setdefault("findings", {}).setdefault(dim, [])
                        arr.append({
                            "id": _uid("f"),
                            "kind": (p.get("kind") or "INSIGHT") if (p.get("kind") or "INSIGHT") in ("FACT", "INSIGHT") else "INSIGHT",
                            "text": p.get("text") or "",
                            "source_research_ids": src_ids,
                            "created_at": now, "updated_at": now,
                        })
                        applied = True
                    elif target == "opportunity":
                        ov.setdefault("opportunities", []).append({
                            "id": _uid("o"),
                            "title": p.get("title") or "",
                            "description": p.get("description") or "",
                            "source_research_ids": src_ids,
                            "related_dimensions": p.get("related_dimensions") or [],
                            "confidence": p.get("confidence") if p.get("confidence") in OVERVIEW_CONFIDENCE else "Low",
                            "status": p.get("status") or "待验证",
                            "created_at": now, "updated_at": now,
                        })
                        applied = True
                    elif target == "risk":
                        ov.setdefault("risks", []).append({
                            "id": _uid("rk"),
                            "title": p.get("title") or "",
                            "description": p.get("description") or "",
                            "severity": p.get("severity") if p.get("severity") in OVERVIEW_SEVERITY else "Low",
                            "source_research_ids": src_ids,
                            "status": p.get("status") or "待验证",
                            "created_at": now, "updated_at": now,
                        })
                        applied = True
                    elif target == "gap":
                        ov.setdefault("research_gaps", []).append({
                            "gap_id": _uid("g"),
                            "title": p.get("title") or "",
                            "description": p.get("description") or "",
                            "dimension": p.get("dimension") if p.get("dimension") in OVERVIEW_DIM_KEYS else "other",
                            "priority": p.get("priority") if p.get("priority") in OVERVIEW_PRIORITY else "Low",
                            "status": p.get("status") or "未研究",
                            "source_research_ids": src_ids,
                            "created_at": now, "updated_at": now,
                        })
                        applied = True
                elif t == "modify" and target == "finding":
                    # 修改：替换已有结论文本（保留原 id 与历史来源，追加新来源）
                    target_id = p.get("target_id") or ""
                    done = False
                    for dim, arr in (ov.get("findings") or {}).items():
                        for f in arr:
                            if f.get("id") == target_id:
                                old = f.get("text") or ""
                                f["text"] = p.get("new_text") or old
                                f["updated_at"] = now
                                f["replaced_from"] = old
                                merged = list(set((f.get("source_research_ids") or []) + src_ids))
                                f["source_research_ids"] = sorted(merged)
                                done = True
                                break
                        if done:
                            break
                    if done:
                        applied = True
                    else:
                        note = "未找到目标结论（可能已被修改），建议已标记忽略"
                        upd["status"] = "ignored"
                elif t == "conflict" and target == "finding":
                    # 冲突：不覆盖旧结论，旧结论加冲突标注；可同时产生新 Gap（重新核验）
                    target_id = p.get("target_id") or ""
                    done = False
                    for dim, arr in (ov.get("findings") or {}).items():
                        for f in arr:
                            if f.get("id") == target_id:
                                f.setdefault("conflicts", []).append({
                                    "new_claim": p.get("new_claim") or "",
                                    "note": p.get("note") or "",
                                    "source_research_ids": src_ids,
                                    "created_at": now,
                                })
                                f["updated_at"] = now
                                done = True
                                break
                        if done:
                            break
                    if done:
                        applied = True
                    else:
                        note = "未找到目标结论，冲突标注未生效"
                    sg = (p.get("suggest_gap") or "").strip()
                    if sg:
                        ov.setdefault("research_gaps", []).append({
                            "gap_id": _uid("g"),
                            "title": sg,
                            "description": "由研究结论冲突产生，需重新核验：{}".format((p.get("note") or "").strip()),
                            "dimension": "mkt",
                            "priority": "High",
                            "status": "未研究",
                            "source_research_ids": src_ids,
                            "created_at": now, "updated_at": now,
                        })
                else:
                    note = "未知建议类型（{} / {}），已标记忽略".format(t, target)
                    upd["status"] = "ignored"
            if action == "accept" and applied:
                upd["status"] = "accepted"
                upd["decided_at"] = now
            ov["pending_updates"] = updates
            ov["updated_at"] = now
            ovs[pid] = ov
            try:
                gh_save_json(OVERVIEWS_PATH, ovs, osha)
            except Exception as e:
                self._send(500, {"error": "保存总览失败: {}".format(e)})
                return
            self._send(200, {"ok": True, "update_id": uid, "status": upd.get("status"), "applied": applied, "note": note})
        else:
            self._send(404, {"error": "not found"})

    def do_DELETE(self):
        """删除云端报告：DELETE /api/reports?id=<reportId>  （需 token）"""
        _path = self.path.split("?")[0]
        if _path not in ("/api/reports", "/api/products"):
            self._send(404, {"error": "not found"})
            return
        rd_token = os.environ.get("RD_TOKEN")
        if rd_token:
            auth = self.headers.get("Authorization", "")
            q_token = ""
            from urllib.parse import parse_qs, urlsplit
            qs = parse_qs(urlsplit(self.path).query)
            q_token = qs.get("token", [""])[0]
            if auth.replace("Bearer ", "") != rd_token and q_token != rd_token:
                self._send(401, {"error": "未授权：缺少有效 token。请在请求头带 Authorization: Bearer <RD_TOKEN>，或部署时移除 RD_TOKEN 关闭鉴权。"})
                return
        if not os.environ.get("GITHUB_TOKEN"):
            self._send(500, {"error": "后端未配置 GITHUB_TOKEN（环境变量）。请联系站长开启云端报告。"})
            return
        from urllib.parse import parse_qs, urlsplit, unquote
        rid = unquote(parse_qs(urlsplit(self.path).query).get("id", [""])[0])
        if not rid:
            self._send(400, {"error": "缺少 id 参数"})
            return
        try:
            if _path == "/api/products":
                content, sha = gh_get_json(PRODUCTS_PATH)
                if content is None or not isinstance(content, list):
                    content = []
                before = len(content)
                content = [p for p in content if p.get("product_id") != rid]
                gh_save_json(PRODUCTS_PATH, content, sha)
                self._send(200, {"ok": True, "deleted": before - len(content), "count": len(content)})
                return
            content, sha = gh_get_report_file()
            if content is None:
                content = []
            if not isinstance(content, list):
                content = []
            before = len(content)
            content = [r for r in content if r.get("id") != rid]
            gh_save_report_file(content, sha)
        except Exception as e:
            self._send(500, {"error": "删除云端报告失败: {}".format(e)})
            return
        self._send(200, {"ok": True, "deleted": before - len(content), "count": len(content)})

    def log_message(self, *args):
        pass  # 静默日志


# ---------------------------------------------------------------------------
# 云端报告存储（GitHub Contents API）
# 报告保存到仓库 research-deck/saved/reports.json，任何设备登录后可见。
# 需要环境变量 GITHUB_TOKEN（fine-grained PAT，仓库 Contents 读写）。
# ---------------------------------------------------------------------------
REPORTS_PATH = os.environ.get("RD_REPORTS_PATH", "research-deck/saved/reports.json")
PRODUCTS_PATH = os.environ.get("RD_PRODUCTS_PATH", "research-deck/saved/products.json")
# v2.2.0：产品综合研究总览（Product Research Overview），按 product_id 存一份
OVERVIEWS_PATH = os.environ.get("RD_OVERVIEWS_PATH", "research-deck/saved/overviews.json")
GITHUB_API = "https://api.github.com"
GITHUB_REPO = os.environ.get("GITHUB_REPO", "Aurillis/database")


def _gh_headers():
    tok = os.environ.get("GITHUB_TOKEN", "")
    return {
        "Authorization": "Bearer " + tok,
        "Accept": "application/vnd.github+json",
        "User-Agent": "researchdeck-scf",
    }


def gh_get_json(gh_path):
    """通用：读取远端 JSON 文件，返回 (content_json, sha)；不存在返回 (None, None)。"""
    tok = os.environ.get("GITHUB_TOKEN", "")
    if not tok:
        return None, None
    url = "{}/repos/{}/contents/{}".format(GITHUB_API, GITHUB_REPO, gh_path)
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


def gh_save_json(gh_path, content, sha):
    """通用：把整个 JSON 写回远端（带 sha 条件更新）。返回 True/抛异常。"""
    tok = os.environ.get("GITHUB_TOKEN", "")
    import base64
    body = {
        "message": "researchdeck: update saved data",
        "content": base64.b64encode(json.dumps(content, ensure_ascii=False).encode("utf-8")).decode("ascii"),
    }
    if sha:
        body["sha"] = sha
    url = "{}/repos/{}/contents/{}".format(GITHUB_API, GITHUB_REPO, gh_path)
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers=_gh_headers(), method="PUT")
    with urllib.request.urlopen(req, timeout=20) as r:
        r.read()
    return True


def gh_get_report_file():
    """读取远端 reports.json，返回 (content_json, sha)；不存在返回 (None, None)。"""
    return gh_get_json(REPORTS_PATH)


def gh_save_report_file(content, sha):
    """把整个 reports.json 写回远端（带 sha 条件更新）。返回 True/抛异常。"""
    return gh_save_json(REPORTS_PATH, content, sha)


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
                "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
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
        elif method == "DELETE":
            fake.do_DELETE()
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
