from aws_cdk import (
    aws_autoscaling as autoscaling,
    aws_ec2 as ec2,
    aws_route53 as route53,
    aws_iam as iam,
    aws_elasticloadbalancingv2 as elbv2,
    aws_elasticloadbalancing as elb,
    core,
)
import json
from requests import get
import boto3
from operator import itemgetter

# ---------------------------------------------------------
# TODO
# - remove repeated code in userdata, route53 json
# - flannel CNI
# ---------------------------------------------------------
# Variables
# ---------------------------------------------------------

# AWS account
aws_account = ''

# AWS region
aws_region = 'us-east-1'

# Get your workstation IPv4 address
myipv4 = get('https://api.ipify.org').text + "/32"

# Set VPC CIDR
vpc_cidr = '10.5.0.0/16'

# Flannel CNI CIDR
# flannel_cidr = '10.244.0.0/16'

# Configure your AWS key pair name here
ssh_key_pair = ''

# FQDN of the hosted zone to create Route53 records in
# Example: test.example.com.
zone_fqdn = ''

# Number of etcd nodes
etcd_nodes = 3

# Number of Kubernetes master nodes (control plane)
master_nodes = 3

# Number of kubernetes worker nodes
worker_nodes = 3

# ---------------------------------------------------------

# Create dict of all regions and most recent Ubuntu Bionic AMI for this region
ami_region_map = {}

ec2_client = boto3.client('ec2', region_name='us-east-1')
response = ec2_client.describe_regions()

for region in response['Regions']:
    regionname = region['RegionName']
    ec2_region = boto3.client('ec2', region_name=regionname)
    response = ec2_region.describe_images(
        Filters=[
            {
                'Name': 'name',
                'Values': [
                    'ubuntu/images/hvm-ssd/ubuntu-bionic-18.04-amd64-server-**',
                ]
            },
        ],
        Owners=[
            '099720109477'
        ]
    )
    image_details = sorted(response['Images'], key=itemgetter('CreationDate'), reverse=True)
    ami_id = image_details[0]['ImageId']
    ami_region_map[regionname] = ami_id


