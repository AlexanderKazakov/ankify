# Ankify Deployment Spec: Persistent Container Server

**Status:** Proposed. Replaces the App Runner research note (`docs/ai_reports/app_runner.md`) and updates the auth part of the Lambda plan (`docs/ai_reports/aws_deployment_steps.md`).

**Goal:** Move Ankify from Lambda to a persistent server, reuse the same building blocks (custom domain, HTTPS, S3, Secrets Manager, Cognito OAuth, budget alarm), and keep it as simple and "out of the box" as possible.

**Date of research:** 2026-06-16. All facts were checked against current AWS and FastMCP documentation. Sources and confidence notes are at the end.

---

## 0. The one fact that decides everything

**AWS App Runner is closed to new customers.** This is stated on the official App Runner page:

> "After careful consideration, we decided to close AWS App Runner to new customers. Existing AWS App Runner customers can continue to use the service as normal, including creating new resources and services. AWS continues to invest in security and availability for AWS App Runner, but we do not plan to introduce new features."
> — https://docs.aws.amazon.com/apprunner/latest/dg/apprunner-availability-change.html

Two consequences:

1. **If this AWS account already used App Runner before the cutoff (around 2026-04-30), you can still create new App Runner services.** App Runner is then the best fit for Ankify (cheapest persistent server, simplest custom domain, safe request timeout). This is **Option A**.
2. **If this account never used App Runner, you probably cannot create one at all.** You must pick an alternative. AWS itself recommends **Amazon ECS Express Mode** (**Option B**).

App Runner is also in maintenance mode (no new features, possible future deprecation). That is a long-term risk to weigh even if you are eligible.

### Prerequisite check (do this first)

The AWS CLI is not installed in this repo's environment, so this was not run automatically. Run it yourself (in this session you can type `! aws ...` so the output lands here):

```bash
# If this returns one or more services, the account is an existing App Runner customer -> Option A is open.
aws apprunner list-services --region eu-central-1

# A more direct test: try to create a tiny throwaway service in the console.
# If the console blocks creation with a "closed to new customers" message, Option A is NOT available.
```

A non-empty list proves you are eligible. An empty list is not conclusive (listing is allowed even for blocked accounts) — the definitive test is whether the console/API lets you create a service.

---

## 1. Options at a glance

| | **A. App Runner** | **B. ECS Express Mode** | C. Lightsail Containers | D. Stay on Lambda |
|---|---|---|---|---|
| **Available to you?** | Only if existing customer | Yes (GA, all regions) | Yes | Yes (current) |
| **Idle cost / month** | ~$3–5 running, **$0 paused** | **~$18–25** (always-on ALB) | **$7 flat** (Nano) | **~$0.73** |
| **Request timeout vs our 30–60s TTS** | 120s fixed — **safe** | ALB idle timeout, raise to 120–180s — **safe** | ~60s, **not configurable — risky** | 15 min Lambda / ~120–180s via CloudFront — safe |
| **Custom domain effort** | Auto TLS cert, one CLI step, DNS CNAME. **No CloudFront, no us-east-1.** | You make the ACM cert + ALB rule + DNS | Built-in managed cert, attach in console. **Simplest.** | CloudFront + ACM in us-east-1 + DNS. **Most complex.** |
| **Persistent server (async, concurrency)** | Yes | Yes | Yes | No (per-request isolation) |
| **Reuses our ECR + CDK** | Yes (L2 alpha or L1) | Yes (CDK L1 or Fargate pattern) | Private ECR yes; CDK L1 only, deploy drift | Already fully in CDK |
| **Scale to zero** | No (pause only, wake takes minutes, not auto) | Fargate to zero, but ALB still bills | No | Yes (true serverless) |

**Recommendation:**

