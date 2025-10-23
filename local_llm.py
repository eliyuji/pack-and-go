import json
import re
from tqdm import tqdm
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, AutoModelForSeq2SeqLM

print("🔄 Loading FLAN-T5-Base for location extraction...")
model_name = "google/flan-t5-base"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
print("✅ FLAN-T5-Base loaded successfully!")


def extract_locations_flan_batch(chunks, batch_size=4, max_input_length=512):
    """
    Run FLAN-T5 on chunks in batches, showing progress.
    Uses CPU, keeps memory low, and handles malformed outputs.
    """
    all_results = []
    num_batches = (len(chunks) + batch_size - 1) // batch_size

    print(f"🚀 Running FLAN-T5 location extraction on {len(chunks)} chunks ({num_batches} batches of {batch_size})")

    for batch_i in tqdm(range(num_batches), desc="🧠 FLAN-T5 batch progress", unit="batch"):
        batch_chunks = chunks[batch_i * batch_size : (batch_i + 1) * batch_size]
        batch_results = []

        for j, chunk in enumerate(batch_chunks):
            # Truncate overly long inputs
            inputs = tokenizer(
                f"Extract all city, restaurant, landmark, or region names from this text. "
                f"Return only a JSON list of strings. Text: {chunk}",
                return_tensors="pt",
                max_length=max_input_length,
                truncation=True,
            )

            outputs = model.generate(**inputs, max_new_tokens=100)
            result = tokenizer.decode(outputs[0], skip_special_tokens=True).strip()

            # Try to extract a valid JSON list
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