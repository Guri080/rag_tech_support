import os
import sys
from pathlib import Path

from src.vectorstore import VectorEmbeddings
from src.chunker import header_chunks, forum_chunks, read_text_file
from src.llm import LLMClient
import src.config as config
from src.reranker import Reranker

class Retrieve():
    def __init__(self, vector_store):
        self.vs = vector_store
    
    def retrieve(self, query: str, n_results: int=10) -> list[dict]:
        raw_context = self.vs.query(query,
                                    n_results=n_results,)
        
        return [
            {
                "text": doc,
                "metadata": meta,
                "distance": dist
            } for doc, meta, dist in zip(raw_context['documents'][0], 
                                         raw_context['metadatas'][0],
                                         raw_context['distances'][0])
        ]

class RagPipeline():
    def __init__(self, vector_store, llm_client, retriever, reranker):
        self.vs = vector_store
        self.llm = llm_client
        self.retriever = retriever
        self.reranker = reranker
    
    def answer(self, query: str) -> dict:
        candidates = self.retriever.retrieve(query)
        chunks = self.reranker.rerank(query, candidates, top_k=5)

        context = "\n\n---\n\n".join([
            f"[Source: {c['metadata']['source']} | {c['metadata']['source_id']}]\n{c['text']}"
            for c in chunks
        ])

        system = "You are a technical support assistant. Answer the user's question using only the provided context. Cite which source each claim comes from. If the context doesn't contain the answer, say so."
        user = f"Context:\n{context}\n\nQuestion: {query}"
        
        answer = self.llm.generate(system, user)
        
        return {
            "query": query,
            "answer": answer,
            "chunks_used": chunks,
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
            all_chunks.extend(header_chunks(text, path.name, source_type="blogs"))

        # Forums
        for path in Path("data/forum").glob("*.md"):
            text = read_text_file(path)
            all_chunks.extend(forum_chunks(text, path.name, source_type="forums"))
        vs.reset()
        vs.add_chunks(all_chunks)
        print(f"Embedded {vs.count()} chunks")
    else:
        print(f"Using existing {vs.count()} chunks")
    
    # ---- retrieve ----
    llm_client = LLMClient()
    print('clinet loaded')
    retrival = Retrieve(vs)
    print('retrival done')
    reranker = Reranker()
    print('reranker done')
    myRag = RagPipeline(vs,
                      llm_client,
                      retrival,
                      reranker)
    print('rag done')
    query = " ".join(sys.argv[1:]) or "How do I configure timeouts?"
    result = myRag.answer(query)
    print('query done')

    print(f"Q: {result['query']}\n")
    print(f"A: {result['answer']}\n")
    print(f"Sources used:")
    for c in result['chunks_used']:
        print(f"  - {c['metadata']['source']}/{c['metadata']['source_id']} (distance: {c['distance']:.3f})")


        

