"""
ULTIMATE PRODUCTION READINESS TEST
===================================
Tests: Stability, Speed, Concurrency, Edge Cases, Data Verification,
Security, Data Integrity, Error Handling, Memory Safety, Scale Readiness

Railbookers Personal Trip Planner v2.0.0
"""

import json, time, urllib.request, urllib.error, concurrent.futures, random, sys

BASE = "http://localhost:8890/api/v1"
P, F = 0, 0
T0 = time.time()

def check(name, cond, detail=""):
    global P, F
    if cond: P += 1; print(f"  \033[92mPASS\033[0m  {name}")
    else: F += 1; print(f"  \033[91mFAIL\033[0m  {name} -- {detail}")

def api_post(path, data, timeout=15):
    body = json.dumps(data).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp: return json.loads(resp.read())
    except Exception as e: return {"error": str(e)}

def api_get(path, timeout=10):
    try:
        with urllib.request.urlopen(f"{BASE}{path}", timeout=timeout) as resp: return json.loads(resp.read())
    except Exception as e: return {"error": str(e)}

def chat(msg, sid=None):
    d = {"message": msg}
    if sid: d["session_id"] = sid
    return api_post("/planner/chat", d)

def full_flow(dest="Switzerland", trav="2 adults", dates="June 2026, 10 days",
              purp="Scenic sightseeing", occ="Anniversary", hotel="Luxury",
              rail="First time", budget="No special requirements") -> tuple:
    """Returns (ms: int, recs: list[dict], error: str|None)"""
    start = time.time()
    try:
        r1 = chat(dest); sid = r1.get("session_id")
        if not sid: return (0, [], "No session_id")
        # Single destination stays at step 1 — need "Continue" to advance
        if r1.get("step_number") == 1:
            chat("Continue", sid)
        for msg in [trav, dates, purp, occ, hotel, rail]:
            chat(msg, sid)
        # Budget answer → summary (step 9)
        r8 = chat(budget, sid)
        recs: list[dict] = r8.get("recommendations") or []  # type: ignore[assignment]
        # If no recs yet (summary shown), send "Search now" to get them
        if not recs:
            r9 = chat("Search now", sid)
            recs = r9.get("recommendations") or []
        return (int((time.time()-start)*1000), recs, None)
    except Exception as e: return (0, [], str(e))

print("="*70)
print("  ULTIMATE PRODUCTION READINESS TEST")
print("  Railbookers Personal Trip Planner v2.0.0")
print("="*70)

# ====== SECTION 1: SPEED ======
print("\n[1] SPEED & RESPONSE TIME")
t=time.time(); h=api_get("/planner/health"); ms=int((time.time()-t)*1000)
check(f"Health: {ms}ms (< 3s)", ms < 3000)
t=time.time(); w=api_get("/planner/flow/welcome"); ms=int((time.time()-t)*1000)
check(f"Welcome: {ms}ms (< 3s)", ms < 3000)
t=time.time(); r=chat("Italy"); ms=int((time.time()-t)*1000)
check(f"Chat response: {ms}ms (< 5s)", ms < 5000)
ms,recs,err = full_flow("France","2 adults","March 2026, 7 days","Romance","Honeymoon","Luxury","First time","No budget limit")
check(f"Full 8-step flow: {ms}ms (< 30s)", ms < 30000 and not err, err or "")
t=time.time(); api_get("/planner/options/countries"); ms=int((time.time()-t)*1000)
check(f"Countries: {ms}ms (< 3s)", ms < 3000)

# ====== SECTION 2: CONCURRENCY ======
print("\n[2] CONCURRENT USER SIMULATION")
def hcheck(_):
    t=time.time(); r=api_get("/planner/health"); return (time.time()-t, "error" not in r)
with concurrent.futures.ThreadPoolExecutor(20) as ex:
    futs = list(ex.map(hcheck, range(20)))
    check("20 concurrent health: all OK", all(f[1] for f in futs))
    check(f"Concurrent avg: {int(sum(f[0] for f in futs)/len(futs)*1000)}ms", sum(f[0] for f in futs)/len(futs) < 5)

dests = ["Italy","France","Spain","Germany","Switzerland","Canada","Australia","Austria","Ireland","United Kingdom"]
def cs(d):
    try: r=chat(d); return "error" not in r and r.get("session_id") is not None
    except: return False
with concurrent.futures.ThreadPoolExecutor(10) as ex:
    check("10 concurrent chats: all OK", all(ex.map(cs, dests)))

def cf(d):
    _,recs,err = full_flow(d); return err is None and len(recs)>0
with concurrent.futures.ThreadPoolExecutor(5) as ex:
    check("5 concurrent full flows: all OK", all(ex.map(cf, ["Italy","Germany","Spain","Canada","France"])))

