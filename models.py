"""
Model backends for Hinglish MedCare.

Primary application model:
    Sarvam sarvam-105b

The model is used for language understanding / extraction and
conversation wording. It does NOT control triage or database state.
"""

import os
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

MODEL_REGISTRY = {
    "airavata": "ai4bharat/Airavata",
    "openhathi": "sarvamai/OpenHathi-7B-Hi-v0.1-Base",
    "sarvam": os.getenv("SARVAM_MODEL", "sarvam-105b"),
}

_loaded_hf_models = {}


def _load_hf_model(repo_id):
    if repo_id in _loaded_hf_models:
        return _loaded_hf_models[repo_id]

    print(f"Loading {repo_id} ...")
    tokenizer = AutoTokenizer.from_pretrained(repo_id)
    model = AutoModelForCausalLM.from_pretrained(
        repo_id,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        device_map="auto",
    )
    model.eval()
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
            pad_token_id=tokenizer.eos_token_id,
        )

    generated_tokens = outputs[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()


def _generate_sarvam(prompt, model_name=None, max_tokens=500):
    from openai import OpenAI

    api_key = os.environ.get("SARVAM_API_KEY")
    if not api_key:
        raise RuntimeError("Set SARVAM_API_KEY in .env or the environment.")

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.sarvam.ai/v1",
    )

    response = client.chat.completions.create(
        model=model_name or MODEL_REGISTRY["sarvam"],
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()


def generate(model_key, prompt):
    if model_key == "airavata":
        return _generate_hf(MODEL_REGISTRY["airavata"], prompt)
    if model_key == "openhathi":
        return _generate_hf(MODEL_REGISTRY["openhathi"], prompt)
    if model_key == "sarvam":
        return _generate_sarvam(prompt, MODEL_REGISTRY["sarvam"])
    raise ValueError(
        f"Unknown model_key '{model_key}'. Valid options: {list(MODEL_REGISTRY.keys())}"
    )


def generate_default(prompt):
    """Primary application model: Sarvam sarvam-105b."""
    return generate("sarvam", prompt)
