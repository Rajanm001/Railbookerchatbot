"""
=============================================================================
  RAILBOOKERS PRODUCTION READINESS VERIFICATION
  Comprehensive end-to-end test suite
  Tests: DB, RAG, Chat Flow, Autocomplete, NL Recognition, Edge Cases
=============================================================================
"""
import urllib.request
import json
import time
import sys
from typing import Any

BASE = "http://127.0.0.1:8890/api/v1"
PASS = 0
FAIL = 0
WARNINGS = []


def api_get(path: str) -> Any:
    try:
        return json.loads(urllib.request.urlopen(f"{BASE}{path}", timeout=10).read())
    except Exception as e:
        return {"error": str(e)}


def api_post(path: str, body: dict[str, Any]) -> Any:
    try:
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            f"{BASE}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        return json.loads(urllib.request.urlopen(req, timeout=15).read())
    except Exception as e:
        return {"error": str(e)}


def chat(msg: str, sid: str | None = None) -> Any:
    return api_post("/planner/chat", {"message": msg, "session_id": sid})


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} -- {detail}")


def warn(msg):
    WARNINGS.append(msg)
    print(f"  [WARN] {msg}")


# =========================================================================
print("\n" + "=" * 70)
print("  SECTION 1: HEALTH & INFRASTRUCTURE")
print("=" * 70)

h = api_get("/planner/health")
check("Health endpoint responds", "error" not in h)
check("Status is healthy", h.get("status") == "healthy", f"got: {h.get('status')}")
check("1996 real packages loaded", h.get("packages_available", 0) >= 1990, f"got: {h.get('packages_available')}")
check("RAG enabled", h.get("rag_enabled") is True)
check("Database connected", h.get("database_connected") is True)
check("System ready", h.get("ready") is True)
check("9 conversation steps", h.get("conversation_steps") == 9, f"got: {h.get('conversation_steps')}")

# =========================================================================
print("\n" + "=" * 70)
print("  SECTION 2: DATABASE REAL DATA VERIFICATION")
print("=" * 70)

# Get packages to verify they're real (from Excel)
pkgs = api_get("/packages?limit=10")
if "error" not in pkgs:
    items = pkgs if isinstance(pkgs, list) else pkgs.get("packages", pkgs.get("items", []))
    if items:
        first = items[0] if items else {}
        check("Packages have real names (external_name)", bool(first.get("external_name", "")), f"got: {list(first.keys())[:8]}")
        check("Packages have countries", bool(first.get("included_countries", "")))
        check("Packages have duration", bool(first.get("duration", "")))
        check("Packages have trip type", bool(first.get("triptype", "")))
        # Verify known package from Excel
        all_names = [p.get("external_name", "") for p in items]
        print(f"    Sample packages: {all_names[:5]}")
    else:
        check("Packages endpoint returns data", False, "Empty list")
else:
    # Try autocomplete to verify DB has data
    ac = api_get("/planner/autocomplete?q=ita&step=destination")
    check("DB has real data (via autocomplete)", "error" not in ac and len(ac.get("suggestions", [])) > 0)

# Verify autocomplete returns real countries from DB
ac = api_get("/planner/autocomplete?q=swit&step=destination")
if "error" not in ac:
    sugg = ac.get("suggestions", [])
    labels = [s.get("label", "") for s in sugg]
    check("Autocomplete: Switzerland found", any("Switz" in l for l in labels), f"got: {labels}")
else:
    check("Autocomplete endpoint works", False, str(ac))

ac2 = api_get("/planner/autocomplete?q=fra&step=destination")
if "error" not in ac2:
    sugg2 = ac2.get("suggestions", [])
    labels2 = [s.get("label", "") for s in sugg2]
    check("Autocomplete: France found", any("Franc" in l for l in labels2), f"got: {labels2}")

ac3 = api_get("/planner/autocomplete?q=rom&step=destination")
if "error" not in ac3:
    sugg3 = ac3.get("suggestions", [])
    labels3 = [s.get("label", "") for s in sugg3]
    types3 = [s.get("type", "") for s in sugg3]
    check("Autocomplete: Rome found as city", any("Rome" in l for l in labels3), f"got: {labels3}")

