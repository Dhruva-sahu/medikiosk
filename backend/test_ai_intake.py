"""Test AI-driven clinical intake with multiple complaint scenarios."""
import requests
import json

BASE = "http://localhost:8000/api/v1"

def login(email="test.ai2@demo.medikiosk", password="demo1234", name="AI Test Patient 2"):
    reg = requests.post(f"{BASE}/auth/register", json={
        "email": email, "password": password, "full_name": name, "role": "PATIENT"
    })
    login_r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": password})
    data = login_r.json()
    token = data.get("data", {}).get("access_token") or data.get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


def run_scenario(name, chief_complaint, expected_keywords, bad_keywords=None, answers_override=None):
    """Run a full intake scenario and validate results."""
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"Chief complaint: {chief_complaint}")
    print(f"{'='*60}")

    headers = login()

    # Grant consent
    requests.post(f"{BASE}/consent", json={
        "scope": ["history", "documents", "ai_processing", "summary"],
        "purpose": "Test AI intake"
    }, headers=headers)

    # Start session
    start = requests.post(f"{BASE}/intake/start", json={"language": "en", "mode": "STANDARD"}, headers=headers)
    sd = start.json()
    sd = sd.get("data", sd)
    sid = sd["id"]
    print(f"Session: {sid[:8]}...")

    # Q1: always chief complaint
    nq = requests.get(f"{BASE}/intake/sessions/{sid}/next-question", headers=headers).json()
    nq = nq.get("data", nq)
    q1 = nq["next_question"]
    print(f"Q1 [{q1['domain']}]: {q1['prompt']}")
    assert "problem" in q1["prompt"].lower() or "today" in q1["prompt"].lower() or "samasya" in q1["prompt"].lower(), \
        f"Q1 should be chief complaint! Got: {q1['prompt']}"

    # Answer chief complaint
    requests.post(f"{BASE}/intake/sessions/{sid}/answer", json={
        "question_code": q1["code"], "answer_text": chief_complaint, "source": "PATIENT_TOUCH"
    }, headers=headers)

    # Default answers for each question type
    default_answers = {
        "duration": "It started 3 days ago",
        "onset": "It started suddenly",
        "location": "Right side of my body",
        "severity": "7 out of 10",
        "character": "Sharp, stabbing pain",
        "associated_symptoms": "Yes, some swelling and warmth",
        "aggravating": "It gets worse when I move or walk",
        "relieving": "Rest helps a little",
        "timing": "It is constant, not coming and going",
        "past_medical": "No major medical conditions",
        "past_surgical": "No surgeries",
        "medications": "I take paracetamol sometimes",
        "allergies": "No known allergies",
        "family_history": "No family history of similar problems",
        "personal_history": "I exercise regularly, no smoking",
        "review_of_systems": "No fever, no weight loss",
        "radiation": "No, the pain stays in one place",
        "red_flag_inquiry": "No emergency symptoms",
        "ayush": "I feel more cold than hot",
        "other": "No other concerns",
    }

    questions_asked = []
    domains_seen = []

    # Answer up to 16 more questions
    for i in range(16):
        nq = requests.get(f"{BASE}/intake/sessions/{sid}/next-question", headers=headers).json()
        nq = nq.get("data", nq)
        if nq.get("is_complete") or not nq.get("next_question"):
            print(f"  [COMPLETE after {i+1} additional questions]")
            break
        q = nq["next_question"]
        qtext = q["prompt"]
        domain = q["domain"]
        code = q["code"]
        questions_asked.append(qtext)
        domains_seen.append(domain)
        print(f"  Q{i+2} [{domain}]: {qtext}")

        # Check for irrelevant questions
        if bad_keywords:
            for bad in bad_keywords:
                assert bad not in qtext.lower(), f"Asked irrelevant question containing '{bad}': {qtext}"

        # Determine answer
        answer = default_answers.get(code, "No issues")

        requests.post(f"{BASE}/intake/sessions/{sid}/answer", json={
            "question_code": code, "answer_text": answer, "source": "PATIENT_TOUCH"
        }, headers=headers)
        print(f"    -> {answer[:50]}")

    # Verify relevant keywords appeared in questions
    all_q_text = " ".join(questions_asked).lower()
    found = [kw for kw in expected_keywords if kw in all_q_text]
    missing = [kw for kw in expected_keywords if kw not in all_q_text]
    print(f"\n  Expected keywords found: {found}")
    if missing:
        print(f"  WARNING - Missing keywords: {missing}")

    # Submit session
    submit = requests.post(f"{BASE}/intake/sessions/{sid}/submit", json={
        "final_chief_complaint": chief_complaint
    }, headers=headers)
    sd2 = submit.json().get("data", submit.json())
    print(f"\n  Submit status: {submit.status_code}")
    print(f"  Session status: {sd2.get('status')}")
    print(f"  Priority: {sd2.get('priority')}")
    print(f"  Red flags: {len(sd2.get('red_flags', []))}")

    # Check conversation history
    state = requests.get(f"{BASE}/intake/sessions/{sid}", headers=headers).json()
    state = state.get("data", state)
    hist = state.get("conversation_history", [])
    collected = state.get("collected_data", {})
    print(f"  History entries: {len(hist)}")
    print(f"  Collected data keys: {list(collected.keys())}")

    # Verify conversation structure
    assistant_entries = [e for e in hist if e.get("role") == "assistant"]
    patient_entries = [e for e in hist if e.get("role") == "patient"]
    print(f"  Assistant entries: {len(assistant_entries)}, Patient entries: {len(patient_entries)}")

    # Verify chief complaint is set
    assert state.get("chief_complaint") == chief_complaint, \
        f"Chief complaint not set! Got: {state.get('chief_complaint')}"

    print(f"\n  RESULT: PASS")
    return True


# Test 1: Knee pain (musculoskeletal)
run_scenario(
    "Knee Pain",
    "My knee has been hurting for three days after a cricket injury.",
    expected_keywords=["knee", "injury", "swelling", "pain"],
    bad_keywords=["cough", "sore throat", "runny nose", "phlegm"],
)

# Test 2: Cold/cough (respiratory)
run_scenario(
    "Cold and Cough",
    "I have a cold and cough for the past week.",
    expected_keywords=["fever", "cough", "breath", "throat"],
    bad_keywords=["knee", "joint", "fracture", "sprain"],
)

# Test 3: Headache (neurological)
run_scenario(
    "Headache",
    "I have been having severe headaches for two weeks.",
    expected_keywords=["headache", "light", "nausea"],
    bad_keywords=["knee", "cough", "diarrhea"],
)

# Test 4: Abdominal pain (gastrointestinal)
run_scenario(
    "Stomach Pain",
    "I have pain in my stomach for two days.",
    expected_keywords=["stomach", "eat", "bowel", "nausea"],
    bad_keywords=["knee", "cough", "headache"],
)

# Test 5: Emergency red flag
run_scenario(
    "Emergency - Chest Pain",
    "I have severe chest pain and cannot breathe properly.",
    expected_keywords=["chest", "breath"],
    bad_keywords=["knee", "cough"],
)

print(f"\n{'='*60}")
print("ALL 5 TEST SCENARIOS COMPLETED")
print(f"{'='*60}")
