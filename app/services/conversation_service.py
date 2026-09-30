import re
import uuid
from app.db.models import Call, Assessment, ConversationMessage, Patient
from app.services.triage_service import emergency_override, assess_burn

FIELDS = [
    "age",
    "cause_of_burn",
    "time_since_burn",
    "body_part_affected",
    "approximate_size",
    "blistering_or_skin_appearance",
    "pain_level",
    "circumferential",
    "smoke_or_enclosed_space_exposure",
]

QUESTIONS = {
    "cause_of_burn": "Burn kaise hua — garam paani/liquid, aag, garam object, chemical ya electrical?",
    "body_part_affected": "Burn body ke kis part par hai? Jaise haath, pair/foot, arm, face, etc.",
    "smoke_or_enclosed_space_exposure": "Kya burn ke time smoke ya band kamre mein exposure hua tha? Haan ya nahi bata sakte hain.",
    "time_since_burn": "Burn kab hua tha — abhi, kuch ghante pehle, ya kal?",
    "approximate_size": "Burn ka area aapki hatheli se chhota hai ya bada?",
    "blistering_or_skin_appearance": "Skin sirf laal hai ya blister/chhala bhi bana hai?",
    "pain_level": "Pain kaisa hai — mild, medium ya bahut zyada?",
    "circumferential": "Kya burn poore finger, haath, pair ya body part ke around hai? Haan ya nahi?",
}

WHO_FIRST_AID = (
    "Burn ko pehle safe tarike se cool karein: burning source se door ho jaayein, "
    "affected area ko cool running water se cool karein, aur agar clothing skin se "
    "chipki nahi hai to carefully remove karein. Ice, oil, paste, haldi ya raw cotton "
    "na lagayein aur blisters na phodein. Severe burn ya concerning symptoms mein "
    "medical care lein."
)


def uid(prefix):
    return prefix + "-" + uuid.uuid4().hex[:8].upper()


def new_call(db):
    call = Call(
        call_uid=uid("CALL"),
        condition="unknown",
        current_stage="IDENTIFY_CONDITION",
    )
    db.add(call)
    db.flush()
    db.add(Assessment(call_id=call.id))
    db.commit()
    db.refresh(call)
    return call


def add_message(db, call, role, message):
    db.add(
        ConversationMessage(
            call_id=call.id,
            role=role,
            message=message,
            input_type="text",
        )
    )


def normalize_hinglish(text):
    """
    Normalize common Roman-Hindi spelling variations without trying to
    rewrite the user's meaning.

    Examples:
        per / pair / paer / paerh  -> pair
        mei / mein / me             -> mein
        haan / haa                  -> haan
        nahin / nahi                -> nahi
    """
    t = text.lower().strip()
    replacements = [
        (r"\bmein\b", "mein"),
        (r"\bmei\b", "mein"),
        (r"\bme\b", "mein"),
        (r"\bmain\b", "mein"),
        (r"\bpaer\b", "pair"),
        (r"\bper\b", "pair"),
        (r"\bpair\b", "pair"),
        (r"\bpayr\b", "pair"),
        (r"\bpaerh\b", "pair"),
        (r"\bha\b", "haan"),
        (r"\bhaa\b", "haan"),
        (r"\bhan\b", "haan"),
        (r"\bnahin\b", "nahi"),
        (r"\bnhi\b", "nahi"),
        (r"\bnahi\b", "nahi"),
        (r"\bgya\b", "gaya"),
        (r"\bgayi\b", "gayi"),
        (r"\bgyi\b", "gayi"),
        (r"\bpe\b", "par"),
    ]
    for pattern, value in replacements:
        t = re.sub(pattern, value, t)
    t = re.sub(r"\s+", " ", t)
    return t


def is_yes(text):
    t = normalize_hinglish(text)
    return bool(
        re.fullmatch(
            r"(haan|ha|yes|yup|yep|true|bilkul|ji|ji haan)([ .!]*)",
            t,
        )
    )


def is_no(text):
    t = normalize_hinglish(text)
    return bool(re.fullmatch(r"(nahi|nahin|no|na|false)([ .!]*)", t))


def _contains_phrase(t, phrases):
    return any(re.search(r"(?<!\w)" + re.escape(p) + r"(?!\w)", t) for p in phrases)


