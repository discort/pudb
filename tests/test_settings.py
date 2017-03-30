#import __builtin__

import pytest

from pudb.py3compat import PY3, builtins
from pudb.settings import load_breakpoints

if PY3:
    from unittest import mock
else:
    import mock


#def test_without_breakpoints():
#    assert load_breakpoints() == []


def test_load_breakpoints(monkeypatch):
    class FakeOpen(object):
        def __init__(self, *args, **kwargs):
            pass

        def close(self):
            pass

        def readlines(*args, **kwargs):
            return ['b /home/user/test.py:41\n', 'b /home/user/test.py:50\n']

    #monkeypatch.setattr(builtins, 'open', FakeOpen)
    fake_data = ['b /home/user/test.py:41\n', 'b /home/user/test.py:50\n']
    with mock.patch('__main__.open', mock.mock_open(read_data=fake_data)):
        result = load_breakpoints()
    print(result)
    expected = [('/home/user/test.py', 41, False, None, None),
                ('/home/user/test.py', 50, False, None, None)]
    assert result == expected
