
# CDK Python - Kubernetes The (real) Hard Way on AWS!

This little project creates the infrastructure in CDK Python for my blog post [Kubernetes The (real) Hard Way on AWS](https://napo.io/posts/kubernetes-the-real-hard-way-on-aws/).

> Terraform code available 🔗[HERE](https://github.com/hajowieland/terraform-k8s-the-real-hard-way-aws)


You can practice creating a multi node K8s Cluster yourself for training purposes or CKA exam preparation.


![Alt text](cdk-python-k8s-real-hard-way.png?raw=true "Infrastructure Diagram")

## Requirements

* Existing AWS EC2 Key Pair
* Existing AWS Route53 Public Hosted Zone
* aws-cli Profile
* AWS CDK (`npm install -g cdk`)
* Python3

## Features

_Default values - you can adapt all of them to your needs_

* AWS CDK Python
* 1x VPC, 3x Public Subnets, 3x Private Subnets, Route Tables, Routes
* 3x Worker Nodes _(editable)_
* 3x Master Nodes _(editable)_
* 3x Etcd Nodes _(editable)_
* 1x Bastion Host
* Route53 Records for internal & external IPv4 addresses
* 1x Public LoadBalancer for Master Nodes (external kubectl access)
* 1x Private LoadBalancer for Master Nodes (fronting kube-apiservers)
* 1x Public LoadBalancer for Bation Host (AutoScalingGroup)
* Gets most recent Ubuntu AMI for all regions (via Boto3)
* Install awscli, cfssl, cfssl_json via UserData
* Allows external access from workstation IPv4 address only (to Bastion & MasterPublicLB)


## Variables

| Name | Description | Type | Default |
|------|-------------|:----:|:-----:|
| aws\_account | AWS account ID to deploy infrastructure | string | `''` |
| aws\_region | AWS region | string | `'us-east-1'` |
| bastion\_desired\_capacity | Bastion ASG desired nodes | int | 1 |
| bastion\_instance\_type | Bastion EC2 instance type | string | `'t3a.small'` |
| bastion\_min\_capacity | Bastion ASG min. nodes | int | 1 |
| bastion\_max\_capacity | Bastion ASG max. nodes | int | 1 |
| etcd\_desired\_capacity | etcd ASG desired nodes | int | 3 |
| etcd\_instance\_type | etcd EC2 instance type | string | `'t3a.small'` |
| etcd\_min\_capacity | etcd ASG min. nodes | int | 3 |
| etcd\_max\_capacity | etcd ASG max. nodes | int | 3 |
| master\_desired\_capacity | K8s-Master ASG desired nodes | int | 3 |
| master\_instance\_type | K8s-Master EC2 instance type | string | `'t3a.small'` |
| master\_min\_capacity | K8s-Master ASG min. nodes | int | 3 |
| master\_max\_capacity | K8s-Master ASG max. nodes | int | 3 |
| worker\_desired\_capacity | K8s-Worker ASG desired nodes | int | 3 |
| worker\_instance\_type | K8s-Worker EC2 instance type | string | `'t3a.small'` |
| worker\_min\_capacity | K8s-Worker ASG min. nodes | int | 3 |
| worker\_max\_capacity | K8s-Worker ASG max. nodes | int | 3 |
| ssh\_key\_pair | AWS EC2 Key Pair name | string | `''` |
| pod\_cidr | Pod CIDR network first octets (for `POD_CIDR` envvar) | string | `'10.200'` |
| tag\_owner | Owner Tag for all resources | string | `'napo.io'` |
| tag\_project | Project Tag for all resources | string | `'k8s-the-real-hard-way-aws'` |
| vpc\_cidr | AWS VPC network CIDR | string | `'10.5.0.0/16'` |
| zone\_fqdn | AWS Route53 Hosted Zone name | string | `''` |



### CDK Python Tutorial

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

### Useful commands

 * `cdk ls`          list all stacks in the app
 * `cdk synth`       emits the synthesized CloudFormation template
 * `cdk deploy`      deploy this stack to your default AWS account/region
 * `cdk diff`        compare deployed stack with current state
 * `cdk docs`        open CDK documentation

Enjoy!
