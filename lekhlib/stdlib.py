"""Lekh standard library: text, numbers, math, lists, sets, maps, files, JSON,
dates & times, randomness, regex-lite patterns, environment, shell commands and HTTP.

Every built-in is a Python function f(interp, node, args) registered in core.BUILTINS
with its arity, plus a one-line example in core.BUILTIN_HELP.
"""
import datetime as _dt
import fnmatch
import functools
import json
import math
import os, shutil
import random
import re
import shlex
import subprocess
import time
import urllib.error
import urllib.request

from .core import (BUILTINS, BUILTIN_HELP, BUILTIN_ARITY, PList, PMap, PSet, Tuple, Record, RecordType, Variant,
                   Some, NOTHING, Ok, Problem, LekhError, TYPE_P, RANGE_P, MATH_P, FILE_P, CALL_P,
                   kind_of, describe, deep_copy, eq_struct, show, is_num, sorted_items, sort_key, _need, fmt_num)

# Built-in record types returned by the library
COMMAND_OUTPUT = RecordType("CommandOutput", [("output", None), ("errors", None), ("code", None)])
RESPONSE = RecordType("Response", [("status", None), ("body", None), ("headers", None)])
BUILTIN_RECORDS = {"CommandOutput": COMMAND_OUTPUT, "Response": RESPONSE}

REG = {}


def builtin(name, lo, hi, help_text):
    def deco(fn):
        REG[name] = (fn, lo, hi, help_text)
        return fn
    return deco


def num(I, e, v, pos=""):
    _need(I, e, v, ("number",), "a number", pos)
    return v


def whole_num(I, e, v, pos=""):
    num(I, e, v, pos)
    if isinstance(v, float) and not v.is_integer():
        I.err(e, TYPE_P, "`%s` needs a whole number%s, but got %s." % (e.name, pos, show(v)), BUILTIN_HELP.get(e.name))
    return int(v)


def text(I, e, v, pos=""):
    _need(I, e, v, ("text",), "text", pos)
    return v


def tidy(x):
    """Turn floats that are whole into ints (3.0 -> 3)."""
    if isinstance(x, float) and x.is_integer() and abs(x) < 1e15:
        return int(x)
    return x


def seq_items(I, e, v, what="a list, set or text"):
    if isinstance(v, PList):
        return v.items
    if isinstance(v, PSet):
        return sorted_items(v)
    if isinstance(v, Tuple):
        return list(v.items)
    if isinstance(v, str):
        return list(v)
    _need(I, e, v, ("list",), what)


def call(I, e, fn, *vals):
    return I.call_values(fn, e, list(vals), want=True)


# ----------------------------------------------------------------------------- text
@builtin("title_case", 1, 1, 'title_case of "hello world"   -> "Hello World"')
def b_title(I, e, a):
    return " ".join(w[:1].upper() + w[1:].lower() for w in text(I, e, a[0]).split(" "))


@builtin("slice", 3, 3, 'slice with "abcdef", 2, 4   -> "bcd"   (positions start at 1, both ends included)')
def b_slice(I, e, a):
    v = a[0]
    _need(I, e, v, ("text", "list"), "text or a list", " as its first input")
    lo, hi = whole_num(I, e, a[1], " as the start"), whole_num(I, e, a[2], " as the end")
    size = len(v) if isinstance(v, str) else len(v.items)
    lo, hi = max(lo, 1), min(hi, size)
    if isinstance(v, str):
        return v[lo - 1:hi] if hi >= lo else ""
    return PList([deep_copy(x) for x in v.items[lo - 1:hi]]) if hi >= lo else PList()


@builtin("pad_left", 2, 3, 'pad_left with "7", 3, "0"   -> "007"')
def b_pad_left(I, e, a):
    s = a[0] if isinstance(a[0], str) else show(a[0])
    fill = text(I, e, a[2], " as the fill") if len(a) > 2 else " "
    return s.rjust(whole_num(I, e, a[1], " as the width"), (fill or " ")[0])


@builtin("pad_right", 2, 3, 'pad_right with "name", 10   -> "name      "')
def b_pad_right(I, e, a):
    s = a[0] if isinstance(a[0], str) else show(a[0])
    fill = text(I, e, a[2], " as the fill") if len(a) > 2 else " "
    return s.ljust(whole_num(I, e, a[1], " as the width"), (fill or " ")[0])


@builtin("centered", 2, 3, 'centered with "hi", 6, "*"   -> "**hi**"')
def b_center(I, e, a):
    s = a[0] if isinstance(a[0], str) else show(a[0])
    fill = text(I, e, a[2], " as the fill") if len(a) > 2 else " "
    return s.center(whole_num(I, e, a[1], " as the width"), (fill or " ")[0])


