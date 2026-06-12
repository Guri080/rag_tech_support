import chromadb
from chromadb.utils import embedding_functions

class VectorEmbeddings():
    def __init__(self,
                 persistant_path: str = "chroma_db_embeddings",
                 collection_name: str = "documents_collection",
                 embedding_model: str = "all-MiniLM-L6-v2"
                 ):
        # initialize ChromaDB client with persistence
        self.client = chromadb.PersistentClient(path=persistant_path)
        self.collection_name = collection_name
        # configure sentence transformer embeddings
        self.sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=embedding_model
        )

        # create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.sentence_transformer_ef
        )
    
    def add_chunks(self, chunks: list[dict]) -> None:
        """Add additional chunks to the collection"""
        if not chunks:
            return
        
        ids = []
        for i, chunk in enumerate(chunks):
            # Build id from source + source_id + a discriminator from metadata
            meta = chunk.get("metadata", {})
            discriminator = meta.get("sub_chunk", meta.get("post_index", i))
            ids.append(f"{chunk['source']}__{chunk['source_id']}__{discriminator}__{i}")
        
        self.collection.add(
            documents=[c["text"] for c in chunks],
            ids=ids,
            metadatas=[{
                "source": c["source"],
                "source_id": c["source_id"],
                **{k: v for k, v in c.get("metadata", {}).items() if isinstance(v, (str, int, float, bool))}
            } for c in chunks],
        )

    def query(
        self,
        query_text: str,
        n_results: int = 10,
        source_filter: str | None = None,
    ) -> dict:
        """query the embedding space and extract top n cloest results"""
        where = {"source": source_filter} if source_filter else None
        return self.collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=where,
        )

    def count(self) -> int:
        """count the number of embeddings present in the collection"""
        return self.collection.count()

    def reset(self) -> None:
        """Delete and recreate the collection"""
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self.sentence_transformer_ef,
        )