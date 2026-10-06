import hmac
import hashlib
import base64
import logging
from typing import Dict, Any, Optional, List
import httpx
from config import LINE_CHANNEL_SECRET, LINE_CHANNEL_ACCESS_TOKEN, BASE_URL

logger = logging.getLogger("line_handler")
LINE_API_ENDPOINT = "https://api.line.me/v2/bot/message"

def verify_signature(body: bytes, signature: str) -> bool:
    if not LINE_CHANNEL_SECRET:
        return True
    
    hash_val = hmac.new(
        LINE_CHANNEL_SECRET.encode("utf-8"),
        body,
        hashlib.sha256
    ).digest()
    expected_signature = base64.b64encode(hash_val).decode("utf-8")
    return hmac.compare_digest(expected_signature, signature)

# --- 繁體中文 Flex Message 樣板 ---

def build_welcome_flex_message() -> Dict[str, Any]:
    return {
        "type": "flex",
        "altText": "✈️ 台北機場專車接送調度系統已就緒",
        "contents": {
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#0284c7",
                "contents": [
                    {
                        "type": "text",
                        "text": "✈️ 台北機場專車智慧調度中心",
                        "weight": "bold",
                        "color": "#ffffff",
                        "size": "sm"
                    },
                    {
                        "type": "text",
                        "text": "嚴格專營：桃園機場 (TPE) & 松山機場 (TSA) 送機",
                        "color": "#e0f2fe",
                        "size": "xs",
                        "margin": "xs"
                    }
                ]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "您好！我是您的 24 小時智慧送機派車助理。只要在群組內直接發送用車需求，系統將自動辨識並即時派車！",
                        "wrap": True,
                        "size": "xs",
                        "color": "#334155"
                    },
                    {
                        "type": "separator",
                        "margin": "md"
                    },
                    {
                        "type": "text",
                        "text": "📌 快速叫車範例（自然語言或格式皆可）：",
                        "weight": "bold",
                        "size": "xs",
                        "margin": "md",
                        "color": "#0f172a"
                    },
                    {
                        "type": "text",
                        "text": "直接傳送：\n「明天早上 06:30 需要一輛車去桃園機場第二航廈，從信義區君悅酒店大廳出發，2位大人、2件28吋大行李，電話 0912-345-678，搭長榮 BR87」\n\n或使用結構化格式：\n上車地點：台北晶華酒店\n前往機場：桃園機場一航\n出發時間：明日 07:00\n搭乘人數：3人\n行李件數：3件\n聯絡電話：0933-xxx-xxx",
                        "wrap": True,
                        "size": "xxs",
                        "color": "#64748b",
                        "margin": "xs"
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "🔒 目的地僅限機場專車送達，非機場行程恕不受理",
                        "size": "xxs",
                        "color": "#94a3b8",
                        "align": "center"
                    }
                ]
            }
        }
    }

