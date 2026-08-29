"""
prompt_template.py
===================
One prompt format, reused for every condition (falls, animal_related,
burns_scalds, fever_cold_diarrhea, ...). The guideline checklist is
the only thing that changes between conditions - it's injected in.
"""


def build_prompt(user_message, guideline):
    """
    guideline: the loaded JSON dict from /guidelines/<condition>.json
    user_message: the caregiver/patient's raw Hindi/Hinglish text
    """

    required_fields = "\n".join(
        f"- {key}: {value['description']}"
        for key, value in guideline["required_information"].items()
    )

    prompt = f"""
You are a first-contact rural health information assistant.

Your job in this stage is ONLY to understand the caller's message
and collect clinically relevant information. This is Stage 1
information-gathering, NOT a diagnosis.

Do NOT diagnose the patient.
Do NOT invent information.
Do NOT assume that an unspecified symptom is present or absent.
Do NOT make a RED/YELLOW/GREEN triage decision yet.

The information that should be assessed for this case
("{guideline['condition']}") is:

{required_fields}

For the caller's message below:

1. Identify the main complaint.
2. Extract ONLY information explicitly present in the message.
3. Mark every other required field as "unknown" (never guess or
   assume a normal/negative value).
4. List which required information is still missing.
5. Ask ONE single most relevant follow-up question to obtain the
   most important missing piece of information.

Return your answer in EXACTLY this format:

MAIN_COMPLAINT:
...

KNOWN_INFORMATION:
- field = value
- field = value

MISSING_INFORMATION:
- field
- field

NEXT_QUESTION:
...

CALLER_MESSAGE:
{user_message}
"""
    return prompt
