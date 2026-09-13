"""What a count read out of a JSON document is, in one place.

Three readers of the same thing had drifted apart: the site builder refused a number below
zero, the selector that writes the documents the site builder reads did not, and the
renderer refused neither with the same words. A selector that can write a negative count is
a selector that can write a document the build then refuses, with the failure landing on
whoever runs the build rather than on whoever made the selection.

The rule is the whole of this module: a count is a whole number and is never below zero.
``bool`` is excluded because it is an ``int`` in Python and nowhere else, so a document
stating ``true`` where a number belongs would otherwise be read as one.

Each caller keeps its own refusal: this raises nothing of its own and the type that reaches
a reader is the one that names what could not be read, a build, a selection or a record.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

NOT_A_WHOLE_NUMBER = "{key} is {found} where a whole number was expected"
BELOW_ZERO = "{key} is {value}, and a count is never below zero"
"""The two reasons, written once so that three readers give one answer."""


def whole_count(
    document: Mapping[str, object], key: str, refuse: Callable[[str], Exception]
) -> int:
    """The count that key states, or the caller's own refusal saying why it is not one."""
    value = document.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise refuse(NOT_A_WHOLE_NUMBER.format(key=key, found=type(value).__name__))
    if value < 0:
        raise refuse(BELOW_ZERO.format(key=key, value=value))
    return value


__all__ = ["BELOW_ZERO", "NOT_A_WHOLE_NUMBER", "whole_count"]
