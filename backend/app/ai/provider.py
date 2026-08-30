"""AI provider abstraction.

Mock provider always works. Real providers (openai, gemini, anthropic)
only activate when AI_MODE=live and a key is present.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Protocol

from app.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Clinical intake system prompt used by real AI providers
# ---------------------------------------------------------------------------
CLINICAL_INTAKE_SYSTEM_PROMPT = """You are Swasthya Setu's AI Clinical Intake Assistant. You collect structured patient history for a doctor. You are NOT a doctor. You do NOT diagnose, prescribe, or recommend treatment.

RULES:
1. Ask exactly ONE clear, simple, patient-friendly question at a time.
2. Your first question is always: "What problem are you having today?"
3. After the patient answers, ask the most clinically relevant follow-up based on their complaint and everything collected so far.
4. Never ask a question whose answer was already provided.
5. Never ask irrelevant questions. If the patient mentions knee pain, ask about knees — not about cough.
6. Use simple, empathetic language a non-medical person understands.
7. After about 15-16 questions, if sufficient information is collected, signal to finish early. 17 is the absolute maximum.
8. If you detect a potential emergency (severe chest pain with breathing difficulty, signs of stroke, loss of consciousness, severe uncontrolled bleeding), clearly tell the patient to seek urgent medical attention and flag it.
9. For AYUSH mode, also ask relevant Ayurvedic questions (Prakriti, Vikriti, Ahara, Vihara, Nidana, Samprapti) in the later questions.
10. Do NOT diagnose. Do NOT prescribe. Do NOT say "you probably have X".

RESPONSE FORMAT — return ONLY valid JSON with these keys:
{
  "question": "your question here",
  "category": "one of: onset|duration|location|severity|character|associated_symptoms|aggravating|relieving|timing|past_medical|past_surgical|medications|allergies|family_history|personal_history|review_of_systems|red_flag_inquiry|ayush|other",
  "reason": "brief internal reason (not shown to patient)",
  "clinical_data": {
    "key": "value extracted from patient's last answer"
  },
  "red_flag": false,
  "should_finish": false,
  "red_flag_message": null
}

clinical_data should capture structured information from the PATIENT'S LAST ANSWER. Keys may include: chief_complaint, duration, onset, location, severity, character, associated_symptoms, aggravating_factors, relieving_factors, timing, past_medical_history, past_surgical_history, medications, allergies, family_history, smoking, alcohol, fever, etc.