@builtin("repeat_text", 2, 2, 'repeat_text with "-", 10   -> "----------"')
def b_repeat(I, e, a):
    n = whole_num(I, e, a[1], " as the count")
    if n < 0 or n > 10_000_000:
        I.err(e, RANGE_P, "`repeat_text` needs a count between 0 and 10 million.")
    return text(I, e, a[0]) * n


@builtin("count_of", 2, 2, 'count_of with "banana", "a"   -> 3   (also works on lists)')
def b_count_of(I, e, a):
    v = a[0]
    if isinstance(v, str):
        return v.count(text(I, e, a[1], " as the thing to count"))
    return sum(1 for x in seq_items(I, e, v, "text or a list") if eq_struct(x, a[1]))


@builtin("is_number", 1, 1, 'is_number of "42"   -> true')
def b_is_number(I, e, a):
    v = a[0]
    if is_num(v):
        return True
    try:
        float(text(I, e, v).strip().replace("_", ""))
        return True
    except ValueError:
        return False


@builtin("trim_start", 1, 1, 'trim_start of "  hi"   -> "hi"')
def b_trim_start(I, e, a):
    return text(I, e, a[0]).lstrip()


@builtin("trim_end", 1, 1, 'trim_end of "hi  "   -> "hi"')
def b_trim_end(I, e, a):
    return text(I, e, a[0]).rstrip()


@builtin("letter_code", 1, 1, 'letter_code of "A"   -> 65')
def b_ord(I, e, a):
    s = text(I, e, a[0])
    if len(s) != 1:
        I.err(e, TYPE_P, "`letter_code` needs exactly one letter, but got %s." % show(s, True))
    return ord(s)


@builtin("letter_from_code", 1, 1, 'letter_from_code of 65   -> "A"')
def b_chr(I, e, a):
    n = whole_num(I, e, a[0])
    if not 0 <= n <= 0x10FFFF:
        I.err(e, RANGE_P, "%d is not a valid letter code." % n)
    return chr(n)


@builtin("is_blank", 1, 1, 'is_blank of "   "   -> true')
def b_blank(I, e, a):
    return text(I, e, a[0]).strip() == ""


@builtin("type_of", 1, 1, 'type_of of 42   -> "number"')
def b_type_of(I, e, a):
    v = a[0]
    if is_num(v):
        return "integer" if isinstance(v, int) else "decimal"
    return kind_of(v)


# ----------------------------------------------------------------------------- numbers & math
@builtin("power", 2, 2, "power with 2, 10   -> 1024   (whole numbers can be as big as you like)")
def b_power(I, e, a):
    x, y = num(I, e, a[0]), num(I, e, a[1])
    if isinstance(x, int) and isinstance(y, int) and y >= 0:
        if y > 100_000:
            I.err(e, RANGE_P, "That power is too large to compute.")
        return x ** y
    if x == 0 and y < 0:
        I.err(e, MATH_P, "Can't raise zero to a negative power.")
    try:
        r = float(x) ** float(y)
    except OverflowError:
        I.err(e, RANGE_P, "That number is too large.")
    if isinstance(r, complex):
        I.err(e, MATH_P, "A negative number can't be raised to a fractional power.")
    return tidy(r)


@builtin("format_number", 2, 2, 'format_number with 3.14159, 2   -> "3.14"')
def b_format(I, e, a):
    return "%.*f" % (whole_num(I, e, a[1], " as the number of decimal places"), num(I, e, a[0]))


@builtin("with_commas", 1, 2, 'with_commas of 1234567.5   -> "1,234,567.5"   (with_commas with x, 2 fixes the decimals)')
def b_commas(I, e, a):
    x = num(I, e, a[0])
    if len(a) > 1:
        return "{:,.{}f}".format(x, whole_num(I, e, a[1]))
    if isinstance(x, int):
        return "{:,}".format(x)
    whole, _, frac = fmt_num(x).partition(".")
    return "{:,}".format(int(whole)) + ("." + frac if frac else "")


@builtin("whole", 1, 1, "whole of 7.9   -> 7   (drops the decimal part)")
def b_whole(I, e, a):
    return int(num(I, e, a[0]))


@builtin("floor", 1, 1, "floor of 7.9   -> 7")
def b_floor(I, e, a):
    return math.floor(num(I, e, a[0]))


@builtin("ceiling", 1, 1, "ceiling of 7.1   -> 8")
def b_ceiling(I, e, a):
    return math.ceil(num(I, e, a[0]))


@builtin("is_whole", 1, 1, "is_whole of 4.0   -> true")
def b_is_whole(I, e, a):
    x = num(I, e, a[0])
    return isinstance(x, int) or x.is_integer()


@builtin("smaller", 2, 2, "smaller with 3, 8   -> 3")
def b_smaller(I, e, a):
    _two_same(I, e, a)
    return min(a[0], a[1])


