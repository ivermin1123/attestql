"""The one error this command raises when a run cannot start.

Raised by the three modules that read an input, run a question or write a result, and
answered by the facade, which is why it is here and not in one of them: a question file
that cannot be read, an output directory that cannot be made and a backend that will not
say what it is are one kind of answer to a person at a terminal, and ``main`` turns every
one of them into the same message and the same exit status.
"""

from __future__ import annotations


class ToolError(Exception):
    """This tool could not run at all, which is exit status 2 and not a finding."""
