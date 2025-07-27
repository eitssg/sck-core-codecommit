"""
Unit tests for CodeCommit listener functionality.

This module contains pytest test cases for the CodeCommit event handler,
including mocking of AWS services and validation of deployment processing.
"""

from unittest.mock import patch, MagicMock
import pytest
import time

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


class MockAWSClient:
    """Mock AWS client for testing CodeCommit listener functionality."""

    def put_parameter(self, **kwargs):
        """
        Mock SSM put_parameter operation.

        :param kwargs: Parameters for put_parameter call
        :type kwargs: dict
        :returns: Mock response with version number
        :rtype: dict
        """
        param_name = kwargs.get("Name")
        current_time = kwargs.get("Value")
        param_type = kwargs.get("Type")  # Fixed: renamed from 'type' to avoid conflict
        overwrite = kwargs.get("Overwrite")

        assert param_name == "/portfolio/my-repo/main/build_time"
        assert current_time is not None
        assert param_type == "String"  # Fixed: use renamed variable
        assert overwrite is True

        return {"Version": 1}  # Fixed: return integer instead of string

    def start_build(self, **kwargs):
        """
        Mock CodeBuild start_build operation.

        :param kwargs: Parameters for start_build call
        :type kwargs: dict
        :returns: Mock CodeBuild response
        :rtype: dict
        """
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
            {
                "name": "BUILD_NUMBER",
                "value": "1",
                "type": "PLAINTEXT",
            },  # Fixed: expect string "1"
            {
                "name": "BUCKET_NAME",
                "value": "test-core-automation-master",
                "type": "PLAINTEXT",
            },
        ]

        return start_build_response


@pytest.fixture
def mock_boto3_clients():
    """
    Mock boto3.client calls for SSM and CodeBuild services.

    :yields: Mock client factory function
    :rtype: MagicMock
    """

    def client_factory(service_name, **kwargs):
        """Factory function to return appropriate mock client."""
        if service_name in ["ssm", "codebuild"]:
            return MockAWSClient()
        else:
            # Return a default mock for unexpected services
            return MagicMock()

    with patch("boto3.client", side_effect=client_factory) as mock_client:
        yield mock_client


@pytest.fixture
def mock_time():
    """
    Mock time.time() to return a predictable timestamp.

    :yields: Mock time function
    :rtype: MagicMock
    """
    with patch("time.time", return_value=1234567890.123) as mock_time_func:
        yield mock_time_func


@pytest.fixture
def mock_util_functions():
    """
    Mock utility functions for configuration values.

    :yields: Dictionary of mocked utility functions
    :rtype: dict
    """
    with patch(
        "core_framework.common.get_bucket_name",
        return_value="test-core-automation-master",
    ) as mock_bucket, patch(
        "core_framework.common.get_region", return_value="us-west-2"
    ) as mock_region:
        yield {"get_bucket_name": mock_bucket, "get_region": mock_region}


@pytest.fixture
def mock_deployment_details():
    """
    Mock DeploymentDetails to provide client information.

    :yields: Mock deployment details
    :rtype: MagicMock
    """
    with patch("core_codecommit.listener.DeploymentDetails") as mock_dd:
        # Create a mock instance with the required attributes
        mock_instance = MagicMock()
        mock_instance.portfolio = "portfolio"
        mock_instance.app = "my-repo"
        mock_instance.branch = "main"
        mock_instance.build = "abcdef1"
        mock_instance.branch_short_name = "main"
        mock_instance.client = "test"  # Fixed: provide client attribute

        # Configure the mock to return our instance
        mock_dd.return_value = mock_instance
        yield mock_dd


@pytest.fixture
def codecommit_event():
    """
    Sample CodeCommit event for testing.

    :returns: Mock CodeCommit event structure
    :rtype: dict
    """
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


def test_codecommit_listener_success(
    mock_boto3_clients,
    mock_time,
    mock_util_functions,
    mock_deployment_details,
    codecommit_event,
):
    """
    Test successful processing of CodeCommit event.

    Verifies that the handler correctly processes a CodeCommit event,
    extracts deployment details, and triggers the appropriate CodeBuild project.

    :param mock_boto3_clients: Mocked boto3 client factory
    :type mock_boto3_clients: MagicMock
    :param mock_time: Mocked time function
    :type mock_time: MagicMock
    :param mock_util_functions: Mocked utility functions
    :type mock_util_functions: dict
    :param mock_deployment_details: Mocked DeploymentDetails class
    :type mock_deployment_details: MagicMock
    :param codecommit_event: Sample CodeCommit event
    :type codecommit_event: dict
    """
    response = handler(codecommit_event, None)

    # Verify response structure
    assert response is not None
    assert "Responses" in response

    responses = response["Responses"]
    assert len(responses) == 1

    build_response = responses[0]
    assert build_response["build"]["buildStatus"] == "IN_PROGRESS"
    assert build_response["build"]["id"] == "my-build-id"


def test_codecommit_listener_missing_records():
    """
    Test error handling when Records key is missing from event.

    Verifies that the handler properly raises ValueError when the event
    structure is malformed.
    """
    invalid_event = {"NotRecords": []}

    with pytest.raises(ValueError, match="No 'Records' key in event"):
        handler(invalid_event, None)


def test_codecommit_listener_empty_records():
    """
    Test handling of event with empty Records array.

    Verifies that the handler can process an event with no records
    and returns an empty response list.
    """
    empty_event = {"Records": []}

    response = handler(empty_event, None)

    assert response is not None
    assert "Responses" in response
    assert len(response["Responses"]) == 0


def test_codecommit_listener_multiple_records(
    mock_boto3_clients, mock_time, mock_util_functions, mock_deployment_details
):
    """
    Test processing of multiple CodeCommit records in single event.

    Verifies that the handler can process multiple repository commits
    in a single event and returns responses for each.

    :param mock_boto3_clients: Mocked boto3 client factory
    :type mock_boto3_clients: MagicMock
    :param mock_time: Mocked time function
    :type mock_time: MagicMock
    :param mock_util_functions: Mocked utility functions
    :type mock_util_functions: dict
    :param mock_deployment_details: Mocked DeploymentDetails class
    :type mock_deployment_details: MagicMock
    """
    multi_record_event = {
        "Records": [
            {
                "eventSourceARN": "arn:aws:codecommit:us-west-2:123456789012:portfolio-my-repo",
                "codecommit": {
                    "references": [
                        {
                            "ref": "refs/heads/main",
                            "commit": "abcdef1234567890abcdef1234567890abcdef12",
                        }
                    ]
                },
            },
            {
                "eventSourceARN": "arn:aws:codecommit:us-west-2:123456789012:portfolio-another-repo",
                "codecommit": {
                    "references": [
                        {
                            "ref": "refs/heads/develop",
                            "commit": "fedcba0987654321fedcba0987654321fedcba09",
                        }
                    ]
                },
            },
        ]
    }

    response = handler(multi_record_event, None)

    assert response is not None
    assert "Responses" in response
    assert len(response["Responses"]) == 2

    # Verify each response has the expected structure
    for build_response in response["Responses"]:
        assert build_response["build"]["buildStatus"] == "IN_PROGRESS"
