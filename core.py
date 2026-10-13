"""
命理 AI Agent 核心 —— ReAct 循环 + 知识检索。

架构：
  用户输入 → ReAct Loop → 计算工具(确定性) / 知识检索(RAG) → LLM综合
  LLM 绝不碰计算，只负责：读盘 + 查典籍 + 综合解释。
"""

import os
import json as _json
import subprocess
import time
from openai import OpenAI

from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, KNOWLEDGE_DIR
)
from compute import compute_bazi, chart_to_text
from fengshui_compute import fengshui_analysis, fengshui_to_text

# ── LLM Client ──────────────────────────────────────────────
client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)


# ── Tool Definitions ─────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "compute_bazi_chart",
            "description": "计算八字命盘。必须精确输入公历年月日时。返回四柱、十神、五行、大运、流年等完整命盘数据。这是最基础的工具，分析任何命理前必须先调用此工具取得命盘。",
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {"type": "integer", "description": "公历出生年份"},
                    "month": {"type": "integer", "description": "公历出生月份(1-12)"},
                    "day": {"type": "integer", "description": "公历出生日期"},
                    "hour": {"type": "integer", "description": "出生小时(0-23)", "default": 0},
                    "minute": {"type": "integer", "description": "出生分钟(0-59)", "default": 0},
                    "sex": {"type": "integer", "description": "性别: 1=男, 0=女", "default": 1},
                    "longitude": {"type": "number", "description": "出生地东经度数(如北京116.4、上海121.5、成都104.1)。按东八区钟表时+真太阳时校正时柱；仅适用于中国境内出生时间", "default": None},
                },
                "required": ["year", "month", "day", "hour", "sex"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "搜索命理知识库。当需要查找十神定义、用神判断规则、大运流年法则等专业知识时调用。使用 ripgrep 全文搜索。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词，如 '正官 事业'、'用神判断'、'大运流年'、'伤官见官'"},
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_knowledge_file",
            "description": "读取完整的知识库文件。当搜索到相关条目后，读完整文件获取上下文。",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "知识库文件名，如 shishen.md, dayun.md, 八宅明鏡.md (classics/下古籍)"},
                },
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fengshui_analysis",
            "description": "风水综合分析。输入房屋朝向和居住者信息，返回宅命匹配、年度飞星布局、个人吉凶方位、八宅分析。用于阳宅选房、布局、办公室和厂房风水分析。",
            "parameters": {
                "type": "object",
                "properties": {
                    "facing": {"type": "string", "description": "房屋朝向: 南/北/东/西/东南/西南/东北/西北"},
                    "residents": {"type": "array", "items": {"type": "array", "items": {}}, "description": "居住者列表: [[出生年, 性别], ...], 性别 male/female/男/女"},
                    "analysis_year": {"type": "integer", "description": "分析年份, 默认当前年"},
                },
                "required": ["facing", "residents"]
            }
        }
    },
]


# ── Tool Implementations ─────────────────────────────────────

def tool_compute_bazi(year, month, day, hour=0, minute=0, sex=1, longitude=None):
    """计算八字命盘（提供 longitude 时按真太阳时校正时柱）"""
    chart = compute_bazi(year, month, day, hour, minute, sex, longitude=longitude)
    return chart, chart_to_text(chart)


