"""Convert between uBlock Origin :has-text(...) and AdGuard :contains(...) text rules.

AdGuard for iOS compiles rules through SafariConverterLib; a `##` element-hide rule
that uses :has-text() is misclassified and silently dropped, so cross-engine lists
must emit an explicit `#?#...:contains(...)` procedural twin. AdGuard also chokes on
quotation marks inside the text argument, so the twin must be quote-free.
"""
from __future__ import annotations

import re

_HAS_TEXT = re.compile(r":has-text\((.*?)\)")
_CONTAINS = re.compile(r":contains\((.*?)\)")


def has_text(selector: str) -> bool:
    return ":has-text(" in selector


def has_contains(selector: str) -> bool:
    return ":contains(" in selector


def _strip_quotes(arg: str) -> str:
    arg = arg.strip()
    if len(arg) >= 2 and arg[0] == arg[-1] and arg[0] in "\"'":
        arg = arg[1:-1]
    return arg


def to_contains(selector: str) -> str:
    """uBO :has-text(X) -> AdGuard :contains(X), with surrounding quotes stripped."""
    return _HAS_TEXT.sub(lambda m: f":contains({_strip_quotes(m.group(1))})", selector)


def to_has_text(selector: str) -> str:
    """AdGuard :contains(X) -> uBO :has-text(X), with surrounding quotes stripped."""
    return _CONTAINS.sub(lambda m: f":has-text({_strip_quotes(m.group(1))})", selector)
