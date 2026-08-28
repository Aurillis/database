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
- 未设置 key 时自动进入 demo 模式：用内置真实数据（哺乳按摩器）+ 通用框架骨架生成，
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
    "amz_us": {"title": "亚马逊美国·盆底肌训练器", "icon": "🇺🇸",
               "badge": "固定模板 · 卖家精灵 MCP", "template": True},
    "amz_eu": {"title": "亚马逊欧洲·盆底肌修复仪", "icon": "🇪🇺",
               "badge": "固定模板 · 卖家精灵 MCP", "template": True},
}

# ---------------------------------------------------------------------------
# 固定模板定义（Amazon US / EU 盆底肌看板结构）
# 这两条维度的输出结构被固定，不随主题漂移。见 AMZ_US_TEMPLATE / AMZ_EU_TEMPLATE
# ---------------------------------------------------------------------------
AMZ_US_TEMPLATE = """【固定模板 · 亚马逊美国站 · 盆底肌训练器（Bladder Control Devices）机会评分看板】
必须严格按以下模块结构产出，不得增删模块、不得改变表头顺序（结构与「US Bladder Control Devices 盆底肌训练器机会评分看板」完全一致）：

· KPI（8 个，顺序固定）：机会评分 / 风险评分 / 候选ASIN→核心ASIN / 样本月销量(件) / 样本月销售额 / 加权成交价 / Top类型 / Top品牌

· 表1「核心指标」表头：核心指标 | 数值 | 说明
  行（固定）：候选→核心产品(ASIN数) / 样本月销量·销售额 / 加权成交价 / Top 类型 / Top 品牌 / Top5 品牌销售额占比(含销量占比) / 平均评分 / 新品(数量·均销额) / Amazon 自营参与

· 表2「产品类型销售额结构」表头：产品类型 | ASIN数 | 销量 | 销售额 | 均价 | 评分
  行（按销售额降序，覆盖全部类型）：EMS电刺激训练器 / 扩张器·硅胶套装 / App·生物反馈训练器 / Kegel负重训练器 / 多功能激活训练器 / 盆底按摩棒

· 表3「品牌销售额 Top10」表头：品牌 | ASIN数 | 销量 | 销售额 | 均价
  行（按销售额降序，固定 10 行）

· 表4「头部品牌产品路线」表头：品牌 | 主打类型 | 价格带 | 打法
  行（覆盖看板品牌策略）：Intimate Rose / Perifit / K-fit / iSTIM / Mumvia / QoQiu 等

· 表5「关键词市场需求」表头：关键词 | 分类 | 月搜索 | 月购买 | 购买率 | 竞价 | 供需比 | 垄断点击率
  行（覆盖五类）：核心训练词 / Kegel负重词 / 扩张·放松词 / 电子训练词 / 品牌·产品词

· 表6「关键词趋势与 PPC」表头：关键词 | 分类 | 最新搜索 | 同比趋势 | PPC竞价
  行：核心词历史搜索趋势（标注增长/下降 %）

· 表7「价格带销售额」表头：价格带 | ASIN数 | 销量 | 销售额
  行（固定五档）：<$30 / $30-60 / $60-120 / $120-200 / $200+

· 表8「目标场景 / 核心痛点」表头：目标场景 | 覆盖产品类型 | 核心痛点 | ASIN数 | 销量 | 销售额
  行（覆盖）：产后/盆底肌力量恢复 / 轻中度漏尿·膀胱控制 / 紧张·疼痛·放松理疗 / 入门自我训练

· 表9「功能/属性热度」表头：功能/属性 | 涉及ASIN数 | 说明
  行（覆盖）：App连接·可视化反馈 / EMS电刺激 / 分阶重量·尺寸 / 硅胶材质 / 触发点·放松

· 表10「十维机会评分」表头：十维机会评分 | 分数 | 要点
  行（固定十个维度，顺序不可变）：市场容量 / 增长想象空间 / 竞争集中度 / 价格承接 / 评分壁垒 / 产品差异化 / 进入门槛 / 内容教育价值 / 复购组合 / 综合机会

· callouts（固定五条线索）：①关键词市场解读 ②价格与销售额机会矩阵 ③产品定义启发（优先/可测/谨慎）④最终建议与验证清单 ⑤机会点 / 主要风险 / 进入建议。结尾附加数据诚实声明（区分卖家精灵实测字段 vs 语义分类字段）"""

