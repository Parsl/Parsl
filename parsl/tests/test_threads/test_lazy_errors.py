import parsl
import pytest
from parsl import python_app
from parsl.tests.configs.local_threads import fresh_config


@pytest.mark.local
def test_lazy_behavior():
    """Testing lazy errors to work"""

    config = fresh_config()
    config.lazy_errors = True
    parsl.load(config)

    @python_app
    def divide(a, b):
        return a / b

    items = []
    for i in range(0, 1):
        items.append(divide(10, i))

    while True:
        if items[0].done:
            break

    parsl.clear()
    return


if __name__ == "__main__":

    test_lazy_behavior()
