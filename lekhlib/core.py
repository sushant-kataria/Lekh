#!/usr/bin/env python3
"""
Lekh (लेख, "a piece of writing") - a programming language that reads like plain English,
with Rust-style safety (immutable by default, no null, ownership) but a gentle learning curve.

Prototype tree-walking interpreter.  Python 3.8+, no dependencies.

    python3 lekh.py program.lekh          run a program
    python3 lekh.py --check program.lekh  only run the safety checker
    python3 lekh.py                       start the interactive REPL
"""

import sys, os, re, math, random, difflib

VERSION = "0.2.0"
EXT = ".lekh"

# =====================================================================================
#  Errors: every problem is a LekhError with a title, a plain-English message and a fix
# =====================================================================================
SYNTAX = "I couldn't understand this line"
NAME_P = "Unknown name"
CHANGE_P = "This can't be changed"
TYPE_P = "Type mix-up"
OWN_P = "Ownership rule"
MISSING_P = "Possibly missing value"
CASE_P = "Unhandled case"
ABILITY_P = "Ability not met"
RANGE_P = "Out of range"
MATH_P = "Math problem"
CALL_P = "Wrong inputs for a task"
FAIL_P = "The program stopped on purpose"
UNHANDLED_P = "Unhandled problem"
LIMIT_P = "Too much recursion"
FILE_P = "File problem"
PLACE_P = "Wrong place"
TEST_P = "Test failed"
INTERNAL_P = "Something went wrong inside Lekh"


class LekhError(Exception):
    def __init__(self, title, message, line=None, fix=None, file=None):
        Exception.__init__(self, message)
        self.title, self.message, self.line, self.fix, self.file = title, message, line, fix, file


SOURCES = {}  # file -> list of source lines (for showing the offending line)


def display_path(p):
    if not p or p.startswith("<"):
        return p or "<program>"
    try:
        r = os.path.relpath(p)
        return p if r.startswith("..") else r
    except ValueError:
        return p


def format_error(e):
    out = ["", "-- Lekh: %s %s" % (e.title, "-" * max(4, 60 - len(e.title)))]
    if e.line:
        out.append("In %s, line %d:" % (display_path(e.file), e.line))
        lines = SOURCES.get(e.file)
        if lines and 0 < e.line <= len(lines):
            out.append("")
            out.append("    %d | %s" % (e.line, lines[e.line - 1].rstrip()))
    out.append("")
    out.append(e.message)
    if e.fix:
        out.append("")
        out.append("How to fix:")
        for l in e.fix.split("\n"):
            out.append("    " + l)
    out.append("")
    return "\n".join(out)


def suggest(word, options):
    m = difflib.get_close_matches(word, [o for o in options if o != word], n=1, cutoff=0.6)
    return m[0] if m else None


# Words people bring from other languages, and what Lekh says instead.
FOREIGN = {
    "print": "say", "println": "say", "echo": "say", "puts": "say", "printf": "say",
    "console": "say", "return": "give back", "def": "to", "fn": "to", "func": "to",
    "function": "to", "var": "let changeable", "const": "let", "mut": "changeable",
    "mutable": "changeable", "elif": "otherwise if", "elsif": "otherwise if",
    "break": "stop", "continue": "skip", "null": "nothing", "None": "nothing", "nil": "nothing",
    "undefined": "nothing", "True": "true", "False": "false", "input": "ask", "struct": "record",
    "class": "record", "enum": "choice", "match": "when", "switch": "when", "import": "use",
    "require": "use", "include": "use", "Some": "some", "Ok": "ok", "Err": "problem",
    "foreach": "for each", "len": "length of", "loop": "repeat ... times / while",
    "then": "a ':' at the end of the line", "end": "(nothing - blocks end when the indentation ends)",
}


def foreign_hint(word):
    if word in FOREIGN:
        return "Lekh says `%s` instead of `%s`." % (FOREIGN[word], word)
    return None


# =====================================================================================
#  Lexer
# =====================================================================================
KEYWORDS = set("""let be changeable change to increase decrease say ask if otherwise for in from
repeat while stop skip give run with of and or not is at true false nothing some ok problem
try else when record choice add remove empty list map copy lend use as mod fail
constant share ability div expect""".split())

BAD_SYMBOLS = {
    "==": ("Lekh compares with the word `is`.", "if x is 5:"),
    "!=": ("Lekh says `is not` instead of `!=`.", "if x is not 5:"),
    "=": ("Lekh doesn't use '='.",
          "To create a variable:  let x be 5\nTo change one:        change x to 5\nTo compare:           if x is 5:"),
    "&&": ("Lekh says `and` instead of `&&`.", "if a and b:"),
    "||": ("Lekh says `or` instead of `||`.", "if a or b:"),
    "!": ("Lekh says `not` instead of `!`.", "if not done:"),
    "[": ("Lekh writes lists with words, not square brackets.",
          "let numbers be list of 1, 2, 3\nlet second be item 2 of numbers"),
    "]": ("Lekh writes lists with words, not square brackets.", "let numbers be list of 1, 2, 3"),
    "{": ("Curly braces are only used inside text, like \"Hi {name}\".",
          "Maps are written:  let ages be map of \"Asha\" to 30, \"Ravi\" to 25"),
    "}": ("Curly braces are only used inside text, like \"Hi {name}\".", None),
    ";": ("Lekh doesn't need semicolons - just put one statement on each line.", None),
    "%": ("Lekh says `mod` for the remainder.", "if n mod 2 is 0:"),
    ".": ("Lekh reads a field with 's, like English.", "account's balance"),
}


class Tok:
    __slots__ = ("type", "value", "line", "col")

    def __init__(self, type, value, line, col):
        self.type, self.value, self.line, self.col = type, value, line, col

    def __repr__(self):
        return "Tok(%s,%r,%d)" % (self.type, self.value, self.line)


def describe_tok(t):
    if t.type == "NEWLINE":
        return "the end of the line"
    if t.type == "EOF":
        return "the end of the file"
    if t.type in ("INDENT", "DEDENT"):
        return "a change in indentation"
    if t.type == "STRING":
        return "some text in quotes"
    if t.type == "NUMBER":
        return "the number %s" % t.value
    if t.type == "POSS":
        return "'s"
    return "'%s'" % t.value


def tokenize(src, file, first_line=1, inline=False):
    toks = []
    indents = [0]
    depth = 0  # open parentheses

    def err(msg, ln, fix=None):
        raise LekhError(SYNTAX, msg, ln, fix, file)

    for idx, raw in enumerate(src.split("\n")):
        ln = first_line + idx
        line = raw.expandtabs(4).rstrip()
        stripped = line.lstrip(" ")
        if depth == 0:
            if not stripped or stripped.startswith("--"):
                continue
            ind = len(line) - len(stripped)
            if not inline:
                if ind > indents[-1]:
                    indents.append(ind)
                    toks.append(Tok("INDENT", ind, ln, 1))
                else:
                    while ind < indents[-1]:
                        indents.pop()
                        toks.append(Tok("DEDENT", None, ln, 1))
                    if ind != indents[-1]:
                        err("This line's indentation doesn't line up with any block above it.", ln,
                            "Use 4 spaces for each level, and line up lines that belong together.")
            pos = ind
        else:
            pos = 0
        n = len(line)
        while pos < n:
            c = line[pos]
            if c == " ":
                pos += 1
                continue
            if line.startswith("--", pos):
                break
            col = pos + 1
            if c.isdigit():
                j = pos
                while j < n and (line[j].isdigit() or line[j] == "_"):
                    j += 1
                is_float = False
                if j + 1 < n and line[j] == "." and line[j + 1].isdigit():
                    is_float = True
                    j += 1
                    while j < n and line[j].isdigit():
                        j += 1
                text = line[pos:j].replace("_", "")
                toks.append(Tok("NUMBER", float(text) if is_float else int(text), ln, col))
                pos = j
            elif c == '"':
                pos += 1
                parts, buf = [], []
                while True:
                    if pos >= n:
                        err("This text is missing its closing quote (\").", ln,
                            "Text must start and end on the same line, like: say \"Hello\"")
                    ch = line[pos]
                    if ch == "\\":
                        nx = line[pos + 1] if pos + 1 < n else ""
                        buf.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\", "{": "{", "}": "}"}.get(nx, "\\" + nx))
                        pos += 2
                    elif ch == '"':
                        pos += 1
                        break
                    elif ch == "{":
                        if line[pos + 1:pos + 2] == "{":
                            buf.append("{")
                            pos += 2
                            continue
                        lit = re.match(r"\{[0-9]*,?[0-9]*\}", line[pos:])
                        if lit and lit.group(0) != "{}":
                            # {3} or {2,5} is kept as written (handy for patterns like "[0-9]{4}")
                            buf.append(lit.group(0))
                            pos += len(lit.group(0))
                            continue
                        if buf:
                            parts.append("".join(buf))
                            buf = []
                        j, d, inq = pos + 1, 1, False
                        while j < n:
                            cj = line[j]
                            if inq:
                                if cj == "\\":
                                    j += 2
                                    continue
                                if cj == '"':
                                    inq = False
                            elif cj == '"':
                                inq = True
                            elif cj == "{":
                                d += 1
                            elif cj == "}":
                                d -= 1
                                if d == 0:
                                    break
                            j += 1
                        if j >= n:
                            err("A '{' inside this text is never closed with '}'.", ln,
                                "Write {name} to put a value inside text, or {{ for a real brace.")
                        code = line[pos + 1:j]
                        if not code.strip():
                            err("There's an empty {} inside this text.", ln,
                                "Put a value inside, like \"Hi {name}\", or write {{}} for real braces.")
                        parts.append(("expr", code, ln))
                        pos = j + 1
                    elif ch == "}":
                        buf.append("}")
                        pos += 2 if line[pos + 1:pos + 2] == "}" else 1
                    else:
                        buf.append(ch)
                        pos += 1
                if buf or not parts:
                    parts.append("".join(buf))
                toks.append(Tok("STRING", parts, ln, col))
            elif c.isalpha() or c == "_":
                j = pos
                while j < n and (line[j].isalnum() or line[j] == "_"):
                    j += 1
                w = line[pos:j]
                toks.append(Tok("KW" if w in KEYWORDS else "NAME", w, ln, col))
                pos = j
            elif c == "'":
                prev = toks[-1] if toks else None
                if (prev and (prev.type == "NAME" or (prev.type == "OP" and prev.value == ")"))
                        and line[pos + 1:pos + 2] == "s"
                        and not (pos + 2 < n and (line[pos + 2].isalnum() or line[pos + 2] == "_"))):
                    toks.append(Tok("POSS", "'s", ln, col))
                    pos += 2
                else:
                    err("Text goes inside double quotes in Lekh.", ln,
                        "say \"hello\"   (an apostrophe is only used for fields, like account's balance)")
            else:
                two = line[pos:pos + 2]
                if two in (">=", "<="):
                    toks.append(Tok("OP", two, ln, col))
                    pos += 2
                    continue
                if two in BAD_SYMBOLS:
                    m, f = BAD_SYMBOLS[two]
                    err(m, ln, f)
                if c in "+-*/(),:<>":
                    if c == "(":
                        depth += 1
                    elif c == ")":
                        depth -= 1
                        if depth < 0:
                            err("There's a ')' without a matching '('.", ln)
                    toks.append(Tok("OP", c, ln, col))
                    pos += 1
                elif c in BAD_SYMBOLS:
                    m, f = BAD_SYMBOLS[c]
                    err(m, ln, f)
                else:
                    err("I don't know what the symbol '%s' means." % c, ln,
                        "Lekh mostly uses words. Symbols allowed: + - * / ( ) , : > < >= <=")
        if depth == 0:
            toks.append(Tok("NEWLINE", None, ln, n + 1))
    if depth > 0:
        err("A '(' was opened but never closed with ')'.", first_line + len(src.split("\n")) - 1)
    last = toks[-1].line if toks else first_line
    while len(indents) > 1:
        indents.pop()
        toks.append(Tok("DEDENT", None, last, 1))
    toks.append(Tok("EOF", None, last, 1))
    return toks


# =====================================================================================
#  Syntax tree
# =====================================================================================
class Node:
    def __init__(self, kind, line, file, **kw):
        self.kind, self.line, self.file = kind, line, file
        self.__dict__.update(kw)

    def __repr__(self):
        return "Node(%s)" % self.kind


def iter_names(x):
    """Yield every Name node inside an expression."""
    if isinstance(x, Node):
        if x.kind == "Name":
            yield x
        for k, v in x.__dict__.items():
            if k not in ("kind", "line", "file"):
                yield from iter_names(v)
    elif isinstance(x, (list, tuple)):
        for v in x:
            yield from iter_names(v)


# words that act like operators after a value; they never start an index expression
CONTEXT_OPS = {"contains", "starts", "ends", "does", "times", "gives", "by", "than"}
END_OF_EXPR = {"NEWLINE", "EOF", "DEDENT", "INDENT"}