- **Eligible for App Runner → use Option A.** It is the only option that is both cheap (~$3–5/month, $0 when paused) and gives the simple persistent-server model with an easy custom domain.
- **Not eligible →** the honest trade-off:
  - If cost matters most: **stay on Lambda (Option D)** and finish the existing CloudFront plan. It is already ~80% built and costs ~$0.73/month. You lose the persistent-server benefits but keep money and a safe timeout.
  - If you specifically want the persistent-container model: **ECS Express Mode (Option B)**, accepting the ~$18–25/month ALB floor.
  - **Avoid Lightsail (Option C)** for our current synchronous TTS workload — its ~60-second, non-configurable timeout sits exactly on top of our 30–60s requests. It only becomes viable if we change the tool to an async job pattern (return a job id, client polls).

The rest of this spec gives full steps for **A** and **B**, summaries for **C** and **D**, and the cross-cutting work (code changes + Cognito OAuth on FastMCP 3.x) that every container option needs.

---

## 2. What stays the same in every option (the "reuse" list)

These map one-to-one from the Lambda plan and do not change with the runtime:

| Item | Reused as | Notes |
|---|---|---|
| Domain `ankify.dev` (Cloudflare registrar) | Same domain | DNS can stay at Cloudflare. Route 53 is optional (only needed for some apex setups). |
| S3 bucket for `.apkg` files, 1-day expiry | Same bucket and lifecycle rule | Already in `infra/cdk/stacks/ankify_stack.py`. |
| Azure TTS key in Secrets Manager (`ankify/azure-tts`) | Same secret | Injected into the container (see §6). |
| Cognito User Pool + OAuth (Level 3) | Same, with **FastMCP 3.x API** (see §7) | The old plan's "pin fastmcp <3" advice is **wrong now** — the project already runs FastMCP 3.x. |
| DynamoDB table for OAuth state | Same | Still needed: a container's default OAuth storage is in-memory and is lost on restart (see §7). |
| Budget alarm ($5/month) | Same | Console or CDK. |
| The FastMCP app and the single tool | Same code, with small runtime fixes (see §5) | |

**What you can delete versus the Lambda + CloudFront plan** (Option A and B both remove most of this):

- CloudFront distribution — gone (the server has its own HTTPS endpoint).
- ACM certificate in **us-east-1** — gone (App Runner manages its own cert; ECS uses a regional cert in eu-central-1).
- Origin secret header + the `OriginVerifyMiddleware` — gone (no CloudFront in front to authenticate).
- The "do not forward Host header" gotcha — gone.
- The CloudFront origin-response-timeout quota increase (the highest-risk blocker in the old plan) — gone.
- Lambda Web Adapter in the Docker image — gone (only Lambda needs it).

This deletion is the main reason the persistent-server model is "simpler" — about half of the old plan's moving parts disappear.

---

## 3. Option A — AWS App Runner (recommended if eligible)

### 3.1 Architecture

```
  MCP client (Claude Desktop, etc.)
        │  HTTPS  https://ankify.dev/mcp
        ▼
  Cloudflare DNS  (CNAME, "DNS only" / grey cloud)
        │
        ▼
  App Runner service           TLS certificate auto-managed by App Runner (ACM)
   ├─ uvicorn → FastMCP app    routes: /mcp, /health, /.well-known/*, /register
   ├─ Cognito OAuth in-app     (FastMCP AWSCognitoProvider, optional phase)
   ├─ instance role ───────────► S3 (decks), Secrets Manager (keys), Polly (TTS)
   └─ DynamoDB (OAuth state) + Azure TTS over the internet
   image pulled from ECR (built by CDK)
```

### 3.2 Cost

- Smallest size is **0.25 vCPU / 0.5 GB**. Memory is billed continuously (~$0.007 per GB-hour), so ~0.5 GB × 730 hours ≈ **~$2.5/month even when idle**. vCPU is billed only while a request is being processed, which for sporadic use is a few cents.
- **Paused = $0 compute.** `PauseService` drops to zero instances. But `ResumeService` takes a few minutes and is **not** triggered by an incoming request — so pause is only useful for "I will not use this for days," not for auto-sleep. For a hobby tool that is fine.
- Deploying from an ECR image avoids the source-code **build fee**. The small automatic-deployment fee is negligible either way.

