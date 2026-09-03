# Project Khet2Kitchen (K2K): Digital Supply Chain Architecture

> **A "Phygital" Agricultural Supply Chain Platform Engineered to Systematically Replace Middlemen.**

Built with **Python 3.12+**, **Django 5+**, **Django REST Framework (DRF)**, **MySQL**, and prepared for 1-click cloud deployment on **Render**.

---

## 🌾 Overview & Core Value Proposition

Traditional agricultural supply chains in emerging markets suffer from severe fragmentation, exploitative intermediaries (aggregators, commission agents, moneylenders), and high post-harvest losses (up to 30-40% in perishables).

**Project Khet2Kitchen (K2K)** introduces the **K2K Intelligence Engine** — a central decision-making layer that:
1. **Replaces the Aggregator**: Locks pre-harvest retailer demand to direct algorithmic harvest windows and eliminate market gluts.
2. **Replaces Subjective Inspection**: Deploys Computer Vision AI grading to evaluate produce objectively on commercial sizing, color uniformity, and surface defects with human-in-the-loop fallback.
3. **Guarantees Transparent Pricing**: Enforces unbreachable Minimum Support Price (MSP) price-floor protection with itemized formula transparency.
4. **Replaces the Predatory Moneylender**: Provides in-kind financing (certified seeds, bio-fertilizers) and automates atomic payback deductions upon harvest.
5. **Replaces the Transporter**: Dynamically clusters village micro-hubs into commercial truck sweeps prioritized by crop perishability (e.g. leafy greens swept first).

---

## 🏛️ System Architecture

```
                               ┌──────────────────────────────────────────────┐
                               │       Client Interaction Layers              │
                               │  - K2K Command Center (B2B Admin Dashboard)  │
                               │  - Farmer Voice UI (Regional NLP Assistant)   │
                               │  - Urban Retailer Demand Portal              │
                               └──────────────────────┬───────────────────────┘
                                                      │
                                                      ▼
 ┌─────────────────────────────────────────────────────────────────────────────────────────────┐
 │                         🧠 K2K Intelligence Engine (Central Decision Layer)                  │
 ├──────────────────────────┬──────────────────────────┬───────────────────────────────────────┤
 │ 1. Demand-Lock System    │ 2. Algorithmic Matching   │ 3. Micro-Hub & Batch Traceability     │
 │    Retailer Pre-Orders   │    Farmer Allocation     │    SHA-256 Chain (Farm -> Kitchen)    │
 ├──────────────────────────┼──────────────────────────┼───────────────────────────────────────┤
 │ 4. CV AI Grading Engine  │ 5. Dynamic Pricing Engine │ 6. Agri-Fintech Payout & Recovery     │
 │    Confidence Guardrail  │    MSP Floor Guarantee   │    Atomic In-Kind Loan Deductions     │
 ├──────────────────────────┴──────────────────────────┴───────────────────────────────────────┤
 │ 7. Perishability-Weighted Dynamic Route Optimizer (Consolidated Village Hub Sweeps)         │
 └────────────────────────────────────────────┬────────────────────────────────────────────────┘
                                              │
                                              ▼
                             ┌───────────────────────────────────┐
                             │       Persistence & Cloud Infra   │
                             │  - MySQL Database / TiDB / RDS    │
                             │  - Render Web Service + Gunicorn  │
                             └───────────────────────────────────┘
```

---

## 📦 Database Schema & Models (`k2k_core/models.py`)

