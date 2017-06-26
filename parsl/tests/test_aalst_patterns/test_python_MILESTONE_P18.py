import parsl
from parsl import *
import random
import argparse
import time 

workers = ThreadPoolExecutor(max_workers = 4)
dfk = DataFlowKernel(workers)

@App('python', dfk)
def rand():
    x = random.randint(1, 10)
    print(x)
    return x

@App('python', dfk)
def square(x):
    if x > 5: 
        return x**2
    else:
        time.sleep(5)
        return x**2

@App('python', dfk)
def increment(x):
    time.sleep(1)
    return x + 1

@App('python', dfk)
def cubed(x):
    return x**3

def test_milestone():
    r = rand().result()
    i = increment(r)
    s = square(r)
    while s.done() != True:
        if i.done() == True:
            print(cubed(r).result())
            return 


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-x", "--input", default = "4", action = "store", dest = "x", type = int)
    args = parser.parse_args()
    test_milestone()
