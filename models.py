"""
models.py
=========
One common interface: generate(model_key, prompt) -> str

Every model is loaded LAZILY (only when first used) so you don't
need all 3 models' dependencies/GPU memory/API keys at once -
you can test one model at a time by only calling that key.

To add a 4th model (e.g. Hanooman/VizzhyGPT once you have API access),
just add one more "elif model_key == '...':" block below. The rest
of the codebase (prompt_template.py, run_eval.py) never needs to change.
"""

import os
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

# ------------------------------------------------------------------
# Registry: human-readable name -> internal key
# Edit this if you swap HF repo IDs.
# ------------------------------------------------------------------

MODEL_REGISTRY = {
    "airavata": "ai4bharat/Airavata",
    "openhathi": "sarvamai/OpenHathi-7B-Hi-v0.1-Base",
    "sarvam": "sarvam-105b",   # API model name, not a HF repo
}

# Cache so each local model is loaded only once per run
_loaded_hf_models = {}


# ------------------------------------------------------------------
# Local HuggingFace models (Airavata, OpenHathi)
# ------------------------------------------------------------------

def _load_hf_model(repo_id):
    if repo_id in _loaded_hf_models:
        return _loaded_hf_models[repo_id]

    print(f"Loading {repo_id} ...")
    tokenizer = AutoTokenizer.from_pretrained(repo_id)
    model = AutoModelForCausalLM.from_pretrained(
        repo_id,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        device_map="auto"
    )
    model.eval()
    print(f"{repo_id} loaded.")

    _loaded_hf_models[repo_id] = (tokenizer, model)
    return tokenizer, model


def _generate_hf(repo_id, prompt, max_new_tokens=500):
    tokenizer, model = _load_hf_model(repo_id)

    inputs = tokenizer(prompt, return_tensors="pt")
    inputs = {k: v.to(model.device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=0.1,
            do_sample=False,
            repetition_penalty=1.1,
            pad_token_id=tokenizer.eos_token_id
        )

    generated_tokens = outputs[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()


# ------------------------------------------------------------------
# Sarvam API (sarvam-30b / sarvam-105b) - OpenAI-compatible endpoint
# ------------------------------------------------------------------

def _generate_sarvam(prompt, model_name="sarvam-105b", max_tokens=500):
    """
    Requires: pip install openai
    Set your key first:  export SARVAM_API_KEY="sk_xxx..."

    Sarvam's /v1/chat/completions endpoint is OpenAI-compatible, so we
    reuse the openai client pointed at Sarvam's base_url.
    Docs: https://docs.sarvam.ai/api-reference/chat/chat-completions
    (Confirm current base_url / model names there before running -
    APIs change; sarvam-30b/105b were current as of this writing.)
    """
    from openai import OpenAI

    api_key = os.environ.get("SARVAM_API_KEY")
    if not api_key:
        raise RuntimeError("Set SARVAM_API_KEY environment variable first.")

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.sarvam.ai/v1"
    )

    response = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=max_tokens,
    )

    return response.choices[0].message.content.strip()


# ------------------------------------------------------------------
# PUBLIC ENTRY POINT - this is the only function run_eval.py calls
# ------------------------------------------------------------------

def generate(model_key, prompt):
    """
    model_key: one of "airavata", "openhathi", "sarvam"
    Returns the raw model text output (str). Raises on error -
    the caller (run_eval.py) catches and logs errors per case.
    """
    if model_key == "airavata":
        return _generate_hf(MODEL_REGISTRY["airavata"], prompt)

    elif model_key == "openhathi":
        return _generate_hf(MODEL_REGISTRY["openhathi"], prompt)

    elif model_key == "sarvam":
        return _generate_sarvam(prompt, model_name=MODEL_REGISTRY["sarvam"])

    else:
        raise ValueError(
            f"Unknown model_key '{model_key}'. "
            f"Valid options: {list(MODEL_REGISTRY.keys())}"
        )
