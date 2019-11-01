import logging
import os
import platform
import requests
import socket
import fcntl
import struct
import psutil

logger = logging.getLogger(__name__)


def address_by_route():
    logger.debug("Finding address by querying local routing table")
    addr = os.popen("/sbin/ip route get 8.8.8.8 | awk '{print $NF;exit}'").read().strip()
    logger.debug("Address found: {}".format(addr))
    return addr


def address_by_query():
    logger.debug("Finding address by querying remote service")
    addr = requests.get('https://api.ipify.org').text
    logger.debug("Address found: {}".format(addr))
    return addr


def address_by_hostname():
    logger.debug("Finding address by using local hostname")
    addr = platform.node()
    logger.debug("Address found: {}".format(addr))
    return addr


def address_by_interface(ifname):
    """Returns the IP address of the given interface name, e.g. 'eth0'

    Parameters
    ----------
    ifname : str
        Name of the interface whose address is to be returned. Required.

    Taken from this Stack Overflow answer: https://stackoverflow.com/questions/24196932/how-can-i-get-the-ip-address-of-eth0-in-python#24196955
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,  # SIOCGIFADDR
        struct.pack('256s', bytes(ifname[:15], 'utf-8'))
    )[20:24])


def get_all_addresses():
    """ Uses a combination of methods to determine possible addresses.

    Returns:
         list of addresses as strings
    """
    net_interfaces = psutil.net_if_addrs()

    s_addresses = []
    for interface in net_interfaces:
        try:
            s_addresses.append(address_by_interface(interface))
        except Exception:
            logger.exception("Ignoring failure to fetch address from interface {}".format(interface))
            pass

    s_addresses = set(s_addresses)

    try:
        s_addresses.add(address_by_hostname())
        s_addresses.add(address_by_route())
        s_addresses.add(address_by_query())
    except Exception:
        logger.exception("Ignoring one or more address finder method failure")
        pass

    return s_addresses
