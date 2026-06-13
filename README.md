# Multi-Source RAG for Technical Support

A RAG system that answers questions about a fictional software product (Tessera, a streaming feature store) by pulling from three different knowledge sources: official docs, user forum threads, and engineering blog posts.

The interesting part isn't just retrieval. The three sources sometimes disagree with each other (on purpose), so the system also weighs sources per query, reranks results, and flags contradictions instead of silently picking one answer.

## What it does

- Loads docs, forums, and blogs and chunks each one differently
- Embeds everything into a Chroma vector store
- For each query, asks an LLM which sources to trust more, then retrieves from each
- Reranks the candidates with a cross-encoder
- Checks the top chunks for contradictions before answering
- Logs which sources were used for every query

## Stack

- sentence-transformers for embeddings (all-MiniLM-L6-v2) and reranking (bge-reranker-base)
- chromadb for the vector store
- OpenAI gpt-4.1-mini for classification, contradiction detection, and answers
- No LangChain framework. Chunking is hand written so the logic stays readable.

## Setup

1. Make a virtual env and activate it
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and drop in your OpenAI key

```
OPENAI_API_KEY=sk-...
```

## Building the vector store

The store is built once and reused. First time, set `remake_embeddings = True` in `src/config.py`, run any query, then set it back to `False`.

If you change the chunking logic or the embedding model, delete `chroma_db_embeddings/` and rebuild, otherwise you'll mix old and new chunks.

## Running it

Single query:

```
python -m src.pipeline "How do I configure the streaming engine?"
```

Run the full example set (13 queries covering routing, contradictions, and out-of-scope):

```
python -m evaluation.run_examples
```

## Where things are

```
chroma_db_embeddings/   chunk vector embeddings
data/                   the three source folders (docs, blogs, forum)
 | blogs/
 | docs/
 | forum/
src/
 | chunker.py               per-source chunking
 | vectorstore.py           chroma wrapper
 | pipeline.py              retrieval + weighting + the full pipeline
 | reranker.py              cross-encoder reranking
 | contradiction.py         contradiction detection
 | llm.py                   openai client wrapper
 | logger.py                jsonl query logging
evaluation/             example queries and their outputs
logs/                   queries.jsonl, one line per query
```

## Outputs

- `logs/queries.jsonl` gets a line per query with the sources used, distances, and any contradictions found
- `evaluation/example_outputs.md` is the readable run of all the example queries