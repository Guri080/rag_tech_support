# We Benchmarked Tessera 2.1 Against Our Hand-Rolled Redis Feature Layer. Here Are the Numbers.

*By Dmitri Yarov, Principal Engineer. Personal blog at dy.engineering.*

A short post with mostly numbers, because that is what the engineering audience for this comparison actually wants. The setup, the numbers, and the conclusion. If you want context and editorial, the second half of the post has that.

## Setup

We are an ad-tech company doing real-time bidding. We have an existing hand-rolled feature serving layer built on Redis Cluster with a custom Go client that I wrote in 2023. It serves around 180k feature reads per second at peak with a p99 latency of around 4 ms. It is in production. It works. The reason I am benchmarking against Tessera is that my CTO is asking me to justify why we should keep maintaining it.

The Tessera setup: Tessera 2.1 (early access, released to us last month) with the same Redis Cluster as the backing store, the same network topology, the same hardware. Same dataset, same feature shapes, replayed from the same Kafka topics.

Benchmark methodology: ten-minute load tests at four traffic levels, repeated five times each, p50 and p99 latency reported. All numbers are from the model server's perspective, measuring end-to-end feature read time from the client SDK call to the value being available.

## The numbers

| Traffic (reads/sec) | Hand-rolled p50 | Hand-rolled p99 | Tessera 2.1 p50 | Tessera 2.1 p99 |
|---------------------|-----------------|-----------------|-----------------|-----------------|
| 50k | 1.1 ms | 3.2 ms | 1.4 ms | 3.8 ms |
| 100k | 1.2 ms | 3.8 ms | 1.5 ms | 4.3 ms |
| 150k | 1.4 ms | 4.4 ms | 1.7 ms | 5.0 ms |
| 200k | 1.6 ms | 5.1 ms | 2.0 ms | 5.9 ms |

Tessera is consistently slower. About 20 to 30% on p50, about 15 to 20% on p99.

I want to be clear that this is a roughly fair comparison, not a perfectly fair one. The hand-rolled client knows things about our data layout that Tessera does not. The hand-rolled client also does not record any lineage, does not do any drift tracking, and does not have a shadow path. Tessera is doing more work per read. The latency difference is the price of that work.

## Reading the numbers honestly

A 20% latency increase at p50 is, for our workload, not significant. Our bidding model has a 50 ms total inference budget and feature reads are a small fraction of that. We could absorb the Tessera latency without changing anything downstream.

A 15 to 20% latency increase at p99 is more interesting. We have tail-latency SLOs that we negotiate carefully with the ad exchange, and giving up a millisecond at p99 is a real cost. Not a deal-breaker, but a cost.

The more important comparison is not latency. It is engineer-hours. The hand-rolled system has cost me, conservatively, four months of engineering time over three years for maintenance, bug fixes, and reluctant feature additions. I am the only person who fully understands it. If I leave the company, the system becomes a liability.

Tessera replaces this with a product the team can actually share ownership of, plus lineage, plus shadow serving, plus drift monitoring. The latency cost is the price of those things.

## What I am going to recommend

I am going to recommend we migrate.

The math, roughly: a one-millisecond p99 increase costs us a measurable but small amount on the bidding side, on the order of tens of thousands of dollars a year. The hand-rolled system costs me about a month and a half of engineering time per year, plus the bus-factor risk. Tessera's licensing cost is in the same neighborhood as the engineering time I would recover.

If Tessera were 2x slower, I would not migrate. At 20% slower with the feature parity we get back, the trade is clearly worth it for us.

## A few things I want to call out about 2.1 specifically

The benchmark above is 2.1. We ran the same benchmark against 2.0 in February and the numbers were materially worse, especially at p99 where 2.0 was about 30% slower than the hand-rolled system at our peak traffic. The 2.1 release notes mention "modest throughput improvements from a new batched-write path" for ScyllaDB but I do not see equivalent notes for Redis, and yet our Redis read latency improved noticeably. I asked the Tessera team about this and the answer was that the 2.1 client SDK has a redesigned connection pool that helps tail latency. Not on the headline release notes. Probably should be.

The embedding support in 2.1 is a separate story and not relevant to this benchmark (we do not serve embeddings yet) but I have spent some time with it and it looks reasonable.

The cost estimator on backfills is genuinely useful. I have not had to use it in anger but the demo output is detailed enough that I trust it.

## What I would tell you to do

If you have a hand-rolled feature serving layer and you are wondering whether to migrate to a managed feature store, the question to ask is not "is the managed system faster." It almost certainly is not. The question is "what is my hand-rolled system costing me in engineer-time and risk, and is the latency penalty of the managed system worth paying to recover that."

For us, the answer is yes. Your math will differ.

I will write a follow-up after the migration with the actual numbers on whether the projected engineer-time recovery materializes. If it does not, I will say so. I owe it to anyone reading this who is in a similar situation.

*Dmitri writes about low-latency systems and complains about distributed databases. dy.engineering.*
