"""
CI lambda for core-* repos that use the deployspec compiler.

This module handles CodeCommit events and triggers CodeBuild projects for deployment
processing. It processes commit events, extracts deployment details, and initiates
the appropriate build pipeline.

Usage example:
    AWS_PROFILE=automation AWS_REGION=ap-southeast-1 ./test.py
"""

import boto3
import time
from typing import Any

import core_logging as log
import core_framework as util
from core_framework.models import DeploymentDetails


def __get_deployment_details(record: dict) -> DeploymentDetails:
    """
    Translate the CodeCommit event Record into a DeploymentDetails object.

    Extracts portfolio, app, branch, and build information from the CodeCommit
    event record structure and creates a properly formatted DeploymentDetails
    instance for downstream processing.

    :param record: CodeCommit event record containing repository and commit information
    :type record: dict
    :returns: Deployment details extracted from the event record
    :rtype: DeploymentDetails
    :raises KeyError: If required keys are missing from the record
    :raises IndexError: If expected array structures are malformed

    Examples
    --------
    >>> record = {
    ...     "eventSourceARN": "arn:aws:codecommit:us-east-1:123456789012:core-api",
    ...     "codecommit": {
    ...         "references": [{
    ...             "ref": "refs/heads/master",
    ...             "commit": "abcdef1234567890"
    ...         }]
    ...     }
    ... }
    >>> dd = __get_deployment_details(record)
    >>> # Returns: DeploymentDetails(Portfolio='core', App='api', Branch='master', Build='abcdef1')

    Notes
    -----
    Repository name format expected: {portfolio}-{app}
    For multi-part app names (e.g., core-api-gateway), the portfolio is 'core'
    and the app name is 'api-gateway'.
    """
    # Dashes in repo names can break the first solution.
    # portfolio, app = record['eventSourceARN'].split(':')[-1].split('-')
    parts = record["eventSourceARN"].split(":")[-1].split("-")
    portfolio = parts[0]
    app = "-".join(parts[1:])

    references = record["codecommit"]["references"][0]
    branch = references["ref"].split("/")[-1]
    build = references["commit"][:7]

    return DeploymentDetails(
        Portfolio=portfolio,
        App=app,
        Branch=branch,
        Build=build,
    )


def __get_new_build_number(deployment: DeploymentDetails) -> str:
    """
    Generate and store a new build number for the deployment.

    Creates a timestamp-based build number and stores it in AWS Systems Manager
    Parameter Store for tracking and reference. The build number is based on
    current Unix timestamp in milliseconds.

    :param deployment: Deployment details containing portfolio, app, and branch information
    :type deployment: DeploymentDetails
    :returns: The version number of the stored parameter (as string)
    :rtype: str
    :raises ClientError: If SSM parameter operation fails
    :raises Exception: If timestamp generation or parameter storage fails

    Examples
    --------
    >>> dd = DeploymentDetails(Portfolio='core', App='api', Branch='master', Build='abc1234')
    >>> build_number = __get_new_build_number(dd)
    >>> # Returns: "1" (first version) or "2" (second version), etc.

    Notes
    -----
    Parameter name format: /{portfolio}/{app}/{branch}/build_time
    The parameter value is the current timestamp in milliseconds.
    The returned build number is the parameter version, not the timestamp.
    """
    param_name = "/{}/{}/{}/build_time".format(
        deployment.portfolio, deployment.app, deployment.branch_short_name
    )
    current_time = str(int(round(time.time() * 1000)))

    client = boto3.client("ssm")
    response = client.put_parameter(
        Name=param_name, Value=current_time, Type="String", Overwrite=True
    )
    log.info(
        "New build number param_name={}, current_time={}, response={}".format(
            param_name, current_time, response
        )
    )
    return str(response["Version"])


