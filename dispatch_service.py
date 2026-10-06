import logging
from typing import Dict, Any, Optional
from nlp_parser import parse_booking_message
import database
from line_handler import (
    build_welcome_flex_message,
    build_trip_registered_flex,
    build_driver_assigned_flex,
    build_rejection_flex,
    send_line_reply,
    send_line_push_to_group
)

logger = logging.getLogger("dispatch_service")

async def process_incoming_message(
    group_id: str,
    group_name: str,
    sender_name: str,
    sender_id: str,
    message_text: str,
    reply_token: Optional[str] = None
) -> Dict[str, Any]:
    text_clean = message_text.strip()
    
    # 1. 登記群組
    database.upsert_group(group_id, group_name)
    
    # 2. 檢測指令 (例如 /help, 說明, 叫車說明)
    if text_clean.lower() in ["/help", "/airport", "help", "說明", "叫車", "預約", "菜單"]:
        welcome_flex = build_welcome_flex_message()
        if reply_token:
            await send_line_reply(reply_token, [welcome_flex])
        database.log_message(group_id, sender_name, sender_id, text_clean, is_booking=False)
        return {
            "type": "help",
            "message": "已傳送叫車格式說明",
            "reply_flex": welcome_flex
        }
        
    # 3. 智能解析送機行程 & 嚴格目的地機場檢驗
    parsed = parse_booking_message(text_clean, sender_name=sender_name)
    
    # 若被明確拒絕（例如非機場目的地：去九份、去西門町等）
    if not parsed.is_valid_booking and parsed.rejection_reason:
        database.log_message(group_id, sender_name, sender_id, text_clean, is_booking=False)
        rejection_flex = build_rejection_flex(parsed.rejection_reason)
        if reply_token:
            await send_line_reply(reply_token, [rejection_flex])
        return {
            "type": "rejected",
            "reason": parsed.rejection_reason,
            "reply_flex": rejection_flex
        }
        
    # 若為有效機場送機訂單
    if parsed.is_valid_booking:
        database.log_message(group_id, sender_name, sender_id, text_clean, is_booking=True)
        
        trip_data = {
            "line_group_id": group_id,
            "line_group_name": group_name,
            "line_user_id": sender_id,
            "customer_name": parsed.customer_name or sender_name,
            "customer_phone": parsed.customer_phone,
            "trip_type": parsed.trip_type,
            "pickup_location": parsed.pickup_location,
            "pickup_datetime": parsed.pickup_datetime,
            "destination_airport": parsed.destination_airport,
            "terminal_flight_no": parsed.flight_number,
            "passengers": parsed.passengers,
            "luggage": parsed.luggage,
            "luggage_large": parsed.luggage_large,
            "luggage_small": parsed.luggage_small,
            "special_luggage": parsed.special_luggage,
            "luggage_breakdown": parsed.luggage_breakdown,
            "vehicle_type": parsed.vehicle_type,
            "estimated_fare": parsed.estimated_fare,
            "platform_fee": parsed.platform_fee,
            "driver_payout": parsed.driver_payout,
            "status": "NEW",
            "raw_message": text_clean,
            "notes": f"來自群組：{group_name}"
        }
        
        trip_id = database.create_trip(trip_data)
        trip = database.get_trip(trip_id)
        
        # 1. 產出給客人群組的預約確認 Flex 卡片
        registered_flex = build_trip_registered_flex(trip)
        if reply_token:
            await send_line_reply(reply_token, [registered_flex])
            
        # 2. 自動秒級推播至【車隊司機搶單大群】，讓待命司機一鍵搶單！
        try:
            from line_handler import build_driver_broadcast_flex
            driver_broadcast_flex = build_driver_broadcast_flex(trip)
            await send_line_push_to_group("tw-group-driver-fleet", [driver_broadcast_flex])
            # 也記錄至司機群對話紀錄中
            database.log_message(
                "tw-group-driver-fleet", "系統廣播派單", "bot-system",
                f"【新單廣播】{trip['pickup_location']} ➔ {trip['destination_airport']} (司機實拿 NT${int(trip['driver_payout'])})",
                is_booking=True
            )
        except Exception as e:
            logger.warning("推播至司機群失敗: %s", e)

        logger.info("已成功建立機場送機預約單 #%s，來源群組：%s", trip_id, group_name)
        return {
            "type": "trip_created",
            "trip": trip,
            "reply_flex": registered_flex
        }
        
    # 群組普通閒聊對話，不主動干擾
    database.log_message(group_id, sender_name, sender_id, text_clean, is_booking=False)
    return {
        "type": "ignored",
        "message": "已記錄對話，無機場送機預約意圖"
    }

async def assign_driver_and_notify_group(trip_id: int, driver_id: int, bundle_matched: bool = False) -> Optional[Dict[str, Any]]:
    updated_trip = database.assign_driver_to_trip(trip_id, driver_id, bundle_matched=bundle_matched)
    if not updated_trip:
        return None
        
    # 推送司機資訊卡片至乘客發起叫車的 LINE 群組
    assigned_flex = build_driver_assigned_flex(updated_trip)
    group_id = updated_trip["line_group_id"]
    await send_line_push_to_group(group_id, [assigned_flex])
    
    logger.info("已為單號 #%s 派定司機 %s (是否雙向連環單: %s)，並推播通知至群組 %s", trip_id, driver_id, bundle_matched, group_id)
    return updated_trip