# =========================================================================
print("\n" + "=" * 70)
print("  SECTION 3: COMPLETE 8-STEP CHAT FLOW (Client Feedback Applied)")
print("=" * 70)

# --- Step 0: Greeting ---
r = chat("Hello")
sid = r["session_id"]
check("Step 0 -> 1: Greeting triggers welcome", r.get("step_number") == 1)
check("Welcome msg: 'destination in mind'", "where" in r.get("message", "").lower() and ("explore" in r.get("message", "").lower() or "go" in r.get("message", "").lower()))
check("Welcome msg: NOT 'Pick a destination below'", "Pick a destination below" not in r.get("message", ""))
sugg = r.get("suggestions") or []
check("Welcome: no big suggestion list", len(sugg) == 0, f"got {len(sugg)}")
print(f"    Suggestions: {sugg}")

# --- Step 1: Destination ---
r = chat("Italy and Switzerland", sid)
check("Step 1 -> 2: Destination accepted", r.get("step_number") == 2)
check("Step 2 msg: 'Who will be travelling'", "travel" in r.get("message", "").lower() or "joining" in r.get("message", "").lower())
check("Step 2: NO suggestion buttons (client feedback)", r.get("suggestions") is None, f"got: {r.get('suggestions')}")
print(f"    Message: {r['message'][:120]}")

# --- Step 2: Travellers ---
r = chat("2 adults and 1 child", sid)
check("Step 2 -> 3: Travellers accepted", r.get("step_number") == 3)
check("Step 3 msg: 'When would you like'", "when" in r.get("message", "").lower() or "timing" in r.get("message", "").lower())
check("Step 3: No suggestion buttons (clean)", r.get("suggestions") is None, f"got: {r.get('suggestions')}")
print(f"    Message: {r['message'][:120]}")

# --- Step 3: Dates ---
r = chat("June 2026, 10 days", sid)
check("Step 3 -> 4: Dates accepted", r.get("step_number") == 4)
check("Step 4 msg: trip experience question", "experience" in r.get("message", "").lower() or "trip" in r.get("message", "").lower())
check("Step 4: No suggestion chips (free-text)", r.get("suggestions") is None, f"got: {r.get('suggestions')}")
print(f"    Message: {r['message'][:120]}")

# --- Step 4: Trip purpose ---
r = chat("Culture and heritage", sid)
check("Step 4 -> 5: Trip purpose accepted", r.get("step_number") == 5)
check("Step 5 msg: special occasion", "occasion" in r.get("message", "").lower() or "moment" in r.get("message", "").lower() or "milestone" in r.get("message", "").lower())
check("Step 5: No suggestion chips (free-text)", r.get("suggestions") is None, f"got: {r.get('suggestions')}")
print(f"    Message: {r['message'][:120]}")

# --- Step 5: Occasion ---
r = chat("Anniversary", sid)
check("Step 5 -> 6: Occasion accepted", r.get("step_number") == 6)
check("Step 6 msg: hotel preference", "hotel" in r.get("message", "").lower() or "accommodation" in r.get("message", "").lower())
check("Step 6: No suggestion chips (free-text)", r.get("suggestions") is None, f"got: {r.get('suggestions')}")
print(f"    Message: {r['message'][:120]}")

# --- Step 6: Hotel tier ---
r = chat("Luxury", sid)
check("Step 6 -> 7: Hotel tier accepted", r.get("step_number") == 7)
check("Step 7 msg: rail experience", "rail" in r.get("message", "").lower())
check("Step 7: No suggestion chips (free-text)", r.get("suggestions") is None, f"got: {r.get('suggestions')}")
print(f"    Message: {r['message'][:120]}")

# --- Step 7: Rail experience ---
r = chat("First time on a rail vacation", sid)
check("Step 7 -> 8: Rail experience accepted", r.get("step_number") == 8)
check("Step 8 msg: budget question", "budget" in r.get("message", "").lower() or "requirement" in r.get("message", "").lower())
step8_sugg = r.get("suggestions") or []
check("Step 8: 'Find my perfect trips' button", "Find my perfect trips" in step8_sugg)
check("Step 8: 'No budget limit' button", "No budget limit" in step8_sugg)
check("Step 8: Only 2 buttons", len(step8_sugg) == 2, f"got {len(step8_sugg)}: {step8_sugg}")
print(f"    Message: {r['message'][:120]}")