def rule_extract(assessment, text, active_field=None):
    """
    Deterministic, high-recall extractor for common Hinglish phrases.

    It is deliberately allowed to extract multiple fields from one
    sentence. A known field is not overwritten by 'unknown'.
    """
    t = normalize_hinglish(text)

    # Direct answer to the currently asked yes/no field.
    if active_field == "smoke_or_enclosed_space_exposure":
        if is_yes(text):
            assessment.smoke_or_enclosed_space_exposure = "yes"
        elif is_no(text):
            assessment.smoke_or_enclosed_space_exposure = "no"

    if active_field == "circumferential":
        if is_yes(text):
            assessment.circumferential = "yes"
        elif is_no(text):
            assessment.circumferential = "no"

    if active_field == "blistering_or_skin_appearance":
        if _contains_phrase(t, ["blister", "chhala", "chhale", "chhala bana"]):
            assessment.blistering_or_skin_appearance = "blistering"
        elif _contains_phrase(t, ["red", "laal", "lal"]):
            assessment.blistering_or_skin_appearance = "redness only"

    if active_field == "pain_level":
        if _contains_phrase(
            t,
            ["bahut zyada", "bahut dard", "bohot dard", "severe", "extreme", "very bad"],
        ):
            assessment.pain_level = "severe"
        elif _contains_phrase(t, ["medium", "moderate", "theek thaak"]):
            assessment.pain_level = "moderate"
        elif _contains_phrase(t, ["mild", "thoda", "kam", "halka"]):
            assessment.pain_level = "mild"

    # Cause
    if assessment.cause_of_burn in (None, "", "unknown"):
        if _contains_phrase(
            t,
            ["garam paani", "garam pani", "hot water", "boiling water", "scald", "garam liquid", "hot liquid"],
        ):
            assessment.cause_of_burn = "hot liquid"
        elif _contains_phrase(t, ["aag", "fire", "flame", "chulha", "stove"]):
            assessment.cause_of_burn = "flame"
        elif _contains_phrase(t, ["chemical", "acid"]):
            assessment.cause_of_burn = "chemical"
        elif _contains_phrase(t, ["electric", "current", "wire", "bijli"]):
            assessment.cause_of_burn = "electrical"

    # Body part. Include common Roman-Hindi misspellings and contextual forms:
    # "per mein", "pair pe", "mere pair par", "foot me", etc.
    if assessment.body_part_affected in (None, "", "unknown"):
        body_map = {
            "hand": ["haath", "hath", "hand"],
            "face": ["face", "chehra", "chehre"],
            "leg": ["leg", "pair", "taang", "tang"],
            "arm": ["arm", "baazu", "bazu"],
            "foot": ["foot", "paon", "paanv", "pav"],
            "eye": ["eye", "aankh", "ankh"],
            "neck": ["neck", "gardan"],
            "chest": ["chest", "seena", "sina"],
        }
        # Prefer exact English body terms where there can be overlap.
        for part, words in body_map.items():
            if any(_contains_phrase(t, [word]) for word in words):
                assessment.body_part_affected = part
                break

    # Time
    if assessment.time_since_burn in (None, "", "unknown"):
        if _contains_phrase(
            t,
            [
                "just now",
                "abhi",
                "abhi hua",
                "abhi hua hai",
                "right now",
                "kuch der pehle",
                "thodi der pehle",
                "ghante pehle",
                "ghanta pehle",
                "hour ago",
                "hours ago",
                "kal",
                "yesterday",
            ],
        ):
            assessment.time_since_burn = text.strip()

    # Size
    if assessment.approximate_size in (None, "", "unknown"):
        if _contains_phrase(
            t,
            ["hatheli se chhota", "smaller than palm", "small", "chhota sa", "chota sa"],
        ):
            assessment.approximate_size = "smaller than palm"
        elif _contains_phrase(
            t,
            ["hatheli se bada", "larger than palm", "bigger than palm", "large", "bada", "bada area", "poora haath", "whole hand"],
        ):
            assessment.approximate_size = "larger than palm"

    # Skin appearance
    if assessment.blistering_or_skin_appearance in (None, "", "unknown"):
        if _contains_phrase(t, ["blister", "chhala", "chhale"]):
            assessment.blistering_or_skin_appearance = "blistering"
        elif _contains_phrase(t, ["red", "laal", "lal"]):
            assessment.blistering_or_skin_appearance = "redness only"

    # Pain
    if assessment.pain_level in (None, "", "unknown"):
        if _contains_phrase(
            t,
            ["bahut zyada", "bahut dard", "bohot dard", "zyada dard", "severe", "extreme", "very bad"],
        ):
            assessment.pain_level = "severe"
        elif _contains_phrase(t, ["medium", "moderate", "theek thaak"]):
            assessment.pain_level = "moderate"
        elif _contains_phrase(t, ["mild", "thoda", "kam", "halka"]):
            assessment.pain_level = "mild"

    # Circumferential, including explicit negative answers in ordinary sentences.
    if assessment.circumferential in (None, "", "unknown"):
        if _contains_phrase(t, ["poore haath", "poora haath", "poore pair", "poora pair", "around", "circumferential"]):
            assessment.circumferential = "yes"

    # Smoke exposure: don't interpret the assistant's question as evidence;
    # this parser only receives user messages.
    if assessment.smoke_or_enclosed_space_exposure in (None, "", "unknown"):
        if _contains_phrase(t, ["smoke", "dhuan", "dhuan tha", "band kamre", "enclosed room"]):
            assessment.smoke_or_enclosed_space_exposure = "yes"

    # Age if explicitly stated anywhere in a user sentence.
    if assessment.age in (None, "", "unknown"):
        age_match = re.search(r"\b(?:age|umar|years old|saal)\s*[:=]?\s*(\d{1,3})\b", t)
        if age_match:
            assessment.age = age_match.group(1)


