import json
from datetime import datetime
from pathlib import Path

class QueryLogger:
    def __init__(self, log_path: str = "logs/queries.jsonl"):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
    
    def log(self, query: str, answer: str, chunks: list[dict]):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "answer": answer,
            "sources_used": [
                {
                    "source": c["metadata"]["source"],
                    "source_id": c["metadata"]["source_id"],
                    "header": c["metadata"].get("header"),
                    "distance": c.get("distance"),
                    "rerank_score": c.get("rerank_score"),
                }
                for c in chunks
            ],
            "source_distribution": self._count_sources(chunks),
        }
        
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    
    def _count_sources(self, chunks: list[dict]) -> dict:
        counts = {}
        for c in chunks:
            src = c["metadata"]["source"]
            counts[src] = counts.get(src, 0) + 1
        return counts