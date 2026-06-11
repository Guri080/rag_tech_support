# Installation

**Version:** 2.0

This document covers installation of the Tessera control plane, worker tier, and client SDKs. Tessera is delivered as a set of container images and language-native SDK packages. There is no hosted offering; all components run inside your environment.

## System Requirements

### Control plane

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 4 vCPU | 16 vCPU |
| Memory | 8 GiB | 32 GiB |
| Disk | 50 GiB SSD | 500 GiB SSD |
| Kubernetes | 1.27 | 1.29 or later |
| Postgres (metadata store) | 14 | 16 |

### Streaming workers

Streaming materialization runs as Flink jobs submitted by the control plane. You must provide a Flink cluster of version 1.17 or later. Per-job sizing depends on event volume; the [Configuration Reference](./configuration.md) covers task slot tuning.

### Backfill workers

Backfills run on DuckDB for datasets up to approximately 2 TB. For larger historical replays, the Spark adapter is officially supported but development iteration is slower. The DuckDB path is single-node and scales vertically; provision at least 32 GiB of memory per backfill worker.

### Online stores

Tessera federates over the following stores. You must provision at least one before applying any feature definitions.

- Redis 6.0 or later
- DynamoDB (any region)
- Apache Cassandra 4.0 or later
- ScyllaDB 5.0 or later

## Installation Methods

### Helm (recommended)

The supported deployment method is Helm. Add the Tessera chart repository:

```bash
helm repo add tessera https://charts.tessera.io
helm repo update
```

Create a values file describing your environment:

```yaml
# tessera-values.yaml
license:
  key: "<your-license-key>"

metadata:
  postgres:
    host: postgres.internal.example.com
    port: 5432
    database: tessera
    user: tessera
    passwordSecret: tessera-postgres-password

flink:
  jobManagerUrl: http://flink-jobmanager.flink.svc.cluster.local:8081

onlineStores:
  - name: redis-primary
    type: redis
    endpoints:
      - redis-0.redis.svc.cluster.local:6379
      - redis-1.redis.svc.cluster.local:6379
    auth:
      passwordSecret: redis-password

control:
  replicas: 3
  ingress:
    enabled: true
    host: tessera.internal.example.com
    tls:
      enabled: true
      secretName: tessera-tls
```

Install the chart:

```bash
helm install tessera tessera/tessera \
  --namespace tessera \
  --create-namespace \
  --version 2.0.0 \
  --values tessera-values.yaml
```

The control plane will be reachable at the configured ingress host once the rollout completes. Verify with:

```bash
kubectl -n tessera rollout status deploy/tessera-control
```

### Docker Compose (development only)

A Compose configuration is available for local development. It is not supported for production use.

```bash
curl -L https://releases.tessera.io/v2.0.0/docker-compose.yaml -o docker-compose.yaml
TESSERA_LICENSE_KEY="<your-license-key>" docker compose up -d
```

This launches the control plane, an embedded Postgres, a local Flink mini-cluster, and a Redis instance. It is intended for evaluation and feature authoring against synthetic data.

## CLI Installation

The Tessera CLI is distributed as a static binary. Install with:

```bash
# macOS (Apple Silicon)
curl -L https://releases.tessera.io/v2.0.0/tessera-darwin-arm64 -o /usr/local/bin/tessera
chmod +x /usr/local/bin/tessera

# Linux (x86_64)
curl -L https://releases.tessera.io/v2.0.0/tessera-linux-amd64 -o /usr/local/bin/tessera
chmod +x /usr/local/bin/tessera
```

Verify the installation:

```bash
tessera version
# Tessera CLI v2.0.0
```

## SDK Installation

Tessera ships first-party client SDKs in Python, Go, and Java. They share a common protocol and feature set.

### Python

```bash
pip install tessera-client==2.0.0
```

Python 3.10 or later is required.

### Go

```bash
go get github.com/tessera-io/tessera-go@v2.0.0
```

Go 1.21 or later is required.

### Java

Add the Maven dependency:

```xml
<dependency>
  <groupId>io.tessera</groupId>
  <artifactId>tessera-client</artifactId>
  <version>2.0.0</version>
</dependency>
```

Java 17 or later is required.

## Post-Installation Verification

After installation, run the built-in health check:

```bash
tessera health --verbose
```

A healthy installation reports green status for the control plane, metadata store, Flink connection, and at least one configured online store. If any check fails, see the [Troubleshooting](./troubleshooting.md) document.

## Upgrading

In-place upgrades from 1.x to 2.0 are not supported because the lineage schema changed. Migration requires a parallel deployment and a feature-by-feature cutover. The upgrade tool `tessera migrate` automates most of this; consult your account team before beginning.

For minor version upgrades within the 2.x series, a standard Helm upgrade is sufficient:

```bash
helm upgrade tessera tessera/tessera \
  --namespace tessera \
  --version 2.0.1 \
  --values tessera-values.yaml
```
