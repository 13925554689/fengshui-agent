"""
风水计算引擎 —— 命卦、宅卦、八宅、玄空飞星。
从 suangua 核心提取，纯 Python 确定性计算。
"""
from __future__ import annotations
from typing import Dict, List, Any, Tuple
from datetime import date

# ═══════════════════════════════════════════════════════════
# 1. 命卦 (Ming Gua)
# ═══════════════════════════════════════════════════════════

EAST_FOUR_LIFE = {1, 3, 4, 9}
WEST_FOUR_LIFE = {2, 5, 6, 7, 8}

DIRECTION_GUA: Dict[str, int] = {
    "南": 9, "北": 1, "东": 3, "西": 7,
    "东南": 4, "西北": 6, "东北": 8, "西南": 2,
}
EAST_FOUR_HOUSE = {1, 3, 4, 9}
WEST_FOUR_HOUSE = {2, 6, 7, 8}

def calculate_ming_gua(birth_year: int, gender: str) -> int:
    """命卦计算"""
    y = birth_year % 100
    while y >= 10:
        y = sum(int(d) for d in str(y))
    if y == 0:
        y = 9
    male = gender in ("male", "男", 1)
    if birth_year < 2000:
        gua = (10 - y) % 9 if male else (y + 5) % 9
    else:
        gua = (9 - y) % 9 if male else (y + 6) % 9
    if gua == 0:
        gua = 9
    if gua == 5:
        gua = 2 if male else 8
    return gua

def get_ming_gua_group(gua: int) -> str:
    return "东四命" if gua in EAST_FOUR_LIFE else "西四命"

def get_house_gua(facing: str) -> int:
    return DIRECTION_GUA.get(facing, 9)

def get_house_group(gua: int) -> str:
    return "东四宅" if gua in EAST_FOUR_HOUSE else "西四宅"

# ═══════════════════════════════════════════════════════════
# 2. 个人八宅吉凶方位
# ═══════════════════════════════════════════════════════════

# 命卦→各方位吉凶 (key: ming_gua, val: {八宅类型: 方向})
PERSONAL_DIRECTIONS_MAP = {
    1: {"shengqi": "东南", "tianyi": "东", "niannian": "南", "fuwei": "北","jueming": "西南", "wugui": "东北", "liusha": "西北", "huohai": "西"},
    2: {"shengqi": "东北", "tianyi": "西", "niannian": "西北", "fuwei": "西南","jueming": "北", "wugui": "东南", "liusha": "南", "huohai": "东"},
    3: {"shengqi": "南", "tianyi": "北", "niannian": "东南", "fuwei": "东","jueming": "西南", "wugui": "东北", "liusha": "西北", "huohai": "西"},
    4: {"shengqi": "北", "tianyi": "南", "niannian": "东", "fuwei": "东南","jueming": "东北", "wugui": "西南", "liusha": "西", "huohai": "西北"},
    6: {"shengqi": "西", "tianyi": "东北", "niannian": "西南", "fuwei": "西北","jueming": "南", "wugui": "北", "liusha": "东", "huohai": "东南"},
    7: {"shengqi": "西北", "tianyi": "西南", "niannian": "东北", "fuwei": "西","jueming": "东", "wugui": "南", "liusha": "东南", "huohai": "北"},
    8: {"shengqi": "西南", "tianyi": "西北", "niannian": "西", "fuwei": "东北","jueming": "东南", "wugui": "北", "liusha": "东", "huohai": "南"},
    9: {"shengqi": "东", "tianyi": "东南", "niannian": "北", "fuwei": "南","jueming": "西北", "wugui": "西", "liusha": "西南", "huohai": "东北"},
}

DIRECTION_MEANINGS = {
    "shengqi": "生气位（最旺财丁，宜主卧门向）",
    "tianyi": "天医位（利健康求医，宜卧室）",
    "niannian": "延年位（利婚姻家庭，宜客厅）",
    "fuwei": "伏位（稳定守成，宜储藏）",
    "jueming": "绝命位（最凶，忌卧室厨房）",
    "wugui": "五鬼位（官非灾祸，忌主要房间）",
    "liusha": "六煞位（破财损丁，忌财位）",
    "huohai": "祸害位（口舌疾病，忌卧室）",
}

def get_personal_directions(mg: int) -> dict:
    """获取个人八宅吉凶方位"""
    dirs = PERSONAL_DIRECTIONS_MAP.get(mg, {})
    result = {"ming_gua": mg}
    for key in ["shengqi", "tianyi", "niannian", "fuwei", "jueming", "wugui", "liusha", "huohai"]:
        if key in dirs:
            result[key] = {"direction": dirs[key], "meaning": DIRECTION_MEANINGS.get(key, "")}
    # 简化建议
    result["best_bed_dir"] = f"{dirs.get('shengqi','')}（生气）"
    result["best_desk_dir"] = f"{dirs.get('tianyi','')}（天医）"
    result["wealth_spot"] = f"{dirs.get('shengqi','')}方"
    result["health_spot"] = f"{dirs.get('tianyi','')}方"
    result["romance_spot"] = f"{dirs.get('niannian','')}方"
    return result