AMZ_EU_TEMPLATE = """【固定模板 · 亚马逊欧洲站 EU5 · 盆底肌修复仪市场看板】
必须严格按以下模块结构产出，不得增删模块、不得改变表头顺序：

· KPI（4 个，顺序固定）：机会评分 / 风险评分 / 五国月销量(件) / 总销售额

· 表1「核心指标」表头：核心指标 | 数值 | 说明
  行（固定）：五国月销量·销售额 / 平均售价 / ASIN数(去重) / Top5 品牌(销量·销售额占比) / 最大国家 / 最大细分

· 表2「五国概览」表头：五国概览 | ASIN | 销量占比 | 销售额占比 | 均价
  行（固定五国，按销量降序）：德国 / 英国 / 法国 / 西班牙 / 意大利

· 表3「产品类型」表头：产品类型 | 销量 | 占比 | ASIN数 | 销售额
  行（固定六类）：电刺激 EMS·TENS / Kegel球·阴道锥 / 生物反馈·App主动训练 / 盆底疼痛按摩·触发点 / 扩张器·产前训练 / 智能震动Kegel球

· 表4「价格带」表头：价格带 | ASIN | 销量占比 | 销售额占比 | 均价
  行（固定五档）：0–20 / 20–40 / 40–70 / 70–120 / 120+

· callouts（固定四条线索）：①欧洲整体市场(全渠道)规模与 CAGR ②关键词热度与 PPC ③MDR/医疗宣称合规风险 ④结论（进入 / 观望 / 放弃）"""

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
def demo_lactation():
    """哺乳按摩器（真实地面真值数据）的演示报告骨架。"""
    return {
        "summary": (
            "哺乳按摩器（lactation massager）在亚马逊美国站是一个 <b>高度集中但仍在增长</b> 的品类："
            "130 个 ASIN、58 个品牌，CR5 高达 72.05%，头部三强合计占据 93.1% 份额。地面真值 25 个月累计销量 "
            "<b>309,966 件 / $10,950,087.71</b>，整体趋势 <b>+16.3%</b> 增长。品类已呈「赢家通吃」格局，"
            "新进入者正面硬刚头部胜算极低，但「加热/冷敷」「多功能组合」「特定人群」仍有空白窗口。"
        ),
        "kpis": [
            {"v": "130", "l": "在售 ASIN 数"},
            {"v": "58", "l": "参与品牌数"},
            {"v": "72.05%", "l": "CR5 集中度"},
            {"v": "+16.3%", "l": "25月销量趋势"},
        ],
        "sections": {
            "mkt": {
                "note": "数据口径：将 lactation/breast massager 视为统一市场（不拆分 Breastfeeding 与 Electric Breast Pumps），行级求和不去重。",
                "kpis": [
                    {"v": "309,966", "l": "地面真值总量(件)"},
                    {"v": "$10.95M", "l": "地面真值金额"},
                    {"v": "90.06%", "l": "CR10 集中度"},
                    {"v": "93.1%", "l": "头部三强合计"},
                ],
                "tables": [{
                    "head": ["指标", "数值", "解读"],
                    "rows": [
                        ["ASIN / 品牌数", "130 / 58", "品类窄但品牌多，长尾分散"],
                        ["CR5 / CR10", "72.05% / 90.06%", "<span class='pill r'>高度集中</span>"],
                        ["头部三强份额", "Momcozy 53.4% · Frida 23.2% · LaVie 16.5%", "三寡头垄断，新品牌难突围"],
                        ["月度跟踪跨度", "2024-06 → 2026-06（25 个月连续）", "2025-04/05 为采集缺口，非真实下滑"],
                        ["整体趋势", "+16.3% 增长", "修正此前 −21.9% 误判（月后缀 .1=10月 bug）"],
                    ],
                }],
                "callouts": ["<b>关键事实核查：</b>趋势曾因 SellerSprite 月标记 .1=10月 的尾零省略规则被误读为下降，已通过地面真值逐月核对纠正为 +16.3% 增长。结论必须经一手数据交叉验证。"],
                "summary": "高度集中但增长的市场，正面硬刚头部无意义，细分功能有窗口。",
            },
            "usr": {
                "note": "采用递进式收集策略：全景概览 → 分平台深入 → 追问关联。",
                "kpis": [],
                "tables": [{
                    "head": ["类别", "核心内容"],
                    "rows": [
                        ["核心痛点(高频)", "堵奶/乳腺炎时力度不足、形状不贴合；续航短、Micro-USB 老旧；噪音大；硅胶异味/清洁死角；与吸奶器协同繁琐"],
                        ["未被满足需求", "温热+振动组合缓解硬块；剖腹产/卧床免手持设计；消毒收纳一体化；家人可操作的简化指引"],
                    ],
                }],
                "callouts": ["拓展线索：r/Prostatitis 等男性健康社群中「盆底肌训练器用于前列腺炎辅助」的讨论，提示跨人群复用可能。"],
                "summary": "痛点集中在贴合/加热/免手持，存在明确功能空白。",
            },
            "prod": {
                "note": "方法论：覆盖多型号硬件参数横向对比（形态/加热/振动/续航/材质/防水）。",
                "kpis": [],
                "tables": [{
                    "head": ["维度", "主流方案", "缺口 / 机会"],
                    "rows": [
                        ["形态", "鹅蛋形 / 环形 / 泪滴形", "免手持 / 贴合穿戴仍稀缺"],
                        ["加热", "多数无；少数恒温 40℃", "<span class='pill w'>加热型严重不足</span>"],
                        ["振动", "3–9 档，单一频率", "可调频 / 脉冲式空白"],
                        ["续航", "1.5–3h，Micro-USB 居多", "USB-C + 长续航是差异化点"],
                        ["材质", "食品级硅胶", "可替换软头 / 抗菌涂层未普及"],
                    ],
                }],
                "callouts": ["参数盘点应细化到单 SKU 级（如拾光 SP1/SP2/SP3、澜渟、麻麻康等），形成横向对比总表。"],
                "summary": "加热与免手持是最大硬件代差机会。",
            },
            "comp": {
                "note": "定位 / 定价 / 功能对比。",
                "kpis": [],
                "tables": [{
                    "head": ["品牌", "份额", "定价", "定位", "弱点(可乘之机)"],
                    "rows": [
                        ["Momcozy", "53.4%", "$25–39", "全场景母婴生态", "产品线广但单品创新放缓"],
                        ["Frida Mom", "23.2%", "$32–45", "高端护理仪式感", "价格高、功能偏传统"],
                        ["LaVie", "16.5%", "$20–30", "性价比 / 套装", "品牌声量弱"],
                        ["其他长尾", "~7%", "$15–25", "白牌/贴牌", "无品牌资产，价格战"],
                    ],
                }],
                "callouts": ["<b>进入策略：</b>建议以「加热 + 免手持」功能差异化切入细分人群，而非价格战。"],
                "summary": "头部靠生态与品牌，新玩家宜做功能差异化。",
            },
            "tech": {
                "note": "对标成人胸部产品工程能力（如 We-Vibe Temp 的 Peltier TEC 方案），评估迁移可行性。",
                "kpis": [],
                "tables": [{
                    "head": ["技术路线", "代表方案", "适用性", "迁移难度"],
                    "rows": [
                        ["恒温热敷(电阻丝)", "主流低端", "<span class='pill t'>可用</span>", "低"],
                        ["Peltier TEC 半导体温控", "We-Vibe Temp", "<span class='pill t'>佳(可冷可热)</span>", "<span class='pill w'>中</span>"],
                        ["脉冲振动(电机调频)", "高端按摩器", "<span class='pill t'>可用</span>", "低"],
                        ["模块化可换头", "—", "<span class='pill b'>差异化</span>", "中"],
                    ],
                }],
                "callouts": ["成人护理的加热/制冷工程能力，正是本品类的技术代差来源——可作自有品牌核心壁垒。"],
                "summary": "Peltier TEC 是潜在技术壁垒，需权衡功耗与尺寸。",
            },
            "reg": {
                "note": "方法论：WorkBuddy 初筛 + 语义分析 + 临床文献「三方交叉验证」，输出分类表格调和结论。",
                "kpis": [],
                "tables": [{
                    "head": ["K号", "产品类别", "治疗/美容模式", "验证结论", "对本品启示"],
                    "rows": [
                        ["K252601", "盆底/pelvic 相关", "<span class='pill b'>治疗模式</span>", "<span class='pill t'>三方一致</span>", "需按医疗器械路径"],
                        ["K252748", "按摩/舒缓类", "<span class='pill w'>美容/舒缓</span>", "<span class='pill t'>三方一致</span>", "可作非医疗定位参照"],
                    ],
                }],
                "callouts": ["<b>合规红线：</b>仅宣称「舒缓/舒适」属低风险；涉及「通乳/治疗乳腺炎」即触发 FDA 审查。定位应守「consumer wellness」而非「medical device」。"],
                "summary": "守消费级 wellness 定位可规避医疗器械监管。",
            },
        },
    }


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


