"""
ERICKsky Signal Engine - API Server
FastAPI server for accessing signal bot status and triggering manual scans.
"""

import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Initialize FastAPI app
app = FastAPI(
    title="ERICKsky Signal Engine API",
    description="API for accessing signal bot status and managing signals",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic models
class SignalRequest(BaseModel):
    pair: str
    force_session: bool = False

class SignalResponse(BaseModel):
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str = "1.0.0"

class BotStatusResponse(BaseModel):
    running: bool
    last_scan: Optional[str] = None
    pairs: List[str] = []
    uptime_seconds: Optional[int] = None


@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint - API info."""
    return {
        "name": "ERICKsky Signal Engine API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs"
    }


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@app.get("/api/v1/status", response_model=BotStatusResponse)
async def get_status():
    """Get signal bot status."""
    try:
        from database.db_manager import db
        from database.repositories import BotStateRepository

        db.initialize()

        running = BotStateRepository.get("bot_running") == "true"
        last_scan = BotStateRepository.get("last_scan_at")

        pairs_str = os.getenv("TRADING_PAIRS", "EURUSD,GBPUSD,XAUUSD,AUDUSD")
        pairs = [p.strip() for p in pairs_str.split(",") if p.strip()]

        return BotStatusResponse(
            running=running,
            last_scan=last_scan,
            pairs=pairs,
            uptime_seconds=None
        )
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/scan", response_model=SignalResponse)
async def trigger_scan(request: SignalRequest, background_tasks: BackgroundTasks):
    """Trigger a manual scan for a specific pair."""
    try:
        from tasks.scan_pair import scan_pair

        # Run in background via Celery
        scan_pair.delay(
            pair=request.pair,
            force_session=request.force_session
        )

        return SignalResponse(
            status="success",
            message=f"Scan triggered for {request.pair}",
            data={"pair": request.pair, "queued": True}
        )
    except Exception as e:
        logger.error(f"Error triggering scan: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/signals")
async def get_signals(limit: int = 50, pair: Optional[str] = None):
    """Get recent signals from database."""
    try:
        from database.db_manager import db
        from database.repositories import SignalRepository

        db.initialize()

        if pair:
            signals = SignalRepository.get_by_pair(pair, limit=limit)
        else:
            signals = SignalRepository.get_recent(limit=limit)

        return {
            "status": "success",
            "count": len(signals),
            "signals": signals
        }
    except Exception as e:
        logger.error(f"Error getting signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/signals/scan-all", response_model=SignalResponse)
async def scan_all(background_tasks: BackgroundTasks):
    """Trigger scan for all pairs."""
    try:
        from tasks.scan_pair import scan_all_pairs

        scan_all_pairs.delay()

        return SignalResponse(
            status="success",
            message="Scan triggered for all pairs",
            data={"queued": True}
        )
    except Exception as e:
        logger.error(f"Error triggering all scan: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