# --- Step 8: Budget -> Summary ---
r = chat("No budget limit", sid)
check("Step 8 -> 9: Summary shown", r.get("step_number") == 9)
msg9 = r.get("message", "")
check("Summary: contains destination", "Italy" in msg9 or "Switzerland" in msg9)
check("Summary: contains travellers", "traveller" in msg9.lower() or "3" in msg9)
check("Summary: contains timing", "June" in msg9 or "10" in msg9 or "night" in msg9.lower())
check("Summary: 'Search now' button", "Search now" in (r.get("suggestions") or []))
check("Summary: 'Modify preferences' button", "Modify preferences" in (r.get("suggestions") or []))
print(f"    Summary: {msg9[:250]}")

# --- Step 9: Confirm -> Recommendations ---
t0 = time.time()
r = chat("Search now", sid)
elapsed = time.time() - t0
check("Step 9: Recommendations returned", r.get("step_number") == 9)
recs = r.get("recommendations") or []
check("Recommendations: 5 results", len(recs) == 5, f"got {len(recs)}")
check("Search time < 5 seconds", elapsed < 5, f"took {elapsed:.1f}s")

if recs:
    top = recs[0]
    check("Rec has name", bool(top.get("name")))
    check("Rec has match_score", top.get("match_score") is not None)
    check("Rec has countries", bool(top.get("countries")))
    score = top.get("match_score", 0)
    check("Top score >= 70%", score >= 70, f"got {score}%")
    check("Rec has real package data", len(top.get("name", "")) > 5, f"name: {top.get('name')}")

    # Verify recommendations match Italy/Switzerland
    for i, rec in enumerate(recs):
        c = rec.get("countries", "")
        if "Italy" in c or "Switzerland" in c:
            check(f"Rec[{i+1}] matches destination", True)
        else:
            warn(f"Rec[{i+1}] '{rec.get('name')}' has countries: {c}")

    print(f"\n    TOP 5 RECOMMENDATIONS:")
    for i, rec in enumerate(recs):
        print(f"      [{i+1}] {rec.get('name')} | {rec.get('match_score', 0):.0f}% | {rec.get('countries')}")

check("Post-rec suggestions include 'Plan another trip'", "Plan another trip" in (r.get("suggestions") or []))

# =========================================================================
print("\n" + "=" * 70)
print("  SECTION 4: NATURAL LANGUAGE RECOGNITION (Client requirement)")
print("=" * 70)

# Client: "if I ask basically, I'm looking for a package in Rome and Venice and Switzerland...
# the chatbot is going to recognize those locations?"
r2 = chat("Hello")
sid2 = r2["session_id"]
r2 = chat("I'm looking for a package in Rome and Venice and Switzerland", sid2)
check("NL: Step moved to 2", r2.get("step_number") == 2)
msg = r2.get("message", "")
check("NL: Rome recognized", "Rome" in msg or "rome" in msg.lower())
check("NL: Venice recognized", "Venice" in msg or "venice" in msg.lower())
check("NL: Switzerland recognized", "Switz" in msg)
print(f"    NL Response: {msg[:150]}")

# Test another NL query
r3 = chat("Hi there")
sid3 = r3["session_id"]
r3 = chat("Take me to France and Germany please", sid3)
check("NL: France recognized", "France" in r3.get("message", ""))
check("NL: Germany recognized", "Germany" in r3.get("message", ""))

# Test NL with city names including state suffixes (Boston, MA)
time.sleep(0.6)
r3b = chat("Hello")
sid3b = r3b["session_id"]
r3b = chat("Can you find trips to Boston and New York", sid3b)
check("NL: Boston recognized", "Boston" in r3b.get("message", ""))
check("NL: New York recognized", "New York" in r3b.get("message", ""))
print(f"    NL Boston/NY: {r3b.get('message', '')[:120]}")

