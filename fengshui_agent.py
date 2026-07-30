"""
传统风水智能体 — Python 计算引擎包装器
整合 suangua 核心：八字排盘 + 玄空飞星 + 八宅 + 命卦
"""
import sys, json
from datetime import datetime
from pathlib import Path

# Ensure suangua core is importable
sys.path.insert(0, str(Path(__file__).parent / "suangua"))

from core.bazi.chart import build_chart
from core.bazi.analyzer import annotate_pillars, calculate_strength, detect_pattern, find_shensha, analyze_chart
from core.fengshui.calculator import (
    calculate_ming_gua, get_house_gua, check_compatibility,
    get_ming_gua_group, get_house_group, DIRECTION_GUA
)
from core.fengshui.flying_stars import (
    calculate_annual_flying_stars, get_personal_directions,
    comprehensive_fengshui_analysis, NINE_STARS
)
from core.constants import TIANGAN_WUXING, DIZHI_WUXING, WUXING, SHISHEN


def bazi_analysis(year: int, month: int, day: int, hour: int, minute: int = 0) -> dict:
    """八字排盘 + 全面分析"""
    chart = build_chart(year, month, day, hour, minute)
    annotate_pillars(chart)
    strength = calculate_strength(chart)
    pattern = detect_pattern(chart)
    shensha = find_shensha(chart)
    full = analyze_chart(chart)

    return {
        "birth": f"{year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}",
        "day_master": chart["day_master"],
        "day_master_wuxing": chart["day_master_wuxing"],
        "pillars": {
            pk: {
                "ganzhi": f"{chart[pk]['tiangan']}{chart[pk]['dizhi']}",
                "tiangan": chart[pk]["tiangan"],
                "dizhi": chart[pk]["dizhi"],
                "shishen_gan": chart[pk].get("shishen_gan", ""),
                "shishen_zhi": chart[pk].get("shishen_zhi", ""),
                "canggan": chart[pk].get("canggan", []),
                "nayin": chart[pk].get("nayin", ""),
            }
            for pk in ["year_pillar", "month_pillar", "day_pillar", "hour_pillar"]
        },
        "strength": strength["strength"],
        "deling": strength["deling"],
        "monthly_status": strength["monthly_status"],
        "pattern": pattern.get("pattern", ""),
        "shensha": [{"name": s["name"], "pillar": s.get("pillar", "")} for s in shensha],
        "wuxing_scores": full.get("wuxing_scores", {}),
        "dayun": full.get("dayun", {}),
        "liunian": full.get("liunian", {}),
    }


def ming_gua_analysis(birth_year: int, gender: str) -> dict:
    """命卦分析"""
    gua = calculate_ming_gua(birth_year, gender)
    group = get_ming_gua_group(gua)
    directions = get_personal_directions(gua)

    return {
        "birth_year": birth_year,
        "gender": gender,
        "ming_gua": gua,
        "group": group,
        "personal_directions": directions,
    }


def house_fengshui_analysis(
    facing: str,
    birth_years: list[tuple[int, str]],  # [(year, gender), ...]
    analysis_year: int = None,
) -> dict:
    """综合阳宅风水分析"""
    from datetime import date
    year = analysis_year or date.today().year

    house_gua = get_house_gua(facing)
    house_group = get_house_group(house_gua)
    annual_fs = calculate_annual_flying_stars(year)

    residents = []
    for by, gender in birth_years:
        mg = calculate_ming_gua(by, gender)
        mg_group = get_ming_gua_group(mg)
        compat = check_compatibility(mg, house_gua)
        personal_dirs = get_personal_directions(mg)

        residents.append({
            "birth_year": by,
            "gender": gender,
            "ming_gua": mg,
            "ming_gua_group": mg_group,
            "compatibility": compat,
            "personal_directions": personal_dirs,
        })

    return {
        "year": year,
        "facing": facing,
        "house_gua": house_gua,
        "house_group": house_group,
        "annual_flying_stars": {
            "center_star": annual_fs["center_star"],
            "center_star_name": annual_fs["center_star_name"],
            "wealth_direction": annual_fs["wealth_direction"],
            "study_direction": annual_fs["study_direction"],
            "five_yellow_direction": annual_fs["five_yellow_direction"],
            "two_black_direction": annual_fs["two_black_direction"],
            "romance_direction": annual_fs["romance_direction"],
            "auspicious_directions": annual_fs["auspicious_directions"],
            "inauspicious_directions": annual_fs["inauspicious_directions"],
            "annual_summary": annual_fs["annual_summary"],
        },
        "residents": residents,
    }


