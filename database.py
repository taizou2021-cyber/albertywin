import os
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any

import tempfile

# 在 Vercel Serverless 雲端無伺服器環境中，只有臨時目錄 (如 /tmp) 具備可寫入權限
if os.environ.get("VERCEL"):
    temp_dir = Path(tempfile.gettempdir())
    temp_dir.mkdir(parents=True, exist_ok=True)
    DB_PATH = temp_dir / "dispatch.db"
    source_db = Path(__file__).resolve().parent / "dispatch.db"
    if not DB_PATH.exists() and source_db.exists():
        try:
            shutil.copy2(source_db, DB_PATH)
        except Exception:
            pass
else:
    DB_PATH = Path(__file__).resolve().parent / "dispatch.db"

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(force_reseed: bool = False):
    with get_db() as conn:
        cursor = conn.cursor()

        if force_reseed:
            cursor.execute("DROP TABLE IF EXISTS trips")
            cursor.execute("DROP TABLE IF EXISTS drivers")
            cursor.execute("DROP TABLE IF EXISTS line_groups")
            cursor.execute("DROP TABLE IF EXISTS messages_log")
        
        # Trips table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            line_group_id TEXT NOT NULL,
            line_group_name TEXT,
            line_user_id TEXT,
            customer_name TEXT,
            customer_phone TEXT,
            trip_type TEXT DEFAULT 'DEPARTURE',
            pickup_location TEXT NOT NULL,
            pickup_datetime TEXT NOT NULL,
            destination_airport TEXT NOT NULL,
            terminal_flight_no TEXT,
            passengers INTEGER DEFAULT 1,
            luggage INTEGER DEFAULT 1,
            luggage_large INTEGER DEFAULT 0,
            luggage_small INTEGER DEFAULT 0,
            special_luggage TEXT,
            luggage_breakdown TEXT,
            vehicle_type TEXT DEFAULT '標準轎車 (4人座)',
            estimated_fare REAL DEFAULT 1100.0,
            platform_fee REAL DEFAULT 50.0,
            driver_payout REAL DEFAULT 1050.0,
            matched_trip_id INTEGER,
            status TEXT DEFAULT 'NEW',
            driver_id INTEGER,
            raw_message TEXT,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (driver_id) REFERENCES drivers (id)
        )
        """)

        # Migration for existing databases
        cursor.execute("PRAGMA table_info(trips)")
        existing_cols = [row[1] for row in cursor.fetchall()]
        needed_cols = {
            "trip_type": "TEXT DEFAULT 'DEPARTURE'",
            "platform_fee": "REAL DEFAULT 50.0",
            "driver_payout": "REAL DEFAULT 1050.0",
            "matched_trip_id": "INTEGER",
            "luggage_large": "INTEGER DEFAULT 0",
            "luggage_small": "INTEGER DEFAULT 0",
            "special_luggage": "TEXT",
            "luggage_breakdown": "TEXT"
        }
        for col, col_def in needed_cols.items():
            if col not in existing_cols:
                cursor.execute(f"ALTER TABLE trips ADD COLUMN {col} {col_def}")

        # Drivers table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS drivers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            vehicle_model TEXT NOT NULL,
            license_plate TEXT NOT NULL,
            vehicle_type TEXT DEFAULT '標準轎車 (4人座)',
            is_active INTEGER DEFAULT 1,
            total_trips INTEGER DEFAULT 0,
            rating REAL DEFAULT 5.0,
            created_at TEXT NOT NULL
        )
        """)

        # LINE Groups table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS line_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id TEXT UNIQUE NOT NULL,
            group_name TEXT NOT NULL,
            joined_at TEXT NOT NULL,
            last_message_at TEXT,
            trip_count INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1
        )
        """)

        # Message logs
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id TEXT NOT NULL,
            sender_name TEXT,
            sender_id TEXT,
            message_text TEXT NOT NULL,
            is_booking INTEGER DEFAULT 0,
            timestamp TEXT NOT NULL
        )
        """)

        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM drivers")
        driver_count = cursor.fetchone()[0]
        if driver_count == 0 or force_reseed:
            if force_reseed:
                cursor.execute("DELETE FROM drivers")
                cursor.execute("DELETE FROM line_groups")
                cursor.execute("DELETE FROM trips")
                
            now = datetime.now()
            now_iso = now.isoformat()
            tomorrow_date = (now + timedelta(days=1)).strftime("%Y-%m-%d")

            seed_drivers = [
                ("陳大明 (老陳)", "0912-345-678", "Toyota Camry 油電尊爵 (黑)", "TDH-8821", "標準轎車 (4人座)", 1, 158, 4.96, now_iso),
                ("林建宏 (阿宏)", "0933-882-910", "Toyota RAV4 Hybrid (珍珠白)", "BCP-1108", "休旅車 SUV (4-6人座)", 1, 112, 4.93, now_iso),
                ("黃志強 (強哥)", "0921-554-719", "Toyota Alphard / 福斯 T6 (黑)", "RBT-9214", "商務九人座 (T6/Alphard)", 1, 246, 4.98, now_iso),
                ("張偉哲 (David)", "0955-771-320", "Lexus ES300h 頂級旗艦 (銀)", "TDJ-7731", "標準轎車 (4人座)", 1, 84, 4.91, now_iso)
            ]
            cursor.executemany("""
                INSERT INTO drivers (name, phone, vehicle_model, license_plate, vehicle_type, is_active, total_trips, rating, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, seed_drivers)

            seed_groups = [
                ("tw-group-taipei-hotels", "台北五星飯店禮賓部送機群", now_iso, now_iso, 1, 1),
                ("tw-group-xinyi-residence", "信義/大安豪宅住戶專車叫車群", now_iso, now_iso, 1, 1),
                ("tw-group-taiwan-biz-expat", "台北外商/台商高階機場接送中心", now_iso, now_iso, 0, 1),
                ("tw-group-driver-fleet", "【台北機場專車】車隊司機即時搶單大群", now_iso, now_iso, 0, 1)
            ]
            cursor.executemany("""
                INSERT INTO line_groups (group_id, group_name, joined_at, last_message_at, trip_count, is_active)
                VALUES (?, ?, ?, ?, ?, ?)
            """, seed_groups)

            # 建立示範行程：一筆「早晨送機單」與一筆「回程接機單 (回程不空車配對示範)」
            seed_trips = [
                (
                    "tw-group-taipei-hotels", "台北五星飯店禮賓部送機群", "user-concierge-01",
                    "晶華酒店禮賓部 (轉交陳副總)", "0912-345-678", "DEPARTURE",
                    "台北晶華酒店大廳門口", f"{tomorrow_date} 06:30 (明天早鳥)",
                    "桃園國際機場 (TPE) 第二航廈", "BR87", 4, 4,
                    3, 1, "高爾夫球具", "28吋大箱x3, 登機箱x1, 高爾夫球具x1",
                    "商務九人座 (T6/Alphard)", 1800.0, 50.0, 1750.0,
                    None, "NEW", None, "需要九人座商務車前往桃機二航",
                    "早鳥早班機，行李較多", now_iso, now_iso
                ),
                (
                    "tw-group-xinyi-residence", "信義/大安豪宅住戶專車叫車群", "user-vip-02",
                    "林董事長 (返台接機)", "0933-882-910", "ARRIVAL",
                    "桃園國際機場 (TPE) 第二航廈入境大廳", f"{tomorrow_date} 08:30 (接機順風)",
                    "桃園國際機場 (TPE)", "BR88", 2, 2,
                    2, 0, None, "28吋大箱x2",
                    "標準轎車 (4人座)", 1300.0, 50.0, 1250.0,
                    None, "NEW", None, "班機 BR88 預計 08:00 降落桃機，接送回台北信義區",
                    "回程順風單：目的地台北市信義區信義路五段", now_iso, now_iso
                )
            ]
            cursor.executemany("""
                INSERT INTO trips (
                    line_group_id, line_group_name, line_user_id,
                    customer_name, customer_phone, trip_type,
                    pickup_location, pickup_datetime, destination_airport,
                    terminal_flight_no, passengers, luggage,
                    luggage_large, luggage_small, special_luggage, luggage_breakdown,
                    vehicle_type, estimated_fare, platform_fee, driver_payout,
                    matched_trip_id, status, driver_id, raw_message,
                    notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, seed_trips)

            conn.commit()

# --- DB Helper Methods ---

def create_trip(data: Dict[str, Any]) -> int:
    with get_db() as conn:
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        fare = float(data.get("estimated_fare", 1100.0))
        platform_fee = float(data.get("platform_fee", 50.0))
        driver_payout = float(data.get("driver_payout", fare - platform_fee))
        
        # 組裝行李明細字串 (若無明確字串則自動根據數量組裝)
        luggage_large = int(data.get("luggage_large", 0))
        luggage_small = int(data.get("luggage_small", 0))
        special_luggage = data.get("special_luggage")
        luggage_breakdown = data.get("luggage_breakdown")
        
        if not luggage_breakdown:
            parts = []
            if luggage_large > 0:
                parts.append(f"28~32吋大箱x{luggage_large}")
            if luggage_small > 0:
                parts.append(f"登機箱x{luggage_small}")
            if special_luggage:
                parts.append(special_luggage)
            if parts:
                luggage_breakdown = ", ".join(parts)
            else:
                total_luggage = data.get("luggage", 1)
                luggage_breakdown = f"{total_luggage} 件行李"

        cursor.execute("""
            INSERT INTO trips (
                line_group_id, line_group_name, line_user_id, customer_name,
                customer_phone, trip_type, pickup_location, pickup_datetime,
                destination_airport, terminal_flight_no, passengers, luggage,
                luggage_large, luggage_small, special_luggage, luggage_breakdown,
                vehicle_type, estimated_fare, platform_fee, driver_payout,
                matched_trip_id, status, driver_id, raw_message, notes,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("line_group_id"),
            data.get("line_group_name", "LINE 群組"),
            data.get("line_user_id"),
            data.get("customer_name", "貴賓乘客"),
            data.get("customer_phone"),
            data.get("trip_type", "DEPARTURE"),
            data.get("pickup_location"),
            data.get("pickup_datetime"),
            data.get("destination_airport"),
            data.get("terminal_flight_no"),
            data.get("passengers", 1),
            data.get("luggage", 1),
            luggage_large,
            luggage_small,
            special_luggage,
            luggage_breakdown,
            data.get("vehicle_type", "標準轎車 (4人座)"),
            fare,
            platform_fee,
            driver_payout,
            data.get("matched_trip_id"),
            data.get("status", "NEW"),
            data.get("driver_id"),
            data.get("raw_message"),
            data.get("notes"),
            now,
            now
        ))
        trip_id = cursor.lastrowid
        
        cursor.execute("""
            UPDATE line_groups SET trip_count = trip_count + 1, last_message_at = ?
            WHERE group_id = ?
        """, (now, data.get("line_group_id")))
        
        conn.commit()
        return trip_id

def get_trip(trip_id: int) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.*, d.name as driver_name, d.phone as driver_phone,
                   d.vehicle_model as driver_vehicle, d.license_plate as driver_plate
            FROM trips t
            LEFT JOIN drivers d ON t.driver_id = d.id
            WHERE t.id = ?
        """, (trip_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_trips(status: Optional[str] = None, group_id: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        query = """
            SELECT t.*, d.name as driver_name, d.phone as driver_phone,
                   d.vehicle_model as driver_vehicle, d.license_plate as driver_plate
            FROM trips t
            LEFT JOIN drivers d ON t.driver_id = d.id
            WHERE 1=1
        """
        params = []
        if status:
            query += " AND t.status = ?"
            params.append(status)
        if group_id:
            query += " AND t.line_group_id = ?"
            params.append(group_id)
            
        query += " ORDER BY t.id DESC"
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

def find_return_matches(trip_id: int) -> List[Dict[str, Any]]:
    """
    智能「回程不空車」配對引擎：
    若為「台北 -> 機場 (DEPARTURE)」，搜尋該機場待接單的「機場 -> 台北 (ARRIVAL)」接機單；
    讓司機出車一趟能接兩單，利潤翻倍，零空車返北。
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trips WHERE id = ?", (trip_id,))
        base_trip = cursor.fetchone()
        if not base_trip:
            return []

        base_type = base_trip["trip_type"]
        target_type = "ARRIVAL" if base_type == "DEPARTURE" else "DEPARTURE"
        target_airport = "TPE" if ("TPE" in base_trip["destination_airport"] or "桃園" in base_trip["destination_airport"] or "TPE" in base_trip["pickup_location"] or "桃園" in base_trip["pickup_location"]) else "TSA"

        cursor.execute("""
            SELECT * FROM trips
            WHERE id != ?
              AND status = 'NEW'
              AND trip_type = ?
              AND (destination_airport LIKE ? OR pickup_location LIKE ?)
            ORDER BY id ASC LIMIT 3
        """, (trip_id, target_type, f"%{target_airport}%", f"%{target_airport}%"))

        return [dict(row) for row in cursor.fetchall()]

def assign_driver_to_trip(trip_id: int, driver_id: int, bundle_matched: bool = False) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        
        cursor.execute("SELECT * FROM trips WHERE id = ?", (trip_id,))
        trip = cursor.fetchone()
        if not trip or trip["status"] in ["COMPLETED", "CANCELLED"]:
            return None
            
        cursor.execute("""
            UPDATE trips
            SET driver_id = ?, status = 'ASSIGNED', updated_at = ?
            WHERE id = ?
        """, (driver_id, now, trip_id))
        
        trips_assigned = 1

        # 若司機選擇「一鍵雙向連環接單 (去程送機 + 回程接機)」
        if bundle_matched:
            matches = find_return_matches(trip_id)
            if matches:
                matched_id = matches[0]["id"]
                cursor.execute("""
                    UPDATE trips
                    SET driver_id = ?, status = 'ASSIGNED', matched_trip_id = ?, updated_at = ?
                    WHERE id = ?
                """, (driver_id, trip_id, now, matched_id))
                
                cursor.execute("UPDATE trips SET matched_trip_id = ? WHERE id = ?", (matched_id, trip_id))
                trips_assigned += 1

        cursor.execute("""
            UPDATE drivers SET total_trips = total_trips + ? WHERE id = ?
        """, (trips_assigned, driver_id))
        
        conn.commit()
        return get_trip(trip_id)

def update_trip_status(trip_id: int, status: str, notes: Optional[str] = None) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        if notes is not None:
            cursor.execute("""
                UPDATE trips SET status = ?, notes = ?, updated_at = ? WHERE id = ?
            """, (status, notes, now, trip_id))
        else:
            cursor.execute("""
                UPDATE trips SET status = ?, updated_at = ? WHERE id = ?
            """, (status, now, trip_id))
        conn.commit()
        return cursor.rowcount > 0

def get_drivers(active_only: bool = True) -> List[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        if active_only:
            cursor.execute("SELECT * FROM drivers WHERE is_active = 1 ORDER BY name ASC")
        else:
            cursor.execute("SELECT * FROM drivers ORDER BY name ASC")
        return [dict(row) for row in cursor.fetchall()]

def get_driver(driver_id: int) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM drivers WHERE id = ?", (driver_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def create_driver(data: Dict[str, Any]) -> int:
    with get_db() as conn:
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO drivers (name, phone, vehicle_model, license_plate, vehicle_type, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("name"),
            data.get("phone"),
            data.get("vehicle_model"),
            data.get("license_plate"),
            data.get("vehicle_type", "標準轎車 (4人座)"),
            1 if data.get("is_active", True) else 0,
            now
        ))
        conn.commit()
        return cursor.lastrowid

def upsert_group(group_id: str, group_name: str) -> Dict[str, Any]:
    with get_db() as conn:
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute("SELECT * FROM line_groups WHERE group_id = ?", (group_id,))
        existing = cursor.fetchone()
        if existing:
            cursor.execute("""
                UPDATE line_groups SET group_name = ?, last_message_at = ?, is_active = 1
                WHERE group_id = ?
            """, (group_name, now, group_id))
        else:
            cursor.execute("""
                INSERT INTO line_groups (group_id, group_name, joined_at, last_message_at, trip_count, is_active)
                VALUES (?, ?, ?, ?, 0, 1)
            """, (group_id, group_name, now, now))
        conn.commit()
        
        cursor.execute("SELECT * FROM line_groups WHERE group_id = ?", (group_id,))
        return dict(cursor.fetchone())

def get_groups() -> List[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM line_groups ORDER BY last_message_at DESC")
        return [dict(row) for row in cursor.fetchall()]

def log_message(group_id: str, sender_name: str, sender_id: str, message_text: str, is_booking: bool = False):
    with get_db() as conn:
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO messages_log (group_id, sender_name, sender_id, message_text, is_booking, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (group_id, sender_name, sender_id, message_text, 1 if is_booking else 0, now))
        conn.commit()

def get_dashboard_stats() -> Dict[str, Any]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM trips")
        total_trips = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM trips WHERE status = 'NEW'")
        new_trips = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM trips WHERE status IN ('ASSIGNED', 'EN_ROUTE', 'PICKED_UP')")
        active_trips = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM trips WHERE status = 'COMPLETED'")
        completed_trips = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM drivers WHERE is_active = 1")
        active_drivers = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM line_groups WHERE is_active = 1")
        total_groups = cursor.fetchone()[0]
        
        return {
            "total_trips": total_trips,
            "new_trips": new_trips,
            "active_trips": active_trips,
            "completed_trips": completed_trips,
            "active_drivers": active_drivers,
            "total_groups": total_groups
        }
