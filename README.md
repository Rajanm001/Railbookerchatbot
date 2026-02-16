Railbookers AI Search Chatbot
==============================

Author: Rajan Mishra
Version: 2.0.0
Organisation: Railbookers Group


Overview
--------

Railbookers AI Search is a full-stack conversational chatbot platform built for discovering
rail vacation packages. The system walks users through an 8-step guided conversation covering
destination preferences, traveller details, travel dates, trip purpose, special occasions,
hotel tier, rail experience type, and budget range. At the end of the conversation, the engine
returns a ranked set of matching packages drawn entirely from the verified database, with no
fabricated or hallucinated content.

The backend pairs a structured SQL query layer with a TF-IDF retrieval augmented generation
(RAG) engine. Together they score and rank results across 1,996 curated packages spanning
54 countries and 6 global regions. The system is designed for enterprise deployment with
connection pooling, per-IP rate limiting, session lifecycle management, and structured
observability.


Capabilities
------------

  - 8-step guided conversational flow for travel planning
  - Hybrid recommendation engine combining TF-IDF vector similarity with SQL-based filtering
  - Multi-factor scoring across location, duration, trip type, hotel tier, and profitability
  - 1,996 verified packages imported from authoritative Excel source data
  - 10-language translation layer (English, French, Spanish, German, Italian, Hindi,
    Japanese, Chinese, Portuguese, Arabic)
  - Zero hallucination guarantee: every option, suggestion, and result is drawn from the
    live database
  - Fuzzy string matching for destination and preference inputs with context-aware alternatives
  - In-memory session store with configurable TTL and automatic background cleanup
  - Per-IP rate limiting via SlowAPI (120 req/min chat, 100/min search, 60/min recommendations)
  - Structured JSON logging, performance decorators, and Kubernetes-ready health probes


System Architecture
-------------------

```
+----------------------------------------------------------+
|                   Frontend (Port 3000)                    |
|  Vanilla JS, Chat Interface, Language Switcher            |
|  Components: ChatInput, ChatMessage, DatePicker,          |
|              MultiSelect, LanguageSwitcher                 |
+----------------------------+-----------------------------+
                             |  HTTP / REST API
+----------------------------v-----------------------------+
|                 FastAPI Backend (Port 8890)               |
|                                                          |
|   Planner Router    Health Probes    i18n Translations    |
|         |                                                |
|   Service Layer                                          |
|     Recommender (Scoring)                                |
|     DB Options (Lookups)                                 |
|     Vector Store (TF-IDF / Cosine Similarity)            |
|         |                                                |
|   Database Layer (SQLAlchemy ORM)                        |
|     Connection Pooling, Health Checks, Auto Recycle      |
+----------------------------+-----------------------------+
                             |
              +--------------v--------------+
              |    PostgreSQL / SQLite      |
              |    1,996 packages           |
              |    TF-IDF vectors           |
              +----------------------------+
```


Technology Stack
----------------

  Backend ......... Python 3.10+, FastAPI 0.104, Uvicorn, SQLAlchemy 2.0
  Database ........ PostgreSQL 16 (primary), SQLite (development fallback)
  Search .......... Custom TF-IDF vector store with cosine similarity scoring
  Frontend ........ Vanilla JavaScript (ES6+), HTML5, CSS3
  Security ........ SlowAPI rate limiting, CORS, input sanitisation
  Infrastructure .. Pydantic settings, structured logging, health probes


Installation
------------

Prerequisites:
  - Python 3.10 or higher
  - PostgreSQL 16 (or SQLite for local development)
  - Git

1. Clone the repository

   git clone https://github.com/Rajanm001/Railbookerchatbot.git
   cd Railbookerchatbot

2. Create a virtual environment

   cd backend
   python -m venv .venv

   On Windows:
     .venv\Scripts\activate

   On macOS / Linux:
     source .venv/bin/activate

3. Install dependencies

   pip install -r requirements.txt

4. Configure environment

   cp .env.example .env

   Open .env and set your database credentials and configuration values.
   Refer to the Environment Variables section below for all available options.

5. Initialise the database

   python scripts/seed_sqlite.py
   python scripts/build_vectors.py

6. Start the application

   Terminal 1 (backend):
     uvicorn app.main:app --host 0.0.0.0 --port 8890 --reload

   Terminal 2 (frontend):
     cd ../frontend
     python serve.py

   The chatbot interface is accessible at http://localhost:3000


Environment Variables
---------------------