# =====================================================================================
#  Parser
# =====================================================================================
class Parser:
    def __init__(self, toks, file, types=(), fields=None):
        self.toks, self.i, self.file = toks, 0, file
        self.types = set(types) | {"CommandOutput", "Response"}
        self.fields = dict(fields) if fields is not None else {}
        self.fields.setdefault("Response", ["status", "body", "headers"])
        self.fields.setdefault("CommandOutput", ["output", "errors", "code"])
        self.no_of = False

    # ---------- helpers
    def peek(self, k=0):
        j = self.i + k
        return self.toks[j] if j < len(self.toks) else self.toks[-1]

    def advance(self):
        t = self.toks[self.i]
        if self.i < len(self.toks) - 1:
            self.i += 1
        return t

    def kw(self, w, k=0):
        t = self.peek(k)
        return t.type == "KW" and t.value == w

    def word(self, w, k=0):
        t = self.peek(k)
        return t.type == "NAME" and t.value == w

    def op(self, o, k=0):
        t = self.peek(k)
        return t.type == "OP" and t.value == o

    def accept_kw(self, w):
        return self.advance() if self.kw(w) else None

    def accept_word(self, w):
        return self.advance() if self.word(w) else None

    def accept_op(self, o):
        return self.advance() if self.op(o) else None

    def N(self, kind, tok, **kw):
        return Node(kind, tok.line, self.file, **kw)

    def fail(self, msg, tok=None, fix=None):
        tok = tok or self.peek()
        raise LekhError(SYNTAX, msg, tok.line, fix, self.file)

    def expect_kw(self, w, msg, fix=None):
        if not self.kw(w):
            self.fail("%s (I found %s instead.)" % (msg, describe_tok(self.peek())), fix=fix)
        return self.advance()

    def expect_word(self, w, msg, fix=None):
        if not self.word(w):
            self.fail("%s (I found %s instead.)" % (msg, describe_tok(self.peek())), fix=fix)
        return self.advance()

    def expect_colon(self, what, example):
        if not self.op(":"):
            self.fail("This %s line should end with ':' to start its block. (I found %s instead.)"
                      % (what, describe_tok(self.peek())), fix=example)
        self.advance()

    def name(self, what):
        t = self.peek()
        if t.type == "NAME":
            self.advance()
            return t.value
        if t.type == "KW":
            self.fail("'%s' is a special word in Lekh, so it can't be used as %s." % (t.value, what),
                      fix="Pick another name, like 'my_%s' or '%s_value'." % (t.value, t.value))
        self.fail("I expected %s here, but found %s." % (what, describe_tok(t)))

    def end_stmt(self, first=None):
        t = self.peek()
        if t.type == "NEWLINE":
            self.advance()
            return
        if t.type in ("EOF", "DEDENT"):
            return
        if self.i > 0 and self.toks[self.i - 1].type == "DEDENT":
            return  # the statement ended with an indented block (e.g. a multi-line `given` task)
        fix = None
        if first is not None and first.type == "NAME":
            fix = foreign_hint(first.value)
        if fix is None and t.type == "NAME" and foreign_hint(t.value):
            fix = foreign_hint(t.value)
        if fix is None:
            fix = ("Each line holds one statement. If you meant to combine values, use an operator "
                   "(+, and, or), separate inputs with commas, or call a task with `with`.")
        self.fail("I didn't expect %s here." % describe_tok(t), t, fix)

    def ends_expr(self, k=0):
        t = self.peek(k)
        if t.type in END_OF_EXPR:
            return True
        if t.type == "OP" and t.value in (":", ")", ","):
            return True
        if t.type == "KW" and t.value in ("and", "or", "to", "from", "in", "be"):
            return True
        return False

    def starts_value(self, t):
        if t.type in ("NUMBER", "STRING"):
            return True
        if t.type == "NAME":
            return t.value not in CONTEXT_OPS
        if t.type == "OP":
            return t.value == "("
        if t.type == "KW":
            return t.value in ("true", "false", "nothing", "list", "map", "empty", "copy", "run", "some", "ok", "problem")
        return False

    # ---------- program & blocks
    def program(self):
        stmts = []
        while self.peek().type != "EOF":
            if self.peek().type == "NEWLINE":
                self.advance()
                continue
            stmts.append(self.statement())
        return stmts

    def block(self, what="block"):
        """Called right after the ':'"""
        if self.peek().type == "NEWLINE":
            self.advance()
            if self.peek().type != "INDENT":
                self.fail("The line after a ':' should be indented (4 spaces) to show what belongs inside the %s." % what,
                          fix="if x is 5:\n    say \"five\"")
            self.advance()
            stmts = []
            while self.peek().type not in ("DEDENT", "EOF"):
                if self.peek().type == "NEWLINE":
                    self.advance()
                    continue
                stmts.append(self.statement())
            if self.peek().type == "DEDENT":
                self.advance()
            return stmts
        t = self.peek()
        if t.type == "KW" and t.value in ("if", "for", "while", "repeat", "when", "to", "record", "choice"):
            self.fail("A '%s' can't go on the same line after ':'. Put it on its own indented line." % t.value)
        return [self.statement()]

    # ---------- statements
    def statement(self):
        t = self.peek()
        if t.type == "INDENT":
            self.fail("This line is indented, but the line above it doesn't start a block.",
                      fix="Only indent after a line that ends with ':' (like if, for each, to, when).")
        if t.type == "KW":
            m = getattr(self, "st_" + t.value, None)
            if m:
                return m()
            if t.value == "otherwise":
                self.fail("'otherwise' must come right after an 'if' block (or as the last case inside 'when').",
                          fix="Line it up exactly with its 'if':\nif x is 1:\n    say \"one\"\notherwise:\n    say \"not one\"")
            if t.value == "else":
                self.fail("Lekh says `otherwise` instead of `else`.", fix="otherwise:")
        if t.type == "NAME":
            v, nxt = t.value, self.peek(1)
            if v == "test" and nxt.type == "STRING":
                return self.st_test()
            if v == "send" and self.starts_value(nxt) and not (nxt.type == "KW"):
                return self.st_send()
            if v == "send" and nxt.type == "KW" and nxt.value in ("true", "false", "nothing", "list", "map", "empty", "copy", "some", "ok", "problem"):
                return self.st_send()
            if v == "close" and nxt.type == "NAME" and self.peek(2).type in ("NEWLINE", "EOF"):
                self.advance()
                e = self.expr()
                self.end_stmt()
                return self.N("Close", t, expr=e)
            if v == "wait" and (nxt.type in ("NUMBER", "NAME") or self.op("(", 1)) and not self.kw("for", 1):
                self.advance()
                e = self.additive()
                if not (self.accept_word("seconds") or self.accept_word("second")):
                    self.fail("Write how long to wait in seconds, like:  wait 0.5 seconds")
                self.end_stmt()
                return self.N("Sleep", t, expr=e)
            if nxt.type == "NAME" and nxt.value == "can" and self.peek(2).type == "NAME":
                self.advance(); self.advance()
                ab = self.advance().value
                self.end_stmt()
                return self.N("Can", t, tname=v, ability=ab)
            if v in FOREIGN:
                if not (nxt.type == "KW" and nxt.value in ("with", "of", "is", "be")) and nxt.type != "POSS":
                    self.fail("I don't know the word `%s`." % v, fix=foreign_hint(v))
        e = self.expr()
        self.end_stmt(t)
        if e.kind == "Field" and not any(e.name in fs for fs in self.fields.values()):
            # `counter's reset` on its own line calls the method (it has no inputs)
            e = Node("MethodCall", e.line, e.file, obj=e.obj, name=e.name, args=[])
        return self.N("ExprStmt", t, expr=e)

    def st_let(self, const=False):
        t = self.advance()
        ch = False if const else bool(self.accept_kw("changeable"))
        if self.op("("):
            self.advance()
            names = [self.name("a name")]
            while self.accept_op(","):
                names.append(self.name("a name"))
            if not self.accept_op(")"):
                self.fail("Close the list of names with ')'.", fix="let (quotient, remainder) be divide with 7, 2")
            self.expect_kw("be", "After the names write `be` and the value.", "let (a, b) be ...")
            e = self.expr()
            self.end_stmt()
            return self.N("LetTuple", t, names=names, changeable=ch, expr=e)
        nm = self.name("a name for the new %s" % ("constant" if const else "variable"))
        typ = None
        if self.accept_kw("as"):
            typ = self.type_()
        if not self.kw("be"):
            self.fail("After `%s %s` write `be` and then the value. (I found %s.)" % ("constant" if const else "let", nm, describe_tok(self.peek())),
                      fix="%s %s be ..." % ("constant" if const else "let", nm))
        self.advance()
        e = self.expr()
        self.end_stmt()
        return self.N("Let", t, name=nm, changeable=ch, type=typ, expr=e, const=const, shared=False)

    def st_constant(self):
        return self.st_let(const=True)

    def st_share(self):
        t = self.advance()
        nt = self.peek()
        if not (nt.type == "KW" and nt.value in ("to", "record", "choice", "ability", "constant", "let")):
            self.fail("`share` goes in front of a task, record, choice, ability or constant to make it public.",
                      fix="share to area shape as Shape gives number:")
        node = self.statement()
        if node.kind == "Let" and node.changeable:
            self.fail("Only unchangeable values can be shared with other modules.", t)
        node.shared = True
        return node

    def target(self):
        t = self.peek()
        if self.word("item") and self.starts_value(self.peek(1)):
            self.advance()
            old = self.no_of
            self.no_of = True
            idx = self.additive()
            self.no_of = old
            self.expect_kw("of", "After `item <number>` write `of` and the list.", "item 2 of cart")
            obj = self.target()
            return self.N("Index", t, obj=obj, index=idx)
        if self.accept_op("("):
            node = self.target()
            if not self.accept_op(")"):
                self.fail("I expected ')' here.")
        elif self.word("my") and getattr(self, "in_method", False) and self.peek(1).type == "NAME":
            self.advance()
            node = self.N("Field", t, obj=self.N("Name", t, name="me"), name=self.name("a field name"))
        else:
            node = self.N("Name", t, name=self.name("the name of the variable to change"))
        while True:
            if self.peek().type == "POSS":
                p = self.advance()
                node = self.N("Field", p, obj=node, name=self.name("a field name after 's"))
            elif self.kw("at") and not self.word("the", 1):
                p = self.advance()
                node = self.N("Key", p, obj=node, key=self.key())
            else:
                return node

    def st_change(self):
        t = self.advance()
        tg = self.target()
        self.expect_kw("to", "After `change %s` write `to` and the new value." % self.tdesc(tg),
                       "change %s to ..." % self.tdesc(tg))
        e = self.expr()
        self.end_stmt()
        return self.N("Change", t, target=tg, expr=e)

    def tdesc(self, tg):
        return target_desc(tg)

    def _incdec(self, sign):
        t = self.advance()
        tg = self.target()
        if self.accept_word("by"):
            e = self.expr()
        else:
            e = self.N("Num", t, value=1)
        self.end_stmt()
        return self.N("Increase", t, target=tg, expr=e, sign=sign)

    def st_increase(self):
        return self._incdec(1)

    def st_decrease(self):
        return self._incdec(-1)

    def st_add(self):
        t = self.advance()
        e = self.expr()
        self.expect_kw("to", "After `add <value>` write `to` and the list.", "add \"milk\" to cart")
        tg = self.target()
        self.end_stmt()
        return self.N("Add", t, expr=e, target=tg)

    def st_remove(self):
        t = self.advance()
        by_pos = False
        if self.word("item") and self.starts_value(self.peek(1)):
            self.advance()
            by_pos = True
        e = self.expr()
        self.expect_kw("from", "After `remove <value>` write `from` and the list or map.", "remove \"milk\" from cart")
        tg = self.target()
        self.end_stmt()
        return self.N("Remove", t, expr=e, target=tg, by_pos=by_pos)

    def st_say(self):
        t = self.advance()
        e = None if self.peek().type in END_OF_EXPR else self.expr()
        self.end_stmt(t)
        return self.N("Say", t, expr=e)

    def st_if(self):
        t = self.advance()
        branches = []
        cond = self.expr()
        self.expect_colon("if", "if %s:" % "age is at least 18")
        branches.append((cond, self.block("if")))
        other = None
        while self.kw("otherwise"):
            if self.kw("if", 1):
                self.advance()
                self.advance()
                c = self.expr()
                self.expect_colon("otherwise if", "otherwise if age is at least 13:")
                branches.append((c, self.block("otherwise if")))
            else:
                self.advance()
                self.expect_colon("otherwise", "otherwise:")
                other = self.block("otherwise")
                break
        return self.N("If", t, branches=branches, other=other)

    def same_time(self):
        if self.kw("at") and self.word("the", 1) and self.word("same", 2) and self.word("time", 3):
            for _ in range(4):
                self.advance()
            return True
        return False

    def st_for(self):
        t = self.advance()
        self.expect_word("each", "Lekh loops are written `for each`.", "for each item in cart:")
        ch = bool(self.accept_kw("changeable"))
        tvars = None
        var = var2 = None
        if self.accept_op("("):
            tvars = [self.name("a name")]
            while self.accept_op(","):
                tvars.append(self.name("a name"))
            if not self.accept_op(")"):
                self.fail("Close the names with ')'.", fix="for each (name, age) in people:")
            if ch:
                self.fail("A loop that unpacks pairs can't be changeable.")
        else:
            var = self.name("a name for each item")
            if self.peek().type == "OP" and self.peek().value == ",":
                self.fail("Join two loop names with `and`, not a comma.",
                          fix="for each %s and position in ...:     (lists: item and its position)\n"
                              "for each key and value in ages:     (maps)\n"
                              "for each (a, b) in pairs:           (groups)" % var)
            if self.accept_kw("and"):
                var2 = self.name("a second name (the position, or the value of a map)")
        if self.accept_kw("in"):
            it = self.expr()
            par = self.same_time()
            self.expect_colon("for each", "for each %s in ...:" % (var or "item"))
            return self.N("ForEach", t, var=var, var2=var2, tvars=tvars, changeable=ch, iterable=it,
                          parallel=par, body=self.block("loop"))
        if self.accept_kw("from"):
            if ch or var2 or tvars:
                self.fail("A counting loop (from ... to ...) has just one name and can't be changeable.")
            a = self.expr()
            self.expect_kw("to", "A counting loop needs `to`.", "for each n from 1 to 10:")
            b = self.expr()
            step = self.additive() if self.accept_word("by") else None
            par = self.same_time()
            self.expect_colon("for each", "for each %s from 1 to 10:" % var)
            return self.N("ForRange", t, var=var, start=a, end=b, step=step, parallel=par, body=self.block("loop"))
        self.fail("After `for each %s` write `in <list>` or `from <number> to <number>`." % var,
                  fix="for each %s in cart:\nfor each %s from 1 to 10:" % (var, var))

    def st_at(self):
        t = self.advance()
        if self.word("the") and self.word("end", 1):
            self.advance(); self.advance()
            self.expect_colon("at the end", "at the end:\n    say \"cleaning up\"")
            return self.N("Defer", t, body=self.block("cleanup"))
        if self.word("the") and self.word("same", 1) and self.word("time", 2):
            self.advance(); self.advance(); self.advance()
            self.expect_colon("at the same time", "at the same time:\n    fetch with url1\n    fetch with url2")
            return self.N("Parallel", t, body=self.block("parallel block"))
        self.fail("A line starting with `at` must be `at the end:` or `at the same time:`.")

    def st_test(self):
        t = self.advance()
        name = "".join(p for p in self.advance().value if isinstance(p, str))
        self.expect_colon("test", 'test "adding works":')
        return self.N("TestBlock", t, name=name, body=self.block("test"))

    def st_expect(self):
        t = self.advance()
        a = self.expr()
        neg = bool(self.accept_kw("not"))
        self.expect_kw("to", "Write `expect <value> to be <value>`.", "expect total to be 10")
        if self.accept_word("contain"):
            return self._expect_end(t, a, "contain", self.expr(), neg)
        self.expect_kw("be", "Write `expect <value> to be <value>`.", "expect total to be 10")
        for w in ("ok", "problem", "nothing", "some"):
            if self.kw(w) and self.ends_expr(1):
                self.advance()
                return self._expect_end(t, a, "test:" + w, None, neg)
        return self._expect_end(t, a, "be", self.expr(), neg)

    def _expect_end(self, t, a, how, b, neg):
        self.end_stmt()
        return self.N("Expect", t, expr=a, how=how, other=b, neg=neg)

    def st_send(self):
        t = self.advance()
        e = self.expr()
        self.expect_kw("to", "Write `send <value> to <channel>`.", "send result to results")
        ch = self.expr()
        self.end_stmt()
        return self.N("Send", t, expr=e, channel=ch)

    def st_repeat(self):
        t = self.advance()
        n = self.expr()
        self.expect_word("times", "A repeat loop is written `repeat <number> times:`.", "repeat 3 times:")
        self.expect_colon("repeat", "repeat 3 times:")
        return self.N("Repeat", t, count=n, body=self.block("loop"))

    def st_while(self):
        t = self.advance()
        c = self.expr()
        self.expect_colon("while", "while count is less than 10:")
        return self.N("While", t, cond=c, body=self.block("loop"))

    def st_stop(self):
        t = self.advance()
        self.end_stmt()
        return self.N("Stop", t)

    def st_skip(self):
        t = self.advance()
        self.end_stmt()
        return self.N("Skip", t)

    def st_to(self, sig_ok=False, ability=None):
        t = self.advance()
        owner = ability
        if self.peek().type == "NAME" and self.peek(1).type == "POSS":
            owner = self.advance().value
            self.advance()
        nm = self.name("the name of the new task")
        params = []
        def at_header_end():
            return (self.op(":") or self.word("gives") or (self.word("changes") and self.word("me", 1))
                    or self.peek().type in ("NEWLINE", "EOF"))
        if not at_header_end():
            while True:
                pt = self.peek()
                ch = bool(self.accept_kw("changeable"))
                pn = self.name("an input name")
                ptype = None
                if self.accept_kw("as"):
                    ptype = self.type_()
                params.append(self.N("Param", pt, name=pn, changeable=ch, type=ptype))
                if not self.accept_op(","):
                    break
        changes_me = False
        if self.word("changes") and self.word("me", 1):
            if owner is None:
                self.fail("`changes me` only makes sense in a task that belongs to a type, like:  to Account's deposit amount changes me:")
            self.advance(); self.advance()
            changes_me = True
        ret = None
        if self.accept_word("gives"):
            ret = self.type_()
        if sig_ok and self.peek().type in ("NEWLINE", "EOF"):
            self.end_stmt()
            return self.N("FuncDef", t, name=nm, params=params, ret=ret, body=None, owner=owner,
                          changes_me=changes_me, shared=False)
        self.expect_colon("task", "to greet person:")
        old = getattr(self, "in_method", False)
        self.in_method = owner is not None
        body = self.block("task")
        self.in_method = old
        return self.N("FuncDef", t, name=nm, params=params, ret=ret, body=body, owner=owner,
                      changes_me=changes_me, shared=False)

    def st_ability(self):
        t = self.advance()
        nm = self.name("the ability's name")
        self.types.add(nm)
        self.expect_colon("ability", "ability Describable:\n    to describe gives text")
        if self.peek().type != "NEWLINE":
            self.fail("List the ability's tasks on indented lines below it.")
        self.advance()
        if not self.accept_kw_type("INDENT"):
            self.fail("List the ability's tasks on indented lines below it.", fix="ability Describable:\n    to describe gives text")
        methods = []
        while self.peek().type not in ("DEDENT", "EOF"):
            if self.peek().type == "NEWLINE":
                self.advance()
                continue
            if not self.kw("to"):
                self.fail("Inside an ability, each line describes a task, starting with `to`.", fix="    to describe gives text")
            methods.append(self.st_to(sig_ok=True, ability=nm))
        self.accept_kw_type("DEDENT")
        return self.N("AbilityDef", t, name=nm, methods=methods, shared=False)

    def type_params(self):
        params = []
        if self.accept_kw("of"):
            params.append(self.name("a type placeholder like T"))
            while self.accept_kw("and") or self.accept_op(","):
                params.append(self.name("a type placeholder"))
        return params

    def st_give(self):
        t = self.advance()
        self.expect_word("back", "To return a value from a task, write `give back`.", "give back total")
        e = None if self.peek().type in END_OF_EXPR else self.expr()
        self.end_stmt()
        return self.N("Return", t, expr=e)

    def st_record(self):
        t = self.advance()
        nm = self.name("the record's name")
        self.types.add(nm)
        tparams = self.type_params()
        self.expect_colon("record", "record %s:\n    title as text" % nm)
        if self.peek().type != "NEWLINE":
            self.fail("List the record's fields on indented lines below it.", fix="record %s:\n    name as text\n    age as number" % nm)
        self.advance()
        if not self.accept_kw_type("INDENT"):
            self.fail("List the record's fields on indented lines below it.", fix="record %s:\n    name as text" % nm)
        fields = []
        while self.peek().type not in ("DEDENT", "EOF"):
            if self.peek().type == "NEWLINE":
                self.advance()
                continue
            fname = self.name("a field name")
            ftype = self.type_() if self.accept_kw("as") else None
            fields.append((fname, ftype))
            self.end_stmt()
        self.accept_kw_type("DEDENT")
        return self.N("RecordDef", t, name=nm, fields=fields, tparams=tparams, shared=False)

    def accept_kw_type(self, typ):
        return self.advance() if self.peek().type == typ else None

    def st_choice(self):
        t = self.advance()
        nm = self.name("the choice's name")
        self.types.add(nm)
        tparams = self.type_params()
        self.expect_colon("choice", "choice %s:\n    Circle with radius as number" % nm)
        if self.peek().type != "NEWLINE":
            self.fail("List the options on indented lines below.", fix="choice Shape:\n    Circle with radius\n    Square with side")
        self.advance()
        if not self.accept_kw_type("INDENT"):
            self.fail("List the options on indented lines below.", fix="choice Shape:\n    Circle with radius")
        variants = []
        while self.peek().type not in ("DEDENT", "EOF"):
            if self.peek().type == "NEWLINE":
                self.advance()
                continue
            vt = self.peek()
            vn = self.name("an option name")
            self.types.add(vn)
            fields = []
            if self.accept_kw("with"):
                while True:
                    fname = self.name("a field name")
                    ftype = self.type_() if self.accept_kw("as") else None
                    fields.append((fname, ftype))
                    if not self.accept_op(","):
                        break
            variants.append((vn, fields, vt.line))
            self.end_stmt()
        self.accept_kw_type("DEDENT")
        return self.N("ChoiceDef", t, name=nm, variants=variants, tparams=tparams, shared=False)

    def st_when(self):
        t = self.advance()
        subj = self.expr()
        self.expect_colon("when", "when shape:\n    is Circle with r: ...")
        if self.peek().type != "NEWLINE":
            self.fail("Put each case of `when` on its own indented line.")
        self.advance()
        if not self.accept_kw_type("INDENT"):
            self.fail("The cases of `when` should be indented below it.", fix="when answer:\n    is \"yes\": say \"great\"\n    otherwise: say \"ok\"")
        cases, other = [], None
        while self.peek().type not in ("DEDENT", "EOF"):
            if self.peek().type == "NEWLINE":
                self.advance()
                continue
            ct = self.peek()
            if self.accept_kw("otherwise"):
                self.expect_colon("otherwise", "otherwise: say \"something else\"")
                other = self.block("otherwise")
                continue
            if not self.accept_kw("is"):
                self.fail("Inside `when`, each case starts with `is` (or `otherwise`).",
                          fix="when shape:\n    is Circle with r: ...\n    otherwise: ...")
            pats = [self.pattern()]
            while self.accept_kw("or"):
                pats.append(self.pattern())
            guard = self.expr() if self.accept_kw("if") else None
            self.expect_colon("case", "is Circle with r:")
            cases.append((pats, self.block("case"), ct.line, guard))
        self.accept_kw_type("DEDENT")
        return self.N("When", t, subject=subj, cases=cases, other=other)

    def pattern_end(self):
        return self.op(":") or self.op(",") or self.op(")") or self.kw("or") or self.kw("if")

    def pattern(self):
        t = self.peek()
        P = lambda **kw: self.N("Pat", t, **kw)
        if self.accept_kw("some"):
            return P(pk="some", sub=self.pattern())
        if self.accept_kw("nothing"):
            return P(pk="nothing")
        if self.accept_kw("ok"):
            return P(pk="ok", sub=None if self.pattern_end() else self.pattern())
        if self.accept_kw("problem"):
            return P(pk="problem", sub=None if self.pattern_end() else self.pattern())
        if self.accept_kw("from"):
            lo = self.literal_value()
            self.expect_kw("to", "A range case is written `is from 1 to 10:`.")
            hi = self.literal_value()
            return P(pk="range", lo=lo, hi=hi)
        if self.accept_op("("):
            items = [self.pattern()]
            while self.accept_op(","):
                items.append(self.pattern())
            if not self.accept_op(")"):
                self.fail("Close the pattern with ')'.")
            return items[0] if len(items) == 1 else P(pk="tuple", items=items)
        if t.type in ("NUMBER", "STRING") or self.op("-") or self.kw("true") or self.kw("false"):
            return P(pk="lit", value=self.literal_value())
        if t.type == "NAME":
            if t.value in ("a", "an") and self.peek(1).type == "NAME" and self.peek(1).value in self.types:
                self.advance()
                t = self.peek()
            vn = t.value
            if vn == "anything":
                self.advance()
                return P(pk="any")
            if vn in self.types:
                self.advance()
                subs = []
                if self.accept_kw("with"):
                    want = len(self.fields.get(vn, [])) or None
                    subs.append(self.pattern())
                    while (want is None or len(subs) < want) and self.accept_op(","):
                        subs.append(self.pattern())
                return P(pk="variant", name=vn, subs=subs)
            if vn[:1].isupper():
                s = suggest(vn, self.types)
                self.fail("I don't know an option called `%s`." % vn, t,
                          fix=("Did you mean `%s`?" % s) if s else "Options are declared with `choice`.")
            self.advance()
            return P(pk="bind", name=vn)
        self.fail("After `is`, write a value (like 3 or \"yes\"), an option (like Circle with r), a name, "
                  "some x, nothing, ok x, problem why, or a pair like (x, 0).")

    def literal_value(self):
        t = self.peek()
        neg = bool(self.accept_op("-"))
        t = self.advance()
        if t.type == "NUMBER":
            return -t.value if neg else t.value
        if neg:
            self.fail("Expected a number after '-'.", t)
        if t.type == "STRING":
            if any(not isinstance(p, str) for p in t.value):
                self.fail("A case value can't contain {...}.", t)
            return "".join(t.value)
        if t.type == "KW" and t.value in ("true", "false"):
            return t.value == "true"
        self.fail("I expected a plain value (a number, text or true/false) here.", t)

    def st_use(self):
        t = self.advance()
        items = []
        while True:
            nt = self.peek()
            if nt.type == "STRING":
                self.advance()
                items.append("".join(p for p in nt.value if isinstance(p, str)))
            else:
                items.append(self.name("a module name"))
            if not self.accept_op(","):
                break
        if self.accept_kw("from"):
            mt = self.peek()
            if mt.type == "STRING":
                self.advance()
                mod = "".join(p for p in mt.value if isinstance(p, str))
            else:
                mod = self.name("a module name")
            names = items
        else:
            if len(items) != 1:
                self.fail("Use one module per line, or pick names with `from`.", fix="use area, perimeter from shapes")
            mod, names = items[0], None
        self.end_stmt()
        return self.N("Use", t, module=mod, names=names, path=None)

    def st_fail(self):
        t = self.advance()
        e = self.expr()
        self.end_stmt()
        return self.N("Fail", t, expr=e)

    # ---------- types
    def type_(self):
        t = self.peek()
        if self.accept_op("("):
            items = [self.type_()]
            while self.accept_op(","):
                items.append(self.type_())
            if not self.accept_op(")"):
                self.fail("Close the type with ')'.", fix="(number, text)")
            return items[0] if len(items) == 1 else self.N("Type", t, name="tuple", args=items)
        if self.accept_kw("list"):
            self.expect_kw("of", "Write `list of <type>`.", "list of number")
            return self.N("Type", t, name="list", args=[self.type_()])
        if self.accept_kw("map"):
            self.expect_kw("of", "Write `map of <key type> to <value type>`.", "map of text to number")
            k = self.type_()
            self.expect_kw("to", "Write `map of <key type> to <value type>`.", "map of text to number")
            return self.N("Type", t, name="map", args=[k, self.type_()])
        if t.type == "NAME" and t.value in ("set", "channel", "job") and self.kw("of", 1):
            self.advance(); self.advance()
            return self.N("Type", t, name=t.value, args=[self.type_()])
        if self.accept_word("maybe"):
            return self.N("Type", t, name="maybe", args=[self.type_()])
        if self.accept_word("result"):
            self.accept_kw("of")
            ok = self.type_()
            args = [ok]
            if self.accept_kw("or"):
                args.append(self.type_())
            return self.N("Type", t, name="result", args=args)
        if self.accept_word("task"):
            params, ret = [], None
            if self.accept_kw("of"):
                params.append(self.type_())
                while self.accept_kw("and"):
                    params.append(self.type_())
            if self.accept_word("gives"):
                ret = self.type_()
            return self.N("Type", t, name="task", args=params, ret=ret)
        if t.type == "NAME":
            self.advance()
            v = t.value
            if len(v) == 1 and v.isupper():
                return self.N("Type", t, name=v, args=[], var=True)
            if v in ("number", "text", "truth", "anything", "integer", "decimal"):
                return self.N("Type", t, name=v, args=[])
            if v in self.types:
                args = []
                if self.accept_kw("of"):
                    args.append(self.type_())
                    while self.accept_kw("and"):
                        args.append(self.type_())
                return self.N("Type", t, name=v, args=args)
            alias = {"int": "integer", "integer": "integer", "float": "decimal", "str": "text", "string": "text", "bool": "truth",
                     "boolean": "truth", "i32": "integer", "i64": "integer", "f64": "decimal", "String": "text"}.get(v)
            s = alias or suggest(v, ["number", "text", "truth", "anything", "integer", "decimal"] + sorted(self.types))
            self.fail("I don't know the type `%s`." % v, t,
                      fix=("Did you mean `%s`? " % s if s else "") +
                      "Types are: number, integer, decimal, text, truth, anything, list of T, map of K to V, set of T, "
                      "maybe T, result of T, (A, B), task of A gives B, a single capital letter like T (any type), "
                      "or a record/choice/ability name.")
        self.fail("I expected a type (like number, text, truth, list of number) here, but found %s." % describe_tok(t))

    def expr(self):
        left = self.or_()
        while self.kw("or") and self.kw("else", 1):
            t = self.advance()
            self.advance()
            left = self.N("OrElse", t, l=left, r=self.or_())
        return left

    def or_(self):
        left = self.and_()
        while self.kw("or") and not self.kw("else", 1):
            t = self.advance()
            left = self.N("Logic", t, op="or", l=left, r=self.and_())
        return left

    def and_(self):
        left = self.not_()
        while self.kw("and"):
            t = self.advance()
            left = self.N("Logic", t, op="and", l=left, r=self.not_())
        return left

    def not_(self):
        if self.kw("not"):
            t = self.advance()
            return self.N("Not", t, expr=self.not_())
        return self.comparison()

    def comparison(self):
        left = self.additive()
        t = self.peek()
        if self.kw("is"):
            self.advance()
            neg = bool(self.accept_kw("not"))
            if self.kw("nothing") and self.ends_expr(1):
                self.advance()
                return self.N("Test", t, what="nothing", expr=left, neg=neg)
            for w in ("ok", "problem", "some"):
                if self.kw(w) and self.ends_expr(1):
                    self.advance()
                    return self.N("Test", t, what=w, expr=left, neg=neg)
            if self.word("a") or self.word("an"):
                if self.peek(1).type in ("NAME", "KW") and (self.peek(1).value in self.types or self.peek(1).value in BUILTIN_KINDS):
                    self.advance()
                    tn = self.advance().value
                    return self.N("TypeTest", t, tname=tn, expr=left, neg=neg)
            if self.word("between"):
                self.advance()
                lo = self.additive()
                self.expect_kw("and", "Write `is between <low> and <high>`.", "if age is between 13 and 19:")
                hi = self.additive()
                return self.N("Between", t, expr=left, lo=lo, hi=hi, neg=neg)
            if self.word("greater") or self.word("more"):
                self.advance()
                self.expect_word("than", "Write `is greater than`.")
                op = ">"
            elif self.word("less") or self.word("fewer"):
                self.advance()
                self.expect_word("than", "Write `is less than`.")
                op = "<"
            elif self.kw("at") and (self.word("least", 1) or self.word("most", 1)):
                self.advance()
                op = ">=" if self.advance().value == "least" else "<="
            else:
                op = "is"
            right = self.additive()
            return self.N("Compare", t, op=op, l=left, r=right, neg=neg)
        if t.type == "OP" and t.value in (">", "<", ">=", "<="):
            self.advance()
            return self.N("Compare", t, op=t.value, l=left, r=self.additive(), neg=False)
        if self.word("contains"):
            self.advance()
            return self.N("Compare", t, op="contains", l=left, r=self.additive(), neg=False)
        if self.word("does") and self.kw("not", 1) and self.word("contain", 2):
            self.advance(); self.advance(); self.advance()
            return self.N("Compare", t, op="contains", l=left, r=self.additive(), neg=True)
        if (self.word("starts") or self.word("ends")) and self.kw("with", 1):
            self.advance(); self.advance()
            return self.N("Compare", t, op=t.value, l=left, r=self.additive(), neg=False)
        return left

    def additive(self):
        left = self.mult()
        while self.op("+") or self.op("-"):
            t = self.advance()
            left = self.N("Arith", t, op=t.value, l=left, r=self.mult())
        return left

    def mult(self):
        left = self.unary()
        while self.op("*") or self.op("/") or self.kw("mod") or self.kw("div"):
            t = self.advance()
            left = self.N("Arith", t, op=t.value, l=left, r=self.unary())
        return left

    def unary(self):
        t = self.peek()
        if self.accept_op("-"):
            return self.N("Neg", t, expr=self.unary())
        if self.accept_kw("try"):
            return self.N("Try", t, expr=self.unary())
        return self.postfix()

    def key(self):
        node = self.primary()
        while self.peek().type == "POSS":
            p = self.advance()
            node = self.N("Field", p, obj=node, name=self.name("a field name after 's"))
        return node

    def postfix(self):
        node = self.primary()
        while True:
            t = self.peek()
            if t.type == "POSS":
                self.advance()
                nm = self.name("a field name after 's")
                if self.kw("with"):
                    self.advance()
                    node = self.N("MethodCall", t, obj=node, name=nm, args=self.args())
                elif self.kw("of") and not self.no_of and not any(nm in fs for fs in self.fields.values()):
                    at = self.advance()
                    mode = "share"
                    if self.accept_kw("lend"):
                        mode = "lend"
                    elif self.accept_kw("give"):
                        mode = "give"
                    node = self.N("MethodCall", t, obj=node, name=nm, args=[self.N("Arg", at, mode=mode, expr=self.unary())])
                else:
                    node = self.N("Field", t, obj=node, name=nm)
            elif self.kw("at") and not (self.word("least", 1) or self.word("most", 1) or self.word("the", 1)):
                self.advance()
                node = self.N("Key", t, obj=node, key=self.key())
            elif self.kw("as"):
                self.advance()
                if (self.kw("list") or self.word("set")) and not self.kw("of", 1):
                    tt = self.advance()
                    ty = self.N("Type", tt, name=tt.value, args=[self.N("Type", tt, name="anything", args=[])])
                else:
                    ty = self.type_()
                node = self.N("Convert", t, expr=node, type=ty)
            else:
                return node

    def args(self):
        out = []
        while True:
            t = self.peek()
            mode = "share"
            if self.accept_kw("lend"):
                mode = "lend"
            elif self.accept_kw("give"):
                mode = "give"
            out.append(self.N("Arg", t, mode=mode, expr=self.or_()))
            if not self.accept_op(","):
                return out

    def primary(self):
        t = self.peek()
        ty = t.type
        if self.kw("if"):
            self.advance()
            cond = self.expr()
            if not self.word("then"):
                self.fail("An `if` inside a value needs `then` and `otherwise`.", fix='let label be if score is at least 50 then "pass" otherwise "fail"')
            self.advance()
            yes = self.expr()
            if not self.kw("otherwise"):
                hint = "Lekh says `otherwise` instead of `else`. " if self.peek().value == "else" else ""
                self.fail(hint + "An `if ... then ...` value also needs an `otherwise` answer.", fix='let label be if score is at least 50 then "pass" otherwise "fail"')
            self.advance()
            no = self.expr()
            return self.N("IfExpr", t, cond=cond, yes=yes, no=no)
        if ty == "NUMBER":
            self.advance()
            return self.N("Num", t, value=t.value)
        if ty == "STRING":
            self.advance()
            parts = []
            for p in t.value:
                if isinstance(p, str):
                    parts.append(p)
                else:
                    sub = tokenize(p[1], self.file, p[2], inline=True)
                    sp = Parser(sub, self.file, self.types, self.fields)
                    sp.in_method = getattr(self, "in_method", False)
                    sp.tvars = getattr(self, "tvars", set())
                    e = sp.expr()
                    if sp.peek().type not in ("NEWLINE", "EOF"):
                        sp.fail("I couldn't understand the {...} part of this text.", fix="Inside {} put one value, like \"Total: {price * 2}\"")
                    parts.append(e)
            return self.N("Str", t, parts=parts)
        if ty == "OP" and t.value == "(":
            self.advance()
            old = self.no_of
            self.no_of = False
            e = self.expr()
            if self.op(","):
                items = [e]
                while self.accept_op(","):
                    items.append(self.expr())
                self.no_of = old
                if not self.accept_op(")"):
                    self.fail("I expected ')' to close the group here, but found %s." % describe_tok(self.peek()))
                return self.N("TupleLit", t, items=items)
            self.no_of = old
            if not self.accept_op(")"):
                self.fail("I expected ')' to close the '(' here, but found %s." % describe_tok(self.peek()))
            return e
        if ty == "KW":
            v = t.value
            if v in ("true", "false"):
                self.advance()
                return self.N("Bool", t, value=(v == "true"))
            if v == "nothing":
                self.advance()
                return self.N("NothingLit", t)
            if v in ("some", "ok", "problem"):
                self.advance()
                return self.N("Wrap", t, tag=v, expr=self.additive())
            if v == "list":
                self.advance()
                self.expect_kw("of", "Write `list of` followed by the items.", "list of 1, 2, 3   (or: empty list)")
                items = [self.or_()]
                while self.accept_op(","):
                    items.append(self.or_())
                return self.N("ListLit", t, items=items)
            if v == "map":
                self.advance()
                self.expect_kw("of", "Write `map of <key> to <value>, ...`.", "map of \"Asha\" to 30, \"Ravi\" to 25   (or: empty map)")
                pairs = []
                while True:
                    k = self.or_()
                    self.expect_kw("to", "In a map, each key needs `to` and a value.", "map of \"Asha\" to 30")
                    pairs.append((k, self.or_()))
                    if not self.accept_op(","):
                        break
                return self.N("MapLit", t, pairs=pairs)
            if v == "empty":
                self.advance()
                if self.accept_kw("list"):
                    return self.N("EmptyList", t)
                if self.accept_kw("map"):
                    return self.N("EmptyMap", t)
                if self.accept_word("set"):
                    return self.N("EmptySet", t)
                self.fail("Write `empty list`, `empty map` or `empty set`.")
            if v == "copy":
                self.advance()
                self.expect_kw("of", "Write `copy of <value>`.", "copy of cart")
                return self.N("Copy", t, expr=self.unary())
            if v == "ask":
                self.advance()
                prompt = None if self.ends_expr() else self.postfix()
                return self.N("Ask", t, prompt=prompt)
            if v == "run":
                self.advance()
                return self.N("RunCall", t, name=self.name("the name of the task to run"))
            if v == "fail":
                self.advance()
                return self.N("Fail", t, expr=self.or_())
            if v in ("lend", "give"):
                self.fail("`%s` is used when handing a value to a task, like: deposit with lend account, 50" % v)
            self.fail("I expected a value here, but found the word '%s'." % v,
                      fix=foreign_hint(v) or "Values are things like 5, \"text\", true, a name, or list of 1, 2.")
        if ty == "NAME":
            v = t.value
            special = self.special_primary(t)
            if special is not None:
                return special
            if v in ("a", "an"):
                nx = self.peek(1)
                if (nx.type == "KW" and nx.value in ("list", "map", "empty", "copy")) or (
                        nx.type == "NAME" and (nx.value in self.types or nx.value in ("new", "set"))):
                    self.advance()
                    return self.primary()
            if v == "item" and self.starts_value(self.peek(1)):
                self.advance()
                old = self.no_of
                self.no_of = True
                idx = self.additive()
                self.no_of = old
                self.expect_kw("of", "After `item <number>` write `of` and the list.", "item 2 of cart")
                return self.N("Index", t, obj=self.unary(), index=idx)
            if v in self.types:
                self.advance()
                fields = []
                if self.accept_kw("with"):
                    while True:
                        fn = self.name("a field name (like: %s with name \"...\")" % v)
                        fields.append((fn, self.or_()))
                        # continue only if the next thing is another field of this type (not a new value)
                        nxt = self.peek(1)
                        known = self.fields.get(v)
                        if known is not None:
                            more = nxt.type == "NAME" and nxt.value in known and nxt.value not in [f for f, _ in fields]
                        else:
                            more = nxt.type == "NAME" and nxt.value not in self.types and self.starts_value(self.peek(2))
                        if self.op(",") and more:
                            self.advance()
                            continue
                        break
                return self.N("Construct", t, tname=v, fields=fields)
            self.advance()
            if self.kw("with"):
                self.advance()
                return self.N("Call", t, name=v, args=self.args())
            if self.kw("of") and not self.no_of:
                at = self.advance()
                mode = "share"
                if self.accept_kw("lend"):
                    mode = "lend"
                elif self.accept_kw("give"):
                    mode = "give"
                return self.N("Call", t, name=v, args=[self.N("Arg", at, mode=mode, expr=self.unary())])
            return self.N("Name", t, name=v)
        self.fail("I expected a value here, but found %s." % describe_tok(t),
                  fix="Values are things like 5, \"text\", true, a variable name, or list of 1, 2.")

    HOF_WORDS = ("keep", "turn", "count", "find", "combine", "sort")

    def special_primary(self, t):
        """Contextual English forms that start with an ordinary word."""
        v, n1, n2 = t.value, self.peek(1), self.peek(2)
        N = self.N
        if v == "given" and (n1.type == "NAME" or (n1.type == "KW" and n1.value == "nothing")):
            return self.lambda_(t)
        if v in self.HOF_WORDS and n1.type == "NAME" and n1.value in ("each", "first") and n2.type == "NAME" and self.kw("in", 3):
            return self.hof(t)
        if v in ("any", "every") and n1.type == "NAME" and self.kw("in", 2):
            return self.hof(t)
        if v == "range" and n1.type == "KW" and n1.value == "from":
            self.advance(); self.advance()
            a = self.additive()
            self.expect_kw("to", "Write `range from 1 to 10`.")
            b = self.additive()
            step = self.additive() if self.accept_word("by") else None
            return N("Range", t, start=a, end=b, step=step)
        if v == "take" and n1.type == "NAME" and n1.value in ("first", "last") and self.kw("from", 2):
            self.advance(); self.advance(); self.advance()
            return N("Take", t, which=n1.value, target=self.target())
        if v == "my" and getattr(self, "in_method", False) and n1.type == "NAME" and n1.value not in CONTEXT_OPS:
            self.advance()
            return N("Field", t, obj=N("Name", t, name="me"), name=self.name("a field name"))
        if v == "new" and n1.type == "NAME" and n1.value == "channel":
            self.advance(); self.advance()
            return N("NewChannel", t)
        if v == "set" and n1.type == "KW" and n1.value == "of":
            self.advance(); self.advance()
            items = [self.or_()]
            while self.accept_op(","):
                items.append(self.or_())
            return N("SetLit", t, items=items)
        if v == "receive" and n1.type == "KW" and n1.value == "from":
            self.advance(); self.advance()
            return N("Receive", t, channel=self.unary())
        if v == "wait" and n1.type == "KW" and n1.value == "for":
            self.advance(); self.advance()
            return N("WaitFor", t, job=self.unary())
        if v == "start" and n1.type == "NAME" and n2.type == "KW" and n2.value in ("with", "of"):
            self.advance()
            call = self.primary()
            return N("Start", t, call=call)
        return None

    def lambda_(self, t):
        self.advance()
        params = []
        if self.accept_kw("nothing"):
            pass
        else:
            while True:
                pt = self.peek()
                pn = self.name("an input name for the task")
                ptype = self.type_() if self.accept_kw("as") else None
                params.append(self.N("Param", pt, name=pn, changeable=False, type=ptype))
                if not self.accept_op(","):
                    break
        if not self.accept_op(":"):
            self.fail("A `given` task needs ':' and then what it gives back.", fix="given n: n * 2")
        if self.peek().type == "NEWLINE":
            body = self.block("task")
            return self.N("Lambda", t, params=params, expr=None, body=body)
        old = self.no_of
        self.no_of = False
        e = self.or_()
        self.no_of = old
        return self.N("Lambda", t, params=params, expr=e, body=None)

    def hof(self, t):
        kind = self.advance().value
        if kind not in ("any", "every"):
            self.advance()  # each / first
        var = self.name("a name for each item")
        self.expect_kw("in", "Write `%s each x in <list> ...`." % kind)
        src = self.additive()
        N = self.N
        if kind in ("keep", "count", "find", "any", "every"):
            self.expect_word("where", "Write `%s ... where <condition>`." % kind, "keep each n in numbers where n is greater than 0")
            return N("HOF", t, form=kind, var=var, src=src, body=self.or_(), acc=None, init=None, desc=False)
        if kind == "turn":
            self.expect_word("into", "Write `turn each x in <list> into <new value>`.", "turn each n in numbers into n * 2")
            return N("HOF", t, form=kind, var=var, src=src, body=self.or_(), acc=None, init=None, desc=False)
        if kind == "sort":
            self.expect_word("by", "Write `sort each x in <list> by <what to compare>`.", "sort each p in people by p's age")
            key = self.expr()
            desc = bool(self.accept_word("descending"))
            if not desc:
                self.accept_word("ascending")
            return N("HOF", t, form=kind, var=var, src=src, body=key, acc=None, init=None, desc=desc)
        # combine each n in numbers into total starting at 0 using total + n
        self.expect_word("into", "Write `combine each x in <list> into total starting at 0 using total + x`.")
        acc = self.name("a name for the running total")
        self.expect_word("starting", "Write `... into %s starting at <first value> using ...`." % acc)
        self.expect_kw("at", "Write `... starting at <first value> ...`.")
        init = self.additive()
        self.expect_word("using", "Write `... using <how to combine>`.", "combine each n in numbers into total starting at 0 using total + n")
        return N("HOF", t, form=kind, var=var, src=src, body=self.or_(), acc=acc, init=init, desc=False)


