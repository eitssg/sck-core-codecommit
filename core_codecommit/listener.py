"""
CI lambda for core-* repos that use the deployspec compiler.
AWS_PROFILE=automation AWS_REGION=ap-southeast-1 ./test.py
"""

import boto3
import time
import traceback
import core_logging as log

import core_framework as util
from core_framework.models import DeploymentDetails

from ._version import __version__


def __get_deployment_details(record: dict) -> DeploymentDetails:
    """
    Translate the codecommit event Record into a DeploymentDetails object.

    Args:
        record (dict): _description_

    Returns:
        DeploymentDetails: The deployment details to pass to CodeDeploy
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

    param_name = "/{}/{}/{}/build_time".format(
        deployment.Portfolio, deployment.App, deployment.BranchShortName
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
    Invoke codebuild project for the app.

    See more details at: http://boto3.readthedocs.io/en/docs/reference/services/codebuild.html#CodeBuild.Client.start_build

    Args:
        dd (DeploymentDetails): The deployment details

    Returns:
        dict: The response from the codebuild project execution

    """
    project_name = "{}-{}".format(dd.Portfolio, dd.App)
    build_number = __get_new_build_number(dd)
    automation_bucket_name = util.get_bucket_name()
    automation_region = util.get_region()

    log.info("Initiating build for project: {}".format(project_name))

    env_vars = [
        {"name": "CLIENT", "value": dd.Client, "type": "PLAINTEXT"},
        {"name": "PORTFOLIO", "value": dd.Portfolio, "type": "PLAINTEXT"},
        {"name": "APP", "value": dd.App, "type": "PLAINTEXT"},
        {"name": "BRANCH", "value": dd.Branch, "type": "PLAINTEXT"},
        # core-* repos are always build 1 - there's no blue/green for the foundations, just stack updates.
        {"name": "BUILD", "value": dd.Build, "type": "PLAINTEXT"},
        {"name": "BUILD_NUMBER", "value": build_number, "type": "PLAINTEXT"},
        # Env var set in deploy.sh
        {"name": "BUCKET_NAME", "value": automation_bucket_name, "type": "PLAINTEXT"},
    ]

    log.info("Details of Environment:", details=env_vars)

    boto3_client = boto3.client("codebuild", region_name=automation_region)

    response = boto3_client.start_build(
        projectName=project_name,
        sourceVersion=dd.Branch,
        environmentVariablesOverride=env_vars,
    )

    log.info("response: ", details=response)

    return response


def handler(event: dict, context) -> dict:
    """
    Handle the event from the CodeCommit trigger.

    Args:
        event (dict): _description_
        context (dict): The context object

    Returns:
        dict: The response to provide to the caller
    """

    try:

        log.info("Commit Listenr Event v{}", __version__)
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
        traceback.print_exc()
        print("Error: {}".format(e))
        raise e
