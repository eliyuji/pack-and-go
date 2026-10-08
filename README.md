# Pack & Go

RAG travel planner: YouTube travel videos → transcript chunks → a day-by-day itinerary you can **edit one slot at a time**.

Ask for a 3-day trip, get morning / afternoon / evening plans with food suggestions, then change **one** slot in chat. The rest of the trip stays put.

**Demo (watch this first):** _paste your recording URL here after you upload it_  
Example: `[Watch the demo](https://youtu.be/YOUR_ID)` or a Google Drive / Loom link set to anyone-with-the-link.

The product UI is **Next.js + FastAPI** (`frontend/`, [http://localhost:3000](http://localhost:3000)). **Streamlit** (`streamlit run frontend/frontend.py`) stays as the rollback / downloadable demo on port 8501.

---

## What to show in the recording (~90 seconds)

1. **Chat** — left rail + composer. Type `3-day trip in Taipei` (Places dump + strongest index coverage).
2. **Board** — clock timeline, food links beside each stop, numbered map pins.
3. **Refine** — in chat: `Change Day 2 morning to something more cultural`.
4. **Proof** — pause on Day 2 morning vs Day 1 / other Day 2 slots. Only that slot should move.
5. Optional: **Save** (this browser) or open Streamlit on :8501 as the rollback demo.

Backup lines: `Remove shopping from Day 3`, `Add more food experiences throughout`.

---

## The interesting part

Most itinerary chat demos **regenerate the whole trip** on every message. Pack & Go treats refine as a patch:

1. LangGraph classifies intent (one activity, one day, or a global vibe).
2. Groq proposes the new JSON for **only that piece**.
3. [`backend/itinerary_patch.py`](backend/itinerary_patch.py) splices it into the existing itinerary. Other days/slots are copied, not rewritten.

That last step is deterministic and unit-tested. The LLM can still mis-classify; the splice will not silently rewrite Day 1 because you asked about Day 2 morning.

Retrieval is hybrid:

- **FAISS** over YouTube transcript chunks (what vloggers actually did).
- **SQLite Places** for city/district attractions and food. Taipei is populated in [`backend/database/travel_data.db`](backend/database/travel_data.db).

---

## Stack

| Layer | Choice |
| --- | --- |
| UI | Next.js — [`frontend/src`](frontend/src) (Streamlit demo: [`frontend/frontend.py`](frontend/frontend.py)) |
| API | FastAPI — `POST /itinerary/v2`, `POST /itinerary/refine` |
| LLM | Groq (`openai/gpt-oss-20b`, override with `GROQ_MODEL`) |
| Agent | LangGraph — [`backend/chat_generation.py`](backend/chat_generation.py) |
| Patch | Pure Python JSON splice — [`backend/itinerary_patch.py`](backend/itinerary_patch.py) |
| Retrieval | FAISS + MiniLM + spaCy / FLAN-T5 location tags |
| Places | SQLite |
| Ingestion (offline) | YouTube captions or Whisper → GCS + Postgres |

## Architecture

```text
YouTube (videos, captions)
        │
        ▼
  Captions, else Whisper → chunk text
        │
        ▼
  ┌─────────────┐   ┌──────────────┐   ┌─────────────┐
  │ Postgres    │   │ FAISS        │   │ SQLite      │
  │ + GCS text  │   │ embeddings   │   │ Places      │
  └─────────────┘   └──────────────┘   └─────────────┘
                           │
                           ▼
              Semantic search + Groq JSON
              LangGraph classify → patch
                           │
                           ▼
              Next.js: chat + day board + map
              Streamlit rollback on :8501
```

---

## Design choices (good interview talking points)

**Next.js is the product UI; Streamlit stays as rollback.** Same FastAPI (`/itinerary/v2`, `/itinerary/refine`). Clock times (08:00 / 13:00 / 18:00) are a **display mapping** from morning / afternoon / evening until the schema stores real clocks. Save is `localStorage` in this browser, not a share URL.

**Streamlit clarifying cards still exist on :8501.** Clicking Paris there does not call Groq twice. The UI asks length and vibe in two fixed turns, then composes a query like `3-day trip in Paris focused on food`. Extra LLM “interviewer” questions would burn quota and add latency.

**Patch, don’t regenerate.** `itinerary_patch.py` has no Groq import. Tests assert Day 1 is bit-for-bit unchanged when Day 2 morning is replaced.

**Hybrid retrieval.** Transcripts give messy, real trip texture. Places gives named restaurants/attractions. Taipei is the city where both are present.

**Groq model as config.** Groq retired `llama-3.1-8b-instant` (2026-08-16). The default is `openai/gpt-oss-20b` via `GROQ_MODEL` so a 404 is a one-line env fix, not a code hunt.

---

## API

| Method | Path | Body | Role |
| --- | --- | --- | --- |
| `GET` | `/health` | — | API up; whether LangGraph imported |
| `POST` | `/itinerary/v2` | `{ "query": "3-day trip in Taipei" }` | First itinerary |
| `POST` | `/itinerary/refine` | `{ "query", "feedback", "current_itinerary" }` | Surgical edit |

Refine payload `current_itinerary` is the **structured** JSON from the previous response, not the pretty-printed text.

---

## Repo map

```text
frontend/src                  Product UI (Next.js chat + board + map)
frontend/frontend.py           Streamlit rollback: cards, itinerary, refine
backend/main.py               FastAPI routes
backend/chat_generation.py    LangGraph generate + classify
backend/itinerary_patch.py    Splice one slot or one day
rag_pipeline.py                Groq JSON + day formatting
semantic_search.py             FAISS retrieve
backend/database/              Places SQLite + queries
tests/test_itinerary_patch.py  Patch invariants (no API)
```

---

## Run it locally

Reviewers: the **recording** is the demo. Local run needs a Groq key plus FAISS files that are gitignored (~84MB). You do **not** need GCS, Postgres, Whisper, YouTube, or Docker.

**Need**

1. Python **3.10+** (3.12 recommended). macOS `/usr/bin/python3` is often 3.9 and spaCy will fail.
2. [Groq](https://console.groq.com) API key.
3. In the **repo root** (`pack-and-go/`): `faiss_index.bin` and `metadata.pkl` (local artifacts; rebuild with `python indexing.py` if you have GCS transcripts).

First API start downloads MiniLM / FLAN-T5 weights and can take a few minutes.

### Env

```bash
cd pack-and-go
bash scripts/setup_venv.sh          # or: python3.12 -m venv venv
source venv/bin/activate
python -V                           # 3.10+, ideally 3.12.x
pip install --upgrade pip
pip install -r requirements.txt
python -m spacy download en_core_web_sm

cp .env.example .env
```

`.env` minimum:

```bash
GROQ_KEY=gsk_...
GROQ_MODEL=openai/gpt-oss-20b
BACKEND_URL=http://127.0.0.1:8000
```

### Terminals

Both from `pack-and-go/` with the venv on.

```bash
# terminal 1
source venv/bin/activate
uvicorn backend.main:app --reload --port 8000
```

Wait for `Application startup complete` and `Loaded FAISS index`.

```bash
# terminal 2 — product UI
cd frontend
cp -n .env.local.example .env.local
npm install
npm run dev
```

```bash
# optional — Streamlit rollback / recording demo
source venv/bin/activate
streamlit run frontend/frontend.py
```

- Product UI: [http://localhost:3000](http://localhost:3000)
- Streamlit demo: [http://localhost:8501](http://localhost:8501)
- Health: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

Then follow the same script as the recording (Taipei generate → Day 2 morning refine).

`docker compose up --build` also works; the venv path is the one used for the demo.

---

## Tests

No Groq, no network:

```bash
source venv/bin/activate
python -m unittest tests.test_itinerary_patch
```

---

Engineering log (bugs, ingest results, what we would change next): [`docs/challenges-and-changes.md`](docs/challenges-and-changes.md).

---

## Status

**In the demo**
- Next.js chat, day board, Leaflet map, localStorage save (`frontend/src`)
- Streamlit rollback: home, destination cards, itinerary + refine sidebar
- Groq itinerary JSON with Places context
- LangGraph refine + surgical JSON patch
- YouTube → captions/Whisper → GCS/Postgres → FAISS pipeline (offline)

**Intentionally not built**
- Auth or server-side share URLs (Save is this-browser `localStorage`)
- Real clock times / stop photos (08:00 / 13:00 / 18:00 are display-only)
- Places coverage beyond Taipei, Tainan, Taichung, and Peninsula
- Publishing the FAISS index (use the recording; rebuild locally if you have GCS)

---

## Offline pipelines (rebuild data)

Only if you are ingesting new videos or Places, not for the Streamlit click-through.

| Variable | For |
| --- | --- |
| `YOUTUBE_API_KEY` | YouTube Data API v3 |
| `GCS_BUCKET_NAME` | Transcript `.txt` objects |
| `GOOGLE_APPLICATION_CREDENTIALS` | Service account JSON that can write that bucket |
| `DATABASE_URL` | Default: `postgresql://packandgo:packandgo@localhost:5432/packandgo` |
| `GOOGLE_API_KEY` | Places Text Search |

```bash
docker compose up -d postgres
python create_tables.py

python data_generation.py Taipei --max-results 3   # captions, else Whisper
python indexing.py                                 # GCS → FAISS
python -m backend.database.populating_db Taipei
```

---

## Limits (known)

- Without `faiss_index.bin` + `metadata.pkl` in the repo root, the API fails while loading the index.
- Groq model IDs change; a `model_not_found` 404 means update `GROQ_MODEL`.
- The patch layer is deterministic; classification and generated JSON are not. Bad model output can still be a no-op or a wrong slot.
- First generate is slow (location tagging + Groq). Next and Streamlit wait up to 120s.
- Paris / Tokyo / Bali cards still generate; retrieval is only as good as what is in FAISS (Taipei is the intended demo city).
