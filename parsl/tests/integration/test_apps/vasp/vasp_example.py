#!/usr/bin/env python3


"""Example for vasp.

[Notes from Dan]
1 - a python code that runs and creates a tar file - it writes the tar file directly,
    rather than creating the contents and then tarring them, though someone likely could
    change this to create the contents directly with some work.
2 - if we open the tar file, we get a bunch of stuff that includes - some directories
    called relax.xy, some directories called neb.xy, and a Makefile.
3 - We need to run VASP in each relax.xy directly - in our test case, there are 4 such
    directories.  Each VASP run will take 10-30 hours on O(100) cores.
4 - once these have finished, we run make, which uses the results in the relax.xy
    directories to build the inputs in the deb.xy directories - perhaps we could
    figure out what Make does and do it in python instead, but likely, we could
    just call Make from python...
5 - We can then run VASP in the deb.xy directories - in our test case, there are 17
    such directories, with similar VASP runtimes as before.
6 - Once these are done, we need to run some more python code that we don't actually
    have yet, but that a student here supposedly does have written and tested.

We will be working on Stampede 2. we haven't put our code in a repo (though we should - Qingyi...)
   and everything we used can be installed via pip.

"""

from parsl import bash_app, python_app, DataFlowKernel, ThreadPoolExecutor
import os
import shutil
import random

workers = ThreadPoolExecutor(max_workers=8)
dfk = DataFlowKernel(workers)


def create_dirs(cwd):

    for dir_ in ['relax.01', 'relax.02', 'relax.03']:
        rel_dir = f'{cwd}/{dir_}'
        if os.path.exists(rel_dir):
            shutil.rmtree(rel_dir)
        os.makedirs(rel_dir)
        for i in range(random.randint(1, 5)):
            rdir = f'{rel_dir}/{i}'
            os.makedirs(rdir)
            with open(f'{rdir}/results', 'w') as f:
                f.write(f"{i} {dir_} - test data\n")

    for dir_ in ['neb01', 'neb02', 'neb03', 'neb04']:
        rel_dir = f'{cwd}/{dir_}'
        if os.path.exists(rel_dir):
            shutil.rmtree(rel_dir)
        os.makedirs(rel_dir)
        with open(f'{rel_dir}/{dir_}.txt', 'w') as f:
            f.write(f"{rel_dir} test data\n")


@python_app(data_flow_kernel=dfk)
def ls(pwd, outputs=[]):
    import os
    items = os.listdir(pwd)
    with open(outputs[0], 'w') as f:
        f.write(' '.join(items))
        f.write('\n')
    # Returning list of items in current dir as python object
    return items


@bash_app(data_flow_kernel=dfk)
def catter(dir, outputs=[], stdout=None, stderr=None):
    pass


if __name__ == "__main__":

    pwd = os.getcwd()
    create_dirs(pwd)

    # Listing the cwd
    ls_fu, [res] = ls(pwd, outputs=['results'])

    dir_fus = {}
    for dir_ in ls_fu.result():
        if dir_.startswith('relax') and os.path.isdir(dir_):
            print(f"Launching {dir_}")
            dir_fus[dir_] = catter(dir_, outputs=[f'{dir_}.allresults'],
                                   stderr=f'{dir_}.stderr')

    for dir_ in dir_fus:
        try:
            print(dir_fus[dir_][0].result())
        except Exception as e:
            print(f"Caught exception{e} on {dir_}")
