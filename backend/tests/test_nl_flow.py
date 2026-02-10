"""Full NL flow test: greeting to recommendations."""
import urllib.request, json, time

BASE = "http://127.0.0.1:8890/api/v1"

def chat(msg, sid=None):
    body = json.dumps({"message": msg, "session_id": sid}).encode()
    req = urllib.request.Request(f"{BASE}/planner/chat", data=body, headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())

r = chat("Hello")
sid = r["session_id"]
print("1. Greeting OK")

r = chat("I am looking for a package in Rome and Venice and Switzerland", sid)
print(f"2. Dest: {r['message'][:100]}")
time.sleep(0.3)

r = chat("myself and my wife", sid)
print(f"3. Travellers: {r['message'][:80]}")
time.sleep(0.3)

r = chat("June 2026, about 10 days", sid)
print(f"4. Dates: {r['message'][:80]}")
time.sleep(0.3)

r = chat("Culture and heritage, scenic rail", sid)
print(f"5. Purpose: {r['message'][:80]}")
time.sleep(0.3)

r = chat("Anniversary", sid)
print(f"6. Occasion: {r['message'][:80]}")
time.sleep(0.3)

r = chat("Luxury", sid)
print(f"7. Hotel: {r['message'][:80]}")
time.sleep(0.3)

r = chat("First time", sid)
print(f"8. Rail: {r['message'][:80]}")
time.sleep(0.3)

r = chat("No budget limit", sid)
print(f"9. Summary: {r['message'][:250]}")
time.sleep(0.3)

r = chat("Search now", sid)
recs = r.get("recommendations", [])
print(f"\n10. RESULTS: {len(recs)} recommendations")
for i, rec in enumerate(recs):
    name = rec.get("name", "?")
    score = rec.get("match_score", 0)
    countries = rec.get("countries", "?")
    print(f"    [{i+1}] {name} | {score:.0f}% | {countries}")

print("\nFLOW COMPLETE" if recs else "\nNO RESULTS - ISSUE!")
