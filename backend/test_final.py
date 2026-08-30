"""Fast comprehensive test."""
import requests, json, time
BASE = 'http://localhost:8000/api/v1'

def unwrap(r):
    j = r.json(); return j.get('data', j)

count = [0]

def login(email, name):
    requests.post(f'{BASE}/auth/register', json={'email':email,'password':'demo1234','full_name':name,'role':'PATIENT'})
    lr = requests.post(f'{BASE}/auth/login', json={'email':email,'password':'demo1234'})
    return {'Authorization': f'Bearer {lr.json().get("access_token","")}'}

def std_ans(code):
    m = {'onset':'Suddenly','duration':'3 days','location':'Right side','severity':'5','character':'Sharp',
         'associated_symptoms':'Some swelling','aggravating':'Walking','relieving':'Rest','timing':'Constant',
         'radiation':'No','past_medical':'None','past_surgical':'None','medications':'None','allergies':'None',
         'family_history':'None','personal_history':'No smoking','review_of_systems':'No fever',
         'red_flag_inquiry':'No','other':'No'}
    return m.get(code, 'No issues')

def run_test(name, cc, bad_kw):
    t = time.time()
    print(f'\n--- {name} ---')
    h = login(f'{name.replace(" ","").lower()}@demo.medikiosk', name)
    requests.post(f'{BASE}/consent',json={'scope':['history'],'purpose':'t'},headers=h)
    s = requests.post(f'{BASE}/intake/start',json={'language':'en','mode':'STANDARD'},headers=h).json()['id']
    
    nq = unwrap(requests.get(f'{BASE}/intake/sessions/{s}/next-question',headers=h))
    q = nq['next_question']
    assert 'problem' in q['prompt'].lower() or 'today' in q['prompt'].lower()
    print(f'  Q1: {q["prompt"][:60]}')
    requests.post(f'{BASE}/intake/sessions/{s}/answer',json={'question_code':q['code'],'answer_text':cc,'source':'PATIENT_TOUCH'},headers=h)
    
    qcount = 1
    for i in range(16):
        nq = unwrap(requests.get(f'{BASE}/intake/sessions/{s}/next-question',headers=h))
        if nq.get('is_complete'): print(f'  [DONE at Q{qcount+1}]'); break
        q = nq['next_question']
        qcount += 1
        is_bad = any(w in q['prompt'].lower() for w in bad_kw)
        flag = ' !!!IRRELEVANT!!!' if is_bad else ''
        print(f'  Q{qcount} [{q["domain"]}]: {q["prompt"][:55]}{flag}')
        if is_bad:
            print(f'  FAIL: irrelevant question for {name}')
            return False
        requests.post(f'{BASE}/intake/sessions/{s}/answer',json={'question_code':q['code'],'answer_text':std_ans(q['code']),'source':'PATIENT_TOUCH'},headers=h)
    
    sub = unwrap(requests.post(f'{BASE}/intake/sessions/{s}/submit',json={},headers=h))
    elapsed = time.time() - t
    print(f'  Flags: {len(sub.get("red_flags",[]))} | Time: {elapsed:.0f}s | PASS')
    return True

results = []
results.append(run_test('Knee Pain', 'My knee has been hurting for three days after a cricket injury.', ['cough','sore throat','runny nose']))
results.append(run_test('Cold Cough', 'I have a cold and cough for the past week.', ['knee','joint','fracture']))
results.append(run_test('Headache', 'I have been having severe headaches for two weeks.', ['knee','cough','diarrhea']))
results.append(run_test('Stomach Pain', 'I have pain in my stomach for two days.', ['knee','cough','headache']))
results.append(run_test('Emergency', 'I have severe chest pain and cannot breathe properly.', ['knee']))

print(f'\n=== RESULTS: {sum(results)}/{len(results)} PASSED ===')
if not all(results):
    exit(1)
