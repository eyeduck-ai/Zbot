"""
Idle Tracker Middleware
=======================
Tracks the last meaningful user activity to enable automatic server shutdown
after a period of inactivity.

Excluded paths (polling endpoints that don't count as "activity"):
- GET /api/tasks/jobs
- GET /api/status
- GET /health

Only meaningful interactions (POST/PUT/DELETE or specific GETs) reset the timer.
"""
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


# Default: 30 minutes (can be overridden from settings)
DEFAULT_IDLE_TIMEOUT_SECONDS = 1800

# Paths that don't count as user activity (polling endpoints)
EXCLUDED_PATHS = [
    "/api/tasks/jobs",
    "/api/status", 
    "/health",
    "/favicon.ico",
]


class IdleTrackerMiddleware(BaseHTTPMiddleware):
    """Middleware to track user activity for idle timeout detection."""
    
    # Class-level last activity timestamp (shared across instances)
    last_activity: float = time.time()
    
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method
        
        # Only non-polling requests reset the activity timer
        is_excluded = any(path.startswith(ep) for ep in EXCLUDED_PATHS)
        is_meaningful = method in ("POST", "PUT", "DELETE", "PATCH")
        
        if is_meaningful or (method == "GET" and not is_excluded):
            IdleTrackerMiddleware.last_activity = time.time()
        
        response = await call_next(request)
        return response
    
    @classmethod
    def get_idle_seconds(cls) -> float:
        """Get seconds since last meaningful activity."""
        return time.time() - cls.last_activity
    
    @classmethod
    def is_idle(cls, timeout_seconds: float = DEFAULT_IDLE_TIMEOUT_SECONDS) -> bool:
        """Check if server has been idle for longer than timeout."""
        return cls.get_idle_seconds() > timeout_seconds