def structured_extract(text, user_history, active_field):
    """
    Use Sarvam-105B to resolve natural Hinglish and extract multiple
    fields from the user's actual history.

    IMPORTANT: assistant messages are intentionally excluded from the
    history passed to the model. Otherwise the model can mistake the
    options inside the assistant's question for facts reported by the user.
    """
    try:
        from models import generate_structured

        system = (
            "You are a strict medical-information extraction component for a burn "
            "conversation. Extract ONLY facts explicitly stated by the USER. "
            "Never infer a fact merely because the assistant asked about it. "
            "Assistant questions are not evidence. A single user sentence can "
            "answer several fields at once. Resolve common Roman-Hindi/Hinglish "
            "misspellings (for example per/pair, mei/mein, paani/pani). "
            "For a one-word yes/no reply, map it only to ACTIVE_FIELD. "
            "Return null for any field that is not explicitly supported by the "
            "user's text/history. Never manufacture size, pain, smoke exposure, "
            "circumferential status, or severity."
        )

        user_prompt = f"""
ACTIVE_FIELD: {active_field or "none"}

LATEST USER MESSAGE:
{text}

USER-ONLY CONVERSATION HISTORY:
{user_history}

Return JSON with exactly these keys:
age,
cause_of_burn,
time_since_burn,
body_part_affected,
approximate_size,
blistering_or_skin_appearance,
pain_level,
circumferential,
smoke_or_enclosed_space_exposure

Use null whenever the user has not actually provided the information.
"""

        data = generate_structured(system, user_prompt)
        return {
            key: value
            for key, value in data.items()
            if key in FIELDS and value not in (None, "", "unknown")
        }
    except Exception:
        return {}


def merge_assessment(assessment, extracted):
    for field, value in extracted.items():
        if value not in (None, "", "unknown"):
            setattr(assessment, field, str(value))


def known_dict(assessment):
    return {
        field: getattr(assessment, field)
        for field in FIELDS
        if getattr(assessment, field) not in (None, "", "unknown")
    }


def missing_fields(assessment):
    return [
        field
        for field in FIELDS
        if field != "age"
        and getattr(assessment, field) in (None, "", "unknown")
    ]