# ═══════════════════════════════════════════════════════════
# 3. 宅命匹配
# ═══════════════════════════════════════════════════════════

def check_compatibility(ming_gua: int, house_gua: int) -> str:
    """判断宅命是否相配"""
    mg_group = get_ming_gua_group(ming_gua)
    hg_group = get_house_group(house_gua)
    if mg_group == "东四命" and hg_group == "东四宅":
        return f"相配｜命卦{ming_gua}（{mg_group}）与宅卦{house_gua}（{hg_group}）同属东四，《八宅明镜》云：东四命住东四宅，同类相得则吉。"
    elif mg_group == "西四命" and hg_group == "西四宅":
        return f"相配｜命卦{ming_gua}（{mg_group}）与宅卦{house_gua}（{hg_group}）同属西四，《八宅明镜》云：西四命住西四宅，同类相得则吉。"
    else:
        return f"不相配｜命卦{ming_gua}（{mg_group}）与宅卦{house_gua}（{hg_group}）不同类，《八宅明镜》云：东命住西宅或西命住东宅，命宅相克则凶。"

# ═══════════════════════════════════════════════════════════
# 4. 玄空飞星
# ═══════════════════════════════════════════════════════════

ANNUAL_FLYING_STAR_MAP = {
    # year % 9 → (入中星数, 九宫分布)
    0: (8, {"北": 7, "西南": 3, "东": 5, "东南": 1, "中": 8, "西北": 4, "西": 6, "东北": 2, "南": 9}),
    1: (1, {"北": 9, "西南": 5, "东": 7, "东南": 3, "中": 1, "西北": 6, "西": 8, "东北": 4, "南": 2}),
    2: (2, {"北": 1, "西南": 6, "东": 8, "东南": 9, "中": 2, "西北": 7, "西": 4, "东北": 5, "南": 3}),
    3: (3, {"北": 2, "西南": 7, "东": 9, "东南": 1, "中": 3, "西北": 5, "西": 8, "东北": 6, "南": 4}),
    4: (4, {"北": 3, "西南": 8, "东": 1, "东南": 2, "中": 4, "西北": 6, "西": 9, "东北": 7, "南": 5}),
    5: (5, {"北": 4, "西南": 9, "东": 2, "东南": 3, "中": 5, "西北": 7, "西": 1, "东北": 8, "南": 6}),
    6: (6, {"北": 5, "西南": 1, "东": 3, "东南": 4, "中": 6, "西北": 8, "西": 2, "东北": 9, "南": 7}),
    7: (7, {"北": 6, "西南": 2, "东": 4, "东南": 5, "中": 7, "西北": 9, "西": 3, "东北": 1, "南": 8}),
    8: (9, {"北": 8, "西南": 4, "东": 6, "东南": 7, "中": 9, "西北": 2, "西": 5, "东北": 3, "南": 1}),
}

STAR_NAMES = {
    1: ("一白贪狼星", "吉", {"element": "水", "meaning": "桃花、文昌、贵人"}),
    2: ("二黑巨门星", "大凶", {"element": "土", "meaning": "病符、疾病", "remedy": "铜葫芦化煞"}),
    3: ("三碧禄存星", "凶", {"element": "木", "meaning": "口舌是非", "remedy": "红色物品化解"}),
    4: ("四绿文昌星", "吉", {"element": "木", "meaning": "文学、考试"}),
    5: ("五黄廉贞星", "大凶", {"element": "土", "meaning": "灾祸、疾病", "remedy": "六帝钱、铜风铃化煞，禁止动土"}),
    6: ("六白武曲星", "吉", {"element": "金", "meaning": "权力、偏财"}),
    7: ("七赤破军星", "凶", {"element": "金", "meaning": "口舌、血光", "remedy": "蓝色水晶化解"}),
    8: ("八白左辅星", "大吉", {"element": "土", "meaning": "正财、旺丁"}),
    9: ("九紫右弼星", "吉", {"element": "火", "meaning": "喜庆、婚姻"}),
}