### 3.3 Step-by-step

**1) Container image.** Reuse the existing Docker build through a CDK `DockerImageAsset` (CDK pushes it to ECR for you). Drop the Lambda Web Adapter from the Dockerfile (see §5). App Runner supports both x86_64 and arm64, so you can keep the current arm64 build.

**2) CDK service.** Two sub-options:

- **A-CDK-1 (recommended): the L2 alpha construct** `@aws-cdk/aws-apprunner-alpha` (Python import `aws_cdk.aws_apprunner_alpha`). It covers everything we need: ECR/asset source, instance role, autoscaling, HTTP `/health` check, env vars, Secrets Manager secrets, CPU/memory, port. It is still "experimental alpha" (API may change between CDK versions), so pin the alpha version.

  ```python
  import aws_cdk.aws_apprunner_alpha as apprunner
  from aws_cdk.aws_ecr_assets import DockerImageAsset, Platform

  image = DockerImageAsset(
      self, "AnkifyImage",
      directory=str(project_root),
      file="infra/docker/Dockerfile",
      platform=Platform.LINUX_ARM64,
  )

  service = apprunner.Service(
      self, "AnkifyService",
      source=apprunner.Source.from_asset(
          asset=image,
          image_configuration=apprunner.ImageConfiguration(
              port=8080,
              environment_variables={
                  "AWS_REGION": "eu-central-1",          # see §5 gotcha
                  "AWS_DEFAULT_REGION": "eu-central-1",
                  "ANKIFY_S3_BUCKET": bucket.bucket_name,
                  "ANKIFY_PRESIGNED_URL_EXPIRY": "86400",
                  "ANKIFY__PROVIDERS__AZURE__REGION": "westeurope",
              },
              environment_secrets={
                  # injects the secret value as an env var (no boto3 needed)
                  "ANKIFY__PROVIDERS__AZURE__SUBSCRIPTION_KEY":
                      apprunner.Secret.from_secrets_manager(azure_secret),
              },
          ),
      ),
      cpu=apprunner.Cpu.QUARTER_VCPU,
      memory=apprunner.Memory.HALF_GB,
      instance_role=instance_role,      # see step 3
      health_check=apprunner.HealthCheck.http(path="/health"),
      auto_scaling_configuration=scaling,   # optional, see step 5
  )
  ```

- **A-CDK-2 (no alpha dependency): the L1 construct** `aws_cdk.aws_apprunner.CfnService` + `CfnAutoScalingConfiguration`. Stable, in `aws-cdk-lib`, but verbose (you write the raw CloudFormation-shaped properties: `SourceConfiguration.ImageRepository`, `AuthenticationConfiguration.AccessRoleArn`, `InstanceConfiguration`, `HealthCheckConfiguration`). Use this only if you want zero alpha risk.

**3) IAM — two roles.**
- **Access role** (trust `build.apprunner.amazonaws.com`, managed policy `AWSAppRunnerServicePolicyForECRAccess`): lets App Runner pull the image from your private ECR repo. The L2 alpha auto-creates it if you do not pass one.
- **Instance role** (trust `tasks.apprunner.amazonaws.com`): the role your code runs as. Grant it the runtime permissions: S3 read/write on the bucket, `secretsmanager:GetSecretValue` on the secrets, `polly:SynthesizeSpeech` if you use Polly, and DynamoDB read/write if you add OAuth (§7). The container gets credentials from this role automatically — **no static AWS keys**.

**4) Secrets.** App Runner can inject Secrets Manager (and SSM Parameter Store) values straight into the container as environment variables (`environment_secrets` above). This **replaces** the boto3 `_get_azure_subscription_key()` fetch in the current code — the value simply arrives as `ANKIFY__PROVIDERS__AZURE__SUBSCRIPTION_KEY`. The instance role still needs `secretsmanager:GetSecretValue`.

