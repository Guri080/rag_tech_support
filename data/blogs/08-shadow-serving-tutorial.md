# Shadow Serving in Practice: How We Validate Ranking Features Before They Hit Production

*By Aisha Mensah, ML Engineer at Tessera. Posted to the Tessera Engineering Blog.*

Shadow serving is the feature in Tessera that gets the least attention in marketing and that I personally use the most. This post is a walkthrough of how we use it internally, against the same dogfood environment that occasionally embarrasses us in postmortems. The workflow is concrete and you should be able to adapt it.

I am writing against Tessera 2.0, with a note at the end about what 2.1 changes.

## The problem shadow serving solves

You have a ranking feature in production. You want to change it. The change might be a better aggregation window, a different normalization, a new upstream signal. You believe the change is an improvement. The new feature compiles, the parity tests pass, and the unit tests look right.

You still do not know what the new feature will actually output against live traffic. You especially do not know whether the new feature shifts the value distribution in ways that will degrade your downstream model. Offline validation can tell you a lot of things; it cannot tell you what your real production users will look like at the ninety-ninth percentile of feature value.

Shadow serving runs the new version of the feature against the same live event stream as the production version, serves it to a shadow path that the model server can optionally consume, and produces comparison reports. You get to look at the distributions side by side before promoting.

## The workflow

I am going to use a real example, lightly anonymized. We had a feature called `merchant_recent_volume_15m` that computed a merchant's transaction volume over the last fifteen minutes. The proposed change was to switch from a tumbling window to a sliding window with a five-minute slide, because the tumbling window produced step-function changes that downstream consumers were occasionally surprised by.

### Step 1: Define the shadow

```python
@feature(
    name="merchant_recent_volume_15m_v2",
    entity="merchant_id",
    online_store="redis-primary",
    ttl="30m",
    shadow_of="merchant_recent_volume_15m",
)
def merchant_recent_volume_15m_v2():
    return (
        transactions
        .group_by("merchant_id")
        .window(window.sliding(minutes=15, slide_minutes=5))
        .agg(volume="sum(amount)")
    )
```

The `shadow_of` argument is what makes this a shadow rather than a new feature. Tessera registers it as parallel to the production feature, materializes it through the streaming pipeline, but does not route any production reads to it. The model server can opt in to receive shadow values alongside production values for comparison.

### Step 2: Apply and wait

```bash
tessera apply features/merchant_recent_volume_15m_v2.py
```

The shadow starts materializing immediately. We typically let it run for at least a full traffic cycle, which for our merchant-volume features means a full day to capture the weekend versus weekday distinction.

### Step 3: Look at the comparison report

```bash
tessera shadow compare merchant_recent_volume_15m_v2 \
  --window 24h \
  --output report.html
```

The report shows:

- The production and shadow value distributions overlaid as histograms.
- Per-entity deltas (which merchants saw the biggest change in feature value).
- A correlation scatter plot of production versus shadow values.
- Summary statistics: mean, p50, p99, max absolute delta.

For the merchant volume change, the histograms looked almost identical, which is what we expected. The interesting finding was that the per-entity delta was bimodal: most merchants saw small changes, but a long tail of merchants (about 4% of the entity set) saw the new sliding-window value diverge from the tumbling-window value by more than 30%. These turned out to be low-volume merchants whose values were dominated by individual large transactions falling into different windows.

We did not know that going in. The shadow report told us.

### Step 4: Decide

Based on the report, we made a judgment call. The downstream model's sensitivity analysis suggested it could tolerate the long-tail divergence. We promoted.

```bash
tessera feature promote merchant_recent_volume_15m_v2 \
  --to merchant_recent_volume_15m
```

The promotion swaps the version pointer atomically. Online reads start returning the new version immediately. The old version's keys remain in the online store until TTL expiry, which gives us a rollback window.

## What this is good at, and what it is not

Shadow serving is good at catching distribution shifts. If your new feature produces values that look meaningfully different from the production feature, you will see it.

Shadow serving is bad at catching semantic bugs. If your new feature is wrong in a way that happens to produce a similar distribution, the shadow comparison will not catch it. We had a case in March where a developer changed an aggregation from `sum(amount)` to `avg(amount) * count(*)`, which introduced a floating-point precision difference that occasionally produced NaN values for empty windows. The shadow comparison did not flag this. We caught it through a separate validation step that checks for NaN rates.

Shadow serving is a layer in your validation stack, not the whole stack.

## What changes in 2.1

The 2.1 release adds a `tessera feature promote --rollback` command that works even after promotion, by re-pointing to the previous version. In 2.0, rollback after the TTL window has expired requires re-applying the old definition. This is operationally annoying and the 2.1 change is welcome.

The 2.1 release also adds native shadow comparison for vector features. In 2.0 you can register a shadow vector feature but the comparison report does not produce meaningful output. In 2.1, the report includes centroid drift and dimension-wise PSI for vector features. If you serve embeddings, this is the single most useful change in the release for you.

## A workflow recommendation

For any feature that more than five downstream features depend on, my personal rule is: shadow first, every time. The cost of the shadow run is almost always less than the cost of debugging a bad promotion. We have a slightly informal team norm around this and it has saved us more than once.

Shadow serving is unglamorous. It is also the thing that lets us change features in production without holding our breath. I would rather work on a platform that has it than one that does not.

*Aisha works on the Tessera ML engineering team. Comments welcome on the community Slack.*
