# Railbookers Rail Vacation Planner

A full-stack conversational chatbot that helps travellers discover and book personalised rail vacation packages. Built with a FastAPI backend, TF-IDF RAG vector engine, and a vanilla JavaScript frontend.

**Author:** Rajan Mishra

---

## Overview

The Rail Vacation Planner is a production-grade chatbot that guides users through an 8-step conversational flow to recommend the best rail vacation packages from a curated database of **1,996 expert-designed packages** across **54 countries**.

The system uses a hybrid recommendation engine combining SQL filtering with TF-IDF semantic search (RAG) to deliver highly relevant results. Every recommendation is sourced strictly from the Excel/database data — the system never hallucinates or fabricates package information.

### Key Highlights

- **1,996 curated packages** imported from Excel data across 54 countries
- **8-step conversational flow** with natural language understanding
- **10-language support**: English, French, Spanish, German, Italian, Chinese, Hindi, Japanese, Portuguese, Arabic
- **Hybrid RAG engine**: TF-IDF vectors + SQL filtering + multi-signal scoring
- **Zero hallucination**: all responses grounded in actual database records
- **Free-text conversational input** at every step with inline hints
- **Fuzzy destination matching** with region-aware alternatives for unavailable destinations
- **Duplicate detection** to prevent .com/.co.uk variant packages from appearing twice
- **356 automated tests** across 6 test suites — all passing

---

## Architecture

```
travel/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI application & middleware
│   │   ├── core/
│   │   │   ├── config.py              # Settings (env, CORS, rate limits)
│   │   │   ├── models.py              # SQLAlchemy ORM (TravelPackage)
│   │   │   └── guards.py              # Input sanitisation & safety guards
│   │   ├── api/
│   │   │   ├── routes_planner.py      # 8-step chat endpoint & NL engine
│   │   │   ├── routes_packages.py     # Package CRUD endpoints
│   │   │   ├── routes_i18n.py         # Translation endpoints
│   │   │   └── health.py              # Health & readiness probes
│   │   └── services/
│   │       ├── recommender.py         # Hybrid recommendation engine
│   │       ├── vector_store.py        # TF-IDF vector store (RAG)
│   │       ├── translations.py        # i18n translations (10 languages)
│   │       └── db_options.py          # Database option provider
│   ├── tests/
│   │   ├── test_production_ready.py   # 136 production tests
│   │   ├── test_prd_deep_verify.py    # 146 PRD verification tests
│   │   ├── test_e2e_production.py     #  64 end-to-end tests
│   │   ├── test_enhancements.py       #  14 enhancement tests
│   │   ├── test_features.py           #   8 feature tests
│   │   └── test_rag_quality.py        #  10 RAG quality tests
│   ├── rail_planner.db                # SQLite database (1,996 packages)
│   └── requirements.txt
├── frontend/
│   ├── index.html                     # Chat UI
│   ├── main.js                        # Chat logic & API integration
│   ├── serve.py                       # Static file server
│   ├── components/                    # UI components
│   ├── services/                      # API service layer
│   └── styles/                        # CSS stylesheets
└── doc/                               # Project documentation
```

---

## Conversational Flow (8 Steps)

The chatbot follows a structured but natural conversational flow:

| Step | Question | Input Type | Notes |
|------|----------|-----------|-------|
| 1 | Where would you like to go? | Free text / autocomplete | Continue button after selection |
| 2 | Who will be travelling with you? | Free text | NL parsing: "2 adults and 3 kids" |
| 3 | When would you like to travel, and for how long? | Free text | Date + duration parsing |
| 4 | What kind of experience are you looking for? | Free text | Inline hints: scenic, adventure, romance... |
| 5 | Are you celebrating a special occasion? | Free text | Inline hints: birthday, anniversary... |
| 6 | What type of hotels do you prefer? | Free text | Inline hints: luxury, premium, value |
| 7 | Have you taken a rail vacation before? | Free text | Inline hints: first time, experienced... |
| 8 | Budget or special requirements? | Free text | Action buttons: Find trips, No limit |

After step 8, the user sees a **summary of their preferences** and can confirm or modify. On confirmation, the system analyses all 1,996 packages and returns the **top 5 personalised recommendations** with match scores, reasons, and booking links.

---

## Recommendation Engine

The hybrid recommendation engine uses a multi-signal scoring system (max 115 points, normalised to 100%):

| Signal | Max Points | Description |
|--------|-----------|-------------|
| RAG semantic similarity | 15 | TF-IDF cosine similarity against package descriptions |
| Location match | 35 | Country and city matching against user destination |
| Duration match | 20 | Closeness to requested trip duration |
| Trip type match | 20 | Alignment with user's travel purpose |
| Hotel tier match | 15 | Profitability group alignment |
| Description relevance | 5 | Contextual cosine similarity bonus |
| Package rank | 5 | Editorial quality ranking |

### Semantic Trip Purpose Mapping

User-friendly labels are mapped to real database trip types:

- **Romance** → Most Scenic Journeys, Once-in-a-Lifetime Experiences, Luxury Rail
- **Culture** → First Time to Europe, Famous Routes, Single Country Tours, Famous Trains
- **Adventure** → Off the Beaten Track, Cross Country Journeys, National Parks
- **Scenic** → Most Scenic Journeys, Via the Alps, Lakes and Mountains
- **Luxury** → Luxury Rail, Once-in-a-Lifetime Experiences, Railbookers Signature
- **Food/Culinary** → Culinary Journeys, Famous Routes
- And 30+ more mappings for natural language inputs

---

## Natural Language Processing

The chatbot understands natural language at every step:

- **Destinations**: "I want to go to Italy and Switzerland" → detects both countries
- **Travellers**: "2 adults and 3 children" → family of 5 | "just me" → solo | "with my wife" → couple
- **Dates**: "June 2026, 10 days" | "4 March to 12 March, 8 nights" | "next summer, about 2 weeks"
- **Trip purpose**: "something romantic for our anniversary" → romance + anniversary occasion
- **Unavailable destinations**: "Japan" → suggests China, India, Singapore inline in the message

### Fuzzy Destination Matching

When a user types an unavailable or misspelled destination:

1. Checks against 50+ known unavailable destinations (Japan, Thailand, etc.)
2. Uses `difflib.get_close_matches` for fuzzy string matching
3. Falls back to region-aware suggestions (e.g., Japan → Asia alternatives)
4. Always offers a "Surprise me" option to search all packages

---

## Multilingual Support

Full translations for all chatbot messages, questions, and system text across 10 languages:

English, French (Français), Spanish (Español), German (Deutsch), Italian (Italiano), Chinese (中文), Hindi (हिन्दी), Japanese (日本語), Portuguese (Português), Arabic (العربية)

The language is auto-detected from the user's first message or can be set via the `language` parameter.

---

## Installation & Setup

### Prerequisites

- Python 3.11+
- pip

### Backend Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
```

### Running the Application

**Start the backend server:**

```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8890 --reload
```

**Start the frontend server:**

```bash
cd frontend
python serve.py 3000
```

**Access the application:**

- Frontend: http://localhost:3000
- API docs: http://localhost:8890/docs
- Health check: http://localhost:8890/api/v1/health

---

## API Reference

### Chat Endpoint

```
POST /api/v1/planner/chat
```

**Request:**
```json
{
    "message": "Italy",
    "session_id": "optional-uuid",
    "language": "en"
}
```

**Response:**
```json
{
    "message": "Italy -- home to legendary rail routes...",
    "step_number": 1,
    "suggestions": ["Continue"],
    "needs_input": true,
    "session_id": "uuid",
    "recommendations": null
}
```

### Other Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/planner/health` | System health status |
| GET | `/api/v1/planner/options/countries` | Available countries list |
| GET | `/api/v1/planner/options/trip-types` | Available trip types |
| GET | `/api/v1/planner/options/hotel-tiers` | Hotel tier options |
| GET | `/api/v1/planner/autocomplete?q=ita` | Destination autocomplete |
| GET | `/api/v1/planner/rag/status` | RAG vector store status |
| POST | `/api/v1/planner/rag/build` | Rebuild RAG vectors |

---

## Database

**SQLite** database (`rail_planner.db`) containing:

- **1,996 packages** with full details (name, route, description, highlights, inclusions, day-by-day itinerary)
- **1,996 TF-IDF vectors** for semantic search
- **54 countries** covered
- **39 trip types** (Famous Trains, Most Scenic Journeys, Luxury Rail, etc.)

### Package Schema

| Column | Description |
|--------|-------------|
| external_name | Package display name |
| start_location / end_location | Route endpoints |
| included_cities | Cities visited |
| included_countries | Countries covered |
| triptype | Pipe-delimited trip categories |
| duration | Trip duration |
| description | Full package description |
| highlights | Key selling points |
| package_rank | Editorial quality ranking |
| profitability_group | Hotel tier grouping |
| package_url | Booking link |

---

## Testing

Run all 6 test suites (356 total tests):

```bash
cd backend

# Production readiness (136 tests)
python tests/test_production_ready.py

# PRD deep verification (146 tests)
python tests/test_prd_deep_verify.py

# E2E production (64 tests)
python tests/test_e2e_production.py

# Enhancement features (14 tests)
python tests/test_enhancements.py

# Feature tests (8 tests)
python tests/test_features.py

# RAG quality verification (10 tests)
python tests/test_rag_quality.py
```

### Test Coverage

- **Production (136):** Full 8-step flow, multi-country selection, multi-language flows, autocomplete, edge cases, error handling, recommendation quality, duplicate prevention
- **PRD Deep Verify (146):** Database integrity vs Excel, RAG pipeline, 8-step flow, recommendation quality, scoring, edge cases, API consistency, performance
- **E2E Production (64):** Root, health, headers, planner, RAG, DB options, packages, search, i18n, full flow, session, frontend, performance
- **Enhancements (14):** Calendar date parsing, traveller NL parsing, reset functionality
- **Features (8):** Multilingual flows (Hindi, German, Spanish, etc.), end-to-end conversation
- **RAG Quality (10):** Italy romance, USA adventure, family Europe, solo UK, Canada luxury, India budget, surprise-me, multi-country, NL input, French language

---

## Configuration

Key settings in `app/core/config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `api_prefix` | `/api/v1` | API route prefix |
| `max_concurrent_sessions` | 500 | Session limit |
| `rate_limit` | 30/minute | Request rate limiting |
| `cors_origins` | `*` | Allowed origins |
| `database_url` | `sqlite:///rail_planner.db` | Database path |

---

## Security

- **CSP headers** with nonce-based script execution
- **XSS prevention** via input sanitisation (HTML entity encoding)
- **Rate limiting** (30 req/min per IP via SlowAPI)
- **Session management** with automatic cleanup of expired sessions
- **SQL injection prevention** via SQLAlchemy parameterised queries
- **Admin endpoints** protected with API key authentication
- **CORS** configured for frontend origin

---

## Project Status

All features complete and tested. Production-ready for deployment.

- 356/356 tests passing
- 0 linting errors
- Full 8-step conversational flow working
- 10-language support active
- RAG engine operational with 1,996 vectors
- Recommendation deduplication active
- Free-text input at all steps with inline hints

---

**Developed by Rajan Mishra**