def target_desc(tg):
    if tg.kind == "Name":
        return tg.name
    if tg.kind == "Field":
        return "%s's %s" % (target_desc(tg.obj), tg.name)
    if tg.kind == "Key":
        return "%s at ..." % target_desc(tg.obj)
    if tg.kind == "Index":
        return "item ... of %s" % target_desc(tg.obj)
    return "that value"


def prescan_types(toks):
    """Find record and choice names (and choice options) before parsing, so `Task with ...` parses."""
    records, choices, fields = set(), {}, {}
    i = 0
    while i < len(toks):
        t = toks[i]
        if t.type == "KW" and t.value == "record" and i + 1 < len(toks) and toks[i + 1].type == "NAME":
            rname = toks[i + 1].value
            records.add(rname)
            fl = []
            j = i + 2
            while j < len(toks) and toks[j].type not in ("INDENT", "EOF"):
                j += 1
            if j < len(toks) and toks[j].type == "INDENT":
                j += 1
                at_start = True
                while j < len(toks) and toks[j].type not in ("DEDENT", "EOF"):
                    if toks[j].type == "NEWLINE":
                        at_start = True
                    else:
                        if at_start and toks[j].type == "NAME":
                            fl.append(toks[j].value)
                        at_start = False
                    j += 1
            fields[rname] = fl
        elif t.type == "KW" and t.value == "choice" and i + 1 < len(toks) and toks[i + 1].type == "NAME":
            cname = toks[i + 1].value
            variants = []
            j = i + 2
            while j < len(toks) and toks[j].type not in ("INDENT", "EOF"):
                j += 1
            if j < len(toks) and toks[j].type == "INDENT":
                j += 1
                depth, at_start = 0, True
                while j < len(toks):
                    tj = toks[j]
                    if tj.type == "INDENT":
                        depth += 1
                    elif tj.type == "DEDENT":
                        if depth == 0:
                            break
                        depth -= 1
                    elif tj.type == "NEWLINE":
                        at_start = True
                        j += 1
                        continue
                    elif at_start and depth == 0 and tj.type == "NAME":
                        variants.append(tj.value)
                        fields[tj.value] = []
                    elif tj.type == "NAME" and variants and toks[j - 1].type in ("KW", "OP") and \
                            toks[j - 1].value in ("with", ","):
                        fields[variants[-1]].append(tj.value)
                    at_start = False
                    j += 1
            choices[cname] = variants
        i += 1
    return records, choices, fields


# =====================================================================================
#  Runtime values
# =====================================================================================
class PList:
    def __init__(self, items=None):
        self.items = items if items is not None else []
        self.looping = 0


class PMap:
    def __init__(self, d=None):
        self.d = d if d is not None else {}
        self.looping = 0


class RecordType:
    def __init__(self, name, fields):
        self.name, self.fields = name, fields  # fields: [(name, TypeNode|None)]
        self.methods = {}


class ChoiceType:
    def __init__(self, name):
        self.name, self.variants = name, {}
        self.methods = {}


class AbilityType:
    def __init__(self, name, node):
        self.name, self.node = name, node
        self.methods = {}


class VariantType:
    def __init__(self, choice, name, fields):
        self.choice, self.name, self.fields = choice, name, fields


class Record:
    def __init__(self, rtype, fields):
        self.rtype, self.fields = rtype, fields


class Variant:
    def __init__(self, vtype, fields):
        self.vtype, self.fields = vtype, fields


class Some:
    def __init__(self, value):
        self.value = value


class NothingType:
    pass


NOTHING = NothingType()


class Ok:
    def __init__(self, value):
        self.value = value


class Problem:
    def __init__(self, value):
        self.value = value


class Function:
    def __init__(self, node, genv):
        self.node, self.genv = node, genv


class Builtin:
    def __init__(self, name, fn, lo, hi):
        self.name, self.fn, self.lo, self.hi = name, fn, lo, hi


class PyTask:
    """A task compiled to a Python function by `lekh build`."""
    def __init__(self, fn, name, nparams):
        self.fn, self.name, self.nparams = fn, name, nparams


class Tuple:
    def __init__(self, items):
        self.items = tuple(items)

    def __eq__(self, other):
        return isinstance(other, Tuple) and len(self.items) == len(other.items) and all(eq_struct(a, b) for a, b in zip(self.items, other.items))

    def __hash__(self):
        return hash(self.items)


class PSet:
    def __init__(self, items=None):
        self.s = items if items is not None else set()
        self.looping = 0


class Lambda:
    def __init__(self, node, env):
        self.node, self.env = node, env
        self.name = "given-task"


class Channel:
    def __init__(self):
        import queue
        self.q = queue.Queue()
        self.closed = False
        self.kind = None


class Job:
    def __init__(self, name):
        self.name, self.thread, self.result, self.error, self.done = name, None, None, None, False


def sort_key(v, interp=None, node=None):
    if is_num(v) or isinstance(v, str):
        return v
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, Tuple):
        return tuple(sort_key(x, interp, node) for x in v.items)
    if interp is not None:
        interp.err(node, TYPE_P, "Things can only be sorted by numbers, text, or groups of those - not %s." % describe(v),
                   "Sort by a field instead, e.g.  sort each p in people by p's age")
    raise TypeError("unsortable")


ABILITY_IMPLS = {}   # type name -> set of ability names (filled at runtime by `X can Y`)


def sorted_items(st):
    try:
        return sorted(st.s, key=lambda x: (str(type(x)), x if not isinstance(x, Tuple) else str(x.items)))
    except TypeError:
        return list(st.s)


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def is_big(v):
    if isinstance(v, (PList, PMap, Record, Variant, PSet)):
        return True
    if isinstance(v, Tuple):
        return any(is_big(x) for x in v.items)
    if isinstance(v, (Some, Ok, Problem)):
        return is_big(v.value)
    return False


def deep_copy(v):
    if isinstance(v, PList):
        c = PList([deep_copy(x) for x in v.items])
        c.elem_type = getattr(v, "elem_type", None)
        return c
    if isinstance(v, PSet):
        return PSet(set(v.s))
    if isinstance(v, Tuple):
        return Tuple([deep_copy(x) for x in v.items])
    if isinstance(v, PMap):
        c = PMap({k: deep_copy(x) for k, x in v.d.items()})
        if getattr(v, "val_type", None) is not None:
            c.val_type = v.val_type
        return c
    if isinstance(v, Record):
        return Record(v.rtype, {k: deep_copy(x) for k, x in v.fields.items()})
    if isinstance(v, Variant):
        return Variant(v.vtype, {k: deep_copy(x) for k, x in v.fields.items()})
    if isinstance(v, Some):
        return Some(deep_copy(v.value))
    if isinstance(v, Ok):
        return Ok(deep_copy(v.value))
    if isinstance(v, Problem):
        return Problem(deep_copy(v.value))
    return v


BUILTIN_KINDS = {"number", "integer", "decimal", "text", "truth", "list", "map", "set", "group", "tuple",
                 "maybe", "result", "task", "channel", "job"}


def type_test_value(v, tname):
    if tname in BUILTIN_KINDS:
        if tname == "integer":
            return isinstance(v, int) and not isinstance(v, bool)
        if tname == "decimal":
            return isinstance(v, float)
        k = kind_of(v)
        return k == tname or (tname == "group" and k == "tuple")
    return (isinstance(v, Record) and v.rtype.name == tname) or \
        (isinstance(v, Variant) and (v.vtype.name == tname or v.vtype.choice.name == tname))


def kind_of(v):
    if isinstance(v, bool):
        return "truth"
    if is_num(v):
        return "number"
    if isinstance(v, str):
        return "text"
    if isinstance(v, PList):
        return "list"
    if isinstance(v, PMap):
        return "map"
    if isinstance(v, Record):
        return v.rtype.name
    if isinstance(v, Variant):
        return v.vtype.choice.name
    if isinstance(v, (Some, NothingType)):
        return "maybe"
    if isinstance(v, (Ok, Problem)):
        return "result"
    if isinstance(v, (Function, Builtin, Lambda, PyTask)):
        return "task"
    if isinstance(v, Tuple):
        return "tuple"
    if isinstance(v, PSet):
        return "set"
    if isinstance(v, Channel):
        return "channel"
    if isinstance(v, Job):
        return "job"
    return "unknown"


KIND_WORDS = {"truth": "true/false", "number": "a number", "text": "text", "list": "a list", "map": "a map",
              "maybe": "a maybe (some/nothing)", "result": "a result (ok/problem)", "task": "a task",
              "tuple": "a group (tuple)", "set": "a set", "channel": "a channel", "job": "a background job"}


def kind_words(k):
    return KIND_WORDS.get(k, "a " + k)


def fmt_num(x):
    if isinstance(x, float):
        if x != x or x in (float("inf"), float("-inf")):
            return str(x)
        if x.is_integer() and abs(x) < 1e15:
            return str(int(x))
        return repr(round(x, 10))
    return str(x)


def show(v, nested=False):
    if v is None:
        return "(no value)"
    if isinstance(v, bool):
        return "true" if v else "false"
    if is_num(v):
        return fmt_num(v)
    if isinstance(v, str):
        return '"%s"' % v if nested else v
    if isinstance(v, PList):
        return "[" + ", ".join(show(x, True) for x in v.items) + "]"
    if isinstance(v, PMap):
        return "{" + ", ".join("%s: %s" % (show(k, True), show(x, True)) for k, x in v.d.items()) + "}"
    if isinstance(v, Record):
        return "%s(%s)" % (v.rtype.name, ", ".join("%s: %s" % (k, show(x, True)) for k, x in v.fields.items()))
    if isinstance(v, Variant):
        if not v.fields:
            return v.vtype.name
        return "%s(%s)" % (v.vtype.name, ", ".join("%s: %s" % (k, show(x, True)) for k, x in v.fields.items()))
    if isinstance(v, Some):
        return "some " + show(v.value, True)
    if v is NOTHING:
        return "nothing"
    if isinstance(v, Ok):
        return "ok " + show(v.value, True)
    if isinstance(v, Problem):
        return "problem " + show(v.value, True)
    if isinstance(v, Tuple):
        return "(" + ", ".join(show(x, True) for x in v.items) + ")"
    if isinstance(v, PSet):
        if not v.s:
            return "empty set"
        return "set of " + ", ".join(show(x, True) for x in sorted_items(v))
    if isinstance(v, Lambda):
        return "<given task>"
    if isinstance(v, Channel):
        return "<channel>"
    if isinstance(v, Job):
        return "<job %s>" % v.name
    if isinstance(v, Function):
        return "<task %s>" % v.node.name
    if isinstance(v, Builtin):
        return "<built-in task %s>" % v.name
    if isinstance(v, PyTask):
        return "<task %s>" % v.name
    if isinstance(v, (RecordType, ChoiceType, VariantType)):
        return "<type %s>" % v.name
    return str(v)


def describe(v):
    k = kind_of(v)
    s = show(v, True)
    if len(s) > 40:
        s = s[:37] + "..."
    if isinstance(v, Variant):
        return "%s (a %s)" % (s, v.vtype.choice.name)
    if isinstance(v, Record):
        return "a %s record" % v.rtype.name
    if k in ("list", "map"):
        return "%s %s" % (kind_words(k), s)
    return "%s (%s)" % (kind_words(k), s)


def eq_struct(a, b):
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if is_num(a) and is_num(b):
        return a == b
    if isinstance(a, str) and isinstance(b, str):
        return a == b
    if isinstance(a, PList) and isinstance(b, PList):
        return len(a.items) == len(b.items) and all(eq_struct(x, y) for x, y in zip(a.items, b.items))
    if isinstance(a, PMap) and isinstance(b, PMap):
        return a.d.keys() == b.d.keys() and all(eq_struct(a.d[k], b.d[k]) for k in a.d)
    if isinstance(a, Record) and isinstance(b, Record):
        return a.rtype is b.rtype and all(eq_struct(a.fields[k], b.fields[k]) for k in a.fields)
    if isinstance(a, Variant) and isinstance(b, Variant):
        return a.vtype is b.vtype and all(eq_struct(a.fields[k], b.fields[k]) for k in a.fields)
    if isinstance(a, Tuple) and isinstance(b, Tuple):
        return a == b
    if isinstance(a, PSet) and isinstance(b, PSet):
        return a.s == b.s
    if a is NOTHING or b is NOTHING:
        return a is b
    for C in (Some, Ok, Problem):
        if isinstance(a, C) and isinstance(b, C):
            return eq_struct(a.value, b.value)
    return False


def type_desc(t):
    n = t.name
    if n == "tuple":
        return "a group of (%s)" % ", ".join(type_desc_plain(a) for a in t.args)
    if n == "set":
        return "a set of " + type_desc_plain(t.args[0])
    if n == "task":
        return "a task"
    if n in ("integer", "decimal"):
        return "a whole number" if n == "integer" else "a decimal number"
    if getattr(t, "var", False):
        return "any type (%s)" % n
    if n == "list":
        return "a list of " + type_desc_plain(t.args[0])
    if n == "map":
        return "a map of %s to %s" % (type_desc_plain(t.args[0]), type_desc_plain(t.args[1]))
    if n == "maybe":
        return "maybe " + type_desc_plain(t.args[0])
    if n == "result":
        return "a result of " + type_desc_plain(t.args[0])
    return {"number": "a number", "text": "text", "truth": "true/false", "anything": "anything"}.get(n, "a " + n)


def type_desc_plain(t):
    if t.name in ("list", "map", "maybe", "result", "tuple", "set"):
        return type_desc(t)
    return t.name


def type_src(t):
    n = t.name
    if n == "tuple":
        return "(" + ", ".join(type_src(a) for a in t.args) + ")"
    if n in ("set", "channel", "job"):
        return "%s of %s" % (n, type_src(t.args[0]))
    if n == "task":
        r = "task"
        if t.args:
            r += " of " + " and ".join(type_src(a) for a in t.args)
        if getattr(t, "ret", None) is not None:
            r += " gives " + type_src(t.ret)
        return r
    if t.args and n not in ("list", "map", "maybe", "result"):
        return n + " of " + " and ".join(type_src(a) for a in t.args)
    if n == "list":
        return "list of " + type_src(t.args[0])
    if n == "map":
        return "map of %s to %s" % (type_src(t.args[0]), type_src(t.args[1]))
    if n == "maybe":
        return "maybe " + type_src(t.args[0])
    if n == "result":
        return "result of " + type_src(t.args[0]) + ((" or " + type_src(t.args[1])) if len(t.args) > 1 else "")
    return n


def matches_type(v, t):
    n = t.name
    if n == "anything" or getattr(t, "var", False):
        return True
    if n == "integer":
        return is_num(v) and (isinstance(v, int) or v.is_integer())
    if n == "decimal":
        return is_num(v)
    if n == "set":
        return isinstance(v, PSet) and all(matches_type(x, t.args[0]) for x in v.s)
    if n == "tuple":
        return isinstance(v, Tuple) and len(v.items) == len(t.args) and all(matches_type(x, a) for x, a in zip(v.items, t.args))
    if n == "task":
        return isinstance(v, (Function, Builtin, Lambda, PyTask))
    if n == "channel":
        return isinstance(v, Channel)
    if n == "job":
        return isinstance(v, Job)
    if n == "number":
        return is_num(v)
    if n == "text":
        return isinstance(v, str)
    if n == "truth":
        return isinstance(v, bool)
    if n == "list":
        return isinstance(v, PList) and all(matches_type(x, t.args[0]) for x in v.items)
    if n == "map":
        return isinstance(v, PMap) and all(matches_type(k, t.args[0]) and matches_type(x, t.args[1]) for k, x in v.d.items())
    if n == "maybe":
        return v is NOTHING or (isinstance(v, Some) and matches_type(v.value, t.args[0]))
    if n == "result":
        if isinstance(v, Problem):
            return len(t.args) < 2 or matches_type(v.value, t.args[1])
        return isinstance(v, Ok) and matches_type(v.value, t.args[0])
    tn = v.rtype.name if isinstance(v, Record) else v.vtype.choice.name if isinstance(v, Variant) else None
    if tn is not None and n in ABILITY_IMPLS.get(tn, ()):
        return True
    if isinstance(v, Record):
        return v.rtype.name == n
    if isinstance(v, Variant):
        return v.vtype.choice.name == n or v.vtype.name == n
    return False


# =====================================================================================
#  Module loader
# =====================================================================================
class Module:
    def __init__(self, path, ast, records, choices, fields=None):
        self.path, self.ast, self.records, self.choices = path, ast, records, choices
        self.fields = fields or {}


PROJECT_FILE = "project.json"


def find_project_root(start):
    d = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(d, PROJECT_FILE)):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def resolve_module(base_file, name):
    """`use "x"` looks next to the current file first, then in the project's src/ and lib/ folders."""
    base = os.path.dirname(os.path.abspath(base_file)) if base_file and not base_file.startswith("<") else os.getcwd()
    fname = name if name.endswith(EXT) else name + EXT
    p = os.path.abspath(os.path.join(base, fname))
    if os.path.exists(p):
        return p
    root = find_project_root(base)
    if root:
        for sub in ("src", "lib", ""):
            q = os.path.abspath(os.path.join(root, sub, fname))
            if os.path.exists(q):
                return q
    return p


def expand_import(names, mod):
    """Selected names plus the options of any selected choice."""
    if names is None:
        return None
    out = set(names)
    for n in names:
        if n in mod.choices:
            out.update(mod.choices[n])
    return out


class Loader:
    def __init__(self):
        self.modules = {}

    def load(self, path, chain=(), line=None, from_file=None):
        ap = os.path.abspath(path)
        if ap in self.modules:
            return self.modules[ap]
        if ap in chain:
            raise LekhError(FILE_P, "These modules use each other in a circle: %s." %
                            " -> ".join(display_path(c) for c in chain + (ap,)), line,
                            "Move the shared tasks into a third module that both can use.", from_file)
        if not os.path.exists(ap):
            raise LekhError(FILE_P, "I can't find the file `%s`." % display_path(ap), line,
                            "Check the name and that the file ends in %s." % EXT, from_file)
        with open(ap, encoding="utf-8") as f:
            src = f.read()
        return self.load_source(src, ap, chain)

    def load_source(self, src, ap, chain=(), extra_types=(), extra_fields=None):
        SOURCES[ap] = src.split("\n")
        toks = tokenize(src, ap)
        imported = set(extra_types)
        all_fields = dict(extra_fields or {})
        for i, t in enumerate(toks):
            if t.type == "KW" and t.value == "use" and (i == 0 or toks[i - 1].type in ("NEWLINE", "INDENT", "DEDENT")):
                j, items, mod_name, names = i + 1, [], None, None
                while j < len(toks) and toks[j].type != "NEWLINE":
                    tj = toks[j]
                    if tj.type == "NAME":
                        items.append(tj.value)
                    elif tj.type == "STRING":
                        items.append("".join(p for p in tj.value if isinstance(p, str)))
                    elif tj.type == "KW" and tj.value == "from":
                        names = list(items)
                        items = []
                    j += 1
                if items:
                    mod_name = items[-1]
                    mod = self.load(resolve_module(ap, mod_name), chain + (ap,), t.line, ap)
                    allowed = expand_import(names, mod)
                    for tn in list(mod.records) + list(mod.choices) + [v for vs in mod.choices.values() for v in vs]:
                        if allowed is None or tn in allowed:
                            imported.add(tn)
                            if tn in mod.fields:
                                all_fields[tn] = mod.fields[tn]
        records, choices, fields = prescan_types(toks)
        all_fields.update(fields)
        types = set(records) | set(choices) | {v for vs in choices.values() for v in vs} | imported
        ast = Parser(toks, ap, types, all_fields).program()
        for s in ast:
            if s.kind == "Use":
                s.path = resolve_module(ap, s.module)
        mod = Module(ap, ast, records, choices, fields)
        self.modules[ap] = mod
        return mod


