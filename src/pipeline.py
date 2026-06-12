import os
from pathlib import Path
from src.vectorstore import VectorEmbeddings
from src.chunker import header_chunks, forum_chunks, read_text_file
# from src.llm import LLMCLient
import src.config as config

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
        for path in Path("data/forums").glob("*.md"):
            text = read_text_file(path)
            all_chunks.extend(forum_chunks(text, path.name))
        vs.reset()
        vs.add_chunks(all_chunks)
        print(f"Embedded {vs.count()} chunks")
    else:
        print(f"Using existing {vs.count()} chunks")
    
    # ---- retrieve ----
    retrival = Retrieve(vs)

    top_k = retrival.retrieve("How do I configure timeouts?")

    [print(k) for k in top_k]
    