def build_trip_registered_flex(trip: Dict[str, Any]) -> Dict[str, Any]:
    trip_id = trip.get("id", "N/A")
    pickup = trip.get("pickup_location", "待確認")
    airport = trip.get("destination_airport", "機場")
    pickup_time = trip.get("pickup_datetime", "待確認")
    pax = trip.get("passengers", 1)
    luggage = trip.get("luggage", 1)
    luggage_info = trip.get("luggage_breakdown") or f"{luggage} 件行李"
    vehicle = trip.get("vehicle_type", "標準轎車")
    phone = trip.get("customer_phone", "未提供")
    flight = trip.get("terminal_flight_no") or "無"
    fare = trip.get("estimated_fare", 1100.0)

    return {
        "type": "flex",
        "altText": f"✈️ 機場送機預約已建立：單號 #{trip_id}",
        "contents": {
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#0f172a",
                "contents": [
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {
                                "type": "text",
                                "text": f"送機預約單 #{trip_id}",
                                "weight": "bold",
                                "color": "#38bdf8",
                                "size": "sm",
                                "flex": 1
                            },
                            {
                                "type": "text",
                                "text": "⏳ 正在為您調度司機",
                                "weight": "bold",
                                "color": "#fbbf24",
                                "size": "xxs",
                                "align": "end"
                            }
                        ]
                    }
                ]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "已成功記錄您的機場送機預約",
                        "weight": "bold",
                        "size": "sm",
                        "color": "#0f172a"
                    },
                    {
                        "type": "separator",
                        "margin": "sm"
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "margin": "md",
                        "spacing": "sm",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "baseline",
                                "contents": [
                                    {"type": "text", "text": "🛫 前往機場:", "size": "xs", "color": "#64748b", "width": "80px"},
                                    {"type": "text", "text": str(airport), "size": "xs", "weight": "bold", "color": "#0284c7", "wrap": True}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "baseline",
                                "contents": [
                                    {"type": "text", "text": "📍 上車地點:", "size": "xs", "color": "#64748b", "width": "80px"},
                                    {"type": "text", "text": str(pickup), "size": "xs", "weight": "bold", "color": "#1e293b", "wrap": True}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "baseline",
                                "contents": [
                                    {"type": "text", "text": "⏰ 出發時間:", "size": "xs", "color": "#64748b", "width": "80px"},
                                    {"type": "text", "text": str(pickup_time), "size": "xs", "weight": "bold", "color": "#d97706", "wrap": True}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "baseline",
                                "contents": [
                                    {"type": "text", "text": "✈️ 航班編號:", "size": "xs", "color": "#64748b", "width": "80px"},
                                    {"type": "text", "text": str(flight), "size": "xs", "color": "#334155"}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "baseline",
                                "contents": [
                                    {"type": "text", "text": "👥 乘客行李:", "size": "xs", "color": "#64748b", "width": "80px"},
                                    {"type": "text", "text": f"{pax} 位乘客 | {luggage_info} ({vehicle})", "size": "xs", "color": "#334155", "wrap": True}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "baseline",
                                "contents": [
                                    {"type": "text", "text": "📞 聯絡電話:", "size": "xs", "color": "#64748b", "width": "80px"},
                                    {"type": "text", "text": str(phone), "size": "xs", "color": "#334155"}
                                ]
                            }
                        ]
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": f"預估參考車資：約 NT$ {int(fare):,} 元 (含高速公路通行費)",
                        "size": "xs",
                        "color": "#16a34a",
                        "weight": "bold",
                        "align": "center"
                    },
                    {
                        "type": "text",
                        "text": "車隊司機正在接單中，確認接單後將立即公告車號與司機資訊。",
                        "size": "xxs",
                        "color": "#94a3b8",
                        "align": "center",
                        "margin": "xs"
                    }
                ]
            }
        }
    }