def tool_search_knowledge(query):
    """ripgrep 搜索知识库（简体查询自动附加繁体变体，古籍库为繁体）"""
    try:
        result = subprocess.run(
            # P0 fix: `--` 终止 flag 解析, 防 query 注入 rg 参数 (如 --files/-e)
            ["rg", "-n", "-i", "--", query, str(KNOWLEDGE_DIR)],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            # 截取前20条
            return "\n".join(lines[:20])
        elif result.returncode == 1:
            return _variant_fallback(query)
        else:
            return f"(搜索错误: {result.stderr})"
    except FileNotFoundError:
        # ripgrep 未安装，fallback 到 grep
        try:
            result = subprocess.run(
                ["grep", "-r", "-n", "-i", query, str(KNOWLEDGE_DIR)],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return "\n".join(result.stdout.strip().split("\n")[:20])
            return _variant_fallback(query)
        except Exception as e:
            return f"(搜索失败: {e})"


# ponytail: 逐字映射表覆盖检索常用字，够用且零依赖；全字表升级用 opencc
_S2T = {"经": "經", "书": "書", "阴": "陰", "阳": "陽", "龙": "龍", "风": "風",
        "水": "水", "山": "山", "宅": "宅", "门": "門", "灶": "竈", "运": "運",
        "盘": "盤", "卦": "卦", "星": "星", "气": "氣", "灵": "靈", "宝": "寶",
        "传": "傳", "记": "記", "历": "曆", "时": "時", "岁": "歲",
        "义": "義", "镜": "鏡", "诀": "訣", "断": "斷", "赋": "賦", "葬": "葬",
        "墓": "墓", "穴": "穴", "砂": "砂", "向": "向", "局": "局", "峰": "峰",
        "城": "城", "精": "精", "奥": "奧", "语": "語", "遗": "遺", "括": "括",
        "贪": "貪", "巨": "巨", "禄": "祿", "文": "文", "廉": "廉", "武": "武",
        "破": "破", "辅": "輔", "弼": "弼", "飞": "飛", "挨": "挨", "替": "替"}

# T→S 反向表: 八宅明鏡.md 等正文为简体, 繁体查询需降级
_S2T_REV = {v: k for k, v in _S2T.items() if v != k}


def _s2t(text: str) -> str:
    return "".join(_S2T.get(ch, ch) for ch in text)


def _t2s(text: str) -> str:
    return "".join(_S2T_REV.get(ch, ch) for ch in text)


def _variant_fallback(query: str) -> str:
    """零命中时用简↔繁变体重试（古籍库繁简混录）"""
    tried = []
    for t in (_s2t(query), _t2s(query)):
        if t != query and t not in tried:
            tried.append(t)
    for t in tried:
        cmd = ["rg", "-n", "-i", "--", t, str(KNOWLEDGE_DIR)]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        except FileNotFoundError:  # rg 不在 PATH 时同主路径降级 grep
            result = subprocess.run(["grep", "-r", "-n", "-i", t, str(KNOWLEDGE_DIR)],
                                    capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            return "\n".join(lines[:20])
    return "(未找到匹配内容)"


def tool_read_knowledge(filename):
    """读取知识库文件（含 classics/ 子目录）"""
    safe_name = os.path.basename(filename)  # 防路径遍历
    filepath = KNOWLEDGE_DIR / safe_name
    if not filepath.exists():
        # 知识文件不存在时扫子目录（classics/ 等）
        for p in KNOWLEDGE_DIR.rglob(safe_name):
            filepath = p
            break
    if filepath.exists():
        return filepath.read_text(encoding="utf-8")
    return f"(文件不存在: {safe_name})"


def tool_fengshui(facing, residents, analysis_year=None):
    """风水综合分析"""
    result = fengshui_analysis(facing, residents, analysis_year)
    return result, fengshui_to_text(result)


TOOL_MAP = {
    "compute_bazi_chart": tool_compute_bazi,
    "search_knowledge": tool_search_knowledge,
    "read_knowledge_file": tool_read_knowledge,
    "fengshui_analysis": tool_fengshui,
}


# ── System Prompt ────────────────────────────────────────────

SYSTEM_PROMPT = """你是一位精通八字命理与风水的AI命理风水师。你的分析融合了《渊海子平》《子平真诠》《穷通宝鉴》《八宅明镜》《玄空飞星》等经典典籍的智慧。

## 核心原则
1. **先算后说**: 分析前必须调用工具获取准确数据，绝不可凭空编造。
   - 八字分析 → 调用 compute_bazi_chart
   - 风水分析 → 调用 fengshui_analysis
2. **指着盘面说话**: 每个结论都要引用具体的盘面数据（某柱某神、五行分布、飞星方位等），不说放诸四海皆准的"巴纳姆废话"。
3. **知识溯源**: 使用 search_knowledge 检索专业规则，引用规则再给结论。
   - knowledge/classics/ 目录收录11篇公版古籍原文（繁简混录）（理气：青囊經/天玉經/都天寶照經；巒頭：撼龍經/靈城精義/葬書；八宅：八宅明鏡/陽宅三要），涉及理气、峦头、葬法、门主灶等论断时检索并注明出处（如"《天玉經》云：…"）。检索词简繁均可（系统自动变体重试）。
4. **流派透明**: 每个风水结论注明所用流派（八宅/玄空飞星/峦头形势）。不同流派结论冲突时明确指出"八宅主吉、玄空主忌"这类分歧，不混为一谈、不 averaging 和稀泥；八宅断门主灶（引《阳宅三要》《八宅明镜》），玄空断宅运飞星，峦头断形煞，各归其位。
5. **坦承局限**: 命理与风水是传统文化智慧，提供的是参考而非绝对预言。遇到不确定的地方要诚实说明。

## 分析框架
### 八字分析
1. 日主分析: 日干是什么，五行属性，得令/得地/得势情况，身强还是身弱
2. 五行平衡: 五行分布如何，缺什么、旺什么
3. 用神判断: 根据强弱和格局，判断喜用神和忌神
4. 十神配置: 十神在四柱的分布
5. 大运走势: 当前走在哪步大运，运势趋势
6. 流年分析: 结合当前流年干支，分析吉凶

### 风水分析
1. 宅运判断: 朝向→宅卦，东/西四宅分类
2. 年度飞星: 财位、文昌位、五黄位、二黑位、桃花位
3. 命卦计算: 每位居住者的命卦和吉凶方位
4. 宅命匹配: 人宅是否相配，不相配如何补救
5. 布局建议: 床位、书桌、财位、厨房、卫生间位置
6. 化煞方案: 五黄、二黑、三煞、太岁等化解措施

## 回答风格
- 用通俗易懂的中文，避免堆砌术语
- 给出具体可操作的布局建议（如"主卧床应朝XX方""财位在XX方放XX物品"）
- 积极正向，帮助用户改善居住环境而非制造焦虑
- 可以适当使用比喻让表达生动
"""


# ── ReAct Agent ──────────────────────────────────────────────

class MingLiAgent:
    """命理AI Agent — ReAct 循环"""

    def __init__(self):
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.chart = None
        self.chart_text = ""

    def _run_llm(self, messages, tools=None):
        """调用 LLM (60s 超时 + 指数退避重试 3 次, P1 fix)"""
        kwargs = {
            "model": DEEPSEEK_MODEL,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 4096,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        last_err = None
        for attempt in range(3):
            try:
                return client.chat.completions.create(**kwargs, timeout=60)
            except Exception as e:
                last_err = e
                time.sleep(2 ** attempt)
        raise RuntimeError(f"LLM调用失败(3次重试): {last_err}") from last_err

    def _trim_context(self, messages):
        """ReAct 上下文预算: 累计 >32k 字符时弹出最早的非 system 轮次。
        ponytail: 字符估算代替 token 计数 (不引 tiktoken); 孤儿 tool_call 被 LLM 宽容忽略。"""
        def _len(m):
            c = m.get("content") if isinstance(m, dict) else getattr(m, "content", None)
            return len(c or "")
        total = sum(_len(m) for m in messages)
        while total > 32000 and len(messages) > 1:  # 至少保留 system
            for i, m in enumerate(messages[1:], start=1):
                if (m.get("role") if isinstance(m, dict) else getattr(m, "role", "")) != "system":
                    removed = messages.pop(i)
                    total -= _len(removed)
                    break

    def analyze(self, user_input: str) -> str:
        """
        分析用户输入。支持两种模式：
        1. 初次分析：用户提供出生信息
        2. 追问：在已有命盘基础上深入探讨
        """
        self.messages.append({"role": "user", "content": user_input})

        # ReAct 循环，最多 8 轮
        for _ in range(8):
            self._trim_context(self.messages)
            response = self._run_llm(self.messages, TOOLS)

            msg = response.choices[0].message
            # ponytail: pydantic 对象转 dict, 否则 _trim_context/序列化都要 dual-path
            msg = {"role": msg.role, "content": msg.content,
                   **({"tool_calls": [{"id": tc.id, "type": "function",
                                       "function": {"name": tc.function.name,
                                                    "arguments": tc.function.arguments}}
                                      for tc in msg.tool_calls]} if msg.tool_calls else {})}
            self.messages.append(msg)

            # 无工具调用 → 最终回答
            if not msg["tool_calls"]:
                return msg["content"] or ""

            # 执行工具调用
            for tc in msg["tool_calls"]:
                fn_name = tc["function"]["name"]
                fn_args = _json.loads(tc["function"]["arguments"])
                fn = TOOL_MAP.get(fn_name)

                if fn is None:
                    result = f"未知工具: {fn_name}"
                elif fn_name == "compute_bazi_chart":
                    chart, chart_text = fn(**fn_args)
                    self.chart = chart
                    self.chart_text = chart_text
                    result = chart_text
                else:
                    result = fn(**fn_args)

                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    # P1 fix: 工具结果截断 8k, 防大运流年文本撑爆 context
                    "content": (str(result)[:8000] + "\n...(结果过长已截断)" if len(str(result)) > 8000 else str(result)),
                })

        # fallback
        return self.messages[-1].get("content", "分析超时，请重试。")

    def chat_stream(self, user_input: str):
        """流式对话（用于SSE）"""
        self.messages.append({"role": "user", "content": user_input})

        # 非流式先跑 ReAct
        for _ in range(8):
            self._trim_context(self.messages)
            response = self._run_llm(self.messages, TOOLS)
            msg = response.choices[0].message
            # ponytail: pydantic 对象转 dict, 否则 _trim_context/序列化都要 dual-path
            msg = {"role": msg.role, "content": msg.content,
                   **({"tool_calls": [{"id": tc.id, "type": "function",
                                       "function": {"name": tc.function.name,
                                                    "arguments": tc.function.arguments}}
                                      for tc in msg.tool_calls]} if msg.tool_calls else {})}
            self.messages.append(msg)

            if not msg.tool_calls:
                yield msg.content or ""
                return

            for tc in msg.tool_calls:
                fn_name = tc.function.name
                fn_args = _json.loads(tc.function.arguments)
                fn = TOOL_MAP.get(fn_name)

                if fn is None:
                    result = f"未知工具: {fn_name}"
                elif fn_name == "compute_bazi_chart":
                    chart, chart_text = fn(**fn_args)
                    self.chart = chart
                    self.chart_text = chart_text
                    result = chart_text
                else:
                    result = fn(**fn_args)

                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    # P1 fix: 工具结果截断 8k, 防大运流年文本撑爆 context
                    "content": (str(result)[:8000] + "\n...(结果过长已截断)" if len(str(result)) > 8000 else str(result)),
                })

        yield self.messages[-1].get("content", "分析超时，请重试。")
