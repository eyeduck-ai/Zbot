"""
System Router
=============
System-level endpoints for server management.
"""
import os
import asyncio
from fastapi import APIRouter, BackgroundTasks, Request, HTTPException
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["system"])


class ShutdownResponse(BaseModel):
    status: str
    message: str


@router.post("/shutdown", response_model=ShutdownResponse)
async def shutdown_server(request: Request, background_tasks: BackgroundTasks):
    """
    Gracefully shutdown the server.
    
    This endpoint is protected to only allow requests from localhost.
    It initiates a graceful shutdown, allowing the response to be sent
    before the server terminates.
    """
    # Security: Only allow from localhost
    client_host = request.client.host if request.client else None
    if client_host not in ("127.0.0.1", "localhost", "::1"):
        raise HTTPException(
            status_code=403, 
            detail="Shutdown can only be requested from localhost"
        )
    
    async def do_shutdown():
        """Perform shutdown after response is sent."""
        await asyncio.sleep(1)  # Allow response to be sent first
        logger.info("Shutdown requested via API, terminating...")
        os._exit(0)
    
    background_tasks.add_task(do_shutdown)
    logger.info(f"Shutdown request received from {client_host}")
    
    return ShutdownResponse(
        status="shutting_down",
        message="Server will shutdown in 1 second"
    )


@router.get("/idle-status")
async def get_idle_status():
    """
    Get current idle status of the server.
    
    Returns:
        - idle_seconds: Seconds since last meaningful activity
        - timeout_seconds: Configured timeout threshold
        - is_idle: Whether server is currently considered idle
    """
    from app.middleware.idle_tracker import IdleTrackerMiddleware, DEFAULT_IDLE_TIMEOUT_SECONDS
    
    idle_seconds = IdleTrackerMiddleware.get_idle_seconds()
    
    return {
        "idle_seconds": round(idle_seconds, 1),
        "timeout_seconds": DEFAULT_IDLE_TIMEOUT_SECONDS,
        "is_idle": idle_seconds > DEFAULT_IDLE_TIMEOUT_SECONDS
    }