# Test NL with preamble stripping
time.sleep(0.6)
r3c = chat("Hello")
sid3c = r3c["session_id"]
r3c = chat("I would love to visit Florence and the Amalfi coast", sid3c)
check("NL: Florence recognized", "Florence" in r3c.get("message", ""))
check("NL: Amalfi recognized", "Amalfi" in r3c.get("message", ""))

# Test multi-word country names
time.sleep(0.6)
r3d = chat("Hello")
sid3d = r3d["session_id"]
r3d = chat("South Africa", sid3d)
check("NL: South Africa recognized", "South Africa" in r3d.get("message", ""))

# Test traveller NL: "myself and my wife" should be couple, not solo
time.sleep(2.0)
r3e = chat("Hello")
sid3e = r3e["session_id"]
time.sleep(0.5)
r3e = chat("Italy", sid3e)
time.sleep(0.5)
r3e = chat("Continue", sid3e)
time.sleep(0.5)
r3e = chat("myself and my wife", sid3e)
check("NL: 'myself and my wife' = couple (2)", r3e.get("step_number") == 3, f"got step={r3e.get('step_number')}, msg={r3e.get('message','')[:80]}")
msg3e = r3e.get("message", "").lower()
check("NL: Not parsed as solo", "solo" not in msg3e, f"got: {msg3e[:80]}")

# =========================================================================
print("\n" + "=" * 70)
print("  SECTION 5: SKIP / SURPRISE / FLEXIBLE PATH")
print("=" * 70)

r4 = chat("Hello")
sid4 = r4["session_id"]
r4 = chat("Surprise me", sid4)
check("Skip: moves to step 2", r4.get("step_number") == 2)
check("Skip: mentions all packages", "1,99" in r4.get("message", "") or "2,00" in r4.get("message", "") or "199" in r4.get("message", ""))
check("Skip: traveller question correct", "travel" in r4.get("message", "").lower() or "joining" in r4.get("message", "").lower() or "journey" in r4.get("message", "").lower())
check("Skip: NO suggestion buttons", r4.get("suggestions") is None, f"got: {r4.get('suggestions')}")

# =========================================================================
print("\n" + "=" * 70)
print("  SECTION 6: SPECIAL COMMANDS")
print("=" * 70)

# Modify preferences
r5 = chat("Hello")
sid5 = r5["session_id"]
r5 = chat("Italy", sid5)
r5 = chat("Continue", sid5)
r5 = chat("modify preferences", sid5)
check("Modify: resets to step 1", r5.get("step_number") == 1)
check("Modify: correct wording", "Where would you like to go" in r5.get("message", ""))
check("Modify: no big suggestion list", r5.get("suggestions") is None, f"got: {r5.get('suggestions')}")

# Plan another trip
r6 = chat("plan another trip", sid5)
check("Plan another: resets to step 1", r6.get("step_number") == 1)
check("Plan another: correct wording", "Where would you like to go" in r6.get("message", ""))

# Speak with advisor
r7 = chat("speak with an advisor", sid5)
check("Advisor: proper response", "advisor" in r7.get("message", "").lower())

# =========================================================================
print("\n" + "=" * 70)
print("  SECTION 7: EDGE CASES & ROBUSTNESS")
print("=" * 70)

# Empty message
r_empty = chat("")
check("Empty msg: handled gracefully", "error" not in r_empty, str(r_empty.get("error", "")))

# Unknown destination
r_unk = chat("Hello")
sid_unk = r_unk["session_id"]
r_unk = chat("Xyzlandia", sid_unk)
check("Unknown dest: handled", r_unk.get("step_number") in (1, 2), f"step: {r_unk.get('step_number')}")
unk_msg = r_unk.get("message", "").lower()
if "could not find" in unk_msg or "no packages matched" in unk_msg or "do not have" in unk_msg:
    check("Unknown dest: helpful error msg", True)
    check("Unknown dest: suggests alternatives inline", "surprise me" in unk_msg or "destinations" in unk_msg or "enjoy" in unk_msg)
else:
    check("Unknown dest: still progresses", r_unk.get("step_number") == 2)

