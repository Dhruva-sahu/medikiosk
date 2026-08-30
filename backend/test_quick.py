"""Test AI-driven clinical intake - single scenario."""
import requests, json

BASE = "http://localhost:8000/api/v1"

def login(email, name="Test"):
    requests.post(f"{BASE}/auth/register", json={
        "email": email, "password": "demo1234", "full_name": name, "role": "PATIENT"
    })
    lr = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo1234"})
    token = lr.json().get("access_token", "")
    return {"Authorization": f"Bearer {token}"}

# Test: Knee Pain
print("=== TEST: Knee Pain ===")
h = login("kp_test@demo.medikiosk", "Knee Test")
requests.post(f"{BASE}/consent", json={"scope":["history","documents","ai_processing","summary"],"purpose":"test"}, headers=h)
start = requests.post(f"{BASE}/intake/start", json={"language":"en","mode":"STANDARD"}, headers=h)
sid = start.json()["id"]
print(f"Session: {sid[:8]}")

# Q1
def unwrap(r):
    j = r.json()
    return j.get("data", j)
nq = unwrap(requests.get(f"{BASE}/intake/sessions/{sid}/next-question", headers=h))
q = nq["next_question"]
print(f"Q1 [{q['domain']}]: {q['prompt']}")
assert "problem" in q["prompt"].lower() or "today" in q["prompt"].lower(), f"Q1 wrong: {q['prompt']}"

# Answer chief complaint
requests.post(f"{BASE}/intake/sessions/{sid}/answer", json={
    "question_code": q["code"], "answer_text": "My knee has been hurting for three days after a cricket injury", "source": "PATIENT_TOUCH"
}, headers=h)

# Q2 - should be musculoskeletal, NOT general
nq = unwrap(requests.get(f"{BASE}/intake/sessions/{sid}/next-question", headers=h))
q2 = nq["next_question"]
print(f"Q2 [{q2['domain']}]: {q2['prompt']}")
print(f"Q2 code: {q2['code']}")

# Verify this is a musculoskeletal question (duration/onset/location/severity/character)
assert q2["domain"] in ["DURATION", "ONSET", "LOCATION", "SEVERITY", "CHARACTER", "ASSOCIATED_SYMPTOMS", "AGGRAVATING", "RELIEVING", "TIMING"], \
    f"Q2 should be musculoskeletal-specific! Got: {q2['domain']}"

# Check conversation history
state = unwrap(requests.get(f"{BASE}/intake/sessions/{sid}", headers=h))
hist = state.get("conversation_history", [])
print(f"\nHistory ({len(hist)} entries):")
for e in hist:
    cat = e.get("category", "N/A")
    print(f"  {e['role']}: [{cat}] {e['content'][:60]}")

print(f"\nChief complaint: {state.get('chief_complaint')}")
print(f"\nRESULT: PASS - Musculoskeletal question correctly served")