@builtin("larger", 2, 2, "larger with 3, 8   -> 8")
def b_larger(I, e, a):
    _two_same(I, e, a)
    return max(a[0], a[1])


def _two_same(I, e, a):
    if not ((is_num(a[0]) and is_num(a[1])) or (isinstance(a[0], str) and isinstance(a[1], str))):
        I.err(e, TYPE_P, "`%s` needs two numbers (or two texts), but got %s and %s." % (e.name, describe(a[0]), describe(a[1])))


@builtin("clamp", 3, 3, "clamp with 15, 0, 10   -> 10")
def b_clamp(I, e, a):
    x, lo, hi = num(I, e, a[0]), num(I, e, a[1]), num(I, e, a[2])
    return max(lo, min(hi, x))


@builtin("sign", 1, 1, "sign of -4   -> -1")
def b_sign(I, e, a):
    x = num(I, e, a[0])
    return (x > 0) - (x < 0)


@builtin("pi", 0, 0, "pi   -> 3.141592653589793")
def b_pi(I, e, a):
    return math.pi


def _math1(name, fn, help_text, check=None):
    def f(I, e, a):
        x = num(I, e, a[0])
        if check and not check(x):
            I.err(e, MATH_P, "`%s` can't work with %s." % (name, show(x)))
        return tidy(fn(x))
    REG[name] = (f, 1, 1, help_text)


_math1("sine", math.sin, "sine of (pi / 2)   -> 1   (angles in radians)")
_math1("cosine", math.cos, "cosine of 0   -> 1")
_math1("tangent", math.tan, "tangent of 0   -> 0")
_math1("log", math.log, "log of 10   -> 2.302585   (natural log)", lambda x: x > 0)
_math1("log10", math.log10, "log10 of 1000   -> 3", lambda x: x > 0)
_math1("exp", math.exp, "exp of 1   -> 2.718281828")
_math1("radians", math.radians, "radians of 180   -> 3.14159")
_math1("degrees", math.degrees, "degrees of pi   -> 180")


@builtin("hex", 1, 1, 'hex of 255   -> "ff"')
def b_hex(I, e, a):
    return format(whole_num(I, e, a[0]), "x")


@builtin("binary", 1, 1, 'binary of 5   -> "101"')
def b_bin(I, e, a):
    return format(whole_num(I, e, a[0]), "b")


@builtin("average", 1, 1, "average of (list of 2, 4, 9)   -> 5")
def b_average(I, e, a):
    items = seq_items(I, e, a[0], "a list of numbers")
    if not items:
        I.err(e, RANGE_P, "Can't average an empty list.", "Check first:  if length of xs is greater than 0: ...")
    for x in items:
        if not is_num(x):
            I.err(e, TYPE_P, "`average` needs a list of numbers, but it contains %s." % describe(x))
    return tidy(sum(items) / len(items))


# ----------------------------------------------------------------------------- randomness
@builtin("random_decimal", 0, 0, "random_decimal   -> a decimal between 0 and 1")
def b_rand_dec(I, e, a):
    return random.random()


@builtin("random_item", 1, 1, 'random_item of (list of "rock", "paper", "scissors")')
def b_rand_item(I, e, a):
    items = seq_items(I, e, a[0])
    if not items:
        I.err(e, RANGE_P, "Can't pick from an empty list.")
    return deep_copy(random.choice(items))


@builtin("shuffled", 1, 1, "shuffled of cards   -> a new list in random order")
def b_shuffled(I, e, a):
    items = [deep_copy(x) for x in seq_items(I, e, a[0])]
    random.shuffle(items)
    return PList(items)


@builtin("seed_random", 1, 1, "seed_random with 42   (makes random results repeatable)")
def b_seed(I, e, a):
    random.seed(whole_num(I, e, a[0]))
    return None


# ----------------------------------------------------------------------------- lists, sets, maps
@builtin("sorted_using", 2, 2, "sorted_using with people, given a, b: a's age is less than b's age")
def b_sorted_using(I, e, a):
    items = [deep_copy(x) for x in seq_items(I, e, a[0])]
    fn = a[1]

    def cmp(x, y):
        r = call(I, e, fn, x, y)
        if isinstance(r, bool):
            if r:
                return -1
            return 1 if call(I, e, fn, y, x) else 0
        if is_num(r):
            return (r > 0) - (r < 0)
        I.err(e, TYPE_P, "The comparing task for `sorted_using` must give back true/false (does a come first?) or a number.")
    return PList(sorted(items, key=functools.cmp_to_key(cmp)))


@builtin("transform", 2, 2, "transform with numbers, given n: n * 2")
def b_transform(I, e, a):
    return PList([call(I, e, a[1], x) for x in seq_items(I, e, a[0])])