def demo_amz_us():
    """亚马逊美国站·盆底肌训练器（Bladder Control Devices）真实卖家精灵数据。
    结构严格对齐「US Bladder Control Devices 盆底肌训练器机会评分看板」：
    KPI → 核心指标 → 产品类型销售额结构 → 品牌Top10 → 头部品牌路线 → 关键词市场需求
    → 关键词趋势PPC → 价格带销售额 → 目标场景/核心痛点 → 功能/属性热度 → 十维机会评分
    → callouts(关键词解读/机会矩阵/产品定义启发/验证清单/机会点·风险·建议)。"""
    return {
        "note": "【固定模板】本维度锁定遵循「US Bladder Control Devices 盆底肌训练器机会评分看板」标准结构（10 表 + KPI + callouts），结构不随主题漂移。数据来源：卖家精灵 MCP（SellerSprite）抓取；样本月销量/销售额/价格/评分/评论/BSR 来自卖家精灵；产品类型与功能原理为基于标题的语义分类。",
        "kpis": [
            {"v": "67", "l": "机会评分"},
            {"v": "58", "l": "风险评分"},
            {"v": "164→31", "l": "候选→核心 ASIN"},
            {"v": "10,076", "l": "样本月销量(件)"},
            {"v": "$780,702", "l": "样本月销售额"},
            {"v": "$77.48", "l": "加权成交价"},
            {"v": "EMS 电刺激", "l": "Top 类型"},
            {"v": "Intimate Rose", "l": "Top 品牌"},
        ],
        "tables": [
            {"head": ["核心指标", "数值", "说明"], "rows": [
                ["候选→核心产品", "164 → 31 ASIN", "语义筛选核心盆底肌产品"],
                ["样本月销量 / 销售额", "10,076 件 / $780,702", "SellerSprite 2026-05"],
                ["加权成交价", "$77.48", "销售额 / 销量"],
                ["Top 类型", "EMS 电刺激训练器", "销售额第一类型"],
                ["Top 品牌", "Intimate Rose", "销售额 $211,728"],
                ["Top5 品牌销售额占比", "73.5%（销量 60.6%）", "头部集中明显"],
                ["平均评分", "4.2", "核心样本均值"],
                ["新品(8个)均销额", "$11,285", "1,589 件 · 198.6 件/ASIN"],
                ["Amazon 自营", "1 ASIN · 38 件 · $7,562", "平台自营参与度低"],
            ]},
            {"head": ["产品类型", "ASIN数", "销量", "销售额", "均价", "评分"], "rows": [
                ["EMS电刺激训练器", "9", "1,597", "$223,641", "$153.61", "3.98"],
                ["扩张器/硅胶套装", "9", "3,628", "$210,438", "$56.54", "4.5"],
                ["App/生物反馈训练器", "4", "1,286", "$204,381", "$204.29", "4.17"],
                ["Kegel负重训练器", "6", "3,095", "$123,454", "$26.96", "4.33"],
                ["多功能激活训练器", "1", "283", "$12,042", "$42.55", "3.1"],
                ["盆底按摩棒", "2", "187", "$6,746", "$39.97", "4.05"],
            ]},
            {"head": ["品牌销售额 Top10", "ASIN数", "销量", "销售额", "均价"], "rows": [
                ["Intimate Rose", "3", "3,236", "$211,728", "$96.66"],
                ["Perifit", "2", "1,221", "$188,181", "$149.10"],
                ["K-fit", "2", "432", "$69,368", "$234.95"],
                ["iSTIM", "2", "443", "$53,726", "$121.88"],
                ["Loving Sex", "1", "777", "$50,497", "$64.99"],
                ["Mumvia", "2", "338", "$48,917", "$144.99"],
                ["QoQiu", "3", "1,096", "$24,101", "$21.99"],
                ["Umtozz", "1", "196", "$23,518", "$119.99"],
                ["Yarlap", "1", "70", "$20,996", "$299.95"],
                ["gokszeud", "1", "283", "$12,042", "$42.55"],
            ]},
            {"head": ["头部品牌产品路线", "主打类型", "价格带", "打法"], "rows": [
                ["Intimate Rose", "扩张器/硅胶套装", "中高价", "分阶扩张 + 放松/理疗场景"],
                ["Perifit", "App/生物反馈训练器", "中高价", "App训练计划 + 可视化反馈"],
                ["K-fit", "EMS电刺激训练器", "高价", "EMS电刺激 + 效果信任建立"],
                ["iSTIM", "EMS电刺激训练器", "中高价", "EMS电刺激 + 效果信任建立"],
                ["Mumvia", "EMS电刺激训练器", "中高价", "EMS电刺激 + 效果信任建立"],
                ["QoQiu", "扩张器/硅胶套装", "低价入门", "分阶扩张 + 放松/理疗场景"],
            ]},
            {"head": ["关键词", "分类", "月搜索", "月购买", "购买率", "竞价", "供需比", "垄断点击率"], "rows": [
                ["pelvic floor exercise devices", "核心训练词", "69,780", "2,386", "3.4%", "$1.72", "123.7", "90.5%"],
                ["pelvic floor trainer", "核心训练词", "49,812", "1,529", "3.1%", "$2.00", "99.4", "86.5%"],
                ["pelvic wand", "扩张/放松词", "26,342", "2,138", "8.1%", "$1.07", "174.5", "83.3%"],
                ["kegel exerciser", "核心训练词", "43,480", "356", "0.8%", "—", "119.5", "93.7%"],
                ["kegel balls for pelvic strength", "Kegel负重词", "13,731", "81", "0.6%", "—", "90.3", "96.4%"],
                ["dilators for pelvic floor therapy", "扩张/放松词", "14,615", "125", "0.9%", "—", "92.5", "37.3%"],
            ]},
            {"head": ["关键词趋势与 PPC", "分类", "最新搜索", "同比趋势", "PPC竞价"], "rows": [
                ["pelvic floor trainer", "核心训练词", "49,812", "+954%", "$2.00"],
                ["pelvic floor exercise devices", "核心训练词", "69,780", "高位平稳", "$1.72"],
                ["pelvic wand", "扩张/放松词", "26,342", "+87%", "$1.07"],
                ["kegel exerciser", "核心训练词", "43,480", "—", "—"],
            ]},
            {"head": ["价格带", "ASIN数", "销量", "销售额"], "rows": [
                ["<$30", "9", "2,393", "$55,073"],
                ["$30-60", "6", "2,715", "$131,762"],
                ["$60-120", "5", "2,765", "$237,266"],
                ["$120-200", "9", "2,106", "$326,965"],
                ["$200+", "2", "97", "$29,635"],
            ]},
            {"head": ["目标场景", "覆盖产品类型", "核心痛点", "ASIN数", "销量", "销售额"], "rows": [
                ["产后/盆底肌力量恢复", "Kegel负重、App生物反馈、EMS电刺激", "不知道是否做对，需要训练计划和可感知反馈", "19", "5,978", "$551,476"],
                ["轻中度漏尿/膀胱控制", "EMS电刺激、App训练器", "需要更强的效果确信，对专业性和隐私敏感", "13", "2,883", "$428,022"],
                ["紧张/疼痛/放松理疗", "扩张器、盆底按摩棒", "需要循序渐进、材质安全和明确使用边界", "—", "—", "—"],
                ["入门自我训练", "Kegel负重、基础硅胶套装", "对价格敏感，但需降低第一次使用的尴尬和不确定", "—", "—", "—"],
            ]},
            {"head": ["功能/属性热度", "涉及ASIN数", "说明"], "rows": [
                ["硅胶材质", "19", "基础产品核心卖点，安全感与易清洁是必填信息"],
                ["分阶重量/尺寸", "15", "负重球和扩张器共同依赖阶梯式训练概念"],
                ["EMS电刺激", "9", "销售额第一类型，价格段 $80-$300"],
                ["App连接/可视化反馈", "4", "集中在 Perifit、K-fit 等高单价产品"],
                ["触发点/放松", "3", "盆底按摩棒和多功能激活器偏理疗工具属性"],
            ]},
            {"head": ["十维机会评分", "分数", "要点"], "rows": [
                ["市场容量", "72", "核心样本月销售额约 $780,702"],
                ["增长想象空间", "68", "App/生物反馈与 EMS 单价高，可拉开差异"],
                ["竞争集中度", "55", "头部占位明显，中长尾新 ASIN 仍有流量"],
                ["价格承接", "70", "加权价 $77.48，中高价有支撑"],
                ["评分壁垒", "58", "多数 4.0 上下，电子新品有体验机会"],
                ["产品差异化", "66", "负重/扩张器/App/EMS 路线清晰"],
                ["进入门槛", "49", "电刺激/生物反馈合规与售后要求高"],
                ["内容教育价值", "76", "依赖使用信心与方法，教程影响转化"],
                ["复购/组合", "52", "主机复购弱，凝胶/清洁/分阶有组合空间"],
                ["综合机会", "67", "选择性进入，避低价同质化"],
            ]},
        ],
        "callouts": [
            "关键词市场解读：核心训练词（pelvic floor exercise devices 69,780 搜索/月）需求巨大但供需比偏高（123.7）、垄断点击率高（90.5%），红海特征明显；扩张/放松词（pelvic wand 购买率 8.1%）转化最好，是差异化切入点。",
            "价格与销售额机会矩阵：$120-200 档以 2,106 件贡献 $326,965（最高销售额），$60-120 档次之——中高价位段已被 EMS/App 产品验证承接力，低价 <$30 档走量但销售额有限。",
            "产品定义启发：①优先——中高端电子训练器（EMS电刺激或App/生物反馈为核心，$120-200 参考价带，卖点聚焦可视化训练、效果进度与使用安全感）；②可测——分阶训练套装（扩张器/Kegel负重低门槛，以分阶指引、清洁收纳、隐私包装差异化）；③谨慎——单纯低价Kegel球（有量但差异化弱、教育成本高）。",
            "最终建议与验证清单：①合规表述——避免医疗治疗承诺，用训练/放松/支持性表述；②详情页——说清人群、禁忌、使用时长、清洁方法与训练节奏；③产品包装——隐私包装+图文教程+收纳/清洁配件是转化加分项；④评价监控——重点跟踪电子类舒适度、强度、App连接与售后问题。",
            "机会点：中高端电子训练器的销售额承接已存在，App反馈和EMS电刺激是最值得深挖的路线。主要风险：电子类涉及身体使用场景，需特别关注合规表述、安全说明、售后与低分评价。进入建议：不打低价Kegel球红海，以EMS电刺激或App生物反馈为主体，配合专业教程和使用引导建立信任。",
            "数据诚实：销量/销售额/价格/评分/评论/BSR 来自卖家精灵；产品类型与功能原理为基于标题/产品信息的语义分类，非厂商披露。",
        ],
        "summary": "美国盆底肌训练器已是明确亚马逊竞品池（月销 10,076 件 / $780,702），头部集中但中高端电子训练器（$120-200 承接力已验证）与场景化套装仍有进入窗口，建议以 EMS/App 路线 + 信任建立切入。",
    }