# =====================================================================================
#  Static checker: runs before the program and catches mistakes early
# =====================================================================================
BUILTIN_ARITY = {}  # filled in when builtins are defined


class VarInfo:
    def __init__(self, name, role, changeable=False, big=None, line=None, loop=0):
        self.name, self.role, self.changeable, self.big, self.line, self.loop = name, role, changeable, big, line, loop
        self.moved = None  # (line, how)
        self.par = 0
        self.kind = None   # statically inferred kind ("number", "text", "list", ...) when known


class Checker:
    def __init__(self, module, loader, predefined=None, repl=False):
        self.m, self.loader, self.repl = module, loader, repl
        self.predefined = predefined or {}
        self.funcs, self.records, self.variants, self.choices = {}, {}, {}, {}
        self.scopes, self.all, self.loop, self.in_func = [], [], 0, None
        self.looping = []
        self.methods, self.abilities = {}, {}
        self.par = 0          # how many `at the same time` blocks we are inside
        self.floors = []      # scope index where each enclosing `given` task starts
        self.in_test = False

    def err(self, node, title, msg, fix=None):
        raise LekhError(title, msg, node.line, fix, node.file)

    # ----- declarations
    def collect_from(self, ast, allowed=None, consts=None, imported=False):
        for s in ast:
            ok = allowed is None or getattr(s, "name", None) in allowed
            if imported and not getattr(s, "shared", False) and s.kind != "Can" and not (s.kind == "FuncDef" and s.owner):
                ok = False
            if s.kind == "FuncDef" and s.owner:
                self.methods[(s.owner, s.name)] = s
            elif s.kind == "FuncDef" and ok:
                self.funcs[s.name] = s
            elif s.kind == "RecordDef" and ok:
                self.records[s.name] = [f[0] for f in s.fields]
            elif s.kind == "ChoiceDef" and ok:
                self.choices[s.name] = [v[0] for v in s.variants]
                for vn, fields, _ in s.variants:
                    self.variants[vn] = (s.name, [f[0] for f in fields])
            elif s.kind == "AbilityDef" and ok:
                self.abilities[s.name] = s
                KNOWN_ABILITIES.add(s.name)
                for m in s.methods:
                    if m.body is not None:
                        self.methods[(s.name, m.name)] = m
            elif s.kind == "Let" and consts is not None and not s.changeable and ok:
                consts.append(s.name)

    def check(self):
        imported_consts = []
        for s in self.m.ast:
            if s.kind == "Use":
                mod = self.loader.modules.get(s.path)
                if mod is None:
                    continue
                allowed = expand_import(s.names, mod)
                if s.names:
                    avail, private = set(), set()
                    for d in mod.ast:
                        if (d.kind in ("FuncDef", "RecordDef", "ChoiceDef", "AbilityDef") and not getattr(d, "owner", None)) or (d.kind == "Let" and not d.changeable):
                            (avail if getattr(d, "shared", False) else private).add(d.name)
                    for n in s.names:
                        if n in private:
                            self.err(s, NAME_P, "`%s` is private to the module `%s`." % (n, s.module),
                                     "In %s, put `share` in front of it to make it public:\n    share to %s ..." % (display_path(s.path), n))
                        if n not in avail:
                            sg = suggest(n, avail)
                            self.err(s, NAME_P, "The module `%s` has nothing called `%s`." % (s.module, n),
                                     ("Did you mean `%s`? " % sg if sg else "") + "It shares: " + (", ".join(sorted(avail)) or "(nothing)"))
                self.collect_from(mod.ast, allowed, imported_consts, imported=True)
        self.collect_from(self.m.ast)
        self.records.setdefault("Response", ["status", "body", "headers"])
        self.records.setdefault("CommandOutput", ["output", "errors", "code"])
        g = {}
        for b in BUILTIN_ARITY:
            g[b] = VarInfo(b, "builtin")
        for n in list(self.records) + list(self.choices) + list(self.variants) + list(self.abilities):
            g[n] = VarInfo(n, "type")
        for n in self.funcs:
            g[n] = VarInfo(n, "function", line=self.funcs[n].line)
        for n in imported_consts:
            g[n] = VarInfo(n, "let", big=None)
        g.update(self.predefined)
        self.scopes = [g]
        for s in self.m.ast:
            if s.kind in ("FuncDef", "RecordDef", "ChoiceDef", "Use", "AbilityDef"):
                continue
            if s.kind == "Can":
                self.check_can(s)
                continue
            if s.kind == "TestBlock":
                self.in_test = True
                self.branches([lambda s=s: self.block(s.body)], False)
                self.in_test = False
                continue
            self.stmt(s)
        # now check task bodies, seeing top-level lets as read-only globals
        fg = {}
        for n, info in g.items():
            if info.role == "let":
                gi = VarInfo(n, "global", changeable=info.changeable, big=info.big, line=info.line)
                fg[n] = gi
            else:
                fg[n] = info
        bodies = [d for d in self.m.ast if d.kind == "FuncDef"]
        for d in self.m.ast:
            if d.kind == "AbilityDef":
                bodies.extend(m for m in d.methods if m.body is not None)
        for s in bodies:
            if True:
                self.scopes = [fg, {}]
                self.in_func, self.loop, self.par, self.floors = s, 0, 0, []
                if s.owner:
                    self.declare(VarInfo("me", "param", changeable=s.changes_me, line=s.line), s)
                    self.scopes[-1]["me"].kind = s.owner
                seen = set()
                for p in s.params:
                    if p.name in seen:
                        self.err(p, SYNTAX, "The task `%s` has two inputs called `%s`." % (s.name, p.name), "Give each input its own name.")
                    seen.add(p.name)
                    pi = VarInfo(p.name, "param", changeable=p.changeable, line=p.line)
                    pi.kind = static_kind_of_type(p.type) if p.type is not None else None
                    self.declare(pi, p)
                self.block(s.body)
                self.in_func = None

    # ----- scopes
    def declare(self, info, node):
        prev = self.lookup_raw(info.name)
        if prev and prev.role in ("function", "type"):
            what = {"function": "a task", "type": "a record, choice or option"}[prev.role]
            self.err(node, NAME_P, "`%s` is already the name of %s, so it can't also be a variable." % (info.name, what),
                     "Pick another name, like `my_%s`." % info.name)
        info.par = self.par
        self.scopes[-1][info.name] = info
        self.all.append(info)

    def lookup_raw(self, name):
        for sc in reversed(self.scopes):
            if name in sc:
                return sc[name]
        return None

    def visible_names(self):
        out = set()
        for sc in self.scopes:
            out.update(sc.keys())
        return out

    def lookup(self, node):
        info = self.lookup_raw(node.name)
        if info is None:
            self.unknown(node)
        return info

    def unknown(self, node):
        name = node.name
        fh = foreign_hint(name)
        if fh:
            self.err(node, NAME_P, "I don't know anything called `%s`." % name, fh)
        s = suggest(name, self.visible_names())
        fix = ("Did you mean `%s`?" % s) if s else ("Create it first with:  let %s be ..." % name)
        self.err(node, NAME_P, "I don't know anything called `%s` here." % name, fix)

    def block(self, stmts, extra=None):
        self.scopes.append({})
        if extra:
            for info, node in extra:
                self.declare(info, node)
        for s in stmts:
            self.stmt(s)
        self.scopes.pop()

    def snapshot(self):
        return [v.moved for v in self.all]

    def branches(self, fns, exhaustive):
        snap = self.snapshot()
        n = len(snap)
        results = []
        for fn in fns:
            for v, m in zip(self.all, snap):
                v.moved = m
            fn()
            results.append([v.moved for v in self.all[:n]])
        if not exhaustive:
            results.append(snap)
        for i, v in enumerate(self.all[:n]):
            v.moved = next((r[i] for r in results if r[i] is not None), None)

    # ----- statements
    def stmt(self, s):
        getattr(self, "s_" + s.kind)(s)

    def s_Let(self, s):
        if getattr(s, "const", False) and (len(self.scopes) > 1 or self.in_func is not None):
            self.err(s, PLACE_P, "Constants must be defined at the top level of the file.", "Use `let %s be ...` here instead." % s.name)
        self.take(s.expr, "into `%s`" % s.name)
        k = self.skind(s.expr)
        if s.type is not None:
            want = static_kind_of_type(s.type)
            if want in self.variants:
                want = self.variants[want][0]
            if k is not None and want is not None and k != want:
                fix = "Give it %s." % type_desc(s.type)
                if want == "number" and k == "text":
                    fix = "Convert the text first:  (<the text> as number) or else 0"
                elif want == "text" and k == "number":
                    fix = "Put it inside text:  \"{x}\"   or convert:  x as text"
                self.err(s, TYPE_P, "`%s` should be %s, but it's given %s." % (s.name, type_desc(s.type), kind_words(k)), fix)
            k = want
        info = VarInfo(s.name, "let", s.changeable, self.bigness(s.expr), s.line, self.loop)
        info.kind = k
        self.declare(info, s)

    def root_of(self, tg):
        while tg.kind in ("Field", "Index", "Key"):
            if tg.kind == "Index":
                self.visit(tg.index)
            if tg.kind == "Key":
                self.visit(tg.key)
            tg = tg.obj
        return tg

    def mutable(self, tg, verb):
        root = self.root_of(tg)
        if root.kind != "Name":
            self.err(tg, CHANGE_P, "Only variables (and their parts) can be changed.")
        info = self.lookup(root)
        if self.crossed_lambda(root.name):
            self.err(root, CHANGE_P, "A `given` task can't %s `%s` - it only has a read-only copy of values from outside." % (verb, root.name),
                     "Give the new value back from the task instead, and change `%s` outside it." % root.name)
        if info.par < self.par and info.role not in ("function", "builtin", "type"):
            self.err(root, OWN_P, "You can't %s `%s` inside `at the same time` - several jobs would change it at once (a data race)." % (verb, root.name),
                     "Send results through a channel instead:\n    let results be a new channel\n    ... send value to results ...\n    for each r in results: ...")
        if not info.changeable or info.role == "global":
            self.not_changeable(root, info, verb)
        for li in self.looping:
            if li is info and verb in ("add to", "remove from"):
                self.err(tg, OWN_P, "You can't %s `%s` while looping over it - the loop would lose its place." % (verb, info.name),
                         "Collect the changes in a separate list during the loop, and apply them after it ends.")
        return info

    def not_changeable(self, node, info, verb):
        n = info.name
        if info.role == "let":
            self.err(node, CHANGE_P,
                     "You tried to %s `%s`, but it was created with plain `let`%s, so it can never change." %
                     (verb, n, " on line %d" % info.line if info.line else ""),
                     "If it really needs to change, create it as changeable:\n    let changeable %s be ..." % n)
        if info.role == "param":
            self.err(node, CHANGE_P,
                     "You tried to %s `%s`, but this task only *looks* at that input (it's shared, read-only)." % (verb, n),
                     "To let the task change it, mark the input changeable in the task header:\n"
                     "    to %s ... changeable %s ...:\nand lend it when calling:  %s with lend <variable>"
                     % (self.in_func.name if self.in_func else "task", n, self.in_func.name if self.in_func else "task"))
        if info.role == "item":
            self.err(node, CHANGE_P,
                     "You tried to %s `%s`, but loop items and matched values are read-only." % (verb, n),
                     "To change items while looping, write:  for each changeable %s in <list>:" % n)
        if info.role == "global":
            self.err(node, CHANGE_P,
                     "Tasks can't change top-level variables like `%s` - that would be hidden shared state." % n,
                     "Pass it in instead: add `changeable %s` to the task's inputs and call it with `lend %s`." % (n, n))
        self.err(node, CHANGE_P, "`%s` is a %s, not a variable, so it can't be changed." %
                 (n, {"function": "task", "builtin": "built-in task", "type": "type"}.get(info.role, "name")))

    def s_Change(self, s):
        self.take(s.expr, "into `%s`" % target_desc(s.target))
        if s.target.kind == "Name":
            info = self.mutable(s.target, "change")
            k = self.skind(s.expr)
            if info.kind and k and k != info.kind:
                self.err(s, TYPE_P, "`%s` holds %s, so it can't become %s." % (info.name, kind_words(info.kind), kind_words(k)),
                         "Keep it %s, or make a separate variable for the new value:\n    let %s_%s be ..." % (kind_words(info.kind), info.name, k if k.islower() else "new"))
            info.moved = None
            if info.big is not True:
                info.big = self.bigness(s.expr) or info.big
        else:
            self.mutable(s.target, "change")
            self.visit_target(s.target)

    def visit_target(self, tg):
        r = tg
        while r.kind in ("Field", "Index", "Key"):
            r = r.obj
        self.visit(r)

    def s_Increase(self, s):
        self.visit(s.expr)
        self.mutable(s.target, "increase" if s.sign > 0 else "decrease")
        self.visit_target(s.target)

    def s_Add(self, s):
        self.take(s.expr, "into `%s`" % target_desc(s.target))
        self.mutable(s.target, "add to")
        self.visit_target(s.target)

    def s_Remove(self, s):
        self.visit(s.expr)
        self.mutable(s.target, "remove from")
        self.visit_target(s.target)

    def s_Say(self, s):
        if s.expr is not None:
            self.visit(s.expr)
            self.static_showable(s.expr)

    def static_showable(self, e):
        k = self.skind(e)
        if k == "maybe":
            self.err(e, MISSING_P, "This might be nothing, so Lekh won't print it directly. (Lekh has no null.)",
                     "Decide what to show when it's missing:  {value or else \"unknown\"}\n"
                     "or use `when value:` with `is some v:` and `is nothing:`")
        if k == "result":
            self.err(e, MISSING_P, "This is a result that might be a problem, so Lekh won't print it directly.",
                     "Use `when value:` with `is ok v:` / `is problem why:`, or give a fallback:  value or else ...")

    STATIC_BUILTIN_KIND = {"length": "number", "sum": "number", "round": "number", "absolute": "number", "sqrt": "number",
                           "random": "number", "uppercase": "text", "lowercase": "text", "trimmed": "text",
                           "capitalized": "text", "join": "text", "replace": "text", "words": "list", "lines": "list",
                           "letters": "list", "sorted": "list", "keys": "list", "values": "list", "split": "list",
                           "position": "maybe"}

    def skind(self, e):
        """Best-effort static kind of an expression (None = unknown)."""
        k = e.kind
        if k == "Num" or k == "Neg":
            return "number"
        if k in ("Str", "Ask"):
            return "text"
        if k in ("Bool", "Compare", "Logic", "Not", "Test", "TypeTest"):
            return "truth"
        if k in ("ListLit", "EmptyList"):
            return "list"
        if k in ("MapLit", "EmptyMap"):
            return "map"
        if k in ("NothingLit", "Key"):
            return "maybe"
        if k == "Wrap":
            return "maybe" if e.tag == "some" else "result"
        if k == "Convert":
            if e.type.name in ("text", "list", "set"):
                return e.type.name
            return "result"
        if k == "Copy":
            return self.skind(e.expr)
        if k == "Construct":
            if e.tname in self.records:
                return e.tname
            if e.tname in self.variants:
                return self.variants[e.tname][0]
            return None
        if k == "Name":
            info = self.lookup_raw(e.name)
            return info.kind if info else None
        if k == "Arith":
            a, b = self.skind(e.l), self.skind(e.r)
            if a == "number" and b == "number":
                return "number"
            if e.op == "+" and a == "text" and b == "text":
                return "text"
            return None
        if k == "Call":
            info = self.lookup_raw(e.name)
            if info and info.role == "function" and e.name in self.funcs:
                r = self.funcs[e.name].ret
                return static_kind_of_type(r) if r is not None else None
            if info and info.role == "builtin":
                return self.STATIC_BUILTIN_KIND.get(e.name)
        return None

    def static_math(self, e):
        a, b = self.skind(e.l), self.skind(e.r)
        for kk, side in ((a, e.l), (b, e.r)):
            if kk == "maybe":
                nm = side.name if side.kind == "Name" else "value"
                self.err(side, MISSING_P,
                         "%s might be nothing, so it can't be used in math yet. Lekh has no null - a maybe value must be checked before use."
                         % ("`%s`" % nm if nm != "value" else "This value"),
                         "Give a fallback:   (%s or else 0)\nor check it first:\n    when %s:\n        is some v: ...\n        is nothing: ..." % (nm, nm))
            if kk == "result":
                self.err(side, MISSING_P, "This is a result that might be a problem, so it can't be used in math yet.",
                         "Unwrap it first:  try value   (inside a task)\nor give a fallback:  value or else 0")
        if e.op == "+" and {a, b} == {"text", "number"}:
            self.err(e, TYPE_P, "Can't add text and a number.",
                     "Put the value inside the text instead:  \"Total: {total}\"\nor turn text into a number:  (x as number) or else 0")
        if e.op != "+" and "text" in (a, b):
            self.err(e, TYPE_P, "Only numbers can be used with `%s`, but one side is text." % e.op,
                     "Convert text to a number first:  (x as number) or else 0")

    def static_compare(self, e):
        a, b = self.skind(e.l), self.skind(e.r)
        simple = ("number", "text", "truth")
        if e.op == "is" and a in simple and b in simple and a != b:
            self.err(e, TYPE_P, "You're comparing %s with %s - those can never be equal." % (kind_words(a), kind_words(b)),
                     "Convert one side first:  (x as number) or else 0   or   x as text")
        if e.op == "is" and "maybe" in (a, b) and (a in simple or b in simple):
            self.err(e, MISSING_P, "One side might be nothing, so it can't be compared with a plain value directly.",
                     "Give a fallback first:  (value or else 0) is 5\nor match the wrapper:  value is some 5")

    def s_If(self, s):
        fns = []
        for cond, body in s.branches:
            self.visit(cond)
            fns.append(lambda b=body: self.block(b))
        if s.other is not None:
            fns.append(lambda: self.block(s.other))
        self.branches(fns, s.other is not None)

    def s_ForEach(self, s):
        self.visit(s.iterable)
        if s.changeable:
            it = s.iterable
            if it.kind not in ("Name", "Field", "Index", "Key"):
                self.err(s, CHANGE_P, "`for each changeable` needs a variable to loop over, so changes have somewhere to go.")
            self.mutable(it, "change the items of")
        looped = None
        if s.iterable.kind == "Name":
            looped = self.lookup_raw(s.iterable.name)
            self.looping.append(looped)
        self.loop += 1
        if s.parallel:
            self.par += 1
        names = s.tvars if s.tvars else [s.var] + ([s.var2] if s.var2 else [])
        extra = [(VarInfo(n, "item", changeable=s.changeable, line=s.line, loop=self.loop), s) for n in names]
        self.branches([lambda: self.block(s.body, extra)], False)
        if s.parallel:
            self.par -= 1
        self.loop -= 1
        if looped is not None:
            self.looping.pop()

    def s_ForRange(self, s):
        self.visit(s.start)
        self.visit(s.end)
        if s.step is not None:
            self.visit(s.step)
        self.loop += 1
        if s.parallel:
            self.par += 1
        self.branches([lambda: self.block(s.body, [(VarInfo(s.var, "item", line=s.line, loop=self.loop), s)])], False)
        if s.parallel:
            self.par -= 1
        self.loop -= 1

    def s_Repeat(self, s):
        self.visit(s.count)
        self.loop += 1
        self.branches([lambda: self.block(s.body)], False)
        self.loop -= 1

    def s_While(self, s):
        self.visit(s.cond)
        self.loop += 1
        self.branches([lambda: self.block(s.body)], False)
        self.loop -= 1

    def s_Stop(self, s):
        if self.loop == 0:
            self.err(s, PLACE_P, "`stop` only works inside a loop (for each, repeat, while).",
                     "To end a task early, use `give back`.")

    def s_Skip(self, s):
        if self.loop == 0:
            self.err(s, PLACE_P, "`skip` only works inside a loop (for each, repeat, while).")

    def s_FuncDef(self, s):
        self.err(s, PLACE_P, "Tasks must be defined at the top level of the file, not inside another block.",
                 "Move `to %s ...:` to the left edge of the file." % s.name)

    def s_RecordDef(self, s):
        self.err(s, PLACE_P, "Records must be defined at the top level of the file.")

    def s_ChoiceDef(self, s):
        self.err(s, PLACE_P, "Choices must be defined at the top level of the file.")

    def s_Use(self, s):
        self.err(s, PLACE_P, "`use` must be at the top level of the file (usually the first lines).")

    def s_Return(self, s):
        if self.in_test and self.in_func is None:
            self.err(s, PLACE_P, "`give back` can't be used inside a test block.")
        if self.in_func is None:
            self.err(s, PLACE_P, "`give back` only works inside a task (a block that starts with `to`).",
                     "To end the whole program early, use:  fail \"reason\"")
        if s.expr is not None:
            self.visit(s.expr)

    def s_Fail(self, s):
        self.visit(s.expr)

    def s_ExprStmt(self, s):
        e = s.expr
        method_like = e.kind == "Field" and not any(e.name in fl for fl in self.records.values()) and \
            not any(e.name in v[1] for v in self.variants.values())
        if not self.repl and not method_like and e.kind not in ("Call", "RunCall", "Try", "Fail", "Ask", "MethodCall", "OrElse", "WaitFor", "Take", "Receive", "Start"):
            if e.kind == "Name" and self.lookup_raw(e.name) and self.lookup_raw(e.name).role == "function":
                self.err(s, SYNTAX, "To run the task `%s`, write `run %s` (or `%s with ...` if it needs inputs)." % (e.name, e.name, e.name))
            self.err(s, SYNTAX, "This line works out a value but doesn't do anything with it.",
                     "To show it, write:  say ...\nTo keep it, write:  let result be ...")
        self.visit(e)

    def s_When(self, s):
        self.visit(s.subject)
        covered, kinds = set(), set()
        inner = {"some": [], "ok": [], "problem": []}
        catch_all = False
        fns = []
        for pats, body, line, guard in s.cases:
            names = []
            for p in pats:
                b = []
                self.pat_check(p, b, kinds, True)
                if len(pats) > 1 and b:
                    self.err(p, CASE_P, "A case with several options joined by `or` can't name values.",
                             "Split it into separate `is` cases.")
                if guard is None:
                    cov = self.pat_covers(p)
                    if cov == "all":
                        catch_all = True
                    elif cov:
                        covered.add(cov)
                    if p.pk in inner and getattr(p, "sub", None) is not None:
                        inner[p.pk].append(p.sub)
                names = b
            extra = [(VarInfo(n, "item", line=line, loop=self.loop), s) for n in names]
            fns.append(lambda body=body, extra=extra, guard=guard: self.case_block(body, extra, guard))
        if s.other is not None:
            fns.append(lambda: self.block(s.other))
        elif not catch_all:
            for wrap, subs in inner.items():
                if wrap not in covered and subs and self.subs_cover(subs):
                    covered.add(wrap)
            for k in kinds:
                if k[0] == "choice":
                    missing = [v for v in self.choices[k[1]] if v not in covered]
                    if missing:
                        self.err(s, CASE_P,
                                 "This `when` doesn't say what to do for: %s. Every option of `%s` must be handled, "
                                 "so nothing slips through." % (", ".join(missing), k[1]),
                                 "Add a case for each, e.g.:\n    is %s%s: ...\nor add `otherwise:` at the end." %
                                 (missing[0], (" with " + ", ".join(self.variants[missing[0]][1])) if self.variants[missing[0]][1] else ""))
                elif k[0] == "maybe":
                    for need, ex in (("some", "is some value: ..."), ("nothing", "is nothing: ...")):
                        if need not in covered:
                            self.err(s, CASE_P, "This `when` handles a maybe value but not the `%s` case." % need, "Add:  " + ex)
                elif k[0] == "result":
                    for need, ex in (("ok", "is ok value: ..."), ("problem", "is problem why: ...")):
                        if need not in covered:
                            self.err(s, CASE_P, "This `when` handles a result but not the `%s` case." % need, "Add:  " + ex)
                elif k[0] == "value":
                    self.err(s, CASE_P, "When matching plain values (numbers, text, groups, or cases with `if`), there's always something you didn't list.",
                             "Add an `otherwise:` case at the end for everything else.")
            if not kinds and any(c[3] is not None for c in s.cases):
                self.err(s, CASE_P, "Every case here has an `if` condition, so some values might match none of them.",
                         "Add an `otherwise:` case at the end.")
        self.branches(fns, True)

    def case_block(self, body, extra, guard):
        self.scopes.append({})
        for info, node in extra:
            self.declare(info, node)
        if guard is not None:
            self.visit(guard)
        for st in body:
            self.stmt(st)
        self.scopes.pop()

    def irrefutable(self, p):
        return p.pk in ("bind", "any") or (p.pk == "tuple" and all(self.irrefutable(x) for x in p.items))

    def pat_covers(self, p):
        if self.irrefutable(p):
            return "all"
        if p.pk == "variant" and all(self.irrefutable(x) for x in p.subs):
            return p.name
        if p.pk == "some" and self.irrefutable(p.sub):
            return "some"
        if p.pk == "nothing":
            return "nothing"
        if p.pk in ("ok", "problem") and (p.sub is None or self.irrefutable(p.sub)):
            return p.pk
        return None

    def pat_check(self, p, binds, kinds, top):
        pk = p.pk
        if pk == "bind":
            if p.name in binds:
                self.err(p, CASE_P, "The name `%s` is used twice in this case." % p.name)
            binds.append(p.name)
        elif pk == "variant":
            if p.name not in self.variants:
                if p.name in self.records:
                    self.err(p, CASE_P, "`%s` is a record, not an option of a choice. Use `if x is a %s:` instead." % (p.name, p.name))
                sg = suggest(p.name, list(self.variants))
                self.err(p, NAME_P, "I don't know an option called `%s`." % p.name, ("Did you mean `%s`?" % sg) if sg else None)
            cname, fields = self.variants[p.name]
            if p.subs and len(p.subs) != len(fields):
                self.err(p, CASE_P, "`%s` has %d field%s (%s), but this case names %d." %
                         (p.name, len(fields), "" if len(fields) == 1 else "s", ", ".join(fields) or "none", len(p.subs)),
                         "is %s with %s:" % (p.name, ", ".join(fields)) if fields else "is %s:" % p.name)
            if top:
                kinds.add(("choice", cname))
            for x in p.subs:
                self.pat_check(x, binds, kinds, False)
        elif pk in ("some", "nothing"):
            if top:
                kinds.add(("maybe",))
            if pk == "some":
                self.pat_check(p.sub, binds, kinds, False)
        elif pk in ("ok", "problem"):
            if top:
                kinds.add(("result",))
            if p.sub is not None:
                self.pat_check(p.sub, binds, kinds, False)
        elif pk == "tuple":
            if top and not self.irrefutable(p):
                kinds.add(("value",))
            for x in p.items:
                self.pat_check(x, binds, kinds, False)
        elif pk in ("lit", "range"):
            if top:
                kinds.add(("value",))

    def bigness(self, e):
        k = e.kind
        if k in ("ListLit", "MapLit", "EmptyList", "EmptyMap", "Construct", "Copy"):
            return True
        if k == "Name":
            info = self.lookup_raw(e.name)
            return info.big if info else None
        if k == "Wrap":
            return self.bigness(e.expr)
        if k in ("Num", "Str", "Bool", "Arith", "Neg", "Logic", "Not", "Compare", "Test", "TypeTest", "Ask", "NothingLit"):
            return False
        return None

    def take(self, e, how, explicit=False):
        self.visit(e)
        if e.kind == "Name":
            info = self.lookup(e)
            if info.role in ("function", "builtin", "type"):
                return
            big = self.bigness(e)
            if big or (explicit and big is not False):
                self.move(info, e, how)

    def move(self, info, node, how):
        n = info.name
        if info.role == "global":
            self.err(node, OWN_P, "A task can't give away the top-level value `%s` - the rest of the program still owns it." % n,
                     "Give away a copy instead:  copy of %s" % n)
        if info.par < self.par:
            self.err(node, OWN_P, "`%s` can't be given away inside `at the same time` - it belongs to the code outside." % n,
                     "Give away a copy instead:  copy of %s" % n)
        if self.crossed_lambda(n):
            self.err(node, OWN_P, "A `given` task only has a read-only copy of `%s`, so it can't give it away." % n,
                     "Give away a copy instead:  copy of %s" % n)
        if info.loop < self.loop:
            self.err(node, OWN_P,
                     "`%s` is given away (%s) inside a loop. On the second time round it would already be gone." % (n, how),
                     "Give away a copy each time:  copy of %s\nor create `%s` inside the loop." % (n, n))
        info.moved = (node.line, how)

    def visit(self, e):
        if e is None:
            return
        k = e.kind
        if k == "Name":
            info = self.lookup(e)
            if info.role == "global" and info.changeable:
                self.err(e, OWN_P, "Tasks can't reach out to the changeable top-level variable `%s`." % e.name,
                         "Pass it in as an input instead (use `lend %s` if the task must change it)." % e.name)
            if info.moved:
                ln, how = info.moved
                self.err(e, OWN_P,
                         "`%s` can't be used here because it was given away on line %d (moved %s). "
                         "Each list, map or record has exactly one owner at a time." % (e.name, ln, how),
                         "If you still need `%s`, give away a copy on line %d instead:\n    copy of %s" % (e.name, ln, e.name))
            return
        if k == "Call":
            self.call(e)
            return
        if k == "Lambda":
            self.visit_lambda(e)
            return
        if k == "HOF":
            self.visit_hof(e)
            return
        if k in ("TupleLit", "SetLit"):
            for it in e.items:
                self.take(it, "into a group" if k == "TupleLit" else "into a set")
            return
        if k == "Take":
            self.mutable(e.target, "take from")
            self.visit_target(e.target)
            return
        if k == "MethodCall":
            self.visit(e.obj)
            for a in e.args:
                if a.mode == "give":
                    self.take(a.expr, "to the task `%s`" % e.name, explicit=True)
                elif a.mode == "lend":
                    if a.expr.kind != "Name":
                        self.err(a, OWN_P, "Only a variable can be lent.")
                    li = self.lookup(a.expr)
                    if not li.changeable:
                        self.not_changeable(a.expr, li, "lend")
                else:
                    self.visit(a.expr)
            return
        if k == "Start":
            c = e.call
            if c.kind == "Call":
                self.lookup(c)
                for a in c.args:
                    if a.mode == "lend":
                        self.err(a, OWN_P, "A background job can't borrow `%s` - it might outlive this code." % target_desc(a.expr),
                                 "Pass it normally (the job gets its own copy) or hand it over with `give`.")
                    if a.mode == "give":
                        self.take(a.expr, "to a background job", explicit=True)
                    else:
                        self.visit(a.expr)
            else:
                self.visit(c)
            return
        if k == "RunCall":
            info = self.lookup(e)
            if info.role == "function" and self.funcs[e.name].params:
                ps = self.funcs[e.name].params
                self.err(e, CALL_P, "`%s` needs %d input%s, so it's called with `with`." % (e.name, len(ps), "" if len(ps) == 1 else "s"),
                         "%s with %s" % (e.name, ", ".join(("lend " if p.changeable else "") + p.name for p in ps)))
            if info.role == "builtin":
                self.err(e, CALL_P, "`%s` needs inputs." % e.name, "%s of <value>" % e.name)
            return
        if k == "ListLit":
            for it in e.items:
                self.take(it, "into a list")
            return
        if k == "MapLit":
            for kk, vv in e.pairs:
                self.visit(kk)
                self.take(vv, "into a map")
            return
        if k == "Construct":
            self.construct(e)
            return
        if k == "Wrap":
            self.take(e.expr, "into `%s`" % e.tag)
            return
        if k == "Str":
            for p in e.parts:
                if isinstance(p, Node):
                    self.visit(p)
                    self.static_showable(p)
            return
        if k == "Arith":
            self.visit(e.l)
            self.visit(e.r)
            self.static_math(e)
            return
        if k == "Compare":
            self.visit(e.l)
            self.visit(e.r)
            self.static_compare(e)
            return
        for attr in ("expr", "l", "r", "obj", "index", "key", "prompt", "lo", "hi", "start", "end", "step",
                     "channel", "job", "cond", "yes", "no"):
            v = getattr(e, attr, None)
            if isinstance(v, Node):
                self.visit(v)

    def construct(self, e):
        tn = e.tname
        if tn in self.records:
            declared = self.records[tn]
        elif tn in self.variants:
            declared = self.variants[tn][1]
        else:
            return
        check_fields(e, tn, declared, [f for f, _ in e.fields])
        for fn, fe in e.fields:
            self.take(fe, "into the %s" % tn)

    def call(self, e):
        info = self.lookup(e)
        args = e.args
        if info.role == "type":
            self.err(e, SYNTAX, "`%s` is a type; build one with field names." % e.name, "%s with field value, field value" % e.name)
        if info.role == "function":
            fd = self.funcs[e.name]
            ps = fd.params
            if len(ps) != len(args):
                if not ps:
                    self.err(e, CALL_P, "`%s` takes no inputs." % e.name, "run %s" % e.name)
                self.err(e, CALL_P, "`%s` needs %d input%s (%s), but this line gives it %d." %
                         (e.name, len(ps), "" if len(ps) == 1 else "s", ", ".join(p.name for p in ps), len(args)),
                         "%s with %s" % (e.name, ", ".join(("lend " if p.changeable else "") + p.name for p in ps)))
            for p, a in zip(ps, args):
                if a.mode == "lend" and not p.changeable:
                    self.err(a, CALL_P, "`%s` only looks at its input `%s`, so there's no need to lend it." % (e.name, p.name),
                             "Remove `lend` here (or mark the input `changeable %s` in the task header)." % p.name)
                if a.mode == "share" and p.changeable:
                    self.err(a, CALL_P, "`%s` may change its input `%s`, so you need to lend it on purpose." % (e.name, p.name),
                             "Write `lend` before it:  %s with %s" % (e.name, ", ".join(("lend " if q.changeable else "") + q.name for q in ps)))
        elif info.role == "builtin":
            lo, hi = BUILTIN_ARITY[e.name]
            if not (lo <= len(args) <= hi):
                need = str(lo) if lo == hi else "%d or %d" % (lo, hi)
                self.err(e, CALL_P, "The built-in task `%s` needs %s input%s, but this line gives it %d." %
                         (e.name, need, "" if hi == 1 else "s", len(args)), BUILTIN_HELP.get(e.name))
            for a in args:
                if a.mode == "lend":
                    self.err(a, CALL_P, "Built-in tasks never change their inputs, so there's no need to lend.", "Remove `lend`.")
        lent = []
        for a in args:
            if a.mode == "lend":
                if a.expr.kind != "Name":
                    self.err(a, OWN_P, "Only a variable can be lent (so the changes have somewhere to go).", "lend my_list")
                li = self.lookup(a.expr)
                self.visit(a.expr)
                if not li.changeable:
                    if li.role == "let":
                        self.err(a, CHANGE_P, "To lend `%s`, it must be changeable, but it was created with plain `let`." % li.name,
                                 "let changeable %s be ..." % li.name)
                    self.not_changeable(a.expr, li, "lend")
                lent.append(a.expr.name)
            elif a.mode == "give":
                self.take(a.expr, "to the task `%s`" % e.name, explicit=True)
            else:
                self.visit(a.expr)
        for n in lent:
            count = sum(1 for a in args for x in iter_names(a.expr) if x.name == n)
            if count > 1:
                self.err(e, OWN_P,
                         "`%s` is lent to `%s` (so it may change it) and also used again in the same call. "
                         "Lekh allows either one changer or many readers at a time, never both." % (n, e.name),
                         "Pass two different values, or make a copy first:  let other be copy of %s" % n)

    # ---------------- Stage 1+ statements
    def check_can(self, s):
        if s.tname not in self.records and s.tname not in self.choices:
            sg = suggest(s.tname, list(self.records) + list(self.choices))
            self.err(s, NAME_P, "I don't know a record or choice called `%s`." % s.tname, ("Did you mean `%s`?" % sg) if sg else None)
        ab = self.abilities.get(s.ability)
        if ab is None:
            sg = suggest(s.ability, list(self.abilities))
            self.err(s, NAME_P, "I don't know an ability called `%s`." % s.ability,
                     ("Did you mean `%s`?" % sg) if sg else "Declare it first:\n    ability %s:\n        to describe gives text" % s.ability)
        for m in ab.methods:
            mine = self.methods.get((s.tname, m.name))
            if mine is None:
                if m.body is not None:
                    continue  # the ability provides a default
                self.err(s, ABILITY_P, "`%s` says it can `%s`, but it has no task called `%s`." % (s.tname, s.ability, m.name),
                         "Add it:\n    to %s's %s%s%s:\n        ..." % (s.tname, m.name,
                                                                 (" " + ", ".join(p.name for p in m.params)) if m.params else "",
                                                                 (" gives " + type_src(m.ret)) if m.ret else ""))
            if len(mine.params) != len(m.params):
                self.err(mine, CALL_P, "`%s`'s task `%s` must take %d input%s to match the ability `%s`." %
                         (s.tname, m.name, len(m.params), "" if len(m.params) == 1 else "s", s.ability))
            if bool(mine.changes_me) != bool(m.changes_me):
                self.err(mine, CALL_P, "`%s` in the ability `%s` %s, so `%s`'s version must match." %
                         (m.name, s.ability, "changes me" if m.changes_me else "doesn't change me", s.tname))
            if m.ret is not None and (mine.ret is None or type_src(mine.ret) != type_src(m.ret)) and not getattr(m.ret, "var", False):
                self.err(mine, TYPE_P, "`%s`'s task `%s` must give back %s to match the ability `%s`." %
                         (s.tname, m.name, type_desc(m.ret), s.ability), "to %s's %s ... gives %s:" % (s.tname, m.name, type_src(m.ret)))

    def s_Can(self, s):
        self.err(s, PLACE_P, "`%s can %s` must be at the top level of the file." % (s.tname, s.ability))

    def s_AbilityDef(self, s):
        self.err(s, PLACE_P, "Abilities must be defined at the top level of the file.")

    def s_TestBlock(self, s):
        self.err(s, PLACE_P, "`test` blocks must be at the top level of the file.")

    def s_Expect(self, s):
        self.visit(s.expr)
        if s.other is not None:
            self.visit(s.other)

    def s_LetTuple(self, s):
        self.take(s.expr, "into (%s)" % ", ".join(s.names))
        seen = set()
        for n in s.names:
            if n in seen:
                self.err(s, SYNTAX, "The name `%s` appears twice." % n)
            seen.add(n)
            self.declare(VarInfo(n, "let", s.changeable, None, s.line, self.loop), s)

    def s_Defer(self, s):
        self.block(s.body)

    def s_Parallel(self, s):
        self.par += 1
        fns = [lambda st=st: self.block([st]) for st in s.body]
        self.branches(fns, False)
        self.par -= 1

    def s_Send(self, s):
        self.visit(s.channel)
        self.take(s.expr, "into a channel", explicit=True)

    def s_Close(self, s):
        self.visit(s.expr)

    def s_Sleep(self, s):
        self.visit(s.expr)

    def find_scope(self, name):
        for i in range(len(self.scopes) - 1, -1, -1):
            if name in self.scopes[i]:
                return self.scopes[i][name], i
        return None, -1

    def crossed_lambda(self, name):
        info, i = self.find_scope(name)
        return info is not None and self.floors and i < self.floors[-1] and info.role not in ("function", "builtin", "type")

    def visit_lambda(self, e):
        self.floors.append(len(self.scopes))
        old_loop, old_func = self.loop, self.in_func
        self.loop = 0
        self.scopes.append({})
        for p in e.params:
            self.declare(VarInfo(p.name, "param", line=p.line), p)
        if e.expr is not None:
            self.visit(e.expr)
        else:
            self.in_func = e
            self.block(e.body)
        self.scopes.pop()
        self.floors.pop()
        self.loop, self.in_func = old_loop, old_func

    def visit_hof(self, e):
        self.visit(e.src)
        if e.init is not None:
            self.visit(e.init)
        self.scopes.append({})
        self.declare(VarInfo(e.var, "item", line=e.line, loop=self.loop), e)
        if e.acc:
            self.declare(VarInfo(e.acc, "item", line=e.line, loop=self.loop), e)
        self.visit(e.body)
        self.scopes.pop()

    def subs_cover(self, pats):
        """Do these (unguarded) patterns together match every possible value?"""
        if any(self.irrefutable(p) for p in pats):
            return True
        names = set(p.name for p in pats if p.pk == "variant" and all(self.irrefutable(x) for x in p.subs))
        for p in pats:
            if p.pk == "variant" and p.name in self.variants:
                cname = self.variants[p.name][0]
                return all(v in names for v in self.choices[cname])
        return False