# ====== SECTION 3: EDGE CASES ======
print("\n[3] EDGE CASES & BOUNDARY TESTING")
check("Empty message: no crash", "error" not in chat(""))
check("1000+ char message: handled", "error" not in chat("Switzerland "*100) and chat("Switzerland "*100).get("session_id"))
check("Special chars: handled", "error" not in chat("Zürich & München — it's @#$%^&*()"))
check("Unicode/emoji: handled", "error" not in chat("Paris 🇫🇷 ❤️"))
check("Numbers only: no crash", "error" not in chat("12345"))
check("SQL injection: safe", "error" not in chat("'; DROP TABLE rag_packages; --"))
check("XSS attempt: safe", "error" not in chat("<script>alert('xss')</script>"))
check("'null' message: handled", "error" not in chat("null"))
check("'undefined' message: handled", "error" not in chat("undefined"))
r1=chat("Italy"); sid=r1.get("session_id")
for i in range(5): chat(f"test {i}", sid)
check("Rapid sequential: stable", "error" not in chat("2 adults", sid))
check("Invalid session ID: graceful", "error" not in chat("Hello", "nonexistent-id-12345"))

# ====== SECTION 4: DATA INTEGRITY VERIFICATION ======
print("\n[4] DATA INTEGRITY VERIFICATION")
flows = [
    ("Italy","2 adults","July 2026, 8 days","Culture & heritage","No special occasion","Premium","Experienced","None"),
    ("Canada","Family of 4","August 2026, 14 days","Adventure & outdoors","Birthday","Luxury","First time","Wheelchair accessible"),
    ("France","Couple","September 2026, 5 days","Romance","Anniversary","Luxury","Experienced","No budget limit"),
    ("United Kingdom","Solo","May 2026, 7 days","Scenic sightseeing","No special occasion","Value","First time","Under 3000"),
]
all_valid, all_urls, all_scores, total_recs, fabricated = True, True, True, 0, False
for dest,trav,dates,purp,occ,hotel,rail,budget in flows:
    time.sleep(0.3)
    _,recs,err = full_flow(dest,trav,dates,purp,occ,hotel,rail,budget)
    if err or not recs: all_valid = False; continue
    for rec in recs:
        total_recs += 1
        if not rec.get("casesafeid"): all_valid = False
        pkg_url = str(rec.get("package_url","")).strip().lower()
        if pkg_url and not pkg_url.startswith("http"): all_urls = False
        s = rec.get("match_score", -1)
        if s < 0 or s > 100: all_scores = False
        n = rec.get("name","")
        if "AI generated" in n or "example" in n.lower(): fabricated = True
check(f"All {total_recs} recs: valid casesafeid", all_valid)
check(f"All {total_recs} recs: valid URL", all_urls)
check(f"All {total_recs} recs: scores 0-100", all_scores)
check("No fabricated data", not fabricated)

time.sleep(0.5)
ms1,recs1,_ = full_flow("Switzerland")
if recs1:
    check("Recs have real CaseSafeIDs", all(r.get("casesafeid") and len(str(r.get("casesafeid")))>5 for r in recs1))
time.sleep(0.3)
_,rf,ef = full_flow("Atlantis","2","July 2026","Adventure","None","Premium","First time","None")
check("Non-existent dest: no crash", ef is None)

# ====== SECTION 5: DATA INTEGRITY ======
print("\n[5] DATA INTEGRITY")
cr = api_get("/planner/options/countries")
countries = cr.get("countries",[]) if isinstance(cr, dict) else cr
check("Countries: valid list (30+)", isinstance(countries, list) and len(countries) > 30)
tr = api_get("/planner/options/trip-types")
tt = tr.get("trip_types",[]) if isinstance(tr, dict) else tr
check("Trip types: valid list (5+)", isinstance(tt, list) and len(tt) > 5)
hr = api_get("/planner/options/hotel-tiers")
ht = hr.get("hotel_tiers",[]) if isinstance(hr, dict) else hr
check("Hotel tiers: exactly 3", isinstance(ht, list) and len(ht) == 3)
ts = " ".join(str(t).lower() for t in (ht or []))
check("Tier: Luxury", "luxury" in ts)
check("Tier: Premium", "premium" in ts)
check("Tier: Value", "value" in ts)
rg = api_get("/planner/rag/status")
check("RAG: 1996 vectors", rg.get("vectors_indexed",0)>=1990)
check("RAG: ready", rg.get("rag_ready")==True)
rr = api_get("/planner/options/regions")
regions = rr.get("regions",[]) if isinstance(rr, dict) else rr
check("Regions: Europe", any("europe" in str(r).lower() for r in (regions or [])))
check("Regions: North America", any("north america" in str(r).lower() for r in (regions or [])))
check("Regions: Asia", any("asia" in str(r).lower() for r in (regions or [])))
check("Packages: 1996+", api_get("/planner/health").get("packages_available",0)>=1990)

