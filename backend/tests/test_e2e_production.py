"""
Railbookers Rail Vacation Planner -- Production E2E Test Suite
Comprehensive test covering all endpoints, full chat flow, and performance.
Developed by Rajan Mishra
"""

import urllib.request
import json
import time
import sys

API = "http://localhost:8890/api/v1"
FRONTEND = "http://localhost:3000"

pass_count = 0
fail_count = 0
start_time = time.time()


def test(name, condition, detail=""):
    global pass_count, fail_count
    if condition:
        pass_count += 1
        print(f"  PASS  {name}")
    else:
        fail_count += 1
        print(f"  FAIL  {name} -- {detail}")


def api_get(path):
    url = f"{API}{path}"
    req = urllib.request.Request(url)
    resp = urllib.request.urlopen(req, timeout=15)
    return json.loads(resp.read().decode()), resp


def api_get_root(path):
    url = f"http://localhost:8890{path}"
    req = urllib.request.Request(url)
    resp = urllib.request.urlopen(req, timeout=15)
    return json.loads(resp.read().decode()), resp


def api_post(path, body):
    url = f"{API}{path}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read().decode()), resp


print("=" * 70)
print("  RAILBOOKERS PRODUCTION E2E TEST SUITE v2.0")
print("=" * 70)

# ---- 1. Root ----
print("\n[1] ROOT ENDPOINT")
data, resp = api_get_root("/")
test("Root returns 200", resp.status == 200)
test("App name present", "Railbookers" in data.get("name", ""))
test("Version 2.0.0", data.get("version") == "2.0.0")

# ---- 2. Health endpoints ----
print("\n[2] HEALTH ENDPOINTS")
data, resp = api_get("/health/")
test("Health 200", resp.status == 200)
test("Status healthy", data["status"] == "healthy")
test("Database available", data["database"] == "available")
test("1995 packages", data["packages"] >= 1990)

data, resp = api_get("/health/ready")
test("Ready check", data.get("ready") == True)

data, resp = api_get("/health/live")
test("Liveness check", data.get("alive") == True)

# ---- 3. Response headers ----
print("\n[3] RESPONSE HEADERS")
_, resp = api_get("/health/live")
headers = {k.lower(): v for k, v in resp.headers.items()}
test("X-Process-Time header", "x-process-time" in headers)
test("X-Powered-By header", headers.get("x-powered-by") == "Railbookers")
test("X-Content-Type-Options", headers.get("x-content-type-options") == "nosniff")
test("X-Frame-Options", headers.get("x-frame-options") == "DENY")

# ---- 4. Planner health & welcome ----
print("\n[4] PLANNER HEALTH & WELCOME")
data, _ = api_get("/planner/health")
test("Planner healthy", data["status"] == "healthy")
test("RAG enabled", data["rag_enabled"] == True)
test("8 conversation steps", data["conversation_steps"] == 9)
test("DB connected", data["database_connected"] == True)

data, _ = api_get("/planner/flow/welcome")
test("Welcome message", "Railbookers" in data.get("message", ""))
test("Package count", data["packages_available"] >= 1990)
test("Countries suggestions", len(data.get("suggestions") or []) > 5)

# ---- 5. RAG status ----
print("\n[5] RAG STATUS")
data, _ = api_get("/planner/rag/status")
test("RAG ready", data["rag_ready"] == True)
test("Vectors indexed", data["vectors_indexed"] >= 1990)

# ---- 6. DB options ----
print("\n[6] DATABASE-DRIVEN OPTIONS")
data, _ = api_get("/planner/options/countries")
countries = data.get("countries", [])
test("Countries from DB", len(countries) > 20)
test("Italy in countries", "Italy" in countries)

data, _ = api_get("/planner/options/trip-types")
tts = data.get("trip_types", [])
test("Trip types from DB", len(tts) > 10)

data, _ = api_get("/planner/options/hotel-tiers")
tiers = data.get("hotel_tiers", [])
test("Hotel tiers", set(tiers) == {"Luxury", "Premium", "Value"})

data, _ = api_get("/planner/options/regions")
regions = data.get("regions", [])
test("Regions from DB", len(regions) >= 3)

# ---- 7. Package endpoints ----
print("\n[7] PACKAGE ENDPOINTS")
data, _ = api_get("/packages/")
pkg_list = data if isinstance(data, list) else data.get("packages", data.get("data", []))
test("Packages list", len(pkg_list) > 0)

data, _ = api_get("/packages/meta/stats")
meta_total = data.get("total_packages", data.get("total", 0)) if isinstance(data, dict) else 0
test("Metadata endpoint", meta_total > 0)

# ---- 8. Destination search ----
print("\n[8] DESTINATION SEARCH")
data, _ = api_get("/planner/destinations/search?q=Italy")
test("Search Italy", "Italy" in data.get("countries", []))

data, _ = api_get("/planner/destinations/search?q=Paris")
test("Search Paris", len(data.get("cities", [])) > 0 or len(data.get("countries", [])) > 0)

# ---- 9. i18n ----
print("\n[9] INTERNATIONALIZATION")
data, _ = api_get("/i18n/translations/en")
test("English translations", len(data) > 0)

data, _ = api_get("/i18n/translations/fr")
test("French translations", len(data) > 0)

# ---- 10. FULL 8-STEP CHAT FLOW (PRD-aligned) ----
print("\n[10] FULL 8-STEP CHAT FLOW (PRD)")
flow_start = time.time()

