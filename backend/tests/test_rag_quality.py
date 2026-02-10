"""
Final RAG quality verification - test real-world search scenarios.
"""
import urllib.request
import urllib.error
import json
import time

BASE = "http://127.0.0.1:8890/api/v1"

def chat(msg, sid=None, lang="en"):
    data = json.dumps({"message": msg, "session_id": sid, "lang": lang}).encode()
    for attempt in range(5):
        req = urllib.request.Request(f"{BASE}/planner/chat", data=data, headers={"Content-Type": "application/json"})
        try:
            return json.loads(urllib.request.urlopen(req, timeout=30).read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 2 ** attempt  # exponential backoff: 1, 2, 4, 8, 16s
                time.sleep(wait)
            else:
                time.sleep(1)
    # Final attempt
    req = urllib.request.Request(f"{BASE}/planner/chat", data=data, headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())

def test_flow(name, messages, expected_check):
    """Run a full chat flow and verify recommendations."""
    time.sleep(2.0)
    r = chat("Hello")
    sid = r["session_id"]
    for msg in messages:
        time.sleep(0.6)
        r = chat(msg, sid)
    recs = r.get("recommendations") or []
    result = expected_check(r, recs)
    status = "PASS" if result else "FAIL"
    print(f"  [{status}] {name}")
    if recs:
        for i, rec in enumerate(recs[:3]):
            print(f"         [{i+1}] {rec.get('name', '')[:55]} | {rec.get('match_score', 0):.0f}% | {rec.get('countries', '')[:30]}")
    else:
        print(f"         No recommendations returned")
        if not result:
            print(f"         Response: step={r.get('step_number')}, msg={r.get('message','')[:100]}")
    return result

print("=" * 70)
print("  RAG QUALITY VERIFICATION - REAL WORLD SCENARIOS")
print("=" * 70)

passed = 0
total = 0

# Test 1: Italy romantic trip
total += 1
if test_flow("Italy romantic honeymoon",
    ["Italy", "Continue", "Couple", "September 2026, 10 days", "Romance", "Honeymoon", "Luxury", "First time", "Find my perfect trips"],
    lambda r, recs: len(recs) > 0 and any("Italy" in rc.get("countries", "") for rc in recs)):
    passed += 1

# Test 2: USA national parks adventure
total += 1
if test_flow("USA National Parks adventure",
    ["United States", "Continue", "4 friends", "July 2026, 14 days", "Adventure and outdoors", "No special occasion", "Premium", "Experienced", "Find my perfect trips"],
    lambda r, recs: len(recs) > 0 and any("United States" in rc.get("countries", "") for rc in recs)):
    passed += 1

# Test 3: Family Europe first time
total += 1
if test_flow("Family first-time Europe",
    ["France and Germany", "2 adults and 2 children", "Summer 2026, 12 days", "Culture", "No special occasion", "Premium", "First time on a rail vacation", "Find my perfect trips"],
    lambda r, recs: len(recs) > 0):
    passed += 1

# Test 4: Solo UK adventure
total += 1
if test_flow("Solo UK short break",
    ["United Kingdom", "Continue", "Solo", "April 2026, 5 days", "Scenic sightseeing", "No special occasion", "Value", "First time", "Find my perfect trips"],
    lambda r, recs: len(recs) > 0 and any("United Kingdom" in rc.get("countries", "") for rc in recs)):
    passed += 1

# Test 5: Canada Rocky Mountaineer
total += 1
if test_flow("Canada Rockies luxury",
    ["Canada", "Continue", "Couple", "August 2026, 14 days", "Scenic", "Anniversary", "Luxury", "Some experience", "Find my perfect trips"],
    lambda r, recs: len(recs) > 0 and any("Canada" in rc.get("countries", "") for rc in recs)):
    passed += 1

# Test 6: Surprise me (no destination)
total += 1
if test_flow("Surprise me flow",
    ["Surprise me", "Solo traveller", "Flexible, 10 days", "Adventure", "No special occasion", "Value", "Never", "Find my perfect trips"],
    lambda r, recs: len(recs) > 0):
    passed += 1

# Test 7: Multi-country Europe
total += 1
if test_flow("Multi-country Europe trip",
    ["Italy, Switzerland, and Austria", "Couple", "October 2026, 14 days", "Scenic", "No special occasion", "Luxury", "Experienced", "Find my perfect trips"],
    lambda r, recs: len(recs) > 0):
    passed += 1

# Test 8: NL query -> full flow (Scotland = United Kingdom in DB)
total += 1
if test_flow("NL input -> Scotland recognized as UK",
    ["I want to explore the Scottish Highlands by rail", "Continue", "myself and my wife", "Spring 2026, 7 days", "Scenic sightseeing", "No special occasion", "Premium", "First time", "Find my perfect trips"],
    lambda r, recs: len(recs) > 0 and any("United Kingdom" in rc.get("countries", "") for rc in recs)):
    passed += 1

# Test 9: Budget-conscious India
total += 1
if test_flow("India budget traveller",
    ["India", "Continue", "Solo", "Winter 2026, 10 days", "Culture", "No special occasion", "Value", "First time", "Find my perfect trips"],
    lambda r, recs: len(recs) > 0 and any("India" in rc.get("countries", "") for rc in recs)):
    passed += 1

# Test 10: French language full flow (uses alias: Italie -> Italy)
total += 1
time.sleep(2.0)
r = chat("Bonjour", lang="fr")
sid = r["session_id"]
for msg in ["Italie", "Continue", "Couple", "Juin 2026, 10 jours", "Romance", "Pas d'occasion spéciale", "Luxury", "Première fois", "Trouver mes voyages parfaits"]:
    time.sleep(0.6)
    r = chat(msg, sid, lang="fr")
recs = r.get("recommendations") or []
if len(recs) > 0:
    passed += 1
    print(f"  [PASS] French language full flow")
    for i, rec in enumerate(recs[:3]):
        print(f"         [{i+1}] {rec.get('name', '')[:55]} | {rec.get('match_score', 0):.0f}% | {rec.get('countries', '')[:30]}")
else:
    print(f"  [FAIL] French language full flow - no recommendations")

print()
print(f"  RAG Quality: {passed}/{total} scenarios passed")
if passed == total:
    print("  ALL RAG SCENARIOS VERIFIED")
else:
    print(f"  {total - passed} scenario(s) need review")
