from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

# from app.core.logger import setup_logging
# from app.routers import vgh # Removed in cleanup
from app.routers import auth, tasks
# import app.plugins # Removed: integrated into tasks module
from app.core.logger import logger
from app.auth.service import set_cached_role_permissions

app = FastAPI()

# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global Exception: {exc}", exc_info=True)
    
    # Send Alert
    from app.core.alert import AlertService
    await AlertService.send_exception_alert(exc, context=f"URL: {request.url}")
    
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "Internal Server Error", "detail": str(exc)},
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "message": exc.detail},
    )

@app.on_event("startup")
async def startup_event():
    logger.info("Application startup")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutdown")

# app.include_router(vgh.router)
app.include_router(auth.router)
app.include_router(tasks.router)

# Lookup API (醫師查詢等)
from app.core.lookup import router as lookup_router
app.include_router(lookup_router)

# Sheets API (刀表設定)
from app.routers.sheets import router as sheets_router
app.include_router(sheets_router)

# Report API (回報/升等)
from app.routers.report import router as report_router
app.include_router(report_router)

# Templates API (手術模板)
from app.routers.templates import router as templates_router
app.include_router(templates_router)

# Frontend Error API (前端錯誤回報)
from app.routers.frontend_error import router as frontend_error_router
app.include_router(frontend_error_router)

# Stats API (任務統計)
from app.routers.stats import router as stats_router
app.include_router(stats_router)

# Config API (環境設定)
from app.routers.config import router as config_router
app.include_router(config_router)

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# RLS Context Middleware - 自動從請求提取 JWT 供 Supabase RLS 使用
from app.middleware.rls_context import RLSContextMiddleware
app.add_middleware(RLSContextMiddleware)

@app.get("/health")
def read_root():
    return {"status": "ok"}

@app.get("/api/test-supabase")
def test_supabase():
    from app.supabase.client import get_supabase_client
    try:
        client = get_supabase_client()
        # Ping Supabase by selecting from users (limit 1)
        # Assuming table exists. If not, this might fail, which is good for test.
        response = client.table("users").select("count", count="exact").execute()
        return {"status": "ok", "data": response.data, "count": response.count}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/status")
async def get_system_status():
    """
    系統狀態檢查 (公開端點，供登入頁面使用)
    
    Returns:
        intranet: 內網連線狀態 (ok/error)
        database: 資料庫連線狀態 (ok/error)
    """
    import asyncio
    import httpx
    
    async def check_intranet():
        """檢查內網連線 (使用 HEAD 請求更快)"""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.head("https://eip.vghtpe.gov.tw/login.php")
                return {"status": "ok" if resp.status_code == 200 else "error"}
        except Exception:
            return {"status": "error"}
    
    # 資料庫連線狀態: role_definitions 只查詢一次，連線狀態每次輕量檢查
    global _db_verified, _cached_role_definitions
    
    async def check_database():
        """檢查資料庫連線 (輕量 ping)"""
        try:
            from app.db.client import get_supabase_client
            import httpx
            client = get_supabase_client()
            # 使用 HEAD 請求輕量檢查 Supabase REST API 是否可達
            async with httpx.AsyncClient(timeout=3.0) as http_client:
                # 只檢查連線，不實際查詢資料
                resp = await http_client.head(f"{client.supabase_url}/rest/v1/")
                return {"status": "ok" if resp.status_code < 500 else "error"}
        except Exception:
            return {"status": "error"}
    
    async def fetch_role_definitions():
        """取得角色定義 (首次查詢後快取)"""
        global _db_verified, _cached_role_definitions
        
        # 已有快取，直接返回
        if _cached_role_definitions is not None:
            return _cached_role_definitions
        
        try:
            from app.db.client import get_supabase_client
            client = get_supabase_client()
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                lambda: client.table("settings").select("value").eq("key", "role_definitions").execute()
            )
            
            role_definitions = {}
            if result.data and len(result.data) > 0:
                role_data = result.data[0].get("value", {})
                role_definitions = role_data.get("roles", {})
            
            _db_verified = True
            _cached_role_definitions = role_definitions  # 快取結果
            
            # 快取角色權限定義 (讓 check_task_permission 使用)
            if role_definitions:
                set_cached_role_permissions(role_definitions)
                logger.info(f"Cached role_definitions: {list(role_definitions.keys())}")
            
            return role_definitions
        except Exception:
            return _cached_role_definitions or {}
    
    # 平行執行三個檢查
    intranet_result, database_result, role_definitions = await asyncio.gather(
        check_intranet(),
        check_database(),
        fetch_role_definitions()
    )
    
    return {
        "intranet": intranet_result,
        "database": database_result,
        "role_definitions": role_definitions
    }

# 資料庫首次驗證標記
_db_verified = False
_cached_role_definitions = None  # role_definitions 快取（只查詢一次）


# --- Frontend Integration ---
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

# Determine path to 'dist' (Frontend build)
# In development: ../frontend/dist
# In PyInstaller bundle: sys._MEIPASS/frontend/dist (Usually)
# We need robust path detection.

# Simple check for now:
# If running mainly as dev:
frontend_dist = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "dist")

# If bundled (sys._MEIPASS logic will be added later or we check existence)
import sys
if getattr(sys, 'frozen', False):
    # PyInstaller creates a temp folder and stores path in _MEIPASS
    base_path = sys._MEIPASS
    frontend_dist = os.path.join(base_path, "frontend", "dist")

if os.path.exists(frontend_dist):
    # Mount assets
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")
    
    # Catch-all for SPA
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Allow API requests to pass through (FastAPI matches specific routes first, but path params match all?)
        # Actually API routes defined ABOVE will be matched first.
        # But we need to exclude /api just in case of 404s inside API which we don't want returning HTML.
        if full_path.startswith("api"):
            return {"error": "API route not found"}
            
        # Check if file exists (e.g. favicon.ico)
        file_path = os.path.join(frontend_dist, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
            
        # Default to index.html
        return FileResponse(os.path.join(frontend_dist, "index.html"))
else:
    print(f"Warning: Frontend build not found at {frontend_dist}. Running API only.")
