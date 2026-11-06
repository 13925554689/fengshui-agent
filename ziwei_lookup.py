"""
紫微斗数 v4.0 解读数据集 — 精确查找表（零训练）。

数据: Renhuai123/ziwei-doushu v4.0 解读数据集, CC BY 4.0（引用须注明来源）。
覆盖: 1950-2026 公历每个真实日期 × 12时辰 × 男女, 每盘 13 维解读约 3 万字。
口径 (README 二·新): 钟表时; 时辰序号 子=0…亥=11;
晚子时(23:00-23:59)按次日排盘、时辰取 0; 早子时(00:00-00:59)按当日、时辰取 0。
已知坑: 数据集混入不存在日期(2/30、非闰年2/29)的假样本, 查询前用 datetime 校验过滤。
"""

import datetime as _dt
import io
import json

import zstandard

from pathlib import Path

DATA_DIR = Path(r"D:/ziwei-doushu/data")
YEAR_MIN, YEAR_MAX = 1950, 2026

DIMS = ["overview", "personality", "love", "career", "wealth", "health",
        "family", "children", "move", "friends", "home", "spirit", "parents"]

# 中文名跟数据集正文实际标题走（family 正文是【兄弟总览】等, 2026-11-06 逐维核对）
DIM_CN = {
    "overview": "命格总览", "personality": "性格", "love": "感情", "career": "事业",
    "wealth": "财运", "health": "健康", "family": "兄弟", "children": "子女",
    "move": "迁移", "friends": "人际", "home": "田宅", "spirit": "福德",
    "parents": "父母",
}

SOURCE_TAG = "来源 ziwei-doushu v4.0 (github.com/Renhuai123/ziwei-doushu), CC BY 4.0"


def hour_to_seq(hour: int) -> int:
    """钟表小时 0-23 → 数据集时辰序号 0-11（子=0 含 23 点起）"""
    return (hour + 1) // 2 % 12


def _norm_gender(g) -> str:
    s = str(g).strip().lower()
    if s in ("male", "男", "1", "m"):
        return "male"
    if s in ("female", "女", "0", "f"):
        return "female"
    raise ValueError(f"性别无法识别: {g} (male/female/男/女)")


def lookup_ziwei_reading(year, month, day, hour, gender, dim="overview"):
    """按出生信息精确命中 v4.0 数据集解读, 返回指定维度文本。

    # ponytail: 每次流式解压全年文件线性匹配(~3-6s), 够用;
    # 高频调用再建 k→offset 索引
    """
    try:
        g = _norm_gender(gender)
        hour = int(hour)
        if not (0 <= hour <= 23):
            raise ValueError(f"hour 须为 0-23 钟表小时, 得到 {hour}")
        if dim not in DIMS and dim != "all":
            return f"(维度 {dim} 不存在, 可用: {', '.join(DIMS + ['all'])})"
        year, month, day = int(year), int(month), int(day)
        birth = _dt.date(year, month, day)  # 不存在日期(2/30等假样本)直接抛错
    except (TypeError, ValueError, OverflowError) as e:
        return f"(输入错误: {e} — 请核对出生日期真实存在)"

    if hour == 23:  # 晚子时按次日排盘(README 二·新口径)
        birth += _dt.timedelta(days=1)
    if not (YEAR_MIN <= birth.year <= YEAR_MAX):
        return f"(年份 {birth.year} 超出数据集覆盖范围 {YEAR_MIN}-{YEAR_MAX})"

    path = DATA_DIR / f"year-{birth.year}.jsonl.zst"
    if not path.exists():
        return f"(数据文件缺失: {path.name})"

    seq = hour_to_seq(hour)
    key = f"{birth.year:04d}-{birth.month:02d}-{birth.day:02d}-{seq}-{g}"
    tag = "晚子时按次日排盘" if hour == 23 else f"时辰序号{seq}"
    who = f"{birth} {'男' if g == 'male' else '女'}命 ({tag}; {SOURCE_TAG})"
    dctx = zstandard.ZstdDecompressor()
    with open(path, "rb") as f:
        for line in io.TextIOWrapper(dctx.stream_reader(f), encoding="utf-8"):
            if f'"{key}"' not in line[:64]:  # k 字段在行首, 先粗筛再解析
                continue
            o = json.loads(line)
            if o["k"] == key:
                if dim == "all":
                    # ponytail: 每维前200字总览(~3k字), 13维全量3万字必被工具层8k截断; LLM总览后逐维细取
                    body = "\n\n".join(
                        f"— {DIM_CN[d]}({len(o['c'][d])}字) —\n{o['c'][d][:200]}…"
                        for d in DIMS)
                    return f"【紫微·13维总览】{who}\n{body}"
                return f"【紫微·{DIM_CN[dim]}】{who}\n{o['c'][dim]}"
    return f"(未命中: {key})"


if __name__ == "__main__":
    # 自检: 早子/晚子口径 / 假日期 / 闰年 / 越界 / 维度名 / 类型
    r1 = lookup_ziwei_reading(2026, 1, 1, 0, "male")            # 早子 1/1
    r23 = lookup_ziwei_reading(2026, 1, 1, 23, "male")          # 晚子 → 1/2 的盘
    r2 = lookup_ziwei_reading(2026, 1, 2, 0, "male")            # 早子 1/2
    assert r23.startswith("【紫微·命格总览】") and "(晚子时按次日排盘" in r23
    assert r23.split("\n", 1)[1] == r2.split("\n", 1)[1], "23点盘须等于次日h0盘正文"
    assert r1.split("\n", 1)[1] != r23.split("\n", 1)[1], "1/1早子与1/2盘必须不同"
    assert len(r1) > 3000, r1[:100]
    assert "(输入错误" in lookup_ziwei_reading(2024, 2, 30, 8, "female")
    assert "(输入错误" in lookup_ziwei_reading(2023, 2, 29, 8, "female")
    assert lookup_ziwei_reading(2024, 2, 29, 8, "female").startswith("【紫微")
    assert "(年份 1949" in lookup_ziwei_reading(1949, 1, 1, 8, "male")
    assert "(年份 2027" in lookup_ziwei_reading(2026, 12, 31, 23, "male")  # 跨年晚子
    r_l = lookup_ziwei_reading(2026, 1, 1, 14, "女", dim="love")
    assert r_l.startswith("【紫微·感情】"), r_l[:60]
    r3 = lookup_ziwei_reading(2026, 1, 1, 0, "male", dim="all")
    assert r3.startswith("【紫微·13维总览】") and len(r3) < 8000, (r3[:60], len(r3))
    assert all(DIM_CN[d] in r3 for d in DIMS), "all 模式须含全部13维名"
    assert lookup_ziwei_reading(2026, 1, 1, 0, "male", dim="bogus").startswith("(维度")
    assert lookup_ziwei_reading(None, 1, 1, 0, "male").startswith("(输入错误")
    print("self-check OK:",
          f"overview={len(r1)}ch love={len(r_l)}ch all={len(r3)}ch")
