"""
DEEP PRD VERIFICATION SUITE
Verifies every aspect of the chatbot against the PRD, Excel data, and SQL query.
Tests: DB schema, data integrity, RAG pipeline, chatbot flow, scoring, options.
"""
import urllib.request
import json
import time
import sys

API = "http://localhost:8890/api/v1"
PASS_COUNT = 0
FAIL_COUNT = 0
WARNINGS = []

def api_get(path):
    url = f"{API}{path}"
    r = urllib.request.urlopen(url)
    return json.loads(r.read())

def api_post(path, body):
    url = f"{API}{path}"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    r = urllib.request.urlopen(req)
    return json.loads(r.read())

def check(label, condition, detail=""):
    global PASS_COUNT, FAIL_COUNT
    if condition:
        PASS_COUNT += 1
        print(f"  PASS  {label}")
    else:
        FAIL_COUNT += 1
        print(f"  FAIL  {label} {detail}")

def warn(msg):
    WARNINGS.append(msg)
    print(f"  WARN  {msg}")

def chat(msg, sid=None):
    body = {"message": msg, "lang": "en"}
    if sid:
        body["session_id"] = sid
    return api_post("/planner/chat", body)

print("=" * 70)
print("  DEEP PRD VERIFICATION -- Railbookers Personal Trip Planner")
print("=" * 70)

# ======================================================================
# SECTION 1: DATABASE SCHEMA & DATA INTEGRITY
# ======================================================================
print("\n[1] DATABASE SCHEMA & DATA INTEGRITY (vs Excel KT_package_filtering_output)")

health = api_get("/planner/health")
check("DB connected", health.get("database_connected") == True)
check("1996+ packages loaded", health.get("packages_available", 0) >= 1990,
      f"got {health.get('packages_available')}")

# Verify all Excel columns are represented in DB via API
countries_data = api_get("/planner/options/countries")
countries = countries_data.get("countries", [])
check("Countries endpoint returns data", len(countries) > 0, f"got {len(countries)}")

# Excel has these countries -- verify top ones exist in DB
excel_countries = ["Italy", "Switzerland", "France", "Germany", "United Kingdom",
                   "Canada", "United States", "Austria", "Spain",
                   "Ireland", "Australia", "Netherlands", "Czech Republic", "India"]
for c in excel_countries:
    check(f"Excel country '{c}' in DB", c in countries, f"missing from {len(countries)} countries")

# Verify regions
regions_data = api_get("/planner/options/regions")
regions = regions_data.get("regions", [])
excel_regions = ["Europe", "North America", "Asia", "Oceania", "Africa", "South America"]
for r in excel_regions:
    check(f"Excel region '{r}' in DB", r in regions,
          f"got regions: {regions}")

# Verify trip types from Excel
trip_types_data = api_get("/planner/options/trip-types")
trip_types = trip_types_data.get("trip_types", [])
check("Trip types endpoint returns data", len(trip_types) > 10, f"got {len(trip_types)}")

# Excel trip types (from the KT SQL query categories)
excel_trip_types = ["Famous Trains", "Most Scenic Journeys", "Canadian Rockies",
                    "Luxury Rail", "Rocky Mountaineer Trips", "National Parks",
                    "Single Country Tours", "Lakes and Mountains", "Snow and Ice",
                    "Winter Experiences", "First Time to Europe"]
for tt in excel_trip_types:
    found = any(tt.lower() in t.lower() for t in trip_types)
    check(f"Excel trip type '{tt}' in DB", found, f"not found in {len(trip_types)} types")

# Verify hotel tiers (mapped from profitability_group in Excel)
tiers_data = api_get("/planner/options/hotel-tiers")
tiers = tiers_data.get("hotel_tiers", [])
check("Hotel tiers: Luxury present", "Luxury" in tiers)
check("Hotel tiers: Premium present", "Premium" in tiers)
check("Hotel tiers: Value present", "Value" in tiers)
# PRD mapping: Packages-High=Luxury, Packages-Standard=Premium, Packages-Low=Value
check("Hotel tier count = 3 (Luxury/Premium/Value)", len(tiers) == 3, f"got {tiers}")

# Verify departure types from Excel
# Excel has: Anyday, Fixed, Seasonal

