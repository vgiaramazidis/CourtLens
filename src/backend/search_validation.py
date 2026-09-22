"""Lexical checks for AI-generated read-only SPARQL, excluding data and comments."""

import re

# SPARQL strings (including long literals), IRI references, and comments are data,
# not command tokens. Preserve whitespace so adjacent tokens never join together.
_IGNORED = re.compile(
    r'"""(?:\\.|(?!""")[\s\S])*"""'
    r"|'''(?:\\.|(?!''')[\s\S])*'''"
    r'|"(?:\\.|[^"\\])*"'
    r"|'(?:\\.|[^'\\])*'"
    r'|<[^<>"{}|^`\\\x00-\x20]*>'
    r"|\#[^\r\n]*"
)


def code_only(query):
    return _IGNORED.sub(lambda match: " " * len(match[0]), query)


def validate_read_only(raw_query):
    query = re.sub(r"^```(?:sparql)?\s*", "", (raw_query or "").strip(), flags=re.I)
    query = re.sub(r"\s*```$", "", query).strip()
    code = code_only(query)
    body = re.sub(r"^\s*(?:(?:PREFIX\s+(?:[A-Za-z][\w-]*)?:|BASE)\s*)*", "", code, flags=re.I)
    if not re.match(r"^(SELECT|ASK)\b", body, flags=re.I):
        raise ValueError("The query must be a read-only SELECT or ASK query.")
    forbidden = re.search(
        r"(?<![\w?:$-])(LOAD|CLEAR|DROP|CREATE|ADD|MOVE|COPY|INSERT|DELETE|WITH|SERVICE)(?![\w:-])",
        code,
        flags=re.I,
    )
    if forbidden:
        raise ValueError(f"Disallowed SPARQL command: {forbidden[1].upper()}")
    if re.match(r"^SELECT\b", body, flags=re.I) and not re.search(
        r"\bLIMIT\s+\d+\b", code, flags=re.I
    ):
        query += "\nLIMIT 200"
    return query


def unsupported_shot_style(message):
    patterns = [
        ("alley-oops", r"\b(?:alley|allay|ally)[\s-]*oops?\b"),
        ("dunks", r"\bdunk(?:s|ing|ed)?\b|\bslam[\s-]*dunks?\b"),
        ("layups", r"\blay[\s-]*ups?\b"),
        ("floaters", r"\bfloaters?\b"),
        ("hook shots", r"\b(?:jump[\s-]*)?hooks?(?:\s+shots?)?\b"),
        ("tip-ins", r"\btip[\s-]*ins?\b"),
        ("fadeaways", r"\bfade[\s-]*aways?\b"),
        ("bank shots", r"\bbank[\s-]*shots?\b"),
        ("putback dunks", r"\bput[\s-]*backs?\b"),
    ]
    return [label for label, pattern in patterns if re.search(pattern, message, re.I)]


def bounded_editor_query(raw_query):
    """Use the configured dataset only and cap the outer editor result at 200 rows."""
    query = validate_read_only(raw_query)
    code = code_only(query)
    if re.search(r"(?<![\w?:$-])(FROM|DEFINE)(?![\w:-])", code, flags=re.I):
        raise ValueError(
            "Use the configured basketball dataset; FROM and DEFINE are not supported."
        )
    prologue = re.match(r"^\s*(?:(?:PREFIX\s+(?:[A-Za-z][\w-]*)?:|BASE)\s*)*", code, flags=re.I)
    start = prologue.end()
    if re.match(r"ASK\b", code[start:], flags=re.I):
        return query
    # Wrapping the SELECT also bounds queries with only a nested LIMIT.
    return query[:start] + "SELECT * WHERE { {\n" + query[start:] + "\n} } LIMIT 200"
