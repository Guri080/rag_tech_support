import json
import src.config as config

class ContradictionDetector:
    def __init__(self, llm_client):
        self.llm = llm_client
    
    def detect(self, query: str, chunks: list[dict]) -> list[dict]:
        if len(chunks) < 2:
            return []
        
        context = "\n\n".join([
            f"[Chunk {i+1}] (source: {c['metadata']['source']}, file: {c['metadata']['source_id']})\n{c['text']}"
            for i, c in enumerate(chunks)
        ])
        
        system = """You analyze retrieved knowledge-base chunks for factual contradictions and output JSON.

        A contradiction exists when two chunks make conflicting factual claims about the same thing: different default values, opposite behaviors, mutually exclusive recommendations, or different version-specific facts (e.g., "X has shipped" vs "X is planned").

        Examples:

        Input chunks:
        [Chunk 1] (docs): The default timeout is 30 seconds.
        [Chunk 2] (forum): The default timeout is actually 10 seconds in practice.

        Output:
        {"contradictions": [{"claim_a": "default timeout is 30 seconds", "source_a": "Chunk 1 (docs)", "claim_b": "default timeout is 10 seconds in practice", "source_b": "Chunk 2 (forum)", "explanation": "Docs and user reports disagree on the actual default value."}]}

        Input chunks:
        [Chunk 1] (docs): To install, run pip install foo.
        [Chunk 2] (blog): Foo supports Python 3.10+.

        Output:
        {"contradictions": []}

        Rules:
        - Output ONLY a JSON object, no prose, no markdown
        - The object must have exactly one key: "contradictions" (a list)
        - Each contradiction must have: claim_a, source_a, claim_b, source_b, explanation
        - If no contradictions exist, return {"contradictions": []}"""

        user = f"Input chunks:\n\n{context}\n\nOutput:"
        
        response = self.llm.generate(system, user)
        if config.debug_rag:
            print(f"DEBUG contradiction raw response (first 500 chars):\n{response[:500]}\n")
        
        try:
            cleaned = response.strip().replace("```json", "").replace("```", "").strip()
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start == -1 or end == -1:
                print("DEBUG: no JSON found in response")
                return []
            cleaned = cleaned[start:end+1]
            
            result = json.loads(cleaned)
            contradictions = result.get("contradictions", [])
            print(f"DEBUG: parsed {len(contradictions)} contradictions")
            return contradictions
        except Exception as e:
            print(f"DEBUG: parse exception: {e}")
            return []