All configuration is managed through environment variables loaded from a .env file
via Pydantic Settings.

  DATABASE_URL .............. postgresql://postgres:postgres@localhost:5432/rail_planner
  DATABASE_POOL_SIZE ........ 25 (SQLAlchemy connection pool size)
  DATABASE_MAX_OVERFLOW ..... 50 (maximum overflow connections beyond pool size)
  DATABASE_POOL_RECYCLE ..... 1800 (connection recycling interval in seconds)
  API_HOST .................. 0.0.0.0 (server bind address)
  API_PORT .................. 8890 (server port)
  API_WORKERS ............... 4 (uvicorn worker processes)
  API_PREFIX ................ /api/v1 (API route prefix)
  CORS_ORIGINS .............. ["http://localhost:3000"] (allowed CORS origins)
  SESSION_TTL_MINUTES ....... 30 (chatbot session expiry in minutes)
  MAX_CONCURRENT_SESSIONS ... 10000 (maximum active sessions)
  ADMIN_API_KEY ............. (required, set a strong unique value)
  LOG_LEVEL ................. INFO (DEBUG, INFO, WARNING, ERROR)
  RAG_RETRIEVAL_TOP_K ....... 5 (number of RAG candidates to retrieve)
  RAG_SIMILARITY_THRESHOLD .. 0.7 (minimum cosine similarity for RAG results)
  ENVIRONMENT ............... production (runtime environment identifier)
  DEBUG ..................... false (enable debug mode)


Running the Application
-----------------------

Development mode:

  Terminal 1 (backend with hot reload):
    cd backend
    uvicorn app.main:app --host 0.0.0.0 --port 8890 --reload

  Terminal 2 (frontend static server):
    cd frontend
    python serve.py

  Open http://localhost:3000 in a browser to use the chatbot.

Production mode:

  cd backend
  uvicorn app.main:app --host 0.0.0.0 --port 8890 --workers 4 --loop uvloop --http httptools --no-access-log

  For production deployments, run behind a reverse proxy (Nginx, Traefik) and use a
  process manager such as systemd or Docker.


API Endpoints
-------------

Health and Monitoring:

  GET  /api/v1/health/                  System health check (database status, package count, uptime)

Chatbot (Planner):

  POST /api/v1/planner/chat            Send a chat message and receive the next guided response
  POST /api/v1/planner/reset           Reset a conversation session to the beginning
  GET  /api/v1/planner/session/{id}    Retrieve the current state of a session

Packages:

  GET  /api/v1/packages/               List packages with pagination
  GET  /api/v1/packages/{id}           Get full details for a single package
  GET  /api/v1/packages/search         Search packages by keyword

Internationalisation:

  GET  /api/v1/i18n/languages          List all supported languages
  GET  /api/v1/i18n/translations/{lang}  Get all translation strings for a given language


Conversational Flow
-------------------

The chatbot guides users through eight sequential steps. Each step presents
database-sourced options and validates the user's input before moving forward.

  Step 1: Destination
           The user specifies a country, region, or city. The system matches
           against destinations available in the package catalogue using fuzzy
           string comparison and suggests alternatives when no exact match exists.

  Step 2: Travellers
           Number and composition of the travelling party.

  Step 3: Travel Dates
           Preferred departure and return dates, presented through an interactive
           calendar date picker component.

  Step 4: Trip Purpose
           The type of trip (leisure, honeymoon, anniversary, family holiday, etc.)
           drawn from values present in the database.

  Step 5: Special Occasion
           Optional occasion tagging (birthday, retirement, celebration) to refine
           recommendations toward packages with relevant inclusions.

  Step 6: Hotel Preference
           Preferred accommodation tier, matched against the hotel_tier column in
           the package catalogue.

  Step 7: Rail Experience
           Type of rail journey (scenic routes, luxury trains, high-speed rail,
           heritage railways) based on rail_experience values in the database.

  Step 8: Budget Range
           The user's budget bracket. The scoring engine uses this to weight results
           by price proximity and profitability ranking.

After all eight steps are complete, the recommendation engine scores every eligible
package against the collected preferences using a weighted multi-factor algorithm.
The top-ranked results are returned with full detail including itinerary, pricing,
duration, rail operator, departure points, and hotel information.


Recommendation Engine
---------------------

The recommendation engine uses a hybrid approach:

  1. Candidate retrieval: The TF-IDF vector store performs cosine similarity search
     across package descriptions to identify semantically relevant candidates.

  2. SQL filtering: Structured filters (destination, dates, traveller count, budget)
     narrow the candidate set to packages that meet hard constraints.

  3. Multi-factor scoring: Each remaining candidate is scored across weighted
     dimensions including location match, duration fit, trip type alignment,
     hotel tier match, and internal profitability ranking.

  4. Result ranking: Candidates are sorted by composite score and the top results
     are returned to the user.

The vector store is built from package descriptions using term frequency-inverse
document frequency (TF-IDF) weighting. It runs entirely in-process with no external
ML dependencies, making deployment straightforward on any Python environment.


Directory Structure
-------------------

