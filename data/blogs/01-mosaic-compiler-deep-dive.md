# One Definition, Two Execution Targets: How Mosaic Compiles

*By Priya Raghavan, Staff Engineer at Tessera. Posted to the Tessera Engineering Blog.*

A question we get every time someone new looks at Tessera: how does the same Mosaic definition actually run on both Flink and DuckDB? The marketing version is "guaranteed semantic parity." The engineering version is messier, more interesting, and worth writing down.

This post walks through the Mosaic compiler from the AST up. If you have ever wondered why your `tessera apply` takes three seconds instead of three hundred milliseconds, this is what it is doing in those three seconds.

## The shape of the problem

A feature definition in Mosaic is just Python. It uses our decorators and our operator types, but it parses as ordinary Python because that is what lets users edit it in PyCharm without inventing a new editor plugin.

```python
@feature(name="user_txn_count_30m", entity="user_id")
def user_txn_count_30m():
    return (
        transactions
        .group_by("user_id")
        .window(window.tumbling(minutes=30))
        .agg(count="count(*)")
    )
```

When the user calls this function (and we do call it, at apply time), they get back a Mosaic IR tree. Not a value, not a Pandas frame. A symbolic graph. That tree is what the rest of the pipeline operates on.

The naive design would be to write two backends, one that walks the tree emitting Flink Table API calls and one that walks the tree emitting DuckDB SQL, and call it a day. We tried this for about six months in early 2024. It was awful. Every new operator required two implementations, and the two implementations drifted, and we shipped at least one bug where the streaming and batch versions of the same feature produced subtly different sessionization results for events that fell exactly on a window boundary. That bug took eleven days to find.

## What we built instead

The Mosaic IR is lowered through three layers before reaching either target.

The first layer is the user-facing surface: `.group_by`, `.window`, `.agg`, `.join_as_of`, and so on. This is what users write.

The second layer is what we call canonical IR. It is roughly forty operators, all with explicit bitemporal semantics. The lowering from surface to canonical is the only place certain decisions are made. For example, `.window(tumbling(minutes=30))` in the surface becomes a canonical `TimeBucket` followed by a `BoundedAggregate`, with explicit `event_time_column` and `watermark_handling` arguments populated from the source's declared watermark policy. After this lowering, there is no ambiguity left for the backends to resolve differently.

The third layer is the target-specific physical plan. Flink gets a sequence of Table API operations. DuckDB gets a SQL string built from a template engine. Both are mechanical translations of the canonical IR, and crucially, neither makes semantic decisions. If a backend cannot directly express a canonical operator, it fails at compile time rather than silently choosing an interpretation.

The semantic parity guarantee, then, is really a claim about the canonical layer. We have a suite of about 1,400 parity tests that take canonical IR, run it through both backends against identical synthetic inputs, and assert bit-identical outputs. Those tests run on every commit to the compiler. They are slow (around 14 minutes on our CI) and we are not allowed to skip them on green-light merges. The eleven-day bug is the reason.

## Where the corners are sharp

Two things still bite us.

The first is the Python UDF problem, which most of you have probably hit. Flink's Python UDF support exists but pulls in a separate Python process per task slot and roughly halves throughput. We tried it for six months in 2023 and quietly removed it from the streaming path because the latency tail got too long. The replacement is the Mosaic stdlib: a curated set of operators we have hand-translated to both Flink Table API expressions and DuckDB scalar functions. It is, frankly, not as expressive as we want, and "rewrite this batch feature using Mosaic primitives" is a sentence that appears in our support channel more often than I would like. We are working on a wasm-based UDF execution path that we hope to land in 2.2.

The second is window functions on the Spark backfill adapter. For datasets above the DuckDB ceiling (around 2 TB) we fall back to Spark, and Spark's window function semantics around timezone-naive timestamps differ from Flink's in ways that are not always catchable at compile time. We document this as a "parity guarantee weakens slightly" caveat and we hate it. The 2.1 release tightens this considerably (more on that from the release team), but it is the closest thing we have to an open wound in the codebase.

## What this buys you

If you have read this far, the practical upshot is: when you write a Mosaic feature and Tessera tells you the compile succeeded, you can rely on the streaming and backfill results matching, with the two caveats above. We earn that guarantee by spending compile-time cycles on canonicalization that most feature stores skip.

The next time `tessera apply` takes three seconds on a complex feature, that is the parity test suite running locally before submission. You are welcome to complain about it. I will not change it.

*Comments and questions welcome on our community Slack. The compiler source lives in `tessera-core/mosaic/compiler`; PRs to the stdlib are particularly welcome since we are perennially short of contributors there.*
