import os
import platform
import socket


def fresh_config():
    hostname = os.getenv('PARSL_HOSTNAME', platform.uname().node)
    print(f"Loading config for {hostname}")

    if 'thetalogin' in hostname:
        from parsl.tests.configs.theta import fresh_config
        config = fresh_config()
        print("Loading Theta config")

    elif 'frontera' in hostname:
        print("Loading Frontera config")
        from parsl.tests.configs.frontera import fresh_config
        config = fresh_config()

    elif 'summit' in socket.getfqdn():
        print("Loading Frontera config")
        from parsl.tests.configs.summit import fresh_config
        config = fresh_config()

    else:
        print("Loading Local HTEX config")
        from parsl.tests.configs.htex_local import config
        config.executors[0].max_workers = 2
        config.executors[0].provider.init_blocks = 2
        config.executors[0].provider.max_blocks = 2
        config.executors[0].provider.min_blocks = 2

    return config


config = fresh_config()