@builtin("select", 2, 2, "select with numbers, given n: n is greater than 2")
def b_select(I, e, a):
    out = []
    for x in seq_items(I, e, a[0]):
        r = call(I, e, a[1], x)
        if not isinstance(r, bool):
            I.err(e, TYPE_P, "The task given to `select` must give back true or false.")
        if r:
            out.append(deep_copy(x))
    return PList(out)


@builtin("reduce", 3, 3, "reduce with numbers, 0, given total, n: total + n")
def b_reduce(I, e, a):
    acc = a[1]
    for x in seq_items(I, e, a[0]):
        acc = call(I, e, a[2], acc, x)
    return acc


@builtin("unique", 1, 1, "unique of (list of 1, 2, 2, 3)   -> [1, 2, 3]   (keeps the first of each)")
def b_unique(I, e, a):
    out = []
    for x in seq_items(I, e, a[0]):
        if not any(eq_struct(x, y) for y in out):
            out.append(deep_copy(x))
    return PList(out)


@builtin("flatten", 1, 1, "flatten of (list of (list of 1, 2), (list of 3))   -> [1, 2, 3]")
def b_flatten(I, e, a):
    out = []
    for x in seq_items(I, e, a[0]):
        if isinstance(x, PList):
            out.extend(deep_copy(y) for y in x.items)
        else:
            out.append(deep_copy(x))
    return PList(out)


@builtin("pairs_of", 2, 2, 'pairs_of with names, ages   -> [("Ann", 31), ("Bo", 25)]')
def b_zip(I, e, a):
    return PList([Tuple([deep_copy(x), deep_copy(y)]) for x, y in zip(seq_items(I, e, a[0]), seq_items(I, e, a[1]))])


@builtin("numbered", 1, 1, 'numbered of (list of "a", "b")   -> [(1, "a"), (2, "b")]')
def b_enumerate(I, e, a):
    return PList([Tuple([i + 1, deep_copy(x)]) for i, x in enumerate(seq_items(I, e, a[0]))])


@builtin("chunks", 2, 2, "chunks with (list of 1, 2, 3, 4, 5), 2   -> [[1, 2], [3, 4], [5]]")
def b_chunks(I, e, a):
    items = seq_items(I, e, a[0])
    n = whole_num(I, e, a[1], " as the chunk size")
    if n < 1:
        I.err(e, RANGE_P, "The chunk size must be at least 1.")
    return PList([PList([deep_copy(x) for x in items[i:i + n]]) for i in range(0, len(items), n)])


@builtin("pairs", 1, 1, 'pairs of ages   -> [("Ann", 31), ("Bo", 25)]   (a map as a list of (key, value) groups)')
def b_pairs(I, e, a):
    _need(I, e, a[0], ("map",), "a map")
    return PList([Tuple([k, deep_copy(v)]) for k, v in a[0].d.items()])


@builtin("merged", 2, 2, "merged with defaults, settings   -> a new map; the second one wins on clashes")
def b_merged(I, e, a):
    _need(I, e, a[0], ("map",), "a map", " as its first input")
    _need(I, e, a[1], ("map",), "a map", " as its second input")
    out = PMap()
    for k, v in list(a[0].d.items()) + list(a[1].d.items()):
        out.d[k] = deep_copy(v)
    return out


@builtin("map_from", 1, 1, 'map_from of (list of ("a", 1), ("b", 2))   -> {"a": 1, "b": 2}')
def b_map_from(I, e, a):
    out = PMap()
    for x in seq_items(I, e, a[0], "a list of (key, value) groups"):
        if not isinstance(x, Tuple) or len(x.items) != 2:
            I.err(e, TYPE_P, "`map_from` needs a list of (key, value) groups, but found %s." % describe(x))
        out.d[x.items[0]] = deep_copy(x.items[1])
    return out


def _sets(I, e, a):
    for i, v in enumerate(a):
        _need(I, e, v, ("set",), "two sets", "")
    return a[0].s, a[1].s


@builtin("union", 2, 2, "union with a, b   -> everything in either set")
def b_union(I, e, a):
    x, y = _sets(I, e, a)
    return PSet(set(x | y))


@builtin("intersection", 2, 2, "intersection with a, b   -> only what both sets have")
def b_inter(I, e, a):
    x, y = _sets(I, e, a)
    return PSet(set(x & y))


@builtin("difference", 2, 2, "difference with a, b   -> what's in a but not in b")
def b_diff(I, e, a):
    x, y = _sets(I, e, a)
    return PSet(set(x - y))


@builtin("is_subset", 2, 2, "is_subset with small, big   -> true if every item of small is in big")
def b_subset(I, e, a):
    x, y = _sets(I, e, a)
    return x <= y


# ----------------------------------------------------------------------------- regex-lite & wildcards
def _regex(I, e, pat):
    try:
        return re.compile(text(I, e, pat, " as the pattern"))
    except re.error as ex:
        I.err(e, TYPE_P, "The pattern %s isn't valid: %s." % (show(pat, True), ex),
              'Patterns use standard regex symbols, e.g. "[0-9]+" for digits, "\\\\s" for spaces.')


