"""Shared validation helpers for untrusted symbolic/algebraic expressions.

These helpers are used by any ``src/core`` function that hands a raw,
user-supplied string to SageMath's symbolic parser (``SR``) or evaluates a
matrix expression. They are a defense-in-depth measure only — the sandbox
subprocess (``src/sandbox/executor.py``) with its resource limits remains the
primary isolation boundary — but expression parsing must never be handed
attacker-controlled code without validation first.
"""

import re

# Substrings that must never appear in an expression handed to SageMath's
# symbolic parser or to ``eval``/``exec``. Matched case-insensitively.
DISALLOWED_SUBSTRINGS = (
    "system", "openr", "openw", "load", "os.", "eval", "exec",
    "__import__", "subprocess", "import", "compile", "execfile",
    "getattr", "setattr", "delattr", "globals", "locals", "vars(",
    "input(", "__",
)

# Identifiers (variable/matrix/vector names) must match this pattern.
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")

# Names that must never be used as a matrix/vector/variable identifier,
# even though they match _IDENTIFIER_RE.
_RESERVED_NAMES = frozenset({
    "eval", "exec", "import", "open", "os", "sys", "globals", "locals",
    "getattr", "setattr", "delattr", "vars", "dir", "input", "help",
    "exit", "quit", "license", "copyright", "credits", "compile",
    "breakpoint", "type", "object", "super", "classmethod", "staticmethod",
    "self", "cls", "__builtins__", "__import__",
})


def validate_no_dangerous_substrings(expression: str) -> None:
    """Raise ``ValueError`` if *expression* contains a disallowed substring."""
    lower = expression.lower()
    for bad in DISALLOWED_SUBSTRINGS:
        if bad in lower:
            raise ValueError(f"disallowed token '{bad}' in expression")


def validate_identifier(name: str, kind: str = "name") -> None:
    """Raise ``ValueError`` unless *name* is a safe, non-reserved identifier."""
    if not isinstance(name, str) or not _IDENTIFIER_RE.match(name):
        raise ValueError(
            f"invalid {kind} '{name}': must match ^[A-Za-z_][A-Za-z0-9_]{{0,63}}$"
        )
    if name.startswith("__") or name.lower() in _RESERVED_NAMES:
        raise ValueError(f"invalid {kind} '{name}': reserved word")


# Token whitelist shared by every module that hands a raw symbolic expression
# string to SageMath: numbers, known functions, variable names, operators,
# whitespace. Kept in one place so ``src.core.maxima`` and ``src.core.optimize``
# cannot silently drift apart on which tokens are allowed.
_TOKEN_RE = re.compile(
    r"^(?:"
    r"\d+\.?\d*(?:e[+-]?\d+)?|"
    r"(?:sin|cos|tan|asin|acos|atan|sinh|cosh|tanh|"
    r"exp|log|ln|sqrt|abs|floor|ceil|sign|erf|"
    r"real|imag|conjugate|arctan|arcsin|arccos|arctan2)|"
    r"[a-zA-Z_][a-zA-Z0-9_]*|"
    r"[+\-*/^()\[\],]|"
    r"\s+"
    r")+$",
)


def validate_expression_tokens(expression: str, max_length: int) -> None:
    """Raise ``ValueError`` unless *expression* is a safe, whitelisted-token
    symbolic expression no longer than *max_length* characters.

    Shared by ``src.core.maxima`` and ``src.core.optimize`` so the allowed
    token set and dangerous-substring checks cannot drift between modules.
    """
    if len(expression) > max_length:
        raise ValueError(f"expression too long ({len(expression)} > {max_length})")
    if not expression or not expression.strip():
        raise ValueError("expression must not be empty")
    validate_no_dangerous_substrings(expression)
    if not _TOKEN_RE.match(expression):
        raise ValueError("expression contains invalid characters or tokens")
