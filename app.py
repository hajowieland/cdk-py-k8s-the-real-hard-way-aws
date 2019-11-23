#!/usr/bin/env python3

from aws_cdk import core

from cdk_python_k8s_right_way_aws.cdk_python_k8s_right_way_aws_stack import CdkPythonK8SRightWayAwsStack, aws_region, aws_account

app = core.App()
CdkPythonK8SRealWayAwsStack(app, "cdk-python-k8s-real-way-aws", env={'account': aws_account, 'region': aws_region})

app.synth()
