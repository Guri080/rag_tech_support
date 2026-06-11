# Why We Ripped Out Tessera After Eight Months

*By Kenji Tanaka, Engineering Manager. Personal blog at kenjit.dev.*

This is going to be a critical post, so I want to start with what I am not saying. I am not saying Tessera is bad software. I am not saying nobody should use it. I am saying that we, specifically, were the wrong fit for it, and the lessons from realizing that are worth writing down because I see a lot of teams making the same mistake we did.

We deployed Tessera 2.0 in September 2025 at a mid-stage SaaS company doing ML-driven product analytics. We ripped it out in May 2026. This post is the honest version of what happened.

## Why we picked it

The decision was mine, and I want to be clear about that because the failure was also mine. We had outgrown a homemade Redis-based feature pipeline and we were evaluating real feature stores. Tessera was attractive for three reasons.

First, the lineage story was genuinely better than anything else we looked at. Coming from a homemade system where "where does this feature come from" was answered by reading three different repos, the prospect of an actual lineage graph was exciting.

Second, the semantic-parity guarantee. We had been bitten by training-serving skew on a churn model and the marketing pitch resonated.

Third, the sales process. The Tessera team did a thorough technical evaluation with us, the AE was honest about limitations, and the contract terms were reasonable. The mistake was assuming that "the tool can do the job" and "the tool is the right fit for our team" were the same question.

## What went wrong

Three things, in order of severity.

**Our feature definitions did not fit Mosaic.** This is the big one. Our existing pipeline had accumulated about 180 features over four years. Roughly 60 of them used custom Python logic that did not have a clean Mosaic equivalent: bespoke user-agent parsing, a custom probability calibration function, a fuzzy-match deduplication routine for merchant names.

In a Mosaic streaming feature, you cannot use arbitrary Python. The documentation calls this out clearly and the Tessera team called it out during evaluation. I read it. I thought "we will just port the logic." Porting 60 features took five engineers more than three months, and we left maybe 15 of them as batch-only features because the streaming versions were too painful.

The fundamental issue: we had a Python-shaped problem and Tessera wanted us to have a Mosaic-shaped problem. The tool was not wrong. We were not wrong. The fit was wrong.

**The backfill bursts kept biting us.** We hit the well-documented "small change to a heavily-used upstream pegs the cluster" problem about once a month. The Tessera team is transparent about this and the upcoming 2.1 cost estimator will help. But in the eight months we were on the product, we ate two incidents that cost us roughly a day of engineering time each, and the cumulative effect on team trust in the platform was larger than the raw time cost.

I want to be fair here. The 2.1 estimator that is in late beta as I write this probably would have prevented both incidents. We just could not wait for it.

**The vector feature gap was a deal-breaker.** Our newer models, the ones we are investing in for 2026, lean heavily on embeddings. Tessera 2.0 treats vectors as opaque bytes. Drift monitoring does not work on them. Shadow serving comparisons do not work on them.

This was disclosed during evaluation. I knew it. I thought "we can bolt on a separate tool." We did bolt on a separate tool. The operational overhead of running two systems for one logical concern (feature serving plus monitoring) was higher than I projected. Every new vector feature became a question of "does this go in Tessera, the separate tool, or both?" The answer was "both," and "both" is expensive.

I am aware 2.1 adds native vector support. By the time it lands in GA we were already three months into our replacement project and committed.

## What we replaced it with

We went back to a homemade pipeline. I want to be honest that this is not necessarily a recommendation for other teams. We have a strong ML platform engineering team and we are willing to spend engineer-time on infrastructure. For teams without that profile, going back to "we will build it ourselves" is usually a bad call.

What we kept from the Tessera experience: the lineage graph concept. We have built a much simpler version of it in our own system, just enough to support our data-quality workflows.

What we did not keep: the parity guarantee, because we no longer have a unified DSL. Our streaming and batch pipelines are separate, and we have a manual process to keep them in sync. This is genuinely worse than what Tessera offered. It is also a tradeoff we have decided we can live with.

## What I would tell my past self

Three things.

One: a feature store is not a database. The choice is not "which one has the best technical specs." The choice is "which one matches the shape of features my team actually writes." We did not do this analysis carefully enough. We looked at the features Tessera could express and confirmed it could express most of them. We did not look at the features we had and ask whether the migration path was a six-week project or a six-month one.

Two: be honest about which limitations you can live with. The vector gap was the most visible limitation but it was actually the least painful. The UDF restriction was the most painful. I underweighted it because I told myself we would port the logic, and porting was harder than I projected.

Three: do not let the polish of the sales process flatter your assessment of the product. Tessera's evaluation team was excellent. The product is also a substantive piece of engineering. Neither of those facts has any bearing on whether the product is right for your specific team.

Tessera is a good product. We were not the right customer. If you are evaluating a feature store, my main advice is to spend more time on the migration math than on the demo.

*Kenji is an engineering manager who probably writes too much about his mistakes. kenjit.dev.*