def build_driver_assigned_flex(trip: Dict[str, Any]) -> Dict[str, Any]:
    trip_id = trip.get("id", "N/A")
    pickup = trip.get("pickup_location", "待確認")
    airport = trip.get("destination_airport", "機場")
    pickup_time = trip.get("pickup_datetime", "待確認")
    driver_name = trip.get("driver_name", "司機已派定")
    driver_phone = trip.get("driver_phone", "N/A")
    driver_vehicle = trip.get("driver_vehicle", "轎車")
    driver_plate = trip.get("driver_plate", "N/A")

    return {
        "type": "flex",
        "altText": f"🚗 送機專車已派定！單號 #{trip_id}",
        "contents": {
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#15803d",
                "contents": [
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {
                                "type": "text",
                                "text": f"預約單 #{trip_id} 已派車",
                                "weight": "bold",
                                "color": "#ffffff",
                                "size": "sm",
                                "flex": 1
                            },
                            {
                                "type": "text",
                                "text": "✅ 司機已接單",
                                "weight": "bold",
                                "color": "#bbf7d0",
                                "size": "xxs",
                                "align": "end"
                            }
                        ]
                    }
                ]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "您的送機專車已確認安排完畢！",
                        "weight": "bold",
                        "size": "sm",
                        "color": "#14532d"
                    },
                    {
                        "type": "separator",
                        "margin": "sm"
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "margin": "md",
                        "spacing": "sm",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "baseline",
                                "contents": [
                                    {"type": "text", "text": "👤 接單司機:", "size": "xs", "color": "#64748b", "width": "80px"},
                                    {"type": "text", "text": str(driver_name), "size": "xs", "weight": "bold", "color": "#0f172a"}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "baseline",
                                "contents": [
                                    {"type": "text", "text": "🚗 車輛款式:", "size": "xs", "color": "#64748b", "width": "80px"},
                                    {"type": "text", "text": str(driver_vehicle), "size": "xs", "color": "#0f172a"}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "baseline",
                                "contents": [
                                    {"type": "text", "text": "🔢 車牌號碼:", "size": "xs", "color": "#64748b", "width": "80px"},
                                    {"type": "text", "text": str(driver_plate), "size": "xs", "weight": "bold", "color": "#1e40af"}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "baseline",
                                "contents": [
                                    {"type": "text", "text": "📞 司機電話:", "size": "xs", "color": "#64748b", "width": "80px"},
                                    {"type": "text", "text": str(driver_phone), "size": "xs", "weight": "bold", "color": "#16a34a"}
                                ]
                            },
                            {
                                "type": "separator",
                                "margin": "xs"
                            },
                            {
                                "type": "box",
                                "layout": "baseline",
                                "contents": [
                                    {"type": "text", "text": "📍 上車地點:", "size": "xs", "color": "#64748b", "width": "80px"},
                                    {"type": "text", "text": str(pickup), "size": "xs", "color": "#334155", "wrap": True}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "baseline",
                                "contents": [
                                    {"type": "text", "text": "🛫 前往機場:", "size": "xs", "color": "#64748b", "width": "80px"},
                                    {"type": "text", "text": str(airport), "size": "xs", "color": "#0284c7"}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "baseline",
                                "contents": [
                                    {"type": "text", "text": "⏰ 出發時間:", "size": "xs", "color": "#64748b", "width": "80px"},
                                    {"type": "text", "text": str(pickup_time), "size": "xs", "weight": "bold", "color": "#d97706"}
                                ]
                            }
                        ]
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "司機將於用車前 15-30 分鐘主動電話聯繫確認接送位置。",
                        "size": "xxs",
                        "color": "#64748b",
                        "align": "center"
                    }
                ]
            }
        }
    }

def build_rejection_flex(reason: str) -> Dict[str, Any]:
    return {
        "type": "flex",
        "altText": "⚠️ 提醒：本車隊僅限機場送機專車服務",
        "contents": {
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#dc2626",
                "contents": [
                    {
                        "type": "text",
                        "text": "⚠️ 僅限機場送機專車服務",
                        "weight": "bold",
                        "color": "#ffffff",
                        "size": "sm"
                    }
                ]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": reason,
                        "wrap": True,
                        "size": "xs",
                        "color": "#334155"
                    },
                    {
                        "type": "separator",
                        "margin": "md"
                    },
                    {
                        "type": "text",
                        "text": "✈️ 本車隊專營送達機場：",
                        "weight": "bold",
                        "size": "xs",
                        "margin": "md",
                        "color": "#0f172a"
                    },
                    {
                        "type": "text",
                        "text": "• 桃園國際機場 (TPE / 桃機一航、二航)\n• 台北松山機場 (TSA / 松機國際線、國內線)",
                        "size": "xs",
                        "color": "#0369a1",
                        "margin": "xs"
                    }
                ]
            }
        }
    }

