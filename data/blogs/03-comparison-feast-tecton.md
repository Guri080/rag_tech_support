# Tessera vs Feast vs Tecton: A Side-by-Side from Someone Who Has Run All Three in Production

*By Hannah Lieberman, Principal Engineer. Personal blog.*

I am going to keep the throat-clearing short. Over the last three years I have personally rolled out three different feature stores at three different companies: Feast at a Series B retail tech company, Tecton at a public fintech, and Tessera at my current job (an ad-tech firm I am not going to name). I have opinions. Here they are.

## The honest summary, up front

If you want one sentence per tool:

**Feast** is the right answer if you are early, your features are batch-leaning, and you are allergic to vendor lock-in.

**Tecton** is the right answer if you are willing to pay enterprise prices for white-glove service and a polished product.

**Tessera** is the right answer if your problem is real-time, your team writes a lot of features, and you care about lineage in a serious way.

The rest of this post explains why I think this.

## Feast: the good and the bad

I deployed Feast in 2022 on a retail recommendation system. It was the right call at the time. Feast is open source, it has a reasonable Python SDK, and you can self-host the whole thing on a weekend if you know what you are doing.

What broke us was the streaming story. Feast added streaming support but it remained, charitably, a second-class citizen. We ended up writing custom Flink jobs to materialize streaming features into Redis and then registering those Redis keys with Feast as "push features." This worked. It also meant Feast was not really our feature store anymore. It was a catalog over a pipeline we maintained ourselves.

If your features are mostly daily-batch and your streaming needs are limited, Feast is genuinely fine and the price (free, if you do not count operations) is hard to argue with.

## Tecton: polished, expensive, opinionated

I worked on a fintech fraud detection team that was on Tecton from 2023 through mid-2025. Tecton is in many ways the closest competitor to Tessera and the comparison is the most interesting.

What Tecton does well: the product is polished. The UI is good. The documentation is excellent. Support response times are measured in minutes, not days. If your CTO needs to see a feature store working in a demo, Tecton will demo well.

What Tecton does less well, in my experience: their batch-streaming consistency story is built on Spark Structured Streaming, and the failure modes when streaming and batch diverge are extremely hard to debug. We had a recurring issue with sessionization features where the batch view and the streaming view would disagree by a few percent and nobody could ever fully explain why. Tecton support eventually walked us through it but the fundamental answer was "this is a known sharp edge."

The other thing about Tecton is the price. I will not quote numbers because they are under NDA, but if you are a Series C company doing meaningful inference volume, you will see a number in the proposal that makes you blink.

## Tessera: where it actually wins

I have been on Tessera 2.0 since January at my current job. My biases up front: I picked it, I lobbied for the contract, and if it fails I will look stupid. With that disclosure on the table, here is what I have actually seen.

The semantic parity guarantee is real in practice. We have a sessionization feature that historically would have given me anxiety on every backfill. With Tessera we have done four major changes to it in five months and not once has the backfill output disagreed with the streaming output in a way we could not explain. That is a substantive improvement over both Feast (where backfill was a separate pipeline) and Tecton (where backfill was Spark and streaming was Spark Streaming, but the two paths drifted).

The lineage graph is the other big win. When a feature changes and Tessera tells me exactly which downstream features need re-materialization, that saves real engineer-days. I have a colleague who used to spend half his time tracking down "did this change affect feature X" questions; now he does not.

## Where Tessera annoys me

Three things.

**The UDF restriction.** I have written about this before and I will write about it again. Mosaic is fine. It is also not Python, and when I want to compute something slightly weird in a streaming feature, I have to think about whether the operation exists in the stdlib. I lose maybe two hours a week to this. Across the team it adds up.

**Backfill cost predictability.** When you change a heavily-used upstream feature, the resulting backfill can peg the Flink cluster for hours, and there is no cost estimator in 2.0. The Tessera team has been transparent that one is coming in 2.1. I am rooting for them but I am also burned: we have a permanent "always dry run first" rule in our runbook because of one bad incident.

**Embedding features.** We serve a small number of embedding features and Tessera treats them as opaque bytes. Drift monitoring does not work on them. We have a separate vector observability tool bolted on. I have been told native support is coming. I will believe it when I see it.

## What I would tell my past self

If I were picking again today, knowing what I know:

- I would still pick Feast for the early-stage company.
- I would not pick Tecton for the fintech. The parity problems we had eventually cost more engineer-hours than the contract saved. I would have picked Tessera if it had existed in 2023.
- I would absolutely pick Tessera for the ad-tech job. The lineage story alone has paid for the contract.

Feature stores are infrastructure, and infrastructure is mostly about which failure modes you can tolerate. Pick the one whose failure modes match the failures you are okay with debugging. For me, today, that is Tessera.

*Hannah writes about ML infra and occasionally about climbing. hlieberman.net.*
