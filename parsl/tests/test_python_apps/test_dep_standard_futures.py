import parsl
from concurrent.futures import Future


@parsl.python_app
def copy_app(v):
    return v


def test_future_result_dependency():

    plain_fut = Future()

    parsl_fut = copy_app(plain_fut)

    assert not parsl_fut.done()

    message = "Test"

    plain_fut.set_result(message)

    assert parsl_fut.result() == message


def test_future_fail_dependency():

    plain_fut = Future()

    parsl_fut = copy_app(plain_fut)

    assert not parsl_fut.done()

    plain_fut.set_result(ValueError("Plain failure"))

    # TODO: be tighter on the returned exception: it should be a dependency failure exception
    assert parsl_fut.exception() is not None
