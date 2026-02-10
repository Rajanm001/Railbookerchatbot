"""Quick test of multi-country and language features."""
import urllib.request, json, sys, io

# Handle non-ASCII output (Hindi, Arabic, etc.)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

API = "http://127.0.0.1:8890/api/v1"

def chat(msg, sid=None, lang="en"):
    body = {"message": msg, "lang": lang}
    if sid:
        body["session_id"] = sid
    req = urllib.request.Request(
        f"{API}/planner/chat",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req).read())


print("=== TEST 1: Single country asks to add more ===")
r1 = chat("Italy")
sid = r1["session_id"]
print(f"  Step: {r1['step_number']}")
print(f"  Suggestions: {r1.get('suggestions')}")
print(f"  Message: {r1['message'][:100]}")

print("\n=== TEST 2: Add Switzerland ===")
r2 = chat("Switzerland", sid)
print(f"  Step: {r2['step_number']}")
print(f"  Message: {r2['message'][:100]}")

print("\n=== TEST 3: Multi-country goes straight to step 2 ===")
r3 = chat("France and Germany")
print(f"  Step: {r3['step_number']}")
print(f"  Message: {r3['message'][:100]}")

print("\n=== TEST 4: Single country + Continue ===")
r4 = chat("Spain")
s4 = r4["session_id"]
print(f"  Step after Spain: {r4['step_number']}")
print(f"  Has Continue btn: {'Continue' in (r4.get('suggestions') or [])}")
r4b = chat("Continue", s4)
print(f"  Step after Continue: {r4b['step_number']}")
print(f"  Message: {r4b['message'][:100]}")
assert r4b['step_number'] == 2, f"FAIL: expected step 2 after Continue, got {r4b['step_number']}"
print("  PASS")

print("\n=== TEST 5: French language ===")
r5 = chat("Bonjour", lang="fr")
s5 = r5["session_id"]
print(f"  Step: {r5['step_number']}")
print(f"  Message: {r5['message'][:150]}")

print("\n=== TEST 6: French destination ===")
r6 = chat("Italy", s5, lang="fr")
print(f"  Step: {r6['step_number']}")
print(f"  Message: {r6['message'][:100]}")
r6b = chat("Continue", s5, lang="fr")
print(f"  Step after Continue: {r6b['step_number']}")
print(f"  Question: {r6b['message'][:120]}")

print("\n=== TEST 7: Hindi language ===")
r7 = chat("Hello", lang="hi")
print(f"  Step: {r7['step_number']}")
print(f"  Message: {r7['message'][:200]}")

print("\n=== TEST 8: Spanish language full flow ===")
r8 = chat("Hola", lang="es")
s8 = r8["session_id"]
print(f"  Welcome: {r8['message'][:100]}")
r8b = chat("Italy and Switzerland", s8, lang="es")
print(f"  Step: {r8b['step_number']}")
r8c = chat("Couple", s8, lang="es")
print(f"  Dates Q: {r8c['message'][:100]}")

print("\nAll tests complete!")