@builtin("matches", 2, 2, 'matches with "2026-10-08", "[0-9]{4}-[0-9]{2}-[0-9]{2}"   -> true (the WHOLE text must match)')
def b_matches(I, e, a):
    return _regex(I, e, a[1]).fullmatch(text(I, e, a[0])) is not None


@builtin("contains_pattern", 2, 2, 'contains_pattern with line, "ERROR|FATAL"   -> true if any part matches')
def b_contains_pattern(I, e, a):
    return _regex(I, e, a[1]).search(text(I, e, a[0])) is not None


@builtin("find_all", 2, 2, 'find_all with "a1b22c333", "[0-9]+"   -> ["1", "22", "333"]')
def b_find_all(I, e, a):
    r = _regex(I, e, a[1])
    return PList([m.group(0) for m in r.finditer(text(I, e, a[0]))])


@builtin("find_groups", 2, 2, 'find_groups with "user=ann id=7", "(\\\\w+)=(\\\\w+)"   -> [["user", "ann"], ["id", "7"]]')
def b_find_groups(I, e, a):
    r = _regex(I, e, a[1])
    return PList([PList([g or "" for g in m.groups()]) for m in r.finditer(text(I, e, a[0]))])


@builtin("replace_pattern", 3, 3, 'replace_pattern with "a1b22", "[0-9]+", "#"   -> "a#b#"')
def b_replace_pattern(I, e, a):
    return _regex(I, e, a[1]).sub(text(I, e, a[2], " as the replacement").replace("\\", "\\\\"), text(I, e, a[0]))


@builtin("split_pattern", 2, 2, 'split_pattern with "a, b;c", "[,;] *"   -> ["a", "b", "c"]')
def b_split_pattern(I, e, a):
    return PList(_regex(I, e, a[1]).split(text(I, e, a[0])))


@builtin("matches_wildcard", 2, 2, 'matches_wildcard with "app.log", "*.log"   -> true   (* = anything, ? = one letter)')
def b_wildcard(I, e, a):
    return fnmatch.fnmatchcase(text(I, e, a[0]), text(I, e, a[1], " as the wildcard"))


# ----------------------------------------------------------------------------- files & folders
def _path(I, e, v):
    p = text(I, e, v, " as the path")
    return os.path.expanduser(p)


def _io_problem(ex, p):
    if isinstance(ex, FileNotFoundError):
        return Problem("no file or folder called \"%s\"" % p)
    if isinstance(ex, IsADirectoryError):
        return Problem("\"%s\" is a folder, not a file" % p)
    if isinstance(ex, PermissionError):
        return Problem("not allowed to use \"%s\"" % p)
    if isinstance(ex, UnicodeDecodeError):
        return Problem("\"%s\" is not a text file" % p)
    return Problem("%s: %s" % (p, getattr(ex, "strerror", None) or ex))


@builtin("read_file", 1, 1, 'read_file of "notes.txt"   -> ok "the text" or problem "no file ..."')
def b_read_file(I, e, a):
    p = _path(I, e, a[0])
    try:
        with open(p, encoding="utf-8") as f:
            return Ok(f.read())
    except (OSError, UnicodeDecodeError) as ex:
        return _io_problem(ex, a[0])


@builtin("read_lines", 1, 1, 'read_lines of "data.csv"   -> ok ["line 1", "line 2"]')
def b_read_lines(I, e, a):
    r = b_read_file(I, e, a)
    return Ok(PList(r.value.splitlines())) if isinstance(r, Ok) else r


@builtin("write_file", 2, 2, 'write_file with "out.txt", "hello"   -> ok 5 (letters written)   (replaces the file)')
def b_write_file(I, e, a):
    return _write(I, e, a, "w")


@builtin("append_file", 2, 2, 'append_file with "log.txt", "one more line\\n"   -> ok 14')
def b_append_file(I, e, a):
    return _write(I, e, a, "a")


def _write(I, e, a, mode):
    p = _path(I, e, a[0])
    data = a[1] if isinstance(a[1], str) else show(a[1])
    try:
        with open(p, mode, encoding="utf-8") as f:
            f.write(data)
        return Ok(len(data))
    except OSError as ex:
        return _io_problem(ex, a[0])


@builtin("file_exists", 1, 1, 'file_exists of "notes.txt"   -> true / false   (also true for folders)')
def b_exists(I, e, a):
    return os.path.exists(_path(I, e, a[0]))


@builtin("is_folder", 1, 1, 'is_folder of "src"   -> true / false')
def b_is_folder(I, e, a):
    return os.path.isdir(_path(I, e, a[0]))


