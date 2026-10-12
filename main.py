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
    # 手動需要公網網址時才透過 /api/tunnel/start 啟動，避免背景重載彈出視窗
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
if not STATIC_DIR.exists():
    STATIC_DIR = Path(__file__).resolve().parent

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

# --- Google Maps Platform Places Autocomplete (New) ---
# Source: Google Maps Platform Code Assist

TAIWAN_MAJOR_AIRPORT_LOCATIONS = [
    {"name": "台北晶華酒店大門口 (Regent Taipei)", "address": "台北市中山區中山北路二段39巷3號"},
    {"name": "台北君悅酒店正門 Lobby (Grand Hyatt Taipei)", "address": "台北市信義區松壽路2號"},
    {"name": "台北萬豪酒店大廳 (Taipei Marriott Hotel)", "address": "台北市中山區樂群二路199號"},
    {"name": "台北W飯店 (W Taipei)", "address": "台北市信義區忠孝東路五段10號"},
    {"name": "台北文華東方酒店 (Mandarin Oriental Taipei)", "address": "台北市松山區敦化北路158號"},
    {"name": "台北喜來登大飯店 (Sheraton Grand Taipei Hotel)", "address": "台北市中正區忠孝東路一段12號"},
    {"name": "台北寒舍艾美酒店 (Le Méridien Taipei)", "address": "台北市信義區松仁路38號"},
    {"name": "台北遠東香格里拉大飯店", "address": "台北市大安區敦化南路二段201號"},
    {"name": "圓山大飯店 (The Grand Hotel)", "address": "台北市中山區中山北路四段1號"},
    {"name": "格拉斯麗台北飯店 (Hotel Gracery Taipei)", "address": "台北市中正區忠孝東路二段89號"},
    {"name": "台北車站 (東三門 / 西三門接送區)", "address": "台北市中正區北平西路3號"},
    {"name": "南港展覽館一館 / 二館", "address": "台北市南港區經貿二路1號"},
    {"name": "板橋車站 / 新板特區 (縣民大道)", "address": "新北市板橋區縣民大道二段7號"},
    {"name": "台北101觀景台 / 大樓正門", "address": "台北市信義區信義路五段7號"},
    {"name": "信義區豪宅特區 / 象山社區", "address": "台北市信義區信義路五段松仁路口"},
    {"name": "大安森林公園捷運站出口", "address": "台北市大安區信義路三段100號"},
    {"name": "內湖科技園區 (瑞光路 / 洲子街)", "address": "台北市內湖區瑞光路399號"},
    {"name": "新店裕隆城 / 家樂福新店店", "address": "新北市新店區中興路三段128號"},
    {"name": "中和環球購物中心", "address": "新北市中和區中山路三段122號"},
    {"name": "新莊副都心 / 宏匯廣場", "address": "新北市新莊區新北大道四段3號"},
    {"name": "桃園高鐵站 (前站 / 後站)", "address": "桃園市中壢區高鐵北路一段6號"},
    {"name": "林口三井Outlet (文化三路門口)", "address": "新北市林口區文化三路一段356號"},
    {"name": "桃園國際機場 (TPE) 第一航廈", "address": "桃園市大園區航站南路15號"},
    {"name": "桃園國際機場 (TPE) 第二航廈", "address": "桃園市大園區航站南路9號"},
    {"name": "台北松山機場 (TSA) 國際線/國內線", "address": "台北市松山區敦化北路340-9號"}
]

