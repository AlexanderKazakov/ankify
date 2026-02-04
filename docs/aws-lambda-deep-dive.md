# AWS Lambda Deep Dive: A Practical Guide

A comprehensive guide based on deploying an MCP server (Ankify) to AWS Lambda with Function URLs, covering execution model, logging, scaling, pricing, and configuration.

---

## Table of Contents

1. [Understanding Lambda Logs](#understanding-lambda-logs)
2. [Lambda Execution Model](#lambda-execution-model)
3. [Scaling Behavior](#scaling-behavior)
4. [All Configurable Parameters](#all-configurable-parameters)
5. [Pricing](#pricing)
6. [Practical Configuration Example](#practical-configuration-example)

---

## Understanding Lambda Logs

### Cold Start Sequence

When a Lambda function starts cold, you'll see a sequence like this:

```
INFO lambda_web_adapter: app is not ready after 2000ms url=http://127.0.0.1:8080/health
2026-02-04 19:36:51,077 - INFO - Using Azure TTS provider...
INFO: Started server process [11]
INFO: Waiting for application startup.
INFO: Application startup complete.
INFO: Uvicorn running on http://0.0.0.0:8080 (Press CTRL+C to quit)
INFO: 127.0.0.1:43682 - "GET /health HTTP/1.1" 200 OK
EXTENSION Name: lambda-adapter State: Ready Events: []
START RequestId: c5015259-f8ee-4c34-ae9a-35c6367ab048 Version: $LATEST
INFO: 160.79.106.16:0 - "POST /mcp HTTP/1.1" 200 OK
END RequestId: c5015259-f8ee-4c34-ae9a-35c6367ab048
REPORT RequestId: c5015259-f8ee-4c34-ae9a-35c6367ab048 Duration: 50.31 ms Billed Duration: 2791 ms Memory Size: 333 MB Max Memory Used: 186 MB Init Duration: 2739.99 ms
```

### What Contributes to Init Duration (~2.7s in this example)

| Component           | Time       | Notes                               |
| ------------------- | ---------- | ----------------------------------- |
| Lambda runtime init | ~50-100ms  | Minimal                             |
| Container start     | ~100-200ms | NOT Docker pull (cached separately) |
| Python interpreter  | ~200-300ms |                                     |
| Dependency imports  | ~2000ms+   | FastMCP, Pydantic, boto3, etc.      |
| Module-level code   | Variable   | Loading resources, secrets, etc.    |

**Important:** Docker image pull is NOT included in Init Duration. Lambda caches container images separately. First-ever deploy has additional latency, but subsequent cold starts use the cached image.

### Log Line Ownership

| Log Line                                                     | Source             | Explanation                             |
| ------------------------------------------------------------ | ------------------ | --------------------------------------- |
| `INFO lambda_web_adapter: app is not ready...`             | Lambda Web Adapter | LWA binary polling `/health` endpoint |
| `START RequestId: ...`                                     | Lambda Platform    | AWS Lambda marking invocation start     |
| `END RequestId: ...`                                       | Lambda Platform    | AWS Lambda marking invocation end       |
| `REPORT RequestId: ... Duration: ... Billed Duration: ...` | Lambda Platform    | Billing/metrics summary                 |
| `EXTENSION Name: lambda-adapter State: Ready`              | Lambda Platform    | Acknowledging LWA extension is ready    |
| `INFO: Started server process [11]`                        | Uvicorn            | Server startup log                      |
| `INFO: Application startup complete.`                      | Uvicorn            | ASGI lifespan protocol                  |
| `INFO: 127.0.0.1:... - "GET /health"`                      | Uvicorn            | Access log — internal LWA health check |
| `INFO: 160.79.106.16:... - "POST /mcp"`                    | Uvicorn            | Access log — external requests         |
| `2026-02-04 ... - INFO - fastmcp...`                       | Your app           | Your logger output                      |

**IP Address Hints:**

- `127.0.0.1` — Internal LWA health checks
- External IPs — Real requests from outside

### What is a "Request" (Invocation)?

In Lambda context, **request = invocation**. Each time something triggers your Lambda (HTTP request, S3 event, SQS message, etc.), Lambda creates one invocation with a unique `RequestId`.

```
External HTTP Request (POST /mcp)
        ↓
    Function URL
        ↓
    Lambda Invocation (RequestId: abc123)
        ↓
    Lambda Web Adapter receives it
        ↓
    Forwards to Uvicorn (http://127.0.0.1:8080/mcp)
        ↓
    Your FastMCP app handles it
        ↓
    Response flows back up
```

**One HTTP Request = One Lambda Invocation = One START/END/REPORT block**

### Log Streams vs Log Groups

- **Log Group:** Container for all logs from a Lambda function (e.g., `/aws/lambda/AnkifyMcpServer`)
- **Log Stream:** Logs from a single Lambda instance's lifetime

## Lambda Execution Model

### One Invocation Per Instance

This is **universal to Lambda**, not specific to Function URLs:

| Trigger Type  | Still 1 invocation per instance?             |
| ------------- | -------------------------------------------- |
| Function URL  | Yes                                          |
| API Gateway   | Yes                                          |
| ALB           | Yes                                          |
| S3 events     | Yes                                          |
| SQS           | Yes (can batch messages into one invocation) |
| Direct invoke | Yes                                          |

### The Uvicorn Paradox

When running an async web server (Uvicorn) inside Lambda:

```
Uvicorn's potential:     1000 concurrent requests
Lambda's restriction:    1 concurrent invocation
Actual throughput:       1 at a time per instance
```

Uvicorn's concurrency capabilities are wasted. It's only there because Lambda Web Adapter needs an HTTP server to forward to.

### Where Requests Wait: Lambda vs Normal Server

**Lambda:** Requests wait in AWS's internal infrastructure. But Lambda doesn't really queue for busy instances:

```
Request arrives
    ↓
Is there a warm idle instance? → Yes → Route to it
    ↓ No
Are we at concurrency limit? → Yes → Return 429 (throttled)
    ↓ No
Spin up new instance (request waits during cold start)
```

**Normal async server (Uvicorn outside Lambda):**

| Layer                 | Queue Location            |
| --------------------- | ------------------------- |
| OS kernel             | TCP accept queue          |
| Reverse proxy (nginx) | Connection pool           |
| ASGI server (uvicorn) | asyncio event loop        |
| Your app              | Explicit queue (if built) |

With asyncio, one process handles many concurrent requests by switching during I/O waits.

### Key Difference

|                          | Lambda                      | Normal async server     |
| ------------------------ | --------------------------- | ----------------------- |
| Concurrency per instance | 1                           | Hundreds/thousands      |
| Scaling model            | Horizontal (more instances) | Vertical + horizontal   |
| You pay for I/O waits    | Yes                         | No (other requests run) |

---

## Scaling Behavior

### Can You Delay Scaling?

**No.** Lambda's philosophy is: scale immediately, never queue. There's no "wait N seconds for busy instance" option.

### Controlling Concurrency

**`reserved_concurrent_executions`** does two things:

| Effect                          | Explanation                          |
| ------------------------------- | ------------------------------------ |
| **Reserves** (guarantees) | Carves out N from account pool       |
| **Caps** (limits)         | Function can**never** exceed N |

There is no separate "max concurrency" setting. Reservation = cap.

```python
reserved_concurrent_executions=100  # Max 100 concurrent, reserved from pool
```

Request #101+ gets throttled (429), not queued.

### Provisioned Concurrency

Keeps N instances pre-warmed (eliminates cold starts for first N concurrent requests):

```python
# Requires versioning/alias
version = lambda_fn.current_version
lambda_.Alias(
    self, "ProdAlias",
    alias_name="prod",
    version=version,
    provisioned_concurrent_executions=1,
)
```

**Cost:** ~$0.0000041667/GB-s for keeping warm ≈ $11/month for 333MB × 1 instance × 24/7

**Important:** Provisioned concurrency doesn't change the execution model — still 1 request per instance. It just eliminates cold start for the first request.

### Burst Limits

Burst is **account-level and region-fixed**. You cannot configure it per-function.

| Region                          | Burst Limit |
| ------------------------------- | ----------- |
| us-east-1, us-west-2, eu-west-1 | 3,000       |
| ap-northeast-1, eu-central-1    | 1,000       |
| Others                          | 500         |

With `reserved_concurrent_executions=100`, burst doesn't matter — you're capped at 100 anyway.

---

## All Configurable Parameters

### Function-Level Parameters

| Parameter                                   | Default             | Range/Options               | Explanation                                        |
| ------------------------------------------- | ------------------- | --------------------------- | -------------------------------------------------- |
| **memory_size**                       | 128 MB              | 128–10,240 MB              | Also scales CPU proportionally. 1,769 MB ≈ 1 vCPU |
| **timeout**                           | 3 sec               | 1–900 sec (15 min)         | Max execution time per invocation                  |
| **ephemeral_storage**                 | 512 MB              | 512–10,240 MB              | `/tmp` directory size                            |
| **architecture**                      | x86_64              | `x86_64`, `arm64`       | ARM is ~20% cheaper                                |
| **reserved_concurrent_executions**    | None                | 0–account limit            | Hard cap AND reservation. 0 = disabled             |
| **provisioned_concurrent_executions** | None                | 1–account limit            | Pre-warmed instances (per alias/version)           |
| **retry_attempts** (async)            | 2                   | 0–2                        | Retries for async invocations                      |
| **maximum_event_age** (async)         | 6 hours             | 60 sec–6 hours             | Max time event waits before discard                |
| **dead_letter_queue**                 | None                | SQS or SNS ARN              | Where failed async invocations go                  |
| **tracing_config**                    | PassThrough         | `Active`, `PassThrough` | X-Ray tracing                                      |
| **vpc_config**                        | None                | Subnets + security groups   | Run inside VPC (adds cold start latency)           |
| **file_system_config**                | None                | EFS ARN + mount path        | Persistent storage                                 |
| **layers**                            | None                | Up to 5 layer ARNs          | Shared code/dependencies                           |
| **snap_start**                        | None                | `PublishedVersions`       | Java only — snapshot after init                   |
| **logging_config**                    | CloudWatch defaults | Log group, format, levels   | JSON vs text                                       |
| **recursive_loop**                    | Terminate           | `Terminate`, `Allow`    | Kill recursive loops                               |

### Function URL Parameters

| Parameter             | Default      | Options                           | Explanation                    |
| --------------------- | ------------ | --------------------------------- | ------------------------------ |
| **auth_type**   | (required)   | `NONE`, `AWS_IAM`             | Public vs signed requests      |
| **invoke_mode** | `BUFFERED` | `BUFFERED`, `RESPONSE_STREAM` | Streaming vs complete response |
| **cors**        | None         | Origins, methods, headers         | CORS configuration             |

### Invoke Mode Details

| Mode                | Behavior                                   | Use Case                             |
| ------------------- | ------------------------------------------ | ------------------------------------ |
| `BUFFERED`        | Lambda waits for full response, then sends | Standard request/response, JSON APIs |
| `RESPONSE_STREAM` | Chunks sent as produced                    | SSE, streaming, long responses       |

**Important:** If using `json_response=True` in FastMCP, use `BUFFERED`. Mismatched modes can cause timeout issues.

### Account/Region-Level Limits

| Limit                 | Default    | Adjustable?                        |
| --------------------- | ---------- | ---------------------------------- |
| Concurrent executions | 1,000      | Yes (request quota increase)       |
| Burst concurrency     | 500–3,000 | No (region-fixed)                  |
| Unreserved minimum    | 100        | No (AWS keeps for other functions) |

---

## Pricing

### Core Charges (US East, 2025)

| Component               | Free Tier       | Paid Rate                             |
| ----------------------- | --------------- | ------------------------------------- |
| **Requests**      | 1M/month        | $0.20 per 1M ($0.0000002/request)     |
| **Compute (x86)** | 400K GB-s/month | $0.0000166667 per GB-s                |
| **Compute (ARM)** | 400K GB-s/month | $0.0000133334 per GB-s (~20% cheaper) |

### GB-Second Calculation

```
GB-seconds = Memory (GB) × Duration (seconds)

Example: 333 MB function running 1 second
= 0.333 GB × 1 s = 0.333 GB-s
= 0.333 × $0.0000166667 = $0.0000055 per invocation
```

### Cost Per Invocation Example (333 MB, ARM)

| Phase                         | Duration | GB-s  | Cost        |
| ----------------------------- | -------- | ----- | ----------- |
| Cold start (init)             | ~2.7s    | 0.9   | ~$0.000012  |
| Warm request (fast)           | ~50ms    | 0.017 | ~$0.0000002 |
| Warm request (TTS generation) | ~30s     | 10    | ~$0.000133  |

### Additional Charges

| Component                | Rate                                              | Notes                   |
| ------------------------ | ------------------------------------------------- | ----------------------- |
| Ephemeral storage        | $0.0000000309/GB-s above 512 MB                   | First 512 MB free       |
| Provisioned Concurrency  | $0.0000041667/GB-s                                | For keeping warm        |
| Data transfer (outbound) | $0.09/GB                                          | First 100 GB/month free |
| Secrets Manager          | $0.40/secret/month | Plus $0.05 per 10K API calls |                         |
| S3 storage               | $0.023/GB/month                                   |                         |

### Cost Optimization Tips

1. **Use ARM (Graviton2)** — 20% cheaper, often faster
2. **Right-size memory** — More memory = more CPU but higher cost
3. **Minimize cold starts** — Each wastes ~2-3s of compute
4. **Free tier is generous** — 400K GB-s covers many use cases
5. **Requests are cheap** — Compute duration dominates costs

---

## Quick Reference

### Log Interpretation Cheat Sheet

```
REPORT RequestId: xxx Duration: 50.31 ms Billed Duration: 2791 ms Memory Size: 333 MB Max Memory Used: 186 MB Init Duration: 2739.99 ms
         │                │                    │                   │                      │                        │
         │                │                    │                   │                      │                        └─ Cold start time
         │                │                    │                   │                      └─ Actual memory consumed
         │                │                    │                   └─ Configured memory
         │                │                    └─ What you pay for (Duration + Init)
         │                └─ Actual execution time (excluding init)
         └─ Unique invocation ID
```

### When to Use What

| Goal                           | Setting                                               |
| ------------------------------ | ----------------------------------------------------- |
| Limit max concurrent instances | `reserved_concurrent_executions=N`                  |
| Eliminate cold starts          | `provisioned_concurrent_executions=N` (costs extra) |
| Handle large payloads          | Increase `memory_size` and `ephemeral_storage`    |
| Long-running tasks             | Increase `timeout` (max 15 min)                     |
| Streaming responses            | `invoke_mode=RESPONSE_STREAM`                       |

### Common Issues

| Symptom               | Likely Cause            | Fix                                            |
| --------------------- | ----------------------- | ---------------------------------------------- |
| 429 errors            | Hit concurrency limit   | Increase `reserved_concurrent_executions`    |
| Timeout errors        | Task takes too long     | Increase `timeout`                           |
| OOM / function killed | Memory exceeded         | Increase `memory_size`                       |
| Slow responses        | Cold starts             | Use provisioned concurrency or keep-warm pings |
| High costs            | Over-provisioned memory | Right-size with Lambda Power Tuning            |