def invoke_codebuild_project(dd: DeploymentDetails) -> dict:
    """
    Invoke CodeBuild project for the application deployment.

    Starts a CodeBuild project execution with the appropriate environment variables
    set for the deployment context. The project name is derived from the portfolio
    and app names, and environment variables are set to provide deployment context
    to the build process.

    :param dd: Deployment details containing portfolio, app, branch, and build information
    :type dd: DeploymentDetails
    :returns: Response from the CodeBuild start_build API call
    :rtype: dict
    :raises ClientError: If CodeBuild project doesn't exist or start_build fails
    :raises Exception: If environment variable setup or project invocation fails

    Examples
    --------
    >>> dd = DeploymentDetails(
    ...     client='acme',
    ...     Portfolio='core',
    ...     App='api',
    ...     Branch='master',
    ...     Build='abc1234'
    ... )
    >>> response = invoke_codebuild_project(dd)
    >>> # Returns: {
    >>> #     'build': {
    >>> #         'id': 'core-api:12345678-1234-1234-1234-123456789012',
    >>> #         'arn': 'arn:aws:codebuild:us-east-1:123456789012:build/core-api:12345678...',
    >>> #         'buildStatus': 'IN_PROGRESS',
    >>> #         ...
    >>> #     }
    >>> # }

    Notes
    -----
    Environment variables set for the build:
        - CLIENT: The client identifier
        - PORTFOLIO: The portfolio name
        - APP: The application name
        - BRANCH: The git branch name
        - BUILD: The git commit hash (first 7 characters)
        - BUILD_NUMBER: Sequential build number from Parameter Store
        - BUCKET_NAME: The automation bucket name

    See Also
    --------
    AWS CodeBuild start_build API documentation:
    https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/codebuild.html#CodeBuild.Client.start_build
    """
    project_name = "{}-{}".format(dd.portfolio, dd.app)
    build_number = __get_new_build_number(dd)
    automation_bucket_name = util.get_bucket_name()
    automation_region = util.get_region()

    log.info("Initiating build for project: {}".format(project_name))

    env_vars = [
        {"name": "CLIENT", "value": dd.client, "type": "PLAINTEXT"},
        {"name": "PORTFOLIO", "value": dd.portfolio, "type": "PLAINTEXT"},
        {"name": "APP", "value": dd.app, "type": "PLAINTEXT"},
        {"name": "BRANCH", "value": dd.branch, "type": "PLAINTEXT"},
        # core-* repos are always build 1 - there's no blue/green for the foundations, just stack updates.
        {"name": "BUILD", "value": dd.build, "type": "PLAINTEXT"},
        {"name": "BUILD_NUMBER", "value": build_number, "type": "PLAINTEXT"},
        # Env var set in deploy.sh
        {"name": "BUCKET_NAME", "value": automation_bucket_name, "type": "PLAINTEXT"},
    ]

    log.info("Details of Environment:", details=env_vars)

    boto3_client = boto3.client("codebuild", region_name=automation_region)

    response = boto3_client.start_build(
        projectName=project_name,
        sourceVersion=dd.branch,
        environmentVariablesOverride=env_vars,
    )

    log.info("response: ", details=response)

    return response


def handler(event: dict, context: Any) -> dict:
    """
    Handle the event from the CodeCommit trigger.

    AWS Lambda handler function that processes CodeCommit events triggered by
    repository commits. For each commit record, it extracts deployment details
    and initiates the corresponding CodeBuild project to process the deployment.

    :param event: Lambda event containing CodeCommit records
    :type event: dict
    :param context: Lambda context object (unused)
    :type context: Any
    :returns: Response containing all CodeBuild invocation results
    :rtype: dict
    :raises ValueError: If event structure is invalid or missing required fields
    :raises Exception: If CodeBuild invocation fails for any record

    Examples
    --------
    >>> event = {
    ...     "Records": [{
    ...         "eventSourceARN": "arn:aws:codecommit:us-east-1:123456789012:core-api",
    ...         "codecommit": {
    ...             "references": [{
    ...                 "ref": "refs/heads/master",
    ...                 "commit": "abcdef1234567890abcdef1234567890abcdef12"
    ...             }]
    ...         }
    ...     }]
    ... }
    >>> response = handler(event, None)
    >>> # Returns: {
    >>> #     "Responses": [{
    >>> #         "build": {
    >>> #             "id": "core-api:12345678-1234-1234-1234-123456789012",
    >>> #             "buildStatus": "IN_PROGRESS",
    >>> #             ...
    >>> #         }
    >>> #     }]
    >>> # }

    Notes
    -----
    Expected event structure:
        - event["Records"]: List of CodeCommit event records
        - Each record contains eventSourceARN and codecommit reference data

    The function processes each record independently and collects all responses.
    If any individual record fails, the exception is raised and processing stops.

    Error Handling
    --------------
    The function validates the event structure and will raise ValueError if:
        - The "Records" key is missing from the event
        - Any record is missing required fields for deployment detail extraction

    All exceptions are logged and re-raised to ensure proper Lambda error handling.
    """
    try:
        # Get the version of this module
        from core_codecommit import __version__

        log.info(f"Commit Listener Event v{__version__}")
        log.debug("event={}".format(event))

        if "Records" not in event:
            log.error("No 'Records' key in event")
            raise ValueError("No 'Records' key in event")

        records = event["Records"]

        log.info("Processing {} Records".format(len(records)))

        responses: list[dict] = []
        for record in records:
            dd = __get_deployment_details(record)

            log.info("deployment: ", details=dd.model_dump())

            identity = dd.get_identity()

            log.info("identity={}", identity)

            response = invoke_codebuild_project(dd)

            responses.append(response)

        return {"Responses": responses}

    except Exception as e:
        log.error(
            "Error processing CodeCommit event: {}".format(e)
        )  # Fixed: use log.error instead of print
        raise e
