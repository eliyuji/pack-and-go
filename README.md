# PackAndGo 
## Core System Architecture 
```text
          ┌───────────────────────────────┐
          │          YouTube API           │
          │   (videos, metadata, captions) │
          └──────────────┬────────────────┘
                         │
                         ▼
              ┌───────────────────────┐
              │   Transcription/ETL   │
              │ - Whisper (if needed) │
              │ - Clean + chunk text  │
              └─────────────┬─────────┘
                            │
                            ▼
         ┌─────────────────────────────────────┐
         │              Database                │
         │ ┌──────────────┐   ┌──────────────┐ │
         │ │ Relational DB │   │  Vector DB   │ │
         │ │ (Postgres)    │   │ (Pinecone/   │ │
         │ │ Metadata:     │   │ Weaviate/    │ │
         │ │ - video URL   │   │ FAISS)       │ │
         │ │ - title, tags │   │ Embeddings   │ │
         │ └──────────────┘   │ of chunks    │ │
         │                     └──────────────┘ │
         └─────────────────────────────────────┘
                            │
                            ▼
             ┌───────────────────────────┐
             │  Retrieval + Generation   │
             │ - User query → embeddings │
             │ - Retrieve relevant text  │
             │ - LLM (GPT) generates     │
             │   itinerary/guide         │
             └─────────────┬─────────────┘
                           │
                           ▼
          ┌─────────────────────────────────┐
          │          Web Frontend           │
          │  - React/Next.js UI             │
          │  - Input prompt                 │
          │  - Display itinerary (timeline) │
          │  - Embed YouTube videos         │
          └─────────────────────────────────┘ 
