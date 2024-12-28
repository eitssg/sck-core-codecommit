"""
CI lambda for core-* repos that use the deployspec compiler.
AWS_PROFILE=automation AWS_REGION=ap-southeast-1 ./test.py
"""

import os
import re
import boto3
import time

from core_api import get_facts


def __get_deployment_details(event):
    record = event["Records"][0]
    # Dashes in repo names can break the first solution.
    # portfolio, app = record['eventSourceARN'].split(':')[-1].split('-')
    parts = record["eventSourceARN"].split(":")[-1].split("-")
    portfolio = parts[0]
    app = "-".join(parts[1:])

    branch = record["codecommit"]["references"][0]["ref"].split("/")[-1]
    # FIXME Build is always 1 for core-* repos
    # build = record['codecommit']['references'][0]['commit']  # FIXME SSM param store for build numbers?
    build = "1"
    return {"portfolio": portfolio, "app": app, "branch": branch, "build": build}


def __s3_path_format(name):
    """Helper function."""
    return re.sub("_", "-", name)


def __get_identity(deployment_details):
    """
    Copied from lambdas/invoker/main.py, case is different :(
    """
    return ":".join(
        [
            "prn",
            deployment_details["portfolio"],
            deployment_details["app"],
            deployment_details["branch"],  # FIXME branchshortname?
            deployment_details["build"],
        ]
    ).lower()


def __get_new_build_number(deployment):
    client = boto3.client("ssm")

    param_name = "/{}/{}/{}/build_time".format(
        deployment["portfolio"], deployment["app"], deployment["branch"]
    )
    current_time = str(int(round(time.time() * 1000)))

    response = client.put_parameter(
        Name=param_name, Value=current_time, Type="String", Overwrite=True
    )
    print(
        "__get_new_build_number param_name={}, current_time={}, response={}".format(
            param_name, current_time, response
        )
    )
    return response["Version"]


def __invoke_codebuild_project(
    deployment,
    automation_region,
    automation_bucket_name,
    run_sh_s3_path,
    client_name,
    invoker_branch,
):
    """Invoke a codebuild project setup for the app.
    http://boto3.readthedocs.io/en/docs/reference/services/codebuild.html#CodeBuild.Client.start_build
    """
    project_name = "{}-{}".format(deployment["portfolio"], deployment["app"])
    branch = deployment["branch"]
    new_build_number = __get_new_build_number(deployment)

    env_vars = [
        {"name": "CLIENT", "value": client_name, "type": "PLAINTEXT"},
        {"name": "PORTFOLIO", "value": deployment["portfolio"], "type": "PLAINTEXT"},
        {"name": "APP", "value": deployment["app"], "type": "PLAINTEXT"},
        {"name": "BRANCH", "value": deployment["branch"], "type": "PLAINTEXT"},
        # core-* repos are always build 1 - there's no blue/green for the foundations, just stack updates.
        {"name": "BUILD", "value": "1", "type": "PLAINTEXT"},
        {"name": "BUILD_NUMBER", "value": str(new_build_number), "type": "PLAINTEXT"},
        # Env var set in deploy.sh
        {"name": "BUCKET_NAME", "value": automation_bucket_name, "type": "PLAINTEXT"},
        {"name": "RUN_SH_S3_PATH", "value": run_sh_s3_path, "type": "PLAINTEXT"},
        {"name": "INVOKER_BRANCH", "value": invoker_branch, "type": "PLAINTEXT"},
    ]

    print(
        "__invoke_codebuild_project client_name={}, project_name={}, branch={}, env_vars={}".format(
            client_name, project_name, branch, env_vars
        )
    )

    boto3_client = boto3.client("codebuild", region_name=automation_region)
    response = boto3_client.start_build(
        projectName=project_name,
        sourceVersion=deployment["branch"],
        environmentVariablesOverride=env_vars,
    )

    print("__invoke_codebuild_project response={}".format(response))
    return response


def handler(event, context):
    print("*** Handler running")
    print("event={}".format(event))

    automation_region = "ap-southeast-1"  # FIXME Set via env vars in deploy.sh etc.
    deployment = __get_deployment_details(event)
    print("deployment={}".format(deployment))

    # Get app facts
    identity = __get_identity(deployment)

    print("identity={}".format(identity))

    facts = get_facts(**identity)

    invoker_branch = facts.get("InvokerBranch", "master")

    # Trust in your codecommit triggers for only master.
    # if deployment['portfolio'] == 'core' and deployment['branch'] != 'master':
    #     raise ValueError('Branch MUST be master for core-* repos. Aborting.')

    response = __invoke_codebuild_project(
        deployment,
        automation_region,
        os.environ["AUTOMATION_BUCKET_NAME"],
        os.environ["RUN_SH_S3_PATH"],
        os.environ["CLIENT_NAME"],
        invoker_branch,
    )

    print("Done")
    return {"id": response["build"]["id"]}
