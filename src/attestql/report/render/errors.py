"""The one refusal a report makes, shared by the four modules below it.

A directory that is not an audit's, a document that does not hold what its format states and
an output directory that is not this render's own are one kind of answer to a person at a
terminal, and the command turns every one of them into the same message and exit status.
"""

from __future__ import annotations


class ReportRefused(Exception):
    """This directory cannot be rendered, and the message says what was looked for.

    The one error this command has. A directory that is not an audit's, a file that is not
    the JSON its name says, and a document that does not hold what its format states are
    all the same answer to a reader: nothing was rendered, and here is why.
    """
