import uuid
from app.db.models import Call, Assessment, ConversationMessage, Patient
from app.services.triage_service import emergency_override, assess_burn

FIELDS = ["age","cause_of_burn","time_since_burn","body_part_affected","approximate_size","blistering_or_skin_appearance","pain_level","circumferential","smoke_or_enclosed_space_exposure"]
QUESTIONS = {"cause_of_burn":"Burn kaise hua — garam paani/liquid, aag, garam object, chemical ya electrical?","body_part_affected":"Burn body ke kis part par hai?","smoke_or_enclosed_space_exposure":"Kya burn ke time smoke ya band kamre mein exposure hua tha?","time_since_burn":"Burn kab hua tha — abhi, kuch ghante pehle, ya kal?","approximate_size":"Burn ka area aapki hatheli se chhota hai ya bada?","blistering_or_skin_appearance":"Skin sirf laal hai ya blister/chhala bhi bana hai?","pain_level":"Pain kaisa hai — mild, medium ya bahut zyada?","circumferential":"Kya burn poore finger, haath, pair ya body part ke around hai?"}
WHO_FIRST_AID = "Burn ko pehle safe tarike se cool karein: burning source se door ho jaayein, affected area ko cool running water se cool karein, aur agar clothing skin se chipki nahi hai to carefully remove karein. Ice, oil, paste, haldi ya raw cotton na lagayein aur blisters na phodein. Severe burn ya concerning symptoms mein medical care lein."

def uid(prefix): return prefix + "-" + uuid.uuid4().hex[:8].upper()
def new_call(db):
    c = Call(call_uid=uid("CALL"), condition="unknown", current_stage="IDENTIFY_CONDITION")
    db.add(c); db.flush(); db.add(Assessment(call_id=c.id)); db.commit(); db.refresh(c); return c
def add(db,c,role,msg): db.add(ConversationMessage(call_id=c.id, role=role, message=msg, input_type="text"))

def extract(a,text):
    t=text.lower()
    if a.cause_of_burn=="unknown":
        if any(x in t for x in ["garam paani","hot water","boiling water","scald"]): a.cause_of_burn="hot liquid"
        elif any(x in t for x in ["aag","fire","flame","chulha","stove"]): a.cause_of_burn="flame"
        elif "chemical" in t: a.cause_of_burn="chemical"
        elif "electric" in t: a.cause_of_burn="electrical"
    if a.body_part_affected=="unknown":
        for p,ws in {"hand":["haath","hand"],"face":["face","chehra"],"leg":["leg","pair"],"arm":["arm","baazu"],"foot":["foot","paon"]}.items():
            if any(w in t for w in ws): a.body_part_affected=p; break
    if a.time_since_burn=="unknown" and any(x in t for x in ["hour","ghante","kal","yesterday","abhi","just now"]): a.time_since_burn=text
    if a.approximate_size=="unknown" and any(x in t for x in ["hatheli se chhota","smaller than palm","small"]): a.approximate_size="smaller than palm"
    if a.approximate_size=="unknown" and any(x in t for x in ["hatheli se bada","larger than palm","large","poora haath","whole hand"]): a.approximate_size="larger/extensive"
    if a.blistering_or_skin_appearance=="unknown" and any(x in t for x in ["blister","chhala"]): a.blistering_or_skin_appearance="blistering"
    if a.blistering_or_skin_appearance=="unknown" and any(x in t for x in ["red","laal"]): a.blistering_or_skin_appearance="redness"
    if a.pain_level=="unknown":
        if any(x in t for x in ["bahut zyada","severe","extreme"]): a.pain_level="severe"
        elif any(x in t for x in ["medium","moderate"]): a.pain_level="moderate"
        elif any(x in t for x in ["mild","thoda"]): a.pain_level="mild"
    if a.circumferential=="unknown" and any(x in t for x in ["around","circumferential"]): a.circumferential="yes"
    if a.smoke_or_enclosed_space_exposure=="unknown" and any(x in t for x in ["smoke","dhuan","band kamre"]): a.smoke_or_enclosed_space_exposure="yes"

def process(db,c,text):
    add(db,c,"user",text); c.condition="burns_scalds"; urgent,reasons=emergency_override(text)
    if c.current_stage=="IDENTIFY_CONDITION":
        extract(c.assessment,text)
        if urgent:
            response="Ye potentially serious situation ho sakti hai. "+WHO_FIRST_AID+" Agar saans lene mein dikkat, behoshi ya smoke inhalation hua hai, turant emergency medical care lein."
            c.severity="RED"; c.severity_reasons=reasons; c.current_stage="COLLECT_PATIENT_DETAILS"
        else:
            missing=[f for f in FIELDS if f!="age" and getattr(c.assessment,f) in (None,"","unknown")]
            c.current_stage="ASSESS_BURN"; response="Samajh gaya — burn/scald case hai. "+WHO_FIRST_AID+" Ab main current burn ki severity samajhne ke liye short questions poochunga. "+QUESTIONS[missing[0]]
    elif c.current_stage=="ASSESS_BURN":
        extract(c.assessment,text); missing=[f for f in FIELDS if f!="age" and getattr(c.assessment,f) in (None,"","unknown")]; c.assessment.missing_information=missing
        if missing: response=QUESTIONS[missing[0]]
        else:
            sev,rs=assess_burn({f:getattr(c.assessment,f) for f in FIELDS}); c.severity=sev; c.severity_reasons=rs; c.current_stage="COLLECT_PATIENT_DETAILS"
            response=WHO_FIRST_AID+"\n\nAssessment complete. Ab case record aur future follow-up ke liye patient details lenge. Aapka naam kya hai?"
    elif c.current_stage=="COLLECT_PATIENT_DETAILS":
        if not c.patient:
            p=Patient(patient_uid=uid("PAT"),name=text.strip(),preferred_language="hinglish"); db.add(p); db.flush(); c.patient_id=p.id
            c.requires_follow_up="required" if c.severity in ("RED","YELLOW") else "unknown"; c.current_stage="FOLLOW_UP"
            response="Thank you. "+("Aapke case mein medical follow-up important hai. " if c.requires_follow_up=="required" else "")+"Future updates ke liye contact number share karna chahenge?"
        else:
            c.current_stage="COMPLETE"; c.status="completed"; response="Case record save ho gaya. Please revert back with any new symptoms or updates."
    elif c.current_stage=="FOLLOW_UP":
        c.current_stage="COMPLETE"; c.status="completed"; c.follow_up_status="pending"
        response="Case record save ho gaya. "+("Please revert back for follow-up updates, especially if symptoms worsen or medical review was advised." if c.requires_follow_up=="required" else "Agar symptoms worsen ya new concerns aayein to medical care lein and revert back with an update.")
    else:
        response="Case already complete hai. Agar condition mein change ya new symptom hai to naya case start karein."
    add(db,c,"assistant",response); db.commit(); db.refresh(c)
    return {"call_uid":c.call_uid,"condition":c.condition,"stage":c.current_stage,"assistant_response":response,"assessment":{f:getattr(c.assessment,f) for f in FIELDS},"missing_information":c.assessment.missing_information or [],"severity":c.severity,"severity_reasons":c.severity_reasons or []}
