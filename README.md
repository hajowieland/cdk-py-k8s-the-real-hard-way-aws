
# CDK Python Kubernetes the (right) hard way on AWS!

This little project creates the infrastructure in CDK Python for my blog post [Kubernetes the (right) hard way on AWS](https://napo.io/posts/kubernetes-the-right-hard-way-on-aws/).

You can practice creating a multi node K8s Cluster yourself for training purposes or CKA exam preparation.


![Alt text](cdk-python-k8s-real-hard-way.png?raw=true "Infrastructure Diagram")

## Requirements

* Existing AWS EC2 Key Pair
* Existing AWS Route53 Public Hosted Zone

## Features

* AWS CDK Python
* 1x VPC, 3x Public Subnets, Route Tables, Routes
* 3x Worker Nodes _(editable)_
* 3x Master Nodes _(editable)_
* 3x Etcd Nodes _(editable)_
* Route53 Records for internal & external IPv4 addresses
* LoadBalancer for Master Node (external kubectl access)
* Gets most recent Ubuntu AMI for all regions
* Install awscli, cfssl, cfssl_json via UserData
* Allows external access from workstation IPv4 address only


## CDK Python Tutorial

The `cdk.json` file tells the CDK Toolkit how to execute your app.

This project is set up like a standard Python project.  The initialization
process also creates a virtualenv within this project, stored under the .env
directory.  To create the virtualenv it assumes that there is a `python3`
(or `python` for Windows) executable in your path with access to the `venv`
package. If for any reason the automatic creation of the virtualenv fails,
you can create the virtualenv manually.

To manually create a virtualenv on MacOS and Linux:

```
$ python3 -m venv .env
```

After the init process completes and the virtualenv is created, you can use the following
step to activate your virtualenv.

```
$ source .env/bin/activate
```

If you are a Windows platform, you would activate the virtualenv like this:

```
% .env\Scripts\activate.bat
```

Once the virtualenv is activated, you can install the required dependencies.

```
$ pip install -r requirements.txt
```

At this point you can now synthesize the CloudFormation template for this code.

```
$ cdk synth
```

To add additional dependencies, for example other CDK libraries, just add
them to your `setup.py` file and rerun the `pip install -r requirements.txt`
command.

# Useful commands

 * `cdk ls`          list all stacks in the app
 * `cdk synth`       emits the synthesized CloudFormation template
 * `cdk deploy`      deploy this stack to your default AWS account/region
 * `cdk diff`        compare deployed stack with current state
 * `cdk docs`        open CDK documentation

Enjoy!
