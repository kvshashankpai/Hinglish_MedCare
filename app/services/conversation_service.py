import re
import uuid
from app.db.models import Call, Assessment, ConversationMessage, Patient
from app.services.triage_service import emergency_override, assess_burn

FIELDS=["age","cause_of_burn","time_since_burn","body_part_affected","approximate_size","blistering_or_skin_appearance","pain_level","circumferential","smoke_or_enclosed_space_exposure"]
QUESTIONS={
"cause_of_burn":"Burn kaise hua — garam paani/liquid, aag, garam object, chemical ya electrical?",
"body_part_affected":"Burn body ke kis part par hai?",
"smoke_or_enclosed_space_exposure":"Kya burn ke time smoke ya band kamre mein exposure hua tha?",
"time_since_burn":"Burn kab hua tha — abhi, kuch ghante pehle, ya kal?",
"approximate_size":"Burn ka area aapki hatheli se chhota hai ya bada?",
"blistering_or_skin_appearance":"Skin sirf laal hai ya blister/chhala bhi bana hai?",
"pain_level":"Pain kaisa hai — mild, medium ya bahut zyada?",
"circumferential":"Kya burn poore finger, haath, pair ya body part ke around hai?"
}
WHO_FIRST_AID="Burn ko pehle safe tarike se cool karein: burning source se door ho jaayein, affected area ko cool running water se cool karein, aur agar clothing skin se chipki nahi hai to carefully remove karein. Ice, oil, paste, haldi ya raw cotton na lagayein aur blisters na phodein. Severe burn ya concerning symptoms mein medical care lein."

def uid(prefix): return prefix+"-"+uuid.uuid4().hex[:8].upper()

def new_call(db):
    c=Call(call_uid=uid("CALL"),condition="unknown",current_stage="IDENTIFY_CONDITION")
    db.add(c); db.flush(); db.add(Assessment(call_id=c.id)); db.commit(); db.refresh(c); return c

def add(db,c,role,msg):
    db.add(ConversationMessage(call_id=c.id,role=role,message=msg,input_type="text"))

def _yes(t): return any(x in t for x in ["yes","haan","ha","ji haan","yup","yep","true","bilkul"])
def _no(t): return any(x in t for x in ["no","nahi","nahin","na","false"])

def rule_extract(a,text,active_field=None):
    """High-recall deterministic extraction. Never overwrites a known value with unknown."""
    t=text.lower().strip()

    if active_field=="smoke_or_enclosed_space_exposure":
        if _yes(t): a.smoke_or_enclosed_space_exposure="yes"
        elif _no(t): a.smoke_or_enclosed_space_exposure="no"
    if active_field=="circumferential":
        if _yes(t): a.circumferential="yes"
        elif _no(t): a.circumferential="no"
    if active_field=="blistering_or_skin_appearance":
        if any(x in t for x in ["blister","chhala","chhale"]): a.blistering_or_skin_appearance="blistering"
        elif any(x in t for x in ["red","laal"]): a.blistering_or_skin_appearance="redness only"
    if active_field=="pain_level":
        if any(x in t for x in ["bahut zyada","severe","extreme","very bad"]): a.pain_level="severe"
        elif any(x in t for x in ["medium","moderate"]): a.pain_level="moderate"
        elif any(x in t for x in ["mild","thoda","kam"]): a.pain_level="mild"

    if a.cause_of_burn in (None,"unknown"):
        if any(x in t for x in ["garam paani","garam pani","hot water","boiling water","scald","garam liquid","hot liquid"]): a.cause_of_burn="hot liquid"
        elif any(x in t for x in ["aag","fire","flame","chulha","stove"]): a.cause_of_burn="flame"
        elif "chemical" in t: a.cause_of_burn="chemical"
        elif any(x in t for x in ["electric","current","wire"]): a.cause_of_burn="electrical"

    if a.body_part_affected in (None,"unknown"):
        # Handles complete sentences such as: "garam paani pair/leg par gir gaya".
        body_map={
            "hand":["haath","hand","hath"],
            "face":["face","chehra"],
            "leg":["leg","pair","taang"],
            "arm":["arm","baazu","bazu"],
            "foot":["foot","paon","paanv"],
            "eye":["eye","aankh"],
            "neck":["neck","gardan"],
        }
        for part,words in body_map.items():
            if any(re.search(r"\b"+re.escape(w)+r"\b",t) for w in words):
                a.body_part_affected=part; break

    if a.time_since_burn in (None,"unknown"):
        if any(x in t for x in ["just now","abhi","abhi hua","abhi hua hai","right now","kuch der pehle","thodi der pehle","ghante pehle","hour ago","kal","yesterday"]):
            a.time_since_burn=text

    if a.approximate_size in (None,"unknown"):
        if any(x in t for x in ["hatheli se chhota","smaller than palm","small","chhota"]): a.approximate_size="smaller than palm"
        elif any(x in t for x in ["hatheli se bada","larger than palm","bigger than palm","large","bada","poora haath","whole hand"]): a.approximate_size="larger than palm"

    if a.blistering_or_skin_appearance in (None,"unknown"):
        if any(x in t for x in ["blister","chhala","chhale"]): a.blistering_or_skin_appearance="blistering"
        elif any(x in t for x in ["red","laal"]): a.blistering_or_skin_appearance="redness only"

    if a.pain_level in (None,"unknown"):
        if any(x in t for x in ["bahut zyada","severe","extreme","very bad"]): a.pain_level="severe"
        elif any(x in t for x in ["medium","moderate"]): a.pain_level="moderate"
        elif any(x in t for x in ["mild","thoda","kam"]): a.pain_level="mild"

    if a.circumferential in (None,"unknown") and (any(x in t for x in ["around","circumferential","poore haath","poore pair"]) or (active_field=="circumferential" and _yes(t))):
        a.circumferential="yes"

    if a.smoke_or_enclosed_space_exposure in (None,"unknown") and (any(x in t for x in ["smoke","dhuan","band kamre","enclosed room"]) or (active_field=="smoke_or_enclosed_space_exposure" and _yes(t))):
        a.smoke_or_enclosed_space_exposure="yes"

