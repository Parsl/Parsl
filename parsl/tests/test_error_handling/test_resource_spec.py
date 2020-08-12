import parsl
from parsl.app.app import python_app
#from parsl.tests.configs.local_threads import config
# from parsl.tests.configs.htex_local import config
from parsl.tests.configs.workqueue_ex import config
from parsl.executors.errors import UnsupportedFeatureError, ExecutorError
from parsl.executors import WorkQueueExecutor


@python_app
def double(x, parsl_resource_specification={}):
    return x * 2


def test_resource(n=2):
    executors = parsl.dfk().executors
    executor = None
    for label in executors:
        if label != 'data_manager':
            executor = executors[label]
            break

    # Specify incorrect number of resources
    spec = {'cores': 2, 'memory': 1000}
    fut = double(n, parsl_resource_specification=spec)
    try:
        fut.result()
    except UnsupportedFeatureError as e:
        print(e)
        assert not isinstance(executor, WorkQueueExecutor)
    except Exception as e:
        print(e)
        assert isinstance(e, ExecutorError)

    # Specify resources with wrong types
    # cpus is incorrect
    spec = {'cpus': 2, 'memory': 1000, 'disk': 1000}
    fut = double(n, parsl_resource_specification=spec)
    try:
        fut.result()
    except UnsupportedFeatureError as e:
        print(e)
        assert not isinstance(executor, WorkQueueExecutor)
    except Exception as e:
        print(e)
        assert isinstance(e, ExecutorError)

    # Correct specification
    spec = {'cores': 2, 'memory': 1000, 'disk': 1000}
    fut = double(n, parsl_resource_specification=spec)
    try:
        fut.result()
    except UnsupportedFeatureError as e:
        print(e)
        assert not isinstance(executor, WorkQueueExecutor)
    else:
        assert isinstance(executor, WorkQueueExecutor)


if __name__ == '__main__':
    local_config = config
    parsl.load(local_config)
    x = test_resource(2)
