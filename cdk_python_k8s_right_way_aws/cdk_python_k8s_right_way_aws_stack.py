from aws_cdk import (
    aws_autoscaling as autoscaling,
    aws_ec2 as ec2,
    aws_elasticloadbalancing as elb,
    aws_route53 as route53,
    aws_route53_targets as route53_targets,
    aws_iam as iam,
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
# Configuration Variables
# ---------------------------------------------------------

# Global Tags applied to all resources
# Project Tag
tag_project = 'k8s-the-right-hard-way-aws'

# Owner Tag (your name)
tag_owner = 'napo.io'

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

# Bastion Host
bastion_min_capacity = 1
bastion_max_capacity = 1
bastion_desired_capacity = 1
bastion_instance_type = "t3a.small"

# Number of etcd nodes
etcd_min_capacity = 3
etcd_max_capacity = 3
etcd_desired_capacity = 3
etcd_instance_type = "t3a.small"

# Number of Kubernetes master nodes (control plane)
master_min_capacity = 3
master_max_capacity = 3
master_desired_capacity = 3
master_instance_type = "t3a.small"

# Number of kubernetes worker nodes
worker_min_capacity = 3
worker_max_capacity = 3
worker_desired_capacity = 3
worker_instance_type = "t3a.small"
# ---------------------------------------------------------


# Create dict for region <=> Ubuntu AMI mapping
ami_region_map = {}

# Loop through all regions and get the most recent Ubuntu Bionic AMIs for all AWS regions
ec2_client = boto3.client('ec2', region_name=aws_region)
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


# Default Tags applied to all taggable AWS Resources in Stack
default_tags={
    "Project": tag_project,
    "Owner": tag_owner
}


class CdkPythonK8SRightWayAwsStack(core.Stack):

    def __init__(self, scope: core.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, tags=default_tags, **kwargs)

        # VPC
        vpc = ec2.Vpc(
            self,
            'k8s-real-hard-way-vpc',
            cidr=vpc_cidr,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    cidr_mask=24,
                    name='Public',
                    subnet_type=ec2.SubnetType.PUBLIC,

                ),
                ec2.SubnetConfiguration(
                    cidr_mask=24,
                    name='Private',
                    subnet_type=ec2.SubnetType.PRIVATE
                )
            ]
        )

        # Ubuntu AMI from dict mapping
        ubuntu_ami = ec2.GenericLinuxImage(
            ami_map={
                aws_region: ami_region_map.get(aws_region)
            }
        )

        # Get HostedZone ID from HostedZone Name
        zoneid = route53.HostedZone.from_lookup(
            self,
            "k8s-real-hard-way-zone",
            domain_name=zone_fqdn
        )

        # IAM Policy for Instance Profile
        iampolicystatement = iam.PolicyStatement(
            actions=[
                "ec2:CreateRoute",
                "ec2:DescribeRouteTables",
                "ec2:DescribeInstances",
                "ec2:DescribeTags",
                "elasticloadbalancing:DescribeLoadBalancers"
            ],
            effect=iam.Effect.ALLOW,
            resources=[
                "*"
            ]
        )
        # BASTION HOST
        # AutoScalingGroup
        bastion = autoscaling.AutoScalingGroup(
            self,
            "bastion",
            vpc=vpc,
            min_capacity=bastion_min_capacity,
            max_capacity=bastion_max_capacity,
            desired_capacity=bastion_desired_capacity,
            instance_type=ec2.InstanceType(bastion_instance_type),
            machine_image=ec2.AmazonLinuxImage(),
            key_name=ssh_key_pair,
            vpc_subnets=ec2.SubnetSelection(
                subnet_name='Private'
            ),
            associate_public_ip_address=False
        )
        bastion.add_to_role_policy(iampolicystatement)

        # Classic LoadBalancer
        bastion_lb = elb.LoadBalancer(
            self,
            "bastion-lb",
            vpc=vpc,
            internet_facing=True,
            health_check=elb.HealthCheck(
                port=22,
                protocol=elb.LoadBalancingProtocol.TCP
            )
        )
        # Security Group and rules for Bastion LB
        bastion_lb_sg = ec2.SecurityGroup(
            self,
            "bastion-lb-sg",
            vpc=vpc,
            allow_all_outbound=True,
            description="Bastion LB",
        )
        bastion_lb_sg.add_ingress_rule(
            peer=ec2.Peer().ipv4(myipv4),
            connection=ec2.Port.tcp(22),
        )
        bastion_lb.add_listener(
            external_port=22,
            external_protocol=elb.LoadBalancingProtocol.TCP,
            allow_connections_from=[ec2.Peer().ipv4(myipv4)]
        )

        bastion_lb.add_target(
            target=bastion
        )
        # UserData
        bastion.add_user_data(
            "sudo yum update",
            "sudo yum upgrade -y",
            "sudo yum install tmux -y",
            "wget https://gist.githubusercontent.com/dmytro/3984680/raw/1e25a9766b2f21d7a8e901492bbf9db672e0c871/ssh-multi.sh -O /home/ec2-user/tmux-multi.sh",
            "chmod +x /home/ec2-user/tmux-multi.sh"
            "wget https://pkg.cfssl.org/R1.2/cfssl_linux-amd64",
            "chmod +x cfssl_linux-amd64",
            "sudo mv cfssl_linux-amd64 /usr/local/bin/cfssl",
            "wget https://pkg.cfssl.org/R1.2/cfssljson_linux-amd64",
            "chmod +x cfssljson_linux-amd64",
            "sudo mv cfssljson_linux-amd64 /usr/local/bin/cfssljson",
            "curl -LO https://storage.googleapis.com/kubernetes-release/release/$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/linux/amd64/kubectl",
            "chmod +x ./kubectl",
            "sudo mv kubectl /usr/local/bin/kubectl",
            "sudo hostname " + "bastion" + "." + zone_fqdn,
        )
        # Route53 Alias Target for LB
        route53_target = route53_targets.ClassicLoadBalancerTarget(bastion_lb)
        # Route53 Record for Bastion Host LB
        route53_bastion = route53.ARecord(
            self,
            "bastion-lb-route53",
            target=route53.RecordTarget.from_alias(route53_target),
            zone=zoneid,
            comment="Bastion Host LB",
            record_name='bastion'
        )

        # ETCD
        # AutoScalingGroup
        etcd = autoscaling.AutoScalingGroup(
            self,
            "etcd",
            vpc=vpc,
            min_capacity=etcd_min_capacity,
            max_capacity=etcd_max_capacity,
            desired_capacity=etcd_desired_capacity,
            instance_type=ec2.InstanceType(etcd_instance_type),
            machine_image=ubuntu_ami,
            key_name=ssh_key_pair,
            vpc_subnets=ec2.SubnetSelection(
                subnet_name='Private'
            ),
            associate_public_ip_address=False
        )
        # UserData
        etcd.add_user_data(
            "sudo apt-get update",
            "sudo apt-get upgrade -y"
        )

        # KUBERNETES MASTER
        # Load Balancer fronting Kubernetes Master nodes (for remote kubectl access)
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
            external_protocol=elb.LoadBalancingProtocol.TCP,
            allow_connections_from=[ec2.Peer().ipv4(myipv4)]
        )
        # AutoScalingGroup
        master = autoscaling.AutoScalingGroup(
            self,
            "master",
            vpc=vpc,
            min_capacity=master_min_capacity,
            max_capacity=master_max_capacity,
            desired_capacity=master_desired_capacity,
            instance_type=ec2.InstanceType(master_instance_type),
            machine_image=ubuntu_ami,
            key_name=ssh_key_pair,
            vpc_subnets=ec2.SubnetSelection(
                subnet_name='Private'
            ),
            associate_public_ip_address=False
        )
        # Add ASG as target for LB
        master_lb.add_target(
            target=master
        )
        # UserData
        master.add_user_data(
            "sudo apt-get update",
            "sudo apt-get upgrade -y",
        )

        # KUBERNETES WORKER
        worker = autoscaling.AutoScalingGroup(
            self,
            "worker",
            vpc=vpc,
            min_capacity=worker_min_capacity,
            max_capacity=worker_max_capacity,
            desired_capacity=worker_desired_capacity,
            instance_type=ec2.InstanceType(worker_instance_type),
            machine_image=ubuntu_ami,
            key_name=ssh_key_pair,
            vpc_subnets=ec2.SubnetSelection(
                subnet_name='Private'
            ),
            associate_public_ip_address=False
        )
        # UserData
        worker.add_user_data(
            "sudo apt-get update",
            "sudo apt-get upgrade -y",
        )

        # SecurityGroups
        # Bastion Host
        bastion_security_group = ec2.SecurityGroup(
            self,
            "bastion-security-group",
            vpc=vpc,
            allow_all_outbound=True,
            description="Basion Host"
        )
        bastion_security_group.add_ingress_rule(
            peer=bastion_lb_sg,
            connection=ec2.Port.tcp(22),
            description="Allow SSH from Bastion LB"
        )

        # Kubernetes Master LoadBalancer, allow kubectl remote access from workstation IP
        master_lb_sg = ec2.SecurityGroup(
            self,
            "k8s-real-hard-way-master-lb-sg",
            vpc=vpc,
            allow_all_outbound=True,
            description="Allow all egress and incoming traffic only port 6443 kubectl",
        )
        master_lb_sg.add_ingress_rule(
            peer=ec2.Peer().ipv4(myipv4),
            connection=ec2.Port(from_port=6443, to_port=6443, protocol=ec2.Protocol.TCP,
                                string_representation="Allow kubectl port 6443 from workstation IPv4")
        )
        # Kubernetes Master
        master_securiy_group = ec2.SecurityGroup(
            self,
            "master-security-group",
            vpc=vpc,
            allow_all_outbound=True,
            description="K8s Master",
        )
        # Kubernetes Worker
        worker_security_group = ec2.SecurityGroup(
            self,
            "worker-security-group",
            vpc=vpc,
            allow_all_outbound=True,
            description="K8s worker"
        )
        # Allow all incoming K8s Workers traffic on K8s Masters
        master_securiy_group.add_ingress_rule(
            peer=worker_security_group,
            connection=ec2.Port.all_traffic(),
            description="Allow all incoming K8s Worker traffic"
        )
        # Allow incoming SSH traffic from Bastion on Masters
        master_securiy_group.add_ingress_rule(
            peer=bastion_security_group,
            connection=ec2.Port.tcp(22),
            description="Allow SSH from Bastion"
        )
        # Allow incoming API/kubectl traffic from Bastion on K8s Masters
        master_securiy_group.add_ingress_rule(
            peer=bastion_security_group,
            connection=ec2.Port.tcp(6443),
            description="Allow kubectl from Bastion"
        )
        # Allow incoming API/kubectl traffic from K8s Master LB on K8s Masters
        master_securiy_group.add_ingress_rule(
            peer=master_lb_sg,
            connection=ec2.Port.tcp(6443),
            description="Allow kubectl from Bastion"
        )
        # Allow all incoming K8s Masters traffic on K8s Workers
        worker_security_group.add_ingress_rule(
            peer=master_securiy_group,
            connection=ec2.Port.all_traffic(),
            description="Allow all incoming K8s Master traffic"
        )
        # Allow incoming SSH traffic from Bastion on K8s Masters
        worker_security_group.add_ingress_rule(
            peer=bastion_security_group,
            connection=ec2.Port.tcp(22),
            description="Allow SSH from Bastion"
        )
        # etcd
        etcd_security_group = ec2.SecurityGroup(
            self,
            "etcd-security-group",
            vpc=vpc,
            allow_all_outbound=True,
            description="etcd"
        )
        # Allow incoming SSH traffic from Bastion on etcds
        etcd_security_group.add_ingress_rule(
            peer=bastion_security_group,
            connection=ec2.Port.tcp(22),
            description="Allow SSH from Bastion"
        )
        # Allow incoming etcd traffic from K8s Master on etcds
        etcd_security_group.add_ingress_rule(
            peer=master_securiy_group,
            connection=ec2.Port.tcp_range(start_port=2379, end_port=2380),
            description="Allow etcd ports from K8s Master"
        )

        # Add SecurityGroups to resources
        bastion.add_security_group(bastion_security_group)
        etcd.add_security_group(etcd_security_group)
        master.add_security_group(master_securiy_group)
        worker.add_security_group(worker_security_group)

        # Elastic Network Interfaces
        i = 1
        while i <= worker_max_capacity:
            eni = ec2.CfnNetworkInterface(
                self,
                "eni" + str(i),
                subnet_id=str(ec2.SubnetSelection(
                    one_per_az=True,
                    subnet_type=ec2.SubnetType.PRIVATE,
                ).subnet_group_name),
                description="ENI K8s Worker nodes",
                tags=[
                    core.CfnTag(
                        key="Project",
                        value=tag_project),
                    core.CfnTag(
                        key="Owner",
                        value=tag_owner)
                ],
                private_ip_address='10.5.' + str(i) + '.100'
            )
            i += 1

        # Add specific Tags to resources
        core.Tag.add(
            bastion,
            apply_to_launched_instances=True,
            key='Name',
            value=tag_project + '-bastion'
        )
        core.Tag.add(
            bastion_lb,
            apply_to_launched_instances=True,
            key='Name',
            value=tag_project + '-bastion-lb'
        )
        core.Tag.add(
            master_lb,
            apply_to_launched_instances=True,
            key='Name',
            value=tag_project + '-master-lb'
        )
        core.Tag.add(
            etcd,
            apply_to_launched_instances=True,
            key='Name',
            value=tag_project + '-etcd'
        )
        core.Tag.add(
            master,
            apply_to_launched_instances=True,
            key='Name',
            value=tag_project + '-k8s-master'
        )
        core.Tag.add(
            worker,
            apply_to_launched_instances=True,
            key='Name',
            value=tag_project + '-k8s-worker'
        )