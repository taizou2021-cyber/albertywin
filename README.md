# ✈️ Airport-Only Driver Dispatch Hub (LINE Multi-Group System)

An automated driver dispatch platform built specifically for **Airport-Only Transfers** that connects directly into multiple LINE chat groups. It listens to group messages, extracts passenger flight and pick-up details, validates that the trip is to an airport (Suvarnabhumi BKK or Don Mueang DMK), alerts drivers, and posts real-time driver confirmation cards back to the LINE group.

---

## 🌟 Key Features

1. **Airport-Only Trip Enforcement**:
   - Destination is strictly validated. Non-airport ride requests are automatically detected and declined with a helpful service notice.
   - Supports Suvarnabhumi Airport (BKK), Don Mueang Airport (DMK), terminals, and flight numbers.

2. **Multi-Group LINE Listening**:
   - Built to operate seamlessly across multiple LINE chat groups simultaneously (concierge groups, condo groups, expat groups, travel agency groups).
   - Auto-discovers and records groups as soon as messages are received.

3. **Dispatcher Control Center (`/`)**:
   - Real-time live dashboard with KPIs, incoming booking queue, group monitors, and driver assignment controls.

4. **Mobile Driver Job Portal (`/driver`)**:
   - Mobile-first interface for drivers to view available airport jobs, review payout & luggage needs, and accept trips with 1 tap.
   - Status progression: `En Route` -> `Picked Up` -> `Completed`.

5. **Built-in Interactive LINE Simulator (`/simulator`)**:
   - Test group messaging, bot flex replies, and driver dispatching immediately without needing an active webhook tunnel.

---

## 🚀 Quick Start

### 1. Run the Server
From this directory:
```powershell
py main.py
```
Or with uvicorn:
```powershell
py -m uvicorn main:app --reload --port 8000
```

### 2. Access the Applications
- **Dispatcher Control Center**: [http://localhost:8000/](http://localhost:8000/)
- **Driver Mobile Portal**: [http://localhost:8000/driver](http://localhost:8000/driver)
- **LINE Multi-Group Simulator**: [http://localhost:8000/simulator](http://localhost:8000/simulator)
- **Swagger API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🧪 Run Automated Tests
```powershell
py -m unittest tests/test_dispatch.py
```

---

## 📖 LINE Official Account Setup
See [LINE_SETUP_GUIDE.md](LINE_SETUP_GUIDE.md) for full instructions on creating your bot channel, enabling group chat permissions, and inviting the bot into all your driver groups.
