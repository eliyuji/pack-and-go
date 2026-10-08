import json
import os
import re
from tqdm import tqdm
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

# HuggingFace tokenizers + PyTorch MPS generate() have segfaulted on this Mac
# (indexing.py exit 139). Keep FLAN on CPU, single-threaded, and lazy-loaded.
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

model_name = "google/flan-t5-base"
tokenizer = None
model = None


def _load_flan():
    global tokenizer, model
    if model is not None:
        return tokenizer, model

    print("🔄 Loading FLAN-T5-Base for location extraction (CPU)...")
    torch.set_num_threads(1)
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
    model.to("cpu")
    model.eval()
    print("✅ FLAN-T5-Base loaded successfully!")
    return tokenizer, model


def extract_locations_flan_batch(chunks, batch_size=4, max_input_length=512):
    """
    Run FLAN-T5 on chunks in batches, showing progress.
    Uses CPU, keeps memory low, and handles malformed outputs.
    """
    tok, flan = _load_flan()

    if isinstance(chunks, str):
        chunks = [chunks]
    elif not isinstance(chunks, (list, tuple)):
        raise TypeError(f"chunks must be a list of strings, got {type(chunks).__name__}")

    all_results = []
    num_batches = (len(chunks) + batch_size - 1) // batch_size

    print(f"🚀 Running FLAN-T5 location extraction on {len(chunks)} chunks ({num_batches} batches of {batch_size})")

    for batch_i in tqdm(range(num_batches), desc="🧠 FLAN-T5 batch progress", unit="batch"):
        batch_chunks = chunks[batch_i * batch_size : (batch_i + 1) * batch_size]
        batch_results = []

        for j, chunk in enumerate(batch_chunks):
            inputs = tok(
                f"Extract all city, restaurant, landmark, or region names from this text. "
                f"Return only a JSON list of strings. Text: {chunk}",
                return_tensors="pt",
                max_length=max_input_length,
                truncation=True,
            )
            inputs = {k: v.to("cpu") for k, v in inputs.items()}

            with torch.inference_mode():
                outputs = flan.generate(**inputs, max_new_tokens=100)
            result = tok.decode(outputs[0], skip_special_tokens=True).strip()

            try:
                json_match = re.search(r"\[.*\]", result, re.DOTALL)
                parsed = json.loads(json_match.group(0)) if json_match else []
            except Exception:
                parsed = []

            entities = sorted(set(e.strip() for e in parsed if isinstance(e, str) and e.strip()))
            batch_results.append(entities)

            print(f"  📄 Chunk {batch_i * batch_size + j}: found {len(entities)} entities")

        all_results.extend(batch_results)

    print(f"✅ FLAN-T5 batch extraction complete — processed {len(chunks)} chunks total")
    return all_results
