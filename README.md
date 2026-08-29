# PR4 Stage 1 - Guideline-Grounded Evaluation

Tests whether a model can, for a given rural-health condition:
1. Understand Hindi/Hinglish input
2. Extract clinically relevant information
3. Identify what's missing (against a guideline-derived checklist)
4. Ask ONE appropriate follow-up question

This is Stage 1 (information gathering) only - NOT a triage/diagnosis system.

## Structure

```
pr4_stage1_eval/
├── guidelines/                 # ONE required-information checklist per condition
│   ├── falls.json
│   ├── animal_related.json
│   ├── burns_scalds.json
│   └── fever_cold_diarrhea.json
├── cases/                      # ONE test-case file per condition (same shape each time)
│   ├── falls_cases.py
│   ├── animal_cases.py
│   ├── burns_cases.py
│   └── fever_diarrhea_cases.py
├── models.py                   # 3 model backends behind one generate() function
├── prompt_template.py          # ONE shared prompt builder for every condition
├── run_eval.py                 # THE common runner - use this for everything
├── results/                    # CSVs land here
└── requirements.txt
```

## IMPORTANT

The `_source_note` field in every `guidelines/*.json` file says this
explicitly, but repeating it here: **these checklists are drafts** built
from general first-aid / WHO / IMNCI / NHM reference material to get you
moving. Before using them in your actual project, your team needs to
verify every field against the specific official guideline document
(WHO / IMNCI / national STG) you've chosen as your source of truth, and
cite that source in your docs.

## Setup

```bash
pip install -r requirements.txt
export SARVAM_API_KEY="sk_xxx..."   # only needed if you're testing sarvam
```

Airavata and OpenHathi are downloaded automatically from HuggingFace the
first time you run them (needs a GPU with enough VRAM for float16, or it
will fall back to slow CPU float32).

## Running

```bash
# One model, one condition
python run_eval.py --condition falls --models airavata

# All 3 models, one condition
python run_eval.py --condition burns_scalds --models airavata,openhathi,sarvam

# One model across a different condition
python run_eval.py --condition animal_related --models sarvam
```

Each run appends `model` and `condition` columns to the output CSV, so
results for the same condition across different model runs land in the
same file (`results/<condition>_eval.csv`) if you re-run with a
different `--models` value - just be aware re-running overwrites that
CSV, so either run all your models for a condition in one `--models`
call, or rename the CSV between runs if you want to keep them separate.

## Adding a new condition later

1. Add `guidelines/<condition>.json` with a `required_information` dict
2. Add `cases/<condition>_cases.py` exporting a `TEST_CASES` list
3. Add one entry to the `CONDITIONS` dict at the top of `run_eval.py`

Nothing else changes - `models.py` and `prompt_template.py` are fully
condition-agnostic.

## Adding a 4th model (e.g. Hanooman / VizzhyGPT)

Add one `elif` branch inside `generate()` in `models.py`. Everything
else (prompts, cases, CSV output) stays the same.
