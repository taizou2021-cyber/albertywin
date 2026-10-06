import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from models import ParsedBooking
from config import DEFAULT_AIRPORTS, DEFAULT_FARES_TPE, DEFAULT_FARES_TSA

# 台灣手機號碼格式 (09xx-xxx-xxx 或 +886-9xx-xxx-xxx)
PHONE_PATTERN = re.compile(r'(?:\+?886[-\s]?)?0?9\d{2}[-\s]?\d{3}[-\s]?\d{3}')

# 人數與行李正則 (支援繁體中文與英文，避免「九人座」車型干擾人數)
PAX_PATTERN = re.compile(r'(\d+|[一二兩三四五六七八九十]+)\s*(?:位大人|位乘客|位貴賓|位|人(?!座)|名|pax|people|persons?|guests?)', re.IGNORECASE)
LUGGAGE_PATTERN = re.compile(r'(\d+|[一二兩三四五六七八九十]+)\s*(?:件大行李|個行李箱|件行李|吋行李|個箱子|件|個|箱|bags?|luggages?|suitcases?)', re.IGNORECASE)

# 時間正則 (例如 07:00, 早上6點, 清晨5:30, 14:00, 7am, 下午3點半)
TIME_PATTERN = re.compile(r'(?:(?:早上|上午|下午|晚上|清晨|凌晨)\s*)?(?:\b\d{1,2}[:.]\d{2}\s*(?:am|pm)?\b|\b\d{1,2}\s*(?:am|pm)\b|\b\d{1,2}\s*點(?:\s*半|\s*\d{1,2}\s*分)?\b)', re.IGNORECASE)

# 航班代碼 (長榮 BR, 華航 CI, 星宇 JX, 虎航 IT, 國泰 CX, 日航 JL, 全日空 NH 等，支援 1~4 位數)
FLIGHT_PATTERN = re.compile(r'\b([A-Z0-9]{2,3}\s?\d{1,4})\b')

CHINESE_NUM_MAP = {
    '一': 1, '二': 2, '兩': 2, '三': 3, '四': 4,
    '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10
}

AIRPORT_KEYWORDS = {
    "TPE": [
        "桃園機場", "桃機", "桃園國際機場", "tpe", "一航", "二航",
        "第一航廈", "第二航廈", "taoyuan airport", "taoyuan"
    ],
    "TSA": [
        "松山機場", "松機", "台北松山機場", "tsa", "台北機場",
        "songshan airport", "songshan"
    ]
}

# 台灣常見非機場目的地 (用於嚴格防呆與拒絕)
NON_AIRPORT_DESTINATIONS = [
    "九份", "西門町", "淡水", "宜蘭", "礁溪", "台中", "台南", "高雄",
    "新竹", "基隆", "台北101", "101", "陽明山", "士林夜市", "野柳",
    "烏來", "墾丁", "花蓮", "台東", "日月潭", "清境", "羅東", "板橋車站", "台北車站",
    "ximending", "jiufen", "tamsui", "yilan", "taichung", "kaohsiung"
]

BOOKING_INTENT_KEYWORDS = [
    "/airport", "/book", "#airport", "送機", "預約送機", "叫車", "要車", "找車",
    "機場專車", "需要車", "去機場", "接送", "前往機場", "需要專車",
    "need car", "book car", "airport transfer", "car to airport"
]

def parse_num_chinese(val_str: str) -> int:
    """轉換數字或中文數字為整數"""
    if not val_str:
        return 1
    val_str = val_str.strip()
    if val_str.isdigit():
        return int(val_str)
    return CHINESE_NUM_MAP.get(val_str, 1)