def calculate_annual_flying_stars(year: int = None) -> dict:
    """年度飞星布局"""
    if year is None:
        year = date.today().year
    center_star, layout = ANNUAL_FLYING_STAR_MAP.get(year % 9, ANNUAL_FLYING_STAR_MAP[8])
    star_name, star_nature, _ = STAR_NAMES.get(center_star, ("未知", "", {}))

    # 找出各关键星位
    wealth_dir = next((d for d, s in layout.items() if s == 8), "未知")
    study_dir = next((d for d, s in layout.items() if s == 4), "未知")
    five_yellow_dir = next((d for d, s in layout.items() if s == 5), "未知")
    two_black_dir = next((d for d, s in layout.items() if s == 2), "未知")
    romance_dir = next((d for d, s in layout.items() if s == 1), "未知")

    # 吉凶分类
    auspicious = []
    inauspicious = []
    for d, s in layout.items():
        _, nature, _ = STAR_NAMES.get(s, ("", "", {}))
        if "吉" in nature:
            auspicious.append(d)
        else:
            inauspicious.append(d)

    summary = (
        f"{year}年，{star_name}入中宫。"
        f"财位在{wealth_dir}方（八白旺财），宜摆放招财物品；"
        f"文昌位在{study_dir}方（四绿文昌），宜设书房；"
        f"五黄在{five_yellow_dir}方，此方绝对禁止动土装修；"
        f"二黑病符在{two_black_dir}方，需摆铜葫芦化病气。"
    )

    return {
        "year": year, "center_star": center_star, "center_star_name": star_name,
        "center_star_nature": star_nature,
        "layout": layout,
        "wealth_direction": wealth_dir, "study_direction": study_dir,
        "five_yellow_direction": five_yellow_dir, "two_black_direction": two_black_dir,
        "romance_direction": romance_dir,
        "auspicious_directions": auspicious, "inauspicious_directions": inauspicious,
        "annual_summary": summary,
    }

# ═══════════════════════════════════════════════════════════
# 5. 综合风水分析 (一站式)
# ═══════════════════════════════════════════════════════════

def fengshui_analysis(facing: str, residents: list[tuple], analysis_year: int = None) -> dict:
    """
    综合风水分析
    Args:
        facing: 朝向(南/北/东/西/东南/西南/东北/西北)
        residents: [(birth_year, gender), ...]
        analysis_year: 分析年份
    """
    year = analysis_year or date.today().year
    house_gua = get_house_gua(facing)
    house_group = get_house_group(house_gua)
    annual_fs = calculate_annual_flying_stars(year)

    residents_result = []
    for birth_year, gender in residents:
        mg = calculate_ming_gua(birth_year, gender)
        mg_group = get_ming_gua_group(mg)
        compat = check_compatibility(mg, house_gua)
        personal_dirs = get_personal_directions(mg)
        residents_result.append({
            "birth_year": birth_year, "gender": gender,
            "ming_gua": mg, "ming_gua_group": mg_group,
            "compatibility": compat, "personal_directions": personal_dirs,
        })

    return {
        "year": year, "facing": facing,
        "house_gua": house_gua, "house_group": house_group,
        "annual_flying_stars": annual_fs,
        "residents": residents_result,
    }


def fengshui_to_text(result: dict) -> str:
    """风水分析转文本 (给LLM阅读)"""
    lines = []
    hg = result["house_gua"]
    hg_group = result["house_group"]
    fs = result["annual_flying_stars"]

    lines.append(f"## 风水分析")
    lines.append(f"房屋朝向: {result['facing']}  宅卦: {hg}({hg_group})  年份: {result['year']}")
    lines.append(f"年度飞星: {fs['center_star_name']}({fs['center_star_nature']})入中宫")
    lines.append(f"财位: {fs['wealth_direction']}方(八白)  文昌: {fs['study_direction']}方(四绿)")
    lines.append(f"⚠ 五黄: {fs['five_yellow_direction']}方  ⚠ 二黑: {fs['two_black_direction']}方")
    lines.append(f"桃花: {fs['romance_direction']}方(一白)")
    lines.append(f"吉方: {', '.join(fs['auspicious_directions'])}")
    lines.append(f"凶方: {', '.join(fs['inauspicious_directions'])}")
    lines.append("")

    for i, r in enumerate(result["residents"]):
        label = f"居住者{i+1}"
        lines.append(f"### {label}: 命卦{r['ming_gua']}({r['ming_gua_group']})")
        lines.append(f"宅命匹配: {r['compatibility']}")
        pd = r["personal_directions"]
        lines.append(f"生气: {pd.get('shengqi',{}).get('direction','')} | 天医: {pd.get('tianyi',{}).get('direction','')} | 绝命: {pd.get('jueming',{}).get('direction','')}")
        lines.append(f"床位建议: {pd['best_bed_dir']}  书桌建议: {pd['best_desk_dir']}")
        lines.append(f"个人财位: {pd['wealth_spot']}  健康位: {pd['health_spot']}")
        lines.append("")

    lines.append(f"年度总结: {fs['annual_summary']}")
    return "\n".join(lines)
