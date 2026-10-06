import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    BASE_DIR = Path(__file__).resolve().parent
    load_dotenv(BASE_DIR / ".env")
except Exception:
    pass
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
BASE_URL = os.getenv("BASE_URL", f"http://localhost:{PORT}")

# 嚴格限定目的地機場 (台灣台北地區主力機場)
DEFAULT_AIRPORTS = [
    {
        "code": "TPE",
        "name": "桃園國際機場 (TPE)",
        "name_en": "Taoyuan International Airport",
        "aliases": [
            "tpe", "桃園機場", "桃機", "桃園國際機場", "第一航廈", "第二航廈",
            "taoyuan", "taoyuan airport"
        ]
    },
    {
        "code": "TSA",
        "name": "台北松山機場 (TSA)",
        "name_en": "Taipei Songshan Airport",
        "aliases": [
            "tsa", "松山機場", "松機", "松山", "台北機場",
            "songshan", "songshan airport"
        ]
    }
]

# 車種分類 (台灣專車標準車種)
VEHICLE_TYPES = ["標準轎車 (4人座)", "休旅車 SUV (4-6人座)", "商務九人座 (T6/Alphard)", "頂級保母車"]

# 預估參考車資 (新台幣 NT$) - 台北市區至桃園機場基準 (松山機場另計)
DEFAULT_FARES_TPE = {
    "標準轎車 (4人座)": 1100,
    "休旅車 SUV (4-6人座)": 1300,
    "商務九人座 (T6/Alphard)": 1800,
    "頂級保母車": 2500
}

DEFAULT_FARES_TSA = {
    "標準轎車 (4人座)": 600,
    "休旅車 SUV (4-6人座)": 800,
    "商務九人座 (T6/Alphard)": 1200,
    "頂級保母車": 1800
}
