import sys
from linecache import clearcache, getlines

from pudb.py3compat import _next
from pudb.source_view import SourceLine, format_source
from pudb.lowlevel import detect_encoding, format_exception


class SourceCodeProvider(object):
    def get_lines(self, debugger_ui):
        """
        Returns the list of source lines
        """
        raise NotImplementedError()

    def __ne__(self, other):
        return not (self == other)


class NullSourceCodeProvider(SourceCodeProvider):
    def __eq__(self, other):
        return type(self) == type(other)

    def identifier(self):
        return "<no source code>"

    def get_breakpoint_source_identifier(self):
        return None

    def clear_cache(self):
        pass

    def get_lines(self, debugger_ui):
        return [
            SourceLine(debugger_ui, "<no source code available>"),
            SourceLine(debugger_ui, ""),
            SourceLine(debugger_ui, "If this is generated code and you would "
                                    "like the source code to show up here,"),
            SourceLine(debugger_ui, "simply set the attribute _MODULE_SOURCE_CODE "
                                    "in the module in which this function"),
            SourceLine(debugger_ui, "was compiled to a string containing the code."),
        ]


class FileSourceCodeProvider(SourceCodeProvider):
    def __init__(self, debugger, file_name):
        self.file_name = debugger.canonic(file_name)

    def __eq__(self, other):
        return (type(self) == type(other) and self.file_name == other.file_name)

    def identifier(self):
        return self.file_name

    def get_breakpoint_source_identifier(self):
        return self.file_name

    def clear_cache(self):
        clearcache()

    def get_lines(self, debugger_ui):
        if self.file_name == "<string>":
            return [SourceLine(debugger_ui, self.file_name)]

        breakpoints = debugger_ui.debugger.get_file_breaks(self.file_name)[:]
        breakpoints = [lineno for lineno in breakpoints
                        if any(bp.enabled for bp in debugger_ui.debugger.get_breaks(self.file_name, lineno))]
        breakpoints += [i for f, i in debugger_ui.debugger.set_traces if f
            == self.file_name and debugger_ui.debugger.set_traces[f, i]]
        try:
            lines = getlines(self.file_name)
            source_enc, _ = detect_encoding(getattr(iter(lines), _next))

            decoded_lines = []
            for l in lines:
                if hasattr(l, "decode"):
                    decoded_lines.append(l.decode(source_enc))
                else:
                    decoded_lines.append(l)

            return format_source(debugger_ui, decoded_lines, set(breakpoints))
        except:
            debugger_ui.message("Could not load source file '%s':\n\n%s" % (
                self.file_name, "".join(format_exception(sys.exc_info()))),
                title="Source Code Load Error")
            return [SourceLine(debugger_ui, "Error while loading '%s'." % self.file_name)]


class DirectSourceCodeProvider(SourceCodeProvider):
    def __init__(self, func_name, code):
        self.function_name = func_name
        self.code = code

    def __eq__(self, other):
        return (type(self) == type(other) and
                self.function_name == other.function_name and
                self.code is other.code)

    def identifier(self):
        return "<source code of function %s>" % self.function_name

    def get_breakpoint_source_identifier(self):
        return None

    def clear_cache(self):
        pass

    def get_lines(self, debugger_ui):
        lines = self.code.split("\n")

        source_enc, _ = detect_encoding(getattr(iter(lines), _next))

        decoded_lines = []
        for i, l in enumerate(lines):
            if hasattr(l, "decode"):
                l = l.decode(source_enc)

            if i+1 < len(lines):
                l += "\n"

            decoded_lines.append(l)

        return format_source(debugger_ui, decoded_lines, set())
