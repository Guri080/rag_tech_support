# from src.vectorstore import VectorEmbeddings
# from collections import Counter
# vs = VectorEmbeddings()
# data = vs.collection.get(limit=500)
# print(Counter(m["source"] for m in data["metadatas"]))
import sys

assert sys.argv[1:] != [], f"please provide a query in CLI"
print(sys.argv[1:])
print("done")