def detect_airport(text: str) -> Tuple[Optional[str], Optional[str]]:
    """辨識輸入文字中指定之機場 (TPE 桃園機場 或 TSA 松山機場)"""
    text_lower = text.lower()
    
    # 先比對具體機場代碼與關鍵字
    for code, keywords in AIRPORT_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                for ap in DEFAULT_AIRPORTS:
                    if ap["code"] == code:
                        return ap["code"], ap["name"]
                        
    # 若僅寫「機場」或「airport」，預設為台北出國最大主力「桃園國際機場 (TPE)」
    if "機場" in text_lower or "airport" in text_lower:
        return "TPE", "桃園國際機場 (TPE) [請確認航廈]"
        
    return None, None

def check_non_airport_destination(text: str) -> Optional[str]:
    """檢測用戶是否預約了非機場之目的地"""
    text_lower = text.lower()
    indicators = ["去", "到", "前往", "送至", "to ", "destination: ", "目的地:"]
    for ind in indicators:
        if ind in text_lower:
            part_after = text_lower.split(ind, 1)[1]
            for non_ap in NON_AIRPORT_DESTINATIONS:
                if non_ap in part_after:
                    # 避免「從九份去桃園機場」被誤判為九份行程
                    if not any(ap_kw in part_after for kw_list in AIRPORT_KEYWORDS.values() for ap_kw in kw_list):
                        return non_ap
    return None

def extract_structured_fields(text: str) -> Dict[str, Any]:
    """解析以換行或冒號為主的格式化文字"""
    extracted = {}
    lines = text.split("\n")
    for line in lines:
        if ":" in line or "：" in line:
            delimiter = ":" if ":" in line else "："
            key, val = line.split(delimiter, 1)
            key = key.strip().lower()
            val = val.strip()
            if any(k in key for k in ["上車", "出發地", "地址", "接駁地", "pickup", "from", "location", "地點"]):
                extracted["pickup_location"] = val
            elif any(k in key for k in ["機場", "目的地", "destination", "to", "機場別"]):
                extracted["destination"] = val
            elif any(k in key for k in ["時間", "出發時間", "日期", "time", "date", "datetime"]):
                extracted["pickup_datetime"] = val
            elif any(k in key for k in ["人數", "搭乘人數", "pax", "passenger", "people"]):
                extracted["passengers"] = val
            elif any(k in key for k in ["行李", "件數", "行李數", "luggage", "bag"]):
                extracted["luggage"] = val
            elif any(k in key for k in ["電話", "手機", "聯絡", "phone", "tel", "contact"]):
                extracted["customer_phone"] = val
            elif any(k in key for k in ["航班", "班機", "flight"]):
                extracted["flight_number"] = val
            elif any(k in key for k in ["姓名", "稱呼", "聯絡人", "name", "customer"]):
                extracted["customer_name"] = val
            elif any(k in key for k in ["車款", "車種", "car", "vehicle"]):
                extracted["vehicle_type"] = val
    return extracted