Only include clinical_data entries that you can extract from the patient's most recent answer. Do not fabricate information.
"""


class AIProvider(Protocol):
    name: str

    def summarise(self, *, structured: Dict[str, Any], documents: list, red_flags: list) -> Dict[str, Any]:
        ...

    def structure(self, *, free_text: str, language: str = "en") -> Dict[str, Any]:
        ...

    def generate_question(
        self,
        *,
        conversation_history: List[Dict[str, str]],
        collected_data: Dict[str, Any],
        question_count: int,
        chief_complaint: Optional[str],
        mode: str = "STANDARD",
        language: str = "en",
    ) -> Dict[str, Any]:
        ...


# ---------------------------------------------------------------------------
# Mock provider — deterministic adaptive questioning without real AI calls
# ---------------------------------------------------------------------------

# Complaint category detection keywords
_CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "musculoskeletal": ["knee", "joint", "back", "bone", "fracture", "sprain", "muscle", "ankle", "wrist", "shoulder", "hip", "leg", "arm", "spine", "neck pain", "hip"],
    "respiratory": ["cough", "cold", "breath", "asthma", "chest", "sore throat", "runny nose", "sneezing", "phlegm", "wheezing"],
    "neurological": ["headache", "migraine", "dizzy", "seizure", "numbness", "tingling", "weakness", "speech", "vision", "concussion"],
    "gastrointestinal": ["stomach", "abdomen", "belly", "nausea", "vomiting", "diarrhea", "constipation", "burning", "indigestion", "bloating", "appetite"],
    "cardiac": ["chest pain", "heart", "palpitation", "palpitations", "heartburn"],
    "ent": ["ear", "eye", "nose", "throat", "hearing", "tinnitus", "sinus"],
    "dermatological": ["skin", "rash", "itch", "acne", "eczema", "wound", "burn", "blister"],
    "general": ["fever", "tired", "fatigue", "weakness", "weight loss", "weight gain", "night sweats"],
}

# Per-category question templates — each is (category, question_en, question_hi)
_MUSCULOSKELETAL_QUESTIONS = [
    ("duration", "When did this problem start? How many days or weeks ago?", "यह समस्या कब शुरू हुई? कितने दिन या हफ्ते पहले?"),
    ("onset", "Did it begin after an injury, fall, or any physical activity?", "क्या यह किसी चोट, गिरने, या किसी शारीरिक गतिविधि के बाद शुरू हुआ?"),
    ("location", "Where exactly do you feel the pain? Can you point to it with your finger?", "दर्द ठीक कहाँ हो रहा है? क्या आप उंगली से दिखा सकते हैं?"),
    ("severity", "On a scale of 1 to 10, how bad is the pain right now?", "1 से 10 के पैमाने पर, अभी दर्द कितना है?"),
    ("character", "How would you describe the pain — is it sharp, a dull ache, burning, or throbbing?", "आप दर्द कैसा बताएंगे — तीखा, भारी, जलन वाला, या धड़कने वाला?"),
    ("associated_symptoms", "Is there any swelling, redness, or warmth around the area?", "क्या उस जगह पर सूजन, लालिमा, या गर्मी है?"),
    ("aggravating", "What makes the pain worse — walking, resting, or moving in a certain way?", "दर्द कब बढ़ता है — चलने में, आराम करने में, या किसी खास तरह से हिलने में?"),
    ("relieving", "What makes it feel better — rest, ice, heat, or any medicine?", "दर्द कब कम होता है — आराम करने से, बर्फ लगाने से, गर्म कपड़े से, या कोई दवा से?"),
    ("timing", "Is the pain constant, or does it come and go?", "दर्द लगातार रहता है या आता-जाता रहता है?"),
    ("past_medical", "Have you ever had this problem before, or any similar injury in the past?", "क्या आपको यह पहले भी हुआ है, या अतीत में कोई ऐसी चोट लगी है?"),
    ("medications", "Are you taking any medicines right now for the pain or for any other condition?", "क्या आप अभी कोई दवा ले रहे हैं दर्द के लिए या किसी और बीमारी के लिए?"),
    ("allergies", "Do you have any allergies to medicines?", "क्या आपको किसी दवा से एलर्जी है?"),
    ("personal_history", "Do you do any physical work or exercise regularly?", "क्या आप नियमित रूप से कोई शारीरिक काम या व्यायाम करते हैं?"),
    ("family_history", "Does anyone in your family have joint problems or bone issues?", "क्या आपके परिवार में किसी को जोड़ों या हड्डियों की समस्या है?"),
    ("review_of_systems", "Any fever, tiredness, or weight loss recently?", "क्या हाल में बुखार, थकान, या वजन घटा है?"),
]

_RESPIRATORY_QUESTIONS = [
    ("duration", "When did these symptoms start? How many days ago?", "ये लक्षण कब शुरू हुए? कितने दिन पहले?"),
    ("onset", "Did it start suddenly or gradually?", "क्या अचानक शुरू हुआ या धीरे-धीरे?"),
    ("severity", "On a scale of 1 to 10, how uncomfortable are you right now?", "1 से 10 के पैमाने पर, अभी आपको कितनी तकलीफ है?"),
    ("associated_symptoms", "Do you have a fever or chills?", "क्या आपको बुखार या कंपकंपी है?"),
    ("character", "Is your cough dry, or are you producing mucus or phlegm?", "क्या खांसी सूखी है, या कफ या बलगम आ रहा है?"),
    ("associated_symptoms", "Do you have a sore throat or runny nose?", "क्या गले में खराश या नाक बह रही है?"),
    ("associated_symptoms", "Are you having any difficulty breathing?", "क्या सांस लेने में कोई तकलीफ है?"),
    ("aggravating", "What makes the cough or breathing worse — lying down, cold air, or exertion?", "खांसी या सांस की तकलीफ कब बढ़ती है — लेटने से, ठंडी हवा से, या मेहनत से?"),
    ("relieving", "Does anything help — warm water, rest, or any medicine?", "कुछ राहत देता है — गर्म पानी, आराम, या कोई दवा?"),
    ("timing", "Is the cough worse at night, in the morning, or throughout the day?", "खांसी रात को, सुबह, या पूरे दिन ज्यादा है?"),
    ("past_medical", "Have you had this kind of cold or cough before? Do you have asthma or any lung problem?", "क्या आपको पहले भी ऐसी सर्दी-खांसी हुई है? क्या दमा या कोई फेफड़ों की बीमारी है?"),
    ("personal_history", "Do you smoke or live with someone who smokes?", "क्या आप धूम्रपान करते हैं या कोई धूम्रपान करने वाले के साथ रहते हैं?"),
    ("medications", "Are you taking any medicines currently?", "क्या आप अभी कोई दवा ले रहे हैं?"),
    ("allergies", "Do you have any allergies?", "क्या आपको कोई एलर्जी है?"),
    ("family_history", "Does anyone in your family have asthma or breathing problems?", "क्या आपके परिवार में किसी को दमा या सांस की बीमारी है?"),
]

_NEUROLOGICAL_QUESTIONS = [
    ("duration", "When did this start? How long have you been having these symptoms?", "यह कब शुरू हुआ? कितने समय से ये लक्षण हैं?"),
    ("onset", "Did it start suddenly or come on gradually?", "क्या अचानक शुरू हुआ या धीरे-धीरे बढ़ा?"),
    ("location", "Where exactly is the pain or discomfort? Is it on one side or both?", "दर्द या तकलीफ ठीक कहाँ है? एक तरफ है या दोनों तरफ?"),
    ("severity", "On a scale of 1 to 10, how severe is it?", "1 से 10 के पैमाने पर, कितना गंभीर है?"),
    ("character", "Is it a throbbing pain, a tight band-like feeling, or something else?", "क्या यह धड़कने वाला दर्द है, कसी हुई पट्टी जैसा, या कुछ और?"),
    ("associated_symptoms", "Do you feel nauseous, or have you vomited?", "क्या जी मिचलाता है या उल्टी हुई है?"),
    ("associated_symptoms", "Are you sensitive to light or noise?", "क्या रोशनी या शोर से तकलीफ होती है?"),
    ("aggravating", "What makes it worse — movement, light, stress, or certain foods?", "दर्द कब बढ़ता है — हिलने से, रोशनी से, तनाव से, या किसी खाने से?"),
    ("relieving", "Does resting in a dark quiet room or taking any medicine help?", "क्या अंधेरे और शांत कमरे में आराम करने या कोई दवा लेने से फायदा होता है?"),
    ("timing", "Is it constant, or does it come in episodes?", "क्या यह लगातार है या उठने-बैठने से होता है?"),
    ("associated_symptoms", "Any numbness, tingling, weakness in any part of your body?", "क्या शरीर के किसी हिस्से में सुन्नता, झनझनाहट, या कमजोरी है?"),
    ("past_medical", "Have you had headaches or similar episodes before? Any head injury?", "क्या आपको पहले भी सिरदर्द या ऐसे दौरे पड़े हैं? कोई सिर की चोट?"),
    ("medications", "Are you taking any medicines?", "क्या आप कोई दवा ले रहे हैं?"),
    ("allergies", "Do you have any allergies to medicines?", "क्या आपको किसी दवा से एलर्जी है?"),
    ("family_history", "Does anyone in your family have migraines or neurological conditions?", "क्या आपके परिवार में किसी को माइग्रेन या न्यूरोलॉजिकल बीमारी है?"),
]

_GASTROINTESTINAL_QUESTIONS = [
    ("duration", "When did the stomach problem start? How many days ago?", "पेट की समस्या कब शुरू हुई? कितने दिन पहले?"),
    ("location", "Where exactly in your abdomen do you feel the pain — upper, lower, left, or right?", "पेट में दर्द ठीक कहाँ है — ऊपर, नीचे, बाएं, या दाएं?"),
    ("severity", "On a scale of 1 to 10, how severe is the pain?", "1 से 10 के पैमाने पर, दर्द कितना गंभीर है?"),
    ("character", "Is it a cramping pain, burning, or a sharp pain?", "क्या यह मरोड़ वाला दर्द है, जलन वाला, या तीखा?"),
    ("associated_symptoms", "Have you had nausea or vomiting?", "क्या जी मिचलाया या उल्टी हुई?"),
    ("associated_symptoms", "Any changes in your bowel movements — diarrhea or constipation?", "क्या पेट साफ होने में कोई बदलाव है — दस्त या कब्ज?"),
    ("aggravating", "What makes the pain worse — eating, lying down, or certain foods?", "दर्द कब बढ़ता है — खाना खाने से, लेटने से, या किसी खास खाने से?"),
    ("relieving", "Does anything help — antacids, warm water, or passing motion?", "कुछ राहत देता है — एंटासिड, गर्म पानी, या पेट साफ होने से?"),
    ("timing", "Is the pain constant or does it come and go? Is it worse after meals?", "दर्द लगातार है या आता-जाता है? क्या खाने के बाद ज्यादा होता है?"),
    ("past_medical", "Have you had any stomach problems before — ulcers, acidity, or gallstones?", "क्या आपको पहले भी पेट की कोई समस्या हुई है — अल्सर, एसिडिटी, या पित्त की पथरी?"),
    ("personal_history", "What does your typical daily diet look like? Do you eat spicy or oily food often?", "आपका रोज़ का खाना कैसा है? क्या मसालेदार या तेल वाला खाना ज्यादा खाते हैं?"),
    ("medications", "Are you taking any medicines, including antacids or painkillers?", "क्या आप कोई दवा ले रहे हैं, एंटासिड या दर्द की दवा सहित?"),
    ("allergies", "Do you have any food or medicine allergies?", "क्या आपको किसी खाने या दवा से एलर्जी है?"),
    ("associated_symptoms", "Any blood in your stool or vomit?", "क्या पेट साफ करते समय या उल्टी में खून आया है?"),
    ("family_history", "Does anyone in your family have stomach ulcers or digestive problems?", "क्या आपके परिवार में किसी को पेट का अल्सर या पाचन की समस्या है?"),
]

_CARDIAC_QUESTIONS = [
    ("duration", "When did this start? How long have you been feeling this way?", "यह कब शुरू हुआ? कितने समय से ऐसा महसूस हो रहा है?"),
    ("location", "Where exactly in your chest do you feel it?", "छाती में ठीक कहाँ महसूस हो रहा है?"),
    ("severity", "On a scale of 1 to 10, how severe is it?", "1 से 10 के पैमाने पर, कितना गंभीर है?"),
    ("character", "What does it feel like — pressure, tightness, burning, or sharp?", "कैसा लगता है — दबाव, कसाव, जलन, या तीखा?"),
    ("radiation", "Does the pain spread to your arm, jaw, or back?", "क्या दर्द बांह, जबड़े, या पीठ में फैलता है?"),
    ("associated_symptoms", "Are you sweating, feeling dizzy, or short of breath?", "क्या पसीना आ रहा है, चक्कर आ रहे हैं, या सांस छोटी पड़ रही है?"),
    ("aggravating", "What makes it worse — walking, climbing stairs, or stress?", "दर्द कब बढ़ता है — चलने में, सीढ़ी चढ़ने में, या तनाव से?"),
    ("relieving", "Does rest or any medicine make it better?", "क्या आराम करने या कोई दवा लेने से फायदा होता है?"),
    ("timing", "Is it constant or does it come and go?", "क्या यह लगातार है या आता-जाता है?"),
    ("past_medical", "Do you have diabetes, high blood pressure, or high cholesterol?", "क्या आपको मधुमेह, उच्च रक्तचाप, या बढ़ा कोलेस्ट्रॉल है?"),
    ("past_surgical", "Have you had any heart procedures or surgeries before?", "क्या आपके दिल की कोई जांच या सर्जरी हुई है?"),
    ("medications", "What medicines are you currently taking?", "आप अभी कौन सी दवाइयाँ ले रहे हैं?"),
    ("family_history", "Did anyone in your family have a heart attack or heart disease at a young age?", "क्या आपके परिवार में किसी को कम उम्र में दिल का दौरा या दिल की बीमारी हुई?"),
    ("personal_history", "Do you smoke? How is your diet and exercise?", "क्या धूम्रपान करते हैं? खान-पान और व्यायाम कैसा है?"),
    ("associated_symptoms", "Any swelling in your legs or ankles?", "क्या पैरों या टखनों में सूजन है?"),
]

_GENERAL_QUESTIONS = [
    ("duration", "How long have you been feeling this way? When did it start?", "आप कितने समय से ऐसा महसूस कर रहे हैं? कब शुरू हुआ?"),
    ("severity", "On a scale of 1 to 10, how would you rate your discomfort?", "1 से 10 के पैमाने पर, आप अपनी तकलीफ को कितना आंकेंगे?"),
    ("associated_symptoms", "Do you have any other symptoms along with this — fever, body ache, or tiredness?", "क्या इसके साथ कोई और लक्षण हैं — बुखार, शरीर दर्द, या थकान?"),
    ("onset", "Did it start suddenly or has it been building up?", "क्या अचानक शुरू हुआ या धीरे-धीरे बढ़ा?"),
    ("aggravating", "What makes it worse?", "क्या चीजें बदतर बनाती हैं?"),
    ("relieving", "What makes you feel better?", "क्या आपको बेहतर महसूस कराता है?"),
    ("timing", "Is it constant or does it come and go?", "क्या यह लगातार है या आता-जाता है?"),
    ("past_medical", "Do you have any known medical conditions — diabetes, blood pressure, thyroid?", "क्या आपको कोई ज्ञात बीमारी है — मधुमेह, ब्लड प्रेशर, थायरॉयड?"),
    ("past_surgical", "Have you had any surgeries or hospital stays in the past?", "क्या आपकी कोई सर्जरी या अस्पताल में भर्ती हुई है?"),
    ("medications", "What medicines are you currently taking?", "आप अभी कौन सी दवाइयाँ ले रहे हैं?"),
    ("allergies", "Do you have any allergies to medicines or food?", "क्या आपको किसी दवा या खाने से एलर्जी है?"),
    ("personal_history", "Do you smoke or drink alcohol?", "क्या धूम्रपान या शराब पीते हैं?"),
    ("family_history", "Any important medical conditions in your family?", "क्या आपके परिवार में कोई महत्वपूर्ण बीमारी है?"),
    ("review_of_systems", "Any weight loss, night sweats, or fatigue recently?", "क्या हाल में वजन घटा, रात को पसीना आया, या थकान है?"),
]

# Map category -> question list
_CATEGORY_QUESTIONS: Dict[str, list] = {
    "musculoskeletal": _MUSCULOSKELETAL_QUESTIONS,
    "respiratory": _RESPIRATORY_QUESTIONS,
    "neurological": _NEUROLOGICAL_QUESTIONS,
    "gastrointestinal": _GASTROINTESTINAL_QUESTIONS,
    "cardiac": _CARDIAC_QUESTIONS,
    "general": _GENERAL_QUESTIONS,
}

# AYUSH questions for the end of the interview
_AYUSH_QUESTIONS = [
    ("ayush", "In Ayurveda, we try to understand your body constitution. Do you tend to feel cold more often, or do you feel hot easily?", "आयुर्वेद में हम आपके शरीर के प्रकार को समझते हैं। क्या आपको ज्यादा ठंड लगती है या ज्यादा गर्मी?"),
    ("ayush", "How would you describe your appetite — good, moderate, or poor?", "आपकी भूख कैसी है — अच्छी, मध्यम, या कम?"),
    ("ayush", "How is your sleep pattern? Do you sleep well or have trouble sleeping?", "आपकी नींद कैसी है? अच्छी नींद आती है या नींद न आने की समस्या है?"),
    ("ayush", "How would you describe your body build — lean, medium, or well-built?", "आपका शरीर कैसा है — दुबला, मध्यम, या अच्छा गठन?"),
    ("ayush", "What is your typical daily diet like? Vegetarian, non-vegetarian, or mixed?", "आपका रोज़ का खाना कैसा है — शाकाहारी, मांसाहारी, या मिश्रित?"),
]


def _classify_complaint(text: str) -> str:
    """Classify a chief complaint into a clinical category."""
    t = text.lower()
    # Check each category's keywords
    best_cat = "general"
    best_score = 0
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in t)
        if score > best_score:
            best_score = score
            best_cat = cat
    return best_cat


def _extract_clinical_data_from_answer(category: str, question_category: str, answer: str) -> Dict[str, Any]:
    """Extract structured clinical data from a patient answer based on the question category."""
    data: Dict[str, Any] = {}
    a = answer.lower().strip()

    if question_category == "duration":
        data["duration"] = answer.strip()
    elif question_category == "onset":
        data["onset"] = answer.strip()
    elif question_category == "location":
        data["location"] = answer.strip()
    elif question_category == "severity":
        # Try to extract a number
        import re
        nums = re.findall(r'\d+', a)
        if nums:
            data["severity"] = nums[0]
        else:
            data["severity"] = answer.strip()
    elif question_category == "character":
        data["character"] = answer.strip()
    elif question_category == "associated_symptoms":
        data["associated_symptoms"] = answer.strip()
    elif question_category == "aggravating":
        data["aggravating_factors"] = answer.strip()
    elif question_category == "relieving":
        data["relieving_factors"] = answer.strip()
    elif question_category == "timing":
        data["timing"] = answer.strip()
    elif question_category == "past_medical":
        data["past_medical_history"] = answer.strip()
    elif question_category == "past_surgical":
        data["past_surgical_history"] = answer.strip()
    elif question_category == "medications":
        data["medications"] = answer.strip()
    elif question_category == "allergies":
        data["allergies"] = answer.strip()
    elif question_category == "family_history":
        data["family_history"] = answer.strip()
    elif question_category == "personal_history":
        data["personal_history"] = answer.strip()
    elif question_category == "review_of_systems":
        data["review_of_systems"] = answer.strip()
    elif question_category == "ayush":
        data["ayush"] = answer.strip()

    return data


class MockAIProvider:
    name = "mock"

    def generate_question(
        self,
        *,
        conversation_history: List[Dict[str, str]],
        collected_data: Dict[str, Any],
        question_count: int,
        chief_complaint: Optional[str],
        mode: str = "STANDARD",
        language: str = "en",
    ) -> Dict[str, Any]:
        """Generate the next question using deterministic adaptive logic."""
        MAX_QUESTIONS = 17
        AYUSH_START = 14  # Start asking AYUSH questions at question 14

        # Check if we should finish
        if question_count >= MAX_QUESTIONS:
            return {
                "question": "",
                "category": "complete",
                "reason": "Maximum question limit reached",
                "clinical_data": {},
                "red_flag": False,
                "should_finish": True,
                "red_flag_message": None,
            }

        # For the very first call (no conversation yet), return the fixed chief complaint question
        if not conversation_history:
            q_hi = "आज आपको क्या समस्या है? डॉक्टर के पास किस बात से आए हैं?"
            q_en = "What problem are you having today? Why have you come to the doctor?"
            return {
                "question": q_hi if language == "hi" else q_en,
                "category": "chief_complaint",
                "reason": "Always start with chief complaint",
                "clinical_data": {},
                "red_flag": False,
                "should_finish": False,
                "red_flag_message": None,
            }

        # Get the chief complaint and classify it
        cc = chief_complaint or ""
        category = _classify_complaint(cc)
        logger.debug("AI generate: cc=%r, category=%s, q_count=%d, hist_len=%d", cc, category, question_count, len(conversation_history))

        # Determine what information we've already collected
        collected_categories = set()
        for entry in conversation_history:
            if entry.get("role") == "assistant":
                cat = entry.get("category")
                if cat and cat not in ("chief_complaint", "complete", "other"):
                    collected_categories.add(cat)
            elif entry.get("role") == "patient":
                if entry == conversation_history[0]:
                    collected_categories.add("chief_complaint")
        for key in collected_data:
            collected_categories.add(key)

        # Build the question pool for the current category
        cat_questions = _CATEGORY_QUESTIONS.get(category, _GENERAL_QUESTIONS)

        # Find the next unanswered question from the category-specific pool
        next_q = None
        for qc, qe, qh in cat_questions:
            if qc not in collected_categories:
                next_q = (qc, qe, qh)
                collected_categories.add(qc)
                break

        # If all category questions are done, try general questions
        if not next_q:
            for qc, qe, qh in _GENERAL_QUESTIONS:
                if qc not in collected_categories:
                    next_q = (qc, qe, qh)
                    collected_categories.add(qc)
                    break

        # AYUSH questions if in AYUSH mode
        if not next_q and mode.upper() == "AYUSH":
            for qc, qe, qh in _AYUSH_QUESTIONS:
                if qc not in collected_categories:
                    next_q = (qc, qe, qh)
                    collected_categories.add(qc)
                    break

        # If nothing left, finish
        if not next_q:
            return {
                "question": "",
                "category": "complete",
                "reason": "All relevant questions have been asked",
                "clinical_data": {},
                "red_flag": False,
                "should_finish": True,
                "red_flag_message": None,
            }

        qc, qe, qh = next_q
        question_text = qh if language == "hi" else qe

        # Simple red-flag detection for the answer we just received
        red_flag = False
        red_flag_message = None
        if conversation_history:
            last_patient = ""
            for entry in reversed(conversation_history):
                if entry.get("role") == "patient":
                    last_patient = entry.get("content", "").lower()
                    break

            emergency_keywords = [
                ("chest", ["breath", "shortness", "sweating", "dizzy"]),
                ("unconscious", []),
                ("seizure", []),
                ("stroke", []),
                ("bleeding", ["uncontrolled", "severe", "vomiting blood"]),
            ]
            for trigger, associated in emergency_keywords:
                if trigger in last_patient:
                    if not associated or any(a in last_patient for a in associated):
                        red_flag = True
                        red_flag_message = f"Potentially urgent: {last_patient[:100]}. Please wait for immediate clinical assessment."
                        break

            # High severity detection
            import re
            nums = re.findall(r'\b(\d+)\b', last_patient)
            for n in nums:
                try:
                    if int(n) >= 9:
                        red_flag = True
                        red_flag_message = "Pain reported as very severe (9-10/10). Clinician review will be prioritised."
                        break
                except ValueError:
                    pass

        return {
            "question": question_text,
            "category": qc,
            "reason": f"Follow-up for {category} complaint, category: {qc}",
            "clinical_data": _extract_clinical_data_from_answer(category, qc, conversation_history[-1].get("content", "") if conversation_history else ""),
            "red_flag": red_flag,
            "should_finish": False,
            "red_flag_message": red_flag_message,
        }

    def summarise(self, *, structured: Dict[str, Any], documents: list, red_flags: list) -> Dict[str, Any]:
        return {
            "summary_text": _build_prose_summary(structured, documents, red_flags),
            "structured": structured,
            "is_ai_generated": False,
            "provider": self.name,
        }

    def structure(self, *, free_text: str, language: str = "en") -> Dict[str, Any]:
        text = free_text.lower()
        out: Dict[str, Any] = {"symptoms": [], "duration": None, "severity": None, "suggested_domain": "HPI"}
        if "chest" in text:
            out["symptoms"].append("chest pain")
        if "breath" in text or "dyspnea" in text:
            out["symptoms"].append("breathlessness")
        if "head" in text or "headache" in text:
            out["symptoms"].append("headache")
        if "fever" in text:
            out["symptoms"].append("fever")
        if "week" in text:
            out["duration"] = "weeks"
        if "day" in text:
            out["duration"] = "days"
        return out


class OpenAIProvider:
    name = "openai"

    def __init__(self) -> None:
        self._client = None
        if get_settings().openai_api_key:
            try:
                from openai import OpenAI  # type: ignore
                self._client = OpenAI(api_key=get_settings().openai_api_key)
            except Exception as exc:  # noqa: BLE001
                logger.warning("OpenAI client init failed: %s", exc)

    def generate_question(
        self,
        *,
        conversation_history: List[Dict[str, str]],
        collected_data: Dict[str, Any],
        question_count: int,
        chief_complaint: Optional[str],
        mode: str = "STANDARD",
        language: str = "en",
    ) -> Dict[str, Any]:
        if not self._client:
            return MockAIProvider().generate_question(
                conversation_history=conversation_history,
                collected_data=collected_data,
                question_count=question_count,
                chief_complaint=chief_complaint,
                mode=mode,
                language=language,
            )

        # Build the conversation context for the AI
        messages = [{"role": "system", "content": CLINICAL_INTAKE_SYSTEM_PROMPT}]

        # Add context about the current state
        context = f"Question count: {question_count}/17\nMode: {mode}\nLanguage: {language}\n"
        if chief_complaint:
            context += f"Chief complaint: {chief_complaint}\n"
        if collected_data:
            context += f"Collected clinical data so far: {json.dumps(collected_data)}\n"
        context += "\nBased on the conversation below, generate the NEXT single most clinically relevant question."

        # Add conversation history
        for entry in conversation_history:
            role = "assistant" if entry["role"] == "assistant" else "user"
            messages.append({"role": role, "content": entry["content"]})

        messages.append({"role": "user", "content": context})

        try:
            r = self._client.chat.completions.create(
                model=get_settings().openai_model or "gpt-4o-mini",
                temperature=0.3,
                response_format={"type": "json_object"},
                messages=messages,
                max_tokens=500,
            )
            content = r.choices[0].message.content
            parsed = json.loads(content)
            # Ensure required fields
            parsed.setdefault("question", "")
            parsed.setdefault("category", "other")
            parsed.setdefault("reason", "")
            parsed.setdefault("clinical_data", {})
            parsed.setdefault("red_flag", False)
            parsed.setdefault("should_finish", question_count >= 17)
            parsed.setdefault("red_flag_message", None)
            return parsed
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenAI generate_question failed, falling back to mock: %s", exc)
            return MockAIProvider().generate_question(
                conversation_history=conversation_history,
                collected_data=collected_data,
                question_count=question_count,
                chief_complaint=chief_complaint,
                mode=mode,
                language=language,
            )

    def summarise(self, *, structured, documents, red_flags) -> Dict[str, Any]:
        if not self._client:
            return MockAIProvider().summarise(structured=structured, documents=documents, red_flags=red_flags)
        sys = (
            "You are a clinical documentation assistant. You NEVER diagnose or prescribe. "
            "Convert the provided structured patient history into a concise physician-ready draft. "
            "Return JSON with keys: summary_text (string) and structured (object)."
        )
        try:
            r = self._client.chat.completions.create(
                model=get_settings().openai_model or "gpt-4o-mini",
                temperature=0.1,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": sys},
                    {"role": "user", "content": json.dumps({"structured": structured, "documents": documents, "red_flags": red_flags})},
                ],
            )
            content = r.choices[0].message.content
            parsed = json.loads(content)
            return {
                "summary_text": parsed.get("summary_text") or _build_prose_summary(structured, documents, red_flags),
                "structured": parsed.get("structured") or structured,
                "is_ai_generated": True,
                "provider": self.name,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenAI summarise failed, falling back to mock: %s", exc)
            return MockAIProvider().summarise(structured=structured, documents=documents, red_flags=red_flags)

    def structure(self, *, free_text, language="en") -> Dict[str, Any]:
        return MockAIProvider().structure(free_text=free_text, language=language)


class GeminiProvider:
    name = "gemini"

    def __init__(self) -> None:
        self._client = None
        if get_settings().gemini_api_key:
            try:
                import google.generativeai as genai  # type: ignore
                genai.configure(api_key=get_settings().gemini_api_key)
                self._client = genai.GenerativeModel(
                    model_name="gemini-1.5-flash",
                    generation_config={"response_mime_type": "application/json"}
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Gemini client init failed: %s", exc)

    def generate_question(
        self,
        *,
        conversation_history: List[Dict[str, str]],
        collected_data: Dict[str, Any],
        question_count: int,
        chief_complaint: Optional[str],
        mode: str = "STANDARD",
        language: str = "en",
    ) -> Dict[str, Any]:
        if not self._client:
            return MockAIProvider().generate_question(
                conversation_history=conversation_history,
                collected_data=collected_data,
                question_count=question_count,
                chief_complaint=chief_complaint,
                mode=mode,
                language=language,
            )

        context = f"Question count: {question_count}/17\nMode: {mode}\nLanguage: {language}\n"
        if chief_complaint:
            context += f"Chief complaint: {chief_complaint}\n"
        if collected_data:
            context += f"Collected data: {json.dumps(collected_data)}\n"

        conv_text = "\n".join(
            f"{'AI' if e['role'] == 'assistant' else 'Patient'}: {e['content']}"
            for e in conversation_history
        )

        prompt = (
            f"{CLINICAL_INTAKE_SYSTEM_PROMPT}\n\n"
            f"{context}\n\n"
            f"Conversation so far:\n{conv_text}\n\n"
            f"Generate the NEXT single most clinically relevant question as JSON."
        )

        try:
            r = self._client.generate_content(prompt)
            parsed = json.loads(r.text)
            parsed.setdefault("question", "")
            parsed.setdefault("category", "other")
            parsed.setdefault("reason", "")
            parsed.setdefault("clinical_data", {})
            parsed.setdefault("red_flag", False)
            parsed.setdefault("should_finish", question_count >= 17)
            parsed.setdefault("red_flag_message", None)
            return parsed
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gemini generate_question failed, falling back to mock: %s", exc)
            return MockAIProvider().generate_question(
                conversation_history=conversation_history,
                collected_data=collected_data,
                question_count=question_count,
                chief_complaint=chief_complaint,
                mode=mode,
                language=language,
            )

    def summarise(self, *, structured, documents, red_flags) -> Dict[str, Any]:
        if not self._client:
            return MockAIProvider().summarise(structured=structured, documents=documents, red_flags=red_flags)
        prompt = (
            "You are a clinical documentation assistant. You NEVER diagnose or prescribe. "
            "Convert the provided structured patient history into a concise physician-ready draft. "
            "Return JSON with keys: summary_text (string) and structured (object). "
            f"Data: {json.dumps({'structured': structured, 'documents': documents, 'red_flags': red_flags})}"
        )
        try:
            r = self._client.generate_content(prompt)
            parsed = json.loads(r.text)
            return {
                "summary_text": parsed.get("summary_text") or _build_prose_summary(structured, documents, red_flags),
                "structured": parsed.get("structured") or structured,
                "is_ai_generated": True,
                "provider": self.name,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gemini summarise failed, falling back to mock: %s", exc)
            return MockAIProvider().summarise(structured=structured, documents=documents, red_flags=red_flags)

    def structure(self, *, free_text, language="en") -> Dict[str, Any]:
        return MockAIProvider().structure(free_text=free_text, language=language)


class ClaudeProvider:
    name = "claude"

    def __init__(self) -> None:
        self._client = None
        if get_settings().claude_api_key:
            try:
                from anthropic import Anthropic  # type: ignore
                self._client = Anthropic(api_key=get_settings().claude_api_key)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Claude client init failed: %s", exc)

    def generate_question(
        self,
        *,
        conversation_history: List[Dict[str, str]],
        collected_data: Dict[str, Any],
        question_count: int,
        chief_complaint: Optional[str],
        mode: str = "STANDARD",
        language: str = "en",
    ) -> Dict[str, Any]:
        if not self._client:
            return MockAIProvider().generate_question(
                conversation_history=conversation_history,
                collected_data=collected_data,
                question_count=question_count,
                chief_complaint=chief_complaint,
                mode=mode,
                language=language,
            )

        context = f"Question count: {question_count}/17\nMode: {mode}\nLanguage: {language}\n"
        if chief_complaint:
            context += f"Chief complaint: {chief_complaint}\n"
        if collected_data:
            context += f"Collected data: {json.dumps(collected_data)}\n"

        conv_text = "\n".join(
            f"{'AI' if e['role'] == 'assistant' else 'Patient'}: {e['content']}"
            for e in conversation_history
        )

        user_msg = (
            f"{context}\n\n"
            f"Conversation so far:\n{conv_text}\n\n"
            f"Generate the NEXT single most clinically relevant question as JSON."
        )

        try:
            r = self._client.messages.create(
                model=get_settings().claude_model or "claude-3-5-sonnet-20240620",
                max_tokens=500,
                system=CLINICAL_INTAKE_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            )
            content = r.content[0].text
            parsed = json.loads(content)
            parsed.setdefault("question", "")
            parsed.setdefault("category", "other")
            parsed.setdefault("reason", "")
            parsed.setdefault("clinical_data", {})
            parsed.setdefault("red_flag", False)
            parsed.setdefault("should_finish", question_count >= 17)
            parsed.setdefault("red_flag_message", None)
            return parsed
        except Exception as exc:  # noqa: BLE001
            logger.warning("Claude generate_question failed, falling back to mock: %s", exc)
            return MockAIProvider().generate_question(
                conversation_history=conversation_history,
                collected_data=collected_data,
                question_count=question_count,
                chief_complaint=chief_complaint,
                mode=mode,
                language=language,
            )

    def summarise(self, *, structured, documents, red_flags) -> Dict[str, Any]:
        if not self._client:
            return MockAIProvider().summarise(structured=structured, documents=documents, red_flags=red_flags)
        sys = (
            "You are a clinical documentation assistant. You NEVER diagnose or prescribe. "
            "Convert the provided structured patient history into a concise physician-ready draft. "
            "Return a JSON object with keys: summary_text (string) and structured (object)."
        )
        try:
            r = self._client.messages.create(
                model=get_settings().claude_model or "claude-3-5-sonnet-20240620",
                max_tokens=2000,
                system=sys,
                messages=[
                    {"role": "user", "content": json.dumps({"structured": structured, "documents": documents, "red_flags": red_flags})},
                ],
            )
            content = r.content[0].text
            parsed = json.loads(content)
            return {
                "summary_text": parsed.get("summary_text") or _build_prose_summary(structured, documents, red_flags),
                "structured": parsed.get("structured") or structured,
                "is_ai_generated": True,
                "provider": self.name,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("Claude summarise failed, falling back to mock: %s", exc)
            return MockAIProvider().summarise(structured=structured, documents=documents, red_flags=red_flags)

    def structure(self, *, free_text, language="en") -> Dict[str, Any]:
        return MockAIProvider().structure(free_text=free_text, language=language)


def get_ai_provider() -> AIProvider:
    settings = get_settings()
    if settings.ai_mode == "live":
        provider_name = settings.ai_provider.lower()
        if provider_name == "openai":
            return OpenAIProvider()
        if provider_name == "gemini":
            return GeminiProvider()
        if provider_name == "claude":
            return ClaudeProvider()
    return MockAIProvider()


def _build_prose_summary(structured: Dict[str, Any], documents: list, red_flags: list) -> str:
    """Deterministic, safe summary generator used by the mock provider."""
    cc = structured.get("chief_complaint") or "Not recorded"
    hpi = structured.get("hpi", {}) or {}
    pmh = structured.get("past_medical_history") or []
    psh = structured.get("past_surgical_history") or []
    drug = structured.get("drug_history") or structured.get("current_medications") or []
    allergy = structured.get("allergies") or []
    family = structured.get("family_history") or []
    personal = structured.get("personal_history", {}) or {}
    ros = structured.get("review_of_systems", {}) or {}
    ayush = structured.get("ayush") or {}

    def _line(items):
        if isinstance(items, list):
            return ", ".join([str(x) for x in items if x]) or "None recorded"
        if isinstance(items, dict):
            bits = [f"{k}: {v}" for k, v in items.items() if v]
            return "\n".join(bits) or "None recorded"
        return str(items) if items else "None recorded"

    sections = [
        ("CHIEF COMPLAINT", cc),
        ("HISTORY OF PRESENT ILLNESS", _format_hpi(hpi)),
        ("PAST MEDICAL HISTORY", _line(pmh)),
        ("PAST SURGICAL HISTORY", _line(psh)),
        ("DRUG HISTORY / CURRENT MEDICATIONS", _line(drug)),
        ("ALLERGIES", _line(allergy)),
        ("FAMILY HISTORY", _line(family)),
        ("PERSONAL HISTORY", _line(personal)),
        ("REVIEW OF SYSTEMS", _line(ros)),
        ("PRIOR INVESTIGATIONS", _line(structured.get("prior_investigations", []))),
        ("DOCUMENT HISTORY", ", ".join(d.get("filename", "?") for d in documents) or "None"),
    ]
    if ayush:
        sections.append(("AYUSH / DASHAVIDHA PARIKSHA", _format_ayush(ayush)))

    if red_flags:
        sections.append(("POTENTIAL PRIORITY FLAGS", "\n".join(f"• {r['message']}" for r in red_flags)))

    out: list[str] = []
    for title, body in sections:
        out.append(title)
        out.append("-" * len(title))
        out.append(body or "Not recorded")
        out.append("")
    return "\n".join(out).strip()


def _format_hpi(hpi: dict) -> str:
    if not hpi:
        return "Not recorded"
    lines: list[str] = []
    for key in [
        "onset", "duration", "location", "character", "severity", "radiation",
        "associated_symptoms", "aggravating", "relieving", "timing",
    ]:
        v = hpi.get(key) or hpi.get(key.upper()) or hpi.get(key.lower())
        if v not in (None, "", []):
            if isinstance(v, list):
                v = ", ".join(map(str, v))
            lines.append(f"  {key.replace('_', ' ').title()}: {v}")
    return "\n".join(lines) or "Not recorded"


def _format_ayush(ayush: dict) -> str:
    lines: list[str] = []
    order = [
        "prakriti", "vikriti", "sara", "samhanana", "pramana", "satmya",
        "sattva", "ahara_shakti", "vyayama_shakti", "vaya",
    ]
    for k in order:
        v = ayush.get(k)
        if v:
            lines.append(f"  {k.replace('_', ' ').title()}: {v}")
    for k in ["ahara", "vihara", "nidana", "samprapti"]:
        v = ayush.get(k)
        if v:
            lines.append(f"  {k.title()}: {v}")
    return "\n".join(lines) or "Not recorded"
