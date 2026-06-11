# Reading the Tessera Lineage Graph: A Tour for the Curious

*By Sven Aalto, Staff Data Engineer. Personal blog at sven.engineering.*

Most users of Tessera interact with the lineage graph through the dashboard. You click on a feature, you see boxes connected by arrows, you confirm something looks right, you go back to writing code. This is fine. This is also leaving the most interesting part of the product on the table.

This post is for people who want to actually query the lineage graph and use it as a tool. I have been doing this for about four months as part of a data-quality initiative at my company. Most of what I have learned is not in the official docs, partly because the lineage API was not really designed for power users and partly because the docs are written for the dashboard use case.

I am writing this against Tessera 2.0. Where I know 2.1 is going to change something, I will note it.

## The shape of the graph

The lineage graph is a directed acyclic graph with three node types: sources, features, and training sets. Edges represent dependencies. A feature node has incoming edges from every source or upstream feature it reads from, and outgoing edges to every downstream feature or training set that consumes its output.

Each node carries metadata. Each edge carries a transformation reference (the version of the Mosaic IR that produced the dependency). The interesting thing is that the graph is bitemporal in the same sense that feature values are: every edge has both an "as-of event time" and an "as-of ingestion time," which means you can query the graph as it existed at any past moment.

This is the property that makes lineage actually useful. A static dependency graph would tell you what your features look like today. The bitemporal lineage tells you what they looked like in March, which is what you need when you are debugging why a model that worked in March is now producing weird outputs.

## The API I actually use

The dashboard hits `/v2/lineage/{feature_id}` under the hood. You can hit it directly:

```bash
curl -H "Authorization: Bearer $TESSERA_API_TOKEN" \
  "https://tessera.internal/v2/lineage/user_risk_score_v3?direction=both&depth=5"
```

The response is a JSON blob with the feature, its upstream sources and features, its downstream consumers, the version history, and the count of serving calls in the last 24 hours.

The two query parameters I actually care about are `depth` and `at`. The first is obvious. The second is the one most people miss: passing `at=2026-03-15T00:00:00Z` returns the lineage as of that ingestion timestamp. This is how you answer "what did the upstream of this feature look like when my March model was trained?"

## What I built with this

The data-quality project I am working on is, in summary: when a feature value flagged as anomalous by our drift monitoring shows up in production, I want to know within five minutes which upstream changes contributed to it.

The naive approach is to look at the feature itself, see if it changed recently, and shrug if it did not. This is wrong, because a feature that has not changed can still produce different values if its upstreams changed.

The lineage-aware approach is:

1. Get the lineage subgraph for the anomalous feature.
2. Walk upstream, recursively, collecting every feature and source that has had a version bump in the last seven days.
3. Cross-reference those changes with the bitemporal value history of the anomalous feature to see if the anomaly onset correlates with any specific upstream change.

I have this scripted in about 200 lines of Python. It is not pretty. It works.

The key insight is that the lineage API gives you everything you need to do this analysis offline, without instrumenting the model server or the streaming jobs. You just query the graph.

## What the docs do not tell you

A few things I learned the hard way.

**`depth=-1` is supposed to mean unbounded but actually returns `DEPTH_TOO_DEEP` past the configured cluster maximum (default 25).** If you have a deep DAG, you will need to paginate manually, walking one layer at a time. This is annoying. I have asked if it could be fixed; the response was "the cluster maximum exists for good operational reasons and we are not going to lift it, but we will document the workaround better." Fair enough.

**Serving call counts are sampled.** The `serving_calls_24h` field in the lineage response is not exact. The control plane samples online read traffic for cost reasons. If you are using this number to make capacity decisions, multiply by a fudge factor or hit the dedicated metrics endpoint instead.

**There is no batch lineage endpoint.** If you want lineage for 200 features, you make 200 calls. The Tessera team confirmed a batch endpoint was on the 2.1 roadmap. (Update: it landed in 2.1 GA. I have not used it yet but my colleague has and reports it works as advertised.)

## Where this is going

The lineage graph is, in my opinion, the most underrated feature of Tessera. Most users will never directly query it. But for the people who own data quality or who debug production model degradations, it is a genuinely powerful tool.

The thing I want next is a way to subscribe to lineage events. Right now I poll the API every five minutes. I would prefer to receive a webhook when a feature in my watch set has a version change. I have asked. It is "on the longer-term roadmap," which in Tessera-speak means "we agree it is a good idea but it is not in the next two releases." I will revisit this post when it lands.

For now, if you have not poked at the lineage API beyond the dashboard, I recommend spending an afternoon with it. There is more there than the UI exposes.

*Sven is a data engineer who writes too much and codes about as much as he should. sven.engineering.*
