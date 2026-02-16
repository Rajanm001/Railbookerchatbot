# Package Finder System — Complete Technical Report

**Application:** Railbookers Rail Vacation Planner v2.0.0  
**Author:** Rajan Mishra  
**Date:** February 2026  
**Status:** Production Ready — All 586+ tests passing

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture Diagram](#2-architecture-diagram)
3. [PostgreSQL Data Layer](#3-postgresql-data-layer)
4. [Backend — FastAPI Server](#4-backend--fastapi-server)
5. [Recommendation Engine — Core Algorithm](#5-recommendation-engine--core-algorithm)
6. [Frontend — Package Finder UI](#6-frontend--package-finder-ui)
7. [End-to-End Data Flow](#7-end-to-end-data-flow)
8. [Files & Their Roles](#8-files--their-roles)
9. [Coding Algorithms & Techniques](#9-coding-algorithms--techniques)
10. [Tools & Technologies Used](#10-tools--technologies-used)
11. [Test Coverage Summary](#11-test-coverage-summary)
12. [Security & Anti-Hallucination](#12-security--anti-hallucination)
13. [Performance Characteristics](#13-performance-characteristics)

---

## 1. System Overview

The Package Finder is a full-stack search & recommendation system that lets users discover rail vacation packages from a catalog of **1,995 real packages**. It replicates the Railbookers production Package Finder UI with:

- **Multi-mode destination search** (Starts in / Ends in / Includes) with multi-row AND logic
- **Autosuggest** on cities, countries, start/end locations, and package names
- **Filter panels** for Region, Trip Duration, Trains, and Vacation Type with paginated chips
- **8 sort modes** (Popularity, Name A-Z/Z-A, Newest, Duration Short/Long, Price Low/High)
- **Zero hallucination**: if no packages match, returns empty — never fabricates results

### Stack

| Layer | Technology | Port |
|-------|-----------|------|
| Database | PostgreSQL 16.8 (portable) | 5432 |
| Backend API | Python 3.11 + FastAPI + Uvicorn | 8890 |
| ORM | SQLAlchemy 2.x + psycopg2-binary | — |
| Frontend | Vanilla HTML/CSS/JS | 3000 |
| Frontend Server | Python SimpleHTTPServer | 3000 |

---

## 2. Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                        BROWSER (Port 3000)                          │
│  ┌─────────────────┐  ┌──────────────────┐  ┌───────────────────┐  │
│  │ recommend.html   │  │ recommend.js     │  │ recommend.css     │  │
│  │ (Layout/Forms)   │  │ (State/API/DOM)  │  │ (Styling)         │  │
│  └────────┬─────────┘  └────────┬─────────┘  └───────────────────┘  │
│           │  HTTP fetch()       │                                    │
└───────────┼─────────────────────┼────────────────────────────────────┘
            │                     │
            ▼                     ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    FastAPI SERVER (Port 8890)                        │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  routes_planner.py        routes_packages.py                 │   │
│  │  (Chatbot 9-step)         (14 CRUD/Meta endpoints)           │   │
│  │                                                              │   │
│  │  + 7 Package Finder endpoints (in routes_planner.py):        │   │
│  │    POST /recommendations/search                              │   │
│  │    GET  /recommendations/filters                             │   │
│  │    GET  /recommendations/locations                           │   │
│  │    GET  /recommendations/autosuggest                         │   │
│  │    GET  /recommendations/search-by-name                      │   │
│  │    POST /planner/chat  (chatbot)                             │   │
│  │    POST /planner/rag/build                                   │   │
│  └──────────────────────┬───────────────────────────────────────┘   │
│                         │                                           │
│  ┌──────────────────────▼───────────────────────────────────────┐   │
│  │              RecommendationEngine                            │   │
│  │  recommendation_engine.py (1,345 lines)                     │   │
│  │                                                              │   │
│  │  ┌─────────────┐ ┌───────────┐ ┌─────────────┐             │   │
│  │  │ _build_where│ │  _score   │ │ _apply_sort  │             │   │
│  │  │ Dynamic SQL │ │ Multi-    │ │ 8 sort modes │             │   │
│  │  │ Builder     │ │ factor    │ │              │             │   │
│  │  └──────┬──────┘ └─────┬─────┘ └──────┬──────┘             │   │
│  │         │              │              │                      │   │
│  │  ┌──────▼──────────────▼──────────────▼──────┐              │   │
│  │  │           recommend(filters)               │              │   │
│  │  │  sanitize → SQL → execute → score → sort   │              │   │
│  │  └──────────────────┬─────────────────────────┘              │   │
│  └─────────────────────┼────────────────────────────────────────┘   │
│                        │                                            │
│  ┌─────────────────────▼────────────────────────────────────────┐   │
│  │           SQLAlchemy ORM  (database.py)                      │   │
│  │  PostgreSQL: QueuePool, pool_size=25, max_overflow=50        │   │
│  └─────────────────────┬────────────────────────────────────────┘   │
└────────────────────────┼────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│                 PostgreSQL 16.8 (Port 5432)                          │
│  Database: rail_planner                                              │
│  Table:    rag_packages (1,995 rows × 23 columns)                   │
│  Indexes:  14 (on id, casesafeid, start/end_location, countries,    │
│            regions, triptype, route, duration, profitability_group,  │
│            departure_type, external_name, package_rank, package_url) │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. PostgreSQL Data Layer

### 3.1 Database Connection

| Parameter | Value |
|-----------|-------|
| Host | localhost |
| Port | 5432 |
| Database | `rail_planner` |
| User | postgres |
| Password | postgres |
| Connection String | `postgresql://postgres:postgres@localhost:5432/rail_planner` |
| Pool Size | 25 connections |
| Max Overflow | 50 connections |
| Pool Recycle | 1800 seconds |
| Pre-Ping | Enabled (validates connections before use) |
| Statement Timeout | 30 seconds |

**File:** `backend/app/db/database.py` (118 lines)

### 3.2 Table Schema — `rag_packages`

The single table `rag_packages` stores all 1,995 travel packages with 23 columns:

| # | Column | Type | Format | Example | Purpose |
|---|--------|------|--------|---------|---------|
| 1 | `id` | INTEGER (PK) | auto-increment | `1` | Internal primary key |
| 2 | `casesafeid` | TEXT | alphanumeric | `a1B2c3D4e5` | Salesforce-style unique package ID |
| 3 | `external_name` | TEXT | plain | `"Rome, Florence, Como, and Mila"` | Package display name |
| 4 | `start_location` | TEXT | plain | `"London"` | Departure city |
| 5 | `end_location` | TEXT | plain | `"Rome"` | Final destination city |
| 6 | `included_cities` | TEXT | pipe-delimited | `"Rome \| Florence \| Milan"` | Cities visited on the trip |
| 7 | `included_states` | TEXT | pipe-delimited | `"New South Wales \| Victoria"` | States (for US/AU packages) |
| 8 | `included_countries` | TEXT | pipe-delimited | `"Italy \| Switzerland"` | Countries visited |
| 9 | `included_regions` | TEXT | pipe-delimited | `"Europe"` | Continents/regions |
| 10 | `triptype` | TEXT | pipe-delimited | `"Famous Trains \| Most Scenic"` | Vacation categories |
| 11 | `route` | TEXT | pipe-delimited | `"Glacier Express \| Bernina"` | Train names on the route |
| 12 | `sales_tips` | TEXT | HTML/plain | Marketing notes | Internal sales guidance |
| 13 | `description` | TEXT | HTML | Package description | Public description (HTML stripped for display) |
| 14 | `highlights` | TEXT | HTML with `<li>` | `"<li>Visit Colosseum</li>"` | Trip highlights (parsed to list) |
| 15 | `inclusions` | TEXT | HTML with `<li>` | `"<li>Hotel stays</li>"` | What's included (parsed to list) |
| 16 | `daybyday` | TEXT | HTML | Detailed itinerary | Day-by-day breakdown |
| 17 | `package_rank` | INTEGER | plain | `295` | Popularity rank (lower = better) |
| 18 | `profitability_group` | TEXT | plain | `"Packages - High"` | Budget tier proxy (no price column exists) |
| 19 | `access_rule` | TEXT | plain | `"All"` | Visibility/access control |
| 20 | `duration` | TEXT | numeric string | `"11"` | Trip length in nights |
| 21 | `departure_type` | TEXT | plain | `"Anyday"` | Booking flexibility |
| 22 | `departure_dates` | TEXT | pipe-delimited | `"2026-03-01 - 2026-11-30"` | Available date ranges |
| 23 | `package_url` | TEXT | URL | `"https://railbookers.com/..."` | Link to package page |

### 3.3 Data Statistics

| Metric | Count |
|--------|-------|
| Total packages | 1,995 |
| Distinct start locations | 178 |
| Distinct end locations | 219 |
| Distinct countries | 54 |
| Distinct regions | 6 (Europe, North America, Asia, Oceania, Africa, South America) |
| Distinct vacation types | 39 |
| Distinct train names | 18 |
| Duration range | 2–34 nights |
| Departure types | 3 (Anyday, Fixed, Seasonal) |
| Hotel tiers | 3 (Luxury, Premium, Value) |
| Database indexes | 14 |

### 3.4 Pipe-Delimited Fields

Five columns use pipe-delimited (`|`) format to store multiple values:

```
included_cities:     "Rome | Florence | Milan | Venice"
included_countries:  "Italy | Switzerland | France"
included_regions:    "Europe"
triptype:            "Famous Trains | Most Scenic Journeys | Romance"
route:               "Glacier Express | Bernina Express"
```

The engine splits these at query time using:
- **SQL:** `LOWER(included_cities) LIKE LOWER(:dest)` for filtering
- **Python:** `field.split("|")` then `strip()` for display formatting

### 3.5 Budget Proxy System

There is **no explicit price column** in the database. Budget is proxied via `profitability_group`:

| profitability_group | User Label | Budget Proxy | Sort Order |
|--------------------|------------|-------------|------------|
| `Packages - High` | Luxury | $5,000+ | 5 (most expensive) |
| `Packages - Standard Margin` | Premium | $2,500–$7,000 | 2 |
| `Packages - Low` | Value | Under $4,000 | 1 (least expensive) |
| `Hurtigruten Packages` | Premium | $3,000–$8,000 | 4 |
| `Package - 29/30/31%` | Premium | — | 3 |

Price sort (`price_asc`/`price_desc`) uses `TIER_SORT_ORDER` mapping, not actual prices.

### 3.6 Database Indexes (14 total)

Indexes are created on all filterable and sortable columns for optimal query performance:
`id`, `casesafeid`, `start_location`, `end_location`, `included_countries`, `included_regions`, `triptype`, `route`, `duration`, `profitability_group`, `departure_type`, `external_name`, `package_rank`, `package_url`.

**File:** `backend/app/db/models.py` (24 lines — SQLAlchemy ORM model)

---

## 4. Backend — FastAPI Server

### 4.1 Server Configuration

| Setting | Value |
|---------|-------|
| Framework | FastAPI |
| ASGI Server | Uvicorn |
| Port | 8890 |
| API Prefix | `/api/v1` |
| CORS Origins | `localhost:3000`, `127.0.0.1:3000`, `localhost:8890` |
| Version | 2.0.0 |
| Environment | production |
| enforce_real_data | `True` (returns 503 if DB unavailable) |

**File:** `backend/app/core/config.py` (65 lines)

### 4.2 Package Finder API Endpoints

These 7 endpoints in `routes_planner.py` power the Package Finder:

#### `POST /api/v1/recommendations/search`
**Purpose:** Main search endpoint for Package Finder  
**Request Body:**
```json
{
  "search_rows": [
    {"mode": "starts_in", "destinations": ["London"]},
    {"mode": "ends_in", "destinations": ["Rome"]}
  ],
  "countries": ["Italy", "Switzerland"],
  "region": "Europe",
  "vacation_types": ["Famous Trains"],
  "train_names": ["Glacier Express"],
  "duration_min": 7,
  "duration_max": 14,
  "sort_by": "popularity"
}
```
**Response:**
```json
{
  "recommendations": [...],
  "total_matched": 6,
  "total_returned": 6,
  "query_time_ms": 14.1,
  "filters_applied": {...}
}
```

#### `GET /api/v1/recommendations/filters`
**Purpose:** Populate all filter dropdowns/chips  
**Response:** `start_locations[]`, `end_locations[]`, `countries[]`, `regions[]`, `vacation_types[]`, `departure_types[]`, `hotel_tiers[]`, `train_names[]`, `duration_range`, `total_packages`

#### `GET /api/v1/recommendations/autosuggest?q=lon&mode=starts_in`
**Purpose:** Real-time typeahead suggestions  
**Parameters:** `q` (query string), `mode` (starts_in/ends_in/includes), `field` (optional), `limit` (default 8)  
**Response:** `suggestions[{value, type}]` — prioritizes startsWith matches

#### `GET /api/v1/recommendations/locations`
**Purpose:** Complete location lists for autocomplete initialization  
**Response:** `start_locations[]`, `end_locations[]`, `cities[]`

#### `GET /api/v1/recommendations/search-by-name?q=rome`
**Purpose:** Search packages by name (LIKE query on `external_name`)

### 4.3 Additional Package Endpoints

14 more endpoints in `routes_packages.py` provide CRUD and metadata:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/packages` | GET | List all with pagination |
| `/packages/filter` | GET | Multi-criteria filter |
| `/packages/search` | GET | Full-text search |
| `/packages/{casesafeid}` | GET | Lookup by CaseSafeID |
| `/packages/count/total` | GET | Total count |
| `/packages/meta/countries` | GET | Unique countries |
| `/packages/meta/trip-types` | GET | Unique trip types |
| `/packages/meta/regions` | GET | Unique regions |
| `/packages/meta/cities` | GET | Unique cities (with optional country filter) |
| `/packages/meta/durations` | GET | Unique durations |
| `/packages/meta/hotel-tiers` | GET | Unique profitability groups |
| `/packages/meta/stats` | GET | Comprehensive stats |

---

## 5. Recommendation Engine — Core Algorithm

**File:** `backend/app/services/recommendation_engine.py` (1,345 lines)

### 5.1 Processing Pipeline

The `recommend(filters)` method executes this pipeline:

```
User Input → _sanitize_filters() → _build_where() → _build_sql()
         → DB Execute (up to 2000 rows) → _row_to_dict()
         → _score() each package → _apply_sort()
         → Return ALL results (browse mode) or _smart_limit() (chatbot mode)
```

### 5.2 Input Sanitization — `_sanitize_filters()`

Every input is validated before touching the database:

| Input Type | Sanitization Rules |
|-----------|-------------------|
| Strings | Strip whitespace, remove control chars `[\x00-\x1f]`, max 200 chars |
| Destination lists | Max 10 items per row, max 100 chars each |
| Search rows | Max 5 rows, each with max 10 destinations |
| Countries/Vacation types | Max 20 items |
| Duration | Clamped to 1–365, auto-swap if min > max |
| Search modes | Whitelist: `starts_in`, `ends_in`, `includes` only |
| Sort values | Whitelist: `popularity`, `name_asc`, `name_desc`, `newest`, `duration_asc`, `duration_desc`, `price_asc`, `price_desc` |

### 5.3 Dynamic SQL Builder — `_build_where()`

Constructs parameterized `WHERE` clauses from sanitized filters:

| Filter | SQL Generated | Parameters |
|--------|--------------|------------|
| `search_rows` (starts_in) | `LOWER(start_location) = LOWER(:sr_0_d_0)` | `:sr_0_d_0 = "London"` |
| `search_rows` (ends_in) | `LOWER(end_location) = LOWER(:sr_0_d_0)` | `:sr_0_d_0 = "Rome"` |
| `search_rows` (includes) | `(LOWER(included_cities) LIKE ... OR LOWER(start_location) = ... OR LOWER(end_location) = ... OR LOWER(included_countries) LIKE ...)` | Multiple `:sr_X_d_Y` params |
| `duration_min/max` | `duration ~ '^[0-9]+$' AND CAST(duration AS INTEGER) >= :dur_min` | `:dur_min = 7` |
| `hotel_tier` | `profitability_group IN (:hotel_grp_0, :hotel_grp_1)` | Mapped from label to group |
| `vacation_types` | `(LOWER(triptype) LIKE ... OR ...)` | OR across all selected types |
| `train_names` | `(LOWER(route) LIKE ... OR ...)` | LIKE match on route column |
| `countries` | `(LOWER(included_countries) LIKE ... OR ...)` | OR across countries |

**All queries are parameterized** — no string concatenation, preventing SQL injection.

Every query automatically includes: `external_name NOT ILIKE '%TEST%'` to exclude test packages.

### 5.4 Multi-Factor Scoring — `_score()`

Each package receives a score from 0–100 based on how well it matches the user's criteria:

| Factor | Points | Condition |
|--------|--------|-----------|
| **Includes match (city)** | +35 | City found in `included_cities` / `start_location` / `end_location` |
| **Includes match (country)** | +25 | Country found in `included_countries` |
| **Legacy includes (city)** | +40 | Direct city match via legacy `includes` filter |
| **Legacy includes (country)** | +30 | Country match via legacy `includes` filter |
| **Starts in** | +15 | Exact match on `start_location` |
| **Ends in** | +15 | Exact match on `end_location` |
| **Vacation type** | +20 | Type found in `triptype` |
| **Vacation types (multi)** | +10–20 | Multiple type matches (10 per match, capped at 20) |
| **Train match** | +8–15 | Train found in `route` (8 per match, capped at 15) |
| **Countries filter** | +25 | Country match from multi-select filter |
| **Duration (exact)** | +15 | Duration exactly matches target |
| **Duration (±2 nights)** | +12 | Within 2 nights of target |
| **Duration (±4 nights)** | +8 | Within 4 nights of target |
| **Duration (±7 nights)** | +4 | Within 7 nights of target |
| **Hotel tier** | +10 | Profitability group matches selected tier |
| **Top-ranked (≤100)** | +10 | Package rank in top 100 |
| **Highly rated (≤300)** | +7 | Package rank 101–300 |
| **Multi-country (3+)** | +5 | Visits 3+ countries |
| **Multi-country (2)** | +3 | Visits 2 countries |
| **Region match** | +5 | Region in `included_regions` |

**Normalization:** Raw score is divided by `ABSOLUTE_CEILING = 100` and capped at 100. Minimum scored = 10.0, unscored baseline = 5.0.

### 5.5 Progressive Fallback — `_fallback_search()`

When the initial query returns zero results, the engine progressively relaxes **secondary filters only**:

```
Relaxation order:
  1. departure_type  (drop first — least impact)
  2. hotel_tier
  3. vacation_type / vacation_types
  4. trains / train_names
  5. countries
  6. duration_min / duration_max  (drop last — most meaningful)
```

**Critical rule:** PRIMARY filters (`search_rows`, `includes`, `starts_in`, `ends_in`, `region`, `package_name`) are **NEVER dropped**. This prevents hallucination — if a user searches for "Japan" (which has 0 packages), the system returns 0 results, not random packages from other countries.

### 5.6 Sorting — `_apply_sort()`

8 sort modes supported:

| Mode | Sort Key | Direction |
|------|---------|-----------|
| `popularity` | `package_rank` | ASC (lower rank = more popular) |
| `name_asc` | `external_name` | A → Z |
| `name_desc` | `external_name` | Z → A |
| `newest` | `id` | DESC (higher id = newer) |
| `duration_asc` | `duration` | Short → Long |
| `duration_desc` | `duration` | Long → Short |
| `price_asc` | `profitability_group` → `TIER_SORT_ORDER` | Low → High |
| `price_desc` | `profitability_group` → `TIER_SORT_ORDER` | High → Low |
| *default* | `match_score` DESC, then `package_rank` ASC | Best match first |

### 5.7 Result Limiting

| Context | Behavior |
|---------|----------|
| **Package Finder (Browse)** | Returns ALL matching results (up to 2,000) — no cap |
| **Chatbot Recommender** | Smart limit: 6 (score ≥ 80), 9 (score ≥ 50), or 12 (default) |

### 5.8 Row-to-Dict Transformation — `_row_to_dict()`

Converts raw DB tuples into frontend-ready dictionaries with formatted display fields:

| Raw Field | Transformed Field | Transformation |
|-----------|------------------|---------------|
| `external_name` | `name` | Fallback to "Rail Vacation Package" |
| `duration` | `duration_display` | `"11 nights"` |
| `included_countries` | `countries_display` | `"Italy, Switzerland, France"` (split pipe) |
| `included_cities` | `cities_display` | `"Rome, Florence, Milan"` (split pipe) |
| `triptype` | `trip_type_display` | `"Famous Trains, Most Scenic"` (split pipe) |
| `profitability_group` | `hotel_tier` | Mapped via TIER_MAP → `"Luxury"` / `"Premium"` / `"Value"` |
| `start_location + end_location` | `route_display` | `"London → Rome"` or `"Round trip from London"` |
| `highlights` (HTML) | `highlights_list` | Extract `<li>` contents, strip HTML tags, max 6 items |
| `inclusions` (HTML) | `inclusions_list` | Extract `<li>` contents, strip HTML tags, max 8 items |
| `description` (HTML) | `description` | Strip all HTML tags, truncate to 400 chars |
| `route` | `trains_display` | `"Glacier Express, Bernina Express"` (split pipe) |
| `departure_dates` | `departure_dates_display` | `"2026-03-01 to 2026-11-30"` (formatted ranges) |

### 5.9 Caching

| Cache | TTL | Purpose |
|-------|-----|---------|
| Filter options | 60 seconds | `get_filter_options()` — avoids repeated DISTINCT queries |
| Location data | 15 minutes | `get_all_locations()` — unified location dataset for autosuggest |

Both are TTL-based in-memory dicts, refreshed automatically.

---

## 6. Frontend — Package Finder UI

### 6.1 Files

| File | Lines | Purpose |
|------|-------|---------|
| `frontend/recommend.html` | ~200 | Page layout, forms, filter panels |
| `frontend/recommend.js` | ~780 | All client-side logic |
| `frontend/styles/recommend.css` | ~600 | Complete styling |

### 6.2 Page Layout

```
┌──────────────────────────────────────────────────────────────┐
│  Header: "Railbookers" logo — [Chat Planner] [Package Finder] │
├──────────────────────────────────────────────────────────────┤
│  Instruction Banner: "Enter a city, country, or region..."   │
├──────────────────────────────────────────────────────────────┤
│  Search Area:                                                │
│  ┌─[Mode ▼]─── [ Destination input with tags ] ─────────┐   │
│  │ Includes ▼   London ×  |  type to add...             │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──── AND ───────────────────────────────────────────────┐  │
│  │ Ends in ▼    Rome ×    |  type to add...              │  │
│  └──────────────────────────────────────────────────────┘   │
│  [+ Add Row]                            [Search] [Clear All] │
├──────────────────────────────────────────────────────────────┤
│  Filter Bar: [Region ▼] [Duration ▼] [Trains ▼] [Type ▼]    │
│              Sort: [Best Match ▼]                             │
├──────────────────────────────────────────────────────────────┤
│  Results: "Showing 116 packages"                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                   │
│  │ Card 1   │  │ Card 2   │  │ Card 3   │  ...              │
│  │ Name     │  │ Name     │  │ Name     │                    │
│  │ Route ↔  │  │ Route ↔  │  │ Route ↔  │                    │
│  │ Duration │  │ Duration │  │ Duration │                    │
│  │ Score 95 │  │ Score 87 │  │ Score 72 │                    │
│  │ [View ↗] │  │ [View ↗] │  │ [View ↗] │                    │
│  └──────────┘  └──────────┘  └──────────┘                    │
└──────────────────────────────────────────────────────────────┘
```

### 6.3 Key Frontend Features

#### Multi-Mode Search Rows
- Each row has a **mode dropdown** (Includes / Starts in / Ends in)
- Each row accepts **multiple destinations** as inline tags (OR logic within row)
- Multiple rows are combined with **AND** logic
- `+ Add Row` button adds more search rows
- Up to 5 rows supported

#### Autosuggest Engine
- Triggers on 2+ characters typed
- Debounced (300ms) API call to `/recommendations/autosuggest`
- Mode-aware: `starts_in` queries `start_locations`, `ends_in` queries `end_locations`
- Results prioritize **startsWith** matches over contains matches
- Dropdown appears below input, navigable with keyboard
- Blur delay (250ms) allows click on suggestion before dropdown closes

#### Filter Panels
4 popup filter panels with:
- **Search box** to filter chips within the panel
- **Paginated chips** (15 per page with Previous/Next navigation)
- **Multi-select** with visual checkmarks
- **Apply / Reset** buttons per panel
- **Backdrop overlay** when panel is open

| Panel | Data Source | Chip Count |
|-------|-----------|-----------|
| Region | `included_regions` DISTINCT | 6 |
| Duration | Range slider (2–34 nights) | Slider |
| Trains | `route` DISTINCT | 18 |
| Vacation Type | `triptype` DISTINCT | 39 |

#### Sort Dropdown
8 options: Best Match, Popularity, Name A–Z, Name Z–A, Newest, Duration (Short→Long), Duration (Long→Short), Price (Low→High), Price (High→Low)

#### Result Cards
Each card displays:
- Package name (bold header)
- Route with arrow: `London → Rome`
- Duration: `11 nights`
- Countries: `Italy, Switzerland`
- Match score with colored badge (green ≥ 70, amber ≥ 40, red < 40)
- Match reasons (expandable)
- Hotel tier badge (Luxury / Premium / Value)
- Train names
- Highlights list (expandable `<li>` items)
- Inclusions list (expandable `<li>` items)
- "View on Railbookers" button → links to `package_url`

### 6.4 Client State Management

```javascript
// Global state in recommend.js
state = {
  filters: {},           // Active filter selections per panel
  searchRows: [          // One or more {mode, destinations[]}
    { mode: 'includes', destinations: [] }
  ],
  results: [],           // Current search results array
  sortBy: '',            // Current sort selection
  chipPages: {},         // Pagination state per filter panel
}
```

### 6.5 API Layer

All API calls use `fetch()` with:
- 15-second timeout via `AbortController`
- Automatic retry (1 retry on failure)
- JSON content type
- Error handling with user-facing messages

---

## 7. End-to-End Data Flow

### Search Flow Example: "Starts in London, Ends in Rome, Duration 7–14 nights"

```
1. USER types "London" in search row 1 (mode: starts_in)
   → API: GET /autosuggest?q=lon&mode=starts_in
   → Returns: [{"value":"London","type":"city"}]
   → User selects "London" → added as tag

2. USER clicks "+ Add Row", sets mode to "ends_in", types "Rome"
   → API: GET /autosuggest?q=rom&mode=ends_in
   → Returns: [{"value":"Rome","type":"city"}]
   → User selects "Rome" → added as tag

3. USER opens Duration filter, sets 7–14 nights
   → Stored in client state: filters.duration_min=7, filters.duration_max=14

4. USER clicks [Search]
   → JS builds request:
     {
       search_rows: [
         {mode: "starts_in", destinations: ["London"]},
         {mode: "ends_in", destinations: ["Rome"]}
       ],
       duration_min: 7,
       duration_max: 14,
       sort_by: ""
     }
   → API: POST /recommendations/search

5. BACKEND receives request
   → _sanitize_filters(): validates modes, clamps durations, strips control chars
   → _build_where(): generates 3 WHERE clauses:
     - LOWER(start_location) = LOWER(:sr_0_d_0)  [sr_0_d_0="London"]
     - LOWER(end_location) = LOWER(:sr_1_d_0)    [sr_1_d_0="Rome"]
     - duration ~ '^[0-9]+$' AND CAST(duration AS INTEGER) BETWEEN :dur_min AND :dur_max
   → _build_sql(): 
     SELECT 23 columns FROM rag_packages
     WHERE external_name NOT ILIKE '%TEST%'
       AND LOWER(start_location) = LOWER(:sr_0_d_0)
       AND LOWER(end_location) = LOWER(:sr_1_d_0)
       AND duration ~ '^[0-9]+$' AND CAST(duration AS INTEGER) >= :dur_min
       AND duration ~ '^[0-9]+$' AND CAST(duration AS INTEGER) <= :dur_max
     LIMIT 2000
   → PostgreSQL executes, returns matching rows

6. BACKEND processes results
   → _row_to_dict(): converts each row to dict + formatted display fields
   → _score(): each package scored:
     - London starts_in: +15
     - Rome ends_in: +15
     - Duration within range: +8 to +15
     - Rank bonus: +2 to +10
     - Multi-country bonus: +3 to +5
     = Total normalized to 0–100
   → _apply_sort(): default sort = score DESC, then rank ASC
   → Returns ALL results (browse mode, no limit cap)

7. FRONTEND receives JSON response
   → Renders result cards in grid layout
   → Shows match score, route, duration, countries, highlights
   → "View on Railbookers" links to actual package_url
```

---

## 8. Files & Their Roles

### Backend Files

| File | Lines | Role |
|------|-------|------|
| `backend/app/main.py` | ~210 | FastAPI app factory, middleware (CORS, security headers, logging, rate limiting), startup/shutdown, lifespan |
| `backend/app/core/config.py` | 65 | Pydantic BaseSettings: DB, API, CORS, RAG, rate limit configuration |
| `backend/app/core/i18n.py` | — | Internationalization (12 languages: EN, FR, DE, ES, IT, PT, NL, JA, ZH, KO, HI, AR) |
| `backend/app/core/monitoring.py` | — | Request logging middleware |
| `backend/app/core/rate_limiting.py` | — | Per-IP rate limiter |
| `backend/app/db/database.py` | 118 | SQLAlchemy engine, session factory, connection pooling, `get_db()` dependency |
| `backend/app/db/models.py` | 24 | `TravelPackage` ORM model (23 columns) |
| `backend/app/db/repositories.py` | — | Data access layer |
| `backend/app/api/routes_planner.py` | ~350 | Chatbot (9-step flow) + Package Finder (7 endpoints) |
| `backend/app/api/routes_packages.py` | 244 | 14 CRUD/Meta package endpoints |
| `backend/app/api/routes_i18n.py` | — | Translation endpoints |
| `backend/app/api/health.py` | — | Health check endpoint |
| `backend/app/services/recommendation_engine.py` | 1,345 | **Core engine**: search, score, sort, filter, autosuggest, sanitize |
| `backend/app/services/vector_store.py` | — | RAG vector store (TF-IDF for semantic search) |
| `backend/app/services/recommender.py` | — | Chatbot recommendation orchestrator |
| `backend/app/services/translations.py` | — | Multi-language translations |
| `backend/app/services/db_options.py` | — | Dynamic dropdown options from DB |

### Frontend Files

| File | Lines | Role |
|------|-------|------|
| `frontend/recommend.html` | ~200 | Package Finder page layout |
| `frontend/recommend.js` | ~780 | Search logic, autosuggest, filters, sort, API calls, card rendering |
| `frontend/styles/recommend.css` | ~600 | Package Finder styling (CSS variables, responsive) |
| `frontend/index.html` | — | Chatbot page |
| `frontend/main.js` | — | Chatbot JavaScript |
| `frontend/serve.py` | — | Python HTTP server (port 3000) |
| `frontend/styles/premium-chat.css` | — | Chatbot styling |

### Configuration Files

| File | Role |
|------|------|
| `backend/.env` | Environment variables: DATABASE_URL, API key |
| `backend/requirements.txt` | Python dependencies |

---

## 9. Coding Algorithms & Techniques

### 9.1 Multi-Mode Search Row System

**Algorithm:** Each search row is an independent filter with its own mode + destination list. Rows are combined with AND logic. Within a row, multiple destinations use OR logic.

```python
# For search_rows: AND across rows, OR within
for row_idx, sr in enumerate(search_rows):
    mode = sr.get("mode", "includes")
    destinations = sr.get("destinations", [])
    row_clauses = []  # OR within this row
    for dest_idx, dest in enumerate(destinations):
        if mode == "starts_in":
            row_clauses.append(f"LOWER(start_location) = LOWER(:sr_{row_idx}_d_{dest_idx})")
        elif mode == "ends_in":
            row_clauses.append(f"LOWER(end_location) = LOWER(:sr_{row_idx}_d_{dest_idx})")
        elif mode == "includes":
            row_clauses.append(f"(LOWER(included_cities) LIKE ... OR ...)")
    # Combine: OR within row
    all_row_clause = "(" + " OR ".join(row_clauses) + ")"
    clauses.append(all_row_clause)  # AND with other rows
```

### 9.2 Two-Phase Autosuggest

**Phase 1:** Database query with `LOWER(field) LIKE LOWER(:query)` on the appropriate field for the mode.

**Phase 2:** Re-ranking in Python — `startsWith` matches are sorted before `contains` matches:
```python
starts = [s for s in suggestions if s["value"].lower().startswith(query_lower)]
others = [s for s in suggestions if not s["value"].lower().startswith(query_lower)]
return starts + others  # startsWith first
```

### 9.3 TTL-Based In-Memory Caching

```python
_filter_cache: Dict[str, Any] = {}
_filter_cache_ts: float = 0.0
FILTER_CACHE_TTL = 60.0

def get_filter_options(self):
    global _filter_cache, _filter_cache_ts
    now = time.time()
    if _filter_cache and (now - _filter_cache_ts) < FILTER_CACHE_TTL:
        return _filter_cache  # Return cached
    # ... execute queries, populate cache ...
    _filter_cache = result
    _filter_cache_ts = now
    return result
```

### 9.4 Progressive Fallback with Hallucination Guard

```python
# Never drop primary filters → prevents returning random packages
PRIMARY_KEYS = {"search_rows", "includes", "starts_in", "ends_in", "region", "package_name"}

# Only relax secondary filters, one at a time
for key in ["departure_type", "hotel_tier", "vacation_type", ...]:
    relaxed.pop(key)
    results = execute(relaxed)
    if results:
        return results  # Found with fewer constraints

# If all secondaries dropped + still 0 → return empty (not random!)
return []
```

### 9.5 Profitability-Based Price Sorting

```python
TIER_SORT_ORDER = {
    "Packages - Low": 1,        # Cheapest
    "Packages - Standard Margin": 2,
    "Package - 29/30/31%": 3,
    "Hurtigruten Packages": 4,
    "Packages - High": 5,       # Most expensive
}

# price_asc: sort by tier order ASC, then rank ASC
sorted(scored, key=lambda x: (
    TIER_SORT_ORDER.get(x["profitability_group"], 3),
    x.get("package_rank", 9999)
))
```

### 9.6 HTML Parsing for Highlights/Inclusions

```python
# Extract <li> items from raw HTML highlights
raw_hl = pkg.get("highlights", "")
hl_items = re.findall(r"<li[^>]*>(.*?)</li>", raw_hl, re.DOTALL | re.IGNORECASE)
highlights_list = [re.sub(r"<[^>]+>", "", item).strip() for item in hl_items[:6]]
```

### 9.7 Pipe-Delimited Field Processing

```python
# Database storage:  "Italy | Switzerland | France"
# SQL filtering:     LOWER(included_countries) LIKE LOWER(:country)
# Python display:    field.split("|") → strip() → join(", ")
```

### 9.8 Frontend Paginated Filter Chips

```javascript
const CHIPS_PER_PAGE = 15;

function renderChips(panel, items, page) {
    const start = page * CHIPS_PER_PAGE;
    const end = start + CHIPS_PER_PAGE;
    const pageItems = items.slice(start, end);
    // Render chips + Previous/Next navigation
}
```

### 9.9 Debounced Autosuggest

```javascript
let suggestTimer = null;
input.addEventListener('input', () => {
    clearTimeout(suggestTimer);
    suggestTimer = setTimeout(() => {
        if (input.value.length >= 2) {
            fetchSuggestions(input.value, mode);
        }
    }, 300);  // 300ms debounce
});
```

---

## 10. Tools & Technologies Used

### Languages & Frameworks

| Technology | Version | Usage |
|-----------|---------|-------|
| Python | 3.11.9 | Backend server, test scripts |
| PostgreSQL | 16.8 | Primary database (portable install) |
| FastAPI | latest | REST API framework |
| Uvicorn | latest | ASGI server |
| SQLAlchemy | 2.x | ORM + connection pooling |
| psycopg2-binary | latest | PostgreSQL driver |
| HTML5 | — | Frontend markup |
| CSS3 | — | Styling with CSS variables |
| JavaScript (ES6+) | — | Frontend logic (vanilla, no framework) |

### Key Libraries

| Library | Purpose |
|---------|---------|
| `pydantic` | Settings validation, request/response models |
| `python-dotenv` | Environment variable loading |
| `scikit-learn (TfidfVectorizer)` | RAG vector store for semantic search |
| `requests` | HTTP client for testing |
| `pytest` | Test framework |
| `re` (regex) | HTML parsing, input sanitization, duration extraction |
| `hashlib` | Cache key generation |
| `logging` | Structured logging throughout |

### Development Tools

| Tool | Purpose |
|------|---------|
| VS Code (Insiders) | IDE |
| GitHub Copilot (Claude Opus 4.6) | AI coding assistant |
| PowerShell | Terminal commands |
| curl | API testing |
| Pylance | Static type checking |

---

## 11. Test Coverage Summary

| Test Suite | Tests | Status | File |
|-----------|-------|--------|------|
| Hallucination Fix | 12/12 | PASS | `test_hallucination_fix.py` |
| PG Endpoints | 25/25 | PASS | `test_pg_endpoints.py` |
| FINAL PG Validation | 29/29 | PASS | `FINAL_PG_VALIDATION.py` |
| Recommendations | 7/7 | PASS | `test_recommendations.py` |
| E2E Production | 64/64 | PASS | `tests/test_e2e_production.py` |
| 50 Checkpoints | 50/50 | PASS | `test_50_checkpoints.py` |
| Deep Verify | 147/147 | PASS | `tests/test_prd_deep_verify.py` |
| Production Ready | 136/136 | PASS | `tests/test_production_ready.py` |
| Ultimate Production | 116/116 | PASS | `tests/test_ultimate_production.py` |
| **TOTAL** | **586/586** | **100% PASS** | |

### What's Tested

- Health endpoint response time, DB connectivity
- All 23 columns present in results
- Start/End/Includes search modes with correct match counts
- Cross-validation: API results == direct DB queries
- No TEST/demo packages in results
- Chatbot 9-step flow (all steps verified)
- Multi-destination accuracy (Italy, Canada, UK, Australia, France)
- SQL injection safety
- Unicode/emoji handling
- Concurrent user simulation (20 health, 10 chats, 5 full flows)
- Frontend page loads, CSS/JS loaded, cache bust present
- Autosuggest functionality
- Duration/hotel/vacation type filters
- Edge cases: empty messages, 1000+ char input, special characters

---

## 12. Security & Anti-Hallucination

### Security Measures

| Measure | Implementation |
|---------|---------------|
| SQL Injection Prevention | All queries use SQLAlchemy parameterized `text()` with `:param` placeholders |
| XSS Prevention | HTML stripped from all text display, `X-Content-Type-Options: nosniff` |
| Input Sanitization | Control chars removed, string length limited, input types validated |
| Rate Limiting | Per-IP rate limiter middleware |
| Security Headers | `X-Frame-Options`, `X-Content-Type-Options`, `X-Powered-By` |
| CORS | Restricted origins: localhost:3000, localhost:8890 |
| Statement Timeout | 30-second PostgreSQL statement timeout |
| API Key | RAG build endpoint requires `X-API-Key` header |

### Anti-Hallucination System

| Rule | Implementation |
|------|---------------|
| Primary filters never dropped | `_fallback_search()` only relaxes secondary filters |
| Zero matches → empty response | Never returns random packages when searched destination has 0 matches |
| TEST packages always excluded | Every SQL query includes `external_name NOT ILIKE '%TEST%'` |
| All data from DB | `enforce_real_data = True` — returns 503 if DB is down, never fabricates |
| No hardcoded packages | Zero mock data in codebase — all 1,995 packages from PostgreSQL |

---

## 13. Performance Characteristics

| Metric | Value |
|--------|-------|
| Health check | ~2s (cold) |
| Single search query | 14ms (server-side) |
| Full chatbot 8-step flow | ~20s |
| Autosuggest latency | < 100ms (cached) |
| Filter options load | < 50ms (cached) |
| Concurrent 20 health checks | All OK, avg 2.3s |
| Concurrent 10 chat sessions | All OK |
| Connection pool | 25 persistent + 50 overflow |
| Filter cache TTL | 60 seconds |
| Location cache TTL | 15 minutes |
| Max query result size | 2,000 rows |
| Frontend search response | < 3s (including network) |

---

*Report generated: February 2026*  
*System verified: All 586 tests passing, 1,995 packages active, zero Pylance errors*
