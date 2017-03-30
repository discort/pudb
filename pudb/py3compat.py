from __future__ import absolute_import, division, print_function
import sys

PY3 = sys.version_info[0] >= 3
if PY3:
    raw_input = input
    xrange = range
    integer_types = (int,)
    string_types = (str,)
    text_type = str
    _next = "__next__"

    def execfile(fname, globs, locs=None):
        exec(compile(open(fname).read(), fname, 'exec'), globs, locs or globs)
else:
    raw_input = raw_input
    xrange = xrange
    integer_types = (int, long)  # noqa: F821
    string_types = (basestring,)  # noqa: F821
    text_type = unicode  # noqa: F821
    execfile = execfile
    _next = "next"

# PY3
try:
    import builtins
    from io import StringIO
    from functools import partial
    from configparser import ConfigParser
# PY2
except ImportError:
    import __builtin__ as builtins
    from cStringIO import StringIO
    from ConfigParser import ConfigParser

    def partial(func, *args, **keywords):
        def newfunc(*fargs, **fkeywords):
            newkeywords = keywords.copy()
            newkeywords.update(fkeywords)
            return func(*(args + fargs), **newkeywords)
        newfunc.func = func
        newfunc.args = args
        newfunc.keywords = keywords
        return newfunc
