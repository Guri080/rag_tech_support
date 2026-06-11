# Getting Started with Tessera

**Version:** 2.0
**Audience:** ML platform engineers, ML engineers, SREs

This guide walks you through registering your first feature with Tessera, materializing it from a live event stream, and serving it at inference time. By the end you will have a working end-to-end pipeline from a Kafka topic to an online store, with point-in-time lineage recorded for every value served.

## What Tessera Is

Tessera is a streaming feature store and lineage engine. It sits between your event bus and your model serving layer, compiling feature definitions written in the Mosaic DSL into both a streaming Flink job and a DuckDB plan for backfills. The same definition runs against live data and historical replays, and every materialized value is recorded in an immutable lineage graph so that any feature served at inference can be reconstructed exactly months later.

## Prerequisites

Before starting, you should have:

- A running Kafka, Kinesis, or Pub/Sub cluster with at least one topic carrying events you want to derive features from.
- An online store provisioned and reachable from the Tessera control plane: Redis 6+, DynamoDB, Cassandra 4+, or ScyllaDB 5+.
- A Flink cluster (1.17 or later) for the streaming materialization path.
- Python 3.10+ for authoring feature definitions.
- A Tessera license key. Contact your account team if you do not have one.

## Core Concepts

A few terms appear throughout the documentation. Understanding them before you start will save time later.

**Feature definition.** A Python file written in Mosaic that describes how to compute a feature from one or more source streams. It compiles to two execution plans: a Flink job for streaming materialization and a DuckDB plan for backfills and training set generation.

**Bitemporal value.** Every feature value in Tessera carries two timestamps: the event-time (when the underlying event occurred) and the ingestion-time (when Tessera observed it). This is what makes point-in-time correct training sets possible.

**Lineage graph.** A directed acyclic graph recording every transformation, backfill, and serving call. The graph is content-addressed, so two engineers training the same model specification receive bit-identical inputs.

**Online store.** The low-latency key-value store Tessera writes through to. Tessera does not ship its own store; it federates over Redis, DynamoDB, Cassandra, or ScyllaDB through a pluggable adapter layer.

## Five-Minute Walkthrough

The walkthrough below assumes you have already installed the Tessera CLI and SDK. If not, see the [Installation Guide](./installation.md).

### Step 1: Configure the control plane

Point the CLI at your Tessera deployment and authenticate.

```bash
tessera config set --endpoint https://tessera.internal.example.com
tessera login --token "$TESSERA_API_TOKEN"
```

### Step 2: Define a source stream

Source definitions tell Tessera where raw events live and how to parse them.

```python
# sources/transactions.py
from tessera import Source, Schema, Field, Timestamp

transactions = Source(
    name="transactions",
    connector="kafka",
    topic="prod.transactions.v1",
    schema=Schema([
        Field("user_id", "string"),
        Field("amount", "float64"),
        Field("merchant_id", "string"),
        Field("event_time", Timestamp()),
    ]),
    event_time_field="event_time",
    watermark_delay="30s",
)
```

Register the source:

```bash
tessera apply sources/transactions.py
```

### Step 3: Define a feature

The following Mosaic definition computes a user's rolling thirty-minute transaction count.

```python
# features/user_txn_count_30m.py
from tessera import feature, window
from sources.transactions import transactions

@feature(
    name="user_txn_count_30m",
    entity="user_id",
    online_store="redis-primary",
    ttl="2h",
)
def user_txn_count_30m():
    return (
        transactions
        .group_by("user_id")
        .window(window.tumbling(minutes=30))
        .agg(count="count(*)")
    )
```

Apply it:

```bash
tessera apply features/user_txn_count_30m.py
```

Tessera compiles the definition, submits the Flink job, and begins materializing values into Redis.

### Step 4: Serve the feature

Use the client SDK from your model server.

```python
from tessera.client import TesseraClient

client = TesseraClient(endpoint="https://tessera.internal.example.com")

values = client.get_online_features(
    features=["user_txn_count_30m"],
    entities={"user_id": ["u_8821", "u_4410"]},
)

print(values)
# {'user_txn_count_30m': {'u_8821': 14, 'u_4410': 2}}
```

Every read is recorded in the lineage graph along with the resolved feature version and the bitemporal timestamps of the values returned.

### Step 5: Generate a training set

When you are ready to train, materialize a point-in-time correct training set.

```python
training_set = client.create_training_set(
    name="fraud_model_v3_train",
    features=["user_txn_count_30m"],
    entity_df="s3://example/labels/fraud_labels_2026_q1.parquet",
    timestamp_column="label_time",
)
```

The returned artifact is content-addressed. Any engineer who runs the same call with the same entity dataframe and the same feature versions will receive an identical SHA-256.

## Where to Go Next

- [Installation Guide](./installation.md) for control plane and worker deployment.
- [Configuration Reference](./configuration.md) for the full set of tunable parameters.
- [API Reference](./api-reference.md) for direct HTTP access to the control plane.
- [Troubleshooting](./troubleshooting.md) for known issues and diagnostic procedures.