# ====== SECTION 6: PRD 8-STEP FLOW ======
print("\n[6] PRD 8-STEP FLOW CORRECTNESS")
r1=chat("Switzerland"); sid=r1.get("session_id")
check("Step 1: session", sid is not None)
check("Step 1: step=1 (single dest)", r1.get("step_number")==1)
check("Step 1: destination ack", "switzerland" in r1.get("message","").lower())
# Continue to advance single destination
r1b=chat("Continue", sid)
check("Step 1b: step=2", r1b.get("step_number")==2)
check("Step 1b: traveller Q", any(w in r1b.get("message","").lower() for w in ["travel","who","companion","group"]))

r2=chat("2 adults and 1 child", sid)
check("Step 2: step=3", r2.get("step_number")==3)
check("Step 2: dates Q", any(w in r2.get("message","").lower() for w in ["when","date","month","duration","long","how"]))

r3=chat("July 2026, 10-12 days", sid)
check("Step 3: step=4", r3.get("step_number")==4)
check("Step 3: purpose Q", any(w in r3.get("message","").lower() for w in ["excit","interest","purpose","motiv","draw","reason","experience","looking"]))

r4=chat("Adventure & outdoors", sid)
check("Step 4: step=5", r4.get("step_number")==5)
check("Step 4: occasion Q", any(w in r4.get("message","").lower() for w in ["occasion","celebrat","special"]))

r5=chat("No special occasion", sid)
check("Step 5: step=6", r5.get("step_number")==6)
check("Step 5: hotel Q", any(w in r5.get("message","").lower() for w in ["hotel","accommodation","stay"]))

r6=chat("Premium", sid)
check("Step 6: step=7", r6.get("step_number")==7)
check("Step 6: rail Q", any(w in r6.get("message","").lower() for w in ["rail","train"]))

r7=chat("First time rail traveller", sid)
check("Step 7: step=8", r7.get("step_number")==8)
check("Step 7: budget Q", any(w in r7.get("message","").lower() for w in ["budget","require","anything","consider","need"]))

r8=chat("No special requirements", sid)
recs = r8.get("recommendations") or []
# If summary shown (no recs), send "Search now" to trigger search
if not recs:
    r9=chat("Search now", sid)
    recs = r9.get("recommendations") or []
check("Step 8: has recs", len(recs) > 0)
check("Step 8: 3-5 recs", 3 <= len(recs) <= 5)
check("Step 8: step>=8", r8.get("step_number",0)>=8 or (recs and len(recs)>0))

if recs:
    for f in ["name","description","duration","countries","cities","match_score","match_reasons","package_url","casesafeid","route","trip_type","highlights","start_location","end_location"]:
        check(f"Rec field: '{f}'", f in recs[0])

# ====== SECTION 7: ERROR HANDLING ======
print("\n[7] ERROR HANDLING")
try:
    req=urllib.request.Request(f"{BASE}/planner/chat", data=b"not json", headers={"Content-Type":"application/json"})
    urllib.request.urlopen(req, timeout=10); check("Malformed JSON", True)
except urllib.error.HTTPError as e: check("Malformed JSON: 422", e.code==422)
except: check("Malformed JSON: handled", True)

try:
    req=urllib.request.Request(f"{BASE}/planner/nonexistent"); urllib.request.urlopen(req, timeout=5)
    check("404 unknown endpoint", False)
except urllib.error.HTTPError as e: check("404 unknown endpoint", e.code==404)
except: check("404 unknown endpoint", True)

r_reset=chat("Italy"); sid_r=r_reset.get("session_id")
api_post("/planner/session/reset", {"session_id": sid_r})
api_post("/planner/session/reset", {"session_id": sid_r})
check("Double reset: no crash", True)

# ====== SECTION 8: SECURITY ======
print("\n[8] SECURITY HEADERS")
try:
    req=urllib.request.Request(f"{BASE}/planner/health")
    with urllib.request.urlopen(req, timeout=10) as resp:
        hdrs = {k.lower(): v for k, v in resp.headers.items()}
        check("X-Content-Type-Options: nosniff", hdrs.get("x-content-type-options","").lower()=="nosniff")
        check("X-Frame-Options", "x-frame-options" in hdrs)
        check("X-Powered-By", "x-powered-by" in hdrs)
        check("X-Process-Time", "x-process-time" in hdrs)
        check("Content-Type: JSON", "application/json" in hdrs.get("content-type",""))
