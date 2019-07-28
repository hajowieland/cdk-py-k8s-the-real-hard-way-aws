#!/usr/bin/env python3

from aws_cdk import core

from cdk_python_k8s_right_way_aws.cdk_python_k8s_right_way_aws_stack import CdkPythonK8SRightWayAwsStack


app = core.App()
CdkPythonK8SRightWayAwsStack(app, "cdk-python-k8s-right-way-aws")

app.synth()