def build_driver_broadcast_flex(trip: Dict[str, Any]) -> Dict[str, Any]:
    trip_id = trip.get("id", "N/A")
    pickup = trip.get("pickup_location", "待確認")
    airport = trip.get("destination_airport", "機場")
    pickup_time = trip.get("pickup_datetime", "待確認")
    pax = trip.get("passengers", 1)
    luggage = trip.get("luggage", 1)
    luggage_info = trip.get("luggage_breakdown") or f"{luggage} 箱"
    vehicle = trip.get("vehicle_type", "標準轎車")
    fare = float(trip.get("estimated_fare", 1100.0))
    payout = float(trip.get("driver_payout", fare - 50.0))
    uber_savings = int(fare * 0.25 - 50.0)

    return {
        "type": "flex",
        "altText": f"⚡【新單待搶】{pickup} ➔ {airport} (司機實拿 NT${int(payout)})",
        "contents": {
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#b45309",
                "contents": [
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {"type": "text", "text": "⚡ 新單待搶・手慢無", "weight": "bold", "color": "#fef3c7", "size": "sm", "flex": 1},
                            {"type": "text", "text": f"#{trip_id}", "weight": "bold", "color": "#fde68a", "size": "sm", "align": "end"}
                        ]
                    }
                ]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "box",
                        "layout": "vertical",
                        "backgroundColor": "#1e293b",
                        "paddingAll": "md",
                        "cornerRadius": "lg",
                        "contents": [
                            {"type": "text", "text": f"💰 司機淨實收：NT$ {int(payout):,} 元", "weight": "bold", "size": "md", "color": "#4ade80"},
                            {"type": "text", "text": f"★ 比跑 Uber 多賺 NT$ {uber_savings} 元 (免收 25% 暴利抽成)", "size": "xxs", "color": "#fbbf24", "margin": "xs"}
                        ]
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "margin": "md",
                        "spacing": "sm",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "baseline",
                                "contents": [
                                    {"type": "text", "text": "📍 上車處:", "size": "xs", "color": "#64748b", "width": "75px"},
                                    {"type": "text", "text": str(pickup), "size": "xs", "weight": "bold", "color": "#0f172a", "wrap": True}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "baseline",
                                "contents": [
                                    {"type": "text", "text": "🛫 機場航廈:", "size": "xs", "color": "#64748b", "width": "75px"},
                                    {"type": "text", "text": str(airport), "size": "xs", "weight": "bold", "color": "#0284c7"}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "baseline",
                                "contents": [
                                    {"type": "text", "text": "⏰ 出發時間:", "size": "xs", "color": "#64748b", "width": "75px"},
                                    {"type": "text", "text": str(pickup_time), "size": "xs", "weight": "bold", "color": "#d97706"}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "baseline",
                                "contents": [
                                    {"type": "text", "text": "👥 乘車需求:", "size": "xs", "color": "#64748b", "width": "75px"},
                                    {"type": "text", "text": f"{pax} 人 | {luggage_info} ({vehicle})", "size": "xs", "color": "#334155", "wrap": True}
                                ]
                            }
                        ]
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "action": {
                            "type": "uri",
                            "label": "⚡ 點此開啟司機端秒殺搶單",
                            "uri": f"{BASE_URL}/?tab=driver"
                        },
                        "style": "primary",
                        "color": "#16a34a"
                    }
                ]
            }
        }
    }

# --- LINE API 訊息推送 ---

async def send_line_reply(reply_token: str, messages: List[Dict[str, Any]]) -> bool:
    if not LINE_CHANNEL_ACCESS_TOKEN:
        logger.info("[模擬回復] 回傳 LINE Token %s: %s 則訊息", reply_token, len(messages))
        return True

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }
    payload = {
        "replyToken": reply_token,
        "messages": messages
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{LINE_API_ENDPOINT}/reply", headers=headers, json=payload, timeout=10.0)
            return resp.status_code == 200
        except Exception as e:
            logger.error("發送 LINE Reply 失敗: %s", e)
            return False

async def send_line_push_to_group(group_id: str, messages: List[Dict[str, Any]]) -> bool:
    if not LINE_CHANNEL_ACCESS_TOKEN:
        logger.info("[模擬推播] 推送至群組 %s: %s 則訊息", group_id, len(messages))
        return True

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }
    payload = {
        "to": group_id,
        "messages": messages
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{LINE_API_ENDPOINT}/push", headers=headers, json=payload, timeout=10.0)
            return resp.status_code == 200
        except Exception as e:
            logger.error("發送 LINE Push 失敗: %s", e)
            return False
