# Bitemporal Correctness: What We Actually Mean When We Say "Point-in-Time"

*By Jonas Reinholt, Principal Engineer at Tessera. Posted to the Tessera Engineering Blog.*

The phrase "point-in-time correct" appears on the first page of almost every feature store's marketing site. Including ours. It is also, in my experience, the single phrase most likely to be used loosely. Different vendors mean different things by it. Sometimes the same vendor means different things by it on different days.

This post is the long version of what Tessera means when we say it, and why we made the choices we made. It is going to be a bit technical. If you have ever wondered why every feature value in the system carries two timestamps instead of one, this is the answer.

## The problem

You are training a fraud model. You have label data from January: a list of transactions that were later confirmed as fraud. You want to train the model on the features as they existed at the moment of the transaction, not as they exist today.

A naive feature store gives you the current value of each feature. This is wrong for training. The user's "lifetime transaction count" today is not what it was in January; it has grown. Training on today's value teaches the model to use information it would not have had at inference time. This is training-serving skew, and it is a leading cause of models that look great offline and underperform in production.

The slightly less naive feature store gives you the value of each feature "as of" a specific timestamp. This is closer to right but it is still not quite right, because there are two different timestamps that could mean "as of January 15."

## The two timestamps

Consider a transaction event with `event_time = 2026-01-15T10:00:00Z`. Suppose the transaction itself happened at 10:00:00, but due to upstream delays, our system did not actually receive the event until `ingestion_time = 2026-01-15T10:00:42Z`. Forty-two seconds of delay. Not unusual.

Now you ask for the user's transaction count "as of January 15 at 10:00:30." There are two reasonable answers.

Answer A: the count as the system actually saw the world at 10:00:30. At that moment, the transaction had occurred but we had not yet ingested it. The count does not include it.

Answer B: the count, restricted to events that occurred at or before 10:00:30, regardless of when they were ingested. The count includes the transaction.

Both answers are correct for some purpose. Answer A is what you want if you are reproducing what the model would have seen at inference time at 10:00:30. Answer B is what you want if you are asking "what was true about the user's behavior at 10:00:30," which is a different question.

The first time you trip over this distinction, you spend a week debugging.

## What Tessera stores

Every feature value in Tessera carries both timestamps. The event-time stamp is the timestamp of the underlying event (or the maximum event-time of the events contributing to an aggregation). The ingestion-time stamp is when our system observed the value.

When you query a feature value "as of T," you specify which clock you mean. The training set API takes an `event_time` and an `ingestion_time`, both optional, with defaults that produce Answer A above. The serving call records both timestamps in the lineage graph. To reconstruct the value months later, we query the same definition with the same two timestamps, and we get the same answer.

## Why this is harder than it sounds

The hard part is not storing two timestamps. The hard part is making the streaming and backfill paths produce bitemporally consistent values.

Streaming materialization is naturally event-time aware. Flink's watermark machinery is built around event-time. Ingestion-time is straightforward: it is the wall clock at the moment Tessera writes the value.

Backfill materialization, replaying historical events, has a problem. The ingestion-time of historical events is, in some sense, "now," because we are processing them now. But "now" is the wrong answer if you want the backfill to produce the same values the streaming path produced when those events were originally ingested.

Our answer is that backfills replay the original ingestion-time from the lineage record, not the wall clock at backfill time. This requires every event to carry both its event-time and the ingestion-time of its original processing. We store this in the source-level lineage tier, separately from the feature-level values, because the storage cost would otherwise be prohibitive.

This is one of the things that makes the Tessera lineage graph larger than people expect. We are not just recording transformations. We are recording the full bitemporal history at the source level so that backfills can faithfully reproduce what the streaming path saw.

## What this buys you

**Reproducible training sets.** Two engineers who run `create_training_set` with the same parameters get bit-identical outputs. The content-addressed hash on the training set artifact is real, not aspirational.

**Forensic debugging.** When a model produces a surprising output in production, you can query the lineage graph at the exact bitemporal moment of the serving call and reconstruct the feature values the model actually saw. Not the values as they "should have been," not the values as they look now. The values the model actually saw.

**Safe re-materialization.** When a feature definition changes, the lineage-aware backfill recomputes downstream features at the original ingestion-times, not at the time of the backfill. Historical values continue to reflect "what the system saw at the time."

## The honest limitations

The bitemporal model adds storage cost. Roughly 1.4x compared to a single-timestamp design, mostly in the source lineage tier. Some users have told us they would prefer the option to disable bitemporal storage for non-critical features to save cost. We are considering this for 2.2 but it would weaken the parity guarantee in a way I personally do not love.

The bitemporal model also adds query complexity. The training set API has more knobs than most users want. We have spent significant effort on making the defaults sensible, and most users never override them. But the knobs exist, and they confuse people the first time they encounter them.

I have made peace with both of these costs. The alternative is a feature store that lies to you about reproducibility.

*Jonas works on the Tessera core engine. Questions and arguments welcome on the community Slack.*
