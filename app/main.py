"""FastAPI application — Merchant Agents API server."""

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse
from starlette.formparsers import MultiPartParser

from app.config import config
from app.models.schemas import ChatRequest, ChatResponse
from app.tools.database import init_db, get_sessions, get_session, save_session
from app.utils.streaming import sse_manager
from app.utils.logger import logger
from app.graph.workflow import run_orchestrator

# Allow large file uploads (videos up to 500MB)
# Starlette defaults to 1MB per part — monkey-patch for video support
_original_init = MultiPartParser.__init__
def _patched_init(self, headers, stream, *, max_files=1000, max_fields=1000, max_part_size=500*1024*1024, **kwargs):
    _original_init(self, headers, stream, max_files=max_files, max_fields=max_fields, max_part_size=max_part_size, **kwargs)
MultiPartParser.__init__ = _patched_init


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    import os as _os
    # Ensure data directories exist (Render.com / fresh deployments)
    _base = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    _os.makedirs(_os.path.join(_base, "data", "uploads"), exist_ok=True)
    logger.info("Initializing database...")
    await init_db()
    logger.info(f"Server starting on {config.HOST}:{config.PORT}")
    yield
    logger.info("Server shutting down.")


app = FastAPI(
    title="商家集合 Agent",
    description="一句话调用所有 Agent：文案/封面/数据/订单/短视频脚本/短视频分析",
    version="0.1.0",
    lifespan=lifespan,
)

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index():
    """Serve the main HTML page."""
    return FileResponse("static/index.html")


@app.post("/api/upload/reference")
async def upload_reference(file: UploadFile = File(...)):
    """Upload a file. Images go to CDN, videos stored locally (fast)."""
    import os, uuid as _uuid, aiofiles

    try:
        contents = await file.read()
        file_size_mb = len(contents) / (1024 * 1024)
        filename = file.filename or "file"
        content_type = file.content_type or "application/octet-stream"
        logger.info(f"Upload: {filename}, size={file_size_mb:.1f}MB, type={content_type}")

        is_video = content_type.startswith("video/") or any(
            filename.lower().endswith(ext) for ext in (".mp4", ".mov", ".avi", ".webm", ".mkv")
        )

        if is_video:
            # Store video locally — instant, no network dependency
            upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "uploads")
            os.makedirs(upload_dir, exist_ok=True)
            safe_name = f"{_uuid.uuid4().hex[:8]}_{filename}"
            filepath = os.path.join(upload_dir, safe_name)
            async with aiofiles.open(filepath, "wb") as f:
                await f.write(contents)
            local_url = f"/api/media/{safe_name}"
            logger.info(f"Video saved locally: {filepath} ({file_size_mb:.1f}MB)")
            return {"url": local_url, "local": True}
        else:
            # Upload image to CDN
            import httpx
            from app.config import config as _config
            async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=15.0)) as client:
                resp = await client.post(
                    "https://api.apidot.ai/api/common/upload-v2",
                    headers={"Authorization": f"Bearer {_config.IMAGE_API_KEY}"},
                    files={"file": (filename, contents, content_type)},
                )
                data = resp.json()
                if data.get("code") == 200:
                    file_url = data["data"]["file_url"]
                    logger.info(f"Image uploaded to CDN: {file_url}")
                    return {"url": file_url}
                else:
                    err_msg = data.get("error", {}).get("message", "") if isinstance(data.get("error"), dict) else data.get("msg", "Upload failed")
                    raise HTTPException(status_code=400, detail=err_msg)
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"Upload failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e) or "Unknown upload error")


@app.get("/api/media/{filename}")
async def serve_media(filename: str):
    """Serve locally stored uploaded files."""
    import os
    from fastapi.responses import FileResponse as _FileResponse
    upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "uploads")
    filepath = os.path.join(upload_dir, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    return _FileResponse(filepath)


@app.post("/api/chat")
async def chat(req: ChatRequest) -> ChatResponse:
    """Receive user input and kick off the agent workflow."""
    session_id = req.session_id or str(uuid.uuid4())[:8]

    # Create SSE queue for this session
    sse_manager.create_session(session_id)

    # Launch the orchestrator workflow in the background
    import asyncio
    asyncio.create_task(_run_workflow(session_id, req.user_input, req.reference_urls, req.video_url))

    logger.info(f"Session {session_id}: processing '{req.user_input[:50]}...'")
    return ChatResponse(session_id=session_id, message="Workflow started")


async def _run_workflow(session_id: str, user_input: str, reference_urls=None, video_url=None):
    """Run the orchestrator workflow and emit results via SSE."""
    try:
        results = await run_orchestrator(session_id, user_input, reference_urls, video_url)
        await sse_manager.emit(session_id, "done", {})
        # Save session
        await save_session(session_id, user_input, results.get("agent_results", {}))
    except Exception as e:
        logger.error(f"Session {session_id} error: {e}")
        await sse_manager.emit(session_id, "error", {"error": str(e)})
        await sse_manager.emit(session_id, "done", {})
    finally:
        # Keep the session alive for a while so the client can reconnect
        sse_manager.remove_session(session_id)


@app.get("/api/chat/{session_id}/stream")
async def stream(session_id: str):
    """SSE endpoint for streaming agent progress."""
    # Re-create session if it was removed (for reconnection)
    if session_id not in sse_manager._queues:
        sse_manager.create_session(session_id)
    return EventSourceResponse(sse_manager.event_stream(session_id))


@app.get("/api/sessions")
async def list_sessions():
    """Get session history."""
    sessions = await get_sessions()
    return {"sessions": sessions}


@app.get("/api/sessions/{session_id}")
async def session_detail(session_id: str):
    """Get a session's full results."""
    session = await get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session