@builtin("list_folder", 1, 1, 'list_folder of "."   -> ok ["a.txt", "src"]   (sorted names)')
def b_list_folder(I, e, a):
    p = _path(I, e, a[0])
    try:
        return Ok(PList(sorted(os.listdir(p))))
    except OSError as ex:
        return _io_problem(ex, a[0])


@builtin("copy_file", 2, 2, 'copy_file with "logo.png", "site/logo.png"   -> ok "site/logo.png"   (any kind of file; makes folders; replaces the copy)')
def b_copy_file(I, e, a):
    src, dst = _path(I, e, a[0]), _path(I, e, a[1])
    if os.path.isdir(src):
        return Problem("\"%s\" is a folder - copy_file copies single files" % a[0])
    try:
        folder = os.path.dirname(dst)
        if folder:
            os.makedirs(folder, exist_ok=True)
        shutil.copyfile(src, dst)
        return Ok(a[1])
    except OSError as ex:
        return _io_problem(ex, a[0])


@builtin("make_folder", 1, 1, 'make_folder of "reports/2026"   -> ok "reports/2026"   (makes parents too)')
def b_make_folder(I, e, a):
    p = _path(I, e, a[0])
    try:
        os.makedirs(p, exist_ok=True)
        return Ok(a[0])
    except OSError as ex:
        return _io_problem(ex, a[0])


@builtin("delete_file", 1, 1, 'delete_file of "old.txt"   -> ok "old.txt"   (files only, never folders)')
def b_delete_file(I, e, a):
    p = _path(I, e, a[0])
    if os.path.isdir(p):
        return Problem("\"%s\" is a folder; delete_file only removes files" % a[0])
    try:
        os.remove(p)
        return Ok(a[0])
    except OSError as ex:
        return _io_problem(ex, a[0])


@builtin("file_size", 1, 1, 'file_size of "photo.jpg"   -> ok 20480 (bytes)')
def b_file_size(I, e, a):
    p = _path(I, e, a[0])
    try:
        return Ok(os.path.getsize(p))
    except OSError as ex:
        return _io_problem(ex, a[0])


@builtin("join_path", 2, 20, 'join_path with "reports", "june.csv"   -> "reports/june.csv"   (any number of parts)')
def b_join_path(I, e, a):
    return os.path.join(*[text(I, e, x) for x in a])


@builtin("file_name", 1, 1, 'file_name of "/tmp/report.csv"   -> "report.csv"')
def b_file_name(I, e, a):
    return os.path.basename(text(I, e, a[0]))


@builtin("folder_of", 1, 1, 'folder_of of "/tmp/report.csv"   -> "/tmp"')
def b_folder_of(I, e, a):
    return os.path.dirname(text(I, e, a[0]))


@builtin("extension", 1, 1, 'extension of "report.csv"   -> "csv"')
def b_ext(I, e, a):
    return os.path.splitext(text(I, e, a[0]))[1].lstrip(".")


# ----------------------------------------------------------------------------- JSON
def to_py(I, e, v):
    if isinstance(v, bool) or v is None or isinstance(v, str):
        return v
    if is_num(v):
        return v
    if isinstance(v, PList):
        return [to_py(I, e, x) for x in v.items]
    if isinstance(v, (PSet,)):
        return [to_py(I, e, x) for x in sorted_items(v)]
    if isinstance(v, Tuple):
        return [to_py(I, e, x) for x in v.items]
    if isinstance(v, PMap):
        return {show(k): to_py(I, e, x) for k, x in v.d.items()}
    if isinstance(v, Record):
        return {k: to_py(I, e, x) for k, x in v.fields.items()}
    if isinstance(v, Variant):
        d = {"kind": v.vtype.name}
        d.update({k: to_py(I, e, x) for k, x in v.fields.items()})
        return d
    if isinstance(v, Some):
        return to_py(I, e, v.value)
    if v is NOTHING:
        return None
    if isinstance(v, Ok):
        return to_py(I, e, v.value)
    if isinstance(v, Problem):
        return {"problem": to_py(I, e, v.value)}
    I.err(e, TYPE_P, "%s can't be turned into JSON." % describe(v)[0].upper() + describe(v)[1:])


class _AnyType:
    """Type tag for JSON data: its lists and maps may hold mixed kinds of values."""
    name, args, var = "anything", [], False


ANY_T = _AnyType()


def from_py(x):
    if x is None:
        return NOTHING
    if isinstance(x, (bool, int, float, str)):
        return x
    if isinstance(x, list):
        out = PList([from_py(y) for y in x])
        out.elem_type = ANY_T
        return out
    if isinstance(x, dict):
        m = PMap()
        m.val_type = ANY_T
        for k, v in x.items():
            m.d[k] = from_py(v)
        return m
    return str(x)