def parse_booking_message(text: str, sender_name: Optional[str] = "貴賓客戶") -> ParsedBooking:
    """
    智能語意解析：嚴格檢驗目的地是否為機場（桃園/松山），並提取出發地、時間、航班、電話、行李與車型
    """
    raw_text = text.strip()
    text_lower = raw_text.lower()

    # 1. 意圖檢測
    has_explicit_tag = any(kw in text_lower for kw in BOOKING_INTENT_KEYWORDS)
    structured_data = extract_structured_fields(raw_text)

    # 2. 檢驗目的地機場
    airport_code, airport_name = detect_airport(raw_text)
    non_airport = check_non_airport_destination(raw_text)

    # 非機場目的地之嚴格拒絕規則
    if non_airport and not airport_code:
        return ParsedBooking(
            is_valid_booking=False,
            is_airport_destination=False,
            rejection_reason=f"目的地「{non_airport}」非機場。本車隊嚴格專營台北/新北前往「桃園國際機場 (TPE)」及「台北松山機場 (TSA)」之送機專車服務，恕無法承接非機場之市區或觀光行程。",
            raw_text=raw_text,
            customer_name=sender_name
        )

    # 未提及任何機場
    if not airport_code:
        if has_explicit_tag:
            return ParsedBooking(
                is_valid_booking=False,
                is_airport_destination=False,
                rejection_reason="請註明預計前往的機場（桃園機場 TPE 或 松山機場 TSA）。本調度平台僅提供機場送機專車服務。",
                raw_text=raw_text,
                customer_name=sender_name
            )
        # 群組一般聊天，靜默忽略
        return ParsedBooking(
            is_valid_booking=False,
            is_airport_destination=False,
            raw_text=raw_text,
            customer_name=sender_name
        )

    # 3. 提取上車地點 (台北地區常見特徵)
    pickup_location = structured_data.get("pickup_location")
    if not pickup_location:
        # 正則比對「從...」、「於...接送」、「上車地點：...」、「接送地點：...」
        loc_match = re.search(r'(?:從|接送地點|上車處|上車地點|接送處|地點|地址|於|在)\s*[:：\s]?\s*([^\n,，。]{3,40})', raw_text)
        if loc_match:
            candidate = loc_match.group(1).strip()
            # 排除含有機場字眼的誤配
            if not any(k in candidate for k in ["機場", "桃機", "松機", "航廈"]):
                pickup_location = candidate

    if not pickup_location:
        # 自動探測台北常見行政區或飯店大樓
        taipei_areas = re.search(r'((?:台北市|新北市)?(?:信義區|大安區|中山區|松山區|中正區|萬華區|內湖區|南港區|士林區|北投區|文山區|板橋區|新店區|中和區|永和區|三重區|汐止區)?[^\n,，。]{2,25}(?:飯店|酒店|大廈|大樓|社區|會館|豪宅|路|街|巷|門口|Lobby|一樓))', raw_text)
        if taipei_areas:
            pickup_location = taipei_areas.group(1).strip()
        else:
            pickup_location = "台北市區 (司機接單後確認詳細地址)"

    # 4. 提取出發日期與時間
    pickup_datetime = structured_data.get("pickup_datetime")
    if not pickup_datetime:
        time_match = TIME_PATTERN.search(raw_text)
        found_time = time_match.group(0).strip() if time_match else None

        now = datetime.now()
        date_str = ""
        if "明天" in text_lower or "tomorrow" in text_lower:
            date_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        elif "後天" in text_lower:
            date_str = (now + timedelta(days=2)).strftime("%Y-%m-%d")
        elif "今天" in text_lower or "today" in text_lower:
            date_str = now.strftime("%Y-%m-%d")
        else:
            d_match = re.search(r'\b(\d{1,2}[月/-]\d{1,2}(?:日)?)\b', raw_text)
            if d_match:
                date_str = d_match.group(1)
            else:
                date_str = (now + timedelta(days=1)).strftime("%Y-%m-%d (明天)")

        if found_time:
            pickup_datetime = f"{date_str} {found_time}"
        else:
            pickup_datetime = f"{date_str} (時間待確認)"

    # 5. 提取聯絡手機 (台灣 09xx-xxx-xxx)
    phone = structured_data.get("customer_phone")
    if not phone:
        phone_match = PHONE_PATTERN.search(raw_text)
        if phone_match:
            phone = phone_match.group(0).strip()

    # 6. 提取搭乘人數與行李規格 (28~32吋大箱, 20~24吋登機箱, 特殊大件行李)
    passengers = 1
    if structured_data.get("passengers"):
        passengers = parse_num_chinese(re.search(r'\d+|[一二兩三四五六七八九十]+', str(structured_data["passengers"])).group(0))
    else:
        pax_match = PAX_PATTERN.search(raw_text)
        if pax_match:
            passengers = parse_num_chinese(pax_match.group(1))

    # 特殊行李探測 (高爾夫球袋、嬰兒推車、輪椅、紙箱、雪板)
    special_items = []
    if any(k in raw_text for k in ["高爾夫", "球袋", "球具"]):
        special_items.append("高爾夫球具")
    if any(k in raw_text for k in ["嬰兒推車", "嬰兒車", "推車", "bb車", "娃娃車"]):
        special_items.append("嬰兒推車")
    if any(k in raw_text for k in ["輪椅", "摺疊輪椅", "折疊輪椅"]):
        special_items.append("摺疊輪椅")
    if any(k in raw_text for k in ["大型紙箱", "出國紙箱", "紙箱"]):
        special_items.append("大型紙箱")
    if any(k in raw_text for k in ["雪板", "滑雪板", "衝浪板"]):
        special_items.append("雪板/衝浪板")
    special_luggage_str = ", ".join(special_items) if special_items else None

    # 大箱 (28~32 吋托運大箱)
    luggage_large = 0
    large_match1 = re.search(r'(?:(?:28|29|30|31|32)\s*吋[^\d一二兩三四五六七八九十\n]*[x*×:]?\s*(\d+|[一二兩三四五六七八九十]+)|(\d+|[一二兩三四五六七八九十]+)\s*(?:件|個)?\s*(?:28|29|30|31|32)\s*吋)', raw_text, re.IGNORECASE)
    if large_match1:
        luggage_large = parse_num_chinese(large_match1.group(1) or large_match1.group(2))
    else:
        large_match2 = re.search(r'(\d+|[一二兩三四五六七八九十]+)\s*(?:件|個)?\s*(?:大箱|大行李|大行李箱)', raw_text)
        if large_match2:
            luggage_large = parse_num_chinese(large_match2.group(1))

    # 登機/中箱 (20~24 吋登機箱)
    luggage_small = 0
    small_match1 = re.search(r'(?:(?:20|22|24)\s*吋[^\d一二兩三四五六七八九十\n]*[x*×:]?\s*(\d+|[一二兩三四五六七八九十]+)|(\d+|[一二兩三四五六七八九十]+)\s*(?:件|個)?\s*(?:20|22|24)\s*吋)', raw_text, re.IGNORECASE)
    if small_match1:
        luggage_small = parse_num_chinese(small_match1.group(1) or small_match1.group(2))
    else:
        small_match2 = re.search(r'(\d+|[一二兩三四五六七八九十]+)\s*(?:件|個)?\s*(?:登機箱|小箱|隨身箱|手提箱)', raw_text)
        if small_match2:
            luggage_small = parse_num_chinese(small_match2.group(1))

    # 一般總行李數提取
    luggage = 1
    if structured_data.get("luggage"):
        luggage = parse_num_chinese(re.search(r'\d+|[一二兩三四五六七八九十]+', str(structured_data["luggage"])).group(0))
    else:
        luggage_match = LUGGAGE_PATTERN.search(raw_text)
        if luggage_match:
            luggage = parse_num_chinese(luggage_match.group(1))

    # 若有提取出具體大箱或小箱，更新總數
    if luggage_large > 0 or luggage_small > 0:
        luggage = max(luggage, luggage_large + luggage_small)
    elif luggage > 0 and luggage_large == 0 and luggage_small == 0:
        # 若未指明尺寸，默認若件數 >= 2 則以大箱估算
        luggage_large = luggage

    # 組裝行李明細字串
    breakdown_parts = []
    if luggage_large > 0:
        breakdown_parts.append(f"28吋大箱x{luggage_large}")
    if luggage_small > 0:
        breakdown_parts.append(f"登機箱x{luggage_small}")
    if special_items:
        breakdown_parts.extend(special_items)
    
    luggage_breakdown = ", ".join(breakdown_parts) if breakdown_parts else f"{luggage} 件行李"

    # 7. 提取航班編號 (長榮 BR, 華航 CI, 星宇 JX, 虎航 IT 等)
    flight_no = structured_data.get("flight_number")
    if not flight_no:
        flight_candidates = FLIGHT_PATTERN.findall(raw_text)
        for cand in flight_candidates:
            cand_clean = cand.replace(" ", "").upper()
            if cand_clean not in ["TPE", "TSA", "BKK", "DMK", "SUV"]:
                flight_no = cand_clean
                break

    # 8. 判定車型與車資 (計算後車廂物理容量防呆)
    fares_table = DEFAULT_FARES_TSA if airport_code == "TSA" else DEFAULT_FARES_TPE
    specified_vehicle = structured_data.get("vehicle_type", "")
    text_vehicle = raw_text.lower()
    
    # 容積點數計算 (大箱=1.0, 登機箱=0.5, 特殊件=1.0)
    special_units = len(special_items) * 1.0
    trunk_units = (luggage_large * 1.0) + (luggage_small * 0.5) + special_units

    if any(k in specified_vehicle or k in text_vehicle for k in ["九人", "9人", "alphard", "t6", "保母車"]):
        vehicle_type = "商務九人座 (T6/Alphard)"
    elif any(k in specified_vehicle or k in text_vehicle for k in ["休旅", "suv"]):
        vehicle_type = "休旅車 SUV (4-6人座)"
    elif any(k in specified_vehicle or k in text_vehicle for k in ["轎車", "房車", "4人座", "四人座", "sedan"]):
        vehicle_type = "標準轎車 (4人座)"
    elif passengers >= 5 or trunk_units > 3.5:
        # 超出 SUV 極限或人數超過 4 人，自動升級九人座
        vehicle_type = "商務九人座 (T6/Alphard)"
    elif passengers >= 4 and trunk_units > 2.0:
        # 4位乘客滿座時後座不可放行李，轎車後車廂極限為2個大箱，超過必須升級SUV
        vehicle_type = "休旅車 SUV (4-6人座)"
    elif passengers >= 3 or trunk_units > 2.0:
        vehicle_type = "休旅車 SUV (4-6人座)"
    else:
        vehicle_type = "標準轎車 (4人座)"

    estimated_fare = float(fares_table.get(vehicle_type, 1100))
    platform_fee = 50.0
    driver_payout = estimated_fare - platform_fee
    customer_name = structured_data.get("customer_name") or sender_name or "貴賓乘客"

    # 判定送機 (DEPARTURE) 還是 接機 (ARRIVAL)
    arrival_keywords = ["接機", "回台北", "返台", "降落", "入境", "機場接", "機場回", "抵達桃機", "抵達松機", "抵達", "接回", "回市區", "返北"]
    if any(k in raw_text for k in arrival_keywords):
        trip_type = "ARRIVAL"
        # 若為接機行程，上車地點在機場入境大廳，目的地為返北地址
        city_dest_match = re.search(r'(?:接回|送回|回到|前往|送到|送至|接送至|到)\s*([^\n,，。]{2,20})', raw_text)
        city_dest = city_dest_match.group(1).strip() if city_dest_match else pickup_location
        if any(k in city_dest for k in ["機場", "桃機", "松機", "航廈"]):
            city_dest = "台北市區 (司機接單後確認地址)"
            
        final_pickup = f"{airport_name} 入境大廳"
        final_destination = f"{city_dest} (返台接機)"
    else:
        trip_type = "DEPARTURE"
        final_pickup = pickup_location
        final_destination = airport_name

    return ParsedBooking(
        is_valid_booking=True,
        is_airport_destination=True,
        trip_type=trip_type,
        destination_airport=final_destination,
        pickup_location=final_pickup,
        pickup_datetime=pickup_datetime,
        flight_number=flight_no,
        passengers=passengers,
        luggage=luggage,
        luggage_large=luggage_large,
        luggage_small=luggage_small,
        special_luggage=special_luggage_str,
        luggage_breakdown=luggage_breakdown,
        customer_phone=phone,
        customer_name=customer_name,
        vehicle_type=vehicle_type,
        estimated_fare=estimated_fare,
        platform_fee=platform_fee,
        driver_payout=driver_payout,
        confidence_score=0.95,
        raw_text=raw_text
    )