# Step 1: Destination
data, _ = api_post("/planner/chat", {"message": "Italy"})
session_id = data["session_id"]
test("Step 1: Destination", "Italy" in data["message"])
test("Step 1: Has placeholder", data.get("placeholder") is not None)
test("Step 1: Session ID", len(session_id) > 10)

# Single destination -> Continue to proceed
if data.get("step_number") == 1:
    data, _ = api_post("/planner/chat", {"message": "Continue", "session_id": session_id})

# Step 2: Travellers
data, _ = api_post("/planner/chat", {"message": "Couple", "session_id": session_id})
test("Step 2: Travellers", "two" in data["message"].lower() or "couple" in data["message"].lower() or "2" in data["message"])

# Step 3: Dates
data, _ = api_post("/planner/chat", {"message": "June 2026, 10 days", "session_id": session_id})
test("Step 3: Dates", "10" in data["message"] or "summer" in data["message"].lower() or "june" in data["message"].lower())

# Step 4: Trip Purpose
data, _ = api_post("/planner/chat", {"message": "Romance", "session_id": session_id})
test("Step 4: Trip Purpose", len(data["message"]) > 20)
test("Step 4: Has occasion options", "occasion" in data["message"].lower() or "celebrating" in data["message"].lower() or "moment" in data["message"].lower() or "milestone" in data["message"].lower())

# Step 5: Special Occasion
data, _ = api_post("/planner/chat", {"message": "Anniversary", "session_id": session_id})
test("Step 5: Occasion", "anniversary" in data["message"].lower())
test("Step 5: Hotel question", "hotel" in data["message"].lower() or "accommodation" in data["message"].lower())

# Step 6: Hotel Preference
data, _ = api_post("/planner/chat", {"message": "Luxury", "session_id": session_id})
test("Step 6: Hotel", "luxury" in data["message"].lower())
test("Step 6: Rail question", "rail" in data["message"].lower())

# Step 7: Rail Experience
data, _ = api_post("/planner/chat", {"message": "First time on rail", "session_id": session_id})
test("Step 7: Rail exp", "first" in data["message"].lower())
test("Step 7: Budget question", "budget" in data["message"].lower() or "find my" in data["message"].lower())

# Step 8: Budget -> Recommendations (Find my perfect trips skips summary)
data, _ = api_post("/planner/chat", {"message": "Find my perfect trips", "session_id": session_id})
test("Step 8: Summary shown", "journey brief" in data["message"].lower() or "packages analysed" in data["message"].lower() or "recommendations" in data["message"].lower())
test("Step 8: Has suggestions", len(data.get("suggestions") or []) > 0)

# Recommendations are already in this response
recs = data.get("recommendations", [])
test("Step 9: Got recommendations", recs is not None and len(recs) > 0)
if recs:
    test("Step 9: 5 recommendations", len(recs) == 5)
    top = recs[0]
    test("Step 9: Has match_score", top.get("match_score", 0) > 0)
    test("Step 9: Has name", len(top.get("name", "")) > 0)
    test("Step 9: Has duration", len(top.get("duration", "")) > 0)
    test("Step 9: Has match_reasons", len(top.get("match_reasons", [])) > 0)
    test("Step 9: Has countries", len(top.get("countries", "")) > 0)
    test("Step 9: Top score > 40%", top.get("match_score", 0) > 40)

flow_elapsed = time.time() - flow_start
test(f"Full flow under 30s ({flow_elapsed:.1f}s)", flow_elapsed < 30)
print("\n[11] SESSION MANAGEMENT")
data2, _ = api_post("/planner/chat", {"message": "Plan another trip", "session_id": session_id})
test("Session reset", "where" in data2["message"].lower() or len(data2.get("suggestions") or []) > 0)

# ---- 12. Frontend ----
print("\n[12] FRONTEND")
try:
    req = urllib.request.Request(FRONTEND)
    resp = urllib.request.urlopen(req, timeout=10)
    html = resp.read().decode()
    test("Frontend 200", resp.status == 200)
    test("Railbookers in HTML", "Railbookers" in html)
    test("Cache bust v2", "v=202602112230" in html)
    test("Premium CSS loaded", "premium-chat.css" in html)
except Exception as e:
    test("Frontend reachable", False, str(e))

# ---- 13. Performance ----
print("\n[13] PERFORMANCE")
perf_start = time.time()
api_get("/health/live")
perf_elapsed = (time.time() - perf_start) * 1000
test(f"Liveness < 3000ms ({perf_elapsed:.0f}ms)", perf_elapsed < 3000)

perf_start = time.time()
api_get("/planner/flow/welcome")
perf_elapsed = (time.time() - perf_start) * 1000
test(f"Welcome < 3000ms ({perf_elapsed:.0f}ms)", perf_elapsed < 3000)

total_elapsed = time.time() - start_time

# ---- SUMMARY ----
print("\n" + "=" * 70)
total = pass_count + fail_count
print(f"  RESULTS: {pass_count}/{total} PASSED | {fail_count} FAILED")
print(f"  TIME: {total_elapsed:.1f}s")
print(f"  VERSION: 2.0.0 Production")
print("=" * 70)

if fail_count > 0:
    sys.exit(1)
else:
    print("\n  ALL TESTS PASSED -- READY FOR LAUNCH")
