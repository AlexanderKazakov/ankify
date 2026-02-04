from pathlib import Path
from typing import Final

from constructs import Construct
from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
    CfnOutput,
    aws_lambda as lambda_,
    aws_s3 as s3,
    aws_secretsmanager as secretsmanager,
)

_PROJECT_ROOT_MARKER: Final = "pyproject.toml"


def _find_project_root() -> Path:
    """Find project root by walking up to find pyproject.toml."""
    current = Path(__file__).resolve().parent
    for parent in [current, *current.parents]:
        if (parent / _PROJECT_ROOT_MARKER).exists():
            return parent
    raise FileNotFoundError(
        f"Could not find project root (no {_PROJECT_ROOT_MARKER} found)"
    )


class AnkifyStack(Stack):
    """Ankify MCP Server stack with Lambda + Function URL + S3."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        aws_lwa_port = "8080"
        project_root = _find_project_root()

        # Reference Azure credentials from Secrets Manager
        azure_secret = secretsmanager.Secret.from_secret_name_v2(
            self,
            "AzureTtsSecret",
            secret_name="ankify/azure-tts",
        )
        azure_region = self.node.try_get_context("azure_region") or "westeurope"

        # S3 bucket for storing .apkg files
        bucket = s3.Bucket(
            self,
            "AnkifyDecksBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            lifecycle_rules=[
                s3.LifecycleRule(
                    expiration=Duration.days(1),
                    enabled=True,
                )
            ],
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        )

        # Lambda function with Docker container
        lambda_fn = lambda_.DockerImageFunction(
            self,
            "AnkifyMcpServer",
            code=lambda_.DockerImageCode.from_image_asset(
                directory=str(project_root),
                file="infra/docker/Dockerfile",
            ),
            architecture=lambda_.Architecture.ARM_64,
            memory_size=333,
            timeout=Duration.minutes(1),
            reserved_concurrent_executions=100,
            environment={
                "PORT": aws_lwa_port,
                "AWS_LWA_PORT": aws_lwa_port,
                "AWS_LWA_READINESS_CHECK_PATH": "/health",
                "AWS_LWA_INVOKE_MODE": "BUFFERED",
                "ANKIFY_S3_BUCKET": bucket.bucket_name,
                "ANKIFY_PRESIGNED_URL_EXPIRY": "86400",
                "ANKIFY_AZURE_SECRET_ARN": azure_secret.secret_arn,
                "ANKIFY__PROVIDERS__AZURE__REGION": azure_region,
                "FASTMCP_ENABLE_RICH_LOGGING": "false",
            },
        )

        # Grant Lambda read/write access to S3 bucket
        bucket.grant_read_write(lambda_fn)

        # Grant Lambda access to read the Azure TTS secret
        azure_secret.grant_read(lambda_fn)

        # Function URL with no authentication (Level 1 MVP)
        function_url = lambda_fn.add_function_url(
            auth_type=lambda_.FunctionUrlAuthType.NONE,
            invoke_mode=lambda_.InvokeMode.BUFFERED,
        )

        # Outputs
        CfnOutput(
            self,
            "FunctionUrl",
            value=function_url.url,
            description="Ankify MCP Server Function URL",
        )

        CfnOutput(
            self,
            "BucketName",
            value=bucket.bucket_name,
            description="S3 bucket for Anki decks",
        )