# Very long message
long_msg = "I want to go to Italy " * 50
r_long = chat("Hello")
sid_long = r_long["session_id"]
r_long = chat(long_msg, sid_long)
check("Long msg: handled gracefully", "error" not in r_long)

# =========================================================================
print("\n" + "=" * 70)
print("  SECTION 8: NO DEMO / NO FAKE DATA VERIFICATION")
print("=" * 70)

# Check that recommendations contain real package names (not generic)
DEMO_NAMES = ["Demo Package", "Sample Trip", "Test Package", "Example", "Placeholder"]
r8 = chat("Hello")
sid8 = r8["session_id"]
for msg in ["France", "Continue", "Couple", "May 2026", "Romance", "Honeymoon", "Premium", "First time", "Find my perfect trips"]:
    r8 = chat(msg, sid8)

recs8 = r8.get("recommendations") or []
for rec in recs8:
    name = rec.get("name", "")
    for demo in DEMO_NAMES:
        check(f"No demo name in '{name[:40]}'", demo.lower() not in name.lower())

    score = rec.get("match_score", 0)
    check(f"Score is realistic (0-100): {score}", 0 <= score <= 100)

    countries = rec.get("countries", "")
    check(f"Real countries in rec", bool(countries) and len(countries) > 2, f"countries: {countries}")

# =========================================================================
print("\n" + "=" * 70)
print("  SECTION 9: PERFORMANCE & STABILITY")
print("=" * 70)

# Rapid sequential requests (stress test)
times = []
for i in range(5):
    t0 = time.time()
    h = api_get("/planner/health")
    times.append(time.time() - t0)
    check(f"Health check #{i+1} < 2s", times[-1] < 2.0, f"took {times[-1]:.2f}s")

avg = sum(times) / len(times)
check(f"Avg health response < 1s", avg < 1.0, f"avg: {avg:.3f}s")

# Full chat flow timing
t0 = time.time()
r9 = chat("Hi")
sid9 = r9["session_id"]
for msg in ["Australia", "Continue", "Solo traveller", "October 2026, 14 days", "Adventure", "No special occasion", "Value", "Experienced", "Find my perfect trips"]:
    r9 = chat(msg, sid9)
total = time.time() - t0
check(f"Full 8-step flow < 30s", total < 30, f"took {total:.1f}s")
recs9 = r9.get("recommendations") or []
check("Australia flow: returns results", len(recs9) > 0, f"got {len(recs9)}")
if recs9:
    print(f"    Australia flow top result: {recs9[0].get('name')} ({recs9[0].get('match_score', 0):.0f}%)")

# =========================================================================
print("\n" + "=" * 70)
print("  SECTION 10: AUTOCOMPLETE API")
print("=" * 70)

# Note: Japan is not a Railbookers destination (not in any package's countries)
# so we test only destinations that exist in the real data

for query, expected in [("ita", "Italy"), ("swi", "Switz"), ("lon", "London"), ("pari", "Paris")]:
    ac = api_get(f"/planner/autocomplete?q={query}&step=destination")
    suggs = ac.get("suggestions", [])
    labels = [s.get("label", "") for s in suggs]
    found = any(expected in l for l in labels)
    check(f"Autocomplete '{query}' -> {expected}", found, f"got: {labels[:3]}")

# =========================================================================
# FINAL REPORT
# =========================================================================
print("\n" + "=" * 70)
print("  FINAL PRODUCTION READINESS REPORT")
print("=" * 70)
total_tests = PASS + FAIL
print(f"\n  Tests Passed:  {PASS}/{total_tests}")
print(f"  Tests Failed:  {FAIL}/{total_tests}")
if WARNINGS:
    print(f"  Warnings:      {len(WARNINGS)}")
    for w in WARNINGS:
        print(f"    - {w}")

if FAIL == 0:
    print("\n  ALL TESTS PASSED -- SYSTEM IS PRODUCTION READY")
    print("  READY FOR PUBLIC LAUNCH")
    sys.exit(0)
else:
    print(f"\n  {FAIL} TEST(S) FAILED -- REVIEW REQUIRED")
    sys.exit(1)