```
Railbookerchatbot/
    backend/
        app/
            __init__.py
            main.py                     FastAPI application entry point
            api/
                health.py               Health check and readiness probes
                routes_planner.py       Chatbot conversation endpoints
                routes_packages.py      Package CRUD endpoints
                routes_i18n.py          Translation endpoints
            core/
                config.py               Pydantic settings and environment variables
                i18n.py                 Translation engine (10 languages)
                monitoring.py           Structured logging and performance tracking
                rate_limiting.py        SlowAPI throttling configuration
            db/
                database.py             SQLAlchemy engine and session factory
                models.py               ORM models (TravelPackage)
                repositories.py         Data access layer
            ingestion/
                cleaned_packages.json   Source package data (1,996 records)
            services/
                db_options.py           Database-driven option lookups
                recommender.py          Multi-factor scoring engine
                translations.py         Runtime translation service
                vector_store.py         TF-IDF RAG vector store
        scripts/
            build_vectors.py            Build TF-IDF vectors from package data
            seed_sqlite.py              Seed database from JSON source
            seed_rag_packages.py        RAG-specific data seeding
        tests/
            test_e2e_production.py      End-to-end production tests
            test_prd_deep_verify.py     Deep verification suite
            test_production_ready.py    Production readiness checks
            test_rag_quality.py         RAG quality validation
            test_ultimate_production.py Comprehensive test suite
        requirements.txt                Python dependencies
    frontend/
        index.html                      Chat interface entry point
        main.js                         Application controller
        serve.py                        Static file server (development)
        components/
            ChatInput.js                Message input component
            ChatMessage.js              Message rendering component
            DatePicker.js               Date selection component
            LanguageSwitcher.js         Language toggle component
            MultiSelect.js              Multi-option selector component
        services/
            api.js                      API service layer with retry logic
        styles/
            premium-chat.css            Chat interface styles
    doc/
        KT_Package_Filtering.sql        Reference SQL queries
    .gitignore
    README.md
```


Deployment
----------

Docker:

  FROM python:3.11-slim
  WORKDIR /app
  COPY backend/ .
  RUN pip install --no-cache-dir -r requirements.txt
  EXPOSE 8890
  CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8890", "--workers", "4"]

Pre-deployment checklist:

  1. Set DATABASE_URL to point to a production PostgreSQL instance.
  2. Set ADMIN_API_KEY to a strong, unique value.
  3. Set ENVIRONMENT=production and DEBUG=false.
  4. Configure CORS_ORIGINS to match the frontend domain.
  5. Run seed_sqlite.py and build_vectors.py to populate data and build vectors.
  6. Tune DATABASE_POOL_SIZE and DATABASE_MAX_OVERFLOW for expected concurrency.

The /api/v1/health/ endpoint reports database connectivity, total package count, and
service uptime. It is suitable for use as a Kubernetes liveness and readiness probe.


Security
--------

  Input sanitisation: All user inputs are stripped of HTML tags and length-limited
  before any processing. No raw user input reaches the database query layer.

  Rate limiting: Endpoints are throttled per IP address. The planner accepts
  120 requests per minute, search accepts 100, and recommendations accept 60.

  CORS: Restricted to explicitly configured origins. Credentials are disabled
  by default.

  Admin protection: Administrative endpoints (vector rebuild, cache clear) require
  a valid ADMIN_API_KEY header. Without it, the server returns 403.

  Session isolation: Each conversation session is keyed by a UUID generated on the
  server. Sessions expire automatically after the configured TTL.

  No external calls: The recommendation engine operates entirely on local data.
  No user input or session data is transmitted to third-party services.

  Connection security: Database connections support SSL and are health-checked
  with pre-ping to detect and replace stale connections before they cause errors.


Testing
-------

  cd backend

  Run the full production test suite:
    python -m pytest tests/ -v

  Run individual test modules:
    python -m pytest tests/test_e2e_production.py -v
    python -m pytest tests/test_production_ready.py -v
    python -m pytest tests/test_rag_quality.py -v
    python -m pytest tests/test_prd_deep_verify.py -v
    python -m pytest tests/test_ultimate_production.py -v


Roadmap
-------

  - Redis session store for horizontal scaling across multiple API workers
  - Elasticsearch or OpenSearch integration for faster similarity queries at scale
  - User analytics dashboard tracking search patterns and popular destinations
  - Webhook notifications for booking alerts and CRM integration
  - Progressive web app with offline support and service workers
  - A/B testing framework for comparing recommendation scoring strategies


Contributing
------------

  1. Fork the repository and create a feature branch from main.
  2. Write clear, descriptive commit messages.
  3. Ensure all existing tests pass before submitting a pull request.
  4. Add tests for any new functionality.
  5. Follow the existing code structure and naming conventions.
  6. Update this README if changes affect API contracts or configuration.
  7. Submit a pull request with a description of the changes and their purpose.


License
-------

This project is proprietary software developed for Railbookers Group.
Unauthorised distribution or reproduction is prohibited. All rights reserved.
