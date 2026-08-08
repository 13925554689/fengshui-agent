"""
八字计算引擎 —— 基于 lunar-python 的确定性排盘。
所有数字、干支、星曜由数学算法生成，LLM 绝不碰计算。
"""

from lunar_python import Solar, Lunar
from dataclasses import dataclass, field, asdict
from typing import Optional
import datetime
import json


@dataclass
class Pillar:
    """一柱（年/月/日/时）"""
    gan: str          # 天干
    zhi: str          # 地支
    gan_zhi: str      # 干支组合
    wu_xing: str      # 五行
    na_yin: str       # 纳音
    shi_shen_gan: str # 十神(天干视角)
    shi_shen_zhi: list[str]  # 十神(地支视角)
    hide_gan: list[str]      # 藏干
    di_shi: str       # 地势(十二长生)
    xun_kong: str     # 旬空


@dataclass
class DaYunStep:
    """一步大运"""
    gan_zhi: str
    start_age: int
    end_age: int
    liu_nian: list[dict] = field(default_factory=list)


@dataclass
class BaZiChart:
    """完整八字命盘"""
    # 基础信息
    solar_date: str       # 公历
    lunar_date: str       # 农历
    sex: str              # 男/女
    # 四柱
    year: Pillar
    month: Pillar
    day: Pillar
    hour: Pillar
    # 综合
    ri_gan: str           # 日干
    ri_zhi: str           # 日支
    wu_xing_score: dict   # 五行计数
    # 特殊
    ming_gong: str        # 命宫
    tai_yuan: str         # 胎元
    # 大运
    qi_yun_age: int       # 起运年龄
    da_yun: list[DaYunStep]
    # 当前流年
    current_liu_nian: Optional[dict] = None


# lunar-python uses 'Time' not 'Hour' for the hour pillar
PILLAR_MAP = {"year": "Year", "month": "Month", "day": "Day", "hour": "Time"}

def _build_pillar(ba, pillar_name: str) -> Pillar:
    """构建一柱"""
    p = PILLAR_MAP[pillar_name]
    gan = getattr(ba, f'get{p}Gan')()
    zhi = getattr(ba, f'get{p}Zhi')()
    return Pillar(
        gan=gan,
        zhi=zhi,
        gan_zhi=f"{gan}{zhi}",
        wu_xing=getattr(ba, f'get{p}WuXing')(),
        na_yin=getattr(ba, f'get{p}NaYin')(),
        shi_shen_gan=getattr(ba, f'get{p}ShiShenGan')(),
        shi_shen_zhi=getattr(ba, f'get{p}ShiShenZhi')(),
        hide_gan=getattr(ba, f'get{p}HideGan')(),
        di_shi=getattr(ba, f'get{p}DiShi')(),
        xun_kong=getattr(ba, f'get{p}XunKong')(),
    )


def _count_wu_xing(pillars: list[Pillar]) -> dict:
    """统计五行分布 (含藏干)"""
    score = {"金": 0, "木": 0, "水": 0, "火": 0, "土": 0}
    wx_map = {
        "金": "金", "木": "木", "水": "水", "火": "火", "土": "土",
        "庚": "金", "辛": "金", "甲": "木", "乙": "木",
        "壬": "水", "癸": "水", "丙": "火", "丁": "火",
        "戊": "土", "己": "土",
        "申": "金", "酉": "金", "寅": "木", "卯": "木",
        "子": "水", "亥": "水", "巳": "火", "午": "火",
        "辰": "土", "戌": "土", "丑": "土", "未": "土",
    }
    for p in pillars:
        # 天干权重 3, 地支权重 2
        if p.gan in wx_map:
            score[wx_map[p.gan]] += 3
        if p.zhi in wx_map:
            score[wx_map[p.zhi]] += 2
        # 藏干权重 1
        for hg in p.hide_gan:
            if hg in wx_map:
                score[wx_map[hg]] += 1
    return score


def compute_bazi(
    year: int, month: int, day: int,
    hour: int = 0, minute: int = 0,
    sex: int = 1  # 1=男, 0=女
) -> BaZiChart:
    """
    计算八字命盘。

    Args:
        year: 公历年
        month: 公历月
        day: 公历日
        hour: 小时 (0-23)
        minute: 分钟
        sex: 1=男, 0=女

    Returns:
        BaZiChart 完整命盘
    """
    solar = Solar.fromYmdHms(year, month, day, hour, minute, 0)
    lunar = solar.getLunar()
    ba = lunar.getEightChar()

    # 四柱
    y = _build_pillar(ba, 'year')
    m = _build_pillar(ba, 'month')
    d = _build_pillar(ba, 'day')
    t = _build_pillar(ba, 'hour')

    # 五行统计
    wx_score = _count_wu_xing([y, m, d, t])

    # 大运
    yun = ba.getYun(sex)
    qi_yun = yun.getStartYear()
    da_yun_steps = []
    for dy in yun.getDaYun():
        gz = dy.getGanZhi()
        if not gz or gz.strip() == '':
            continue
        ln_list = []
        for ln in dy.getLiuNian():
            ln_list.append({
                "year": ln.getYear(),
                "gan_zhi": ln.getGanZhi(),
                "age": ln.getAge(),
            })
        da_yun_steps.append(DaYunStep(
            gan_zhi=gz,
            start_age=dy.getStartAge(),
            end_age=dy.getEndAge(),
            liu_nian=ln_list,
        ))

    # 当前流年
    curr_year = datetime.datetime.now().year
    current_ln = None
    for ds in da_yun_steps:
        for ln in ds.liu_nian:
            if ln["year"] == curr_year:
                current_ln = {**ln, "da_yun": ds.gan_zhi}
                break
        if current_ln:
            break

    chart = BaZiChart(
        solar_date=solar.toFullString(),
        lunar_date=f"{lunar.getYearInChinese()}年 {lunar.getMonthInChinese()}月 {lunar.getDayInChinese()}日 {lunar.getTimeZhi()}时",
        sex="男" if sex == 1 else "女",
        year=y,
        month=m,
        day=d,
        hour=t,
        ri_gan=d.gan,
        ri_zhi=d.zhi,
        wu_xing_score=wx_score,
        ming_gong=ba.getMingGong(),
        tai_yuan=ba.getTaiYuan(),
        qi_yun_age=qi_yun,
        da_yun=da_yun_steps,
        current_liu_nian=current_ln,
    )
    return chart


