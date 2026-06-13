import os
import sys
from pathlib import Path

from src.vectorstore import VectorEmbeddings
from src.chunker import header_chunks, forum_chunks, read_text_file
from src.llm import LLMClient
import src.config as config
from src.reranker import Reranker
from src.logger import QueryLogger
from src.contradiction import ContradictionDetector

import json

class Retrieve:
    def __init__(self, vector_store, llm_client):
        self.vs = vector_store
        self.llm = llm_client
    
    def classify_query(self, query: str) -> dict:
        """LLM-based per-source weights."""
        system = """You output JSON weight distributions for source selection.

        Three sources exist: docs, forum, blog.
        You output a JSON object with exactly these three keys, values are floats summing to 1.0.

        Examples:

        Query: "How do I configure the streaming engine?"
        Output: {"docs": 0.7, "forum": 0.2, "blog": 0.1}

        Query: "Anyone have a workaround for the backfill timeout bug?"
        Output: {"docs": 0.1, "forum": 0.8, "blog": 0.1}

        Query: "What's new in Tessera 2.1?"
        Output: {"docs": 0.2, "forum": 0.1, "blog": 0.7}

        Query: "Why does my watermark stall when one partition is idle?"
        Output: {"docs": 0.5, "forum": 0.4, "blog": 0.1}

        Rules:
        - Output ONLY the JSON object on a single line
        - No prose, no markdown, no other keys
        - Keys MUST be exactly: docs, forum, blog
        - Values MUST sum to 1.0"""

        user = f'Query: "{query}"\nOutput:'
        
        response = self.llm.generate(system, user)
        
        try:
            # strip markdown fences if model wraps in ```json
            cleaned = response.strip().replace("```json", "").replace("```", "").strip()
            weights = json.loads(cleaned)
            # sanity check to see if all keys present, weights sum approx. 1
            assert set(weights.keys()) == {"docs", "forum", "blog"}
            return weights
        except (json.JSONDecodeError, AssertionError, KeyError):
            # fallball to equal weights if LLM misbehaves
            print(f"Warning: LLM classification failed, falling back to equal weights. Response: {response[:200]}")
            return {"docs": 0.33, "forum": 0.34, "blog": 0.33}
    
    def retrieve(self, query: str, n_results: int = 20) -> list[dict]:
        weights = self.classify_query(query)
        all_chunks = []
        
        for source, weight in weights.items():
            per_source_n = max(2, int(n_results * weight))
            raw = self.vs.query(query, n_results=per_source_n, source_filter=source)
            
            for doc, meta, dist in zip(
                raw["documents"][0],
                raw["metadatas"][0],
                raw["distances"][0],
            ):
                all_chunks.append({
                    "text": doc,
                    "metadata": meta,
                    "distance": dist,
                    "source_weight": weight,
                })
        
        return all_chunks

class RagPipeline():
    """Full rag pipeline that feeds ranked chunks to the LLM"""
    def __init__(self, vector_store, llm_client, retriever, reranker, logger, contradiction):
        self.vs = vector_store
        self.llm = llm_client
        self.retriever = retriever
        self.reranker = reranker
        self.logger = logger
        self.contradiction_detector = contradiction
    
    def answer(self, query: str) -> dict:
        candidates = self.retriever.retrieve(query)
        chunks = self.reranker.rerank(query, candidates, top_k=5)
        
        # detect contradictions
        contradictions = self.contradiction_detector.detect(query, chunks)
        print(f"DEBUG: contradictions found: {len(contradictions)}")
        print(f"DEBUG: raw: {contradictions}")
    
        context = "\n\n---\n\n".join([
            f"[Source: {c['metadata']['source']} | {c['metadata']['source_id']}]\n{c['text']}"
            for c in chunks
        ])
        
        contradiction_note = ""
        if contradictions:
            contradiction_note = "\n\nIMPORTANT - the following contradictions were detected between sources:\n"
            for c in contradictions:
                contradiction_note += f"- {c['claim_a']} ({c['source_a']}) vs {c['claim_b']} ({c['source_b']}). {c['explanation']}\n"
            contradiction_note += "\nWhen answering, acknowledge these disagreements explicitly."

        system = "You are a technical support assistant. Answer using only the provided context. Cite sources for each claim. If sources disagree, surface the disagreement transparently — do not silently pick one."
        user = f"Context:\n{context}{contradiction_note}\n\nQuestion: {query}"
        
        answer = self.llm.generate(system, user)
        self.logger.log(query, answer, chunks)
        
        return {
            "query": query,
            "answer": answer,
            "chunks_used": chunks,
            "contradictions": contradictions,
        }

if __name__ == '__main__':
    #---- Generate chunks and embbed ----
    vs = VectorEmbeddings()

    if config.remake_embeddings or vs.count() == 0:
        all_chunks = []
        # Docs
        for path in Path("data/docs").glob("*.md"):
            text = read_text_file(path)
            all_chunks.extend(header_chunks(text, path.name, source_type="docs"))

        # Blogs
        for path in Path("data/blogs").glob("*.md"):
            text = read_text_file(path)
            all_chunks.extend(header_chunks(text, path.name, source_type="blog"))

        # Forums
        for path in Path("data/forum").glob("*.md"):
            text = read_text_file(path)
            all_chunks.extend(forum_chunks(text, path.name, source_type="forum"))
        vs.reset()
        vs.add_chunks(all_chunks)
        print(f"Embedded {vs.count()} chunks")
    else:
        print(f"Using existing {vs.count()} chunks")
    
    # ---- retrieve and provide content to model ----
    llm_client = LLMClient(model_name="gpt-oss-120b")
    retrival = Retrieve(vs, llm_client)
    reranker = Reranker()
    logger = QueryLogger()
    contradiction = ContradictionDetector(llm_client)

    myRag = RagPipeline(vs,
                      llm_client,
                      retrival,
                      reranker,
                      logger,
                      contradiction)
    print('rag done')
    query = " ".join(sys.argv[1:]) or "How do I configure timeouts?"
    result = myRag.answer(query)

    print(f"Q: {result['query']}\n")
    print(f"A: {result['answer']}\n")
    print(f"Sources used:")
    for c in result['chunks_used']:
        print(f"  - {c['metadata']['source']}/{c['metadata']['source_id']} (distance: {c['distance']:.3f})")