@builtin("to_json", 1, 2, 'to_json of data   -> "{\\"name\\": \\"Ann\\"}"   (to_json with data, true  makes it pretty)')
def b_to_json(I, e, a):
    pretty = len(a) > 1 and a[1] is True
    return json.dumps(to_py(I, e, a[0]), indent=2 if pretty else None, ensure_ascii=False)


@builtin("from_json", 1, 1, 'from_json of text   -> ok value, or problem "bad JSON ..."   (objects become maps, null becomes nothing)')
def b_from_json(I, e, a):
    try:
        return Ok(from_py(json.loads(text(I, e, a[0]))))
    except json.JSONDecodeError as ex:
        return Problem("bad JSON at line %d, column %d: %s" % (ex.lineno, ex.colno, ex.msg))


@builtin("json_get", 2, 2, 'json_get with data, "user.address.city"   -> some value or nothing   (numbers pick list items, from 1)')
def b_json_get(I, e, a):
    cur = a[0]
    for part in text(I, e, a[1], " as the path").split("."):
        if isinstance(cur, PMap) and part in cur.d:
            cur = cur.d[part]
        elif isinstance(cur, PList) and part.isdigit() and 1 <= int(part) <= len(cur.items):
            cur = cur.items[int(part) - 1]
        elif isinstance(cur, Record) and part in cur.fields:
            cur = cur.fields[part]
        else:
            return NOTHING
    if cur is NOTHING:
        return NOTHING
    return Some(deep_copy(cur))


# ----------------------------------------------------------------------------- dates & times
def _moment(I, e, v):
    return _dt.datetime.fromtimestamp(num(I, e, v, " (a moment from `now`)"))


@builtin("now", 0, 0, "now   -> the current moment as seconds (use it with format_time, add_days, ...)")
def b_now(I, e, a):
    return time.time()


@builtin("today", 0, 0, 'today   -> "2026-10-08"')
def b_today(I, e, a):
    return _dt.date.today().isoformat()


@builtin("current_time", 0, 0, 'current_time   -> "14:03:22"')
def b_current_time(I, e, a):
    return _dt.datetime.now().strftime("%H:%M:%S")


_FMT = [("YYYY", "%Y"), ("MMMM", "%B"), ("MMM", "%b"), ("MM", "%m"), ("DDDD", "%A"), ("DDD", "%a"), ("DD", "%d"),
        ("hh", "%H"), ("mm", "%M"), ("ss", "%S")]


@builtin("format_time", 1, 2, 'format_time with now, "DD MMM YYYY, hh:mm"   -> "08 Oct 2026, 14:03"')
def b_format_time(I, e, a):
    m = _moment(I, e, a[0])
    pattern = text(I, e, a[1], " as the pattern") if len(a) > 1 else "YYYY-MM-DD hh:mm:ss"
    out, i = [], 0
    while i < len(pattern):
        for tok, code in _FMT:
            if pattern.startswith(tok, i):
                out.append(m.strftime(code))
                i += len(tok)
                break
        else:
            out.append(pattern[i])
            i += 1
    return "".join(out)


@builtin("parse_date", 1, 1, 'parse_date of "2026-10-08"   -> ok moment   (also "2026-10-08 14:30")')
def b_parse_date(I, e, a):
    s = text(I, e, a[0]).strip()
    for f in ("%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y"):
        try:
            return Ok(tidy(_dt.datetime.strptime(s, f).timestamp()))
        except ValueError:
            pass
    return Problem("\"%s\" is not a date I understand (try YYYY-MM-DD)" % s)


@builtin("add_days", 2, 2, "add_days with now, 7   -> the moment one week later")
def b_add_days(I, e, a):
    return tidy((_moment(I, e, a[0]) + _dt.timedelta(days=num(I, e, a[1]))).timestamp())


@builtin("days_between", 2, 2, "days_between with start, finish   -> whole days from start to finish")
def b_days_between(I, e, a):
    return (_moment(I, e, a[1]).date() - _moment(I, e, a[0]).date()).days


def _part(name, fn, help_text):
    REG[name] = (lambda I, e, a: fn(_moment(I, e, a[0])), 1, 1, help_text)


_part("year_of", lambda m: m.year, "year_of of now   -> 2026")
_part("month_of", lambda m: m.month, "month_of of now   -> 10")
_part("day_of", lambda m: m.day, "day_of of now   -> 8")
_part("hour_of", lambda m: m.hour, "hour_of of now   -> 14")
_part("minute_of", lambda m: m.minute, "minute_of of now   -> 3")
_part("weekday_of", lambda m: m.strftime("%A"), 'weekday_of of now   -> "Thursday"')


@builtin("seconds_since", 1, 1, "seconds_since of started   -> how long ago that moment was, in seconds")
def b_seconds_since(I, e, a):
    return time.time() - num(I, e, a[0])


# ----------------------------------------------------------------------------- program, environment, shell
@builtin("arguments", 0, 0, 'arguments   -> the words after the file name:  lekh run app.lekh add milk  ->  ["add", "milk"]')
def b_arguments(I, e, a):
    return PList(list(I.program_args))


