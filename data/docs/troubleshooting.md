# Troubleshooting

**Version:** 2.0

This document covers the most frequent issues reported against Tessera 2.0 deployments, along with diagnostic procedures and known limitations. If a problem here matches your symptoms, the suggested resolution should apply directly. If not, collect a support bundle with `tessera support bundle` and contact your account team.

## Diagnostic First Steps

Before working through a specific issue, run the health check:

```bash
tessera health --verbose
```

The output reports the status of the control plane, metadata store, Flink connection, online stores, and any active backfills. Most issues below correspond to a single failed check.

## Streaming and Materialization

### Mosaic compilation fails with `UNSUPPORTED_UDF`

**Symptom.** Applying a feature definition returns `INVALID_PLAN` with detail `UNSUPPORTED_UDF`, naming a Python function in your definition.

**Cause.** Mosaic does not support arbitrary Python UDFs in streaming mode. Because feature definitions must compile to Flink, only a whitelisted subset of NumPy and the Tessera-provided standard library are available in streaming features. This is a hard limitation, not a missing import.

**Resolution.** Rewrite the logic using Mosaic primitives. The most common cases are:

- Replace `np.percentile` with `tessera.agg.approx_quantile`.
- Replace custom string parsing with `tessera.text` helpers.
- Replace bespoke time-bucket logic with `tessera.window` builders.

If the logic cannot be expressed in Mosaic, the feature may need to be authored as a batch-only feature, served from the backfill path. Note that this loses the semantic-parity guarantee.

### Flink job stuck in `RECONCILING`

**Symptom.** A newly applied feature stays in `materializing` status indefinitely and the Flink dashboard shows the job in `RECONCILING`.

**Cause.** Most often a checkpoint storage misconfiguration. The Flink workers cannot write to the configured `flink.checkpointStorage` URI.

**Resolution.** Verify storage credentials are reachable from the Flink task managers, not only from the Tessera control plane. The two run in different pods and frequently have different service accounts.

### Watermark stalls

**Symptom.** Feature values lag the upstream Kafka topic by minutes or hours; the per-feature staleness SLO fires repeatedly.

**Cause.** A source whose `watermark_delay` is too low for actual event-time skew, or a partition with no data at all.

**Resolution.** Inspect the source watermark with `tessera source describe <name>`. If one partition is idle, set `idle_partition_timeout` on the source so Tessera advances the watermark in its absence. If skew is genuinely larger than expected, raise `watermark_delay`; this trades end-to-end latency for completeness.

## Backfills

### Backfill pegs the Flink cluster for hours

**Symptom.** A small change to a feature definition triggers a multi-hour backfill that consumes all available Flink task slots, blocking unrelated jobs.

**Cause.** This is a known sharp edge. The lineage-aware diff correctly identifies the minimum re-materialization set, but if the changed feature is a widely used upstream (a session aggregation used by forty downstream features, for example), the resulting work set is large. There is no built-in cost estimator in 2.0.

**Resolution.** Always submit backfills with `dry_run=true` first. The response includes the full work set and the estimated partition count. If the count is large, either:

- Narrow the time window and run multiple smaller backfills.
- Raise `control.maxConcurrentBackfills` to prevent the single job from monopolizing slots, then submit with a lower per-job parallelism.
- Coordinate the backfill during a low-traffic window.

A cost estimator is on the roadmap for 2.1.

### Backfill fails with `BACKFILL_TOO_LARGE`

**Symptom.** A backfill against historical data returns `413 BACKFILL_TOO_LARGE`.

**Cause.** The DuckDB backfill path tops out at approximately 2 TB of working set. The estimator refuses to start a job that would exceed this.

**Resolution.** Switch the cluster to the Spark adapter by setting `backfill.engine: spark` in the Helm values and reinstalling. The Spark path is officially supported but iteration is noticeably slower than DuckDB.

### Spark adapter produces values that differ from streaming

**Symptom.** After switching to the Spark adapter, a small number of window-function feature values disagree between the streaming output and the backfill output.

**Cause.** The semantic-parity guarantee weakens slightly around timezone handling in window functions on the Spark adapter. Events near daylight saving transitions or events whose timestamps lack explicit timezone information are the usual culprits.

**Resolution.** Audit affected feature definitions to ensure all timestamps are UTC at the source. If divergence persists, set `backfill.timezoneStrict: true` to make Spark refuse rather than silently bucket ambiguous timestamps.

## Online Serving

### Reads return stale values after promotion

**Symptom.** After promoting a shadow feature to production, online reads continue to return values from the old version.

**Cause.** The online store TTL on the previous version's keys has not yet expired, and the new version writes to a separate key space.

**Resolution.** This is intentional behavior to allow safe rollback. To force convergence immediately, run `tessera feature promote <name> --invalidate-online`. This deletes the previous version's keys at the cost of a brief read-miss window.

### `STORE_UNAVAILABLE` errors during peak traffic

**Symptom.** Online reads return `503 STORE_UNAVAILABLE` intermittently under load.

**Cause.** The client SDK's load balancer cannot find a healthy replica. This usually indicates an under-provisioned online store, not a Tessera bug.

**Resolution.** Inspect store-side metrics first. If the store is healthy, switch `clientLoadBalancing` from `pinned` to `least-latency` so traffic shifts away from a degraded replica more quickly.

## Embedding Features

### Drift monitoring reports no data for vector features

**Symptom.** A feature whose values are embedding vectors shows no entries in the drift dashboard and no PSI or KL alerts ever fire.

**Cause.** Tessera 2.0 treats vectors as opaque byte arrays. They can be stored and served, but drift monitoring and distribution comparison tooling only work on scalar and categorical features.

**Resolution.** Teams serving embeddings typically pair Tessera with a dedicated vector observability tool. Native vector drift support is on the roadmap but not in 2.0.

## Lineage and Training Sets

### Two engineers get different `content_hash` values for the same training set

**Symptom.** Engineers A and B run apparently identical `create_training_set` calls but receive different content hashes.

**Cause.** Almost always one of three things: the underlying `entity_df` file changed between calls, the feature versions resolved at materialization time differed, or the `timestamp_column` contains timestamps with sub-second precision that round differently.

**Resolution.** Pin feature versions explicitly in the request rather than relying on the current version. Use a content-addressed entity dataframe URI (for example, a versioned S3 object). Truncate timestamps to millisecond precision before submission.

### Lineage query returns `DEPTH_TOO_DEEP`

**Symptom.** A lineage query with `depth=-1` returns `400 DEPTH_TOO_DEEP`.

**Cause.** The configured maximum traversal depth (default 25) was exceeded. This usually indicates a cyclic structure in user-defined dependencies that the validator should have caught, or a genuinely very deep DAG.

**Resolution.** Reduce the requested depth or query in stages, walking the graph one layer at a time. If you believe the DAG is legitimately deep, raise `control.lineage.maxTraversalDepth`.

## Collecting a Support Bundle

When opening a support ticket, attach the output of:

```bash
tessera support bundle --since 24h --output tessera-bundle.tar.gz
```

The bundle contains anonymized control plane logs, the most recent Flink job manifests, and a snapshot of the metadata schema version. It does not include feature values or entity keys.
