#!/usr/bin/env python3
"""A small HTML sanity checker for the built website (no extra packages needed).

    python3 tools/check_html.py site/dist

For every .html file it checks: <!doctype html>, <html lang>, <meta charset>, a viewport,
a <title>, exactly one <h1>, every opened tag closed in the right order, no stray closing
tags, no duplicate ids, alt text on images, and no links with an empty href.
Exit code 1 when anything is wrong.
"""
import os, sys
from html.parser import HTMLParser

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
# end tags HTML lets you leave out; the site never does, but don't complain about them
OPTIONAL_END = {"p", "li", "dt", "dd", "tr", "td", "th", "thead", "tbody", "option"}


class Checker(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.problems, self.ids = [], [], {}
        self.counts = {}
        self.attrs_seen = {}

    def where(self):
        return "line %d" % self.getpos()[0]

    def note(self, tag, attrs):
        self.counts[tag] = self.counts.get(tag, 0) + 1
        a = dict(attrs)
        if "id" in a:
            if a["id"] in self.ids:
                self.problems.append("%s: duplicate id %r" % (self.where(), a["id"]))
            self.ids[a["id"]] = True
        if tag == "img" and "alt" not in a:
            self.problems.append("%s: <img> without alt text" % self.where())
        if tag == "a" and "href" in a and not (a["href"] or "").strip():
            self.problems.append("%s: <a> with an empty href" % self.where())
        if tag == "html":
            self.attrs_seen["lang"] = a.get("lang")
        if tag == "meta" and "charset" in a:
            self.attrs_seen["charset"] = True
        if tag == "meta" and a.get("name") == "viewport":
            self.attrs_seen["viewport"] = True

    def handle_starttag(self, tag, attrs):
        self.note(tag, attrs)
        if tag not in VOID:
            self.stack.append((tag, self.getpos()[0]))

    def handle_startendtag(self, tag, attrs):
        self.note(tag, attrs)

    def handle_endtag(self, tag):
        if tag in VOID:
            self.problems.append("%s: </%s> is a void element and has no end tag" % (self.where(), tag))
            return
        if not self.stack:
            self.problems.append("%s: stray </%s>" % (self.where(), tag))
            return
        if self.stack[-1][0] == tag:
            self.stack.pop()
            return
        # allow leaving out optional end tags before closing an outer element
        names = [t for t, _ in self.stack]
        if tag in names:
            while self.stack and self.stack[-1][0] != tag:
                t, line = self.stack.pop()
                if t not in OPTIONAL_END:
                    self.problems.append("line %d: <%s> is never closed (closed by </%s> at %s)" % (line, t, tag, self.where()))
            self.stack.pop()
        else:
            self.problems.append("%s: </%s> doesn't match the open <%s>" % (self.where(), tag, self.stack[-1][0]))


def check_file(path):
    text = open(path, encoding="utf-8").read()
    c = Checker()
    c.feed(text)
    c.close()
    problems = list(c.problems)
    for t, line in c.stack:
        if t not in OPTIONAL_END:
            problems.append("line %d: <%s> is never closed" % (line, t))
    if not text.lstrip().lower().startswith("<!doctype html>"):
        problems.append("doesn't start with <!doctype html>")
    if not c.attrs_seen.get("lang"):
        problems.append("<html> has no lang")
    if not c.attrs_seen.get("charset"):
        problems.append("no <meta charset>")
    if not c.attrs_seen.get("viewport"):
        problems.append("no viewport <meta>")
    if c.counts.get("title", 0) != 1:
        problems.append("should have exactly one <title> (has %d)" % c.counts.get("title", 0))
    if c.counts.get("h1", 0) != 1:
        problems.append("should have exactly one <h1> (has %d)" % c.counts.get("h1", 0))
    return problems


def main(folder):
    pages = sorted(os.path.join(d, f) for d, _, fs in os.walk(folder) for f in fs if f.endswith(".html"))
    bad = 0
    for p in pages:
        for problem in check_file(p):
            bad += 1
            print("  %s: %s" % (os.path.relpath(p, folder), problem))
    if not pages:
        print("No .html files in %s." % folder)
        return 1
    if bad:
        print("%d HTML problem(s) in %d pages." % (bad, len(pages)))
        return 1
    print("HTML looks fine: %d pages checked." % len(pages))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "site/dist"))
