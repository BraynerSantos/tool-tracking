"""RFC-4180 CSV writing — port of tool_db2's ``server/csv.js``.

Escapes commas, double quotes, CR and LF by quoting (doubling embedded
quotes); a CRLF terminates every line including the last.
"""

import re

_SPECIAL = re.compile(r'[",\n\r]')


def _esc(v) -> str:
    s = "" if v is None else str(v)
    if _SPECIAL.search(s):
        return '"' + s.replace('"', '""') + '"'
    return s


def to_csv(headers, rows) -> str:
    lines = [",".join(_esc(h) for h in headers)]
    lines.extend(",".join(_esc(c) for c in row) for row in rows)
    return "\r\n".join(lines) + "\r\n"
