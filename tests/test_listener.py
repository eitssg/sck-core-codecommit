from unittest.mock import patch
import pytest

from core_codecommit.listener import handler


start_build_response = {
    "build": {
        "id": "my-build-id",
        "arn": "arn:aws:codebuild:us-west-2:123456789012:build/my-project:my-build-id",
        "startTime": "2023-10-01T12:34:56Z",
        "currentPhase": "SUBMITTED",
        "buildStatus": "IN_PROGRESS",
        "sourceVersion": "abcdef1234567890abcdef1234567890abcdef12",
        "resolvedSourceVersion": "abcdef1234567890abcdef1234567890abcdef12",
        "projectName": "my-project",
        "phases": [
            {
                "phaseType": "SUBMITTED",
                "phaseStatus": "SUCCEEDED",
                "startTime": "2023-10-01T12:34:56Z",
                "endTime": "2023-10-01T12:35:00Z",
            },
            {
                "phaseType": "QUEUED",
                "phaseStatus": "IN_PROGRESS",
                "startTime": "2023-10-01T12:35:00Z",
            },
        ],
        "source": {
            "type": "CODECOMMIT",
            "location": "https://git-codecommit.us-west-2.amazonaws.com/v1/repos/my-repo",
        },
        "artifacts": {"location": "arn:aws:s3:::my-artifact-bucket/my-artifact.zip"},
        "environment": {
            "type": "LINUX_CONTAINER",
            "image": "aws/codebuild/standard:4.0",
            "computeType": "BUILD_GENERAL1_SMALL",
            "environmentVariables": [
                {"name": "ENV_VAR_NAME", "value": "value", "type": "PLAINTEXT"}
            ],
        },
        "logs": {
            "groupName": "/aws/codebuild/my-project",
            "streamName": "my-build-id",
            "deepLink": "https://console.aws.amazon.com/cloudwatch/home?region=us-west-2#logEvent:group=/aws/codebuild/my-project;stream=my-build-id",
        },
    }
}


class MagicClient:

    def put_parameter(self, **kwargs):

        param_name = kwargs.get("Name")
        current_time = kwargs.get("Value")
        type = kwargs.get("Type")
        overwrite = kwargs.get("Overwrite")

        assert param_name == "/portfolio/my-repo/main/build_time"
        assert current_time is not None
        assert type == "String"
        assert overwrite is True

        return {"Version": "param_store_id"}

    def start_build(self, **kwargs):

        project_name = kwargs.get("projectName")
        source_version = kwargs.get("sourceVersion")
        env_vars = kwargs.get("environmentVariablesOverride")

        assert project_name == "portfolio-my-repo"
        assert source_version == "main"
        assert env_vars == [
            {"name": "CLIENT", "value": "test", "type": "PLAINTEXT"},
            {"name": "PORTFOLIO", "value": "portfolio", "type": "PLAINTEXT"},
            {"name": "APP", "value": "my-repo", "type": "PLAINTEXT"},
            {"name": "BRANCH", "value": "main", "type": "PLAINTEXT"},
            {"name": "BUILD", "value": "abcdef1", "type": "PLAINTEXT"},
            {"name": "BUILD_NUMBER", "value": "param_store_id", "type": "PLAINTEXT"},
            {
                "name": "BUCKET_NAME",
                "value": "test-core-automation-master",
                "type": "PLAINTEXT",
            },
        ]

        return start_build_response


@pytest.fixture
def codecommit_listener():

    with patch("boto3.client") as mock_client:
        mock_client.return_value = MagicClient()
        yield mock_client


@pytest.fixture
def event():

    return {
        "Records": [
            {
                "eventId": "12345678-1234-1234-1234-123456789012",
                "eventVersion": "1.0",
                "eventTime": "2023-10-01T12:34:56Z",
                "eventSource": "aws:codecommit",
                "awsRegion": "us-west-2",
                "eventName": "ReferenceChanges",
                "userIdentityARN": "arn:aws:iam::123456789012:user/username",
                "eventSourceARN": "arn:aws:codecommit:us-west-2:123456789012:portfolio-my-repo",
                "repositoryId": "12345678-1234-1234-1234-123456789012",
                "codecommit": {
                    "references": [
                        {
                            "ref": "refs/heads/main",
                            "commit": "abcdef1234567890abcdef1234567890abcdef12",
                        }
                    ]
                },
            }
        ]
    }


def test_codecommit_listener(codecommit_listener, event):

    try:
        response = handler(event, None)

        assert response is not None

        assert "Responses" in response

        responses = response["Responses"]

        response = responses[0]

        assert response["build"]["buildStatus"] == "IN_PROGRESS"

    except Exception as e:
        assert False, e