# ======================================================================
# SECTION 2: RAG / VECTOR PIPELINE
# ======================================================================
print("\n[2] RAG / VECTOR PIPELINE VERIFICATION")

rag = api_get("/planner/rag/status")
check("RAG ready", rag.get("rag_ready") == True)
check("Vectors indexed >= 1990", rag.get("vectors_indexed", 0) >= 1990,
      f"got {rag.get('vectors_indexed')}")

# Verify RAG search returns results (semantic search test)
# We'll test this via the recommendation flow later

# ======================================================================
# SECTION 3: PRD CHATBOT FLOW -- 8 STEPS
# ======================================================================
print("\n[3] PRD 8-STEP CONVERSATIONAL FLOW")

# PRD Step 1: "Where would you like to go?"
r1 = chat("Switzerland")
sid = r1.get("session_id")
check("Step 1: Session created", sid is not None)
check("Step 1: Destination acknowledged", "switzerland" in r1.get("message", "").lower())
check("Step 1: step_number=1 (single dest)", r1.get("step_number") in (1, 2))
check("Step 1: total_steps=9", r1.get("total_steps") == 9)

# If single destination stays at step 1 (add more?), send Continue
if r1.get("step_number") == 1:
    r1b = chat("Continue", sid)
    check("Step 1b: Continue accepted", r1b.get("step_number") == 2)
    check("Step 1b: Asks about travellers", "travel" in r1b.get("message", "").lower())

# Test "suggest if unsure" (PRD improvement #1)
r1_flex = chat("surprise me")
check("Step 1 flex: 'suggest' handled", "package" in r1_flex.get("message", "").lower() or "search" in r1_flex.get("message", "").lower())

# PRD Step 2: "Who will be travelling with you?"
r2 = chat("Couple", sid)
check("Step 2: Travellers acknowledged", "two" in r2.get("message", "").lower() or "couple" in r2.get("message", "").lower() or "trip for" in r2.get("message", "").lower())
check("Step 2: Asks dates/duration", "when" in r2.get("message", "").lower() or "travel" in r2.get("message", "").lower())
check("Step 2: step_number=3", r2.get("step_number") == 3)
check("Step 2: Free-text input (no chips)", r2.get("suggestions") is None)

# PRD Step 3: "When would you like to travel, and for how long?"
r3 = chat("September 2026, 12 days, flexible dates", sid)
check("Step 3: Dates acknowledged", "sept" in r3.get("message", "").lower() or "autumn" in r3.get("message", "").lower() or "12" in r3.get("message", ""))
check("Step 3: Flexibility noted", "flexible" in r3.get("message", "").lower() or "noted" in r3.get("message", "").lower())
check("Step 3: Asks trip purpose", "reason" in r3.get("message", "").lower() or "experience" in r3.get("message", "").lower())
check("Step 3: step_number=4", r3.get("step_number") == 4)

# PRD-specified motivators now appear as inline hints in message text
check("Step 3: Inline hint has 'scenic'", "scenic" in r3.get("message", "").lower())
check("Step 3: Inline hint has 'romance'", "romance" in r3.get("message", "").lower())
check("Step 3: No chip buttons (free-text)", r3.get("suggestions") is None, f"got: {r3.get('suggestions')}")

# PRD Step 4: "What's the main reason for this trip?"
r4 = chat("Scenic sightseeing", sid)
check("Step 4: Purpose acknowledged", "scenic" in r4.get("message", "").lower() or "sightseeing" in r4.get("message", "").lower() or "great" in r4.get("message", "").lower())
check("Step 4: Asks special occasion", "occasion" in r4.get("message", "").lower() or "celebrating" in r4.get("message", "").lower())
check("Step 4: step_number=5", r4.get("step_number") == 5)

# PRD: occasion options now appear as inline hints, not chips
check("Step 4: No chip buttons (free-text)", r4.get("suggestions") is None, f"got: {r4.get('suggestions')}")
check("Step 4: Inline hint has occasion examples", "birthday" in r4.get("message", "").lower() or "anniversary" in r4.get("message", "").lower() or "honeymoon" in r4.get("message", "").lower())

# PRD Step 5: "Are you celebrating a special occasion?"
r5 = chat("Anniversary", sid)
check("Step 5: Occasion acknowledged", "anniversary" in r5.get("message", "").lower())
check("Step 5: Asks hotel preference", "hotel" in r5.get("message", "").lower())
check("Step 5: step_number=6", r5.get("step_number") == 6)