def full_property_analysis(
    facing: str,
    birth_years: list[tuple[int, str]],
    bazi_list: list[dict],  # [{year, month, day, hour, minute}, ...]
    analysis_year: int = None,
) -> dict:
    """完整房产风水分析 = 宅运 + 命卦 + 八字 + 飞星"""
    house = house_fengshui_analysis(facing, birth_years, analysis_year)

    bazi_results = []
    for b in bazi_list:
        bazi_results.append(bazi_analysis(
            b["year"], b["month"], b["day"],
            b.get("hour", 12), b.get("minute", 0)
        ))

    # Cross-reference: which residents' lucky directions overlap with annual good sectors
    synergy_analysis = _build_synergy_analysis(house, bazi_results)

    return {
        "house": house,
        "bazi": bazi_results,
        "synergy_analysis": synergy_analysis,
    }


def _build_synergy_analysis(house: dict, bazi_list: list[dict]) -> dict:
    """合参分析：八字五行喜忌 × 宅运飞星 × 个人命卦吉方"""
    annual_fs = house["annual_flying_stars"]
    residents = house["residents"]

    recommendations = []
    for i, resident in enumerate(residents):
        pd = resident["personal_directions"]
        mg = resident["ming_gua"]

        # Check if personal wealth spot overlaps with annual wealth direction
        if pd.get("wealth_spot"):
            rec = {
                "resident_index": i,
                "ming_gua": mg,
                "personal_wealth": pd["wealth_spot"],
                "annual_wealth": annual_fs["wealth_direction"],
                "wealth_overlap": pd["wealth_spot"] == annual_fs["wealth_direction"],
                "bed_direction": pd.get("best_bed_dir", ""),
                "desk_direction": pd.get("best_desk_dir", ""),
                "avoid_direction": pd.get("jueming", {}).get("direction", ""),
            }
            recommendations.append(rec)

    # Cross-check with BaZi wuxing needs
    wuxing_advice = []
    if bazi_list:
        for i, bz in enumerate(bazi_list):
            dm_wx = bz["day_master_wuxing"]
            strength = bz["strength"]
            wuxing_advice.append({
                "resident_index": i,
                "day_master": bz["day_master"],
                "wuxing": dm_wx,
                "strength": strength,
                "favorable_elements": _get_favorable_wuxing(dm_wx, strength),
            })

    return {
        "recommendations": recommendations,
        "wuxing_advice": wuxing_advice,
    }


def _get_favorable_wuxing(day_master_wx: str, strength: str) -> list[str]:
    """根据日主五行和强弱，推算喜用神五行"""
    wxs = ["木", "火", "土", "金", "水"]
    dm_idx = wxs.index(day_master_wx)

    if strength == "身强":
        # 身强喜克泄耗：我生(食伤) + 克我(官杀) + 我克(财)
        return [wxs[(dm_idx + 1) % 5], wxs[(dm_idx + 2) % 5], wxs[(dm_idx + 3) % 5]]
    else:
        # 身弱喜生扶：生我(印) + 同我(比劫)
        return [wxs[(dm_idx - 1) % 5], wxs[dm_idx]]


# ── CLI entry ──
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="传统风水智能体")
    sub = ap.add_subparsers(dest="cmd")

    # bazi
    bazi_p = sub.add_parser("bazi")
    bazi_p.add_argument("--year", type=int, required=True)
    bazi_p.add_argument("--month", type=int, required=True)
    bazi_p.add_argument("--day", type=int, required=True)
    bazi_p.add_argument("--hour", type=int, default=12)
    bazi_p.add_argument("--minute", type=int, default=0)

    # minggua
    mg_p = sub.add_parser("minggua")
    mg_p.add_argument("--year", type=int, required=True)
    mg_p.add_argument("--gender", choices=["male", "female", "男", "女"], required=True)

    # house
    house_p = sub.add_parser("house")
    house_p.add_argument("--facing", required=True)
    house_p.add_argument("--residents", required=True, help="JSON: [[year,gender],...]")
    house_p.add_argument("--year", type=int, default=None)

    args = ap.parse_args()

    if args.cmd == "bazi":
        r = bazi_analysis(args.year, args.month, args.day, args.hour, args.minute)
    elif args.cmd == "minggua":
        r = ming_gua_analysis(args.year, args.gender)
    elif args.cmd == "house":
        residents = json.loads(args.residents)
        r = house_fengshui_analysis(args.facing, residents, args.year)
    else:
        r = {"error": "unknown command"}

    print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