**5) Autoscaling / concurrency.** One instance handles many concurrent requests; App Runner adds an instance only when in-flight requests pass `MaxConcurrency` (default 100). Our TTS request uses CPU for 30–60s on a 0.25 vCPU instance, so a handful of overlapping requests would compete before scale-out triggers. For a hobby tool with rare concurrency this is fine; if you expect bursts, set `MaxConcurrency` lower (e.g. 5–10) so it scales out sooner.

**6) Custom domain.** App Runner provisions and auto-renews the TLS certificate itself — no ACM work, no us-east-1, no CloudFront. **Custom domain association is not available in CloudFormation/CDK**, so do it once after `cdk deploy` via the console or CLI:

```bash
aws apprunner associate-custom-domain \
  --service-arn  <service-arn-from-cdk-output> \
  --domain-name  ankify.dev \
  --enable-www-subdomain          # optional; this flag is API-only
```

The response returns:
- a **DNS target** (an `*.<region>.awsapprunner.com` hostname) — point your domain at it;
- one or more **certificate validation records** (CNAMEs) — add them so ACM can issue and later renew the cert. **Never delete these** or auto-renewal breaks.

Add the records at Cloudflare. Two sub-options:
- **Subdomain `mcp.ankify.dev` (simplest):** one CNAME → the DNS target, plus the validation CNAMEs. Works at any DNS provider.
- **Apex `ankify.dev`:** you cannot CNAME a bare apex in plain DNS. Either use **Cloudflare CNAME flattening** (it turns the apex CNAME into A/AAAA automatically) or move DNS to **Route 53** and use an **ALIAS to App Runner** (supported since 2022, ~$0.50/month for the hosted zone). Cloudflare flattening keeps DNS where it is and avoids Route 53.

Cloudflare caveat: set these records to **"DNS only" (grey cloud)**, not proxied (orange cloud). The orange-cloud proxy breaks ACM's CNAME validation and renewal. Also make sure any CAA record allows `amazon.com`.

**7) Auth (optional phase).** See §7. You can deploy without auth first (simplest, the server is public), then add Cognito OAuth as a second step. `base_url` for Cognito = `https://ankify.dev`; the MCP endpoint stays `/mcp`.

**8) Pause to save money (optional).** `aws apprunner pause-service --service-arn ...` → $0 compute. Resume with `resume-service` (takes a few minutes). Can be automated with an EventBridge schedule + a small Lambda, but for a hobby tool manual pause is enough.

### 3.4 Gotchas

- **`AWS_REGION` is not set automatically** in an App Runner container (Lambda sets it; App Runner does not). boto3 then has no region and presigned URLs / Secrets / Polly calls fail. Set `AWS_REGION` and `AWS_DEFAULT_REGION` explicitly as env vars (done in the snippet above).
- **Custom domain is outside CDK** — it is a one-time CLI/console step. The CDK custom-resource workaround exists but adds complexity; the one-time CLI call is simpler.
- **No native scale-to-zero.** Pause is the only $0-idle path and wake is not request-triggered.
- **Maintenance mode.** No new features; plan for a possible future migration to ECS Express Mode.

---

## 4. Option B — Amazon ECS Express Mode (recommended if App Runner is unavailable)

AWS's own recommended replacement for App Runner. GA since 2025-11-21, in all regions including eu-central-1. One action provisions a Fargate service, an Application Load Balancer (ALB) with an HTTPS listener, autoscaling, security groups, and CloudWatch logs, using your default VPC's public subnets.

### 4.1 Cost — read this before choosing

ECS Express Mode itself is free; you pay for the underlying resources. The decider is the **Application Load Balancer**, which runs continuously: roughly **$0.027/hour in Frankfurt plus LCU charges ≈ ~$18–25/month**, present whenever the service exists — even if you scale Fargate tasks to zero. Add Fargate for the task (smallest 0.25 vCPU / 0.5 GB ≈ ~$9/month if always on). So the realistic floor is **~$18–25+/month**, about 5–8× App Runner's idle floor. For a low-traffic hobby tool this is the main argument against it.