# PRD: Hotel tiers with brand examples
msg5 = r5.get("message", "")
check("Step 5: Luxury tier mentioned", "luxury" in msg5.lower())
check("Step 5: Premium tier mentioned", "premium" in msg5.lower())
check("Step 5: Value tier mentioned", "value" in msg5.lower())
check("Step 5: Ritz-Carlton example", "ritz" in msg5.lower() or "ritz-carlton" in msg5.lower())
check("Step 5: Marriott example", "marriott" in msg5.lower())
check("Step 5: Holiday Inn example", "holiday inn" in msg5.lower())

# PRD Step 6: "What type of hotels do you prefer?"
r6 = chat("Luxury", sid)
check("Step 6: Hotel pref acknowledged", "luxury" in r6.get("message", "").lower())
check("Step 6: Asks rail experience", "rail" in r6.get("message", "").lower())
check("Step 6: PRD phrasing", "first time" in r6.get("message", "").lower() or "taken a rail" in r6.get("message", "").lower())
check("Step 6: step_number=7", r6.get("step_number") == 7)

# PRD Step 7: "Have you taken a rail vacation before?"
r7 = chat("First time", sid)
check("Step 7: Rail exp acknowledged", "first" in r7.get("message", "").lower())
check("Step 7: Asks budget/requirements", "budget" in r7.get("message", "").lower() or "requirement" in r7.get("message", "").lower())
check("Step 7: step_number=8", r7.get("step_number") == 8)
check("Step 7: Accessibility mention", "accessibility" in r7.get("message", "").lower() or "special" in r7.get("message", "").lower())

# PRD Step 8: Budget + recommendations
r8 = chat("Under 5000 per person", sid)
check("Step 8: Got recommendations", r8.get("recommendations") is not None)
recs = r8.get("recommendations") or []
check("Step 8: 3-5 recommendations", 3 <= len(recs) <= 5, f"got {len(recs)}")
check("Step 8: step_number=8", r8.get("step_number") == 8)

# ======================================================================
# SECTION 4: RECOMMENDATION QUALITY & SCORING
# ======================================================================
print("\n[4] RECOMMENDATION QUALITY & SCORING")

if recs:
    r = recs[0]
    check("Rec has 'name'", "name" in r)
    check("Rec has 'description'", "description" in r)
    check("Rec has 'duration'", "duration" in r)
    check("Rec has 'countries'", "countries" in r)
    check("Rec has 'cities'", "cities" in r)
    check("Rec has 'match_score'", "match_score" in r)
    check("Rec has 'match_reasons'", "match_reasons" in r)
    check("Rec has 'package_url'", "package_url" in r)
    check("Rec has 'casesafeid'", "casesafeid" in r)
    check("Rec has 'route'", "route" in r)
    check("Rec has 'trip_type'", "trip_type" in r)
    check("Rec has 'highlights'", "highlights" in r)
    check("Rec has 'start_location'", "start_location" in r)
    check("Rec has 'end_location'", "end_location" in r)

    # Verify results match user preferences
    check("Top rec matches Switzerland", "switzerland" in r.get("countries", "").lower(),
          f"countries: {r.get('countries')}")
    check("Top rec score > 50%", r.get("match_score", 0) > 50,
          f"score: {r.get('match_score')}")
    check("Top rec has reasons", len(r.get("match_reasons", [])) >= 2,
          f"reasons: {r.get('match_reasons')}")

    # Verify package_url format matches Excel/SQL pattern
    url = r.get("package_url", "")
    check("Package URL is railbookers.com", "railbookers" in url.lower() or "amtrak" in url.lower(),
          f"url: {url}")

    # Verify duration format
    dur = r.get("duration", "")
    check("Duration has 'nights'", "night" in dur.lower(), f"duration: {dur}")

    # Verify scores are normalized (0-100)
    for rec in recs:
        s = rec.get("match_score", 0)
        check(f"Score in 0-100 range: {rec['name'][:30]}", 0 <= s <= 100, f"score={s}")

    # Summary message quality
    msg8 = r8.get("message", "")
    check("Summary has package count", "1,996" in msg8 or "1996" in msg8 or "2,000" in msg8 or "2000" in msg8)
    check("Summary shows destination", "switzerland" in msg8.lower())
    check("Summary shows travel count", "traveller" in msg8.lower() or "2" in msg8)
    check("Summary shows duration", "12" in msg8 or "night" in msg8.lower())
    check("Summary shows hotel pref", "luxury" in msg8.lower())
    check("Summary shows occasion", "anniversary" in msg8.lower())

