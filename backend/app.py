"""FastAPI server for Kintsugi.

Thin HTTP layer over the `dqi` library. Enforces input caps + per-IP rate
limiting, never logs raw data (only shapes and codes), and returns clean JSON
errors.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

load_dotenv()

import dqi
from dqi import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("dqi.api")

DEMOS_DIR = Path(__file__).resolve().parent / "data" / "demos"

DEMOS = {
    "clean": {
        "id": "clean",
        "name": "Clean dataset",
        "description": "A well-behaved dataset that should score an A/B.",
        "file": "clean.csv",
        "target": "churned",
    },
    "messy": {
        "id": "messy",
        "name": "Messy dataset",
        "description": "Missingness, duplicates, a constant column, outliers, and class imbalance.",
        "file": "messy.csv",
        "target": "converted",
    },
    "leaky": {
        "id": "leaky",
        "name": "Leaky dataset",
        "description": "Contains an obvious target-leakage column — should score an F.",
        "file": "leaky.csv",
        "target": "defaulted",
    },
}

# ---------------------------------------------------------------------------
# Tiny in-memory per-IP rate limiter: 20 analyses / IP / hour.
# ---------------------------------------------------------------------------
RATE_LIMIT = 20
RATE_WINDOW_SECS = 3600
_hits: dict[str, deque[float]] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_rate_limit(request: Request) -> None:
    ip = _client_ip(request)
    now = time.time()
    q = _hits[ip]
    while q and now - q[0] > RATE_WINDOW_SECS:
        q.popleft()
    if len(q) >= RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit reached ({RATE_LIMIT} analyses/hour). Please try again later.",
        )
    q.append(now)


app = FastAPI(title="Kintsugi", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your Vercel domain in production
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/health")
def health():
    return {"status": "ok", "ai_configured": dqi_ai_configured()}


def dqi_ai_configured() -> bool:
    try:
        from dqi.ai import groq_client

        return groq_client.is_configured()
    except Exception:
        return False


@app.get("/demos")
def list_demos():
    return {
        "demos": [
            {
                "id": d["id"],
                "name": d["name"],
                "description": d["description"],
                "suggested_target": d["target"],
            }
            for d in DEMOS.values()
        ]
    }


@app.post("/analyze")
async def analyze_upload(
    request: Request,
    file: UploadFile = File(...),
    target: Optional[str] = Form(None),
):
    _check_rate_limit(request)
    try:
        raw = await file.read()
        name = file.filename or "uploaded.csv"
        target_clean = (target or "").strip() or None
        report = dqi.analyze_csv_bytes(raw, name, target_clean)
        return report.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("analyze failed: %s", type(exc).__name__)
        raise HTTPException(status_code=500, detail="Analysis failed. Please try a different file.")


class DemoRequest(BaseModel):
    demo_id: str
    target: Optional[str] = None


@app.post("/analyze/demo")
def analyze_demo(req: DemoRequest, request: Request):
    _check_rate_limit(request)
    demo = DEMOS.get(req.demo_id)
    if not demo:
        raise HTTPException(status_code=404, detail=f"Unknown demo '{req.demo_id}'.")
    path = DEMOS_DIR / demo["file"]
    if not path.exists():
        raise HTTPException(
            status_code=500,
            detail="Demo data missing. Run `python make_demos.py` in the backend.",
        )
    try:
        raw = path.read_bytes()
        target = req.target if req.target is not None else demo["target"]
        target = (target or "").strip() or None
        report = dqi.analyze_csv_bytes(raw, demo["name"], target)
        return report.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("analyze_demo failed: %s", type(exc).__name__)
        raise HTTPException(status_code=500, detail="Analysis failed.")