| Model | Purpose | Key Attributes |
|---|---|---|
| **`User`** | Role-Based Access Control | `FARMER`, `HUB_MANAGER`, `RETAILER`, `ADMIN`, Phone-first auth, Regional Dialect (`hi`, `mr`, `te`, `ta`, `kn`) |
| **`FarmerProfile`** | Farm & Credit Profile | Land acreage, Soil type, **K2K Farm Reliability Score** (0-100), Credit limit, UPI details |
| **`RetailerProfile`** | B2B Urban Buyer | Supermarket/Restaurant business details, GSTIN, Delivery address |
| **`MicroHub`** | Village Drop-Off Center | GPS Coordinates, Capacity (kg), Cold-chain facility, Status |
| **`Crop`** | Agricultural Master | Perishability Tier (`URGENT_24H`, `HIGH_48H`, `MEDIUM_7D`, `STABLE_30D`), Statutory MSP Floor Price, Benchmark price |
| **`DemandOrder`** | Retailer Demand-Lock | Locked volume, Guaranteed price, Target delivery date, Grade requirements |
| **`HarvestSchedule`** | Algorithmic Supply Matching | Allocated farmer volume, Harvest time window, Drop-off deadline, Match score |
| **`ProduceBatch`** | Cryptographic Traceability | Batch ID, **SHA-256 Trace Hash**, Shelf-life hours remaining, Dynamic Freshness Score |
| **`AIGradingRecord`** | Computer Vision Grading | Size uniformity, Color uniformity, Surface defect %, Final Grade (`A`/`B`/`C`/`Reject`), Confidence Score, **0.82 Confidence Threshold Fallback** |
| **`DynamicPricingRecord`**| Transparent Dynamic Pricing | Base value, Grade premium, Demand surge bonus, Logistics deduction, **Price Floor Enforced Flag**, Final Unit Price |
| **`InputLoan`** | In-Kind Financing | Certified seeds / bio-fertilizers delivered on credit, Outstanding balance, Repayment ledger |
| **`FarmerWallet`** | Digital Wallet | Current balance, Lifetime earnings, Instant UPI credit |
| **`PayoutSettlement`** | Atomic Settlement | Gross revenue, Automated in-kind loan deduction, Net payout, UTR reference |
| **`Vehicle` & `TransitRoute`**| Dynamic Sweep Logistics | Truck payload capacity, Reefer status, Waypoints ordered by crop perishability |

---

## 🚀 Core API Endpoints

### 1. Computer Vision AI Quality Grading
- **Endpoint**: `POST /api/v1/grading/scan/`
- **Payload**:
  ```json
  {
    "batch_id": "K2K-2026-TOM-DEMO01",
    "simulation_size_uniformity": 92.0,
    "simulation_color_uniformity": 94.0,
    "simulation_surface_defect_pct": 3.0,
    "simulation_confidence_score": 0.930
  }
  ```
- **Confidence Fallback**:
  - If `confidence_score >= 0.82`: Produces immediate Commercial Grade (`GRADE_A`).
  - If `confidence_score < 0.82`: Automatically flags batch with `FLAGGED_FOR_MANUAL_REVIEW` and routes to Hub Manager.
- **Hub Manager Audit Endpoint**: `POST /api/v1/grading/manual-review/`

### 2. Transparent Dynamic Pricing Engine
- **Endpoint**: `POST /api/v1/pricing/calculate/`
- **Formula**:
  $$\text{Final Price} = \max(\text{MSP Floor}, \text{Base Value} + \text{Grade Premium} + \text{Demand Surge} - \text{Logistics Deduction})$$
- **Itemized Transparency Response**:
  ```json
  {
    "status": "OFFER_CALCULATED",
    "final_unit_price_per_kg": 27.50,
    "total_gross_amount": 11000.00,
    "price_floor_enforced": false,
    "itemized_transparency_breakdown": {
      "base_market_price_per_kg": 24.00,
      "quality_grade_adjustment_per_kg": 6.00,
      "demand_surge_bonus_per_kg": 0.00,
      "logistics_transport_deduction_per_kg": 2.50,
      "statutory_msp_price_floor_per_kg": 14.00,
      "transparency_guarantee": "K2K guarantees 100% price transparency. No hidden commission."
    }
  }
  ```
- **Acceptance Endpoint**: `POST /api/v1/pricing/accept-offer/`