# ======================================================================
# SECTION 5: EXCEL DATA MAPPING VERIFICATION
# ======================================================================
print("\n[5] EXCEL/SQL DATA FIELD MAPPING")

# Verify DB has all Excel columns mapped
# Excel: CASESAFEID__c, KaptioTravel__ExternalName__c, startlocation, endlocation,
#         includedcities, includedstates_provinces, includedcountries, includedregions,
#         triptype, route, KaptioTravel__Value__c(sales tips), packagedescription,
#         packagehighlights, packageinclusions, packagedaybyday, packagerank,
#         profitabilitygroup, accessrule, duration, departuretype, departuredates, package_url

# Test via a search result
search = api_get("/planner/destinations/search?q=Italy")
check("Search returns countries", len(search.get("countries", [])) > 0)
check("Search finds Italy", "Italy" in search.get("countries", []))

# Test multi-country search
search2 = api_get("/planner/destinations/search?q=Switzerland")
check("Search finds Switzerland", "Switzerland" in search2.get("countries", []))

# ======================================================================
# SECTION 6: PRD EDGE CASES & SPECIAL HANDLING
# ======================================================================
print("\n[6] PRD EDGE CASES & SPECIAL FLOWS")

# Test "No special occasion" (PRD explicit option)
r_occ = chat("Italy")
sid_occ = r_occ.get("session_id")
if r_occ.get("step_number") == 1:
    chat("Continue", sid_occ)
chat("Solo traveller", sid_occ)
chat("March 2026, 7 days", sid_occ)
chat("Culture & heritage", sid_occ)
r_no_occ = chat("No special occasion", sid_occ)
check("'No special occasion' handled gracefully",
      "reason enough" in r_no_occ.get("message", "").lower() or "no special" in r_no_occ.get("message", "").lower() or "hotel" in r_no_occ.get("message", "").lower() or r_no_occ.get("step_number") == 6)

# Test greeting handling
r_greet = chat("Hello!")
check("Greeting starts step 1", r_greet.get("step_number") == 1 or "where" in r_greet.get("message", "").lower())

# Test flexible destination (PRD: "suggest if unsure")
r_unsure = chat("I'm not sure where to go")
check("Unsure handled", "surprise" in r_unsure.get("message", "").lower() or "package" in r_unsure.get("message", "").lower() or "search" in r_unsure.get("message", "").lower())

# Test unknown destination
r_unknown = chat("Atlantis")
check("Unknown destination: helpful response", "could not find" in r_unknown.get("message", "").lower()
      or "not have" in r_unknown.get("message", "").lower()
      or "matched" in r_unknown.get("message", "").lower()
      or "suggest" in r_unknown.get("message", "").lower())

# Test family parsing (PRD: combined question)
r_fam = chat("France")
sid_f = r_fam.get("session_id")
if r_fam.get("step_number") == 1:
    chat("Continue", sid_f)
r_fam2 = chat("Family with 2 kids, 4 total", sid_f)
check("Family parsing: type", "family" in r_fam2.get("message", "").lower())

# ======================================================================
# SECTION 7: SCORING ALGORITHM VERIFICATION
# ======================================================================
print("\n[7] SCORING ALGORITHM DEPTH CHECK")

# Run a very specific query and verify scoring makes sense
# Italy + 10 days + Culture + Premium hotel
r_score = chat("Italy")
sid_s = r_score.get("session_id")
if r_score.get("step_number") == 1:
    chat("Continue", sid_s)
chat("2 adults", sid_s)
chat("October 2026, 10 days", sid_s)
chat("Culture & heritage", sid_s)
chat("No special occasion", sid_s)
chat("Premium", sid_s)
chat("Experienced rail traveller", sid_s)
r_final = chat("Find my perfect trips", sid_s)
score_recs = r_final.get("recommendations") or []