KNOWN_ABILITIES = set()


def static_kind_of_type(t):
    if t is None or t.name == "anything" or getattr(t, "var", False) or t.name in KNOWN_ABILITIES:
        return None
    if t.name in ("integer", "decimal"):
        return "number"
    return t.name


def check_fields(e, tn, declared, provided):
    seen = set()
    for f in provided:
        if f in seen:
            raise LekhError(SYNTAX, "The field `%s` is given twice." % f, e.line, None, e.file)
        seen.add(f)
        if f not in declared:
            s = suggest(f, declared)
            raise LekhError(NAME_P, "A `%s` has no field called `%s`.%s" % (tn, f, (" Did you mean `%s`?" % s) if s else ""),
                            e.line, "Its fields are: " + (", ".join(declared) or "(none)"), e.file)
    missing = [f for f in declared if f not in seen]
    if missing:
        raise LekhError(TYPE_P, "A `%s` needs: %s. Missing: %s." % (tn, ", ".join(declared), ", ".join(missing)),
                        e.line, "%s with %s" % (tn, ", ".join("%s ..." % f for f in declared)), e.file)


# =====================================================================================
#  Interpreter
# =====================================================================================
class Slot:
    def __init__(self, value, changeable=False, mode="own", line=None, role="let"):
        self._v = value
        self.changeable, self.mode, self.line, self.role = changeable, mode, line, role
        self.moved = None
        self.shared = False
        self.kind = kind_of(value)

    def get(self):
        return self._v

    def set(self, v):
        self._v = v


class LentSlot(Slot):
    """A mutable borrow: reads and writes go straight to the caller's variable."""

    def __init__(self, target, line):
        self.target = target
        self.changeable, self.mode, self.line, self.role = True, "lent", line, "param"
        self.moved = None
        self.kind = target.kind

    def get(self):
        return self.target.get()

    def set(self, v):
        self.target.set(v)


class Env:
    def __init__(self, parent=None, boundary=False):
        self.vars, self.parent, self.boundary = {}, parent, boundary

    def find(self, name):
        e, crossed = self, None
        while e is not None:
            if name in e.vars:
                return e.vars[name], crossed
            if e.boundary:
                crossed = "parallel" if (e.boundary == "parallel" and crossed is None) else ("task" if e.boundary != "parallel" else crossed)
            e = e.parent
        return None, None

    def names(self):
        out, e = set(), self
        while e is not None:
            out.update(e.vars.keys())
            e = e.parent
        return out


class StopSignal(Exception):
    pass


class SkipSignal(Exception):
    pass


class ReturnSignal(Exception):
    def __init__(self, value, from_try=None):
        self.value, self.from_try = value, from_try


FRESH = {"Num", "Str", "Bool", "NothingLit", "Wrap", "Call", "RunCall", "Arith", "Neg", "Logic", "Not", "Compare",
         "Test", "TypeTest", "Convert", "ListLit", "MapLit", "EmptyList", "EmptyMap", "Copy", "Ask", "Construct"}
MAX_DEPTH = 2000


