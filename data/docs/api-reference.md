# API Reference

**Version:** 2.0
**Base URL:** `https://<your-tessera-host>/v2`

This document describes the five primary HTTP endpoints exposed by the Tessera control plane. All endpoints accept and return JSON unless noted otherwise. Authentication is performed by passing a bearer token in the `Authorization` header:

```
Authorization: Bearer <TESSERA_API_TOKEN>
```

All timestamps are RFC 3339 in UTC. All durations are ISO 8601. Errors follow a uniform envelope:

```json
{
  "error": {
    "code": "FEATURE_NOT_FOUND",
    "message": "No feature named 'user_txn_count_30m' is registered.",
    "request_id": "req_01HK2..."
  }
}
```

---

## 1. Register a Feature Definition

`POST /v2/features`

Registers a new feature definition or updates an existing one. The body must contain the compiled Mosaic plan; in normal operation this endpoint is called by the CLI on `tessera apply`, not by hand.

### Request

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Globally unique feature name. |
| `entity` | string or list | yes | Entity key or composite key. |
| `online_store` | string | yes | Name of a registered online store. |
| `ttl` | duration | no | Online value TTL. Defaults to cluster default. |
| `compiled_plan` | object | yes | Output of the Mosaic compiler. Contains both the Flink plan and the DuckDB plan. |
| `slo` | object | no | Per-feature SLO declarations. |
| `shadow_of` | string | no | If set, registers this feature as a shadow of the named production feature. |

### Response

`201 Created` on a new registration. `200 OK` on update.

```json
{
  "feature_id": "feat_01HK2X9...",
  "name": "user_txn_count_30m",
  "version": 7,
  "status": "materializing",
  "flink_job_id": "fjob_8a2c...",
  "created_at": "2026-06-11T14:22:01Z"
}
```

### Example

```bash
curl -X POST https://tessera.internal.example.com/v2/features \
  -H "Authorization: Bearer $TESSERA_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d @user_txn_count_30m.compiled.json
```

### Errors

| Code | HTTP | Description |
|------|------|-------------|
| `INVALID_PLAN` | 400 | The compiled plan failed validation against the streaming and backfill targets. |
| `STORE_NOT_FOUND` | 404 | The named online store is not registered. |
| `NAME_CONFLICT` | 409 | A feature with this name exists and belongs to a different owner. |

---

## 2. Read Online Feature Values

`POST /v2/features/values:batchGet`

Reads current values from the online store for one or more features across one or more entities. This is the hot path used by model servers.

### Request

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `features` | list of strings | yes | Feature names to fetch. |
| `entities` | object | yes | Map from entity key name to a list of entity values. |
| `read_consistency` | string | no | `eventual` (default) or `strong`. Strong consistency is only honored by stores that support it. |
| `include_metadata` | bool | no | When true, includes per-value bitemporal timestamps in the response. |

### Response

```json
{
  "values": {
    "user_txn_count_30m": {
      "u_8821": 14,
      "u_4410": 2
    }
  },
  "metadata": {
    "user_txn_count_30m": {
      "u_8821": {
        "event_time": "2026-06-11T14:21:55Z",
        "ingestion_time": "2026-06-11T14:21:57Z",
        "feature_version": 7
      }
    }
  },
  "request_id": "req_01HK2X..."
}
```

### Example

```bash
curl -X POST https://tessera.internal.example.com/v2/features/values:batchGet \
  -H "Authorization: Bearer $TESSERA_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "features": ["user_txn_count_30m"],
    "entities": {"user_id": ["u_8821", "u_4410"]}
  }'
```

### Errors

| Code | HTTP | Description |
|------|------|-------------|
| `FEATURE_NOT_FOUND` | 404 | One or more named features are not registered. |
| `ENTITY_MISMATCH` | 400 | A requested feature does not declare the supplied entity key. |
| `STORE_UNAVAILABLE` | 503 | The backing online store is unreachable. |

---

## 3. Create a Training Set Snapshot

`POST /v2/training-sets`

Materializes a point-in-time correct training set against the lineage graph and registers it as an immutable, content-addressed artifact.

