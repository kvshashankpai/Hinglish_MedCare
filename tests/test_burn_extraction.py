import pytest
from app.services.conversation_service import normalize_hinglish, rule_extract

class A:
    def __init__(self):
        for f in ["age","cause_of_burn","time_since_burn","body_part_affected","approximate_size","blistering_or_skin_appearance","pain_level","circumferential","smoke_or_enclosed_space_exposure"]:
            setattr(self,f,"unknown")

def test_roman_hindi_body_part_per():
    a=A()
    rule_extract(a,"garam paani per mei hua hai")
    assert a.body_part_affected=="leg"

def test_full_sentence_extracts_multiple_fields():
    a=A()
    rule_extract(a,"garam paani mere pair par gira, abhi hua hai aur bahut dard ho raha hai")
    assert a.cause_of_burn=="hot liquid"
    assert a.body_part_affected=="leg"
    assert a.time_since_burn=="garam paani mere pair par gira, abhi hua hai aur bahut dard ho raha hai"
    assert a.pain_level=="severe"

def test_yes_no_active_field():
    a=A()
    rule_extract(a,"haan","smoke_or_enclosed_space_exposure")
    assert a.smoke_or_enclosed_space_exposure=="yes"
    rule_extract(a,"nahi","circumferential")
    assert a.circumferential=="no"

def test_known_value_is_not_overwritten():
    a=A()
    a.body_part_affected="leg"
    rule_extract(a,"haan")
    assert a.body_part_affected=="leg"