@app.get("/api/places/autocomplete")
def autocomplete_places(input: str = Query(..., min_length=1), session_token: Optional[str] = None):
    import config
    import urllib.request
    
    query = input.strip()
    if not query:
        return {"predictions": [], "source": "empty", "api_key_configured": bool(config.GOOGLE_MAPS_API_KEY)}
        
    api_key = config.GOOGLE_MAPS_API_KEY.strip() if config.GOOGLE_MAPS_API_KEY else ""
    
    if api_key:
        try:
            req_body = {
                "input": query,
                "includedRegionCodes": ["tw"],
                "locationBias": {
                    "circle": {
                        "center": {"latitude": 25.0478, "longitude": 121.5170},
                        "radius": 50000.0
                    }
                }
            }
            if session_token:
                req_body["sessionToken"] = session_token

            url = "https://places.googleapis.com/v1/places:autocomplete"
            req = urllib.request.Request(
                url,
                data=json.dumps(req_body).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": api_key,
                    "X-Goog-Maps-Solution-ID": "gmp_git_agentskills_v1",
                    "X-Goog-FieldMask": "suggestions.placePrediction.placeId,suggestions.placePrediction.text.text,suggestions.placePrediction.structuredFormat.mainText.text,suggestions.placePrediction.structuredFormat.secondaryText.text"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=4) as response:
                result = json.loads(response.read().decode("utf-8"))
                predictions = []
                for s in result.get("suggestions", []):
                    p = s.get("placePrediction")
                    if p:
                        main_text = p.get("structuredFormat", {}).get("mainText", {}).get("text") or p.get("text", {}).get("text", "")
                        secondary_text = p.get("structuredFormat", {}).get("secondaryText", {}).get("text") or ""
                        full_text = p.get("text", {}).get("text", "")
                        predictions.append({
                            "place_id": p.get("placeId", ""),
                            "main_text": main_text,
                            "secondary_text": secondary_text,
                            "full_text": full_text or f"{main_text} {secondary_text}".strip()
                        })
                if predictions:
                    return {"predictions": predictions, "source": "google_maps_places", "api_key_configured": True}
        except Exception as e:
            logger.warning("Google Maps Places API Autocomplete 呼叫異常: %s", e)

    # 本地高頻機場接送地標比對（模糊匹配備用）
    matched = []
    q_lower = query.lower()
    for item in TAIWAN_MAJOR_AIRPORT_LOCATIONS:
        if q_lower in item["name"].lower() or q_lower in item["address"].lower():
            matched.append({
                "place_id": f"local_{hash(item['name'])}",
                "main_text": item["name"],
                "secondary_text": item["address"],
                "full_text": f"{item['name']} ({item['address']})"
            })
    
    return {
        "predictions": matched[:6],
        "source": "curated_fallback",
        "api_key_configured": bool(api_key)
    }

# --- Settings API ---

class LineKeysRequest(BaseModel):
    channel_secret: str
    channel_access_token: str

class GoogleMapsKeyRequest(BaseModel):
    google_maps_api_key: str

@app.get("/api/settings/status")
def get_settings_status():
    import config
    has_secret = bool(config.LINE_CHANNEL_SECRET)
    has_token = bool(config.LINE_CHANNEL_ACCESS_TOKEN)
    has_gmap = bool(config.GOOGLE_MAPS_API_KEY)
    return {
        "is_configured": has_secret and has_token,
        "has_google_maps_key": has_gmap,
        "google_maps_key_masked": f"{config.GOOGLE_MAPS_API_KEY[:4]}...{config.GOOGLE_MAPS_API_KEY[-4:]}" if has_gmap and len(config.GOOGLE_MAPS_API_KEY) >= 8 else ("已設定" if has_gmap else "未設定 (已啟用北台灣高頻地標庫)"),
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
    existing_lines = []
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.startswith(("LINE_CHANNEL_SECRET=", "LINE_CHANNEL_ACCESS_TOKEN=")):
                    existing_lines.append(line.rstrip("\r\n"))
    existing_lines.append(f"LINE_CHANNEL_SECRET={secret}")
    existing_lines.append(f"LINE_CHANNEL_ACCESS_TOKEN={token}")
    with open(env_file, "w", encoding="utf-8") as f:
        f.write("\n".join(existing_lines) + "\n")
        
    return {"status": "ok", "message": "LINE 機器人金鑰儲存成功，即時連線已啟動！"}

@app.post("/api/settings/google-maps-key")
def update_google_maps_key(req: GoogleMapsKeyRequest):
    import config
    key = req.google_maps_api_key.strip()
    config.GOOGLE_MAPS_API_KEY = key
    
    env_file = Path(__file__).resolve().parent / ".env"
    existing_lines = []
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.startswith("GOOGLE_MAPS_API_KEY="):
                    existing_lines.append(line.rstrip("\r\n"))
    existing_lines.append(f"GOOGLE_MAPS_API_KEY={key}")
    with open(env_file, "w", encoding="utf-8") as f:
        f.write("\n".join(existing_lines) + "\n")
        
    return {"status": "ok", "message": "Google Maps Platform API 金鑰儲存成功！全台地址即時自動聯想已啟用！"}

if __name__ == "__main__":
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