def chart_to_text(chart: BaZiChart) -> str:
    """将命盘转为给 LLM 阅读的精简文本"""
    lines = []
    lines.append(f"## 八字命盘")
    lines.append(f"公历: {chart.solar_date}")
    lines.append(f"农历: {chart.lunar_date}")
    lines.append(f"性别: {chart.sex}")
    lines.append("")
    lines.append("### 四柱")
    lines.append(f"|  | 年柱 | 月柱 | 日柱 | 时柱 |")
    lines.append(f"|---|---|---|---|---|")
    lines.append(f"| 干支 | {chart.year.gan_zhi} | {chart.month.gan_zhi} | {chart.day.gan_zhi} | {chart.hour.gan_zhi} |")
    lines.append(f"| 天干 | {chart.year.gan} | {chart.month.gan} | {chart.day.gan} | {chart.hour.gan} |")
    lines.append(f"| 地支 | {chart.year.zhi} | {chart.month.zhi} | {chart.day.zhi} | {chart.hour.zhi} |")
    lines.append(f"| 五行 | {chart.year.wu_xing} | {chart.month.wu_xing} | {chart.day.wu_xing} | {chart.hour.wu_xing} |")
    lines.append(f"| 十神 | {chart.year.shi_shen_gan} | {chart.month.shi_shen_gan} | {chart.day.shi_shen_gan} | {chart.hour.shi_shen_gan} |")
    lines.append(f"| 藏干 | {'、'.join(chart.year.hide_gan)} | {'、'.join(chart.month.hide_gan)} | {'、'.join(chart.day.hide_gan)} | {'、'.join(chart.hour.hide_gan)} |")
    lines.append(f"| 纳音 | {chart.year.na_yin} | {chart.month.na_yin} | {chart.day.na_yin} | {chart.hour.na_yin} |")
    lines.append(f"| 地势 | {chart.year.di_shi} | {chart.month.di_shi} | {chart.day.di_shi} | {chart.hour.di_shi} |")
    lines.append(f"| 旬空 | {chart.year.xun_kong} | {chart.month.xun_kong} | {chart.day.xun_kong} | {chart.hour.xun_kong} |")
    lines.append("")
    lines.append(f"日主: **{chart.ri_gan}** ({chart.day.wu_xing})")
    lines.append(f"五行分布: {chart.wu_xing_score}")
    lines.append(f"命宫: {chart.ming_gong}  胎元: {chart.tai_yuan}")
    lines.append("")
    # 大运
    lines.append("### 大运 (起运{0}岁)".format(chart.qi_yun_age))
    for ds in chart.da_yun[:8]:
        lines.append(f"- {ds.gan_zhi} ({ds.start_age}-{ds.end_age}岁)")

    if chart.current_liu_nian:
        ln = chart.current_liu_nian
        lines.append("")
        lines.append(f"### 当前流年: {ln['year']}年 {ln['gan_zhi']} (大运: {ln['da_yun']}, 年龄: {ln['age']})")

    return "\n".join(lines)


def chart_to_json(chart: BaZiChart) -> dict:
    """将命盘转为 JSON (用于 API 返回)"""
    da_yun_json = []
    for ds in chart.da_yun[:8]:
        da_yun_json.append({
            "gan_zhi": ds.gan_zhi,
            "start_age": ds.start_age,
            "end_age": ds.end_age,
            "liu_nian": ds.liu_nian[:3],  # 只取前3年概览
        })
    return {
        "solar_date": chart.solar_date,
        "lunar_date": chart.lunar_date,
        "sex": chart.sex,
        "bazi": {
            "year": chart.year.gan_zhi,
            "month": chart.month.gan_zhi,
            "day": chart.day.gan_zhi,
            "hour": chart.hour.gan_zhi,
        },
        "ri_gan": chart.ri_gan,
        "ri_zhi": chart.ri_zhi,
        "pillars": {
            "year": asdict(chart.year),
            "month": asdict(chart.month),
            "day": asdict(chart.day),
            "hour": asdict(chart.hour),
        },
        "wu_xing_score": chart.wu_xing_score,
        "ming_gong": chart.ming_gong,
        "tai_yuan": chart.tai_yuan,
        "qi_yun_age": chart.qi_yun_age,
        "da_yun": da_yun_json,
        "current_liu_nian": chart.current_liu_nian,
    }
