"""MPIExecutor builds on the Swift/T executor to use MPI for fast task distribution

"""
from concurrent.futures import Future
import logging
import uuid
import time
import threading
import queue
import zmq

try:
    import mpi4py
except ImportError:
    _mpi_enabled = False
else:
    _mpi_enabled = True

from ipyparallel.serialize import pack_apply_message  # , unpack_apply_message
from ipyparallel.serialize import deserialize_object  # , serialize_object,

from parsl.executors.mpix import zmq_pipes
from parsl.executors.errors import *
from parsl.executors.base import ParslExecutor
from parsl.dataflow.error import ConfigurationError

from libsubmit.utils import RepresentationMixin
from libsubmit.providers import LocalProvider

logger = logging.getLogger(__name__)

BUFFER_THRESHOLD = 1024 * 1024
ITEM_THRESHOLD = 1024

HEARTBEAT_PERIOD = 30   # Seconds
MAX_BEATS_MISSABLE = 3  # Failure assumed after these many heartbeat periods


class MPIExecutor(ParslExecutor, RepresentationMixin):
    """The MPI executor.

    The MPI Executor system has 3 components:
      1. The MPIExecutor instance which is run as part of the Parsl script.
      2. The MPI based fabric which coordinates task execution over several nodes.
      3. ZeroMQ pipes that connect the MPIExecutor and the fabric

    Our design assumes that there is a single fabric running over a `block` and that
    there might be several such `fabric` instances.

    Here is a diagram

    .. code:: python

                        |  Data   |  Executor   |   IPC      | External Process(es)
                        |  Flow   |             |            |
                   Task | Kernel  |             |            |
                 +----->|-------->|------------>|outgoing_q -|-> Fabric (MPI Ranks)
                 |      |         |             |            |    |         |
           Parsl<---Fut-|         |             |            |  result   exception
                     ^  |         |             |            |    |         |
                     |  |         |   Q_mngmnt  |            |    V         V
                     |  |         |    Thread<--|incoming_q<-|--- +---------+
                     |  |         |      |      |            |
                     |  |         |      |      |            |
                     +----update_fut-----+

    """

    def __init__(self,
                 label='MPIExecutor',
                 provider=LocalProvider(),
                 launch_cmd=None,
                 jobs_q_url=None,
                 results_q_url=None,
                 storage_access=None,
                 working_dir=None,
                 engine_debug_level=None,
                 mock=False,
                 managed=True):
        """Initialize the MPI Executor

        We only store the config options here, the executor is started only when
        start() is called.
        """

        if not _mpi_enabled:
            raise OptionalModuleMissing("mpi4py", "Cannot initialize MPIExecutor without mpi4py")
        else:
            # This is only to stop flake8 from complaining
            logger.debug("MPI version :{}".format(mpi4py.__version__))

        logger.debug("Initializing MPIExecutor")
        self.jobs_q_url = jobs_q_url
        self.results_q_url = results_q_url
        self.label = label
        self.launch_cmd = launch_cmd
        self.mock = mock
        self.provider = provider
        self.engine_debug_level = engine_debug_level
        self.storage_access = storage_access if storage_access is not None else []
        if len(self.storage_access) > 1:
            raise ConfigurationError('Multiple storage access schemes are not yet supported')
        self.working_dir = working_dir
        self.managed = managed
        self.engines = []
        self.tasks = {}
        if not launch_cmd:
            self.launch_cmd = "mpiexec -np {tasks_per_node} fabric.py -d \
 --task_url={task_url} \
 --result_url={result_url} \
 --id={fabric_id} \
 --logdir={logdir}"

        if (self.provider.tasks_per_node * self.provider.nodes_per_block) < 2:
            logger.error("MPIExecutor requires atleast 2 workers launched")
            raise InsufficientMPIRanks(tasks_per_node=self.provider.tasks_per_node,
                                       nodes_per_block=self.provider.nodes_per_block)

    def start(self):
        """ Here we create the ZMQ pipes and the MPI fabric
        """
        self.outgoing_q = zmq_pipes.JobsQOutgoing(self.jobs_q_url)
        self.incoming_q = zmq_pipes.ResultsQIncoming(self.results_q_url)

        self.is_alive = True

        self._queue_management_thread = None
        self._start_queue_management_thread()

        print("Run dir : ", self.run_dir)
        logger.debug("Created management thread : %s", self._queue_management_thread)

        l_cmd = self.launch_cmd.format(task_url=self.jobs_q_url,
                                       result_url=self.results_q_url,
                                       tasks_per_node=self.provider.tasks_per_node,
                                       nodes_per_block=self.provider.nodes_per_block,
                                       fabric_id=uuid.uuid4(),
                                       logdir="{}/parsl_worker_logs".format(self.run_dir)
        )
        self.launch_cmd = l_cmd
        logger.debug("Launch command :{}".format(self.launch_cmd))

        if self.provider:
            self._scaling_enabled = self.provider.scaling_enabled
            logger.debug("Starting MPIExecutor with provider:\n%s", self.provider)
            if hasattr(self.provider, 'init_blocks'):
                try:
                    for i in range(self.provider.init_blocks):
                        engine = self.provider.submit(self.launch_cmd, 1)
                        logger.debug("Launched block: {0}:{1}".format(i, engine))
                        if not engine:
                            raise(ScalingFailed(self.provider.label,
                                                "Attempts to provision nodes via provider has failed"))
                        self.engines.extend([engine])

                except Exception as e:
                    logger.error("Scaling out failed: %s" % e)
                    raise e

        else:
            self._scaling_enabled = False
            logger.debug("Starting IpyParallelExecutor with no provider")

    def _queue_management_worker(self):
        """Listen to the queue for task status messages and handle them.

        Depending on the message, tasks will be updated with results, exceptions,
        or updates. It expects the following messages:

        .. code:: python

            {
               "task_id" : <task_id>
               "result"  : serialized result object, if task succeeded
               ... more tags could be added later
            }

            {
               "task_id" : <task_id>
               "exception" : serialized exception object, on failure
            }

        We do not support these yet, but they could be added easily.

        .. code:: python

            {
               "task_id" : <task_id>
               "cpu_stat" : <>
               "mem_stat" : <>
               "io_stat"  : <>
               "started"  : tstamp
            }

        The `None` message is a die request.
        """

        fabric_catalog = {}

        while True:
            if not self.is_alive:
                break

            try:
                msg = self.incoming_q.get()

            except zmq.Again as e:
                for fabric_id in fabric_catalog:
                    if time.time() - fabric_catalog[fabric_id]['last_beat'] > HEARTBEAT_PERIOD * MAX_BEATS_MISSABLE:
                        logger.debug("Fabric:{} has missed {}. Cancelling tasks".format(fabric_id,
                                                                                        MAX_BEATS_MISSABLE))
                        for tid in fabric_catalog[fabric_id]['active_tasks']:
                            self.tasks[tid].set_exception(
                                Exception("EngineError: MPIExecutor has lost contact with fabric:{}".format(fabric_id))
                            )
                time.sleep(0.5)
                continue

            except queue.Empty as e:
                # Timed out.
                time.sleep(0.1)
                continue

            except IOError as e:
                logger.debug("[MTHREAD] Caught broken queue with exception code {}: {}".format(e.errno, e))
                raise

            except Exception as e:
                logger.debug("[MTHREAD] Caught unknown exception: {}".format(e))
                raise

            else:
                if msg is None:
                    logger.debug("[MTHREAD] Got None")
                    return

                elif 'hbt' in msg:
                    fabric_id = msg['fabric_id']
                    logger.debug("[MTHREAD] Got heartbeat from :{}".format(msg['fabric_id']))

                    if fabric_id not in fabric_catalog:
                        fabric_catalog[fabric_id] = {'last_beat': time.time(),
                                                     'active_tasks': []}
                    else:
                        fabric_catalog[fabric_id]['last_beat'] = time.time()
                        fabric_catalog[fabric_id]['active_tasks'] = msg['active_tasks']

                else:
                    task_id = msg['task_id']
                    task_fut = self.tasks[msg['task_id']]
                    fabric_id = msg.get('fabric_id', None)

                    if fabric_id not in fabric_catalog:
                        fabric_catalog[fabric_id] = {'last_beat': time.time(),
                                                     'active_tasks': []}

                    if 'result' in msg:
                        result, _ = deserialize_object(msg['result'])
                        task_fut.set_result(result)
                        try:
                            fabric_catalog[fabric_id]['active_tasks'].remove(task_id)
                        except ValueError:
                            pass

                    elif 'exception' in msg:
                        exception, _ = deserialize_object(msg['exception'])
                        task_fut.set_exception(exception)
                        try:
                            fabric_catalog[fabric_id]['active_tasks'].remove(task_id)
                        except ValueError:
                            pass

                    elif 'info' in msg:
                        # logger.debug('Received start notice from:{}'.format(task_id))
                        # We ignore the start time returned in msg['info'] for now
                        # info = msg['info']
                        fabric_catalog[fabric_id]['active_tasks'].append(task_id)

    # When the executor gets lost, the weakref callback will wake up
    # the queue management thread.
    def weakref_cb(self, q=None):
        """We do not use this yet."""
        q.put(None)

    def _start_queue_management_thread(self):
        """Method to start the management thread as a daemon.

        Checks if a thread already exists, then starts it.
        Could be used later as a restart if the management thread dies.
        """
        logging.debug("In _start %s", "*" * 40)
        if self._queue_management_thread is None:
            logging.debug("Starting management thread ")
            self._queue_management_thread = threading.Thread(target=self._queue_management_worker)
            self._queue_management_thread.daemon = True
            self._queue_management_thread.start()

        else:
            logging.debug("Management thread already exists, returning")

    def shutdown(self):
        """Shutdown method, to kill the threads and workers."""
        self.is_alive = False
        logging.debug("Waking management thread")
        self.incoming_q.put(None)  # Wake up the thread
        self._queue_management_thread.join()  # Force join
        logging.debug("Exiting thread")
        self.worker.join()
        return True

    def submit(self, func, *args, **kwargs):
        """Submits work to the the outgoing_q.

        The outgoing_q is an external process listens on this
        queue for new work. This method is simply pass through and behaves like a
        submit call as described here `Python docs: <https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.ThreadPoolExecutor>`_

        Args:
            - func (callable) : Callable function
            - *args (list) : List of arbitrary positional arguments.

        Kwargs:
            - **kwargs (dict) : A dictionary of arbitrary keyword args for func.

        Returns:
              Future
        """
        task_id = uuid.uuid4()

        logger.debug("Pushing function {} to queue with args {}".format(func, args))

        self.tasks[task_id] = Future()

        fn_buf = pack_apply_message(func, args, kwargs,
                                    buffer_threshold=1024 * 1024,
                                    item_threshold=1024)

        msg = {"task_id": task_id,
               "buffer": fn_buf}

        # Post task to the the outgoing queue
        self.outgoing_q.put(msg)

        # Return the future
        return self.tasks[task_id]

    @property
    def scaling_enabled(self):
        return self._scaling_enabled

    def scale_out(self, workers=1):
        """Scales out the number of active workers by 1.

        This method is not implemented for threads and will raise the error if called.
        This would be nice to have, and can be done

        Raises:
             NotImplementedError
        """
        if self.provider:
            r = self.provider.submit(self.launch_cmd)
            self.engines.extend([r])
        else:
            logger.error("No execution provider available")
            r = None

        return r

    def scale_in(self, blocks):
        """Scale in the number of active blocks by specified amount.

        This method is not implemented for turbine and will raise an error if called.

        Raises:
             NotImplementedError
        """
        to_kill = self.engines[:blocks]
        if self.provider:
            r = self.provider.cancel(to_kill)
        else:
            logger.error("No execution provider available")
            r = None

        return r

    def shutdown(self, hub=True, targets='all', block=False):
        """Shutdown the executor, including all workers and controllers.

        This is not implemented.

        Kwargs:
            - hub (Bool): Whether the hub should be shutdown, Default:True,
            - targets (list of ints| 'all'): List of engine id's to kill, Default:'all'
            - block (Bool): To block for confirmations or not

        Raises:
             NotImplementedError
        """
        return True


if __name__ == "__main__":

    print("Start")
    turb_x = MPIExecutor()
    print("Done")
