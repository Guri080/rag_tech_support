from src.vectorstore import VectorEmbeddings
from collections import Counter
vs = VectorEmbeddings()
data = vs.collection.get(limit=500)
print(Counter(m["source"] for m in data["metadatas"]))