import json
from datetime import datetime
from pathlib import Path
from src.pipeline import RagPipeline, Retrieve, build_chunks
from src.vectorstore import VectorEmbeddings
from src.llm import LLMClient
import src.config as config
from src.reranker import Reranker
from src.logger import QueryLogger
from src.contradiction import ContradictionDetector


# Each query is tagged with what it is meant to demonstrate, so the report
# can group results by capability rather than treating them as a flat list.
EXAMPLE_QUERIES = [
    # --- Source routing: should weight a single source highly ---
    {"query": "How do I configure the streaming engine?",
     "category": "routing", "expected_source": "docs"},
    {"query": "What's the workaround for implementing a piecewise calibration curve in a streaming feature?",
     "category": "routing", "expected_source": "forum"},
    {"query": "What's new in Tessera 2.1?",
     "category": "routing", "expected_source": "blog"},
    {"query": "Why do watermark stalls happen and how do I fix them?",
     "category": "routing", "expected_source": "docs"},

    # --- Contradiction detection: maps to the known-contradiction audit ---
    {"query": "Has the batched lineage endpoint shipped in Tessera 2.1?",
     "category": "contradiction", "expected_source": "blog/forum"},
    {"query": "What does passing depth=-1 to the lineage endpoint do?",
     "category": "contradiction", "expected_source": "docs/blog"},
    {"query": "How do I rollback a feature promotion in Tessera 2.0?",
     "category": "contradiction", "expected_source": "docs/blog"},
    {"query": "Does Mosaic support count(distinct ...)?",
     "category": "contradiction", "expected_source": "blog/docs"},
    {"query": "When does Tessera 2.1 reach GA?",
     "category": "contradiction", "expected_source": "blog"},

    # --- Clean single-source factual answers ---
    {"query": "What are the default backfill engine and memory limits?",
     "category": "factual", "expected_source": "docs"},
    {"query": "What is the Spark adapter parity test pass rate?",
     "category": "factual", "expected_source": "forum/blog"},

    # --- Out of scope: system should admit it doesn't know, not hallucinate ---
    {"query": "How do I integrate Tessera with Snowflake?",
     "category": "out_of_scope", "expected_source": "none"},
    {"query": "What is the pricing for Tessera enterprise?",
     "category": "out_of_scope", "expected_source": "none"},
]


def run_all(pipeline) -> list[dict]:
    """Run every example query and collect structured results."""
    results = []

    for i, item in enumerate(EXAMPLE_QUERIES, start=1):
        query = item["query"]
        print(f"[{i}/{len(EXAMPLE_QUERIES)}] {query}")

        result = pipeline.answer(query)

        # Distribution of sources among the chunks actually used
        source_dist = {}
        for c in result["chunks_used"]:
            src = c["metadata"]["source"]
            source_dist[src] = source_dist.get(src, 0) + 1

        results.append({
            "category": item["category"],
            "expected_source": item["expected_source"],
            "query": query,
            "answer": result["answer"],
            "source_distribution": source_dist,
            "sources_used": [
                {
                    "source": c["metadata"]["source"],
                    "source_id": c["metadata"]["source_id"],
                    "distance": round(c.get("distance", 0.0), 3),
                }
                for c in result["chunks_used"]
            ],
            "contradictions": result.get("contradictions", []),
        })

    return results


def write_markdown(results: list[dict], path: Path) -> None:
    """Write a readable report of all query results."""
    lines = [
        "# Example Query Outputs",
        f"\n_Generated: {datetime.now().isoformat()}_",
        f"\nTotal queries: {len(results)}\n",
    ]

    for i, r in enumerate(results, start=1):
        lines.append(f"\n---\n\n## {i}. {r['query']}")
        lines.append(f"\n**Category:** {r['category']}  ")
        lines.append(f"**Expected source:** {r['expected_source']}  ")
        lines.append(f"**Source distribution:** {r['source_distribution']}\n")

        lines.append(f"**Answer:**\n\n{r['answer']}\n")

        lines.append("**Sources used:**\n")
        for s in r["sources_used"]:
            lines.append(f"- {s['source']}/{s['source_id']} (distance: {s['distance']})")

        if r["contradictions"]:
            lines.append("\n**Contradictions detected:**\n")
            for c in r["contradictions"]:
                lines.append(f"- {c.get('claim_a', '')}")
                lines.append(f"  - vs {c.get('claim_b', '')}")
                lines.append(f"  - {c.get('explanation', '')}")
        else:
            lines.append("\n**Contradictions detected:** none")

        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    out_dir = Path("evaluation")
    out_dir.mkdir(parents=True, exist_ok=True)

    #---- Generate chunks and embbed ----
    vs = VectorEmbeddings()

    if config.remake_embeddings or vs.count() == 0:
        all_chunks = build_chunks()
        vs.reset()
        vs.add_chunks(all_chunks)
        print(f"Embedded {vs.count()} chunks")
    else:
        print(f"Using existing {vs.count()} chunks")
    
    ## Init the pipeline services
    llm_client = LLMClient(model_name=config.base_llm)
    retrival = Retrieve(vs, llm_client)
    reranker = Reranker()
    logger = QueryLogger()
    contradiction = ContradictionDetector(llm_client)

    # feed the services to the pipeline
    myRag = RagPipeline(vs,
                      llm_client,
                      retrival,
                      reranker,
                      logger,
                      contradiction)


    results = run_all(myRag)

    write_markdown(results, out_dir / "example_outputs.md")
    (out_dir / "example_outputs.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )

    # Quick summary to console
    contradiction_hits = sum(1 for r in results if r["contradictions"])
    print(f"\nDone. {len(results)} queries run.")
    print(f"Contradictions surfaced in {contradiction_hits} queries.")
    print("Outputs written to evaluation/example_outputs.md and .json")


if __name__ == "__main__":
    main()