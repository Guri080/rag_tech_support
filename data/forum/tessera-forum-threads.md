# Tessera Community Forum — Selected Threads

---

## Thread 1: [BUG] redis TTLs not respected on backfilled values in 1.7?

**posted by feat_eng_carlos** — Mar 14, 2025 02:41 UTC
**tags:** bug, 1.7, redis, backfill

hey all, hitting something weird. running tessera 1.7.3 against redis 6.2 cluster. when i do a streaming-only feature with ttl="1h" it works fine, values expire as expected. but the moment i run a backfill on the same feature, the backfilled values get written with NO ttl. like, `TTL key` returns -1 in redis-cli. they just sit there forever.

is this a known thing? i checked the 1.7 release notes and didn't see anything. the docs definitely say ttl is enforced on all writes regardless of execution path.

anyone seen this?

---

**reply from datadrew** — Mar 14, 2025 03:12 UTC

yeah we hit this in december. it's a real bug. the backfill writer was using a different redis client path that didn't honor the per-feature ttl config. we ended up writing a janky cleanup cron that scans key patterns and reapplies TTLs after every backfill. cursed but it worked.

afaik they fixed it in 1.8 but we never upgraded because the migration was scary.

---

**reply from tessera_staff_marco [STAFF]** — Mar 14, 2025 09:47 UTC

Confirming this was a bug in 1.7.x — the backfill writer bypassed the per-feature TTL config. Fixed in 1.8.0 (see release note "backfill respects online_store TTL"). If you can't upgrade immediately, the workaround datadrew describes is fine, or you can set a global default TTL at the redis level as a backstop.

We did not get this into the 1.7.x patch series because the fix required changes to the writer interface that we didn't want to backport. Apologies.

---

**reply from feat_eng_carlos** — Mar 14, 2025 14:22 UTC

ok thanks. gonna plan the 1.8 upgrade. cron hack will hold us until then 🙏

---

## Thread 2: per-feature parallelism setting being ignored??

**posted by sre_jenny** — 2026-02-08 11:04 UTC
**tags:** config, 2.0, flink, parallelism

we have a high-volume feature where we set `parallelism=16` in the @feature decorator. flink dashboard shows the job running with parallelism 4 (which is our cluster default). tried it three ways:

```python
@feature(name="user_event_rate_1m", entity="user_id", parallelism=16)
```

also tried setting it via the cli `tessera feature update ... --parallelism 16`. also tried bumping `flink.defaultParallelism` to 16 cluster-wide which DID work but obviously that affects everything.

is the per-feature override broken in 2.0? docs say it should work.

---

**reply from gopal_b** — 2026-02-08 13:18 UTC

it works but theres a gotcha. the parallelism setting in the decorator only takes effect on a fresh job submission. if your feature already had a running flink job and you just bumped the parallelism in the definition and ran `tessera apply`, the existing job keeps running with the old parallelism. you have to do `tessera feature restart <name>` to actually pick up the change.

i lost like a day to this. nothing in the docs about it as far as i can tell.

---

**reply from sre_jenny** — 2026-02-08 13:41 UTC

🤦 ok yeah that's it. just restarted and parallelism is now 16. thanks.

this is the kind of thing that should be a warning in `tessera apply` output tbh. "note: parallelism changed but existing job not restarted, run `tessera feature restart` to apply"

---

**reply from tessera_staff_priya [STAFF]** — 2026-02-09 17:30 UTC

You're right, this is a footgun. Filed as TES-3891. We'll add the warning to apply output in the next patch release. Sorry for the lost day.

There's also an undocumented env var `TESSERA_AUTO_RESTART_ON_PARALLELISM_CHANGE=true` that will do the restart automatically on apply. It's undocumented because we weren't sure we wanted to commit to the behavior, but it's been stable for months. Use at your own risk; we may make it the default in 2.1 and remove the flag.

---

## Thread 3: [FEATURE REQUEST] first class embedding support

