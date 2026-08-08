"""
Harness 端到端验证：传统风水智能体
验证：fengshui_compute + compute + core 集成
"""
import sys, os, json

sys.path.insert(0, r"D:\命理AI模型")

# ── HAR-01: fengshui_compute 独立计算 ──
print("━ HAR-01: fengshui_compute 独立性")
from fengshui_compute import (
    calculate_ming_gua, get_house_gua, check_compatibility,
    get_personal_directions, calculate_annual_flying_stars,
    fengshui_analysis, fengshui_to_text, DIRECTION_GUA,
    get_house_group, get_ming_gua_group,
)

# 综合场景：夫妻选房
result = fengshui_analysis("南", [(1988, "male"), (1990, "female")], 2026)
assert result["house_gua"] == 9, f"BAD: house_gua={result['house_gua']}"
assert result["house_group"] == "东四宅", f"BAD: house_group={result['house_group']}"
assert len(result["residents"]) == 2
assert result["residents"][0]["ming_gua"] == 3  # 1988 male
assert result["residents"][1]["ming_gua"] == 8  # 1990 female
assert "相配" in result["residents"][0]["compatibility"]
assert "不相配" in result["residents"][1]["compatibility"]

fs = result["annual_flying_stars"]
assert fs["year"] == 2026
assert len(fs["layout"]) == 9
assert fs["wealth_direction"]  # 财位
assert fs["five_yellow_direction"]  # 五黄
print("  ✓ 多居住者综合风水分析")

# 单居住者
r1 = fengshui_analysis("北", [(2000, "male")], 2025)
assert len(r1["residents"]) == 1
assert r1["year"] == 2025
print("  ✓ 单居住者 + 指定年份")

# 默认年份
r2 = fengshui_analysis("东", [(1995, "female")])
from datetime import date
assert r2["year"] == date.today().year
print("  ✓ 默认年份=当前年")

# to_text
text = fengshui_to_text(result)
for kw in ["风水分析", "宅命匹配", "居住者", "财位", "五黄"]:
    assert kw in text, f"text missing: {kw}"
print("  ✓ fengshui_to_text 完整")

# ── HAR-02: 八字排盘 (lunar-python) ──
print("\n━ HAR-02: compute.py (八字排盘)")
try:
    from compute import compute_bazi, chart_to_text, chart_to_json
    chart = compute_bazi(1988, 10, 12, 8, 0, 1)

    # 基础字段
    assert chart.ri_gan == "庚", f"BAD: ri_gan={chart.ri_gan}"
    assert chart.ri_zhi == "子", f"BAD: ri_zhi={chart.ri_zhi}"
    assert chart.year.gan_zhi == "戊辰"
    assert chart.month.gan_zhi == "壬戌"
    assert chart.day.gan_zhi == "庚子"
    assert chart.hour.gan_zhi == "庚辰"
    print("  ✓ 四柱排盘正确")

    assert chart.wu_xing_score  # 五行分数
    assert chart.da_yun  # 大运
    assert isinstance(chart.qi_yun_age, int)
    print("  ✓ 五行+大运+起运年龄")

    # JSON/Text 导出
    j = chart_to_json(chart)
    assert j["bazi"]["year"] == "戊辰"
    t = chart_to_text(chart)
    assert "庚子" in t and "偏印" in t
    print("  ✓ JSON/Text 导出正确")
    BAZI_OK = True
except ImportError:
    print("  ⚠ lunar-python 未安装 (仅系统Python)，跳过")
    BAZI_OK = False

# ── HAR-03: 飞星布局完整性 ──
print("\n━ HAR-03: 飞星布局全维度")
from fengshui_compute import ANNUAL_FLYING_STAR_MAP, STAR_NAMES

# 所有9种飞星模式都存在
for i in range(9):
    assert i in ANNUAL_FLYING_STAR_MAP, f"missing flying star map for {i}"
    center, layout = ANNUAL_FLYING_STAR_MAP[i]
    assert len(layout) == 9, f"layout size {i}: {len(layout)}"
    # 1-9各出现一次
    stars = list(layout.values())
    assert sorted(stars) == list(range(1, 10)), f"stars check {i}: {sorted(stars)}"
print("  ✓ 9种飞星模式完整，1-9各出现一次")

# 星名完整性
for i in range(1, 10):
    name, nature, info = STAR_NAMES[i]
    assert len(name) > 0 and len(nature) > 0
    assert "element" in info
print("  ✓ 九星命名+属性完整")

# ── HAR-04: 个人方位完整性 ──
print("\n━ HAR-04: 个人方位")
ALL_DIRECTIONS = {"南", "北", "东", "西", "东南", "西南", "东北", "西北"}
for mg in [1, 2, 3, 4, 6, 7, 8, 9]:
    pd = get_personal_directions(mg)
    dirs = set()
    for k in ["shengqi", "tianyi", "niannian", "fuwei", "jueming", "wugui", "liusha", "huohai"]:
        d = pd[k]["direction"]
        dirs.add(d)
    missing = ALL_DIRECTIONS - dirs
    if missing:
        print(f"  ⚠ 命卦{mg}缺少方位: {missing}")
    assert dirs == ALL_DIRECTIONS, f"mg={mg}: dirs={dirs} ≠ {ALL_DIRECTIONS}"
print("  ✓ 8种命卦×8方位 = 完整覆盖")

# ── HAR-05: 边界case ──
print("\n━ HAR-05: 边界case")
# 极端年份
for y in [1900, 2023, 2026]:
    r = calculate_ming_gua(y, "male")
    assert 1 <= r <= 9, f"MG {y} out of range: {r}"
print("  ✓ 极端年份命卦不越界")

# 所有朝向
for d in DIRECTION_GUA:
    g = get_house_gua(d)
    assert 1 <= g <= 9
    assert get_house_group(g) in ["东四宅", "西四宅"]
print("  ✓ 8朝向宅卦+分类")

# 未知朝向default
assert get_house_gua("火星") == 9
print("  ✓ 未知朝向默认9(离)")

# ── HAR-06: 结构检查 ──
print("\n━ HAR-06: 模块结构")
files = [
    r"D:\命理AI模型\fengshui_compute.py",
    r"D:\命理AI模型\core.py",
    r"D:\命理AI模型\compute.py",
    r"D:\命理AI模型\app.py",
    r"D:\命理AI模型\config.py",
    r"D:\命理AI模型\knowledge\fengshui.md",
    r"D:\命理AI模型\knowledge\yangzhai.md",
]
for f in files:
    assert os.path.exists(f), f"missing: {f}"
print("  ✓ 7个核心文件全部存在")

# 导入链 (只检查fengshui_compute，不触发openai)
import ast
with open(r"D:\命理AI模型\core.py", encoding='utf-8') as f:
    core_ast = ast.parse(f.read())

imports = set()
for n in ast.walk(core_ast):
    if isinstance(n, ast.ImportFrom) and n.module:
        imports.add(n.module)
assert 'fengshui_compute' in imports, "core.py 缺少 fengshui_compute 导入"
print("  ✓ core.py → fengshui_compute 导入链正确")

# ── 总结 ──
print(f"\n{'='*50}")
print(f"HARNESS VERIFICATION: {6 if BAZI_OK else 5}/6 模块")
print("  HAR-01 fengshui_compute ✓")
print(f"  HAR-02 compute (lunar-python) {'✓' if BAZI_OK else '⚠ 跳过(lunar-python未安装)'}")
print("  HAR-03 飞星布局 ✓")
print("  HAR-04 个人方位 ✓")
print("  HAR-05 边界case ✓")
print("  HAR-06 模块结构 ✓")
print("STATUS: PASSED")
