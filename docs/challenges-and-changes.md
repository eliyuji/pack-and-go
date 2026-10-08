# Challenges, improvements, and changes

Working notes for Pack & Go: what broke, what we changed, and what is still weak. The [README](../README.md) is the demo / runbook. This file is the engineering log.

Last updated: 2026-09-12.

---

## How the system is supposed to work

| Store | Role | Used at generate time? |
| --- | --- | --- |
| FAISS + `metadata.pkl` | Transcript chunks (vlog texture) | Yes |
| SQLite `travel_data.db` | Named places, ratings, districts | Yes |
| GCS `{video_id}.txt` | Full transcript blobs | Only when indexing |
| Postgres `youtube_transcripts` | Ingest catalog + dedupe (stores GCS URI, not text) | No |

Next.js and Streamlit generate/refine do **not** query Postgres. Local demo needs Groq + FAISS + Places. GCS/Postgres/YouTube are offline pipelines.

---

## Changes shipped

### Phase 1 — retrieve and itinerary correctness

The first generate path had several silent bugs.

- **Retrieve no longer runs FLAN-T5 on the user query.** The old loop treated the query as a sequence of characters (~100 T5 calls). Locations now come from an allowlist / spaCy; boost compares against **chunk text**, not a mutated metadata row.
- **City parse is shared.** `split(" in ")` turned `3-day trip in Taipei focused on food` into city `Taipei Focused On Food`. [`backend/query_parse.py`](../backend/query_parse.py) `extract_city` is used on generate and refine.
- **Day cards follow `activity["time"]`.** `normalize_activity_times` only fills missing times instead of overwriting them.
- **`ensure_food` runs on v2 and refine** with Places from `places_for_query`.
- Groq **retries** after empty / invalid itinerary JSON (was a hard 500).
- Tests: [`tests/test_query_parse.py`](../tests/test_query_parse.py), [`tests/test_format_itinerary.py`](../tests/test_format_itinerary.py).

### Phase 2 — API and refine

- FLAN loads **lazily** (indexing / location tagging), not on every uvicorn import.
- Empty feedback on generate **skips** the intent Groq call (retrieve → generate).
- Bad / unparseable intent → **noop**, keep the current trip.
- `add_preference` applies a **patch list** when possible; full rewrite only if the model returns a full itinerary or type is `regenerate_all`.
- Refine context capped (~4000 chars) so the prompt stays usable.

### Phase 3 — dedup

- One `extract_json` (from `itinerary_patch`). Removed the copy in `rag_pipeline.py`.
- Shared city helper. Legacy `POST /itinerary` kept.

### Ops / config (around the same window)

- Default Groq model is `openai/gpt-oss-20b` via `GROQ_MODEL`. `llama-3.1-8b-instant` was retired 2026-08-16 (404).
- Local Postgres via `docker compose up -d postgres` + `python create_tables.py`. `DATABASE_URL` matches Compose (`packandgo` / `packandgo` / `packandgo` on `localhost:5432`).
- Streamlit mockup: home, destination cards, session recents, refine sidebar.

### Map + food options (2026-09-10)

- `get_places_for_city` now returns `address`, `lat`, `lon`, `place_id` (the dump already had them; the query dropped them).
- `ensure_food` attaches `food_options`: up to 3 restaurants per slot, district-matched first, each with rating, address, coordinates, and a free `maps_url` deep link. The `food` string is unchanged, so the prompt, formatter, and patch tests still work.
- `patch_activity` drops stale `food_options` when the food changes and keeps them when it does not; `ensure_food` refills after refine.
- Streamlit shows a per-day `st.map` plus expandable food cards. `st.map` needs no Google key and costs nothing.
- **Repeat bug (same day, fixed).** The first version reused the prompt's Places list, which is only 3 restaurants per district, so three Anping slots all drew the same 3 venues. `food_places_for_query` now pulls 15 per district for `ensure_food` only (the prompt list stays small), and `ensure_food` tracks which venues a day already used, falling back to repeats only when the city genuinely lacks enough restaurants.
- Models sometimes emit `"food": "N/A"`. That counts as missing now (`PLACEHOLDER_FOOD`) so the slot gets filled.
- **Anping pile-up.** Named Anping activities still get Anping food. Landmarks like Fine Arts / Chihkan map to West Central. Unmatched slots rotate to the least-used district. The generate prompt now asks Groq not to keep every Tainan day in Anping.
- Not mapped yet: **activity** pins. The model writes free text with no link to a `places` row, so only food has coordinates. Fuzzy-matching activity text to place names is the follow-up.
- Photos are still unimplemented on purpose: Place Photos is 1,000 free/month then $7/1,000. Menus are not available from Google at all.

### Not done yet

- Phase 4: overlapping chunks at index time (`backend/chunking.py` exists, `semantic_search.chunk_text` is still 50 words, no overlap).
- Phase 5: more tests + README notes (this file is the start of the notes).
- RAG eval set (Recall@k / MRR) not built.
- Peninsula / Bay Area: one city `Peninsula` with towns as districts (San Mateo → Fremont). Aliases map Palo Alto / Bay Area / etc. to `Peninsula`. Extra evergreen queries: park, hiking trail, nature preserve, farmers market, historic downtown. No seasonal pass, no transcripts yet.
- New GCS transcripts: spaCy-only reindex finished 2026-09-04 (21 files added, 1 empty blob skipped). Restart uvicorn to load the new FAISS files.

---

## Challenges

### 1. Transcripts are a weak venue catalog

YouTube text is good for trip *shape* (night markets at night, don’t stack Jiufen and Beitou). It is a bad source of **named local recs**.

Generate already treats them differently: FAISS chunks = prose; SQLite Places = name / district / rating; `ensure_food` fills food from Places.