### 4.2 Step-by-step

**1) Image and IAM.** Same ECR image. Three roles: **task execution role** (pull from ECR, write logs — managed policy `AmazonECSTaskExecutionRolePolicy`), **task role** (your S3/Secrets/Polly/DynamoDB permissions), and an **infrastructure role** (`AmazonECSInfrastructureRoleforExpressGatewayServices`, lets ECS create the ALB and scaling for you).

**2) CDK.** Two sub-options:
- **B-CDK-1: the new L1** `aws_cdk.aws_ecs.CfnExpressGatewayService` (needs a recent `aws-cdk-lib` v2, around 2.230+). Maps 1:1 to `AWS::ECS::ExpressGatewayService`. No L2 yet, so it is verbose.
- **B-CDK-2 (more mature): `aws_cdk.aws_ecs_patterns.ApplicationLoadBalancedFargateService`.** This is the well-supported, full-control equivalent (Fargate + ALB + everything in your CDK stack). Same ALB cost. If you want stable IaC today, this is the safer choice; Express Mode's L1 is very new.

**3) Custom domain — not automatic.** The default `*.ecs.<region>.on.aws` URL gets an auto-managed cert, but for `ankify.dev` you do the work:
1. Request a **public ACM certificate for `ankify.dev` in eu-central-1** (same region — not us-east-1, because it attaches to a regional ALB).
2. Add an ALB HTTPS **listener rule** for the host `ankify.dev` → the service's target group, with that cert.
3. Point DNS at the ALB: Route 53 **ALIAS to the ALB**, or Cloudflare **CNAME to the ALB hostname** (apex via CNAME flattening). Any DNS provider works.

**4) Request timeout.** The ALB idle timeout defaults to **60 seconds** — right on top of our worst-case TTS request. Raise it (the ALB attribute `idle_timeout.timeout_seconds`, up to 4000s) to e.g. 120–180s. Then 30–60s requests are safe. This is actually more flexible than App Runner's fixed 120s.

**5) Scale to zero.** You can set `minTaskCount = 0` so Fargate tasks stop when idle, but the **ALB keeps billing**, and the first request after idle pays a Fargate cold start (a task launch) that can be slow — risky for a 30–60s synchronous request. For predictable behavior, keep `minTaskCount = 1`.

**6) Auth, secrets, env vars, region.** Same as Option A: Cognito OAuth in-app (§7), Secrets Manager values injected as env vars (`secrets` on the container definition), and set `AWS_REGION`/`AWS_DEFAULT_REGION` explicitly.

---

## 5. Cross-cutting: code and Docker changes (needed for any non-Lambda option)

The current server keys several behaviors off the `AWS_LAMBDA_FUNCTION_NAME` environment variable, which is **only set on Lambda**. On App Runner / ECS / Lightsail it is absent, so the logic breaks. Files: `src/ankify/mcp/ankify_mcp_server.py`.

| Current Lambda-only logic | Problem off Lambda | Fix |
|---|---|---|
| `_configure_logging_for_runtime`: rich logging off when `AWS_LAMBDA_FUNCTION_NAME` set | Container would use rich logging → noisy, hard-to-read CloudWatch logs | Use `enable_rich_logging = sys.stderr.isatty()` (rich only on a real terminal = local dev) |
| `decks_directory = /tmp/ankify` only when `AWS_LAMBDA_FUNCTION_NAME` set, else `~/ankify` | Container would try `~/ankify`; home may not exist or be writable | Use `/tmp/ankify` whenever running in the cloud. Simplest signal: `if os.environ.get("ANKIFY_S3_BUCKET")` → `/tmp/ankify`, else `~/ankify` |
| S3 upload gated on `ANKIFY_S3_BUCKET` | Already correct — works on any runtime | No change |
| `AWS_REGION` read with a default | Lambda sets `AWS_REGION`; containers do not | Set `AWS_REGION`/`AWS_DEFAULT_REGION` as explicit env vars in the service config (see §3.3) |

