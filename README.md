# Pack & Go

RAG travel planner: YouTube travel videos → transcript chunks → a day-by-day itinerary you can **edit one slot at a time**.

Ask for a 3-day trip, get morning / afternoon / evening plans with food suggestions, then change **one** slot in chat. The rest of the trip stays put.

## The interesting part

Most itinerary chat demos **regenerate the whole trip** on every message. Pack & Go treats refine as a patch:

1. LangGraph classifies intent (one activity, one day, or a global vibe).
2. Groq proposes the new JSON for **only that piece**.
3. [`backend/itinerary_patch.py`](backend/itinerary_patch.py) splices it into the existing itinerary. Other days/slots are copied, not rewritten.

That last step is deterministic and unit-tested. The LLM can still mis-classify; the splice will not silently rewrite Day 1 because you asked about Day 2 morning.

Retrieval is hybrid:

- **FAISS** over YouTube transcript chunks (what vloggers actually did).
- **SQLite Places** for city/district attractions and food. 
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
