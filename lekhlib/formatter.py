"""`lekh format`: tidy a Lekh file without changing what it means.

Rules
  * indentation becomes exactly 4 spaces per level (tabs and odd widths are fixed);
  * trailing spaces are removed and the file ends with one newline;
  * at most one blank line in a row, and one blank line before every top-level
    `to` / `record` / `choice` / `ability` / `test` block (comments directly above stay attached);
  * outside text and comments: one space between words, `a, b` after commas,
    no space just inside ( ), no space before `:` or `,`, and `--comment` becomes `-- comment`.

Safety: the tokens of the result are compared with the tokens of the original.
If anything other than spacing would change, the file is left alone.
"""
import re

from .core import tokenize, LekhError

BLOCK_START = re.compile(r"^(share\s+)?(to|record|choice|ability|test)\b")


def string_end(code, i):
    """`code[i]` is an opening quote; return the index of the matching closing quote
    (quotes inside {...} interpolations don't count)."""
    n, j, depth, inner = len(code), i + 1, 0, False
    while j < n:
        ch = code[j]
        if inner:
            if ch == "\\":
                j += 2
                continue
            if ch == '"':
                inner = False
        elif depth > 0:
            if ch == '"':
                inner = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
        else:
            if ch == "\\":
                j += 2
                continue
            if ch == "{":
                if code[j + 1:j + 2] == "{":
                    j += 2
                    continue
                depth = 1
            elif ch == '"':
                return j
        j += 1
    return n


def split_code_comment(line):
    """Return (code, comment) where comment starts at `--` outside a string (or '' if none)."""
    i = 0
    while i < len(line):
        c = line[i]
        if c == '"':
            i = string_end(line, i) + 1
            continue
        if line.startswith("--", i):
            return line[:i], line[i:]
        i += 1
    return line, ""


def tidy_code(code):
    out, i, n = [], 0, len(code)
    while i < n:
        c = code[i]
        if c == '"':
            j = string_end(code, i)
            out.append(code[i:j + 1])
            i = j + 1
            continue
        if c in " \t":
            while i < n and code[i] in " \t":
                i += 1
            if out and i < n and code[i] not in ",:)" and not out[-1].endswith("("):
                out.append(" ")
            continue
        if c == ",":
            while out and out[-1] == " ":
                out.pop()
            out.append(", ")
            i += 1
            while i < n and code[i] in " \t":
                i += 1
            continue
        if c in "+*/":
            while out and out[-1] == " ":
                out.pop()
            if out and not out[-1].endswith("("):
                out.append(" ")
            out.append(c + " ")
            i += 1
            while i < n and code[i] in " \t":
                i += 1
            continue
        if c == "(":
            out.append("(")
            i += 1
            while i < n and code[i] in " \t":
                i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out).rstrip()


def tidy_comment(com):
    if not com:
        return ""
    body = com[2:]
    if body and not body.startswith((" ", "-")):
        body = " " + body
    return "--" + body.rstrip()


def reindent(lines):
    """Map each line's leading whitespace to a nesting level, then use 4 spaces per level."""
    stack, out = [0], []
    for raw in lines:
        expanded = raw.replace("\t", "    ")
        stripped = expanded.lstrip(" ")
        if not stripped:
            out.append((None, ""))
            continue
        width = len(expanded) - len(stripped)
        if stripped.startswith("--") and width > stack[-1]:
            # a comment deeper than the code: keep it at the current level + 1 at most
            out.append((len(stack), stripped))
            continue
        if width > stack[-1]:
            stack.append(width)
        else:
            while len(stack) > 1 and width < stack[-1]:
                stack.pop()
        out.append((len(stack) - 1, stripped))
    return out


def format_source(src):
    lines = src.replace("\r\n", "\n").split("\n")
    leveled = reindent(lines)
    result = []
    for level, text in leveled:
        if level is None:
            if result and result[-1] != "":
                result.append("")
            continue
        code, com = split_code_comment(text)
        code = tidy_code(code)
        com = tidy_comment(com)
        line = code + ((" " + com) if code and com else com)
        if level == 0 and BLOCK_START.match(code) and result and result[-1] != "":
            # keep comments directly above the block attached to it
            k = len(result)
            while k > 0 and result[k - 1].startswith("--"):
                k -= 1
            if k > 0 and result[k - 1] != "":
                result.insert(k, "")
        result.append("    " * level + line)
    while result and result[-1] == "":
        result.pop()
    while result and result[0] == "":
        result.pop(0)
    return "\n".join(result) + "\n"


def token_signature(src, name):
    sig = []
    for t in tokenize(src, name):
        v = t.value
        if isinstance(v, list):
            v = tuple(p if isinstance(p, str) else ("expr", " ".join(p[1].split())) for p in v)
        if t.type in ("INDENT", "DEDENT"):
            v = None
        sig.append((t.type, v))
    return sig


def format_file_text(src, name="<file>"):
    """Return the formatted text, or raise LekhError if the source doesn't parse or the format would change meaning."""
    new = format_source(src)
    if token_signature(src, name) != token_signature(new, name):
        raise LekhError("Formatting stopped", "Tidying this file would change more than spacing, so I left it alone.", None,
                        "Please report this file as a formatter bug.", name)
    return new