**Dockerfile** (`infra/docker/Dockerfile`): remove the Lambda Web Adapter layer — it is a Lambda extension and is dead weight on App Runner/ECS/Lightsail. Keep the rest:

```dockerfile
FROM public.ecr.aws/docker/library/python:3.12-slim-bookworm
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
COPY src/ ./src/
ARG TARGETARCH
RUN --mount=type=cache,target=/root/.cache/pip,id=pip-${TARGETARCH} pip install ".[aws]"
# App Runner/ECS set the listening port; default 8080
ENV PORT=8080
CMD ["sh", "-c", "exec uvicorn ankify.mcp.ankify_mcp_server:app --host 0.0.0.0 --port $PORT"]
```

If you want one image that still runs on Lambda too, keep the LWA `COPY` line — it is harmless when unused. A clean split is cleaner.

The health check (`GET /health`), the `app = mcp.http_app(stateless_http=True, json_response=True)` line, and the tool itself need no changes. `stateless_http=True` is still correct (and required if more than one instance can run).

---

## 6. Cross-cutting: secrets handling

Two equivalent ways to get the Azure key into the container:

- **Inject as env var (simpler, recommended for App Runner/ECS):** map the Secrets Manager secret to `ANKIFY__PROVIDERS__AZURE__SUBSCRIPTION_KEY` (see §3.3). The current `_get_azure_subscription_key()` boto3 fetch can then be removed — the value is already in the environment.
- **Fetch with boto3 at startup (current code):** keep `ANKIFY_AZURE_SECRET_ARN` and the boto3 call. Works too, using the instance/task role. No change needed.

Either way, follow the project's env conventions: `ANKIFY__PROVIDERS__...` (double underscore) for provider settings, and the existing single-underscore `ANKIFY_S3_BUCKET` / `ANKIFY_PRESIGNED_URL_EXPIRY` style for deployment flags.

To cut Secrets Manager cost (~$0.40 per secret per month), consider one JSON secret `ankify/auth-config` holding all auth values instead of one secret each.

---

## 7. Cross-cutting: Cognito OAuth on FastMCP 3.x

This reuses Level 3 of the Lambda plan but **corrects it for FastMCP 3.x**, which the project already runs (`fastmcp>=3.0.0,<4`). The old note said "pin fastmcp <3" — ignore that; it was written for v2.

### 7.1 What is the same in v3

- Import is unchanged: `from fastmcp.server.auth.providers.aws import AWSCognitoProvider`.
- Attach is unchanged: `mcp = FastMCP(name="Ankify", auth=auth_provider)`.
- The provider still auto-serves the discovery and registration routes at the root: `/.well-known/oauth-authorization-server`, `/.well-known/oauth-protected-resource`, `/.well-known/openid-configuration`, `/authorize`, `/token`, `/auth/callback`, `/register`. Because the app is mounted at root, no extra wiring is needed.
- Cognito has no Dynamic Client Registration, so the provider presents a DCR-compliant `/register` to MCP clients and uses your fixed Cognito client behind it. This is the intended pattern.
- The Cognito **Resource Server identifier must exactly equal `base_url` + the MCP path**, e.g. `https://ankify.dev/mcp`. A mismatch fails token exchange with `invalid_grant`.

### 7.2 What changed in v3 (and matters here)

- **Transport kwargs moved off the constructor.** In v3, `stateless_http` and `json_response` must be passed to `http_app()`, not to `FastMCP(...)`. The current code already does this correctly.
- **No env auto-loading of auth.** Pass `client_id` / `client_secret` explicitly (read from env or injected secret). The v2 `FASTMCP_SERVER_AUTH` mechanism is gone.
- **`AWSCognitoProvider` gained optional params:** `resource_base_url`, `issuer_url`, `redirect_path` (default `/auth/callback`), `required_scopes`, `allowed_client_redirect_uris`, plus token-lifetime knobs. Required params are still `user_pool_id`, `client_id`, `client_secret`, `base_url` (keyword-only); `aws_region` defaults to `eu-central-1`.
- **`jwt_signing_key` is now optional** — if omitted it is derived from the client secret. For a server that can restart or run more than one instance, **set it explicitly** so issued tokens stay valid across restarts and instances.

