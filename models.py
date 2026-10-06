from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class TripBase(BaseModel):
    customer_name: Optional[str] = "貴賓乘客"
    customer_phone: Optional[str] = None
    line_user_id: Optional[str] = None
    line_group_id: str
    line_group_name: Optional[str] = "LINE 群組"
    trip_type: str = "DEPARTURE"  # DEPARTURE (台北->機場送機), ARRIVAL (機場->台北接機)
    pickup_location: str
    pickup_datetime: str
    destination_airport: str
    terminal_flight_no: Optional[str] = None
    passengers: int = 1
    luggage: int = 1
    luggage_large: Optional[int] = 0        # 28~32 吋托運大箱
    luggage_small: Optional[int] = 0        # 20~24 吋登機/中箱
    special_luggage: Optional[str] = None   # 特殊行李標籤 (高爾夫球具, 嬰兒推車, 輪椅, 紙箱等)
    luggage_breakdown: Optional[str] = None # 完整行李組合字串 (例如: 28吋大箱x2, 登機箱x1, 嬰兒推車x1)
    vehicle_type: str = "標準轎車 (4人座)"
    estimated_fare: float = 1100.0
    platform_fee: float = 50.0   # 平台超低固定服務費 (NT$ 50)
    driver_payout: float = 1050.0 # 司機實拿淨額
    matched_trip_id: Optional[int] = None # 回程不空車配對單號
    notes: Optional[str] = None

class TripCreate(TripBase):
    raw_message: Optional[str] = None

class TripUpdate(BaseModel):
    status: Optional[str] = None
    driver_id: Optional[int] = None
    notes: Optional[str] = None
    pickup_datetime: Optional[str] = None
    pickup_location: Optional[str] = None
    destination_airport: Optional[str] = None
    estimated_fare: Optional[float] = None
    matched_trip_id: Optional[int] = None

class Trip(TripBase):
    id: int
    status: str = "NEW"  # NEW, ASSIGNED, EN_ROUTE, PICKED_UP, COMPLETED, CANCELLED
    driver_id: Optional[int] = None
    driver_name: Optional[str] = None
    driver_phone: Optional[str] = None
    driver_vehicle: Optional[str] = None
    driver_plate: Optional[str] = None
    raw_message: Optional[str] = None
    created_at: str
    updated_at: str

class DriverBase(BaseModel):
    name: str
    phone: str
    vehicle_model: str
    license_plate: str
    vehicle_type: str = "標準轎車 (4人座)"
    is_active: bool = True

class DriverCreate(DriverBase):
    pass

class Driver(DriverBase):
    id: int
    total_trips: int = 0
    rating: float = 5.0
    created_at: str

class LineGroup(BaseModel):
    id: int
    group_id: str
    group_name: str
    joined_at: str
    last_message_at: Optional[str] = None
    trip_count: int = 0
    is_active: bool = True

class AssignDriverRequest(BaseModel):
    driver_id: int
    bundle_matched_trip: bool = False # 是否一鍵雙向連環接單 (送機+回程接機)

class LineKeysRequest(BaseModel):
    channel_secret: str
    channel_access_token: str

class ParsedBooking(BaseModel):
    is_valid_booking: bool
    is_airport_destination: bool
    trip_type: str = "DEPARTURE" # DEPARTURE 或 ARRIVAL
    destination_airport: Optional[str] = None
    pickup_location: Optional[str] = None
    pickup_datetime: Optional[str] = None
    flight_number: Optional[str] = None
    passengers: int = 1
    luggage: int = 1
    luggage_large: int = 0
    luggage_small: int = 0
    special_luggage: Optional[str] = None
    luggage_breakdown: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_name: Optional[str] = None
    vehicle_type: str = "標準轎車 (4人座)"
    estimated_fare: float = 1100.0
    platform_fee: float = 50.0
    driver_payout: float = 1050.0
    confidence_score: float = 0.0
    rejection_reason: Optional[str] = None
    raw_text: str

class SimulatorMessageRequest(BaseModel):
    group_id: str
    group_name: str
    sender_name: str
    message_text: str
