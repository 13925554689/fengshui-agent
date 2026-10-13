"""
FastAPI 服务 —— 八字命理 AI 的 Web 接口。
支持 SSE 流式响应，可直接嵌入前端。

启动: python app.py
接口: POST /analyze  { "birth": {...}, "question": "..." }
       GET  /health
"""

import json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional

from config import HOST, PORT
from compute import compute_bazi, chart_to_json, chart_to_text
from core import MingLiAgent

app = FastAPI(title="命理AI", description="八字命理分析 Agent", version="1.0.0")

# 全局 Agent 实例（简化版，生产应使用会话管理）
active_agent: Optional[MingLiAgent] = None


# ── Request Models ───────────────────────────────────────────

class BirthInfo(BaseModel):
    year: int
    month: int
    day: int
    hour: int = 0
    minute: int = 0
    sex: int = 1  # 1=男, 0=女
    longitude: Optional[float] = None  # 出生地东经度数，提供则真太阳时校正时柱


class AnalyzeRequest(BaseModel):
    birth: BirthInfo
    question: Optional[str] = None


class ChatRequest(BaseModel):
    message: str


# ── Routes ───────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "name": "命理AI"}


@app.post("/compute")
async def compute_chart(birth: BirthInfo):
    """仅计算命盘，返回 JSON"""
    chart = compute_bazi(birth.year, birth.month, birth.day, 
                         birth.hour, birth.minute, birth.sex,
                         longitude=birth.longitude)
    return chart_to_json(chart)


@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    """完整分析：计算命盘 + AI 解读"""
    chart = compute_bazi(req.birth.year, req.birth.month, req.birth.day,
                         req.birth.hour, req.birth.minute, req.birth.sex,
                         longitude=req.birth.longitude)

    question = req.question or "请全面分析此八字命盘，包括日主强弱、五行平衡、用神建议、大运走势和当前流年分析。"

    # 构建完整输入
    chart_md = chart_to_text(chart)
    full_input = f"{chart_md}\n\n---\n用户问题: {question}"

    agent = MingLiAgent()
    result = agent.analyze(full_input)

    return JSONResponse({
        "chart": chart_to_json(chart),
        "analysis": result,
    })


@app.post("/chat")
async def chat(req: ChatRequest):
    """对话式分析（SSE 流式）"""
    global active_agent

    # 判断是否包含出生信息
    has_birth = any(kw in req.message for kw in ["出生", "生日", "八字", "排盘", "命盘"])

    if has_birth or active_agent is None:
        active_agent = MingLiAgent()

    async def generate():
        for chunk in active_agent.chat_stream(req.message):
            yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/")
async def root():
    """API 说明"""
    return {
        "name": "命理AI — 八字命理分析 Agent",
        "endpoints": {
            "POST /compute": "计算八字命盘 (JSON)",
            "POST /analyze": "完整分析 (命盘 + AI 解读)",
            "POST /chat": "对话式分析 (SSE 流式)",
            "GET /health": "健康检查",
        },
        "example": {
            "compute": {
                "year": 1990, "month": 5, "day": 15,
                "hour": 8, "minute": 0, "sex": 1
            },
            "analyze": {
                "birth": {"year": 1990, "month": 5, "day": 15, "hour": 8, "sex": 1},
                "question": "请全面分析"
            }
        }
    }


# ── CLI 模式 ─────────────────────────────────────────────────

def cli_mode():
    """命令行交互模式"""
    print("\n" + "=" * 50)
    print("   🔮 命理AI — 八字命理分析 Agent")
    print("=" * 50)
    print("输入出生信息开始，格式: 年 月 日 时 性别(1男0女) [东经度]，如: 1990 5 15 8 1 116.4")
    print("例如: 1990 5 15 8 1")
    print("直接输入问题可对已排盘追问")
    print("输入 /new 重新排盘, /quit 退出")
    print("=" * 50 + "\n")

    agent = None
    
    while True:
        try:
            user_input = input("\n💬 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见!")
            break

        if not user_input:
            continue
        if user_input == "/quit":
            print("再见!")
            break
        if user_input == "/new":
            agent = None
            print("已重置，请输入新的出生信息。")
            continue

        # 检测出生信息: 数字开头
        parts = user_input.split()
        if parts[0].isdigit() and len(parts) >= 4:
            try:
                y, m, d, h = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
                sex = int(parts[4]) if len(parts) > 4 else 1
                lon = float(parts[5]) if len(parts) > 5 else None  # 可选: 东经度
                if lon is not None and not (-180 <= lon <= 180):
                    print(f"⚠ 经度 {lon} 超出 [-180,180]，忽略校正")
                    lon = None
                chart = compute_bazi(y, m, d, h, 0, sex, longitude=lon)
                chart_md = chart_to_text(chart)
                print(f"\n{chart_md}")

                agent = MingLiAgent()
                question = "请全面分析此八字命盘，包括日主强弱、五行平衡、用神建议、大运走势和当前流年分析。"
                full_input = f"{chart_md}\n\n---\n用户问题: {question}"
                print("\n⏳ 分析中...\n")
                result = agent.analyze(full_input)
                print(result)
                continue
            except (ValueError, OverflowError):  # ponytail: inf/1e308 走 OverflowError, 与非法输入同路回落
                pass

        # 追问模式
        if agent is None:
            print("请先输入出生信息（年 月 日 时 性别）。")
            continue

        print("\n⏳ 分析中...\n")
        result = agent.analyze(user_input)
        print(result)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--serve":
        import uvicorn
        uvicorn.run(app, host=HOST, port=PORT)
    else:
        cli_mode()