def demo_amz_eu():
    """亚马逊欧洲站（EU5）·盆底肌修复仪真实卖家精灵数据。"""
    return {
        "note": "【固定模板】本维度锁定遵循「欧洲盆底肌修复仪市场看板」标准结构：KPI(机会评分/风险评分/五国月销量/总销售额) → 核心指标 → 五国概览 → 产品类型 → 价格带 → 市场CAGR/关键词PPC/MDR合规/结论。结构不随主题漂移。数据来源：卖家精灵 MCP（SellerSprite）Amazon EU5 抓取；销售额=price×totalUnits（本轮 totalAmount 未返回）。已复核核心竞品池：原始 274→保留 119→去重 88 ASIN。",
        "kpis": [
            {"v": "69", "l": "机会评分"},
            {"v": "65", "l": "风险评分"},
            {"v": "6,334", "l": "五国月销量(件)"},
            {"v": "$451,079", "l": "总销售额"},
        ],
        "tables": [
            {"head": ["核心指标", "数值", "说明"], "rows": [
                ["五国月销量 / 销售额", "6,334 件 / $451,079", "price×totalUnits"],
                ["平均售价", "$71.38", "抓取价算术平均"],
                ["ASIN 数(去重)", "88", "五国"],
                ["Top5 品牌", "销量 73.1% · 销售额 75.7%", "头部集中"],
                ["最大国家", "德国 2,540 件", "销量主战场"],
                ["最大细分", "生物反馈/App 1,581 件", "智能主动训练"],
            ]},
            {"head": ["五国概览", "ASIN", "销量占比", "销售额占比", "均价"], "rows": [
                ["德国", "41", "40.1%", "37.6%", "$59.24"],
                ["英国", "35", "27.0%", "21.9%", "$71.99"],
                ["法国", "15", "17.4%", "23.6%", "$91.79"],
                ["西班牙", "20", "9.4%", "10.6%", "$74.27"],
                ["意大利", "8", "6.1%", "6.3%", "$85.52"],
            ]},
            {"head": ["产品类型", "销量", "占比", "ASIN数", "销售额"], "rows": [
                ["电刺激 EMS/TENS", "1,762", "27.8%", "34", "$131,264"],
                ["Kegel球/阴道锥", "1,684", "26.6%", "33", "—"],
                ["生物反馈/App主动训练", "1,581", "25.0%", "7", "$202,615"],
                ["盆底疼痛按摩/触发点", "913", "14.4%", "5", "—"],
                ["扩张器/产前训练", "364", "5.7%", "7", "—"],
                ["智能震动Kegel球", "30", "0.5%", "2", "—"],
            ]},
            {"head": ["价格带", "ASIN", "销量占比", "销售额占比", "均价"], "rows": [
                ["0–20", "11", "5.3%", "1.3%", "$15.37"],
                ["20–40", "20", "28.6%", "14.3%", "$32.38"],
                ["40–70", "27", "28.4%", "22.0%", "$55.67"],
                ["70–120", "22", "19.4%", "27.4%", "$95.07"],
                ["120+", "11", "18.3%", "35.1%", "$149.14"],
            ]},
        ],
        "callouts": [
            "欧洲整体市场(全渠道)2024 约 5–7 亿美元，全球占比 20–30%（第二大市场）；智能家用设备 CAGR 12–15%。",
            "关键词热度：德国 beckenbodentrainer 20,577 搜索/月；英国 pelvic floor muscle trainer 11,019；法国 perifit 3,644。PPC：西班牙最高 2.55€。",
            "风险中心：尿失禁/治疗/医疗器械/TENS 等表述需按各国 MDR 与平台政策分别核查（风险评分 65 偏高）。",
            "结论：Watchlist / 选择性进入——先验证智能反馈款与 EMS/TENS 款；德国看销量、法国看高客单。",
        ],
        "summary": "欧洲 EU5 盆底肌修复仪已形成亚马逊竞品池（月销 6,334 件），德国走量、法国高客单；智能生物反馈与电刺激为两条主线，合规风险偏高需优先。",
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
            "generatedAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "summary": summary,
            "kpis": top_kpis,
            "sections": sections_out,
        }

    # —— 模板数据（离线·卖家精灵快照 / 示意）模式 ——
    if any(w in topic.lower() for w in ["哺乳按摩器", "lactation", "breast massager"]):
        data = demo_lactation()
    else:
        data = demo_generic(topic)
    sections_out = {}
    amz_summaries = []
    for k in dims:
        if k == "amz_us":
            sections_out[k] = demo_amz_us(); amz_summaries.append("【亚马逊美国·盆底肌训练器】" + sections_out[k]["summary"])
        elif k == "amz_eu":
            sections_out[k] = demo_amz_eu(); amz_summaries.append("【亚马逊欧洲·盆底肌修复仪】" + sections_out[k]["summary"])
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
        "generatedAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
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
