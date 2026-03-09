"""
PII Redactor — x402 FastAPI Service
Powered by Microsoft Presidio
"""

import logging
import os
import time
from collections import Counter
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import RecognizerResult
from pydantic import BaseModel, Field, validator

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PAYMENT_REQUIRED = os.getenv("PAYMENT_REQUIRED", "true").lower() == "true"
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "0x0000000000000000000000000000000000000000")
VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("pii-redactor")

# ---------------------------------------------------------------------------
# Presidio engines (initialised once at startup)
# ---------------------------------------------------------------------------

analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class TextRequest(BaseModel):
    texts: List[str] = Field(..., min_items=1, max_items=10)
    language: str = Field(default="en")
    entities: Optional[List[str]] = None

    @validator("texts", each_item=True)
    def check_length(cls, v):
        if len(v) > 5000:
            raise ValueError("Each text must be 5000 characters or fewer.")
        return v


class EntityCount(BaseModel):
    entity_type: str
    count: int


class RedactResult(BaseModel):
    redacted_text: str
    original_length: int
    entities_found: List[EntityCount]


class RedactMeta(BaseModel):
    total_entities_redacted: int
    processing_time_ms: float


class RedactResponse(BaseModel):
    results: List[RedactResult]
    meta: RedactMeta


class EntityDetail(BaseModel):
    entity_type: str
    text: str
    start: int
    end: int
    score: float


class AnalyzeResult(BaseModel):
    entities: List[EntityDetail]


class AnalyzeResponse(BaseModel):
    results: List[AnalyzeResult]


# ---------------------------------------------------------------------------
# x402 payment middleware
# ---------------------------------------------------------------------------

X402_RESPONSE = {
    "x402Version": 1,
    "accepts": [
        {
            "scheme": "exact",
            "network": "eip155:8453",
            "maxAmountRequired": "10000",
            "resource": "https://pii-redactor.up.railway.app/api/redact",
            "description": "PII redaction",
            "mimeType": "application/json",
            "payTo": WALLET_ADDRESS,
            "maxTimeoutSeconds": 300,
            "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            "extra": {"name": "USDC", "decimals": 6},
        }
    ],
}


async def payment_middleware(request: Request, call_next):
    if PAYMENT_REQUIRED and request.url.path.startswith("/api/"):
        payment_header = request.headers.get("X-Payment")
        if not payment_header:
            logger.info("402 — missing X-Payment header for %s", request.url.path)
            return JSONResponse(status_code=402, content=X402_RESPONSE)
    return await call_next(request)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="PII Redactor",
    description="x402 PII redaction API for AI agents — powered by Microsoft Presidio",
    version=VERSION,
)

app.middleware("http")(payment_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    return {"status": "ok", "version": VERSION}


@app.post("/api/redact", response_model=RedactResponse)
async def redact(body: TextRequest):
    start = time.time()
    results: List[RedactResult] = []
    total_entities = 0

    for text in body.texts:
        analyzer_results = analyzer.analyze(
            text=text,
            language=body.language,
            entities=body.entities,
        )

        # Build entity count summary
        counter = Counter(r.entity_type for r in analyzer_results)
        entities_found = [
            EntityCount(entity_type=et, count=cnt) for et, cnt in counter.items()
        ]
        total_entities += len(analyzer_results)

        # Replace with bracket placeholders
        anonymized = anonymizer.anonymize(
            text=text,
            analyzer_results=analyzer_results,
        )

        results.append(
            RedactResult(
                redacted_text=anonymized.text,
                original_length=len(text),
                entities_found=entities_found,
            )
        )

    elapsed_ms = (time.time() - start) * 1000
    logger.info(
        "redact — %d texts, %d entities, %.1f ms", len(body.texts), total_entities, elapsed_ms
    )

    return RedactResponse(
        results=results,
        meta=RedactMeta(
            total_entities_redacted=total_entities,
            processing_time_ms=round(elapsed_ms, 2),
        ),
    )


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(body: TextRequest):
    start = time.time()
    results: List[AnalyzeResult] = []

    for text in body.texts:
        analyzer_results = analyzer.analyze(
            text=text,
            language=body.language,
            entities=body.entities,
        )

        entities = [
            EntityDetail(
                entity_type=r.entity_type,
                text=text[r.start : r.end],
                start=r.start,
                end=r.end,
                score=round(r.score, 4),
            )
            for r in analyzer_results
        ]

        results.append(AnalyzeResult(entities=entities))

    elapsed_ms = (time.time() - start) * 1000
    logger.info("analyze — %d texts, %.1f ms", len(body.texts), elapsed_ms)

    return AnalyzeResponse(results=results)


if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
