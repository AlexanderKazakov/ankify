FROM public.ecr.aws/docker/library/python:3.12-slim-bookworm

# Lambda Web Adapter (LWA) - /opt/extensions are run by Lambda automatically
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1 /lambda-adapter /opt/extensions/lambda-adapter

WORKDIR /var/task

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src/ ./src/

# local cache for pip to prevent downloading dependencies on every build, 
# we must specify the target arch for proper caching, since we build for arm64 on x86_64
ARG TARGETARCH
RUN --mount=type=cache,target=/root/.cache/pip,id=pip-${TARGETARCH} pip install ".[aws]"

CMD ["sh", "-c", "exec uvicorn ankify.mcp.ankify_mcp_server:app --host 0.0.0.0 --port $PORT"]