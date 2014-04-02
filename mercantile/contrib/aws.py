import time, sys
from fabric.decorators import task
from fabric.tasks import execute
from fabric.api import env, run, sudo, cd, hide, prefix, prompt, settings
from fabric.contrib.console import confirm
from fabric.contrib.files import append, sed


### Config ###
from mercantile.config import config, required
conf = config.add_group('aws', {
    'region': unicode,                        # Region to place the server, e.g. 'us-east-1'
    'access_key_id': unicode | required,      # Access Key from the AWS Command Console.
    'secret_access_key': unicode | required,  # Secret Access Key and from the AWS Command Console.
    'key_pair': unicode,                      # Name of the Key Pair to use.
    'security_group': unicode,                # The Security Group to use.
    'ami': unicode,                           # The name of the AMI to use.
    'zone': unicode,                          # The Zone to place the server in, e.g. 'us-east-1c'
    'type': unicode,                          # The Type to use, e.g. 'm1.small'
    'disk_size': int,                         # Disk size in gigabytes.
})


### Helpers ###
def activate(name):
    global conf
    conf = conf[name]

env.aws = None
def ec2_connection():
    """
    Create the connection to ec2, raises an error if boto is not installed.
    """
    try:
        from boto.ec2 import connect_to_region
    except ImportError:
        raise ImportError("Boto is not installed, pip install boto or something.")

    if env.aws:
        return env.aws

    env.aws = connect_to_region(conf.region,
                        aws_access_key_id = conf.access_key_id,
                        aws_secret_access_key = conf.secret_access_key)

    if env.server:
        env.aws.instance = find_instance(name=env.server.name)

    return env.aws

def aws_task(fn):
    def wrapper(*args, **kwargs):
        boto = ec2_connection()
        return fn(boto, *args, **kwargs)
    return task(name=fn.func_name)(wrapper)

def build_if_needed():
    ec2_connection()
    if 'instance' not in conf:
        build(automated=True)

def exists():
    ec2_connection()
    return 'instance' in conf


def wait_for_status(instance, prompt, status):
    sys.stdout.write(prompt); sys.stdout.flush()
    while instance.update() != status:
        sys.stdout.write("."); sys.stdout.flush()
        time.sleep(1)

def find_instance(name=None, id=None):
    for reservation in env.aws.get_all_instances():
        for instance in reservation.instances:
            if name and name == instance.tags.get('Name'):
                return instance
            if id and id == instance.id:
                return instance

def find_address(ip):
    for a in env.aws.get_all_addresses():
        if a.public_ip == ip:
            return a

def find_security_group(name):
    for group in env.aws.get_all_security_groups():
        if group.name == name:
            return group

def authorize_tcp_port(group, number):
    from boto.exception import EC2ResponseError
    try:
        group.authorize('tcp', number, number, '0.0.0.0/0')
    except EC2ResponseError:
        pass

def create_instance():
    """Support function to create a new AWS instance."""
    from boto.ec2.blockdevicemapping import EBSBlockDeviceType, BlockDeviceMapping

    # We want a larger EBS root volume, so override /dev/sda1.
    dev_root = EBSBlockDeviceType()
    dev_root.size = conf.disk_size
    
    # Create the mapping.
    dev_mapping = BlockDeviceMapping()
    dev_mapping['/dev/sda1'] = dev_root 

    reservation = env.aws.run_instances(
        conf.ami,
        instance_type = conf.type, 
        key_name=conf.key_pair,
        placement=conf.zone,
        block_device_map = dev_mapping)

    instance = env.aws.instance = reservation.instances[0]
    wait_for_status(instance, "Creating server", "running")
    env.aws.create_tags([instance.id], {'Name': env.server.name})

    print " Done. \nInstance built:", instance.public_dns_name

    return instance

### Tasks ###
@aws_task
def regions(aws):
    """Lists the available AWS regions."""
    print "Available AWS Regions:"
    for r in aws.get_all_regions():
        print "", r

@aws_task
def zones(aws):
    """Lists the available zones in the region."""
    print "Available AWS Zones:"
    for r in aws.get_all_zones():
        print "", r

@aws_task
def build(aws, automated=False):
    """Builds the selected aws instance."""
    if not hasattr(env, 'server'):
        raise RuntimeError("Need a server selected first.")

    config = conf

    instance = find_instance(name=env.server.name)
    if instance:
        print "Instance found:", instance.id
    else:
        instance = create_instance()

    # Security Groups
    print "Authorizing ports %r for the security group." % ((80, 22),)
    group = find_security_group(config.security_group)
    authorize_tcp_port(group, 80)   # Web
    authorize_tcp_port(group, 22)   # SSH

    # Elastic IP
    for key, server in env.config.servers.items():
        if server.aws == config.key:
            address = find_address(server.host)
            if address:
                address.associate(instance.id)
                print "Elastic IP Associated:", address.public_ip

    if automated:
        env.user = 'root'
        env.hosts = [instance.public_dns_name]
    else:
        print "Please update the host in the config, and then run task 'own'."
        print "Host:", instance.public_dns_name

@aws_task
def terminate(aws):
    """
    Terminate the selected server.  This is not undoable and destroys it completely.
    """
    instance = env.aws.instance
    if instance is None:
        print "Instance not found, assumed dead."
        return
    print instance.tags.get('Name'), "|", instance.public_dns_name, "|", instance.update()
    if raw_input("Are you sure you want to terminate the server? It will be destroyed. [yes/NO]:\n").strip().lower() != "yes":
        return
    instance.terminate()
    print "Server destroyed."
    aws.delete_tags([instance.id], ['Name'])


@aws_task
def stop(aws):
    """Stops the server.  It is still avilable, but not running."""
    env.aws.instance.stop()
    wait_for_status(env.aws.instance, "Stopping server", "stopped")

@aws_task
def start(aws):
    """Starts the server."""
    env.aws.instance.start()
    wait_for_status(env.aws.instance, "Starting server", "running")

@aws_task
def status(aws):
    """Print the status of all instances."""
    for reservation in aws.get_all_instances():
        for instance in reservation.instances:
            print instance.tags.get('Name'), "|", instance.public_dns_name, "|", instance.update()

@aws_task
def ips(aws):
    """Print list of ip addresses and connected instances."""
    for a in aws.get_all_addresses():
        instance = find_instance(id=a.instance_id)
        if not instance:
            print a.public_ip, "-", "<unassigned>"
        else:
            print a.public_ip, "-", instance.tags.get('Name'), "-", instance.id, "-", instance.update()

@aws_task 
def ip_create(aws):
    """Create a new elastic ip."""
    print "New address allocated:"
    print "", aws.allocate_address().public_ip


@aws_task
def ip_set(aws, eip):
    """Sets the ip of the selected server to the given Elastic IP."""
    instance = env.aws.instance
    for a in aws.get_all_addresses():
        if a.public_ip == eip:
            a.associate(instance.id)
            print "Associated eip %r with instance %r" % (a.public_ip, instance.id)

