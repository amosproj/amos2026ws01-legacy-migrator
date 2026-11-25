"""Normalize package-manager license metadata to SPDX expressions conservatively."""
import re


ALIASES = {
    "apache license 2.0": "Apache-2.0",
    "apache license, version 2.0": "Apache-2.0",
    "apache software license": "Apache-2.0",
    "bsd 2-clause license": "BSD-2-Clause",
    "bsd 3-clause license": "BSD-3-Clause",
    "eclipse public license 2.0": "EPL-2.0",
    "isc license": "ISC",
    "isc license (iscl)": "ISC",
    "mit license": "MIT",
    "mozilla public license 2.0": "MPL-2.0",
    "python software foundation license": "PSF-2.0",
    "the unlicense": "Unlicense",
    "zero-clause bsd": "0BSD",
}

TOKEN = re.compile(r"\(|\)|\bAND\b|\bOR\b|\bWITH\b|[A-Za-z0-9][A-Za-z0-9.+:-]*", re.I)
UNKNOWN = {"", "NOASSERTION", "NONE", "UNKNOWN", "UNLICENSED", "PROPRIETARY"}


def _expression_is_valid(tokens):
    position = 0

    def atom():
        nonlocal position
        if position >= len(tokens):
            raise ValueError
        token = tokens[position]
        if token == "(":
            position += 1
            expression()
            if position >= len(tokens) or tokens[position] != ")":
                raise ValueError
            position += 1
            return
        if token in {"AND", "OR", "WITH", ")"}:
            raise ValueError
        position += 1
        if position < len(tokens) and tokens[position] == "WITH":
            position += 1
            if position >= len(tokens) or tokens[position] in {"AND", "OR", "WITH", "(", ")"}:
                raise ValueError
            position += 1

    def conjunction():
        nonlocal position
        atom()
        while position < len(tokens) and tokens[position] == "AND":
            position += 1
            atom()

    def expression():
        nonlocal position
        conjunction()
        while position < len(tokens) and tokens[position] == "OR":
            position += 1
            conjunction()

    try:
        expression()
        return position == len(tokens)
    except ValueError:
        return False


def normalize_license(value):
    """Return a syntactically valid SPDX expression, or None if ambiguous."""
    if isinstance(value, dict):
        value = value.get("type") or value.get("name")
    if not isinstance(value, str):
        return None
    expression = " ".join(value.strip().split())
    if expression.upper() in UNKNOWN:
        return None
    alias = ALIASES.get(expression.casefold())
    if alias:
        return alias

    # Normalize known phrases inside otherwise valid SPDX expressions.
    for label, identifier in sorted(ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        expression = re.sub(
            r"(?<![A-Za-z0-9.+-])" + re.escape(label) + r"(?![A-Za-z0-9.+-])",
            identifier,
            expression,
            flags=re.I,
        )

    raw_tokens = TOKEN.findall(expression)
    if "".join(raw_tokens).casefold() != re.sub(r"\s+", "", expression).casefold():
        return None
    tokens = [token.upper() if token.upper() in {"AND", "OR", "WITH"} else token for token in raw_tokens]
    if not _expression_is_valid(tokens):
        return None

    # SPDX 2.3 permits the historical '+' notation; emit the current form.
    tokens = [re.sub(r"^(AGPL|GPL|LGPL)-(\d+\.\d+)\+$", r"\1-\2-or-later", token, flags=re.I) for token in tokens]
    if len(tokens) == 1:
        return tokens[0]
    normalized = " ".join(tokens)
    normalized = re.sub(r"\(\s+", "(", normalized)
    return re.sub(r"\s+\)", ")", normalized)