def structured_extract(text, history, active_field):
    """Use Sarvam to extract multiple fields from the full current context."""
    try:
        from models import generate_structured
        system=(
            "You extract structured burn information from Hinglish/Indian English. "
            "Return JSON only. Never guess. Only fill a field when explicitly stated. "
            "Resolve pronouns and conversational references using the history. "
            "A sentence can answer several questions at once. "
            "For yes/no replies, map the answer to active_field. "
            "Allowed values are strings; unknown fields must be null."
        )
        user=f"""ACTIVE_FIELD: {active_field}
CURRENT MESSAGE: {text}
RECENT CONVERSATION:
{history}

Return exactly these JSON keys:
age, cause_of_burn, time_since_burn, body_part_affected, approximate_size,
blistering_or_skin_appearance, pain_level, circumferential,
smoke_or_enclosed_space_exposure"""
        data=generate_structured(system,user)
        return {k:v for k,v in data.items() if k in FIELDS and v not in (None,"","unknown")}
    except Exception:
        return {}

def merge(a, extracted):
    for field,value in extracted.items():
        if value not in (None,"","unknown"):
            setattr(a,field,str(value))

def known_dict(a):
    return {f:getattr(a,f) for f in FIELDS if getattr(a,f) not in (None,"","unknown")}

def process(db,c,text):
    add(db,c,"user",text)
    history="\n".join(
        f"{m.role}: {m.message}"
        for m in db.query(ConversationMessage).filter(ConversationMessage.call_id==c.id).order_by(ConversationMessage.id.desc()).limit(12).all()[::-1]
    )
    active_field=None
    if c.current_stage=="ASSESS_BURN" and c.assessment.missing_information:
        active_field=c.assessment.missing_information[0]

    rule_extract(c.assessment,text,active_field)
    merge(c.assessment,structured_extract(text,history,active_field))
    c.condition="burns_scalds"
    urgent,reasons=emergency_override(text)

    if c.current_stage=="IDENTIFY_CONDITION":
        if urgent:
            c.severity="RED"; c.severity_reasons=reasons; c.current_stage="COLLECT_PATIENT_DETAILS"
            response="Ye potentially serious situation ho sakti hai. "+WHO_FIRST_AID+" Agar saans lene mein dikkat, behoshi ya smoke inhalation hua hai, turant emergency medical care lein."
        else:
            missing=[f for f in FIELDS if f!="age" and getattr(c.assessment,f) in (None,"","unknown")]
            c.current_stage="ASSESS_BURN"
            if missing:
                response="Samajh gaya — burn/scald case hai. "+WHO_FIRST_AID+"\n\nMain aapke message mein jo details already mili hain unhe repeat nahi karunga. "+QUESTIONS[missing[0]]
            else:
                c.current_stage="COLLECT_PATIENT_DETAILS"
                response=WHO_FIRST_AID+"\n\nBurn assessment complete hai. Ab patient details lenge. Aapka naam kya hai?"
    elif c.current_stage=="ASSESS_BURN":
        missing=[f for f in FIELDS if f!="age" and getattr(c.assessment,f) in (None,"","unknown")]
        c.assessment.missing_information=missing
        if missing:
            response="Theek hai. "+QUESTIONS[missing[0]]
        else:
            sev,rs=assess_burn(known_dict(c.assessment)); c.severity=sev; c.severity_reasons=rs; c.current_stage="COLLECT_PATIENT_DETAILS"
            response=WHO_FIRST_AID+"\n\nAssessment complete hai. Ab case record aur follow-up ke liye patient details lenge. Aapka naam kya hai?"
    elif c.current_stage=="COLLECT_PATIENT_DETAILS":
        if not c.patient:
            p=Patient(patient_uid=uid("PAT"),name=text.strip(),preferred_language="hinglish")
            db.add(p); db.flush(); c.patient_id=p.id
            c.requires_follow_up="required" if c.severity in ("RED","YELLOW") else "unknown"; c.current_stage="FOLLOW_UP"
            response="Thank you. "+("Aapke case mein medical follow-up important hai. " if c.requires_follow_up=="required" else "")+"Future updates ke liye contact number share karna chahenge?"
        else:
            c.current_stage="COMPLETE"; c.status="completed"; response="Case record save ho gaya. Please revert back with any new symptoms or updates."
    elif c.current_stage=="FOLLOW_UP":
        c.current_stage="COMPLETE"; c.status="completed"; c.follow_up_status="pending"
        response="Case record save ho gaya. Please revert back for follow-up updates, especially if symptoms worsen or medical review was advised."
    else:
        response="Case already complete hai. Agar condition mein change ya new symptom hai to naya case start karein."

    add(db,c,"assistant",response); db.commit(); db.refresh(c)
    return {
        "call_uid":c.call_uid,"condition":c.condition,"stage":c.current_stage,
        "assistant_response":response,
        "assessment":{f:getattr(c.assessment,f) for f in FIELDS},
        "missing_information":c.assessment.missing_information or [],
        "severity":c.severity,"severity_reasons":c.severity_reasons or []
    }