def process(db, call, text):
    text = text.strip()
    if not text:
        return {
            "call_uid": call.call_uid,
            "condition": call.condition,
            "stage": call.current_stage,
            "assistant_response": "Please describe what happened.",
            "assessment": known_dict(call.assessment),
            "missing_information": missing_fields(call.assessment),
            "severity": call.severity,
            "severity_reasons": call.severity_reasons or [],
        }

    add_message(db, call, "user", text)

    # ONLY user messages are given to the extraction model.
    user_messages = (
        db.query(ConversationMessage)
        .filter(
            ConversationMessage.call_id == call.id,
            ConversationMessage.role == "user",
        )
        .order_by(ConversationMessage.id.desc())
        .limit(20)
        .all()
    )
    user_history = "\n".join(
        f"user: {m.message}" for m in reversed(user_messages)
    )

    active_field = None
    current_missing = missing_fields(call.assessment)
    if call.current_stage == "ASSESS_BURN" and current_missing:
        active_field = current_missing[0]

    # First deterministic extraction, then LLM extraction over user-only context.
    rule_extract(call.assessment, text, active_field)
    extracted = structured_extract(text, user_history, active_field)
    merge_assessment(call.assessment, extracted)

    # A known field must never become unknown because a model omitted it.
    call.condition = "burns_scalds"
    urgent, emergency_reasons = emergency_override(text)

    if call.current_stage == "IDENTIFY_CONDITION":
        if urgent:
            call.severity = "RED"
            call.severity_reasons = emergency_reasons
            call.current_stage = "GUIDANCE"
            response = (
                "Ye potentially serious situation ho sakti hai. "
                + WHO_FIRST_AID
                + " Agar saans lene mein dikkat, behoshi ya smoke inhalation hua hai, "
                  "turant emergency medical care lein."
            )
        else:
            missing = missing_fields(call.assessment)
            call.assessment.missing_information = missing
            if missing:
                call.current_stage = "ASSESS_BURN"
                response = (
                    "Samajh gaya — burn/scald case hai. "
                    + WHO_FIRST_AID
                    + "\n\nMain aapke message mein jo details already mili hain unhe repeat nahi karunga. "
                    + QUESTIONS[missing[0]]
                )
            else:
                call.current_stage = "COLLECT_PATIENT_DETAILS"
                response = (
                    WHO_FIRST_AID
                    + "\n\nBurn assessment complete hai. Ab case record ke liye patient details lenge. "
                      "Aapka naam kya hai?"
                )

    elif call.current_stage == "ASSESS_BURN":
        missing = missing_fields(call.assessment)
        call.assessment.missing_information = missing

        if missing:
            response = QUESTIONS[missing[0]]
        else:
            severity, reasons = assess_burn(known_dict(call.assessment))
            call.severity = severity
            call.severity_reasons = reasons
            call.current_stage = "COLLECT_PATIENT_DETAILS"
            response = (
                WHO_FIRST_AID
                + "\n\nAssessment complete hai. Ab case record aur future follow-up ke liye "
                  "patient details lenge. Aapka naam kya hai?"
            )

    elif call.current_stage == "COLLECT_PATIENT_DETAILS":
        if not call.patient:
            patient_name = text.strip()
            patient_age = None
            if str(call.assessment.age).isdigit():
                patient_age = int(call.assessment.age)

            patient = Patient(
                patient_uid=uid("PAT"),
                name=patient_name,
                age=patient_age,
                preferred_language="hinglish",
            )
            db.add(patient)
            db.flush()
            call.patient_id = patient.id
            call.requires_follow_up = (
                "required" if call.severity in ("RED", "YELLOW") else "unknown"
            )
            call.current_stage = "FOLLOW_UP"
            response = (
                "Thank you. "
                + (
                    "Aapke case mein medical follow-up important hai. "
                    if call.requires_follow_up == "required"
                    else ""
                )
                + "Future updates ke liye contact number share karna chahenge?"
            )
        else:
            call.current_stage = "COMPLETE"
            call.status = "completed"
            response = (
                "Case record save ho gaya. Please revert back with any new symptoms "
                "ya updates."
            )

    elif call.current_stage == "FOLLOW_UP":
        call.current_stage = "COMPLETE"
        call.status = "completed"
        call.follow_up_status = "pending"
        response = (
            "Case record save ho gaya. Please revert back for follow-up updates, "
            "especially if symptoms worsen or medical review was advised."
        )

    else:
        response = (
            "Case already complete hai. Agar condition mein change ya new symptom hai "
            "to naya case start karein."
        )

    add_message(db, call, "assistant", response)
    db.commit()
    db.refresh(call)

    return {
        "call_uid": call.call_uid,
        "condition": call.condition,
        "stage": call.current_stage,
        "assistant_response": response,
        "assessment": {field: getattr(call.assessment, field) for field in FIELDS},
        "missing_information": call.assessment.missing_information or [],
        "severity": call.severity,
        "severity_reasons": call.severity_reasons or [],
    }