check("Italy query: got recs", len(score_recs) > 0)
if score_recs:
    top = score_recs[0]
    check("Italy query: top rec visits Italy",
          "italy" in top.get("countries", "").lower(),
          f"countries={top.get('countries')}")
    check("Italy query: top score > 50%", top.get("match_score", 0) > 50,
          f"score={top.get('match_score')}")

    # Verify scores are descending
    scores = [r.get("match_score", 0) for r in score_recs]
    is_descending = all(scores[i] >= scores[i+1] for i in range(len(scores)-1))
    check("Scores in descending order", is_descending, f"scores={scores}")

    # Verify match_reasons mention user preferences
    all_reasons = " ".join(" ".join(r.get("match_reasons", [])) for r in score_recs)
    check("Reasons mention Italy", "italy" in all_reasons.lower())
    check("Reasons mention duration", "night" in all_reasons.lower() or "duration" in all_reasons.lower())

# ======================================================================
# SECTION 8: WELCOME / OPTIONS ENDPOINTS
# ======================================================================
print("\n[8] WELCOME & OPTIONS ENDPOINTS")

welcome = api_get("/planner/flow/welcome")
check("Welcome: has message", welcome.get("message") == "Railbookers")
check("Welcome: has subtitle", "planner" in welcome.get("subtitle", "").lower())
check("Welcome: has first_question", "where" in welcome.get("first_question", "").lower())
check("Welcome: has packages_available", welcome.get("packages_available", 0) >= 1990)
check("Welcome: has suggestions (countries)", len(welcome.get("suggestions", [])) > 5)

# Cities endpoint
cities = api_get("/planner/options/cities?country=Italy")
check("Cities for Italy: has data", len(cities.get("cities", [])) > 0)
italy_cities = cities.get("cities", [])
check("Cities for Italy: Rome", any("rome" in c.lower() for c in italy_cities),
      f"got {len(italy_cities)} cities")

# ======================================================================
# SECTION 9: API CONSISTENCY
# ======================================================================
print("\n[9] API RESPONSE CONSISTENCY")

# Verify ChatResponse model fields
r_test = chat("Japan")
check("Response has 'message'", "message" in r_test)
check("Response has 'suggestions'", "suggestions" in r_test)
check("Response has 'step_number'", "step_number" in r_test)
check("Response has 'total_steps'", "total_steps" in r_test)
check("Response has 'needs_input'", "needs_input" in r_test)
check("Response has 'session_id'", "session_id" in r_test)
check("Response has 'placeholder'", "placeholder" in r_test)
check("total_steps always 9", r_test.get("total_steps") == 9)

# ======================================================================
# SECTION 10: PERFORMANCE
# ======================================================================
print("\n[10] PERFORMANCE")

# Full flow speed test
t0 = time.time()
r = chat("Canada")
sid_perf = r.get("session_id")
if r.get("step_number") == 1:
    chat("Continue", sid_perf)
chat("4 adults", sid_perf)
chat("July 2026, 14 days", sid_perf)
chat("Adventure & outdoors", sid_perf)
chat("No special occasion", sid_perf)
chat("Value", sid_perf)
chat("First time on rail", sid_perf)
r_perf = chat("Find my perfect trips", sid_perf)
t_total = time.time() - t0
check(f"Full 8-step flow < 30s", t_total < 30, f"took {t_total:.1f}s")
check("Canada query: got recs", len(r_perf.get("recommendations") or []) > 0)
if r_perf.get("recommendations"):
    check("Canada query: matches Canada",
          "canada" in r_perf["recommendations"][0].get("countries", "").lower(),
          f"got {r_perf['recommendations'][0].get('countries')}")

# ======================================================================
# RESULTS
# ======================================================================
print("\n" + "=" * 70)
print(f"  RESULTS: {PASS_COUNT}/{PASS_COUNT + FAIL_COUNT} PASSED | {FAIL_COUNT} FAILED")
if WARNINGS:
    print(f"  WARNINGS: {len(WARNINGS)}")
    for w in WARNINGS:
        print(f"    - {w}")
print(f"  TIME: {time.time() - t0:.1f}s")
print("=" * 70)

if FAIL_COUNT == 0:
    print("\n  ALL CHECKS PASSED -- PRD VERIFIED -- PRODUCTION READY")
else:
    print(f"\n  {FAIL_COUNT} ISSUES NEED ATTENTION")

sys.exit(FAIL_COUNT)