### 3. Integrated Agri-Fintech & Automated Payback
- **Endpoint**: `POST /api/v1/fintech/settle-payout/`
- **Execution**: Atomic database transaction (`transaction.atomic`).
  1. Computes gross batch revenue.
  2. Identifies active in-kind input loans (seeds/bio-fertilizers).
  3. Automatically deducts loan balance (capped at 50% max of harvest check to ensure farmer liquidity).
  4. Credits remaining net profit directly to farmer's UPI/Wallet.
  5. Generates audited settlement slip with UTR bank reference.
- **Wallet Detail Endpoint**: `GET /api/v1/fintech/wallet/?phone=+919876543210`

### 4. Perishability-Weighted Route Optimization
- **Endpoint**: `POST /api/v1/logistics/optimize-routes/`
- **Algorithm**:
  - Sweeps active micro-hubs with inventory awaiting transit.
  - Multiplies batch weight by Crop Perishability Tier (`URGENT_24H` leafy greens = 3.5x urgency).
  - Consolidates smallholder batches into commercial vehicle payloads (3,500 kg).
  - Emits ordered waypoint sweeps ensuring urgent crops reach urban centers first.
- **Routes List Endpoint**: `GET /api/v1/logistics/routes/`

### 5. K2K Command Center (B2B Admin Dashboard)
- **Endpoint**: `GET /api/v1/command-center/overview/`
- Real-time telemetry: Active crop inventory, unmatched retailer demand, fleet truck GPS coordinates, and urgent spoilage alerts.

### 6. Farmer Multilingual Voice/UI NLP Assistant
- **Endpoint**: `POST /api/v1/voice-assistant/process-command/`
- **Payload**:
  ```json
  {
    "voice_transcript": "आज टमाटर का क्या भाव है?",
    "language": "hi",
    "farmer_phone": "+919876543210"
  }
  ```
- Recognizes farmer intents (`CHECK_PRICE`, `LOG_HARVEST`, `INPUT_FINANCING`, `WALLET_STATUS`) and responds with localized text-to-speech audio script.

---

## 🖥️ Frontend Integration Strategy

### 1. K2K Command Center (B2B Admin Dashboard)
- **Tech Stack**: React 18 / Vite + Tailwind CSS / Leaflet Maps + Recharts.
- **Data Channels**:
  - Polling `GET /api/v1/command-center/overview/` every 10 seconds.
  - Interactive Map: Renders active micro-hubs (color-coded by storage capacity) and moving truck markers.
  - Exception Modal: One-click approval for low-confidence AI scans (`/api/v1/grading/manual-review/`) and Grade C re-routing to puree processors.

### 2. Farmer Multilingual Voice/UI Layer
- **Tech Stack**: Progressive Web App (PWA) with Web Speech API / Whisper STT + Responsive Touch UI.
- **Dialect Handling**: Farmers speak in Hindi, Marathi, Telugu, etc. The client sends speech audio transcript to `/api/v1/voice-assistant/process-command/` and receives structured action data and translated speech responses for audio playback.

---

## ☁️ Deployment on Render

The repository is configured for Render deployment via `render.yaml`:

```yaml
services:
  - type: web
    name: k2k-api
    runtime: python
    buildCommand: "./build.sh"
    startCommand: "gunicorn k2k_project.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --timeout 120"
    plan: starter
    region: singapore
    envVars:
      - key: DJANGO_SETTINGS_MODULE
        value: k2k_project.settings
      - key: DATABASE_URL
        fromDatabase:
          name: k2k-mysql
          property: connectionString
```

### Steps to Deploy:
1. Connect this repository to your [Render Dashboard](https://dashboard.render.com).
2. Click **New + Blueprint** and select this repo (`render.yaml` will be auto-detected).
3. Render will provision the MySQL database and Web Service running `build.sh`.

---

## 🧪 Local Setup & Verification

```bash
# 1. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Apply migrations
python manage.py migrate

# 4. Seed demo data
python manage.py seed_demo_data

# 5. Run test suite
python manage.py test k2k_core

# 6. Start development server
python manage.py runserver
```
