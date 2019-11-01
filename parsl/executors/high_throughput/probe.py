import zmq
import argparse
import uuid
from parsl.addresses import get_all_addresses
from zmq.utils.monitor import recv_monitor_message
import time
HEARTBEAT_CODE = (2 ** 32) - 1


def probe_addresses(addresses, task_port, timeout=2):
    """
    Parameters
    ----------

    addresses: [string]
        List of addresses as strings
    task_port: int
        Task port on the interchange
    timeout: int
        Timeout in seconds

    Returns
    -------
    None or string address
    """
    context = zmq.Context()
    addr_map = {}
    for addr in addresses:
        socket = context.socket(zmq.DEALER)
        # socket.setsockopt(zmq.LINGER, 0)
        url = f"tcp://{addr}:{task_port}"
        print("Trying url: ", url)
        socket.connect(url)
        addr_map[addr] = {'sock': socket,
                          'mon_sock': socket.get_monitor_socket(events=zmq.EVENT_CONNECTED)}

    start_t = time.time()

    print(addr_map)

    first_connected = None
    while time.time() < start_t + timeout:
        for addr in addr_map:
            try:
                recv_monitor_message(addr_map[addr]['mon_sock'], zmq.NOBLOCK)
                first_connected = addr
                print("Connected :", addr)
                break
            except zmq.Again:
                pass
            # Wait for 2ms
            # print("Sleeping...")
            time.sleep(0.01)
    for addr in addr_map:
        addr_map[addr]['sock'].close()

    return first_connected


class TestWorker(object):

    def __init__(self, addresses, port):
        uid = str(uuid.uuid4())
        self.context = zmq.Context()
        self.task_incoming = self.context.socket(zmq.DEALER)
        self.task_incoming.setsockopt(zmq.IDENTITY, uid.encode('utf-8'))
        # Linger is set to 0, so that the manager can exit even when there might be
        # messages in the pipe
        self.task_incoming.setsockopt(zmq.LINGER, 0)

        address = probe_addresses(addresses, port)
        print("Viable address :", address)
        self.task_incoming.connect(f"tcp://{address}:{port}")
        print("Here")

    def heartbeat(self):
        """ Send heartbeat to the incoming task queue
        """
        heartbeat = (HEARTBEAT_CODE).to_bytes(4, "little")
        r = self.task_incoming.send(heartbeat)
        print("Return from heartbeat: {}".format(r))


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", required=True,
                        help="Port to connect to")

    args = parser.parse_args()
    addresses = get_all_addresses()
    worker = TestWorker(addresses, args.port)
    worker.heartbeat()
