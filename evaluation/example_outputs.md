# Example Query Outputs

_Generated: 2026-06-13T11:08:20.115893_

Total queries: 13


---

## 1. How do I configure the streaming engine?

**Category:** routing  
**Expected source:** docs  
**Source distribution:** {'docs': 5}

**Answer:**

To configure the streaming engine, you need to set up and provide a Flink cluster version 1.17 or later, as the streaming materialization runs as Flink jobs submitted by the control plane ([installation.md](#Streaming-workers)). 

The actual configuration of the Flink jobs is controlled through several configuration keys, including:

- `flink.jobManagerUrl`: URL of the Flink job manager REST endpoint (required).
- `flink.defaultParallelism`: Default parallelism for newly submitted streaming jobs, default is 4.
- `flink.checkpointIntervalSeconds`: Checkpoint interval for all Tessera-managed jobs, default is 60 seconds.
- `flink.checkpointStorage`: URI for checkpoint storage (required), for example, a URI on S3.
- `flink.restartStrategy`: Job restart strategy, defaults to `exponential-delay`.
- `flink.taskSlotsPerFeature`: Default task slots assigned to a single feature job, default is 2.

These configuration keys control the Flink job submission path and can be set according to your event volume and job sizing needs ([configuration.md](#Streaming-Configuration)).

Additionally, before starting, ensure that your Flink cluster is properly running and accessible, alongside other prerequisites like Kafka or Kinesis cluster, an online store reachable from the control plane, and Python 3.10+ for feature authoring ([getting-started.md](#Prerequisites)).

**Sources used:**

- docs/troubleshooting.md (distance: 0.581)
- docs/installation.md (distance: 0.515)
- docs/configuration.md (distance: 0.552)
- docs/getting-started.md (distance: 0.6)
- docs/installation.md (distance: 0.743)

**Contradictions detected:** none


---

## 2. What's the workaround for implementing a piecewise calibration curve in a streaming feature?

**Category:** routing  
**Expected source:** forum  
**Source distribution:** {'forum': 3, 'docs': 2}

**Answer:**

The recommended workaround for implementing a piecewise calibration curve in a streaming feature is to use the `tessera.transform.piecewise_linear` function available in the standard library as of Mosaic 1.9. This function is specifically designed for such cases and compiles cleanly to streaming, avoiding the need to rewrite complex logic as a long chain of `case when` statements, which can be unwieldy and hard to review.

This approach is advised since Mosaic does not support arbitrary Python UDFs in streaming mode, and the standard solution is to express logic using Mosaic primitives or functions from the Tessera standard library. The `piecewise_linear` transform is a suitable primitive for piecewise calibration curves with multiple breakpoints.

Supporting details:

- Arbitrary Python UDFs are not supported in streaming features due to compilation constraints into Flink (docs/troubleshooting.md).
- A staff member confirms a wasm-based UDF execution path is in early R&D but not yet available (forum Thread 4).
- The specific callout to `tessera.transform.piecewise_linear` as a direct solution to piecewise calibration curves was given by staff Jonas in response to the same question (forum Thread 4).

Therefore, to implement your logistic transformation with multiple breakpoints in streaming, use `tessera.transform.piecewise_linear` in your feature definition rather than arbitrary Python UDFs or overly long `case when` chains. This will compile correctly and maintain lineage visibility.

Sources:  
- forum Thread 4 (tessera_staff_jonas reply 2024-09-02)  
- docs troubleshooting.md (UNSUPPORTED_UDF limitation)

**Sources used:**

- forum/tessera-forum-threads.md (distance: 0.467)
- forum/tessera-forum-threads.md (distance: 0.441)
- forum/tessera-forum-threads.md (distance: 0.691)
- docs/troubleshooting.md (distance: 0.685)
- docs/getting-started.md (distance: 0.743)

**Contradictions detected:** none


---

## 3. What's new in Tessera 2.1?

**Category:** routing  
**Expected source:** blog  
**Source distribution:** {'blog': 5}

**Answer:**

Tessera 2.1 introduces several notable new features and improvements over the 2.0 release:

1. A new `tessera feature promote --rollback` command that allows rolling back to a previous version even after promotion, without needing to re-apply the old definition. This fixes the operational annoyance in 2.0 where rollback after the TTL window expiration required manual re-application of the old feature definition [blog | 08-shadow-serving-tutorial.md].

2. Native shadow comparison support for vector features. In 2.0, shadow vector features could be registered but the shadow comparison report was not meaningful. Tessera 2.1 adds centroid drift and dimension-wise Population Stability Index (PSI) metrics to the report for vector features, which is particularly useful for embedding serving use cases [blog | 08-shadow-serving-tutorial.md].

3. A new backfill cost estimator with a configurable threshold. Upgrading to 2.1 includes one configuration change for this estimator, which has a sensible default but can be tuned by users [blog | 05-announcing-2-1.md].

4. General focus on smoothing out rough edges that led to the most support tickets earlier in the year. The 2.1 release is the largest update since 2.0 and emphasizes improvements in operational experience and parity with Apache Spark where possible [blog | 05-announcing-2-1.md].

5. The release is backward-compatible with 2.0 and can be upgraded via `helm upgrade` commands [blog | 05-announcing-2-1.md].

In summary, the key new capabilities are better rollback operations, enhanced shadow serving reports for embeddings, and the addition of a cost estimator, all aimed at increased polish and operational ease [blog | 05-announcing-2-1.md][blog | 08-shadow-serving-tutorial.md].

**Sources used:**

- blog/05-announcing-2-1.md (distance: 0.275)
- blog/05-announcing-2-1.md (distance: 0.405)
- blog/08-shadow-serving-tutorial.md (distance: 0.408)
- blog/05-announcing-2-1.md (distance: 0.448)
- blog/08-shadow-serving-tutorial.md (distance: 0.486)

**Contradictions detected:** none


---

## 4. Why do watermark stalls happen and how do I fix them?

**Category:** routing  
**Expected source:** docs  
**Source distribution:** {'docs': 2, 'blog': 2, 'forum': 1}

**Answer:**

Watermark stalls happen when the feature values lag behind the upstream Kafka topic significantly (by minutes or hours), causing the per-feature staleness SLO to trigger repeatedly. This usually occurs for two main reasons:

1. A source whose `watermark_delay` is configured too low compared to the actual event-time skew, meaning the system expects events to arrive more promptly than they actually do.
2. A partition of the Kafka source that is idle or has no data at all, preventing watermark advancement.

To fix watermark stalls, the recommended steps are:

- Inspect the source watermark using the CLI command `tessera source describe <name>` to check state and identify whether an idle partition is causing the stall.
- If you find an idle partition, set the `idle_partition_timeout` on the source. This instructs Tessera to advance the watermark even when no data arrives on that partition.
- If you determine that the actual event-time skew is larger than expected, increase the `watermark_delay`. Note that this trades some end-to-end latency for completeness.
- Use the `--diagnose` flag with `tessera source describe` or `tessera feature describe` commands to get hypotheses about why a feature is not advancing, which helps pinpoint issues without digging into Flink logs.

These recommendations come from the official troubleshooting documentation and blog posts explaining common causes and diagnostic steps for watermark stalls ([docs | troubleshooting.md], [blog | 05-announcing-2-1.md]).

**Sources used:**

- docs/troubleshooting.md (distance: 0.481)
- blog/05-announcing-2-1.md (distance: 0.49)
- forum/tessera-forum-threads.md (distance: 0.767)
- docs/troubleshooting.md (distance: 0.795)
- blog/04-backfill-postmortem.md (distance: 0.688)

**Contradictions detected:** none


---

## 5. Has the batched lineage endpoint shipped in Tessera 2.1?

**Category:** contradiction  
**Expected source:** blog/forum  
**Source distribution:** {'blog': 2, 'forum': 1, 'docs': 2}

**Answer:**

There is conflicting information regarding whether the batched lineage endpoint has shipped in Tessera 2.1:

- According to the blog source on lineage graph deep dive, initially there was no batch lineage endpoint, meaning if you wanted lineage for 200 features, you had to make 200 calls. However, it also says that the batch endpoint was on the 2.1 roadmap and, in an update, notes that it landed in the 2.1 general availability (GA) release. A colleague reportedly confirmed it works as advertised ([Source: blog | 06-lineage-graph-deep-dive.md]).

- In contrast, a forum reply from Tessera staff states that the batch lineage endpoint is on the longer-term roadmap and explicitly says it is *not* in 2.1 (which is locked), nor can they promise it in 2.2 without more discussion ([Source: forum | tessera-forum-threads.md]).

Thus, there is a contradiction:
- Blog source claims the batch lineage endpoint shipped in 2.1 GA.
- Forum staff states it is not part of 2.1 and is planned for the longer term.

Given this disagreement, it is unclear from the provided information whether the batch lineage endpoint is actually available in Tessera 2.1. If you need this feature, you might want to verify directly with Tessera support or the latest Tessera documentation to confirm its availability.

**Sources used:**

- blog/06-lineage-graph-deep-dive.md (distance: 0.324)
- blog/05-announcing-2-1.md (distance: 0.363)
- forum/tessera-forum-threads.md (distance: 0.49)
- docs/api-reference.md (distance: 0.475)
- docs/getting-started.md (distance: 0.522)

**Contradictions detected:**

- There is no batch lineage endpoint. If you want lineage for 200 features, you make 200 calls. The Tessera team confirmed a batch endpoint was on the 2.1 roadmap. (Update: it landed in 2.1 GA. I have not used it yet but my colleague has and reports it works as advertised.)
  - vs This is on the longer-term roadmap. We've talked about it for a while and there's broad agreement internally that it should exist. It's not in 2.1 (which is locked) and I can't promise 2.2 without more discussion...
  - Chunk 1 states a batch lineage endpoint landed in 2.1 GA, whereas Chunk 3 states it is not in 2.1 (which is locked) and remains on the longer-term roadmap, indicating conflicting information about the batch lineage endpoint availability in version 2.1.


---

## 6. What does passing depth=-1 to the lineage endpoint do?

**Category:** contradiction  
**Expected source:** docs/blog  
**Source distribution:** {'docs': 2, 'blog': 1, 'forum': 2}

**Answer:**

Passing `depth=-1` to the lineage endpoint is documented to mean "unbounded" depth, intended to traverse the entire lineage graph without a fixed maximum number of hops from the target feature [api-reference.md]. However, in practice, `depth=-1` does not truly allow an unlimited traversal because the system enforces a configured maximum traversal depth, which defaults to 25. When this maximum is exceeded, the query returns a `400 DEPTH_TOO_DEEP` error [troubleshooting.md].

Additionally, a firsthand account from the blog clarifies that although `depth=-1` should mean unbounded, it actually returns `DEPTH_TOO_DEEP` if the traversal exceeds the cluster maximum depth (default 25). The operational decision to keep this limit exists for good reasons, and users are advised to paginate manually by walking through the graph one layer at a time [06-lineage-graph-deep-dive.md].

Notably, forum reports indicate that in real usage, trying depths greater than 10 or 11 often results in timeouts, well before reaching the documented max depth of 25. This reveals a practical limitation that the documented maximum depth of 25 is a configuration ceiling rather than a guaranteed achievable depth without performance issues. The staff confirms that the number 25 is a configured limit but not a performance guarantee and suggests pagination as a workaround until future improvements arrive in version 2.1 [tessera-forum-threads.md].

In summary, passing `depth=-1` signals an unbounded request, but in reality it is capped by a default maximum depth (25), beyond which a `DEPTH_TOO_DEEP` error is returned. Due to performance constraints, in practice much smaller depths (around 10-11) are achievable before timeouts occur, so manual pagination is recommended for deep traversals. This discrepancy between documentation and practical experience is acknowledged by official staff and slated for improvement in upcoming versions.

**Sources used:**

- docs/troubleshooting.md (distance: 0.462)
- blog/06-lineage-graph-deep-dive.md (distance: 0.536)
- forum/tessera-forum-threads.md (distance: 0.356)
- docs/api-reference.md (distance: 0.534)
- forum/tessera-forum-threads.md (distance: 0.59)

**Contradictions detected:**

- The configured maximum traversal depth (default 25) was exceeded
  - vs depth=25 number in the docs is the configured limit, not a performance guarantee; in practice requests time out past depth 10-11
  - Docs state max depth default is 25 and exceeding causes DEPTH_TOO_DEEP; forum reports show practical timeouts at depth >10-11, indicating the 25 limit is not achievable in practice.


---

## 7. How do I rollback a feature promotion in Tessera 2.0?

**Category:** contradiction  
**Expected source:** docs/blog  
**Source distribution:** {'docs': 3, 'blog': 1, 'forum': 1}

**Answer:**

In Tessera 2.0, rollback after promoting a feature requires re-applying the old feature definition manually. This is because the `tessera feature promote --rollback` command that allows rollback after promotion was introduced in version 2.1. Without this command in 2.0, to rollback, you must re-apply the old version's feature definition to revert changes.

This operational step is a known limitation and can be inconvenient compared to the improved rollback in 2.1:

> "In 2.0, rollback after the TTL window has expired requires re-applying the old definition. This is operationally annoying and the 2.1 change is welcome."  
> [Source: blog | 08-shadow-serving-tutorial.md]

So to rollback in 2.0:

1. Retrieve the previous feature definition.
2. Re-apply it using `tessera apply` or equivalent commands.

There is no built-in rollback command post-promotion in Tessera 2.0.

**Sources used:**

- docs/troubleshooting.md (distance: 0.418)
- blog/08-shadow-serving-tutorial.md (distance: 0.368)
- forum/tessera-forum-threads.md (distance: 0.461)
- docs/installation.md (distance: 0.543)
- docs/api-reference.md (distance: 0.545)

**Contradictions detected:** none


---

## 8. Does Mosaic support count(distinct ...)?

**Category:** contradiction  
**Expected source:** blog/docs  
**Source distribution:** {'docs': 3, 'forum': 1, 'blog': 1}

**Answer:**

The provided context does not explicitly mention support or lack thereof for `count(distinct ...)` in Mosaic feature definitions.

However, general information about Mosaic's compilation and supported operations indicates:

- Mosaic feature definitions compile to a symbolic intermediate representation (IR) that must be compatible with Flink execution, especially for streaming features. (From blog | 01-mosaic-compiler-deep-dive.md)

- Features must use a whitelisted set of primitives and aggregations. Custom Python UDFs are not allowed in streaming mode; only certain known aggregations and primitives (including those from NumPy and Tessera stdlib) are supported. (From docs | troubleshooting.md)

Given this, and the example aggregation shown:

```python
transactions
    .group_by("user_id")
    .window(window.tumbling(minutes=30))
    .agg(count="count(*)")
```

Mosaic supports standard aggregations like `count(*)` but the documentation and examples do not demonstrate explicit support for `count(distinct ...)`.

No direct citation confirms or denies `count(distinct ...)` support. The absence of mention and emphasis on limited supported operations suggests it may not be directly supported or may require specific Mosaic primitives or Tessera helpers if available.

**Summary:**  
There is no explicit confirmation in the provided context that Mosaic supports `count(distinct ...)`. Given Mosaic's compilation constraints and the examples, standard aggregations like `count(*)` are supported, but distinct counting is not clearly mentioned and may not be supported or could require special handling.

If counting distinct values is essential, it might require a custom approach or be limited to batch-only features, as some complex logic isn't supported in streaming mode due to UDF restrictions (docs | troubleshooting.md). You may want to consult more detailed Mosaic documentation or contact support for confirmation.

**Sources used:**

- docs/troubleshooting.md (distance: 0.7)
- forum/tessera-forum-threads.md (distance: 0.793)
- blog/01-mosaic-compiler-deep-dive.md (distance: 0.588)
- docs/configuration.md (distance: 0.714)
- docs/configuration.md (distance: 0.715)

**Contradictions detected:** none


---

## 9. When does Tessera 2.1 reach GA?

**Category:** contradiction  
**Expected source:** blog  
**Source distribution:** {'blog': 2, 'docs': 2, 'forum': 1}

**Answer:**

Tessera 2.1 reaches general availability next month from the time of the blog post. The blog post announcing Tessera 2.1 is dated 05-announcing-2-1.md, but the exact posting date is not provided in the context. However, it states: "Tessera 2.1 enters general availability next month." [Source: blog | 05-announcing-2-1.md]

**Sources used:**

- blog/05-announcing-2-1.md (distance: 0.312)
- docs/installation.md (distance: 0.414)
- blog/07-why-we-left.md (distance: 0.358)
- forum/tessera-forum-threads.md (distance: 0.427)
- docs/api-reference.md (distance: 0.45)

**Contradictions detected:** none


---

## 10. What are the default backfill engine and memory limits?

**Category:** factual  
**Expected source:** docs  
**Source distribution:** {'docs': 5}

**Answer:**

The default backfill engine is `duckdb`, and the default per-worker memory limit for DuckDB backfill workers is `24GiB` (24 gigabytes). This is specified in the `backfill.engine` and `backfill.duckdb.memoryLimit` configuration keys, respectively, with their default values shown as `duckdb` and `24GiB` ([source](docs | configuration.md)).

**Sources used:**

- docs/configuration.md (distance: 0.373)
- docs/troubleshooting.md (distance: 0.552)
- docs/installation.md (distance: 0.45)
- docs/installation.md (distance: 0.647)
- docs/api-reference.md (distance: 0.608)

**Contradictions detected:** none


---

## 11. What is the Spark adapter parity test pass rate?

**Category:** factual  
**Expected source:** forum/blog  
**Source distribution:** {'forum': 2, 'docs': 3}

**Answer:**

The Spark adapter parity test pass rate for version 2.1 is 1,397 out of 1,400 tests passing, a significant improvement over version 2.0, which had about 1,340 out of 1,400 tests passing. The few remaining failures in 2.1 (3 tests) are around daylight saving time (DST) transitions for time-zoned sources [forum | tessera-forum-threads.md].

However, it's important to note that although the documentation states the semantic-parity guarantee "weakens slightly around timezone handling" with the Spark adapter, real user reports describe much worse parity issues — for example, around 1.3% of session boundaries disagree between streaming and backfill outputs for large datasets using Spark, especially when event timestamps lack explicit UTC timezones [forum | tessera-forum-threads.md]. This indicates that the docs may understate the practical severity of the parity problem despite the relatively high test pass rate.

**Sources used:**

- forum/tessera-forum-threads.md (distance: 0.744)
- docs/configuration.md (distance: 0.614)
- docs/troubleshooting.md (distance: 0.641)
- forum/tessera-forum-threads.md (distance: 0.733)
- docs/installation.md (distance: 0.609)

**Contradictions detected:**

- backfill.timezoneStrict default is true, making Spark refuse ambiguous timestamps
  - vs docs say 'the semantic-parity guarantee weakens slightly around timezone handling in window functions' on Spark adapter
  - Chunk 4 reports severe parity issues with Spark backfill adapter timezone handling, contrasting with docs characterizing the issue as only 'slightly' weakening; this implies the docs understate the problem severity.


---

## 12. How do I integrate Tessera with Snowflake?

**Category:** out_of_scope  
**Expected source:** none  
**Source distribution:** {'forum': 1, 'docs': 4}

**Answer:**

The provided context does not include specific instructions or details on integrating Tessera with Snowflake. The available documents describe Tessera as a streaming feature store and lineage engine that compiles feature definitions into streaming Flink jobs and DuckDB plans for backfills, along with general setup and API reference details. There is no mention of Snowflake integration steps or configurations in the forum replies or documentation excerpts provided. 

If you are looking to integrate Tessera with Snowflake, you might need to consult additional Tessera documentation or reach out to Tessera support or community channels for specific guidance.

**Sources used:**

- forum/tessera-forum-threads.md (distance: 0.56)
- docs/getting-started.md (distance: 0.505)
- docs/api-reference.md (distance: 0.602)
- docs/getting-started.md (distance: 0.544)
- docs/installation.md (distance: 0.57)

**Contradictions detected:** none


---

## 13. What is the pricing for Tessera enterprise?

**Category:** out_of_scope  
**Expected source:** none  
**Source distribution:** {'docs': 4, 'blog': 1}

**Answer:**

The provided context does not include any information regarding the pricing for Tessera enterprise. There are no references to pricing details or enterprise cost structures in the docs or blog excerpts given.

**Sources used:**

- docs/getting-started.md (distance: 0.511)
- blog/07-why-we-left.md (distance: 0.384)
- docs/installation.md (distance: 0.41)
- docs/getting-started.md (distance: 0.547)
- docs/configuration.md (distance: 0.569)

**Contradictions detected:** none
