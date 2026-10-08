"""Tiny helper to replace/insert methods inside a class of lekhlib/core.py."""
import re, sys

PATH = "lekhlib/core.py"


def load():
    return open(PATH).read()


def save(s):
    open(PATH, "w").write(s)


def class_span(s, cls):
    m = re.search(r"^class %s\b.*?:\n" % re.escape(cls), s, re.M)
    if not m:
        raise SystemExit("class not found: " + cls)
    start = m.end()
    n = re.search(r"^\S", s[start:], re.M)
    end = start + n.start() if n else len(s)
    return start, end


def replace_method(s, cls, name, code):
    a, b = class_span(s, cls)
    body = s[a:b]
    m = re.search(r"^    def %s\(.*?(?=^    def |^    [A-Z_]+ = |\Z)" % re.escape(name), body, re.M | re.S)
    if not m:
        raise SystemExit("method not found: %s.%s" % (cls, name))
    code = code.rstrip("\n") + "\n\n"
    return s[:a] + body[:m.start()] + code + body[m.end():] + s[b:]


def add_methods(s, cls, code):
    a, b = class_span(s, cls)
    body = s[a:b].rstrip("\n") + "\n\n" + code.rstrip("\n") + "\n\n\n"
    return s[:a] + body + s[b:]


def replace_text(s, old, new, count=1):
    if old not in s:
        raise SystemExit("text not found:\n" + old[:300])
    return s.replace(old, new, count)
