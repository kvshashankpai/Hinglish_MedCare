def emergency_override(text):
    t=text.lower(); reasons=[]
    if any(x in t for x in ['saans lene mein dikkat','difficulty breathing',"can't breathe",'breathing problem']): reasons.append('breathing difficulty reported')
    if any(x in t for x in ['smoke inhal','dhuan andar','smoke tha','smoke exposure']): reasons.append('possible smoke inhalation/exposure reported')
    if any(x in t for x in ['behosh','unconscious','not responding']): reasons.append('loss of consciousness reported')
    return bool(reasons), reasons

def assess_burn(a):
    reasons=[]; body=str(a.get('body_part_affected','unknown')).lower(); cause=str(a.get('cause_of_burn','unknown')).lower(); smoke=str(a.get('smoke_or_enclosed_space_exposure','unknown')).lower(); appearance=str(a.get('blistering_or_skin_appearance','unknown')).lower(); size=str(a.get('approximate_size','unknown')).lower(); circ=str(a.get('circumferential','unknown')).lower()
    if 'electrical' in cause or 'chemical' in cause: reasons.append('electrical/chemical mechanism reported')
    if any(x in body for x in ['face','eye','neck','throat','airway']): reasons.append('face/airway involvement reported')
    if any(x in smoke for x in ['yes','smoke','dhuan']): reasons.append('smoke/enclosed-space exposure reported')
    if any(x in circ for x in ['yes','true']): reasons.append('circumferential burn reported')
    if any(x in appearance for x in ['charred','white','leathery','black']): reasons.append('concerning skin appearance reported')
    if any(x in size for x in ['large','extensive','whole','entire']): reasons.append('large/extensive area reported')
    if reasons:return 'RED',reasons
    if any(x in body for x in ['hand','foot','joint','genital','groin']) or any(x in appearance for x in ['blister','chhala']):
        return 'YELLOW',['higher-risk location or blistering reported']
    return 'GREEN',['no configured high-risk feature reported']
