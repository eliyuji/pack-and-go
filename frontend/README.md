# Pack & Go — product UI

Next.js 15 app that talks to FastAPI. Streamlit (`frontend.py` in this folder) is the rollback demo on port 8501.

## Run

API must already be up (`uvicorn backend.main:app --reload --port 8000` from `pack-and-go/`).

```bash
cd frontend
cp -n .env.local.example .env.local
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

`NEXT_PUBLIC_BACKEND_URL` defaults to `http://127.0.0.1:8000`.

## What it calls

| Action | Endpoint |
| --- | --- |
| First trip | `POST /itinerary/v2` `{ query }` |
| Chat refine | `POST /itinerary/refine` `{ query, feedback, current_itinerary }` |

Clock times on the board (08:00 / 13:00 / 18:00) are a display mapping from morning / afternoon / evening. Save stays in this browser.

## Streamlit rollback

From `pack-and-go/` with the venv on:

```bash
streamlit run frontend/frontend.py
```