### 7.3 Persistence is still required (important for containers)

On Linux, FastMCP 3.x defaults OAuth client storage to **in-memory**. App Runner / ECS / Lightsail can restart or replace the instance, which would wipe all client registrations and force clients to re-register. So provide a **persistent `client_storage`** (DynamoDB) and a **fixed `jwt_signing_key`**:

```python
import os
from fastmcp.server.auth.providers.aws import AWSCognitoProvider
from key_value.aio.stores.dynamodb import DynamoDBStore          # py-key-value-aio[dynamodb]
from key_value.aio.wrappers.encryption import FernetEncryptionWrapper
from cryptography.fernet import Fernet

auth = AWSCognitoProvider(
    user_pool_id=os.environ["ANKIFY_COGNITO_USER_POOL_ID"],
    aws_region="eu-central-1",
    client_id=os.environ["ANKIFY_COGNITO_CLIENT_ID"],
    client_secret=os.environ["ANKIFY_COGNITO_CLIENT_SECRET"],   # injected from Secrets Manager
    base_url="https://ankify.dev",
    jwt_signing_key=os.environ["ANKIFY_JWT_SIGNING_KEY"],       # fixed, from Secrets Manager
    client_storage=FernetEncryptionWrapper(
        key_value=DynamoDBStore(table_name="ankify-oauth-state", region_name="eu-central-1"),
        fernet=Fernet(os.environ["ANKIFY_STORAGE_ENCRYPTION_KEY"]),
    ),
)
```

The DynamoDB + Fernet approach from the v2 plan is still valid in v3. **Verify the exact `DynamoDBStore` import path and constructor against the current `py-key-value-aio` library** before relying on it — the FastMCP docs name DynamoDB as supported but defer the details to that library, and some of its backends are marked preview.

### 7.4 Cognito setup (unchanged from the Lambda plan)

Same as `aws_deployment_steps.md` L3.1–L3.4: create the User Pool (Lite tier), an app client with the callback `https://ankify.dev/auth/callback` (and `http://localhost:8000/auth/callback` for local), grant type "authorization code", scopes `openid email profile`, a Cognito domain, and a **Resource Server with identifier `https://ankify.dev/mcp`**. Store the client secret, the JWT signing key, and the Fernet key in Secrets Manager and inject them.

### 7.5 Deploy without auth first

Auth is optional and separable. `FastMCP(name="Ankify", auth=None)` runs the server with no auth, which is the fastest way to get a working public endpoint. Add the Cognito provider as a second deployment once the domain and TLS work. This keeps the "out of the box" first step truly simple.

---

## 8. Secondary options (summary)

### C. Lightsail Container Services
Simplest domain story and cheapest flat price (**Nano $7/month**, 0.25 vCPU / 512 MB), built-in managed TLS certificate and custom domain with no load balancer, ACM, or CloudFront, and it can pull directly from a private ECR repo in the same region. **But the public endpoint's request timeout is about 60 seconds and is not user-configurable** (AWS does not document the exact value; community reports show 504s on long requests, and the only way to raise it is an AWS Support case). That collides directly with our 30–60s synchronous TTS. CDK support is L1-only (`CfnContainer`, `CfnCertificate`) and CloudFormation deploys are known to drift. **Use only if you first change the tool to an async job pattern** (return a job id, the client polls for the result), which removes the long synchronous request.

