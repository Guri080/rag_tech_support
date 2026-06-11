# Configuration Reference

**Version:** 2.0

Tessera is configured through a layered system: cluster-wide settings in the Helm values file, per-feature settings in Mosaic definitions, and per-call settings passed through the SDK or REST API. This document is the canonical reference for every supported configuration key.

## Configuration Layers

Configuration is resolved in the following order, with later layers overriding earlier ones:

1. Built-in defaults compiled into the control plane.
2. Helm values applied at install time.
3. Cluster runtime configuration set via `tessera config set`.
4. Per-feature options declared in Mosaic decorators.
5. Per-call options passed through SDK or REST.

## Control Plane Configuration

These keys live under the top-level `control` block of the Helm values file.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `control.replicas` | int | `2` | Number of control plane replicas. Three or more is recommended for production. |
| `control.logLevel` | string | `info` | One of `debug`, `info`, `warn`, `error`. |
| `control.maxConcurrentBackfills` | int | `4` | Cluster-wide cap on concurrent backfill jobs. See the bursty-cost note in [Troubleshooting](./troubleshooting.md). |
| `control.lineageRetentionDays` | int | `730` | How long lineage records are retained. Lineage is append-only; raise with care. |
| `control.shadowServingEnabled` | bool | `true` | When true, shadow versions of features can be registered and compared against production. |
| `control.api.maxRequestBytes` | int | `4194304` | Maximum HTTP request size. Raise if you submit very large entity lists in online reads. |
| `control.api.rateLimitPerToken` | int | `1000` | Requests per second per API token. |

## Metadata Store Configuration

The metadata store holds feature definitions, the lineage graph, and training set manifests.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `metadata.postgres.host` | string | required | Postgres host. |
| `metadata.postgres.port` | int | `5432` | Postgres port. |
| `metadata.postgres.database` | string | `tessera` | Database name. |
| `metadata.postgres.user` | string | required | Database user. Must have DDL privileges on the schema. |
| `metadata.postgres.passwordSecret` | string | required | Kubernetes secret containing the password under key `password`. |
| `metadata.postgres.sslMode` | string | `require` | One of `disable`, `require`, `verify-ca`, `verify-full`. |
| `metadata.postgres.maxConnections` | int | `50` | Connection pool size per control plane replica. |

## Streaming Configuration

These keys control the Flink job submission path.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `flink.jobManagerUrl` | string | required | URL of the Flink job manager REST endpoint. |
| `flink.defaultParallelism` | int | `4` | Default parallelism for newly submitted streaming jobs. Override per feature with `@feature(parallelism=...)`. |
| `flink.checkpointIntervalSeconds` | int | `60` | Checkpoint interval applied to all Tessera-managed jobs. |
| `flink.checkpointStorage` | string | required | URI for checkpoint storage, e.g. `s3://example/flink-checkpoints`. |
| `flink.restartStrategy` | string | `exponential-delay` | One of `fixed-delay`, `exponential-delay`, `failure-rate`. |
| `flink.taskSlotsPerFeature` | int | `2` | Default task slots assigned to a single feature job. |

## Backfill Configuration

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `backfill.engine` | string | `duckdb` | One of `duckdb`, `spark`. Spark is required for datasets larger than approximately 2 TB. |
| `backfill.duckdb.memoryLimit` | string | `24GiB` | Per-worker memory cap. |
| `backfill.duckdb.threads` | int | `8` | Threads per backfill worker. |
| `backfill.spark.master` | string | `k8s://...` | Spark master URL when the Spark engine is selected. |
| `backfill.spark.executorMemory` | string | `8g` | Memory per executor. |
| `backfill.spark.executorCount` | int | `8` | Executor count. |
| `backfill.timezoneStrict` | bool | `true` | When false, window functions in the Spark adapter tolerate timezone mismatches between event-time and ingestion-time. See the parity note in [Troubleshooting](./troubleshooting.md). |

## Online Store Configuration

Multiple stores may be registered. Each is referenced by name from feature definitions.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `onlineStores[].name` | string | required | Logical name used in `@feature(online_store=...)`. |
| `onlineStores[].type` | string | required | One of `redis`, `dynamodb`, `cassandra`, `scylladb`. |
| `onlineStores[].endpoints` | list | required | Endpoint list. For DynamoDB, supply a single region string. |
| `onlineStores[].auth.passwordSecret` | string | conditional | Secret name for password-based auth. |
| `onlineStores[].auth.iamRole` | string | conditional | IAM role for DynamoDB. |
| `onlineStores[].readConsistency` | string | `eventual` | One of `eventual`, `strong`. Strong consistency increases read latency. |
| `onlineStores[].clientLoadBalancing` | string | `round-robin` | One of `round-robin`, `least-latency`, `pinned`. |

## Per-Feature Configuration

These options are passed to the `@feature` decorator in Mosaic. They override cluster defaults for a single feature.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `name` | string | required | Globally unique feature name. |
| `entity` | string or list | required | Entity key or composite key. |
| `online_store` | string | cluster default | Name of a registered online store. |
| `ttl` | duration | `24h` | TTL applied to online values. |
| `parallelism` | int | cluster default | Flink parallelism override. |
| `slo.staleness_p99` | duration | unset | Per-feature SLO for event-to-serve latency. Violations alert through configured notifiers. |
| `slo.drift_psi` | float | unset | PSI threshold above which a drift alert fires. |
| `shadow_of` | string | unset | When set, marks this definition as a shadow of the named production feature. |

## Alerting Configuration

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `alerting.providers.pagerduty.integrationKey` | string | unset | PagerDuty Events API v2 integration key. |
| `alerting.providers.opsgenie.apiKey` | string | unset | Opsgenie API key. |
| `alerting.providers.slack.webhookUrl` | string | unset | Slack incoming webhook URL. |
| `alerting.defaultProvider` | string | unset | Provider used when a feature SLO does not specify one. |

## Environment Variables

The CLI and SDKs honor the following environment variables.

| Variable | Description |
|----------|-------------|
| `TESSERA_ENDPOINT` | Control plane URL. |
| `TESSERA_API_TOKEN` | API token for authentication. |
| `TESSERA_PROFILE` | Named profile to load from `~/.tessera/config.yaml`. |
| `TESSERA_LOG_LEVEL` | Client-side log level. |
| `TESSERA_TIMEOUT_MS` | Default per-request timeout in milliseconds. |
