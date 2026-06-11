# Postmortem: How a Ten-Line Feature Change Took Down Our Staging Cluster for Six Hours

*By Daniel Park, Senior SRE on the Tessera platform team. Posted to the Tessera Engineering Blog.*

This is a postmortem for an incident that hit our internal staging cluster on April 18, 2026. It did not affect any customer environment. We are posting it publicly because the failure mode is one our users could also hit, and because we said we would be more transparent about our own operational mistakes.

## Summary

A platform engineer (me) modified a single upstream session aggregation feature in our internal "dogfood" staging environment. The modification looked innocent. The resulting backfill consumed all Flink task slots in the cluster for six hours, blocked seventeen other in-flight backfills, and caused two unrelated dogfood services to miss their freshness SLOs because their materialization jobs could not get scheduled.

Nobody got paged at three in the morning. No customers were affected. But the failure mode is exactly what we have been warning users about, and the irony of triggering it ourselves was not lost on the team.

## The change

The session aggregation feature in question is called `user_session_window_v2`. It computes the start and end of a user's current activity session based on a thirty-minute inactivity gap, and it is used by approximately forty downstream features across our dogfood environment, including engagement metrics, churn signals, and several experimental fraud features.

The change I made was to lower the inactivity gap from thirty minutes to twenty-five minutes. Five lines of Mosaic code. I tested it locally against a one-day synthetic dataset. The output looked right. I committed, the CI parity tests passed, I ran `tessera apply` against staging, and I went to lunch.

```python
@feature(name="user_session_window_v2", entity="user_id")
def user_session_window_v2():
    return (
        transactions
        .group_by("user_id")
        .session_window(gap_minutes=25)  # was 30
        .agg(session_start="min(event_time)", session_end="max(event_time)")
    )
```

## What happened

The lineage-aware backfill diff correctly identified that the semantics of `user_session_window_v2` had changed. It also correctly identified that all forty downstream features now needed to be re-materialized for the lookback window.

What I did not appreciate, because I did not check, is that the lookback window for this feature in our staging environment is ninety days. Multiplied by forty downstream features and the per-feature partition counts, the resulting work set was approximately 1.4 million Flink task partitions.

Our staging Flink cluster has 96 task slots.

The work set started landing on the cluster around 12:47 PM. Within four minutes, every task slot was occupied. New job submissions queued. Our internal `freshness-monitor` service started firing low-priority alerts on dependent features that could not materialize. By 1:15 PM the alert backlog had triggered our paging policy and someone on the on-call rotation (also me, as it happened) saw the alert.

By 1:20 PM I had identified the cause and was making the call to either let the backfill run to completion or kill it and rebuild the affected features from a known-good state. I chose to let it run, because killing it would have meant manually reasoning about which of the forty downstream features were in a consistent state, which was not a problem I wanted to solve at 1:20 PM.

The job completed at 6:54 PM. Six hours, seven minutes after submission.

## What went wrong

Three things, in order of severity.

**No cost estimator in 2.0.** This is the headline. The lineage-aware backfill is smart about what to recompute, but "smart" is not the same as "cheap." A diff that touches a forty-fanout upstream is going to generate a forty-fanout work set, and there is currently no way to see that number before you submit. This is documented as a known limitation. It is being addressed in 2.1. I will say more about that in a moment.

**I did not dry-run the backfill.** The CLI supports `--dry-run` on `tessera apply` and it would have surfaced the work set size in the output. The reason I did not run it is that I have made versions of this change a hundred times and it has always been fine. The reason it was fine before is that I had never previously touched an upstream with this fanout factor. The lesson here is in the runbook now.

**Staging Flink was undersized.** Our dogfood staging cluster is provisioned for "normal" workloads, which mostly meant we sized it for steady-state streaming and not for backfill bursts. We are bumping its capacity, but more importantly we are adding a backfill-specific task slot reservation so that backfill work cannot fully starve streaming jobs.

## What we are changing

Three concrete changes.

**Cost estimator in 2.1.** This is now a hard requirement for the 2.1 release, currently in late beta. The estimator will return an estimated partition count, estimated Flink task slot hours, and a rough cost estimate based on cluster pricing. It will run automatically on every `tessera apply` and will require an explicit `--confirm-expensive-backfill` flag above a configurable threshold. Early access customers have been using it for about a month and the feedback is good.

**Mandatory dry-run for high-fanout upstreams.** The control plane will now refuse to execute a backfill that touches more than ten downstream features without an explicit dry-run within the previous fifteen minutes.

**Better runbook content for users.** The current docs mention this failure mode. They do not, in retrospect, mention it loudly enough.

## What I would tell users today

If you are running Tessera 2.0 and you have any feature that fans out to more than twenty downstream features, treat changes to it like database schema changes. Dry-run first. Look at the work set. If the partition count surprises you, ask why before submitting.

If you are running 2.1 (general availability is targeting mid-Q3), the estimator will do most of this work for you. But the underlying physics has not changed. A small change to a heavily-used feature is still a big amount of computation.

We would rather tell users exactly what we got wrong than have them rediscover it on their own clusters.

*Comments and questions are welcome. The runbook updates are in PR #4421 on the internal repo and will land in next week's docs publish.*