**posted by ml_eng_tomas** — 2025-11-22 09:15 UTC
**tags:** feature-request, embeddings, 2.0, vectors

i know this has been raised before but bumping it. we serve like 30 embedding features and tessera's "they're just bytes" stance is making us bolt on arize for the drift monitoring side. that's $$$ and operational overhead.

at minimum i want:
- a `vector` type with declared dim and metric
- centroid drift / dimension-wise PSI on the drift dashboard
- shadow comparison that actually produces meaningful output for vectors

is this on a roadmap somewhere? happy to beta test.

---

**reply from kai_z** — 2025-11-22 14:02 UTC

+1 we're in the same boat. weights and biases for vector monitoring, tessera for everything else. would love to consolidate.

---

**reply from another_ml_eng** — 2025-11-23 22:51 UTC

bumping this. it's been the top feature request in our usage for like 8 months.

---

**reply from tessera_staff_elena [STAFF]** — 2025-11-24 16:08 UTC

Hi all — I can't commit to a date publicly but I will say this is the #1 item on the 2.1 plan, and the team has been working on it since September. I'd expect early access to selected customers in Q1 and GA mid-year.

If you want to be in the EA cohort, ping your account team. We're prioritizing customers serving production embeddings at meaningful scale.

---

**reply from ml_eng_tomas** — 2025-11-24 17:22 UTC

🚀 noted, will reach out. ty

---

## Thread 4: workaround for python udfs in 1.9 streaming?

**posted by quant_dev_amir** — 2024-08-30 18:33 UTC
**tags:** workaround, 1.9, mosaic, udf

ok so i know mosaic doesn't support arbitrary python in streaming. i know. i've read the docs five times. but i have this one logistic transformation that's annoyingly hard to express in the stdlib (involves a piecewise calibration curve with like 12 breakpoints) and rewriting it as a chain of `case when` calls produces a mosaic definition that's 200 lines long and impossible to review.

has anyone actually gotten around this? like is there ANY way to inject custom logic into a streaming feature?

---

**reply from infra_lurker** — 2024-08-31 02:07 UTC

ok so there's an unsupported way. we did this in 1.9.2 and it still works in 1.9.5 last i checked.

you can write a flink sidecar job that consumes the same kafka topic, does your python transformation, and writes the result to ANOTHER kafka topic. then you register that downstream topic as a tessera source and write a trivial mosaic feature that just reads from it.

it's gross. you lose the parity guarantee because tessera doesn't see the transformation. but it works and your model server doesn't know the difference.

NOT a tessera-supported pattern. would not recommend if you have any other option. but it exists.

---

**reply from quant_dev_amir** — 2024-08-31 11:14 UTC

ok that's clever. how do you handle backfills though? the sidecar isn't going to replay history.

---

**reply from infra_lurker** — 2024-08-31 15:42 UTC

we don't lol. we accept that this one feature has no usable backfill. for our use case (online-only, model retrained quarterly on rolling 90 day live data) it's fine. for anyone needing historical training sets this would be a non starter.

---

**reply from tessera_staff_jonas [STAFF]** — 2024-09-02 14:11 UTC

Just want to be clear that the sidecar pattern infra_lurker describes is not supported and we'd discourage it in production unless you really know what you're getting into. The lineage graph won't have visibility into the transformation, which defeats most of the point of using Tessera.

That said, we hear the underlying request. There's a wasm-based UDF execution path in early R&D that we hope to ship eventually. No timeline yet.

For the specific case of piecewise calibration curves: take a look at `tessera.transform.piecewise_linear` in the stdlib (added in 1.9). It's not in the prominent docs but it does exactly what you described, and it compiles cleanly to streaming.

---

**reply from quant_dev_amir** — 2024-09-02 16:38 UTC

WAIT WHAT. `piecewise_linear` exists?? not in the stdlib reference page that i can find. let me try this.

[edit: it works perfectly. 6 lines. why is this not in the docs.]

