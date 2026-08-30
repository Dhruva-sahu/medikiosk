"""Comprehensive test for AI-driven clinical intake with 5 scenarios."""
import requests
import json

BASE = "http://localhost:8000/api/v1"

def unwrap(r):
    j = r.json()
    return j.get("data", j)

def login(email, name="Test"):
    requests.post(f"{BASE}/auth/register", json={
        "email": email, "password": "demo1234", "full_name": name, "role": "PATIENT"
    })
    lr = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo1234"})
    token = lr.json().get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


def run_scenario(name, chief_complaint, expected_domain_keywords, bad_keywords=None):
    """Run a full intake scenario and validate."""
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"Chief complaint: {chief_complaint}")
    print(f"{'='*60}")

    headers = login(f"test_{name.lower().replace(' ','_')}@demo.medikiosk", f"Test {name}")
    requests.post(f"{BASE}/consent", json={"scope":["history","documents","ai_processing","summary"],"purpose":"test"}, headers=headers)
    start = requests.post(f"{BASE}/intake/start", json={"language":"en","mode":"STANDARD"}, headers=headers)
    sid = start.json()["id"]

    # Q1: chief complaint
    nq = unwrap(requests.get(f"{BASE}/intake/sessions/{sid}/next-question", headers=headers))
    q1 = nq["next_question"]
    assert "problem" in q1["prompt"].lower() or "today" in q1["prompt"].lower(), f"Q1 wrong: {q1['prompt']}"
    print(f"Q1 [{q1['domain']}]: {q1['prompt']}")

    requests.post(f"{BASE}/intake/sessions/{sid}/answer", json={
        "question_code": q1["code"], "answer_text": chief_complaint, "source": "PATIENT_TOUCH"
    }, headers=headers)

    # Standard answers for each domain
    std_answers = {
        "onset": "It started suddenly",
        "duration": "Three days ago",
        "location": "Right knee",
        "severity": "7 out of 10",
        "character": "Sharp pain",
        "associated_symptoms": "Some swelling",
        "aggravating": "Walking makes it worse",
        "relieving": "Rest helps",
        "timing": "Constant",
        "radiation": "No radiation",
        "past_medical": "No major conditions",
        "past_surgical": "No surgeries",
        "medications": "Paracetamol sometimes",
        "allergies": "No allergies",
        "family_history": "No family history",
        "personal_history": "No smoking, moderate exercise",
        "review_of_systems": "No fever or weight loss",
    }

    domains_served = []
    for i in range(16):
        nq = unwrap(requests.get(f"{BASE}/intake/sessions/{sid}/next-question", headers=headers))
        if nq.get("is_complete") or not nq.get("next_question"):
            print(f"  [COMPLETE after {i+1} additional questions]")
            break
        q = nq["next_question"]
        domains_served.append(q["domain"].lower())
        print(f"  Q{i+2} [{q['domain']}]: {q['prompt'][:80]}")

        # Check for irrelevant questions
        if bad_keywords:
            for bad in bad_keywords:
                assert bad not in q["prompt"].lower(), f"IRRELEVANT question '{bad}': {q['prompt']}"

        answer = std_answers.get(q["code"], "No issues")
        requests.post(f"{BASE}/intake/sessions/{sid}/answer", json={
            "question_code": q["code"], "answer_text": answer, "source": "PATIENT_TOUCH"
        }, headers=headers)

    # Check expected domains appeared
    found = [kw for kw in expected_domain_keywords if kw in " ".join(domains_served)]
    print(f"\n  Found expected domains: {found}")

    # Submit
    submit = unwrap(requests.post(f"{BASE}/intake/sessions/{sid}/submit", json={
        "final_chief_complaint": chief_complaint
    }, headers=headers))
    print(f"  Status: {submit.get('status')}, Priority: {submit.get('priority')}, Red flags: {len(submit.get('red_flags', []))}")

    # Verify
    state = unwrap(requests.get(f"{BASE}/intake/sessions/{sid}", headers=headers))
    hist = state.get("conversation_history", [])
    assert state.get("chief_complaint") == chief_complaint, f"chief_complaint mismatch"
    assistant_entries = [e for e in hist if e.get("role") == "assistant"]
    patient_entries = [e for e in hist if e.get("role") == "patient"]
    print(f"  History: {len(assistant_entries)} assistant, {len(patient_entries)} patient entries")
    print(f"  RESULT: PASS\n")
    return True


# Test 1: Knee pain (musculoskeletal)
run_scenario(
    "Knee Pain",
    "My knee has been hurting for three days after a cricket injury.",
    expected_domain_keywords=["onset", "severity", "location", "character"],
    bad_keywords=["cough", "sore throat", "runny nose"],
)

# Test 2: Cold/cough (respiratory)
run_scenario(
    "Cold and Cough",
    "I have a cold and cough for the past week.",
    expected_domain_keywords=["duration", "severity", "character", "associated"],
    bad_keywords=["knee", "joint", "fracture"],
)

# Test 3: Headache (neurological)
run_scenario(
    "Headache",
    "I have been having severe headaches for two weeks.",
    expected_domain_keywords=["duration", "severity", "character", "onset"],
    bad_keywords=["knee", "cough", "diarrhea"],
)

# Test 4: Stomach pain (gastrointestinal)
run_scenario(
    "Stomach Pain",
    "I have pain in my stomach for two days.",
    expected_domain_keywords=["duration", "severity", "location", "character"],
    bad_keywords=["knee", "cough", "headache"],
)

# Test 5: Emergency red flag
run_scenario(
    "Emergency Chest Pain",
    "I have severe chest pain and cannot breathe properly since this morning.",
    expected_domain_keywords=["severity", "duration"],
    bad_keywords=["knee"],
)

print(f"\n{'='*60}")
print("ALL 5 TEST SCENARIOS COMPLETED")
print(f"{'='*60}")