class CdkPythonK8SRightWayAwsStack(core.Stack):

    def __init__(self, scope: core.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # VPC
        vpc = ec2.Vpc(
            self,
            'k8s-real-hard-way-vpc',
            cidr=vpc_cidr,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    cidr_mask=24,
                    name='Public',
                    subnet_type=ec2.SubnetType.PUBLIC
                ),
                # ec2.SubnetConfiguration(
                #     cidr_mask=24,
                #     name='Private',
                #     subnet_type=ec2.SubnetType.PRIVATE
                # )
            ]
        )

        ubuntu_ami = ec2.GenericLinuxImage(
            ami_map={
                aws_region: ami_region_map.get(aws_region)
            }
        )

        zoneid = route53.HostedZone.from_lookup(
            self,
            "k8s-real-hard-way-zone",
            domain_name=zone_fqdn
        )

        iampolicystatement = iam.PolicyStatement(
            actions=[
                "route53:ChangeResourceRecordSets",
                "route53:GetHostedZone",
                "route53:ListResourceRecordSets"
            ],
            effect=iam.Effect.ALLOW,
            resources=[
                "arn:aws:route53:::" + zoneid.hosted_zone_id[1:]
            ]
        )

        x = 0
        while x < etcd_nodes:

            etcd = autoscaling.AutoScalingGroup(
                self,
                "etcd" + str(x + 1),
                vpc=vpc,
                instance_type=ec2.InstanceType.of(
                    ec2.InstanceClass.BURSTABLE3_AMD, ec2.InstanceSize.SMALL
                ),
                machine_image=ubuntu_ami,
                key_name=ssh_key_pair,
                vpc_subnets=ec2.SubnetSelection(
                    subnet_name='Public'
                ),
                associate_public_ip_address=True
            )

            etcd.add_to_role_policy(iampolicystatement)

            route53_record_public = {
                "Comment": "Update the A record set",
                "Changes": [
                    {
                    "Action": "UPSERT",
                    "ResourceRecordSet": {
                        "Name": "etcd" + str(x + 1) + "." + zone_fqdn,
                        "Type": "A",
                        "TTL": 300,
                        "ResourceRecords": [
                        {
                            "Value": "$publicip"
                        }
                        ]
                    }
                    }
                ]
            }

            route53_record_local = {
                "Comment": "Update the local A record set",
                "Changes": [
                    {
                    "Action": "UPSERT",
                    "ResourceRecordSet": {
                        "Name": "etcd" + str(x + 1) + "." + "internal." + zone_fqdn,
                        "Type": "A",
                        "TTL": 300,
                        "ResourceRecords": [
                        {
                            "Value": "$localip"
                        }
                        ]
                    }
                    }
                ]
            }

            etcd.add_user_data(
                "sudo apt-get update",
                "sudo apt-get upgrade -y",
                "sudo apt-get install python3-pip -y",
                "pip3 install awscli",
                "wget https://pkg.cfssl.org/R1.2/cfssl_linux-amd64",
                "chmod +x cfssl_linux-amd64",
                "sudo mv cfssl_linux-amd64 /usr/local/bin/cfssl",
                "wget https://pkg.cfssl.org/R1.2/cfssljson_linux-amd64",
                "chmod +x cfssljson_linux-amd64",
                "sudo mv cfssljson_linux-amd64 /usr/local/bin/cfssljson",
                "sudo hostname " + "etcd" + str(x + 1) + "." + "internal." + zone_fqdn,
                "publicip=$(curl -fs http://169.254.169.254/latest/meta-data/public-ipv4)",
                "localip=$(curl -fs http://169.254.169.254/latest/meta-data/local-ipv4)",
                "cat << EOF > /tmp/publicrecord.json",
                json.dumps(route53_record_public),
                "EOF",
                "cat << EOF > /tmp/localrecord.json",
                json.dumps(route53_record_local),
                "EOF",
                "aws route53 change-resource-record-sets --hosted-zone-id " + zoneid.hosted_zone_id + " --change-batch file:///tmp/publicrecord.json",
                "aws route53 change-resource-record-sets --hosted-zone-id " + zoneid.hosted_zone_id + " --change-batch file:///tmp/localrecord.json"
            )
            
            etcd.connections.allow_from(
                    other=ec2.Peer().ipv4(myipv4),
                    port_range=ec2.Port(from_port=0, to_port=65535, protocol=ec2.Protocol.TCP,
                                        string_representation="Allow all from workstation"))
            etcd.connections.allow_from(
                    other=ec2.Peer().ipv4(vpc_cidr),
                    port_range=ec2.Port(from_port=0, to_port=65535, protocol=ec2.Protocol.ALL,
                                        string_representation="Allow all VPC")
            )
            x += 1

        master_lb = elb.LoadBalancer(
            self,
            "k8s-real-hard-way-master-lb",
            vpc=vpc,
            internet_facing=True,
            health_check=elb.HealthCheck(
                port=6443,
                protocol=elb.LoadBalancingProtocol.TCP
            )
        )
        master_lb.add_listener(
            external_port=6443,
            external_protocol=elb.LoadBalancingProtocol.TCP
        )

        y = 0
        while y < master_nodes:

            master = autoscaling.AutoScalingGroup(
                self,
                "master" + str(y + 1),
                vpc=vpc,
                instance_type=ec2.InstanceType.of(
                    ec2.InstanceClass.BURSTABLE3_AMD, ec2.InstanceSize.SMALL
                ),
                machine_image=ubuntu_ami,
                key_name=ssh_key_pair,
                vpc_subnets=ec2.SubnetSelection(
                    subnet_name='Public'
                ),
                associate_public_ip_address=True
            )

            master_lb.add_target(
                target=master
            )

            master.add_to_role_policy(iampolicystatement)

            route53_record_public = {
                "Comment": "Update the A record set",
                "Changes": [
                    {
                    "Action": "UPSERT",
                    "ResourceRecordSet": {
                        "Name": "master" + str(y + 1) + "." + zone_fqdn,
                        "Type": "A",
                        "TTL": 300,
                        "ResourceRecords": [
                        {
                            "Value": "$publicip"
                        }
                        ]
                    }
                    }
                ]
            }

            route53_record_local = {
                "Comment": "Update the local A record set",
                "Changes": [
                    {
                    "Action": "UPSERT",
                    "ResourceRecordSet": {
                        "Name": "master" + str(y + 1) + "." + "internal." + zone_fqdn,
                        "Type": "A",
                        "TTL": 300,
                        "ResourceRecords": [
                        {
                            "Value": "$localip"
                        }
                        ]
                    }
                    }
                ]
            }

            master.add_user_data(
                "sudo apt-get update",
                "sudo apt-get upgrade -y",
                "sudo apt-get install python3-pip -y",
                "pip3 install awscli",
                "wget https://pkg.cfssl.org/R1.2/cfssl_linux-amd64",
                "chmod +x cfssl_linux-amd64",
                "sudo mv cfssl_linux-amd64 /usr/local/bin/cfssl",
                "wget https://pkg.cfssl.org/R1.2/cfssljson_linux-amd64",
                "chmod +x cfssljson_linux-amd64",
                "sudo mv cfssljson_linux-amd64 /usr/local/bin/cfssljson",
                "sudo hostname " + "master" + str(y + 1) + "." + "internal." + zone_fqdn,
                "publicip=$(curl -fs http://169.254.169.254/latest/meta-data/public-ipv4)",
                "localip=$(curl -fs http://169.254.169.254/latest/meta-data/local-ipv4)",
                "cat << EOF > /tmp/publicrecord.json",
                json.dumps(route53_record_public),
                "EOF",
                "cat << EOF > /tmp/localrecord.json",
                json.dumps(route53_record_local),
                "EOF",
                "aws route53 change-resource-record-sets --hosted-zone-id " + zoneid.hosted_zone_id + " --change-batch file:///tmp/publicrecord.json",
                "aws route53 change-resource-record-sets --hosted-zone-id " + zoneid.hosted_zone_id + " --change-batch file:///tmp/localrecord.json"
            )

            master.connections.allow_from(
                    other=ec2.Peer().ipv4(myipv4),
                    port_range=ec2.Port(from_port=0, to_port=65535, protocol=ec2.Protocol.TCP,
                                        string_representation="Allow all from workstation"))
            master.connections.allow_from(
                    other=ec2.Peer().ipv4(vpc_cidr),
                    port_range=ec2.Port(from_port=0, to_port=65535, protocol=ec2.Protocol.ALL,
                                        string_representation="Allow all VPC")
            )
            y += 1

        z = 0
        while z < worker_nodes:

            worker = autoscaling.AutoScalingGroup(
                self,
                "worker" + str(z + 1),
                vpc=vpc,
                instance_type=ec2.InstanceType.of(
                    ec2.InstanceClass.BURSTABLE3_AMD, ec2.InstanceSize.SMALL
                ),
                machine_image=ubuntu_ami,
                key_name=ssh_key_pair,
                vpc_subnets=ec2.SubnetSelection(
                    subnet_name='Public'
                ),
                associate_public_ip_address=True
            )

            worker.add_to_role_policy(iampolicystatement)

            route53_record_public = {
                "Comment": "Update the A record set",
                "Changes": [
                    {
                    "Action": "UPSERT",
                    "ResourceRecordSet": {
                        "Name": "worker" + str(z + 1) + "." + zone_fqdn,
                        "Type": "A",
                        "TTL": 300,
                        "ResourceRecords": [
                        {
                            "Value": "$publicip"
                        }
                        ]
                    }
                    }
                ]
            }

            route53_record_local = {
                "Comment": "Update the local A record set",
                "Changes": [
                    {
                    "Action": "UPSERT",
                    "ResourceRecordSet": {
                        "Name": "worker" + str(z + 1) + "." + "internal." + zone_fqdn,
                        "Type": "A",
                        "TTL": 300,
                        "ResourceRecords": [
                        {
                            "Value": "$localip"
                        }
                        ]
                    }
                    }
                ]
            }

            worker.add_user_data(
                "sudo apt-get update",
                "sudo apt-get upgrade -y",
                "sudo apt-get install python3-pip -y",
                "pip3 install awscli",
                "wget https://pkg.cfssl.org/R1.2/cfssl_linux-amd64",
                "chmod +x cfssl_linux-amd64",
                "sudo mv cfssl_linux-amd64 /usr/local/bin/cfssl",
                "wget https://pkg.cfssl.org/R1.2/cfssljson_linux-amd64",
                "chmod +x cfssljson_linux-amd64",
                "sudo mv cfssljson_linux-amd64 /usr/local/bin/cfssljson",
                "sudo hostname " + "worker" + str(z + 1) + "." + "internal." + zone_fqdn,
                "publicip=$(curl -fs http://169.254.169.254/latest/meta-data/public-ipv4)",
                "localip=$(curl -fs http://169.254.169.254/latest/meta-data/local-ipv4)",
                "cat << EOF > /tmp/publicrecord.json",
                json.dumps(route53_record_public),
                "EOF",
                "cat << EOF > /tmp/localrecord.json",
                json.dumps(route53_record_local),
                "EOF",
                "aws route53 change-resource-record-sets --hosted-zone-id " + zoneid.hosted_zone_id + " --change-batch file:///tmp/publicrecord.json",
                "aws route53 change-resource-record-sets --hosted-zone-id " + zoneid.hosted_zone_id + " --change-batch file:///tmp/localrecord.json",
                "echo POD_CIDR=10.200." + str(z + 1) + ".0/24 >> /etc/environment"
            )

            worker.connections.allow_from(
                    other=ec2.Peer().ipv4(myipv4),
                    port_range=ec2.Port(from_port=0, to_port=65535, protocol=ec2.Protocol.TCP,
                                        string_representation="Allow all from workstation"))
            worker.connections.allow_from(
                    other=ec2.Peer().ipv4(vpc_cidr),
                    port_range=ec2.Port(from_port=0, to_port=65535, protocol=ec2.Protocol.ALL,
                                        string_representation="Allow all VPC")
            )
            z += 1
