from urwid.raw_display import Screen as RawScreen

try:
    import curses
except ImportError:
    curses = None

try:
    from urwid.curses_display import Screen as CursesScreen
except ImportError:
    CursesScreen = None


class ThreadsafeScreenMixin(object):
    "A Screen subclass that doesn't crash when running from a non-main thread."

    def signal_init(self):
        "Initialize signal handler, ignoring errors silently."
        try:
            super(ThreadsafeScreenMixin, self).signal_init()
        except ValueError:
            pass

    def signal_restore(self):
        "Restore default signal handler, ignoring errors silently."
        try:
            super(ThreadsafeScreenMixin, self).signal_restore()
        except ValueError:
            pass


class ThreadsafeRawScreen(ThreadsafeScreenMixin, RawScreen):
    pass


class ThreadsafeFixedSizeRawScreen(ThreadsafeScreenMixin, RawScreen):
    def __init__(self, **kwargs):
        self._term_size = kwargs.pop("term_size", None)
        super(ThreadsafeFixedSizeRawScreen, self).__init__(**kwargs)

    def get_cols_rows(self):
        if self._term_size is not None:
            return self._term_size
        else:
            return 80, 24


if curses is not None:
    class ThreadsafeCursesScreen(ThreadsafeScreenMixin, RawScreen):
        pass