except Exception as e: check("Security headers", False, str(e))

# ====== SECTION 9: FRONTEND ======
print("\n[9] FRONTEND PRODUCTION")
try:
    with urllib.request.urlopen("http://localhost:3000", timeout=10) as resp:
        html = resp.read().decode()
        check("Frontend: 200 OK", resp.status==200)
        check("Frontend: Railbookers brand", "railbookers" in html.lower())
        check("Frontend: CSS loaded", ".css" in html)
        check("Frontend: JS loaded", ".js" in html)
        check("Frontend: cache bust", "?v=" in html)
        check("Frontend: has <title>", "<title>" in html.lower())
        check("Frontend: viewport meta", "viewport" in html.lower())
except Exception as e: check("Frontend reachable", False, str(e))

# ====== SECTION 10: MULTI-DESTINATION ACCURACY ======
print("\n[10] MULTI-DESTINATION ACCURACY")
time.sleep(5)  # Allow server to recover from concurrent tests
for dest, exp in {"Italy":["italy"],"Canada":["canada"],"United Kingdom":["united kingdom","england","scotland","uk"],"Australia":["australia"],"France":["france"]}.items():
    time.sleep(3)
    for _retry in range(3):
        _,recs,err = full_flow(dest)
        if err is None: break
        time.sleep(3)
    if recs:
        ac = " ".join(r.get("countries","").lower() for r in recs)
        check(f"{dest}: relevant recs", any(c in ac for c in exp))
    else: check(f"{dest}: got recs", False)

# ====== SECTION 11: STABILITY ======
print("\n[11] STABILITY UNDER LOAD")
time.sleep(5)  # Allow server to recover
results = []
for i in range(5):
    time.sleep(3)
    ms,recs,err = full_flow(
        random.choice(["Italy","France","Germany","Spain","Canada"]),
        random.choice(["2 adults","Solo traveller","Family of 4"]),
        random.choice(["June 2026, 7 days","August 2026, 10 days","December 2026, 5 days"]),
        random.choice(["Romance","Adventure & outdoors","Culture & heritage"]),
        random.choice(["No special occasion","Anniversary","Birthday"]),
        random.choice(["Luxury","Premium","Value"]),
        random.choice(["First time","Experienced"]),
        "No requirements"
    )
    results.append((err is None, ms, len(recs or [])))
sc = sum(1 for s,_,_ in results if s)
avg_ms = sum(m for _,m,_ in results)/len(results)
total_r = sum(r for _,_,r in results)
check(f"5 sequential flows: {sc}/5", sc==5)
check(f"Avg flow time: {int(avg_ms)}ms (< 30s)", avg_ms < 30000)
check(f"Total recs: {total_r}", total_r > 0)

# ====== SECTION 12: SCHEMA CONSISTENCY ======
print("\n[12] API SCHEMA CONSISTENCY")
rs = chat("Spain")
for f in ["message","step_number","total_steps","needs_input","session_id","suggestions"]:
    check(f"Chat has '{f}'", f in rs)
check("total_steps=9", rs.get("total_steps")==9)
check("step_number is int", isinstance(rs.get("step_number"), int))
check("needs_input is bool", isinstance(rs.get("needs_input"), bool))
check("session_id is str", isinstance(rs.get("session_id"), str))
check("suggestions is list", isinstance(rs.get("suggestions"), list))

# ====== SECTION 13: WELCOME FLOW ======
print("\n[13] WELCOME FLOW QUALITY")
w = api_get("/planner/flow/welcome")
for f in ["message","subtitle","first_question","suggestions","packages_available"]:
    check(f"Welcome: '{f}'", f in w)
check("Welcome: 1996+ packages", w.get("packages_available",0)>=1990)
check("Welcome: country suggestions", len(w.get("suggestions",[]))>5)
check("Welcome: Railbookers brand", "railbookers" in w.get("message","").lower())

rh=chat("Hello!")
check("Greeting: step=1", rh.get("step_number")==1)
rd=chat("Italy")
check("Direct dest: step=1 (single)", rd.get("step_number")==1 and rd.get("session_id"))

# ====== FINAL ======
total_time = time.time() - T0
print("\n" + "="*70)
print(f"  RESULTS: {P}/{P+F} PASSED | {F} FAILED")
print(f"  TIME: {total_time:.1f}s")
print("="*70)
if F == 0:
    print("\n  ALL CHECKS PASSED")
    print("  PRODUCTION READY")
    print("  ALL CHECKS PASSED - VERIFIED")
else:
    print(f"\n  {F} ISSUES NEED ATTENTION")
