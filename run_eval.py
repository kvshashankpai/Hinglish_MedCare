"""
run_eval.py
===========
ONE common testing file for ALL conditions and ALL 3 models.

Usage examples:
    python run_eval.py --condition falls --models airavata
    python run_eval.py --condition burns_scalds --models airavata,openhathi,sarvam
    python run_eval.py --condition fever_cold_diarrhea --models sarvam

To add a NEW condition later (e.g. "poisoning"):
    1. Add /guidelines/poisoning.json          (required_information dict)
    2. Add /cases/poisoning_cases.py            (TEST_CASES list)
    3. Add one line to CONDITIONS dict below.
No other file needs to change.
"""

import argparse
import json
import importlib
import pandas as pd

from prompt_template import build_prompt
from models import generate

# ------------------------------------------------------------------
# Register conditions here: condition_name -> (guideline file, cases module)
# ------------------------------------------------------------------

CONDITIONS = {
    "falls": {
        "guideline_file": "guidelines/falls.json",
        "cases_module": "cases.falls_cases",
    },
    "animal_related": {
        "guideline_file": "guidelines/animal_related.json",
        "cases_module": "cases.animal_cases",
    },
    "burns_scalds": {
        "guideline_file": "guidelines/burns_scalds.json",
        "cases_module": "cases.burns_cases",
    },
    "fever_cold_diarrhea": {
        "guideline_file": "guidelines/fever_cold_diarrhea.json",
        "cases_module": "cases.fever_diarrhea_cases",
    },
}


def load_guideline(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_cases(module_name):
    module = importlib.import_module(module_name)
    return module.TEST_CASES


def run(condition, model_keys):
    config = CONDITIONS[condition]
    guideline = load_guideline(config["guideline_file"])
    test_cases = load_cases(config["cases_module"])

    results = []

    for model_key in model_keys:
        for case in test_cases:

            print("=" * 80)
            print(f"MODEL: {model_key} | CONDITION: {condition} | "
                  f"CASE {case['id']} | {case['style']}")
            print(f"INPUT: {case['prompt']}")

            prompt = build_prompt(case["prompt"], guideline)

            error = ""
            try:
                output = generate(model_key, prompt)
                print("\nMODEL RESPONSE:")
                print(output)
            except Exception as e:
                output = ""
                error = str(e)
                print("\nERROR:")
                print(error)

            results.append({
                "condition": condition,
                "model": model_key,
                "case_id": case["id"],
                "language_style": case["style"],
                "user_input": case["prompt"],
                "model_response": output,
                "error": error,

                # ---- fill these manually while reviewing the CSV ----
                "understood_condition": "",
                "extracted_fields_correct": "",
                "identified_missing_information": "",
                "asked_relevant_question": "",
                "guideline_compliance": "",
                "notes": "",
            })

    df = pd.DataFrame(results)
    out_file = f"results/{condition}_eval.csv"
    df.to_csv(out_file, index=False, encoding="utf-8-sig")

    print("\n" + "=" * 80)
    print("EVALUATION COMPLETE")
    print(f"Results saved to: {out_file}")
    print("Open in Excel/Sheets and fill in the manual evaluation columns.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--condition",
        required=True,
        choices=list(CONDITIONS.keys()),
        help="Which condition to test"
    )
    parser.add_argument(
        "--models",
        required=True,
        help="Comma-separated: airavata,openhathi,sarvam"
    )
    args = parser.parse_args()

    model_list = [m.strip() for m in args.models.split(",")]
    run(args.condition, model_list)