---

## Thread 5: training set hashes are different for "identical" calls — what gives

**posted by datasci_brigitte** — 2026-04-11 16:01 UTC
**tags:** bug, 2.0, training-set, content-hash

my coworker and i are both trying to create the same training set. exact same `create_training_set` call, exact same entity_df parquet path, exact same feature list. we're getting different content_hash values back. like wildly different.

the whole pitch of training set snapshots is that two engineers get bit-identical inputs. so something is wrong.

what we're calling:
```python
client.create_training_set(
    name="fraud_v4_train",
    features=["user_txn_count_30m", "user_decline_ratio_1h", "merchant_risk_v2"],
    entity_df="s3://our-bucket/labels/2026_q1.parquet",
    timestamp_column="label_time",
)
```

both running 2.0.4 client. control plane is 2.0.4.

---

**reply from rachel_data** — 2026-04-11 17:55 UTC

is your `timestamp_column` floats by any chance? we hit this. if your timestamps have sub-millisecond precision (like float64 seconds with extra digits) different filesystems / parquet writers can produce different actual binary representations and the hash includes them.

we round to millisecond before writing the parquet now. fixed it for us.

---

**reply from datasci_brigitte** — 2026-04-11 18:14 UTC

🤯 yes they're float64 with microsecond precision. let me try truncating to ms.

---

**reply from datasci_brigitte** — 2026-04-11 19:48 UTC

confirmed that was it. truncated to ms, hashes match. but this is a real footgun. the docs say "two engineers training the same model spec get bit-identical inputs" but actually you need to also ensure your entity dataframe is bit-identical down to floating point precision, which isn't obvious.

---

**reply from tessera_staff_marco [STAFF]** — 2026-04-12 09:33 UTC

You're right, this is a documentation gap. The content_hash includes the entity_df contents byte-for-byte, so any difference in floating point representation propagates. We should be clearer about this in the API reference.

