import pytest

import parsl
from parsl import App, File
from parsl.configs.local_threads import config

parsl.clear()
parsl.load(config)


@App('python')
def convert(inputs=[], outputs=[]):
    with open(inputs[0].filepath, 'r') as inp:
        content = inp.read()
        with open(outputs[0].filepath, 'w') as out:
            out.write(content.upper())


# @pytest.mark.local
@pytest.mark.skip("Broke somewhere between PR #525 and PR #652")
def test():
    # create an remote Parsl file
    inp = File('ftp://www.iana.org/pub/mirror/rirstats/arin/ARIN-STATS-FORMAT-CHANGE.txt')

    # create a local Parsl file
    out = File('file:///tmp/ARIN-STATS-FORMAT-CHANGE.txt')

    # call the convert app with the Parsl file
    f = convert(inputs=[inp], outputs=[out])
    f.result()