### Request

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Human-readable name. Not required to be unique. |
| `features` | list of strings | yes | Feature names to include. |
| `entity_df` | string | yes | URI to a Parquet file containing entity keys and a timestamp column. |
| `timestamp_column` | string | yes | Column in `entity_df` providing the point-in-time cutoff for each row. |
| `output_uri` | string | no | Destination for the materialized Parquet output. Defaults to a managed location. |

### Response

```json
{
  "training_set_id": "ts_01HK2X...",
  "content_hash": "sha256:b1e7c9a4...",
  "feature_versions": {
    "user_txn_count_30m": 7
  },
  "row_count": 1842091,
  "output_uri": "s3://tessera-artifacts/ts/sha256/b1e7c9a4.../part-*.parquet",
  "status": "ready",
  "created_at": "2026-06-11T14:30:12Z"
}
```

The `content_hash` is computed as the SHA-256 of the sorted feature set and the per-row point-in-time cutoffs. Two callers who submit the same request will receive the same hash and bit-identical output.

### Errors

| Code | HTTP | Description |
|------|------|-------------|
| `ENTITY_DF_UNREADABLE` | 400 | The entity dataframe URI is not accessible from the backfill workers. |
| `BACKFILL_TOO_LARGE` | 413 | The estimated DuckDB working set exceeds 2 TB. Retry with `backfill.engine=spark` in cluster configuration. |

---

## 4. Trigger a Lineage-Aware Backfill

`POST /v2/backfills`

Recomputes historical feature values for a feature or set of features. Tessera computes the minimum re-materialization set by diffing the lineage DAG, so a backfill targets only those downstream features whose semantics actually changed.

### Request

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `features` | list of strings | yes | Features to backfill. Tessera will automatically include affected downstream features. |
| `start_time` | timestamp | yes | Inclusive event-time lower bound. |
| `end_time` | timestamp | yes | Exclusive event-time upper bound. |
| `dry_run` | bool | no | When true, returns the computed work set without executing. Recommended for any backfill touching a widely used upstream. |

### Response

```json
{
  "backfill_id": "bf_01HK2X...",
  "status": "queued",
  "work_set": {
    "direct": ["user_txn_count_30m"],
    "downstream": ["user_risk_score_v3", "merchant_volume_1d"]
  },
  "estimated_partitions": 1280,
  "submitted_at": "2026-06-11T14:33:01Z"
}
```

### Example

```bash
curl -X POST https://tessera.internal.example.com/v2/backfills \
  -H "Authorization: Bearer $TESSERA_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "features": ["user_session_agg"],
    "start_time": "2026-05-01T00:00:00Z",
    "end_time": "2026-06-01T00:00:00Z",
    "dry_run": true
  }'
```

### Errors

| Code | HTTP | Description |
|------|------|-------------|
| `WINDOW_INVALID` | 400 | `end_time` is not after `start_time`. |
| `QUOTA_EXCEEDED` | 429 | The configured `control.maxConcurrentBackfills` cap would be exceeded. |

---

## 5. Query the Lineage Graph

`GET /v2/lineage/{feature_id}`

Returns the lineage subgraph for a feature, including all upstream sources, all downstream features, and the history of versions, backfills, and serving call counts.

### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `feature_id` | string | Either a feature ID (`feat_...`) or a feature name. |

### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `direction` | string | `both` | One of `upstream`, `downstream`, `both`. |
| `depth` | int | `3` | Maximum hops from the target. Pass `-1` for unbounded. |
| `at` | timestamp | now | Returns the lineage as of the given ingestion-time. |

### Response

```json
{
  "feature": {
    "id": "feat_01HK2X...",
    "name": "user_txn_count_30m",
    "current_version": 7
  },
  "upstream": [
    {"id": "src_01HJ...", "name": "transactions", "type": "source"}
  ],
  "downstream": [
    {"id": "feat_01HK3...", "name": "user_risk_score_v3", "type": "feature"}
  ],
  "versions": [
    {
      "version": 7,
      "created_at": "2026-06-11T14:22:01Z",
      "author": "[email protected]",
      "compiled_plan_hash": "sha256:c81f..."
    }
  ],
  "serving_calls_24h": 18420113
}
```

### Errors

| Code | HTTP | Description |
|------|------|-------------|
| `FEATURE_NOT_FOUND` | 404 | The feature identifier does not resolve. |
| `DEPTH_TOO_DEEP` | 400 | `depth` exceeds the configured maximum (default 25). |