### D. Stay on Lambda (current)
Cheapest (~$0.73/month) and already mostly built. To get a custom domain you still need the CloudFront + ACM-in-us-east-1 + origin-secret path from `aws_deployment_steps.md` — the complexity you wanted to avoid. You also keep Lambda's per-request isolation (no shared async server). If App Runner is not available and ~$18–25/month for ECS is too much, finishing this plan is the rational fallback. The only code update needed is the FastMCP 3.x auth section in §7 (the rest of that doc is still valid; just drop the "pin fastmcp <3" note).

---

## 9. Suggested order of work

1. **Run the eligibility check in §0.** This picks Option A or not.
2. **Make the cross-cutting code + Docker changes (§5).** They are needed for any container option and are safe to do now. Update tests (logging/path selection).
3. **Deploy the chosen option without auth first** (§3 or §4), confirm `GET /health` and a real deck generation work over the new endpoint.
4. **Attach the custom domain** and confirm HTTPS.
5. **Add Cognito OAuth (§7)** as the final phase, with DynamoDB persistence and a fixed JWT key.
6. **Add the budget alarm** and (Option A) optionally a pause schedule.

---

## 10. Sources and confidence

**High confidence (official AWS / FastMCP docs, current 2026):**
- App Runner closed to new customers; existing customers can still create services; ECS Express Mode recommended — https://docs.aws.amazon.com/apprunner/latest/dg/apprunner-availability-change.html
- App Runner custom domains (auto ACM cert, DNS target + validation CNAMEs, Route 53 ALIAS supported, any DNS provider, up to 5 domains) — https://docs.aws.amazon.com/apprunner/latest/dg/manage-custom-domains.html
- App Runner custom domain **not** in CloudFormation/CDK; L2 alpha `aws_apprunner_alpha` lacks custom domains — https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-apprunner-service.html and https://docs.aws.amazon.com/cdk/api/v2/docs/aws-apprunner-alpha-readme.html
- App Runner pricing model, 120s fixed request timeout, pause/resume, two IAM roles, secret injection, default public egress, health check defaults, port 8080 — https://aws.amazon.com/apprunner/pricing/ , https://docs.aws.amazon.com/apprunner/latest/dg/develop.html , https://docs.aws.amazon.com/apprunner/latest/dg/manage-pause.html
- `AWS_REGION` is not auto-set in App Runner (only `PORT` is documented as auto) — confirmed by absence in https://docs.aws.amazon.com/apprunner/latest/dg/develop.html ; recommendation: set it explicitly.
- ECS Express Mode (GA 2025-11-21, all regions, ALB + Fargate, shared ALB, custom domain needs own ACM cert, CFN `AWS::ECS::ExpressGatewayService`, CDK L1 `CfnExpressGatewayService`, three IAM roles) — https://aws.amazon.com/about-aws/whats-new/2025/11/announcing-amazon-ecs-express-mode/ , https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-work.html
- ALB idle timeout default 60s, configurable to 4000s — AWS ELB docs.
- Lightsail Containers current, $7 Nano, built-in managed cert + custom domain, private-ECR support, no scale-to-zero — https://aws.amazon.com/lightsail/pricing/ , https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-container-service-ecr-private-repo-access.html
- FastMCP 3.x `AWSCognitoProvider` (import path, params, v3 transport-kwarg change, in-memory default storage on Linux, DynamoDB+Fernet still valid) — gofastmcp.com docs (aws-cognito integration, oauth-proxy, storage-backends, upgrading-from-v2) and the v3.4.2 source.

**Lower confidence / to verify yourself:**
- The exact App Runner closure **date** (~2026-04-30) comes from news reports, not the primary doc page. The decision-critical fact — that existing customers can still create services — is from the primary doc.
- Whether **this account** is an existing App Runner customer — run §0.
- Exact eu-central-1 ALB hourly rate and the smallest-ECS-Express cost — rough; the principle (an always-on ALB sets a ~$18–25/month floor) is solid.
- The exact `py-key-value-aio` `DynamoDBStore` import and constructor — confirm against that library before coding §7.3.
- Lightsail's exact request timeout — AWS does not publish it; treat ~60s as a hard, non-configurable risk.