class Interp:
    def __init__(self, loader, out=None):
        import threading
        self.loader = loader
        self.module_envs = {}
        self.tl = threading.local()
        self.print_lock = threading.Lock()
        self.builtins = Env()
        self.test_mode = False
        self.program_args = []
        self.workers = 0
        self.worker_lock = threading.Lock()
        for name, (fn, lo, hi) in BUILTINS.items():
            self.builtins.vars[name] = Slot(Builtin(name, fn, lo, hi), role="builtin")
        from .stdlib import BUILTIN_RECORDS
        for name, rt in BUILTIN_RECORDS.items():
            self.builtins.vars[name] = Slot(rt, role="type")

    @property
    def depth(self):
        return getattr(self.tl, "depth", 0)

    @depth.setter
    def depth(self, v):
        self.tl.depth = v

    def err(self, node, title, msg, fix=None):
        raise LekhError(title, msg, node.line, fix, node.file)

    # ---------------- modules
    def run_module(self, mod, env=None):
        if mod.path in self.module_envs:
            return self.module_envs[mod.path]
        g = env or Env(self.builtins)
        self.module_envs[mod.path] = g
        self.run_stmts(mod.ast, g)
        return g

    DECL_ORDER = (("Use",), ("RecordDef", "ChoiceDef", "AbilityDef"), ("FuncDef",), ("Can",))
    DECLS = ("Use", "RecordDef", "ChoiceDef", "AbilityDef", "FuncDef", "Can", "TestBlock")

    def run_stmts(self, stmts, g, repl=False):
        g.is_global = True
        for kinds in self.DECL_ORDER:
            for s in stmts:
                if s.kind in kinds:
                    self.exec(s, g)
        if not hasattr(g, "defers"):
            g.defers = []
        last = None
        try:
            for s in stmts:
                if s.kind in self.DECLS:
                    continue
                if self.test_mode and s.kind not in ("Let", "LetTuple"):
                    continue
                if repl and s.kind == "ExprStmt":
                    last = self.eval(s.expr, g, want=False)
                    if last is not None:
                        print(show(last, True))
                else:
                    self.exec(s, g)
        except ReturnSignal as r:
            n = r.from_try
            why = show(r.value.value) if isinstance(r.value, Problem) else "nothing"
            raise LekhError(UNHANDLED_P,
                            "A `try` here got %s, and there's no task around it to pass the problem up to."
                            % ("the problem: " + why if isinstance(r.value, Problem) else "nothing (a missing value)"),
                            n.line if n else None,
                            "Handle it right here, e.g.:\n    when <value>:\n        is ok v: ...\n        is problem why: say why\n"
                            "or give a fallback:  <value> or else <default>", n.file if n else None)
        finally:
            defers, g.defers = g.defers, []
            for body in reversed(defers):
                self.exec_block(body, g)

    def run_tests(self, mod):
        """Run the `test` blocks of a module. Returns [(test_node, error_or_None)]."""
        self.test_mode = True
        g = Env(self.builtins)
        self.module_envs[mod.path] = g
        self.run_stmts(mod.ast, g)
        out = []
        for s in mod.ast:
            if s.kind != "TestBlock":
                continue
            try:
                self.exec_block(s.body, g)
                out.append((s, None))
            except LekhError as ex:
                out.append((s, ex))
            except ReturnSignal as r:
                out.append((s, LekhError(UNHANDLED_P, "A `try` inside this test got a problem: %s" % show(r.value), s.line, None, s.file)))
        return out

    def find(self, node, env, name=None):
        name = name or node.name
        slot, crossed = env.find(name)
        if slot is None:
            fh = foreign_hint(name)
            s = suggest(name, env.names())
            self.err(node, NAME_P, "I don't know anything called `%s` here." % name,
                     fh or (("Did you mean `%s`?" % s) if s else "Create it first with:  let %s be ..." % name))
        return slot, crossed

    def moved_error(self, node, name, moved):
        ln, how = moved
        self.err(node, OWN_P,
                 "`%s` can't be used here because it was given away on line %d (moved %s). "
                 "Each list, map or record has exactly one owner at a time." % (name, ln, how),
                 "If you still need `%s`, give away a copy on line %d instead:\n    copy of %s" % (name, ln, name))

    def take(self, e, env, how, explicit=False):
        """Evaluate a value that is being stored somewhere new (moves owned variables, copies parts)."""
        if e.kind == "Name":
            v = self.e_Name(e, env)
            slot, crossed = env.find(e.name)
            if slot.role in ("function", "builtin", "type"):
                return v
            if is_big(v) or explicit:
                if crossed == "parallel" and is_big(v):
                    self.err(e, OWN_P, "`%s` can't be given away inside `at the same time` - it belongs to the code outside." % e.name,
                             "Give away a copy instead:  copy of %s" % e.name)
                if crossed and is_big(v):
                    self.err(e, OWN_P, "A task can't give away the top-level value `%s`." % e.name,
                             "Give away a copy instead:  copy of %s" % e.name)
                if slot.mode == "shared" and is_big(v):
                    self.err(e, OWN_P,
                             "`%s` is only borrowed for reading here (shared), so it can't be given away %s." % (e.name, how),
                             "Give away a copy instead:  copy of %s" % e.name)
                if slot.mode == "lent" and is_big(v):
                    self.err(e, OWN_P,
                             "`%s` is only lent to this task - it still belongs to the caller - so it can't be given away %s."
                             % (e.name, how), "Give away a copy instead:  copy of %s" % e.name)
                slot.moved = (e.line, how)
            return v
        v = self.eval(e, env)
        if e.kind not in FRESH and is_big(v):
            v = deep_copy(v)
        return v

    def truth(self, v, node, what="`if`"):
        if isinstance(v, bool):
            return v
        if isinstance(v, (Some, NothingType)):
            self.err(node, MISSING_P, "%s needs true or false, but this is a maybe value (it might be nothing)." % what,
                     "Check it directly:  if x is nothing:   or   if x is some:")
        self.err(node, TYPE_P, "%s needs true or false, but got %s." % (what, describe(v)),
                 "Compare it to something, e.g.:  if x is 5:   or   if x is not 0:")

    def no_maybe(self, v, node, doing):
        if isinstance(v, (Some, NothingType)):
            nm = node.name if getattr(node, "kind", "") == "Name" else "value"
            label = "`%s`" % nm if nm != "value" else "This value"
            self.err(node, MISSING_P,
                     "%s might be nothing (right now it's %s), so it can't be %s yet. "
                     "Lekh has no null - a maybe value must be checked before use." % (label, show(v), doing),
                     "Give a fallback:   (%s or else 0)\nor check it first:\n    when %s:\n        is some v: ...\n        is nothing: ..." % (nm, nm))
        if isinstance(v, (Ok, Problem)):
            self.err(node, MISSING_P,
                     "This is a result that might be a problem (%s), so it can't be %s yet." % (show(v), doing),
                     "Unwrap it first:  try value   (inside a task)\nor give a fallback:  value or else 0\nor use `when` with `is ok v:` / `is problem why:`")
        if v is None:
            self.err(node, TYPE_P, "This task doesn't give back a value, so there's nothing to use here.",
                     "Add a `give back ...` line to the task.")

    def showable(self, v, node):
        if isinstance(v, (Some, NothingType, Ok, Problem)) or v is None:
            if isinstance(v, (Some, NothingType)):
                self.err(node, MISSING_P, "This might be nothing, so Lekh won't print it directly.",
                         "Decide what to show when it's missing:  {value or else \"unknown\"}\n"
                         "or use `when value:` with `is some v:` and `is nothing:`")
            self.no_maybe(v, node, "printed")
        return show(v)

    def check_type(self, v, t, node, what):
        if matches_type(v, t):
            return
        fix = "Give it %s." % type_desc(t)
        if t.name == "number" and isinstance(v, str):
            fix = "Convert the text first:  (%s as number) or else 0" % show(v, True)
        elif t.name == "text" and is_num(v):
            fix = "Put it inside text:  \"{x}\"   or convert:  x as text"
        elif t.name == "maybe" and matches_type(v, t.args[0]):
            fix = "Wrap it:  some %s" % show(v, True)
        elif t.name == "result" and matches_type(v, t.args[0]):
            fix = "Wrap it:  ok %s" % show(v, True)
        self.err(node, TYPE_P, "%s should be %s, but it's %s." % (what, type_desc(t), describe(v)), fix)

    def check_kind(self, old_kind, v, node, name):
        new = kind_of(v)
        if old_kind and old_kind != "unknown" and new != old_kind:
            self.err(node, TYPE_P, "`%s` holds %s, so it can't become %s." % (name, kind_words(old_kind), describe(v)),
                     "Keep it %s, or make a separate variable for the new value:\n    let %s_%s be ..." % (kind_words(old_kind), name, new if new.islower() else "new"))

    def check_elem(self, lst, v, node, name):
        et = getattr(lst, "elem_type", None)
        if et is not None and et.name == "anything":
            return
        if et is not None:
            if not matches_type(v, et):
                self.err(node, TYPE_P, "`%s` holds %s, so you can't put %s in it." % (name, type_desc(et) if et.name != "anything" else "anything", describe(v)))
            return
        if lst.items:
            k0, k = kind_of(lst.items[0]), kind_of(v)
            if k != k0:
                if name == "this list":
                    self.err(node, TYPE_P, "This list holds %s, so it can't also hold %s. A list holds one kind of thing."
                             % (kind_words(k0), describe(v)),
                             "If the list is an input to a task, wrap it in parentheses so the task's other inputs\n"
                             "aren't swallowed:  join with (list of 1, 2, 3), \"-\"\n"
                             "To group different kinds of data, use a record.\n"
                    "If they share an ability, say so:  let shapes as list of Shape be list of ...")
                self.err(node, TYPE_P, "`%s` holds %s, so you can't put %s in it. A list holds one kind of thing."
                         % (name, kind_words(k0), describe(v)),
                         "Convert the value first, or use a record to group different kinds of data together.")

    def check_looping(self, obj, node, name, verb):
        if getattr(obj, "looping", 0):
            self.err(node, OWN_P, "You can't %s `%s` while looping over it - the loop would lose its place." % (verb, name),
                     "Collect the changes in a separate list during the loop, and apply them after it ends.")

    def root_slot(self, tg, env, verb):
        r = tg
        while r.kind in ("Field", "Index", "Key"):
            r = r.obj
        if r.kind != "Name":
            self.err(tg, CHANGE_P, "Only variables (and their parts) can be changed.")
        slot, crossed = self.find(r, env)
        if crossed == "parallel":
            self.err(r, OWN_P, "You can't change `%s` inside `at the same time` - several jobs would change it at once (a data race)." % r.name,
                     "Send results through a channel instead, and collect them after the block.")
        if crossed:
            self.err(r, CHANGE_P, "Tasks can't change top-level variables like `%s`." % r.name,
                     "Add `changeable %s` to the task's inputs and call it with `lend %s`." % (r.name, r.name))
        if not slot.changeable:
            if slot.mode == "shared" or slot.role == "param":
                self.err(r, CHANGE_P, "You tried to %s `%s`, but this task only looks at that input (read-only)." % (verb, r.name),
                         "Mark the input `changeable %s` in the task header and call it with `lend`." % r.name)
            if slot.role == "item":
                self.err(r, CHANGE_P, "You tried to %s `%s`, but loop items and matched values are read-only." % (verb, r.name),
                         "for each changeable %s in <list>:" % r.name)
            if slot.role in ("function", "builtin", "type"):
                self.err(r, CHANGE_P, "`%s` is not a variable, so it can't be changed." % r.name)
            self.err(r, CHANGE_P, "You tried to %s `%s`, but it was created with plain `let`, so it can never change." % (verb, r.name),
                     "If it really needs to change, create it as changeable:\n    let changeable %s be ..." % r.name)
        if tg is not r and slot.moved:
            self.moved_error(r, r.name, slot.moved)
        return slot, r

    def index_of(self, obj, idx, node, name):
        if not is_num(idx) or (isinstance(idx, float) and not idx.is_integer()):
            self.no_maybe(idx, node, "used as a position")
            self.err(node, TYPE_P, "A position must be a whole number, but got %s." % describe(idx), "item 1 of %s" % name)
        idx = int(idx)
        size = len(obj.items) if isinstance(obj, PList) else len(obj)
        if idx < 1 or idx > size:
            what = "item" if isinstance(obj, PList) else "letter"
            if size == 0:
                msg = "`%s` is empty, so there is no %s %d." % (name, what, idx)
            else:
                msg = "`%s` has %d %s%s, so there is no %s %d. (Positions start at 1.)" % (name, size, what, "" if size == 1 else "s", what, idx)
            self.err(node, RANGE_P, msg, "Check the size first:  if %d is at most length of %s: ..." % (idx, name))
        return idx - 1

    # ---------------- statements
    def exec_block(self, stmts, env):
        e = Env(env)
        try:
            for s in stmts:
                self.exec(s, e)
        finally:
            defers = getattr(e, "defers", None)
            if defers:
                e.defers = []
                for body in reversed(defers):
                    self.exec_block(body, e)

    def exec(self, s, env):
        return getattr(self, "x_" + s.kind)(s, env)

    def x_Let(self, s, env):
        if s.type is not None and s.type.name == "list" and s.expr.kind == "ListLit":
            v = self.e_ListLit(s.expr, env, s.type.args[0])
        elif s.type is not None and s.type.name == "map" and s.expr.kind == "MapLit":
            v = self.e_MapLit(s.expr, env, s.type.args[1])
        else:
            v = self.take(s.expr, env, "into `%s`" % s.name)
        if v is None:
            self.no_maybe(v, s.expr, "stored")
        if s.type is not None:
            self.check_type(v, s.type, s, "`%s`" % s.name)
        slot = Slot(v, s.changeable, "own", s.line, "let")
        slot.shared = getattr(s, "shared", False)
        if s.type is not None and s.type.name in ("maybe", "result"):
            slot.kind = s.type.name
        if s.type is not None and s.type.name == "list" and isinstance(v, PList):
            v.elem_type = s.type.args[0]
        if s.type is not None and s.type.name == "map" and isinstance(v, PMap):
            v.val_type = s.type.args[1]
        env.vars[s.name] = slot

    def x_Change(self, s, env):
        tg = s.target
        slot, root = self.root_slot(tg, env, "change")
        v = self.take(s.expr, env, "into `%s`" % target_desc(tg))
        self.no_maybe(v, s.expr, "stored") if v is None else None
        if tg.kind == "Name":
            self.check_kind(slot.kind, v, s, tg.name)
            slot.set(v)
            slot.moved = None
        else:
            self.assign(tg, v, env, s)

    def assign(self, tg, v, env, s):
        name = target_desc(tg.obj)
        obj = self.eval(tg.obj, env)
        if tg.kind == "Field":
            if isinstance(obj, Variant):
                self.err(s, CHANGE_P, "The fields of an option like `%s` can't be changed one by one." % obj.vtype.name,
                         "Make a new one instead:  change %s to %s with ..." % (name, obj.vtype.name))
            if not isinstance(obj, Record):
                self.no_maybe(obj, s, "changed")
                self.err(s, TYPE_P, "`%s` is %s, which has no fields." % (name, describe(obj)))
            if tg.name not in obj.fields:
                sg = suggest(tg.name, list(obj.fields))
                self.err(s, NAME_P, "A `%s` has no field called `%s`.%s" % (obj.rtype.name, tg.name, (" Did you mean `%s`?" % sg) if sg else ""),
                         "Its fields are: " + ", ".join(obj.fields))
            ftype = dict(obj.rtype.fields).get(tg.name)
            if ftype is not None:
                self.check_type(v, ftype, s, "The field `%s`" % tg.name)
            else:
                self.check_kind(kind_of(obj.fields[tg.name]), v, s, "%s's %s" % (name, tg.name))
            obj.fields[tg.name] = v
        elif tg.kind == "Index":
            idx = self.eval(tg.index, env)
            if isinstance(obj, str):
                self.err(s, CHANGE_P, "Text can't be changed letter by letter.", "Build new text instead, e.g. with replace.")
            if not isinstance(obj, PList):
                self.no_maybe(obj, s, "changed")
                self.err(s, TYPE_P, "`item ... of` needs a list, but `%s` is %s." % (name, describe(obj)))
            i = self.index_of(obj, idx, tg, name)
            self.check_kind(kind_of(obj.items[i]), v, s, "items of " + name)
            obj.items[i] = v
        elif tg.kind == "Key":
            key = self.eval(tg.key, env)
            if not isinstance(obj, PMap):
                self.no_maybe(obj, s, "changed")
                self.err(s, TYPE_P, "`at` works with maps, but `%s` is %s." % (name, describe(obj)),
                         "For lists use:  change item 2 of %s to ..." % name)
            self.check_key(obj, key, s, name)
            vt = getattr(obj, "val_type", None)
            if vt is not None:
                if not matches_type(v, vt):
                    self.err(s, TYPE_P, "`%s` holds %s values, so it can't hold %s." % (name, type_desc(vt), describe(v)))
            elif obj.d:
                k0 = next(iter(obj.d.values()))
                if key in obj.d:
                    k0 = obj.d[key]
                self.check_kind(kind_of(k0), v, s, "values of " + name)
            if key not in obj.d:
                self.check_looping(obj, s, name, "add new keys to")
            obj.d[key] = v

    def check_key(self, m, key, node, name):
        if not (isinstance(key, str) or is_num(key)) or isinstance(key, bool):
            self.no_maybe(key, node, "used as a key")
            self.err(node, TYPE_P, "Map keys must be text or numbers, but got %s." % describe(key))
        if m.d:
            k0 = kind_of(next(iter(m.d)))
            if kind_of(key) != k0:
                self.err(node, TYPE_P, "`%s` uses %s as keys, so %s can't be a key." % (name, kind_words(k0), describe(key)))

    def x_Increase(self, s, env):
        verb = "increase" if s.sign > 0 else "decrease"
        slot, root = self.root_slot(s.target, env, verb)
        if slot.moved:
            self.moved_error(root, root.name, slot.moved)
        cur = self.eval(s.target, env)
        amt = self.eval(s.expr, env)
        for v, n in ((cur, s.target), (amt, s.expr)):
            self.no_maybe(v, n, "%sd" % verb)
            if not is_num(v):
                self.err(n, TYPE_P, "Only numbers can be %sd, but this is %s." % (verb, describe(v)),
                         "To add to text or a list, use:  add <value> to %s" % target_desc(s.target) if verb == "increase" else None)
        new = cur + amt * s.sign
        if s.target.kind == "Name":
            slot.set(new)
        else:
            self.assign(s.target, new, env, s)

    def x_Add(self, s, env):
        slot, root = self.root_slot(s.target, env, "add to")
        if slot.moved:
            self.moved_error(root, root.name, slot.moved)
        name = target_desc(s.target)
        tv = self.eval(s.target, env)
        v = self.take(s.expr, env, "into `%s`" % name)
        if isinstance(tv, PList):
            self.check_looping(tv, s, name, "add to")
            self.check_elem(tv, v, s, name)
            tv.items.append(v)
        elif isinstance(tv, PSet):
            self.check_looping(tv, s, name, "add to")
            tv.s.add(self.set_value(tv, v, s.expr))
        elif isinstance(tv, str):
            if not isinstance(v, str):
                self.err(s, TYPE_P, "`%s` is text, so only text can be added to it, not %s." % (name, describe(v)),
                         "Put the value inside text:  add \"{value}\" to %s" % name)
            if s.target.kind == "Name":
                slot.set(tv + v)
            else:
                self.assign(s.target, tv + v, env, s)
        elif is_num(tv):
            self.err(s, TYPE_P, "`%s` is a number. To add to a number, use `increase`." % name, "increase %s by ..." % name)
        elif isinstance(tv, PMap):
            self.err(s, TYPE_P, "To put something in the map `%s`, give it a key." % name, "change %s at \"key\" to value" % name)
        else:
            self.no_maybe(tv, s, "added to")
            self.err(s, TYPE_P, "You can only add to a list or text, but `%s` is %s." % (name, describe(tv)))

    def x_Remove(self, s, env):
        slot, root = self.root_slot(s.target, env, "remove from")
        if slot.moved:
            self.moved_error(root, root.name, slot.moved)
        name = target_desc(s.target)
        tv = self.eval(s.target, env)
        v = self.eval(s.expr, env)
        if isinstance(tv, PList):
            self.check_looping(tv, s, name, "remove from")
            if s.by_pos:
                i = self.index_of(tv, v, s, name)
                tv.items.pop(i)
                return
            for i, x in enumerate(tv.items):
                if eq_struct(x, v):
                    tv.items.pop(i)
                    return
            self.err(s, RANGE_P, "%s isn't in `%s`, so it can't be removed." % (show(v, True), name),
                     "Check first:  if %s contains %s: ..." % (name, show(v, True)))
        elif isinstance(tv, PSet):
            self.check_looping(tv, s, name, "remove from")
            if v not in tv.s:
                self.err(s, RANGE_P, "%s isn't in the set `%s`, so it can't be removed." % (show(v, True), name),
                         "Check first:  if %s contains %s: ..." % (name, show(v, True)))
            tv.s.discard(v)
        elif isinstance(tv, PMap):
            self.check_looping(tv, s, name, "remove from")
            if v not in tv.d or isinstance(v, (bool, PList)):
                self.err(s, RANGE_P, "The map `%s` has no key %s." % (name, show(v, True)),
                         "Check first:  if %s contains %s: ..." % (name, show(v, True)))
            del tv.d[v]
        else:
            self.no_maybe(tv, s, "removed from")
            self.err(s, TYPE_P, "You can only remove from a list or map, but `%s` is %s." % (name, describe(tv)))

    def x_Say(self, s, env):
        if s.expr is None:
            text = ""
        else:
            text = self.showable(self.eval(s.expr, env), s.expr)
        with self.print_lock:
            print(text, flush=True)

    def x_If(self, s, env):
        for cond, body in s.branches:
            if self.truth(self.eval(cond, env), cond):
                self.exec_block(body, env)
                return
        if s.other is not None:
            self.exec_block(s.other, env)

    def iter_source(self, it, node, changeable):
        """Return (owner_for_looping_flag, list_of_keys) for a loopable value."""
        if isinstance(it, PList):
            return it, list(range(len(it.items)))
        if isinstance(it, PMap):
            return it, list(it.d.keys())
        if isinstance(it, PSet):
            if changeable:
                self.err(node, CHANGE_P, "Items of a set can't be changed in a loop.", "Remove the old value and add the new one after the loop.")
            return it, sorted_items(it)
        if isinstance(it, (str, Tuple)):
            if changeable:
                self.err(node, CHANGE_P, "Letters of text (or parts of a group) can't be changed in a loop.")
            return None, list(range(len(it) if isinstance(it, str) else len(it.items)))
        self.no_maybe(it, node, "looped over")
        self.err(node, TYPE_P, "`for each` needs a list, map, set, text or channel, but got %s." % describe(it),
                 "To count, write:  for each n from 1 to 10:")

    def bind_loop_vars(self, s, e, first, second, it, owned=False):
        if s.tvars:
            if not isinstance(first, Tuple) or len(first.items) != len(s.tvars):
                self.err(s, TYPE_P, "`for each (%s)` needs groups of %d values, but got %s." % (", ".join(s.tvars), len(s.tvars), describe(first)))
            for n, v in zip(s.tvars, first.items):
                e.vars[n] = Slot(v, False, "shared" if is_big(v) else "own", s.line, "item")
            return None, None
        if isinstance(it, PMap) and s.var2 is None:
            s1 = Slot(first, False, "own", s.line, "item")
        else:
            lendable = s.changeable and isinstance(it, PList)
            s1 = Slot(first, lendable, "lent" if lendable else ("shared" if is_big(first) and not owned else "own"), s.line, "item")
        e.vars[s.var] = s1
        s2 = None
        if s.var2:
            if isinstance(it, PMap):
                s2 = Slot(second, s.changeable, "lent" if s.changeable else ("shared" if is_big(second) else "own"), s.line, "item")
            else:
                s2 = Slot(second, False, "own", s.line, "item")
            e.vars[s.var2] = s2
        return s1, s2

    def element_at(self, it, key, pos):
        if isinstance(it, PList):
            return it.items[key], pos + 1
        if isinstance(it, PMap):
            return key, it.d[key]
        if isinstance(it, PSet):
            return key, pos + 1
        if isinstance(it, Tuple):
            return it.items[key], pos + 1
        return it[key], pos + 1

    def x_ForEach(self, s, env):
        it = self.eval(s.iterable, env)
        if s.changeable:
            if s.parallel:
                self.err(s, OWN_P, "Items can't be changed in an `at the same time` loop.", "Collect results through a channel instead.")
            self.root_slot(s.iterable, env, "change the items of")
        if isinstance(it, Channel):
            if s.parallel:
                self.err(s, SYNTAX, "Reading a channel `at the same time` isn't supported - read it with a plain `for each`.")
            while True:
                got = self.receive(it, s)
                if got is NOTHING:
                    break
                e = Env(env)
                self.bind_loop_vars(s, e, got.value, None, PList(), owned=True)
                try:
                    self.exec_block(s.body, e)
                except SkipSignal:
                    pass
                except StopSignal:
                    break
            return
        owner, seq = self.iter_source(it, s.iterable, s.changeable)
        if s.parallel:
            def job(pos, key):
                first, second = self.element_at(it, key, pos)
                e = Env(Env(env, boundary="parallel"))
                self.bind_loop_vars(s, e, first, second, it)
                try:
                    self.exec_block(s.body, e)
                except (SkipSignal, StopSignal):
                    pass
            if owner is not None:
                owner.looping += 1
            try:
                self.run_parallel([lambda p=p, k=k: job(p, k) for p, k in enumerate(seq)], s)
            finally:
                if owner is not None:
                    owner.looping -= 1
            return
        if owner is not None:
            owner.looping += 1
        try:
            for pos, key in enumerate(seq):
                e = Env(env)
                if isinstance(it, PList) and key >= len(it.items):
                    break
                first, second = self.element_at(it, key, pos)
                s1, s2 = self.bind_loop_vars(s, e, first, second, it)
                stop = False
                try:
                    self.exec_block(s.body, e)
                except SkipSignal:
                    pass
                except StopSignal:
                    stop = True
                if s.changeable:
                    if isinstance(it, PList):
                        it.items[key] = s1.get()
                    elif isinstance(it, PMap) and s2 is not None:
                        it.d[key] = s2.get()
                if stop:
                    break
        finally:
            if owner is not None:
                owner.looping -= 1

    def whole(self, v, n, what="A counting loop"):
        self.no_maybe(v, n, "used to count")
        if not is_num(v) or (isinstance(v, float) and not v.is_integer()):
            self.err(n, TYPE_P, "%s needs whole numbers, but got %s." % (what, describe(v)), "for each n from 1 to 10:")
        return int(v)

    def counting(self, a, b, step, node):
        if step is None:
            step = 1 if b >= a else -1
        if step == 0:
            self.err(node, RANGE_P, "Counting `by 0` would never finish.", "Use a step like `by 2` or `by -1`.")
        if (b - a) * step < 0:
            return range(0)
        return range(a, b + (1 if step > 0 else -1), step)

    def x_ForRange(self, s, env):
        a = self.whole(self.eval(s.start, env), s.start)
        b = self.whole(self.eval(s.end, env), s.end)
        step = self.whole(self.eval(s.step, env), s.step) if s.step is not None else None
        seq = self.counting(a, b, step, s)
        if s.parallel:
            def job(i):
                e = Env(Env(env, boundary="parallel"))
                e.vars[s.var] = Slot(i, False, "own", s.line, "item")
                try:
                    self.exec_block(s.body, e)
                except (SkipSignal, StopSignal):
                    pass
            self.run_parallel([lambda i=i: job(i) for i in seq], s)
            return
        for i in seq:
            e = Env(env)
            e.vars[s.var] = Slot(i, False, "own", s.line, "item")
            try:
                self.exec_block(s.body, e)
            except SkipSignal:
                continue
            except StopSignal:
                break

    def x_Repeat(self, s, env):
        n = self.eval(s.count, env)
        self.no_maybe(n, s.count, "used as a count")
        if not is_num(n) or (isinstance(n, float) and not n.is_integer()) or n < 0:
            self.err(s.count, TYPE_P, "`repeat` needs a whole number of times (0 or more), but got %s." % describe(n), "repeat 3 times:")
        for _ in range(int(n)):
            try:
                self.exec_block(s.body, env)
            except SkipSignal:
                continue
            except StopSignal:
                break

    def x_While(self, s, env):
        while self.truth(self.eval(s.cond, env), s.cond, "`while`"):
            try:
                self.exec_block(s.body, env)
            except SkipSignal:
                continue
            except StopSignal:
                break

    def x_Stop(self, s, env):
        raise StopSignal()

    def x_Skip(self, s, env):
        raise SkipSignal()

    def x_FuncDef(self, s, env):
        if s.owner:
            slot, _ = env.find(s.owner)
            t = slot.get() if slot else None
            if not isinstance(t, (RecordType, ChoiceType, AbilityType)):
                self.err(s, NAME_P, "I don't know a record or choice called `%s` to add the task `%s` to." % (s.owner, s.name))
            if s.body is not None:
                t.methods[s.name] = Function(s, env)
            return
        slot = Slot(Function(s, env), role="function")
        slot.shared = getattr(s, "shared", False)
        env.vars[s.name] = slot

    def x_AbilityDef(self, s, env):
        slot = Slot(AbilityType(s.name, s), role="type")
        slot.shared = s.shared
        env.vars[s.name] = slot

    def x_Can(self, s, env):
        tslot, _ = env.find(s.tname)
        aslot, _ = env.find(s.ability)
        t, ab = (tslot.get() if tslot else None), (aslot.get() if aslot else None)
        if not isinstance(t, (RecordType, ChoiceType)) or not isinstance(ab, AbilityType):
            self.err(s, NAME_P, "`%s can %s` needs a record/choice and an ability." % (s.tname, s.ability))
        for m in ab.node.methods:
            if m.name not in t.methods:
                if m.body is None:
                    self.err(s, ABILITY_P, "`%s` says it can `%s`, but it has no task called `%s`." % (s.tname, s.ability, m.name))
                t.methods[m.name] = ab.methods.get(m.name) or Function(m, env)
        ABILITY_IMPLS.setdefault(s.tname, set()).add(s.ability)

    def x_Return(self, s, env):
        if s.expr is None:
            raise ReturnSignal(None)
        e = s.expr
        if e.kind == "Name":
            v = self.e_Name(e, env)
            slot, crossed = env.find(e.name)
            if is_big(v) and (slot.mode in ("shared", "lent") or crossed):
                self.err(e, OWN_P, "This task only borrowed `%s`, so it can't give it back as its own result." % e.name,
                         "Give back a copy instead:  give back copy of %s" % e.name)
            raise ReturnSignal(v)
        v = self.eval(e, env)
        if e.kind not in FRESH and is_big(v):
            v = deep_copy(v)
        raise ReturnSignal(v)

    def x_RecordDef(self, s, env):
        slot = Slot(RecordType(s.name, s.fields), role="type")
        slot.shared = getattr(s, "shared", False)
        env.vars[s.name] = slot

    def x_ChoiceDef(self, s, env):
        ct = ChoiceType(s.name)
        slot = Slot(ct, role="type")
        slot.shared = getattr(s, "shared", False)
        env.vars[s.name] = slot
        for vn, fields, _ in s.variants:
            vt = VariantType(ct, vn, fields)
            ct.variants[vn] = vt
            vs = Slot(vt, role="type")
            vs.shared = slot.shared
            env.vars[vn] = vs

    def x_When(self, s, env):
        v = self.eval(s.subject, env)
        for pats, body, line, guard in s.cases:
            for p in pats:
                b = {}
                if self.match(p, v, s, b):
                    e = Env(env)
                    fresh = s.subject.kind in FRESH or s.subject.kind in ("MethodCall", "Take", "Receive", "WaitFor", "HOF", "TupleLit")
                    for n, bv in b.items():
                        e.vars[n] = Slot(bv, False, "shared" if (is_big(bv) and not fresh) else "own", line, "item")
                    if guard is not None and not self.truth(self.eval(guard, e), guard, "The `if` of a case"):
                        continue
                    self.exec_block(body, e)
                    return
        if s.other is not None:
            self.exec_block(s.other, env)
            return
        self.err(s, CASE_P, "No case in this `when` matches %s." % describe(v),
                 "Add `otherwise:` at the end to handle everything else.")

    def match(self, p, v, node, b):
        pk = p.pk
        if pk == "bind":
            b[p.name] = v
            return True
        if pk == "any":
            return True
        if pk == "some":
            return isinstance(v, Some) and self.match(p.sub, v.value, node, b)
        if pk == "nothing":
            return v is NOTHING
        if pk in ("ok", "problem"):
            C = Ok if pk == "ok" else Problem
            return isinstance(v, C) and (p.sub is None or self.match(p.sub, v.value, node, b))
        if pk == "tuple":
            return isinstance(v, Tuple) and len(v.items) == len(p.items) and all(self.match(x, y, node, b) for x, y in zip(p.items, v.items))
        if pk in ("lit", "range"):
            self.no_maybe(v, node, "matched against plain values")
            if pk == "range":
                if not is_num(v):
                    self.err(node, TYPE_P, "A `from ... to ...` case needs a number, but got %s." % describe(v))
                return p.lo <= v <= p.hi
            if kind_of(v) != kind_of(p.value):
                self.err(p, TYPE_P, "This case compares %s with %s, which can never match." % (describe(v), describe(p.value)),
                         "Convert first, e.g.  when answer as number:")
            return eq_struct(v, p.value)
        if pk == "variant":
            if isinstance(v, Variant):
                if v.vtype.name != p.name:
                    return False
                vals = list(v.fields.values())
                if p.subs and len(p.subs) != len(vals):
                    self.err(p, CASE_P, "`%s` has %d fields, but this case names %d." % (p.name, len(vals), len(p.subs)))
                return all(self.match(x, y, node, b) for x, y in zip(p.subs, vals))
            self.no_maybe(v, node, "matched")
            self.err(node, TYPE_P, "This case expects an option like `%s`, but the value is %s." % (p.name, describe(v)))
        return False

    def x_Use(self, s, env):
        mod = self.loader.modules[s.path]
        menv = self.run_module(mod)
        allowed = expand_import(s.names, mod)
        for n, slot in menv.vars.items():
            exportable = slot.shared and (slot.role in ("function", "type") or (slot.role == "let" and not slot.changeable))
            if exportable and (allowed is None or n in allowed):
                env.vars[n] = slot
        if s.names:
            for n in s.names:
                if n not in menv.vars or not menv.vars[n].shared:
                    self.err(s, NAME_P, "The module `%s` doesn't share anything called `%s`." % (s.module, n))

    def x_Fail(self, s, env):
        self.e_Fail(s, env)

    def x_ExprStmt(self, s, env):
        self.eval(s.expr, env, want=False)

    # ---------------- expressions
    def eval(self, e, env, want=True):
        if e.kind == "Call":
            return self.e_Call(e, env, want)
        if e.kind == "RunCall":
            return self.e_RunCall(e, env, want)
        if e.kind == "MethodCall":
            return self.e_MethodCall(e, env, want)
        if e.kind == "WaitFor":
            return self.e_WaitFor(e, env, want)
        return getattr(self, "e_" + e.kind)(e, env)

    def e_Num(self, e, env):
        return e.value

    def e_Bool(self, e, env):
        return e.value

    def e_NothingLit(self, e, env):
        return NOTHING

    def e_Str(self, e, env):
        out = []
        for p in e.parts:
            if isinstance(p, str):
                out.append(p)
            else:
                out.append(self.showable(self.eval(p, env), p))
        return "".join(out)

    def e_Name(self, e, env):
        slot, crossed = self.find(e, env)
        if slot.moved:
            self.moved_error(e, e.name, slot.moved)
        if crossed == "task" and slot.changeable:
            self.err(e, OWN_P, "Tasks can't reach out to the changeable top-level variable `%s`." % e.name,
                     "Pass it in as an input instead (use `lend %s` if the task must change it)." % e.name)
        v = slot.get()
        if isinstance(v, Builtin) and v.hi == 0:
            return v.fn(self, e, [])
        return v

    def e_Wrap(self, e, env):
        v = self.take(e.expr, env, "into `%s`" % e.tag)
        self.no_maybe(v, e.expr, "wrapped") if v is None else None
        return {"some": Some, "ok": Ok, "problem": Problem}[e.tag](v)

    def e_Arith(self, e, env):
        a, b = self.eval(e.l, env), self.eval(e.r, env)
        op = e.op
        word = {"+": "added", "-": "subtracted", "*": "multiplied", "/": "divided", "mod": "used with mod", "div": "divided"}[op]
        self.no_maybe(a, e.l, "used in math")
        self.no_maybe(b, e.r, "used in math")
        if is_num(a) and is_num(b):
            if op == "+":
                return a + b
            if op == "-":
                return a - b
            if op == "*":
                return a * b
            if b == 0:
                self.err(e, MATH_P, "Can't divide by zero.", "Check the number first:  if divisor is not 0: ...")
            if op == "/":
                if isinstance(a, int) and isinstance(b, int) and a % b == 0:
                    return a // b
                return a / b
            if op == "div":
                return int(a // b)
            return a % b
        if op == "+" and isinstance(a, str) and isinstance(b, str):
            return a + b
        if op == "+" and isinstance(a, PList) and isinstance(b, PList):
            return PList([deep_copy(x) for x in a.items + b.items])
        if isinstance(a, PSet) and isinstance(b, PSet) and op in ("+", "-"):
            return PSet(set(a.s | b.s) if op == "+" else set(a.s - b.s))
        if op == "+" and (isinstance(a, str) or isinstance(b, str)):
            self.err(e, TYPE_P, "Can't add text and %s (%s + %s)." % (
                kind_words(kind_of(b if isinstance(a, str) else a)), show(a, True), show(b, True)),
                "Put the value inside the text instead:  \"Total: {total}\"\nor turn text into a number:  (x as number) or else 0")
        self.err(e, TYPE_P, "Only numbers can be %s, but this has %s and %s." % (word, describe(a), describe(b)),
                 "Convert text to a number first:  (x as number) or else 0")

    def e_Neg(self, e, env):
        v = self.eval(e.expr, env)
        self.no_maybe(v, e.expr, "made negative")
        if not is_num(v):
            self.err(e, TYPE_P, "Only numbers can be negative, but this is %s." % describe(v))
        return -v

    def e_Logic(self, e, env):
        a = self.truth(self.eval(e.l, env), e.l, "`%s`" % e.op)
        if e.op == "and" and not a:
            return False
        if e.op == "or" and a:
            return True
        return self.truth(self.eval(e.r, env), e.r, "`%s`" % e.op)

    def e_Not(self, e, env):
        return not self.truth(self.eval(e.expr, env), e.expr, "`not`")

    def equal(self, a, b, e):
        for x, y, xn in ((a, b, e.l), (b, a, e.r)):
            if isinstance(x, (Some, Ok, Problem)) and not isinstance(y, (Some, Ok, Problem, NothingType)):
                self.err(xn, MISSING_P, "This might be %s (%s), so it can't be compared with %s directly." %
                         ("nothing" if isinstance(x, Some) else "a problem", show(x), show(y, True)),
                         "Give a fallback first:  (value or else 0) is %s\nor match the wrapper:  value is some %s" % (show(y, True), show(y, True)))
        if a is NOTHING or b is NOTHING:
            return a is b
        if kind_of(a) != kind_of(b) and not (isinstance(a, (Some, Ok, Problem)) and isinstance(b, (Some, Ok, Problem))):
            fix = "Convert one side first:  (x as number) or else 0   or   x as text"
            self.err(e, TYPE_P, "You're comparing %s with %s - those can never be equal." % (describe(a), describe(b)), fix)
        return eq_struct(a, b)

    def e_Compare(self, e, env):
        a = self.eval(e.l, env)
        b = self.eval(e.r, env)
        op = e.op
        if op == "is":
            r = self.equal(a, b, e)
        elif op in (">", "<", ">=", "<="):
            self.no_maybe(a, e.l, "compared")
            self.no_maybe(b, e.r, "compared")
            if not ((is_num(a) and is_num(b)) or (isinstance(a, str) and isinstance(b, str))):
                self.err(e, TYPE_P, "Only two numbers (or two texts) can be compared by size, but this has %s and %s." % (describe(a), describe(b)),
                         "Convert text to a number first:  (x as number) or else 0")
            r = {">": a > b, "<": a < b, ">=": a >= b, "<=": a <= b}[op]
        elif op == "contains":
            self.no_maybe(a, e.l, "searched")
            if isinstance(a, PList):
                r = any(eq_struct(x, b) for x in a.items)
            elif isinstance(a, str):
                if not isinstance(b, str):
                    self.err(e, TYPE_P, "Text can only contain text, not %s." % describe(b), "x contains \"{value}\"")
                r = b in a
            elif isinstance(a, PMap):
                r = (isinstance(b, str) or is_num(b)) and not isinstance(b, bool) and b in a.d
            elif isinstance(a, PSet):
                self.no_maybe(b, e.r, "looked for")
                r = (not a.s or kind_of(next(iter(a.s))) == kind_of(b)) and b in a.s
            elif isinstance(a, Tuple):
                r = any(eq_struct(x, b) for x in a.items)
            else:
                self.err(e, TYPE_P, "`contains` works with lists, text, maps and sets, but got %s." % describe(a))
        else:
            if not (isinstance(a, str) and isinstance(b, str)):
                self.no_maybe(a, e.l, "checked")
                self.err(e, TYPE_P, "`%s with` works with text, but got %s and %s." % (op, describe(a), describe(b)))
            r = a.startswith(b) if op == "starts" else a.endswith(b)
        return (not r) if e.neg else r

    def e_Test(self, e, env):
        v = self.eval(e.expr, env)
        w = e.what
        if w in ("nothing", "some"):
            if not isinstance(v, (Some, NothingType)):
                r = False if w == "nothing" else True
            else:
                r = (v is NOTHING) if w == "nothing" else isinstance(v, Some)
        else:
            if not isinstance(v, (Ok, Problem)):
                self.err(e, TYPE_P, "`is %s` checks a result (ok/problem), but this is %s." % (w, describe(v)))
            r = isinstance(v, Ok) if w == "ok" else isinstance(v, Problem)
        return (not r) if e.neg else r

    def e_TypeTest(self, e, env):
        r = type_test_value(self.eval(e.expr, env), e.tname)
        return (not r) if e.neg else r

    def e_OrElse(self, e, env):
        v = self.eval(e.l, env)
        if isinstance(v, (Some, Ok)):
            return v.value
        if v is NOTHING or isinstance(v, Problem):
            return self.eval(e.r, env)
        return v

    def e_Try(self, e, env):
        v = self.eval(e.expr, env)
        if isinstance(v, (Some, Ok)):
            return v.value
        if v is NOTHING or isinstance(v, Problem):
            raise ReturnSignal(v, from_try=e)
        self.err(e, TYPE_P, "`try` is for values that might be a problem or nothing, but this is %s." % describe(v),
                 "Just use the value directly (remove `try`).")

    def e_Field(self, e, env):
        obj = self.eval(e.obj, env)
        name = target_desc(e.obj) if e.obj.kind in ("Name", "Field") else "this value"
        if isinstance(obj, (Record, Variant)) and e.name in obj.fields:
            return obj.fields[e.name]
        m = self.find_method(obj, e.name)
        if m is not None:
            return self.call_method(m, e, obj, [], env, True)
        if e.name in BUILTINS and not isinstance(obj, (Record, Variant)):
            b = self.builtins.vars[e.name].get()
            if b.lo <= 1 <= b.hi:
                self.no_maybe(obj, e.obj, "asked for `%s`" % e.name)
                return b.fn(self, e, [obj])
        if isinstance(obj, (Record, Variant)):
            tn = obj.rtype.name if isinstance(obj, Record) else obj.vtype.name
            sg = suggest(e.name, list(obj.fields))
            self.err(e, NAME_P, "A `%s` has no field called `%s`.%s" % (tn, e.name, (" Did you mean `%s`?" % sg) if sg else ""),
                     "Its fields are: " + (", ".join(obj.fields) or "(none)"))
        self.no_maybe(obj, e.obj, "asked for a field")
        self.err(e, TYPE_P, "`%s` is %s, so it has no field `%s`." % (name, describe(obj), e.name))

    def e_Key(self, e, env):
        obj = self.eval(e.obj, env)
        key = self.eval(e.key, env)
        name = target_desc(e.obj) if e.obj.kind in ("Name", "Field") else "this value"
        if isinstance(obj, PMap):
            self.no_maybe(key, e.key, "used as a key")
            if isinstance(key, (str, int, float)) and not isinstance(key, bool) and key in obj.d:
                return Some(obj.d[key])
            return NOTHING
        if isinstance(obj, PList):
            self.err(e, TYPE_P, "`at` looks things up in a map. For a list, ask for a position.", "item 2 of %s" % name)
        self.no_maybe(obj, e.obj, "looked up")
        self.err(e, TYPE_P, "`at` works with maps, but `%s` is %s." % (name, describe(obj)))

    def e_Index(self, e, env):
        obj = self.eval(e.obj, env)
        idx = self.eval(e.index, env)
        name = target_desc(e.obj) if e.obj.kind in ("Name", "Field") else "the list"
        if isinstance(obj, PList):
            return obj.items[self.index_of(obj, idx, e, name)]
        if isinstance(obj, str):
            return obj[self.index_of(obj, idx, e, name)]
        if isinstance(obj, Tuple):
            return obj.items[self.index_of(PList(list(obj.items)), idx, e, name)]
        self.no_maybe(obj, e.obj, "indexed")
        self.err(e, TYPE_P, "`item ... of` needs a list or text, but `%s` is %s." % (name, describe(obj)),
                 "For maps use:  %s at key" % name)

    def e_Convert(self, e, env):
        v = self.eval(e.expr, env)
        t = e.type.name
        if t == "text":
            self.no_maybe(v, e.expr, "turned into text")
            return show(v)
        if t == "number":
            if is_num(v):
                return Ok(v)
            if isinstance(v, str):
                s = v.strip().replace("_", "")
                try:
                    return Ok(int(s))
                except ValueError:
                    try:
                        f = float(s)
                        if f != f or f in (float("inf"), float("-inf")):
                            raise ValueError
                        return Ok(f)
                    except ValueError:
                        return Problem("\"%s\" is not a number" % v)
            self.no_maybe(v, e.expr, "turned into a number")
            return Problem("%s can't be turned into a number" % describe(v))
        if t in ("integer", "decimal"):
            if isinstance(v, str):
                txt = v.strip().replace("_", "")
                try:
                    v = int(txt)
                except ValueError:
                    try:
                        v = float(txt)
                        if v != v or v in (float("inf"), float("-inf")):
                            raise ValueError
                    except ValueError:
                        return Problem("\"%s\" is not a number" % txt)
            if not is_num(v):
                self.no_maybe(v, e.expr, "turned into a number")
                return Problem("%s can't be turned into a number" % describe(v))
            if t == "integer":
                if isinstance(v, float) and (v != v or v in (float("inf"), float("-inf"))):
                    return Problem("%s is not a whole number" % show(v))
                return Ok(int(v))
            return Ok(float(v))
        if t == "list" and isinstance(v, (PSet, Tuple, str, PMap)):
            return PList([deep_copy(x) for x in self.hof_items(v, e.expr)])
        if t == "set" and isinstance(v, (PList, Tuple, str)):
            out = PSet()
            for x in self.hof_items(v, e.expr):
                out.s.add(self.set_value(out, x, e.expr))
            return out
        self.err(e, TYPE_P, "`as` can turn values into text, number, integer, decimal, list or set - not `%s` from %s." % (type_src(e.type), describe(v)))

    def e_ListLit(self, e, env, elem_type=None):
        out = PList()
        if elem_type is not None:
            out.elem_type = elem_type
        for it in e.items:
            v = self.take(it, env, "into a list")
            self.no_maybe(v, it, "put in a list") if v is None else None
            self.check_elem(out, v, it, "this list")
            out.items.append(v)
        return out

    def e_MapLit(self, e, env, val_type=None):
        out = PMap()
        if val_type is not None:
            out.val_type = val_type
        for k, vv in e.pairs:
            key = self.eval(k, env)
            self.check_key(out, key, k, "this map")
            v = self.take(vv, env, "into a map")
            if val_type is not None:
                if not matches_type(v, val_type):
                    self.err(vv, TYPE_P, "This map holds %s values, so it can't hold %s." % (type_desc(val_type), describe(v)))
            elif out.d:
                k0 = kind_of(next(iter(out.d.values())))
                if kind_of(v) != k0:
                    self.err(vv, TYPE_P, "This map holds %s values, so it can't also hold %s." % (kind_words(k0), describe(v)))
            out.d[key] = v
        return out

    def e_EmptyList(self, e, env):
        return PList()

    def e_EmptyMap(self, e, env):
        return PMap()

    def e_Copy(self, e, env):
        return deep_copy(self.eval(e.expr, env))

    def e_IfExpr(self, e, env):
        pick = e.yes if self.truth(self.eval(e.cond, env), e.cond) else e.no
        v = self.eval(pick, env)
        # the answer is a fresh value: never an alias of a list/map/record someone else owns
        return deep_copy(v) if pick.kind in ("Name", "Field", "Key", "Index") and is_big(v) else v

    def e_Ask(self, e, env):
        prompt = self.showable(self.eval(e.prompt, env), e.prompt) if e.prompt is not None else ""
        if prompt and not prompt.endswith(" "):
            prompt += " "
        with self.print_lock:
            sys.stdout.write(prompt)
            sys.stdout.flush()
            line = sys.stdin.readline()
        if not sys.stdin.isatty():
            sys.stdout.write(line if line.endswith("\n") else line + "\n")
        return line.rstrip("\r\n")

    def e_Fail(self, e, env):
        v = self.eval(e.expr, env)
        raise LekhError(FAIL_P, self.showable(v, e.expr), e.line,
                        "This came from a `fail` line in the program. Handle the situation before it, or change the message.", e.file)

    def e_Construct(self, e, env):
        slot, _ = self.find(e, env, e.tname)
        t = slot.get()
        if isinstance(t, RecordType):
            declared = t.fields
        elif isinstance(t, VariantType):
            declared = t.fields
        else:
            self.err(e, TYPE_P, "`%s` is not a record or option." % e.tname)
        check_fields(e, e.tname, [f for f, _ in declared], [f for f, _ in e.fields])
        given = {}
        for fn, fe in e.fields:
            v = self.take(fe, env, "into the %s" % e.tname)
            self.no_maybe(v, fe, "stored") if v is None else None
            given[fn] = (v, fe)
        fields = {}
        for fn, ftype in declared:
            v, fe = given[fn]
            if ftype is not None:
                self.check_type(v, ftype, fe, "The field `%s` of %s %s" % (fn, "an" if e.tname[:1] in "AEIOU" else "a", e.tname))
            fields[fn] = v
        return Record(t, fields) if isinstance(t, RecordType) else Variant(t, fields)

    def e_RunCall(self, e, env, want=True):
        slot, _ = self.find(e, env)
        f = slot.get()
        if isinstance(f, (Function, Lambda)):
            return self.call_function(f, e, [], env, want)
        if isinstance(f, Builtin):
            if f.lo == 0:
                return f.fn(self, e, [])
            self.err(e, CALL_P, "`%s` needs inputs." % e.name, "%s of <value>" % e.name)
        self.err(e, TYPE_P, "`%s` is %s, not a task, so it can't be run." % (e.name, describe(f)))

    def e_Call(self, e, env, want=True):
        slot, _ = self.find(e, env)
        f = slot.get()
        if isinstance(f, Builtin):
            if not (f.lo <= len(e.args) <= f.hi):
                need = str(f.lo) if f.lo == f.hi else "%d or %d" % (f.lo, f.hi)
                self.err(e, CALL_P, "The built-in task `%s` needs %s input%s, but got %d." % (f.name, need, "" if f.hi == 1 else "s", len(e.args)),
                         BUILTIN_HELP.get(f.name))
            vals = []
            for a in e.args:
                if a.mode == "lend":
                    self.err(a, CALL_P, "Built-in tasks never change their inputs, so there's no need to lend.", "Remove `lend`.")
                v = self.take(a.expr, env, "to `%s`" % f.name, True) if a.mode == "give" else self.eval(a.expr, env)
                vals.append(v)
            return f.fn(self, e, vals)
        if isinstance(f, (Function, Lambda)):
            return self.call_function(f, e, e.args, env, want)
        if isinstance(f, (RecordType, VariantType)):
            self.err(e, SYNTAX, "`%s` is a type; build one with field names." % e.name, "%s with field value, field value" % e.name)
        self.err(e, TYPE_P, "`%s` is %s, not a task, so it can't be called with `with`/`of`." % (e.name, describe(f)))

    def fn_parts(self, fn):
        d = fn.node
        genv = fn.env if isinstance(fn, Lambda) else fn.genv
        name = getattr(d, "name", None) or "given task"
        return d, genv, name

    def call_function(self, fn, e, args, env, want, me_slot=None):
        d, genv, fname = self.fn_parts(fn)
        ps = d.params
        if len(ps) != len(args):
            if not ps:
                self.err(e, CALL_P, "`%s` takes no inputs." % fname, "run %s" % fname)
            self.err(e, CALL_P, "`%s` needs %d input%s (%s), but got %d." % (fname, len(ps), "" if len(ps) == 1 else "s",
                                                                          ", ".join(p.name for p in ps), len(args)),
                     "%s with %s" % (fname, ", ".join(("lend " if p.changeable else "") + p.name for p in ps)))
        lent = [a.expr.name for a in args if a.mode == "lend" and a.expr.kind == "Name"]
        for n in lent:
            if sum(1 for a in args for x in iter_names(a.expr) if x.name == n) > 1:
                self.err(e, OWN_P, "`%s` is lent to `%s` (so it may change it) and also used again in the same call. "
                                   "Lekh allows either one changer or many readers at a time, never both." % (n, fname),
                         "Pass two different values, or make a copy first:  let other be copy of %s" % n)
        fenv = Env(genv, boundary=True)
        if me_slot is not None:
            fenv.vars["me"] = me_slot
        for p, a in zip(ps, args):
            if a.mode == "lend":
                if not p.changeable:
                    self.err(a, CALL_P, "`%s` only looks at its input `%s`, so there's no need to lend it." % (fname, p.name), "Remove `lend`.")
                if a.expr.kind != "Name":
                    self.err(a, OWN_P, "Only a variable can be lent (so the changes have somewhere to go).")
                src, crossed = self.find(a.expr, env)
                if src.moved:
                    self.moved_error(a.expr, a.expr.name, src.moved)
                if crossed or not src.changeable:
                    self.err(a, CHANGE_P, "To lend `%s`, it must be changeable." % a.expr.name,
                             "let changeable %s be ..." % a.expr.name)
                ps_slot = LentSlot(src, a.line)
            elif a.mode == "give":
                v = self.take(a.expr, env, "to the task `%s`" % fname, explicit=True)
                ps_slot = Slot(v, p.changeable, "own", a.line, "param")
            else:
                if p.changeable:
                    self.err(a, CALL_P, "`%s` may change its input `%s`, so you need to lend it on purpose." % (fname, p.name),
                             "%s with %s" % (fname, ", ".join(("lend " if q.changeable else "") + q.name for q in ps)))
                v = self.eval(a.expr, env)
                self.no_maybe(v, a.expr, "passed to a task") if v is None else None
                mode = "own" if (a.expr.kind in FRESH or not is_big(v)) else "shared"
                ps_slot = Slot(v, False, mode, a.line, "param")
            if p.type is not None:
                self.check_type(ps_slot.get(), p.type, a.expr, "The input `%s` of `%s`" % (p.name, fname))
                if p.type.name in ("maybe", "result"):
                    ps_slot.kind = p.type.name
            fenv.vars[p.name] = ps_slot
        return self.invoke(fn, fenv, e, want)

    def call_values(self, fn, e, values, want=True, me_slot=None):
        """Call a task with already-evaluated values (used by built-ins, jobs and higher-order forms)."""
        if isinstance(fn, Builtin):
            if not (fn.lo <= len(values) <= fn.hi):
                self.err(e, CALL_P, "The built-in task `%s` can't take %d input%s here." % (fn.name, len(values), "" if len(values) == 1 else "s"))
            return fn.fn(self, e, values)
        if isinstance(fn, PyTask):
            if len(values) != fn.nparams:
                self.err(e, CALL_P, "`%s` needs %d input%s, but is given %d here." % (fn.name, fn.nparams, "" if fn.nparams == 1 else "s", len(values)))
            r = fn.fn(*values)
            if want and r is None:
                self.err(e, TYPE_P, "`%s` doesn't give back a value, so there's nothing to use here." % fn.name)
            return r
        if not isinstance(fn, (Function, Lambda)):
            self.err(e, TYPE_P, "Expected a task here, but got %s." % describe(fn), "given x: x * 2")
        d, genv, fname = self.fn_parts(fn)
        ps = d.params
        if len(ps) != len(values):
            self.err(e, CALL_P, "`%s` needs %d input%s, but is given %d here." % (fname, len(ps), "" if len(ps) == 1 else "s", len(values)))
        fenv = Env(genv, boundary=True)
        if me_slot is not None:
            fenv.vars["me"] = me_slot
        for p, v in zip(ps, values):
            if p.changeable:
                self.err(e, CALL_P, "`%s` wants to change its input `%s`, so it can't be used here." % (fname, p.name))
            if p.type is not None:
                self.check_type(v, p.type, e, "The input `%s` of `%s`" % (p.name, fname))
            fenv.vars[p.name] = Slot(v, False, "shared" if is_big(v) else "own", e.line, "param")
        return self.invoke(fn, fenv, e, want)

    def invoke(self, fn, fenv, e, want):
        d, genv, fname = self.fn_parts(fn)
        self.depth += 1
        if self.depth > MAX_DEPTH:
            self.depth = 0
            self.err(e, LIMIT_P, "`%s` called itself (or other tasks) more than %d levels deep." % (fname, MAX_DEPTH),
                     "Make sure the task has a stopping case, e.g.  if n is 0: give back 1")
        result = None
        try:
            if isinstance(fn, Lambda) and d.expr is not None:
                result = self.eval(d.expr, fenv)
                if d.expr.kind not in FRESH and is_big(result):
                    result = deep_copy(result)
            else:
                self.exec_block(d.body, fenv)
        except ReturnSignal as r:
            result = r.value
        finally:
            self.depth -= 1
        ret = getattr(d, "ret", None)
        if ret is not None:
            if result is None:
                self.err(e, TYPE_P, "`%s` promises to give back %s, but it finished without `give back`." % (fname, type_desc(ret)),
                         "Make sure every path through `%s` ends with `give back ...`." % fname)
            self.check_type(result, ret, e, "The value given back by `%s`" % fname)
        if want and result is None:
            self.err(e, TYPE_P, "`%s` doesn't give back a value, so there's nothing to use here." % fname,
                     "Add a `give back ...` line to `%s`, or call it on its own line." % fname)
        return result

    # ---------------- methods
    def type_obj(self, v):
        if isinstance(v, Record):
            return v.rtype
        if isinstance(v, Variant):
            return v.vtype.choice
        return None

    def find_method(self, v, name):
        t = self.type_obj(v)
        return t.methods.get(name) if t is not None else None

    def call_method(self, m, e, obj, args, env, want):
        d = m.node
        if d.changes_me:
            slot, root = self.root_slot(e.obj, env, "change (with its task `%s`)" % d.name)
            me = LentSlot(slot, e.line) if e.obj.kind == "Name" else Slot(obj, True, "lent", e.line, "param")
        else:
            me = Slot(obj, False, "shared" if is_big(obj) else "own", e.line, "param")
        return self.call_function(m, e, args, env, want, me_slot=me)

    def e_MethodCall(self, e, env, want=True):
        obj = self.eval(e.obj, env)
        m = self.find_method(obj, e.name)
        if m is not None:
            return self.call_method(m, e, obj, e.args, env, want)
        if isinstance(obj, (Record, Variant)) and e.name in obj.fields and isinstance(obj.fields[e.name], (Function, Lambda, Builtin)):
            return self.call_values(obj.fields[e.name], e, [self.eval(a.expr, env) for a in e.args], want)
        if e.name in BUILTINS:
            b = self.builtins.vars[e.name].get()
            vals = [obj] + [self.eval(a.expr, env) for a in e.args]
            if not (b.lo <= len(vals) <= b.hi):
                self.err(e, CALL_P, "`%s` can't take %d extra input%s here." % (e.name, len(e.args), "" if len(e.args) == 1 else "s"),
                         BUILTIN_HELP.get(e.name))
            return b.fn(self, e, vals)
        self.no_method(e, obj)

    def no_method(self, e, obj):
        self.no_maybe(obj, e.obj, "asked to `%s`" % e.name)
        t = self.type_obj(obj)
        options = list(t.methods) if t else []
        if isinstance(obj, (Record, Variant)):
            options += list(obj.fields)
        sg = suggest(e.name, options + list(BUILTINS))
        self.err(e, NAME_P, "%s has no field or task called `%s`." % (describe(obj)[0].upper() + describe(obj)[1:], e.name),
                 ("Did you mean `%s`?" % sg) if sg else ("Add one:  to %s's %s ...:" % (t.name, e.name) if t else None))

    # ---------------- Stage 1: new statements
    def x_LetTuple(self, s, env):
        v = self.take(s.expr, env, "into (%s)" % ", ".join(s.names))
        items = v.items if isinstance(v, (Tuple, PList)) else None
        if items is None:
            self.no_maybe(v, s.expr, "split into parts")
            self.err(s, TYPE_P, "`let (%s) be ...` needs a group like (1, 2), but got %s." % (", ".join(s.names), describe(v)))
        if len(items) != len(s.names):
            self.err(s, TYPE_P, "This gives %d values, but you named %d (%s)." % (len(items), len(s.names), ", ".join(s.names)),
                     "Use one name per value, e.g.  let (%s) be ..." % ", ".join("v%d" % (i + 1) for i in range(len(items))))
        for n, x in zip(s.names, items):
            env.vars[n] = Slot(x, s.changeable, "own", s.line, "let")

    def x_Defer(self, s, env):
        if not hasattr(env, "defers"):
            env.defers = []
        env.defers.append(s.body)

    def x_TestBlock(self, s, env):
        pass

    def x_Expect(self, s, env):
        a = self.eval(s.expr, env)
        how, neg = s.how.replace("test:", ""), s.neg
        if how == "be":
            b = self.eval(s.other, env)
            ok = kind_of(a) == kind_of(b) and eq_struct(a, b) if not (is_num(a) and is_num(b)) else (abs(a - b) < 1e-9)
            words = "to be %s" % show(b, True)
        elif how == "contain":
            b = self.eval(s.other, env)
            if isinstance(a, PList):
                ok = any(eq_struct(x, b) for x in a.items)
            elif isinstance(a, str):
                ok = isinstance(b, str) and b in a
            elif isinstance(a, PMap):
                ok = b in a.d if isinstance(b, (str, int, float)) else False
            elif isinstance(a, PSet):
                ok = b in a.s
            else:
                self.err(s, TYPE_P, "`to contain` works with lists, text, maps and sets, but got %s." % describe(a))
            words = "to contain %s" % show(b, True)
        elif how in ("ok", "problem", "nothing", "some"):
            ok = {"ok": isinstance(a, Ok), "problem": isinstance(a, Problem), "nothing": a is NOTHING, "some": isinstance(a, Some)}[how]
            words = "to be %s" % how
        elif how == "true":
            ok = self.truth(a, s.expr, "`expect`")
            words = "to be true"
        else:
            self.err(s, SYNTAX, "Unknown expectation.")
        if neg:
            ok = not ok
        if not ok:
            src = "the value"
            try:
                line = SOURCES[s.file][s.line - 1].strip()
                m = re.match(r"expect (.*?) (not )?to (be|contain)\b", line)
                if m:
                    src = "`%s`" % m.group(1)
            except (KeyError, IndexError, TypeError):
                pass
            raise LekhError(TEST_P, "Expected %s %s%s, but it was %s." % (src, "not " if neg else "", words, show(a, True)),
                            s.line, None, s.file)

    # ---------------- concurrency
    def run_parallel(self, fns, node):
        import threading
        errors = []
        sem = threading.Semaphore(32)

        def wrap(f):
            with sem:
                self.tl.worker = True
                try:
                    f()
                except LekhError as ex:
                    errors.append(ex)
                except ReturnSignal:
                    errors.append(LekhError(PLACE_P, "`give back` or `try` can't jump out of an `at the same time` job.", node.line,
                                            "Handle the problem inside the job, or send it through a channel.", node.file))
                except RecursionError:
                    errors.append(LekhError(LIMIT_P, "A job went too deep.", node.line, None, node.file))
                finally:
                    with self.worker_lock:
                        self.workers -= 1
        threads = []
        for f in fns:
            with self.worker_lock:
                self.workers += 1
            t = threading.Thread(target=wrap, args=(f,), daemon=True)
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        if errors:
            errors.sort(key=lambda x: x.line or 0)
            raise errors[0]

    def x_Parallel(self, s, env):
        self.run_parallel([lambda st=st: self.exec_block([st], Env(env, boundary="parallel")) for st in s.body], s)

    def e_NewChannel(self, e, env):
        return Channel()

    def get_channel(self, node, env):
        ch = self.eval(node, env)
        if not isinstance(ch, Channel):
            self.no_maybe(ch, node, "used as a channel")
            self.err(node, TYPE_P, "Expected a channel, but got %s." % describe(ch), "let results be a new channel")
        return ch

    def x_Send(self, s, env):
        ch = self.get_channel(s.channel, env)
        if ch.closed:
            self.err(s, PLACE_P, "This channel was closed, so nothing more can be sent to it.")
        v = self.take(s.expr, env, "into a channel", explicit=True)
        self.no_maybe(v, s.expr, "sent") if v is None else None
        v = deep_copy(v) if is_big(v) else v
        k = kind_of(v)
        with self.worker_lock:
            if ch.kind is None:
                ch.kind = k
        if ch.kind != k:
            self.err(s, TYPE_P, "This channel carries %s, so it can't also carry %s." % (kind_words(ch.kind), describe(v)))
        ch.q.put(v)

    def x_Close(self, s, env):
        ch = self.get_channel(s.expr, env)
        ch.closed = True

    def receive(self, ch, node):
        import queue
        while True:
            try:
                return Some(ch.q.get(timeout=0.01))
            except queue.Empty:
                others = self.workers - (1 if getattr(self.tl, "worker", False) else 0)
                if ch.closed or others <= 0:
                    try:
                        return Some(ch.q.get_nowait())
                    except queue.Empty:
                        return NOTHING

    def e_Receive(self, e, env):
        return self.receive(self.get_channel(e.channel, env), e)

    def x_Sleep(self, s, env):
        import time
        n = self.eval(s.expr, env)
        if not is_num(n) or n < 0:
            self.no_maybe(n, s.expr, "used as a time")
            self.err(s, TYPE_P, "`wait` needs a number of seconds, but got %s." % describe(n), "wait 0.5 seconds")
        time.sleep(min(n, 3600))

    def e_Start(self, e, env):
        import threading
        c = e.call
        if c.kind in ("Call", "RunCall"):
            slot, _ = self.find(c, env)
            fn = slot.get()
            args = c.args if c.kind == "Call" else []
        else:
            self.err(e, SYNTAX, "`start` needs a task call, e.g.  start fetch with url")
        values = []
        for a in args:
            if a.mode == "lend":
                self.err(a, OWN_P, "A background job can't borrow `%s` - it might outlive this code." % target_desc(a.expr),
                         "Pass it normally (the job gets its own copy) or hand it over with `give`.")
            v = self.take(a.expr, env, "to a background job", explicit=True) if a.mode == "give" else self.eval(a.expr, env)
            values.append(deep_copy(v) if is_big(v) else v)
        job = Job(getattr(c, "name", "job"))

        def run():
            self.tl.worker = True
            try:
                job.result = self.call_values(fn, c, values, want=False)
            except LekhError as ex:
                job.error = ex
            except ReturnSignal as r:
                job.result = r.value
            finally:
                job.done = True
                with self.worker_lock:
                    self.workers -= 1
        with self.worker_lock:
            self.workers += 1
        job.thread = threading.Thread(target=run, daemon=True)
        job.thread.start()
        return job

    def e_WaitFor(self, e, env, want=True):
        job = self.eval(e.job, env)
        if isinstance(job, PList):
            out = PList()
            for j in job.items:
                out.items.append(self.finish_job(j, e, want))
            return out
        return self.finish_job(job, e, want)

    def finish_job(self, job, e, want):
        if not isinstance(job, Job):
            self.no_maybe(job, e, "waited for")
            self.err(e, TYPE_P, "`wait for` needs a job made with `start`, but got %s." % describe(job))
        job.thread.join()
        if job.error is not None:
            raise job.error
        if want and job.result is None:
            self.err(e, TYPE_P, "The job `%s` doesn't give back a value." % job.name)
        return job.result

    # ---------------- Stage 1: new expressions
    def e_TupleLit(self, e, env):
        return Tuple([self.take(it, env, "into a group") for it in e.items])

    def e_EmptySet(self, e, env):
        return PSet()

    def set_value(self, st, v, node):
        ok = isinstance(v, (str, bool)) or is_num(v) or (isinstance(v, Tuple) and all(isinstance(x, (str, bool)) or is_num(x) for x in v.items))
        if not ok:
            self.no_maybe(v, node, "put in a set")
            self.err(node, TYPE_P, "Sets can hold text, numbers, truths or groups of those - not %s." % describe(v),
                     "Use a list instead:  list of ...")
        if st.s:
            k0 = kind_of(next(iter(st.s)))
            if kind_of(v) != k0:
                self.err(node, TYPE_P, "This set holds %s, so it can't also hold %s." % (kind_words(k0), describe(v)))
        return v

    def e_SetLit(self, e, env):
        out = PSet()
        for it in e.items:
            out.s.add(self.set_value(out, self.eval(it, env), it))
        return out

    def e_Lambda(self, e, env):
        g = env
        while g is not None and not getattr(g, "is_global", False):
            g = g.parent
        cap = Env(g if g is not None else self.builtins)
        params = set(p.name for p in e.params)
        body = [e.expr] if e.expr is not None else e.body
        names = set()
        for b in body:
            for x in iter_names(b):
                names.add(x.name)
        for n in names:
            if n in params:
                continue
            slot, crossed = env.find(n)
            if slot is None or slot.moved:
                continue
            if g is not None and g.vars.get(n) is slot:
                continue
            if slot.role in ("function", "builtin", "type"):
                cap.vars[n] = slot
                continue
            v = slot.get()
            cap.vars[n] = Slot(deep_copy(v) if is_big(v) else v, False, "own", slot.line, "let")
        return Lambda(e, cap)

    def hof_items(self, src, node):
        if isinstance(src, PList):
            return src.items
        if isinstance(src, PSet):
            return sorted_items(src)
        if isinstance(src, PMap):
            return list(src.d.keys())
        if isinstance(src, str):
            return list(src)
        if isinstance(src, Tuple):
            return list(src.items)
        self.no_maybe(src, node, "looped over")
        self.err(node, TYPE_P, "This needs a list, set, map or text to go through, but got %s." % describe(src))

    def e_HOF(self, e, env):
        src = self.eval(e.src, env)
        items = list(self.hof_items(src, e.src))
        k = e.form

        def val(x, acc=None):
            en = Env(env)
            en.vars[e.var] = Slot(x, False, "shared" if is_big(x) else "own", e.line, "item")
            if e.acc:
                en.vars[e.acc] = Slot(acc, False, "own", e.line, "item")
            return self.eval(e.body, en)

        def cond(x):
            return self.truth(val(x), e.body, "The `where` condition")
        if k == "keep":
            out = [deep_copy(x) for x in items if cond(x)]
            return PSet(set(out)) if isinstance(src, PSet) else PList(out)
        if k == "turn":
            out = PList()
            for x in items:
                v = val(x)
                if v is None:
                    self.no_maybe(v, e.body, "kept")
                if e.body.kind not in FRESH and is_big(v):
                    v = deep_copy(v)
                self.check_elem(out, v, e.body, "the new list")
                out.items.append(v)
            return out
        if k == "count":
            return sum(1 for x in items if cond(x))
        if k == "find":
            for x in items:
                if cond(x):
                    return Some(deep_copy(x))
            return NOTHING
        if k == "any":
            return any(cond(x) for x in items)
        if k == "every":
            return all(cond(x) for x in items)
        if k == "sort":
            keyed = []
            for x in items:
                kv = val(x)
                self.no_maybe(kv, e.body, "used to sort")
                keyed.append((sort_key(kv, self, e.body), x))
            if keyed:
                kinds = set(type(kk[0]).__name__ if not isinstance(kk[0], (int, float)) else "num" for kk in keyed)
                if len(kinds) > 1:
                    self.err(e.body, TYPE_P, "Sorting needs keys of one kind (all numbers or all text), but got a mix.")
            keyed.sort(key=lambda t: t[0], reverse=bool(e.desc))
            return PList([deep_copy(x) for _, x in keyed])
        if k == "combine":
            acc = self.take(e.init, env, "as a starting value")
            for x in items:
                acc = val(x, acc)
                if acc is None:
                    self.no_maybe(acc, e.body, "combined")
            return deep_copy(acc) if is_big(acc) else acc
        self.err(e, SYNTAX, "Unknown list form `%s`." % k)

    def e_Range(self, e, env):
        a = self.whole(self.eval(e.start, env), e.start, "A range")
        b = self.whole(self.eval(e.end, env), e.end, "A range")
        step = self.whole(self.eval(e.step, env), e.step, "A range") if e.step is not None else None
        seq = self.counting(a, b, step, e)
        if len(seq) > 10_000_000:
            self.err(e, LIMIT_P, "That range has %d numbers - too many to hold in a list." % len(seq), "Use a counting loop:  for each n from a to b:")
        return PList(list(seq))

    def e_Take(self, e, env):
        slot, root = self.root_slot(e.target, env, "take from")
        if slot.moved:
            self.moved_error(root, root.name, slot.moved)
        tv = self.eval(e.target, env)
        name = target_desc(e.target)
        if isinstance(tv, PList):
            self.check_looping(tv, e, name, "take from")
            if not tv.items:
                return NOTHING
            return Some(tv.items.pop(0) if e.which == "first" else tv.items.pop())
        self.no_maybe(tv, e.target, "taken from")
        self.err(e, TYPE_P, "`take %s from` needs a list, but `%s` is %s." % (e.which, name, describe(tv)))

    def e_Between(self, e, env):
        v, lo, hi = self.eval(e.expr, env), self.eval(e.lo, env), self.eval(e.hi, env)
        for x, n in ((v, e.expr), (lo, e.lo), (hi, e.hi)):
            self.no_maybe(x, n, "compared")
        if not ((is_num(v) and is_num(lo) and is_num(hi)) or all(isinstance(x, str) for x in (v, lo, hi))):
            self.err(e, TYPE_P, "`is between` needs three numbers (or three texts), but got %s, %s and %s." % (describe(v), describe(lo), describe(hi)))
        r = lo <= v <= hi
        return (not r) if e.neg else r


# =====================================================================================
#  Built-in tasks  (call with `of` for one input, or `with` for several)
# =====================================================================================
def _need(I, e, v, kinds, what, pos=""):
    I.no_maybe(v, e, "used by `%s`" % e.name)
    if kind_of(v) not in kinds:
        I.err(e, TYPE_P, "`%s` needs %s%s, but got %s." % (e.name, what, pos, describe(v)), BUILTIN_HELP.get(e.name))


def b_length(I, e, a):
    v = a[0]
    _need(I, e, v, ("text", "list", "map"), "text, a list or a map")
    return len(v) if isinstance(v, str) else len(v.items) if isinstance(v, PList) else len(v.d)


def _firstlast(which):
    def f(I, e, a):
        v = a[0]
        _need(I, e, v, ("text", "list"), "a list or text")
        seq = v if isinstance(v, str) else v.items
        if not seq:
            I.err(e, RANGE_P, "There is no %s item, because the %s is empty." % (which, "text" if isinstance(v, str) else "list"),
                  "Check first:  if length of xs is greater than 0: ...")
        return deep_copy(seq[0] if which == "first" else seq[-1])
    return f


def _text(fn):
    def f(I, e, a):
        _need(I, e, a[0], ("text",), "text")
        return fn(a[0])
    return f


def b_reversed(I, e, a):
    v = a[0]
    _need(I, e, v, ("text", "list"), "a list or text")
    return v[::-1] if isinstance(v, str) else PList([deep_copy(x) for x in reversed(v.items)])


def _nums_or_texts(I, e, v, allow_empty=True):
    _need(I, e, v, ("list",), "a list")
    ks = {kind_of(x) for x in v.items}
    if ks and not (ks == {"number"} or ks == {"text"}):
        I.err(e, TYPE_P, "`%s` needs a list of numbers or a list of text." % e.name)
    if not allow_empty and not v.items:
        I.err(e, RANGE_P, "`%s` can't work on an empty list." % e.name, "Check first:  if length of xs is greater than 0: ...")
    return v.items


def b_sorted(I, e, a):
    return PList(sorted(_nums_or_texts(I, e, a[0])))


def b_sum(I, e, a):
    items = _nums_or_texts(I, e, a[0])
    if items and not is_num(items[0]):
        I.err(e, TYPE_P, "`sum` needs a list of numbers.")
    return sum(items)


def b_largest(I, e, a):
    return max(_nums_or_texts(I, e, a[0], False))


def b_smallest(I, e, a):
    return min(_nums_or_texts(I, e, a[0], False))


def b_keys(I, e, a):
    _need(I, e, a[0], ("map",), "a map")
    return PList(list(a[0].d.keys()))


def b_values(I, e, a):
    _need(I, e, a[0], ("map",), "a map")
    return PList([deep_copy(x) for x in a[0].d.values()])


def b_round(I, e, a):
    _need(I, e, a[0], ("number",), "a number")
    places = 0
    if len(a) > 1:
        _need(I, e, a[1], ("number",), "a number of decimal places", " as its second input")
        places = int(a[1])
    r = round(a[0], places)
    return int(r) if places == 0 else r


def b_absolute(I, e, a):
    _need(I, e, a[0], ("number",), "a number")
    return abs(a[0])


def b_sqrt(I, e, a):
    _need(I, e, a[0], ("number",), "a number")
    if a[0] < 0:
        I.err(e, MATH_P, "Negative numbers don't have a square root.")
    r = math.sqrt(a[0])
    return int(r) if r.is_integer() else r


def b_random(I, e, a):
    for i, v in enumerate(a):
        _need(I, e, v, ("number",), "whole numbers")
    return random.randint(int(a[0]), int(a[1]))


def b_join(I, e, a):
    _need(I, e, a[0], ("list",), "a list", " as its first input")
    sep = ""
    if len(a) > 1:
        _need(I, e, a[1], ("text",), "text", " as its second input (the separator)")
        sep = a[1]
    return sep.join(show(x) for x in a[0].items)


def b_split(I, e, a):
    _need(I, e, a[0], ("text",), "text", " as its first input")
    if len(a) > 1:
        _need(I, e, a[1], ("text",), "text", " as its second input (the separator)")
        if a[1] == "":
            return PList(list(a[0]))
        return PList(a[0].split(a[1]))
    return PList(a[0].split())


def b_replace(I, e, a):
    for v in a:
        _need(I, e, v, ("text",), "three pieces of text")
    return a[0].replace(a[1], a[2])


def b_position(I, e, a):
    _need(I, e, a[0], ("list", "text"), "a list or text", " as its first input")
    if isinstance(a[0], str):
        _need(I, e, a[1], ("text",), "text", " as its second input")
        i = a[0].find(a[1])
        return Some(i + 1) if i >= 0 else NOTHING
    for i, x in enumerate(a[0].items):
        if eq_struct(x, a[1]):
            return Some(i + 1)
    return NOTHING


BUILTINS = {
    "length": (b_length, 1, 1), "first": (_firstlast("first"), 1, 1), "last": (_firstlast("last"), 1, 1),
    "uppercase": (_text(str.upper), 1, 1), "lowercase": (_text(str.lower), 1, 1),
    "trimmed": (_text(str.strip), 1, 1), "capitalized": (_text(lambda s: s[:1].upper() + s[1:]), 1, 1),
    "words": (_text(lambda s: PList(s.split())), 1, 1), "lines": (_text(lambda s: PList(s.splitlines())), 1, 1),
    "letters": (_text(lambda s: PList(list(s))), 1, 1), "reversed": (b_reversed, 1, 1),
    "sorted": (b_sorted, 1, 1), "sum": (b_sum, 1, 1), "largest": (b_largest, 1, 1), "smallest": (b_smallest, 1, 1),
    "keys": (b_keys, 1, 1), "values": (b_values, 1, 1), "round": (b_round, 1, 2), "absolute": (b_absolute, 1, 1),
    "sqrt": (b_sqrt, 1, 1), "random": (b_random, 2, 2), "join": (b_join, 1, 2), "split": (b_split, 1, 2),
    "replace": (b_replace, 3, 3), "position": (b_position, 2, 2),
}
BUILTIN_HELP = {
    "length": "length of cart", "first": "first of cart", "last": "last of cart", "uppercase": "uppercase of name",
    "lowercase": "lowercase of name", "trimmed": "trimmed of answer", "capitalized": "capitalized of name",
    "words": "words of sentence", "lines": "lines of text", "letters": "letters of word", "reversed": "reversed of cart",
    "sorted": "sorted of scores", "sum": "sum of prices", "largest": "largest of scores", "smallest": "smallest of scores",
    "keys": "keys of ages", "values": "values of ages", "round": "round of 3.7   or   round with price, 2",
    "absolute": "absolute of -5", "sqrt": "sqrt of 16", "random": "random with 1, 6", "join": "join with names, \", \"",
    "split": "split with line, \",\"", "replace": "replace with text, \"old\", \"new\"",
    "position": "position with cart, \"milk\"   (gives some 2, or nothing)",
}
for _n, (_f, _lo, _hi) in BUILTINS.items():
    BUILTIN_ARITY[_n] = (_lo, _hi)

from . import stdlib as _stdlib  # noqa: E402  (registers the standard library built-ins)


# =====================================================================================
#  Command line & REPL
# =====================================================================================
def run_file(path, check_only=False):
    loader = Loader()
    try:
        mod = loader.load(path)
        for m in list(loader.modules.values()):
            Checker(m, loader).check()
        from .typecheck import typecheck
        for m in list(loader.modules.values()):
            typecheck(m, loader)
        if check_only:
            print("No problems found in %s." % display_path(os.path.abspath(path)))
            return 0
        Interp(loader).run_module(mod)
        return 0
    except LekhError as e:
        sys.stdout.flush()
        sys.stderr.write(format_error(e))
        return 1
    except RecursionError:
        sys.stdout.flush()
        sys.stderr.write(format_error(LekhError(LIMIT_P, "The program went too deep (a task probably calls itself forever).", None,
                                                "Make sure recursive tasks have a stopping case.")))
        return 1
    except KeyboardInterrupt:
        sys.stderr.write("\nStopped.\n")
        return 130


REPL_HELP = """Type Lekh statements. Lines ending in ':' start a block; finish a block with an empty line.
  let name be "Sushant"          say "Hello, {name}"
  let changeable n be 1           increase n by 1
  to double x: give back x * 2   (then)  say double of 21
Commands: help, quit"""


def repl():
    print("Lekh %s - a language that reads like English. Type 'help' for tips, 'quit' to leave." % VERSION)
    loader = Loader()
    interp = Interp(loader)
    genv = Env(interp.builtins)
    types, count, tfields = set(), 0, {}
    buf = []
    while True:
        try:
            line = input("...   " if buf else "lekh> ")
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            buf = []
            continue
        if not buf:
            cmd = line.strip()
            if cmd in ("quit", "exit"):
                break
            if cmd == "help":
                print(REPL_HELP)
                continue
            if not cmd:
                continue
        buf.append(line)
        if line.rstrip().endswith(":") or (len(buf) > 1 and line.strip()):
            continue
        src = "\n".join(buf)
        buf = []
        count += 1
        name = "<repl>"
        try:
            mod = loader.load_source(src, name, extra_types=types, extra_fields=tfields)
            types |= set(mod.records) | set(mod.choices) | {v for vs in mod.choices.values() for v in vs}
            tfields.update(mod.fields)
            pre = {}
            for n, slot in genv.vars.items():
                role = {"function": "function", "type": "type"}.get(slot.role, "let")
                pre[n] = VarInfo(n, role, changeable=slot.changeable, line=slot.line)
            ch = Checker(mod, loader, predefined=pre, repl=True)
            # make previously defined tasks/types known to the checker
            for n, slot in genv.vars.items():
                v = slot.get()
                if isinstance(v, Function):
                    ch.funcs[n] = v.node
                elif isinstance(v, RecordType):
                    ch.records[n] = [f for f, _ in v.fields]
                elif isinstance(v, ChoiceType):
                    ch.choices[n] = list(v.variants)
                    for vn, vt in v.variants.items():
                        ch.variants[vn] = (n, [f for f, _ in vt.fields])
            ch.check()
            interp.run_stmts(mod.ast, genv, repl=True)
        except LekhError as e:
            sys.stdout.write(format_error(e))
        except RecursionError:
            print("Too deep: a task probably calls itself forever.")


def main(argv):
    sys.setrecursionlimit(100000)
    args = argv[1:]
    if not args:
        repl()
        return 0
    if args[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0
    if args[0] in ("-v", "--version"):
        print("Lekh", VERSION)
        return 0
    check_only = False
    if args[0] == "--check":
        check_only = True
        args = args[1:]
    if not args:
        print("Usage: python3 lekh.py [--check] program%s" % EXT)
        return 2
    return run_file(args[0], check_only)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
