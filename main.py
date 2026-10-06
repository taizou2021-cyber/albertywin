import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from fastapi import FastAPI, Request, Response, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from config import HOST, PORT, LINE_CHANNEL_SECRET
import database
from models import (
    Trip, TripCreate, TripUpdate, Driver, DriverCreate,
    AssignDriverRequest, SimulatorMessageRequest
)
from line_handler import verify_signature, build_welcome_flex_message, send_line_reply
import dispatch_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("main")

# Initialize database
database.init_db()

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    import os
    if not os.environ.get("VERCEL"):
        try:
            from tunnel_manager import tunnel_mgr
            from config import PORT
            tunnel_mgr.start_tunnel(port=PORT)
            logger.info("自動啟動 Cloudflare 全球加密公開通道...")
        except Exception as e:
            logger.warning("無法自動啟動通道: %s", e)
    yield

app = FastAPI(
    title="Airport-Only Driver Dispatch System",
    description="Automated Driver Dispatching for Airport-Only transfers from multi-group LINE chats",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse

# --- Health Check Endpoint ---
@app.get("/health")
def health_check():
    return {"status": "ok", "app": "Airport-Only Driver Dispatch System"}

# --- Vercel Deployment Package Download ---
@app.get("/download-vercel-zip")
def download_vercel_zip():
    from create_vercel_zip import create_vercel_package
    zip_path = create_vercel_package()
    return FileResponse(
        path=str(zip_path),
        media_type="application/zip",
        filename="line-airport-dispatch-vercel.zip"
    )

# --- HTML Route Handlers (All-in-One Unified App) ---

@app.get("/", response_class=FileResponse)
async def serve_unified_app():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/driver")
async def redirect_driver():
    return RedirectResponse(url="/?tab=driver")

@app.get("/simulator")
async def redirect_simulator():
    return RedirectResponse(url="/?tab=simulator")

@app.get("/guide")
async def redirect_guide():
    return RedirectResponse(url="/?tab=guide")

@app.get("/book")
async def redirect_book():
    return RedirectResponse(url="/?tab=book")

# --- Cloudflare Public Tunnel API ---
from tunnel_manager import tunnel_mgr

@app.get("/api/tunnel/status")
def get_tunnel_status():
    return tunnel_mgr.get_status()

@app.post("/api/tunnel/start")
def start_public_tunnel():
    from config import PORT
    return tunnel_mgr.start_tunnel(port=PORT)

@app.post("/api/tunnel/stop")
def stop_public_tunnel():
    return tunnel_mgr.stop_tunnel()


# --- LINE Webhook Handler ---

@app.post("/api/line/webhook")
async def line_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Official webhook for LINE Messaging API.
    Handles message events and bot join events from multiple LINE groups.
    """
    body = await request.body()
    signature = request.headers.get("X-Line-Signature", "")
    
    # Signature check
    if LINE_CHANNEL_SECRET and not verify_signature(body, signature):
        logger.warning("Invalid LINE webhook signature")
        raise HTTPException(status_code=400, detail="Invalid signature")

    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Malformed JSON")

    events = payload.get("events", [])
    for event in events:
        event_type = event.get("type")
        source = event.get("source", {})
        source_type = source.get("type", "")
        reply_token = event.get("replyToken")
        
        # Determine group id
        group_id = source.get("groupId") or source.get("roomId") or source.get("userId") or "direct-chat"
        group_name = f"LINE Group ({group_id[-6:]})" if "groupId" in source else "Direct Chat"

        # Handle Bot joining a group
        if event_type in ["join", "memberJoined"]:
            database.upsert_group(group_id, group_name)
            welcome_flex = build_welcome_flex_message()
            if reply_token:
                background_tasks.add_task(send_line_reply, reply_token, [welcome_flex])
            logger.info("Bot joined LINE group: %s", group_id)
            continue

        # Handle incoming message in a group
        if event_type == "message":
            msg = event.get("message", {})
            if msg.get("type") == "text":
                text = msg.get("text", "")
                sender_id = source.get("userId", "unknown-user")
                sender_name = f"User-{sender_id[-4:]}" if len(sender_id) >= 4 else "Customer"
                
                background_tasks.add_task(
                    dispatch_service.process_incoming_message,
                    group_id=group_id,
                    group_name=group_name,
                    sender_name=sender_name,
                    sender_id=sender_id,
                    message_text=text,
                    reply_token=reply_token
                )

    return {"status": "ok", "events_processed": len(events)}

# --- Trips API ---

@app.get("/api/trips")
def list_trips(status: Optional[str] = Query(None), group_id: Optional[str] = Query(None)):
    return database.get_trips(status=status, group_id=group_id)

@app.get("/api/trips/{trip_id}")
def get_trip_details(trip_id: int):
    trip = database.get_trip(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip

@app.post("/api/trips")
async def create_manual_trip(trip: TripCreate, background_tasks: BackgroundTasks):
    data = trip.model_dump()
    fare = data.get("estimated_fare") or 1100.0
    data["platform_fee"] = 50.0
    data["driver_payout"] = fare - 50.0
    trip_id = database.create_trip(data)
    created = database.get_trip(trip_id)
    
    # 秒級推播至【車隊司機即時搶單大群】
    try:
        from line_handler import build_driver_broadcast_flex, send_line_push_to_group
        flex = build_driver_broadcast_flex(created)
        background_tasks.add_task(send_line_push_to_group, "tw-group-driver-fleet", [flex])
        lug_info = created.get("luggage_breakdown") or f"{created.get('luggage', 1)}件行李"
        database.log_message(
            "tw-group-driver-fleet", "顧客線上預約廣播", "bot-system",
            f"【官網直客新單】{created['pickup_location']} ➔ {created['destination_airport']} | {created['passengers']}人 {lug_info} (司機實拿 NT${int(created['driver_payout'])})",
            is_booking=True
        )
    except Exception as e:
        logger.warning("推播網頁預約單至司機群失敗: %s", e)

    return created

@app.get("/api/trips/{trip_id}/return-matches")
def get_return_matches(trip_id: int):
    return database.find_return_matches(trip_id)

@app.patch("/api/trips/{trip_id}/assign")
@app.post("/api/trips/{trip_id}/assign")
async def assign_driver(trip_id: int, req: AssignDriverRequest):
    updated = await dispatch_service.assign_driver_and_notify_group(
        trip_id, req.driver_id, bundle_matched=req.bundle_matched_trip
    )
    if not updated:
        raise HTTPException(status_code=400, detail="Cannot assign driver. Trip may not exist or is already completed.")
    return updated

@app.patch("/api/trips/{trip_id}/status")
@app.post("/api/trips/{trip_id}/status")
def update_status(trip_id: int, update: TripUpdate):
    if not update.status:
        raise HTTPException(status_code=400, detail="Status is required")
    success = database.update_trip_status(trip_id, update.status, update.notes)
    if not success:
        raise HTTPException(status_code=404, detail="Trip not found")
    return database.get_trip(trip_id)

# --- Drivers API ---

@app.get("/api/drivers")
def list_drivers(active_only: bool = True):
    return database.get_drivers(active_only=active_only)

@app.post("/api/drivers")
def add_driver(driver: DriverCreate):
    driver_id = database.create_driver(driver.model_dump())
    return database.get_driver(driver_id)

# --- Groups & Stats API ---

@app.get("/api/groups")
def list_groups():
    return database.get_groups()

@app.get("/api/stats")
def get_stats():
    return database.get_dashboard_stats()

# --- Simulator API (Multi-Group Testing) ---

@app.post("/api/simulator/send")
async def simulate_group_message(req: SimulatorMessageRequest):
    """
    Simulates a member typing in a specified LINE group.
    Runs the exact same pipeline and returns the bot's reaction and Flex Card.
    """
    res = await dispatch_service.process_incoming_message(
        group_id=req.group_id,
        group_name=req.group_name,
        sender_name=req.sender_name,
        sender_id=f"sim-user-{hash(req.sender_name) % 10000:04d}",
        message_text=req.message_text,
        reply_token=None
    )
    return res

# --- LINE Settings API ---

class LineKeysRequest(BaseModel):
    channel_secret: str
    channel_access_token: str

@app.get("/api/settings/status")
def get_settings_status():
    import config
    has_secret = bool(config.LINE_CHANNEL_SECRET)
    has_token = bool(config.LINE_CHANNEL_ACCESS_TOKEN)
    return {
        "is_configured": has_secret and has_token,
        "channel_secret_masked": f"{config.LINE_CHANNEL_SECRET[:4]}...{config.LINE_CHANNEL_SECRET[-4:]}" if has_secret and len(config.LINE_CHANNEL_SECRET) >= 8 else ("已設定" if has_secret else "未設定"),
        "channel_token_masked": f"{config.LINE_CHANNEL_ACCESS_TOKEN[:6]}...{config.LINE_CHANNEL_ACCESS_TOKEN[-6:]}" if has_token and len(config.LINE_CHANNEL_ACCESS_TOKEN) >= 12 else ("已設定" if has_token else "未設定")
    }

@app.post("/api/settings/line-keys")
def update_line_keys(req: LineKeysRequest):
    import config
    secret = req.channel_secret.strip()
    token = req.channel_access_token.strip()
    
    config.LINE_CHANNEL_SECRET = secret
    config.LINE_CHANNEL_ACCESS_TOKEN = token
    
    env_file = Path(__file__).resolve().parent / ".env"
    with open(env_file, "w", encoding="utf-8") as f:
        f.write(f"LINE_CHANNEL_SECRET={secret}\n")
        f.write(f"LINE_CHANNEL_ACCESS_TOKEN={token}\n")
        f.write(f"PORT={config.PORT}\n")
        f.write(f"HOST={config.HOST}\n")
        f.write(f"BASE_URL={config.BASE_URL}\n")
        
    return {"status": "ok", "message": "LINE 機器人金鑰儲存成功，即時連線已啟動！"}

if __name__ == "__main__":
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
