"""Every text pair the design spec names, computed against WCAG, in both themes.

The spec fixes eight colours and says which text sits on which background. Whether that text
can be read is arithmetic over the two values, so it is computed here rather than judged by
eye: a page whose secondary text is a shade too light is a page a reader with ordinary sight
gives up on, and no screenshot shows it.

The values are read out of ``report.css`` and not restated here. That is the point of the
test: the stylesheet is where a colour is changed, and a change that drops a pair under the
threshold fails here rather than reaching a page. A pair that has to move is moved in the
stylesheet and reported, which is what the spec means when it says the values may move but
only together with this test.

The thresholds are WCAG 2.1's: 4.5:1 for body text, 3:1 for text at 24px or heavier than
this page's own 20px heads. The two tints are checked against the paper as well, for the
opposite reason: a tint under 1.2:1 marks nothing a reader can see and is decoration, which
is how the first pair of tints was caught.
"""

from __future__ import annotations

import re

import pytest

from attestql.report.render import STATIC

STYLESHEET = STATIC / "report.css"

LIGHT = re.compile(r":root\s*\{(.*?)\}", re.DOTALL)
DARK = re.compile(r"@media \(prefers-color-scheme: dark\) \{\s*:root\s*\{(.*?)\}", re.DOTALL)
"""The two blocks the tokens are declared in. The light theme is the first ``:root`` of the
file and the dark theme is the one inside the colour-scheme query, which is the whole of how
the stylesheet states a second theme."""

COLOUR = re.compile(r"--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})\s*;")

BODY = 4.5
LARGE = 3.0
"""What WCAG 2.1 asks of text at this page's sizes: 13px and 16px are body text, and the
20px heads and the 28px title are large."""

PERCEPTIBLE = 1.2
"""What a tint has to reach against the paper to be a mark rather than a decoration. The
spec's own tints sit at about 1.3:1, deepened from 1.04:1 for exactly this reason."""

PAIRS: tuple[tuple[str, str, float], ...] = (
    ("ink", "paper", BODY),
    ("ink-2", "paper", BODY),
    ("accent", "paper", BODY),
    ("warn", "paper", BODY),
    ("ink", "gold-tint", BODY),
    ("ink-2", "gold-tint", BODY),
    ("accent", "gold-tint", BODY),
    ("warn", "gold-tint", BODY),
    ("ink", "second-tint", BODY),
    ("ink-2", "second-tint", BODY),
    ("accent", "second-tint", BODY),
    ("warn", "second-tint", BODY),
    ("ink", "rule", BODY),
    ("ink-2", "rule", BODY),
)
"""Every text-on-background pair these pages put on a reader's screen.

The paper carries all four text colours. The two tints carry them too: a tinted row holds
its cells, its label and, where the row is one a probe fired on, a warning word. ``--rule``
is the fill of a chip that states something, and it carries the two ink colours only:
``--warn`` on it is 4.32:1 in light, which is why a warning chip takes the gold tint
instead. That decision is in the stylesheet's own comment beside the rule that makes it."""

TITLE = (("ink", "paper", LARGE),)
"""The 28px title and the 20px heads, which are the page's large text and are ink on paper
like everything else. Stated separately so that the threshold each pair is held to is the
one its size earns."""


def tokens(block: str) -> dict[str, str]:
    """The colour tokens of one block, by name."""
    return dict(COLOUR.findall(block))


def themes() -> dict[str, dict[str, str]]:
    """The two themes as the stylesheet declares them, dark inheriting what it does not restate.

    A dark theme that restated every token would be an inversion, and the spec says it is
    not one: it names eight colours and the rest of the file is shared. So the dark theme
    here is the light one with the eight replaced, which is what a browser computes.
    """
    text = STYLESHEET.read_text(encoding="utf-8")
    light_block = LIGHT.search(text)
    dark_block = DARK.search(text)
    assert light_block is not None, f"{STYLESHEET} declares no :root block"
    assert dark_block is not None, f"{STYLESHEET} declares no dark theme"
    light = tokens(light_block.group(1))
    assert light, "the :root block declares no colour"
    return {"light": light, "dark": {**light, **tokens(dark_block.group(1))}}


THEMES = themes()


def channel(value: int) -> float:
    """One sRGB channel, linearised, as WCAG 2.1 relative luminance defines it."""
    fraction = value / 255
    return fraction / 12.92 if fraction <= 0.03928 else ((fraction + 0.055) / 1.055) ** 2.4


def luminance(colour: str) -> float:
    red, green, blue = (int(colour[index : index + 2], 16) for index in (1, 3, 5))
    return 0.2126 * channel(red) + 0.7152 * channel(green) + 0.0722 * channel(blue)


def contrast(foreground: str, background: str) -> float:
    """The contrast ratio of two colours, WCAG 2.1's own formula."""
    first, second = luminance(foreground), luminance(background)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


@pytest.mark.parametrize("theme", sorted(THEMES), ids=lambda name: name)
@pytest.mark.parametrize(
    ("foreground", "background", "threshold"),
    (*PAIRS, *TITLE),
    ids=lambda value: str(value),
)
def test_every_pair_the_spec_names_is_readable(
    theme: str, foreground: str, background: str, threshold: float
) -> None:
    """One pair, one theme, one number, so a failure names the colour that has to move."""
    values = THEMES[theme]
    for token in (foreground, background):
        assert token in values, f"{STYLESHEET} declares no --{token} for the {theme} theme"

    ratio = contrast(values[foreground], values[background])

    assert ratio >= threshold, (
        f"--{foreground} on --{background} in {theme} is {ratio:.2f}:1 and has to reach "
        f"{threshold}:1"
    )


@pytest.mark.parametrize("theme", sorted(THEMES), ids=lambda name: name)
@pytest.mark.parametrize("tint", ("gold-tint", "second-tint"), ids=lambda name: name)
def test_a_tint_is_a_mark_a_reader_can_see(theme: str, tint: str) -> None:
    """A tint under 1.2:1 against the paper marks nothing and is decoration.

    The other half of the same rule the spec states: the tints are what say which side a row
    came from, and they are always paired with a label and a glyph so that the answer
    survives grayscale. A tint that is invisible fails the first half without failing the
    second, and nothing else here would catch it.
    """
    values = THEMES[theme]

    ratio = contrast(values[tint], values["paper"])

    assert ratio >= PERCEPTIBLE, (
        f"--{tint} against --paper in {theme} is {ratio:.2f}:1, which a reader does not see"
    )


def test_the_two_themes_are_two_decisions_and_not_one_inversion() -> None:
    """Every colour token is restated in dark, and none of them is the light one back.

    The spec's rule about the dark theme, as a property of the file: eight colours declared
    again with eight other values. A theme that inherited one of them would be an inversion
    of the page with a hole in it, and the pair test above would pass over it.
    """
    light, dark = THEMES["light"], THEMES["dark"]
    colours = [name for name in light if name.endswith(("paper", "ink", "ink-2", "rule", "tint"))]

    shared = [name for name in (*colours, "accent", "warn") if light[name] == dark[name]]

    assert not shared, f"the dark theme keeps the light value of {shared}"
