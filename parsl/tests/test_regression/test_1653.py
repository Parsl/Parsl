import parsl
from parsl import python_app
import pytest
from parsl.tests.configs.htex_local import config

local_config = config


@python_app
def compute_descript(size=1000):
    import numpy as np
    x = np.array(list(range(0, size)), dtype=complex).astype(np.float32)
    return x


@pytest.mark.local
def test_1653():
    """ Check if #1653 works correctly
    """
    #from parsl.configs.htex_local import config
    #parsl.load(config)

    x = compute_descript(size=100).result()
    assert x.shape == (100,), "Got incorrect numpy shape"

    x = compute_descript(size=1000).result()
    assert x.shape == (1000,), "Got incorrect numpy shape"
    #parsl.clear()



if __name__ == "__main__":
    test_1653()