**Places coverage today**

| City | Approx. rows | Notes |
| --- | --- | --- |
| Taipei | ~1967 | District-aware dump |
| Bangkok | ~299 | Leftover; not the demo |
| Tainan | 0 | District list ready; Places API key not authorized yet |
| Taichung | 0 | Same |

`get_places_for_city` now samples 3 venues from the top 15 rated in each district/category (Taipei variety improves immediately). Dump Tainan/Taichung after `GOOGLE_API_KEY` can call Places Text Search.

### 2. Ingest is brittle (2026-09-04 run)

Command (from `pack-and-go/`, venv `venv` not `.venv`):

```bash
python data_generation.py Taipei Tainan Taichung --max-results 3
```

| Outcome | Count |
| --- | --- |
| Saved to GCS + Postgres | **25** (Taipei 12, Tainan 9, Taichung 4) |
| Whisper fallback failed | **13 unique** (`ffmpeg` missing) |
| Caption API | YouTube **IP-blocked** late in the Taichung queries |

`Saved transcript + metadata` means the `.txt` is already in GCS (`gs://<bucket>/{video_id}.txt`) and a Postgres row points at that URI.

Whisper path: no English captions → `yt-dlp` download → `whisper` → needs **`ffmpeg` on PATH**. Without it, the video is skipped and **not** in GCS.

Captions-only languages (`en-CA`, `en-GB`) are treated as “no transcript” because the API defaults to `en`.

Do **not** run the script from the parent `packAndGoRE/` folder. `ingest.log` for this run lives in `pack-and-go/ingest.log`.

### 3. Reindex crashed on FLAN-T5 (`exit 139`)

`python indexing.py` loaded the existing index (~48,691 vectors), skipped already-indexed blobs, started `0vy50-De12s.txt`, then **segfaulted on the first FLAN-T5 `generate()`** (native crash, not a Python exception). The in-memory add never reached `save_index`, so the on-disk FAISS files stayed at the pre-ingest snapshot.

**Change:** indexing is **spaCy-only by default**. Chunks with no spaCy locations get `[]`. Retrieve still boosts on chunk text (Phase 1). Set `INDEX_USE_FLAN=1` if you want the old T5 fallback (`local_llm.py` now lazy-loads on CPU). Reindex completed: 21 new files in FAISS (plus one empty GCS blob skipped). Restart uvicorn to pick them up.

### 4. Query-time correctness (fixed, keep the lesson)

- FLAN on query **characters** made retrieve slow and wrong.
- City `split(" in ")` broke any query with words after the city.
- Mutating shared metadata rows during boost was unsafe.
- Format ignored `activity["time"]`, so the UI and refine targets could disagree with the JSON.

### 5. Model and network

- Groq model IDs change; keep `GROQ_MODEL` in `.env`.
- Empty JSON from Groq used to 500; retries help but first generate can still take a long time (UI timeout 120s).
- Groq 403 (Cloudflare / IP) happened once; needed a new key. Separate from YouTube caption blocks.
- GCS writes need a billed bucket + service account. Historical 403s blocked ingest before this run.

### 6. Product / demo

- Paris / Tokyo / Bali cards still call generate; retrieval and Places are Taipei-shaped.
- No auth. Next.js save is `localStorage` in this browser; Streamlit still uses session recents.
- **Next.js is the product UI** (`frontend/`, port 3000). Streamlit stays as rollback / recording demo on 8501. Same `/itinerary/v2` and `/itinerary/refine` contracts. Clock times and the numbered route are display-only until the schema stores real clocks.
- FAISS artifacts are gitignored (~84MB); reviewers are pointed at a recording.
- Patch splice is deterministic; **intent classification is not**. Wrong type → no-op or wrong slot.

---

## Improvements (suggested order)

1. **Places for Tainan and Taichung** — structured names the model can actually emit. Add districts later if recs feel city-wide and generic.
2. **Finish FAISS reindex** for the 25 GCS files. If FLAN keeps crashing: spaCy-only tags, or index without location extraction, then tag offline.
3. **Install `ffmpeg`** (`brew install ffmpeg`) before another Whisper pass. Wait out the YouTube IP block or set `WEBSHARE_PROXY_*`. Already-saved ids are skipped.
4. **Prefer captions over Whisper** — request `en`, `en-US`, `en-GB`, `en-CA` before downloading audio. Walking tours will still often have no speech captions.
5. **Overlapping chunks** (Phase 4) — `backend/chunking.py` (400 / 50) at index time so place names are less often split across 50-word windows.
6. **RAG eval** — label from `metadata.pkl` keyword search (not FAISS top-k), then Recall@5/10 and MRR. Proves retrieve after the Phase 1 fix.
7. **Do not treat “more YouTube” as the local-rec strategy.** Keep transcripts for texture; keep Places as the catalog. Live Places at query time is an option later (cost + latency).

---

## Operational reminders

```bash
# Always from pack-and-go/ with ./venv
source venv/bin/activate

# Postgres (ingest only)
docker compose up -d postgres
python create_tables.py

# New videos
python data_generation.py Taipei Tainan Taichung --max-results 3

# Searchable index (after GCS has new .txt files)
python indexing.py

# Places dump
python -m backend.database.populating_db Tainan Taichung
```

- Venv path is `venv/`, not `.venv/`.
- `DATABASE_URL=postgresql://packandgo:packandgo@localhost:5432/packandgo`
- Do not commit `.env` or the GCP JSON key.

---

## Open questions

- Rebuild FAISS from scratch with overlap, or keep appending to the current ~49k index?
- Drop FLAN from the hot path entirely (index + query)?
- Host a smaller Taipei-only index for reviewers instead of “watch the recording”?
- Curated night-market / food list vs more Google Places pages?