@builtin("environment", 1, 1, 'environment of "HOME"   -> some "/home/sushant" or nothing')
def b_env(I, e, a):
    v = os.environ.get(text(I, e, a[0]))
    return Some(v) if v is not None else NOTHING


@builtin("read_all_input", 0, 0, "read_all_input   -> everything typed or piped into the program, as text")
def b_read_all(I, e, a):
    import sys
    return sys.stdin.read()


class ExitSignal(Exception):
    def __init__(self, code):
        self.code = code


@builtin("exit_program", 1, 1, "exit_program with 1   (stops at once; 0 means success)")
def b_exit(I, e, a):
    raise ExitSignal(whole_num(I, e, a[0]))


COMMAND_TIMEOUT = 60


@builtin("run_command", 1, 2, 'run_command of "git status"   -> ok CommandOutput(output, errors, code) or a problem   '
                              '(run_command with "ls", "/tmp" runs it in a folder)')
def b_run_command(I, e, a):
    # SAFETY: the command is split into words with shell rules (quotes work) but is NOT run by a shell, so
    # pipes, `;`, `&&`, `$VARS` and globs are passed as plain text - nobody can sneak a second command in
    # through a value you put in the text. It also has a time limit.
    cmd = text(I, e, a[0], " (the command)")
    try:
        words = shlex.split(cmd)
    except ValueError as ex:
        return Problem("can't split the command into words: %s" % ex)
    if not words:
        return Problem("the command is empty")
    cwd = _path(I, e, a[1]) if len(a) > 1 else None
    try:
        p = subprocess.run(words, capture_output=True, text=True, timeout=COMMAND_TIMEOUT, cwd=cwd)
    except FileNotFoundError:
        return Problem("no program called \"%s\" was found" % words[0])
    except PermissionError:
        return Problem("not allowed to run \"%s\"" % words[0])
    except subprocess.TimeoutExpired:
        return Problem("\"%s\" took longer than %d seconds and was stopped" % (cmd, COMMAND_TIMEOUT))
    except OSError as ex:
        return Problem(str(ex))
    return Ok(Record(COMMAND_OUTPUT, {"output": p.stdout, "errors": p.stderr, "code": p.returncode}))


# ----------------------------------------------------------------------------- HTTP
HTTP_TIMEOUT = 15


def _http(I, e, url, data=None, ctype=None, method=None):
    url = text(I, e, url, " (the web address)")
    if not url.startswith(("http://", "https://")):
        return Problem("only http:// and https:// addresses are allowed, not \"%s\"" % url)
    headers = {"User-Agent": "Lekh/0.2"}
    body = None
    if data is not None:
        body = data.encode("utf-8")
        headers["Content-Type"] = ctype or "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            raw, status, hdrs = r.read(), r.status, r.headers
    except urllib.error.HTTPError as ex:
        raw, status, hdrs = ex.read(), ex.code, ex.headers
    except urllib.error.URLError as ex:
        return Problem("couldn't reach %s: %s" % (url, ex.reason))
    except (TimeoutError, OSError) as ex:
        return Problem("couldn't reach %s: %s" % (url, ex))
    hm = PMap()
    for k, v in (hdrs.items() if hdrs else []):
        hm.d[k.lower()] = v
    return Ok(Record(RESPONSE, {"status": status, "body": raw.decode("utf-8", "replace"), "headers": hm}))


@builtin("http_get", 1, 1, 'http_get of "https://example.com"   -> ok Response(status, body, headers) or a problem')
def b_http_get(I, e, a):
    return _http(I, e, a[0])


@builtin("http_post", 2, 3, 'http_post with url, (to_json of data)   -> ok Response   (3rd input: content type)')
def b_http_post(I, e, a):
    data = a[1] if isinstance(a[1], str) else json.dumps(to_py(I, e, a[1]))
    ctype = text(I, e, a[2], " as the content type") if len(a) > 2 else None
    return _http(I, e, a[0], data, ctype, "POST")


# ----------------------------------------------------------------------------- improved core built-ins
def b_length(I, e, a):
    v = a[0]
    _need(I, e, v, ("text", "list", "map", "set", "tuple"), "text, a list, a map or a set")
    if isinstance(v, str):
        return len(v)
    if isinstance(v, PList):
        return len(v.items)
    if isinstance(v, PSet):
        return len(v.s)
    if isinstance(v, Tuple):
        return len(v.items)
    return len(v.d)


REG["length"] = (b_length, 1, 1, "length of cart")


def register():
    for name, (fn, lo, hi, h) in REG.items():
        BUILTINS[name] = (fn, lo, hi)
        BUILTIN_HELP[name] = h
        BUILTIN_ARITY[name] = (lo, hi)


register()
