from setuptools import setup, find_packages

with open('parsl/version.py') as f:
    exec(f.read())

with open('requirements.txt') as f:
    install_requires = f.readlines()

setup(
    name='parsl',
    version=VERSION,
    description='Simple data dependent workflows in Python',
    long_description='Simple parallel workflows system for Python',
    url='https://github.com/Parsl/parsl',
    author='The Parsl Team',
    author_email='parsl@googlegroups.com',
    license='Apache 2.0',
    download_url='https://github.com/Parsl/parsl/archive/{}.tar.gz'.format(VERSION),
    package_data={'': ['LICENSE']},
    packages=find_packages(),
    install_requires=install_requires,
    scripts = ['parsl/executors/high_throughput/process_worker_pool.py',
               'parsl/executors/extreme_scale/mpi_worker_pool.py'],
    extras_require = {
        'db_logging' : ['CMRESHandler', 'psutil', 'sqlalchemy'],
        'aws' : ['boto3'],
        'jetstream' : ['python-novaclient'],
        'extreme_scale' : ['mpi4py'],
        'docs' : ['nbsphinx', 'sphinx_rtd_theme'],
        'google_cloud' : ['google-auth', 'google-api-python-client']
        },
    classifiers = [
        # Maturity
        'Development Status :: 3 - Alpha',
        # Intended audience
        'Intended Audience :: Developers',
        # Licence, must match with licence above
        'License :: OSI Approved :: Apache Software License',
        # Python versions supported
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    keywords=['Workflows', 'Scientific computing'],
)
