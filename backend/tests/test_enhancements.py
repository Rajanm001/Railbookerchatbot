"""Quick test of the new enhancements."""
import urllib.request, json, time

BASE = 'http://127.0.0.1:8890/api/v1'

def post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(f'{BASE}{path}', data=data, headers={'Content-Type':'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=15).read())

passed = 0
failed = 0

def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name} -- {detail}")


print("\n=== GO BACK FEATURE ===")
r = post('/planner/chat', {'message': 'Hello'})
sid = r['session_id']
time.sleep(0.3)
r = post('/planner/chat', {'message': 'Italy', 'session_id': sid})
check("Step after Italy = 1 (single dest)", r['step_number'] == 1)
time.sleep(0.3)
r = post('/planner/chat', {'message': 'Continue', 'session_id': sid})
check("Continue -> step 2", r['step_number'] == 2)
time.sleep(0.3)
r = post('/planner/chat', {'message': 'go back', 'session_id': sid})
check("Go back -> step 1", r['step_number'] == 1)
check("Go back msg: destination", "where" in r['message'].lower() or "destination" in r['message'].lower())

# Go forward again and back from step 3
time.sleep(0.3)
r = post('/planner/chat', {'message': 'France', 'session_id': sid})
check("Step after France = 1 (single dest)", r['step_number'] == 1)
time.sleep(0.3)
r = post('/planner/chat', {'message': 'Continue', 'session_id': sid})
check("Continue -> step 2", r['step_number'] == 2)
time.sleep(0.3)
r = post('/planner/chat', {'message': '2 adults', 'session_id': sid})
check("Step after travellers = 3", r['step_number'] == 3)
time.sleep(0.3)
r = post('/planner/chat', {'message': 'previous', 'session_id': sid})
check("Previous -> step 2", r['step_number'] == 2)
check("Previous msg: traveller", "travelling" in r['message'].lower() or "traveller" in r['message'].lower())

print("\n=== ENHANCED TRAVELER PARSING ===")
time.sleep(0.5)
r = post('/planner/chat', {'message': 'Hi'})
sid2 = r['session_id']
time.sleep(0.3)
r = post('/planner/chat', {'message': 'Spain', 'session_id': sid2})
time.sleep(0.3)
r = post('/planner/chat', {'message': 'Continue', 'session_id': sid2})
time.sleep(0.3)
r = post('/planner/chat', {'message': '2 adults and 3 children', 'session_id': sid2})
check("2 adults + 3 children = family of 5", "family of 5" in r['message'].lower())

time.sleep(0.5)
r = post('/planner/chat', {'message': 'Hi'})
sid3 = r['session_id']
time.sleep(0.3)
r = post('/planner/chat', {'message': 'Italy', 'session_id': sid3})
time.sleep(0.3)
r = post('/planner/chat', {'message': 'Continue', 'session_id': sid3})
time.sleep(0.3)
r = post('/planner/chat', {'message': 'me and my mom', 'session_id': sid3})
check("Mom = family", "family" in r['message'].lower(), r['message'][:60])

time.sleep(0.5)
r = post('/planner/chat', {'message': 'Hi'})
sid4 = r['session_id']
time.sleep(0.3)
r = post('/planner/chat', {'message': 'Germany', 'session_id': sid4})
time.sleep(0.3)
r = post('/planner/chat', {'message': 'Continue', 'session_id': sid4})
time.sleep(0.3)
r = post('/planner/chat', {'message': 'on my own', 'session_id': sid4})
check("On my own = solo", "solo" in r['message'].lower(), r['message'][:60])

time.sleep(0.5)
r = post('/planner/chat', {'message': 'Hi'})
sid5 = r['session_id']
time.sleep(0.3)
r = post('/planner/chat', {'message': 'Austria', 'session_id': sid5})
time.sleep(0.3)
r = post('/planner/chat', {'message': 'Continue', 'session_id': sid5})
time.sleep(0.3)
r = post('/planner/chat', {'message': 'myself, my wife and our 2 kids', 'session_id': sid5})
check("Wife + 2 kids = family", "family" in r['message'].lower(), r['message'][:80])

print("\n=== RESET KEYWORD ===")
time.sleep(0.5)
r = post('/planner/chat', {'message': 'Hi'})
sid6 = r['session_id']
time.sleep(0.3)
r = post('/planner/chat', {'message': 'Italy', 'session_id': sid6})
time.sleep(0.3)
r = post('/planner/chat', {'message': 'Continue', 'session_id': sid6})
time.sleep(0.3)
r = post('/planner/chat', {'message': 'reset', 'session_id': sid6})
check("Reset keyword works", r['step_number'] == 1)

print(f"\n=== Results: {passed}/{passed+failed} passed ===")
