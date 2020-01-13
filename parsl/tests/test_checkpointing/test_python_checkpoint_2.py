import argparse
import os
import pytest
import parsl

from parsl.tests.test_checkpointing.test_python_checkpoint_1 import test_initial_checkpoint_write
from parsl.tests.test_checkpointing.test_python_checkpoint_1 import launch_n_random
from parsl.tests.configs.local_threads_checkpoint import fresh_config


@pytest.mark.local
def test_loading_checkpoint(n=2):
    """Load memoization table from previous checkpoint
    """

    rundir, results = test_initial_checkpoint_write()

    local_config = fresh_config()
    local_config.checkpoint_files = [os.path.join(rundir, 'checkpoint')]
    parsl.load(local_config)

    relaunched = launch_n_random(n)

    assert len(relaunched) == len(results) == n, "Expected all results to have n items"

    for i in range(n):
        assert relaunched[i] == results[i], "Expected relaunched to contain cached results from first run"
    parsl.clear()


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--count", default="10",
                        help="Count of apps to launch")
    parser.add_argument("-d", "--debug", action='store_true',
                        help="Count of apps to launch")
    args = parser.parse_args()

    if args.debug:
        parsl.set_stream_logger()

    x = test_loading_checkpoint()
