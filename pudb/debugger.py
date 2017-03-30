#! /usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function
import bdb
import gc
import sys
import linecache
from types import TracebackType

from pudb.py3compat import PY3
from pudb.settings import load_config, save_config, save_breakpoints, load_breakpoints
from pudb.source_code_providers import (NullSourceCodeProvider, DirectSourceCodeProvider,
                                        FileSourceCodeProvider)
from pudb.ui import DebuggerUI

CONFIG = load_config()
save_config(CONFIG)


class Debugger(bdb.Bdb):
    def __init__(self, stdin=None, stdout=None, term_size=None, steal_output=False):
        super(Debugger, self).__init__()

        self.ui = DebuggerUI(self, stdin=stdin, stdout=stdout, term_size=term_size)
        self.steal_output = steal_output

        self.setup_state()

        if steal_output:
            raise NotImplementedError("output stealing")

        for bpoint_descr in load_breakpoints():
            self.set_break(*bpoint_descr)

    # These (dispatch_line and set_continue) are copied from bdb with the
    # patch from https://bugs.python.org/issue16482 applied. See
    # https://github.com/inducer/pudb/pull/90.
    def dispatch_line(self, frame):
        if self.stop_here(frame) or self.break_here(frame):
            self.user_line(frame)
            if self.quitting:
                raise bdb.BdbQuit
            # Do not re-install the local trace when we are finished debugging,
            # see issues 16482 and 7238.
            if not sys.gettrace():
                return None
        return self.trace_dispatch

    def set_continue(self):
        # Don't stop except at breakpoints or when finished
        self._set_stopinfo(self.botframe, None, -1)
        if not self.breaks:
            # no breakpoints; run without debugger overhead
            sys.settrace(None)
            frame = sys._getframe().f_back
            while frame:
                del frame.f_trace
                if frame is self.botframe:
                    break
                frame = frame.f_back

    def set_trace(self, frame=None, as_breakpoint=True):
        """Start debugging from `frame`.

        If frame is not specified, debugging starts from caller's frame.

        Unlike Bdb.set_trace(), this does not call self.reset(), which causes
        the debugger to enter bdb source code. This also implements treating
        set_trace() calls as breakpoints in the PuDB UI.
        """
        if frame is None:
            frame = thisframe = sys._getframe().f_back
        else:
            thisframe = frame
        # See pudb issue #52. If this works well enough we should upstream to
        # stdlib bdb.py.
        # self.reset()

        while frame:
            frame.f_trace = self.trace_dispatch
            self.botframe = frame
            frame = frame.f_back

        thisframe_info = (self.canonic(thisframe.f_code.co_filename), thisframe.f_lineno)
        if thisframe_info not in self.set_traces or self.set_traces[thisframe_info]:
            if as_breakpoint:
                self.set_traces[thisframe_info] = True
                if self.ui.source_code_provider is not None:
                    self.ui.set_source_code_provider(self.ui.source_code_provider,
                                                     force_update=True)

            self.set_step()
            sys.settrace(self.trace_dispatch)
        else:
            return

    def save_breakpoints(self):
        save_breakpoints([
            bp
            for fn, bp_lst in self.get_all_breaks().items()
            for lineno in bp_lst
            for bp in self.get_breaks(fn, lineno)
            if not bp.temporary])

    def enter_post_mortem(self, exc_tuple):
        self.post_mortem = True

    def setup_state(self):
        self.bottom_frame = None
        self.mainpyfile = ''
        self._wait_for_mainpyfile = False
        self.current_bp = None
        self.post_mortem = False
        # Mapping of (filename, lineno) to bool. If True, will stop on the
        # set_trace() call at that location.
        self.set_traces = {}

    def restart(self):
        from linecache import checkcache
        checkcache()
        self.ui.set_source_code_provider(NullSourceCodeProvider())
        self.setup_state()

    def do_clear(self, arg):
        self.clear_bpbynumber(int(arg))

    def set_frame_index(self, index):
        self.curindex = index
        if index < 0 or index >= len(self.stack):
            return

        self.curframe, lineno = self.stack[index]

        filename = self.curframe.f_code.co_filename

        if not linecache.getlines(filename):
            code = self.curframe.f_globals.get("_MODULE_SOURCE_CODE")
            if code is not None:
                code_provider = DirectSourceCodeProvider(self.curframe.f_code.co_name, code)
                self.ui.set_current_line(lineno, code_provider)
            else:
                self.ui.set_current_line(lineno, NullSourceCodeProvider())

        else:
            self.ui.set_current_line(lineno, FileSourceCodeProvider(self, filename))

        self.ui.update_var_view()
        self.ui.update_stack()

        self.ui.stack_list._w.set_focus(self.ui.translate_ui_stack_index(index))

    def move_up_frame(self):
        if self.curindex > 0:
            self.set_frame_index(self.curindex - 1)

    def move_down_frame(self):
        if self.curindex < len(self.stack) - 1:
            self.set_frame_index(self.curindex + 1)

    def get_shortened_stack(self, frame, tb):
        stack, index = self.get_stack(frame, tb)

        for i, (s_frame, lineno) in enumerate(stack):
            if s_frame is self.bottom_frame and index >= i:
                stack = stack[i:]
                index -= i

        return stack, index

    def interaction(self, frame, exc_tuple=None, show_exc_dialog=True):
        if exc_tuple is None:
            tb = None
        elif isinstance(exc_tuple, TracebackType):
            # For API compatibility with other debuggers, the second variable
            # can be a traceback object.  In that case, we need to retrieve the
            # corresponding exception tuple.
            tb = exc_tuple
            exc, = (exc for exc in gc.get_referrers(tb)
                    if getattr(exc, "__traceback__", None) is tb)
            exc_tuple = type(exc), exc, tb
        else:
            tb = exc_tuple[2]

        if frame is None and tb is not None:
            frame = tb.tb_frame

        found_bottom_frame = False
        walk_frame = frame
        while True:
            if walk_frame is self.bottom_frame:
                found_bottom_frame = True
                break
            if walk_frame is None:
                break
            walk_frame = walk_frame.f_back

        if not found_bottom_frame and not self.post_mortem:
            return

        self.stack, index = self.get_shortened_stack(frame, tb)

        if self.post_mortem:
            index = len(self.stack) - 1

        self.set_frame_index(index)

        self.ui.call_with_ui(self.ui.interaction, exc_tuple, show_exc_dialog=show_exc_dialog)

    def get_stack_situation_id(self):
        return str(id(self.stack[self.curindex][0].f_code))

    def user_call(self, frame, argument_list):
        """This method is called when there is the remote possibility
        that we ever need to stop in this function."""
        if self._wait_for_mainpyfile:
            return
        if self.stop_here(frame):
            self.interaction(frame)

    def user_line(self, frame):
        """This function is called when we stop or break at this line."""
        if "__exc_tuple__" in frame.f_locals:
            del frame.f_locals['__exc_tuple__']

        if self._wait_for_mainpyfile:
            if (self.mainpyfile != self.canonic(frame.f_code.co_filename) or frame.f_lineno <= 0):
                return
            self._wait_for_mainpyfile = False
            self.bottom_frame = frame

        if self.get_break(self.canonic(frame.f_code.co_filename), frame.f_lineno):
            self.current_bp = (self.canonic(frame.f_code.co_filename), frame.f_lineno)
        else:
            self.current_bp = None
        self.ui.update_breakpoints()

        self.interaction(frame)

    def user_return(self, frame, return_value):
        """This function is called when a return trap is set here."""
        frame.f_locals['__return__'] = return_value

        if self._wait_for_mainpyfile:
            if (self.mainpyfile != self.canonic(frame.f_code.co_filename) or frame.f_lineno <= 0):
                return
            self._wait_for_mainpyfile = False
            self.bottom_frame = frame

        if "__exc_tuple__" not in frame.f_locals:
            self.interaction(frame)

    def user_exception(self, frame, exc_tuple):
        """This function is called if an exception occurs,
        but only if we are to stop at or just below this level."""
        frame.f_locals['__exc_tuple__'] = exc_tuple

        if not self._wait_for_mainpyfile:
            self.interaction(frame, exc_tuple)

    def _runscript(self, filename):
        # Start with fresh empty copy of globals and locals and tell the script
        # that it's being run as __main__ to avoid scripts being able to access
        # the debugger's namespace.
        globals_ = {"__name__": "__main__", "__file__": filename}
        locals_ = globals_

        # When bdb sets tracing, a number of call and line events happens
        # BEFORE debugger even reaches user's code (and the exact sequence of
        # events depends on python version). So we take special measures to
        # avoid stopping before we reach the main script (see user_line and
        # user_call for details).
        self._wait_for_mainpyfile = 1
        self.mainpyfile = self.canonic(filename)
        if PY3:
            statement = 'exec(compile(open("%s").read(), "%s", "exec"))' % (filename, filename)
        else:
            statement = 'execfile( "%s")' % filename

        # Set up an interrupt handler
        from pudb import set_interrupt_handler
        set_interrupt_handler()

        self.run(statement, globals=globals_, locals=locals_)
