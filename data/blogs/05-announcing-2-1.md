# Announcing Tessera 2.1: Embedding Drift, Backfill Cost Estimation, and Tighter Spark Parity

*By Elena Voss, VP of Engineering at Tessera. Posted to the Tessera Engineering Blog.*

Tessera 2.1 enters general availability next month. This is the largest release we have shipped since the original 2.0 launch, and it is squarely focused on the rough edges that have generated the most support tickets in the first half of the year. I want to walk through what is changing and, equally important, what is not changing yet.

## The three big ones

**Native embedding feature support.** This was the most-requested item by a margin we could measure. Tessera 2.0 treated vector features as opaque byte arrays, which meant our drift monitoring and distribution comparison tools could not look inside them. Teams serving embeddings ended up bolting on a separate vector observability tool. In 2.1, embeddings are first-class.

Concretely: we now support a `vector` type in Mosaic with a declared dimensionality and distance metric. Drift detection runs on configurable summary statistics (centroid drift, dimension-wise PSI, and a sample-based MMD test). The shadow serving comparison tool now produces meaningful reports for vector features. We are not trying to replace dedicated vector databases or full vector observability platforms; we are trying to make embeddings a feature type you do not have to think about separately. Early access customers have been using this since March.

**Backfill cost estimator.** If you read Daniel's postmortem from April, you know why this matters. Every `tessera apply` and every explicit backfill request now produces an estimate: partition count, expected Flink task slot hours, and a rough cost figure based on your cluster's configured pricing. The estimator is conservative by design, which means it will sometimes overestimate. We would rather make you confirm an "expensive" backfill that turns out to be cheap than the reverse.

The control plane will refuse to execute any backfill whose estimated cost exceeds a configurable threshold without an explicit confirmation flag. The default threshold can be tuned per environment. We have heard the feedback that "smart defaults" can be paternalistic; for this one we have decided we are willing to be slightly paternalistic, because the worst-case cost of underestimating is worse than the worst-case cost of overestimating.

**Spark backfill parity.** The 2.0 documentation noted that "the semantic-parity guarantee weakens slightly around timezone handling in window functions" on the Spark adapter for datasets above the DuckDB ceiling. This was the closest thing in the product to an open wound. 2.1 closes most of it.

The fix is, in short, a rewrite of the canonical-to-Spark lowering for window operators that preserves explicit UTC normalization at every boundary. We have run the full 1,400-case parity test suite against the Spark backend in 2.1 and it now passes 1,397 of them. The three remaining failures are around DST transition handling for time-zoned sources, and they are documented. We are working on the last three for 2.2.

## The smaller things that I personally care about

**Watermark diagnostics in the CLI.** A common debugging story in 2.0 was: a feature is stalled, the user does not know why, and the actual cause (an idle partition, a misconfigured watermark delay, a late-arriving source) is buried in Flink logs. We have surfaced watermark state through `tessera source describe` and `tessera feature describe`, and added a `--diagnose` flag that will offer hypotheses about why a feature is not advancing. The hypothesis quality is not perfect but it is better than reading Flink logs.

**Online store adapter for KeyDB.** We have customers on KeyDB who have been hand-rolling adapters. We now ship one.

## What is not changing yet

I want to be honest about the limitations we have not addressed.

**The Python UDF restriction in Mosaic streaming.** Still in force. Streaming features cannot use arbitrary Python; they must compile to Flink. We are working on a wasm-based UDF execution path, but it is not in 2.1 and I am not going to commit to a specific release for it. The performance characteristics are still being evaluated.

**The DuckDB 2 TB ceiling.** Unchanged. For larger backfills you still fall back to Spark. The Spark path is now tighter on parity, but the developer ergonomics gap remains. Closing that gap is harder than it looks because DuckDB and Spark have genuinely different operational models, and we do not want to ship something that pretends to be DuckDB but silently changes semantics under the user.

**Cost estimator accuracy on novel feature patterns.** The estimator is trained (in the loose sense of "calibrated against historical backfill telemetry") and it is most accurate on features that look like ones we have seen before. For genuinely novel computation shapes the estimate can be off by up to 2x in either direction. We are flagging low-confidence estimates explicitly.

## Upgrading

Tessera 2.1 is a backward-compatible upgrade from 2.0. The Helm chart upgrade is the usual `helm upgrade tessera tessera/tessera --version 2.1.0`. Read the release notes first; there is one configuration change for the new estimator threshold that has a sensible default but that you may want to tune. If you are on 1.x, follow the 2.0 migration path first.

## A note on roadmap

We try to be careful about pre-announcing features because we have been burned before. With that caveat, here is what is on the 2.2 plan as of today: wasm-based UDF execution, full Spark parity on DST cases, and a substantial revision to the lineage UI based on user research we have been running this quarter. Dates are not firm. The general theme of 2.2 is "fewer rough edges, more polish on what already exists" rather than new headline features.

As always, the best place to send feedback is the community Slack. We read all of it.

*Tessera 2.1 GA targets July 2026. Early access is open to existing customers; ask your account team.*
