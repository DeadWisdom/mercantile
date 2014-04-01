import sys; sys.path.insert(0, '.')

from mercantile.config import config, required

def test_config():
    conf = config.add_group('aws', {
        'region': unicode,                        # Region to place the server, e.g. 'us-east-1'
        'access_key_id': unicode | required,      # Access Key from the AWS Command Console.
        'key_pair': unicode,                      # Name of the Key Pair to use.
        'security_group': unicode,                # The Security Group to use.
        'ami': unicode,                           # The name of the AMI to use.
        'zone': unicode,                          # The Zone to place the server in, e.g. 'us-east-1c'
        'type': unicode,                          # The Type to use, e.g. 'm1.small'
        'disk_size': int,                         # Disk size in gigabytes.
    })

    config.add('aws', {
        'secret_access_key': unicode | required,  # Secret Access Key and from the AWS Command Console.
    })

    config.load('tests/examples/aws.yaml')

    assert config.value.aws is conf

    small = conf.small
    assert small.key == 'small'
    assert small.region == 'us-east-1'
    assert small.access_key_id == 'FAKE$@!@%YWUTERHGFT'
    assert small.secret_access_key == 'fake328twigpojasdfoiweitjiogjaspdofjjflk'
    assert small.type == 'm1.small'

    micro = conf.micro
    assert small.key == 'small'
    assert micro.region == 'us-east-1'
    assert micro.access_key_id == 'FAKE$@!@%YWUTERHGFT'
    assert micro.secret_access_key == 'fake328twigpojasdfoiweitjiogjaspdofjjflk'
    assert micro.type == 't1.micro'
