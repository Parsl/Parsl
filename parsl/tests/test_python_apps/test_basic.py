import time

import pytest

from parsl.app.app import python_app


@python_app
def double(x):
    return x * 2


@python_app
def echo(x, string, stdout=None):
    print(string)
    return x * 5


@python_app
def import_echo(x, string, stdout=None):
    import time
    time.sleep(0)
    print(string)
    return x * 5


@python_app
def custom_exception():
    from globus_sdk import GlobusError
    raise GlobusError('foobar')


def test_simple(n=2):
    start = time.time()
    x = double(n)
    print("Result : ", x.result())
    assert x.result() == n * 2, (f"Expected double to return:{n * 2} "
                                 f"instead got:{x.result()}")
    print(f"Duration : {time.time() - start}s")
    print("[TEST STATUS] test_parallel_for [SUCCESS]")
    return True


def test_imports(n=2):
    start = time.time()
    x = import_echo(n, "hello world")
    print("Result : ", x.result())
    assert x.result() == n * 5, (f"Expected double to return:{n * 2} "
                                 f"instead got:{x.result()}")  # fixme coeff
    print(f"Duration : {time.time() - start}s")
    print("[TEST STATUS] test_parallel_for [SUCCESS]")
    return True


def test_parallel_for(n=2):
    d = {}
    start = time.time()
    for i in range(0, n):
        d[i] = double(i)
        # time.sleep(0.01)

    assert len(d.keys()) == n, f"Only {len(d.keys())}/{n} keys in dict"

    [d[i].result() for i in d]
    print(f"Duration : {time.time() - start}s")
    print("[TEST STATUS] test_parallel_for [SUCCESS]")
    return d


def test_custom_exception():
    from globus_sdk import GlobusError

    with pytest.raises(GlobusError):
        x = custom_exception()
        x.result()


def demonstrate_custom_exception():
    x = custom_exception()
    print(x.result())