There's also a related issue: the content_hash includes the resolved feature versions at the moment of materialization. If you and your coworker create the training set at different times and a feature version was bumped in between, you'll also get different hashes even if everything else is identical. For reproducibility-critical workflows you should pin feature versions explicitly with the `feature_versions` param (it's in the API but not prominently documented). Filing a docs update.

---

## Thread 6: spark backfill adapter — timezone parity is way worse than "weakens slightly"

**posted by data_eng_oluchi** — 2026-01-19 22:40 UTC
**tags:** bug, 2.0, spark, backfill, timezone

docs say "the semantic-parity guarantee weakens slightly around timezone handling in window functions" on the Spark backfill adapter. that's a hell of an understatement for what we're seeing.

we backfilled a session window feature over 4 TB of historical events (so spark, since duckdb tops out at 2). the backfill output disagrees with the streaming output for about 1.3% of session boundaries. specifically: any session that spans midnight UTC on a day where the source event timezone was inferred as local time rather than UTC, the session gets split into two.

so "slightly" is doing a LOT of work in that doc sentence.

i need this to actually match streaming. is there a workaround?

---

**reply from heavy_user_carlos** — 2026-01-20 04:11 UTC

we have the same problem. we ended up forcing all our source timestamps to be explicit utc strings (with the Z suffix) at the kafka producer layer. spark adapter handles those correctly. it's timezone-naive timestamps where it goes off the rails.

i agree the docs undersell this. it's not "slight" it's "this will silently produce wrong results until you notice."

---

**reply from data_eng_oluchi** — 2026-01-20 12:30 UTC

ok we'll try the producer-side normalization. annoying because we'd have to coordinate with the upstream service team but doable.

is there an ETA on this getting properly fixed? i feel like "spark adapter has different semantics than flink" kind of undermines the whole product pitch.

---

**reply from tessera_staff_jonas [STAFF]** — 2026-01-21 11:08 UTC

You're right to push on this. The docs language is too soft for the actual user experience and we'll update it.

The real fix is landing in 2.1: we've rewritten the canonical-to-Spark lowering for window operators to preserve explicit UTC normalization at every boundary. Our internal parity tests went from 1,397/1,400 passing on Spark in 2.1 vs ~1,340/1,400 in 2.0. The remaining 3 failures are around DST transitions for time-zoned sources.

For 2.0 the producer-side normalization that heavy_user_carlos describes is the recommended workaround. We'll add it to the troubleshooting docs.

---

**reply from data_eng_oluchi** — 2026-01-21 15:55 UTC

appreciate the honesty. will hold for 2.1, in the meantime the producer normalization is in flight.

---

## Thread 7: features broke after 1.x → 2.0 migration, specifically anything using `.join_as_of`

**posted by ml_lead_priya_g** — 2025-12-04 14:22 UTC
**tags:** migration, 1.x, 2.0, breaking-change, join

we did the 1.10 → 2.0 migration this past weekend. mostly went fine. but every feature using `.join_as_of` is now producing slightly different values than it did under 1.10. like, the lineage shows the migration tool re-registered them, the definitions look identical, but the actual values diverge by some small percentage on most entities.

i can't find this in the migration notes. is this expected? are we just supposed to know the join_as_of semantics changed?

---

**reply from old_user_bri** — 2025-12-04 18:09 UTC

omg yes. this was in the upgrade guide but it's buried. 2.0 changed the default behavior of `.join_as_of` from "look back up to feature ttl" to "look back up to a configurable bound that defaults to 24h". if your 1.x features were silently joining against records older than 24h you'll see divergence.

the fix is to add `lookback="<duration>"` to your join_as_of calls explicitly. set it to whatever your ttl was in 1.x and you should get the old behavior back.

---

**reply from ml_lead_priya_g** — 2025-12-04 18:33 UTC

ok that explains it. our chargeback joins were looking back 90 days because the underlying feature had a 90 day ttl. now they're silently capped at 24h. ugh.

the migration tool should have flagged this. "this feature uses join_as_of with no explicit lookback and your 1.x ttl was >24h, this behavior is changing." that would have saved us a week.

---

**reply from tessera_staff_aisha [STAFF]** — 2025-12-05 10:14 UTC

You're absolutely right. The migration tool should have caught this and warned. We had it in scope for the tool and it slipped. Filing TES-3712 to add the check in a tool update — anyone who hasn't migrated yet will get the warning, and we'll publish a standalone "audit your join_as_of calls" script for folks who already migrated.

The behavior change was intentional (the unbounded lookback was a frequent source of correctness bugs at scale) but the upgrade-time communication was bad. Sorry.

---

## Thread 8: lineage queries timeout at depth >10, but docs say default max is 25?

**posted by dataops_finn** — 2026-05-02 08:47 UTC
**tags:** lineage, 2.0, performance, api

the api docs for `/v2/lineage/{feature_id}` say the default max depth is 25 and you can pass `depth=-1` for unbounded.

in practice i can't get past depth=10 without the request timing out. depth=11 is a coinflip. depth=12 and higher i've never seen succeed.

is this a known performance issue or are we misconfigured?

---

**reply from sven_se** — 2026-05-02 13:22 UTC

it's known. the docs default of 25 refers to the configured maximum, not the practical maximum. the actual perf cliff depends on your dag fanout. on a fanout >5 dag, anything past depth 8-10 is going to be slow because the result set grows exponentially.

i wrote about this on my blog. the workaround is to walk the graph one layer at a time using depth=1 and follow the edges yourself.

---

**reply from dataops_finn** — 2026-05-02 14:11 UTC

oh hmm. so the docs are technically correct but practically misleading. ok i can manually paginate.

is there any plan to actually make deep queries fast? walking 8 layers manually is 8 round trips.

---

**reply from tessera_staff_marco [STAFF]** — 2026-05-03 09:55 UTC

The depth=25 number in the docs is the configured limit, not a performance guarantee. We agree it's misleading and we're updating the docs to be explicit about practical limits.

The actual fix is on the 2.1 plan: a batched lineage endpoint that lets you fetch multiple feature subgraphs in one request, and a streaming-response mode for large queries that returns layers incrementally instead of waiting for the full traversal. Should land with 2.1 GA.

For now, the layer-by-layer pagination sven describes is the way.

---

## Thread 9: feature request: webhooks on lineage events

**posted by sven_se** — 2026-05-15 11:30 UTC
**tags:** feature-request, lineage, webhooks, 2.0

would love a way to subscribe to lineage events instead of polling the api every 5 min. specifically:
- feature version changed
- backfill started/completed on a feature
- training set materialized
- shadow promoted to production

webhooks would be fine. event stream over websockets would be fancier but webhooks would unblock my use case.

---

**reply from also_sven_fan** — 2026-05-15 16:20 UTC

+1 we have a pipeline that needs to invalidate downstream caches when feature versions change. polling is gross.

---

**reply from rachel_data** — 2026-05-16 09:14 UTC

+1 from us too, we want to fire airflow dags on training set materialization.

---

**reply from tessera_staff_elena [STAFF]** — 2026-05-18 14:02 UTC

This is on the longer-term roadmap. We've talked about it for a while and there's broad agreement internally that it should exist. It's not in 2.1 (which is locked) and I can't promise 2.2 without more discussion, but the use cases you're all describing are exactly the ones we have in mind.

In the meantime, there is an undocumented Kafka topic that the control plane publishes lineage events to (`__tessera_lineage_events`) which you could subscribe to directly. It's not a public API and the format may change without notice, so I'm hesitant to recommend it for production. But if you want to prototype something, it's there.

---

**reply from sven_se** — 2026-05-18 14:38 UTC

oh that's interesting. yeah i'd use that for prototyping with a giant "this will break" comment in the code. thanks for the pointer.

---

## Thread 10: cassandra adapter dropping writes during node failover in 1.8.x?

**posted by reliability_eng_max** — 2025-04-02 23:12 UTC
**tags:** bug, 1.8, cassandra, online-store

running 1.8.4 against cassandra 4.1 (5 node cluster). during routine maintenance we cycled one node (drain, stop, restart, rejoin) and we noticed that during the ~30 second window the node was being drained, tessera's cassandra adapter silently dropped about 0.8% of feature writes. no errors logged on the tessera side, no failed flink tasks, the data just isn't there.

is this a known issue? we expected the adapter to handle node failover transparently.

---

**reply from reliability_eng_max** — 2025-04-03 01:40 UTC

bumping. this is kind of scary for us because we run cassandra maintenance regularly.

---

**reply from tessera_staff_priya [STAFF]** — 2025-04-03 11:18 UTC

This is a real bug in 1.8.x. The cassandra adapter was using a write consistency level of ONE with a retry policy that gave up too aggressively on the draining node. Under failover, writes routed to the draining replica would fail-fast and be considered "complete" without actually being persisted.

Fixed in 1.9.0 — the adapter now uses LOCAL_QUORUM by default and retries with a different coordinator on failure. There's also a config flag `onlineStores[].cassandra.writeConsistency` to override.

We did backport the fix to 1.8.6. If you can upgrade to 1.8.6 or later within the 1.8.x line you'll get the fix without a major version bump. I'd strongly recommend it.

---

**reply from reliability_eng_max** — 2025-04-03 14:55 UTC

upgrading to 1.8.6 today. thanks for the fast response. i'd note this didn't show up in the 1.8.6 release notes as a behavior change which is why we missed it.

---

**reply from tessera_staff_priya [STAFF]** — 2025-04-04 09:22 UTC

You're right that the release notes were too terse. The note said "improved Cassandra adapter reliability under failover" without spelling out the consistency level change. We'll be more explicit about behavior-changing fixes in future patch notes. Thanks for the feedback.
