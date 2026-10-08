"""Runtime support for programs made by `lekh build`.

A built program is plain Python that keeps Lekh's values (PList, PMap, Record, ...) and its
standard library, so results and error messages match `lekh run`.  The static checks
(ownership, names, types) already ran at build time, so here only the checks that depend on
actual values remain: missing values, list positions, division by zero, value kinds for
`anything`-typed data, and so on.
"""
import sys
import threading
import time

from . import core
from .core import (type_test_value, Interp, Loader, LekhError, PList, PMap, PSet, Tuple, Record, Variant, RecordType, ChoiceType,
                   VariantType, AbilityType, Some, NOTHING, NothingType, Ok, Problem, Channel, Job, PyTask, Builtin,
                   BUILTINS, ABILITY_IMPLS, deep_copy, is_big, is_num, show, describe, kind_of, kind_words, eq_struct,
                   matches_type, type_desc, sorted_items, sort_key, format_error, SOURCES,
                   TYPE_P, RANGE_P, MATH_P, MISSING_P, CASE_P, FAIL_P, UNHANDLED_P, NAME_P, CALL_P, LIMIT_P, PLACE_P, OWN_P,
                   TEST_P, CHANGE_P)
from . import stdlib  # noqa: F401  (registers built-ins)
from .stdlib import ExitSignal


class Loc:
    """Where something happens in the source (for error messages)."""
    __slots__ = ("line", "file", "name", "kind")

    def __init__(self, line, file, name=None, kind="Loc"):
        self.line, self.file, self.name, self.kind = line, file, name, kind


class TY:
    """A type annotation (same shape as the parser's Type nodes)."""
    def __init__(self, name, args=(), ret=None, var=False):
        self.name, self.args, self.ret, self.var = name, list(args), ret, var


class PAT:
    """A `when` pattern (same shape as the parser's Pat nodes)."""
    def __init__(self, pk, line, file, **kw):
        self.pk, self.line, self.file, self.kind = pk, line, file, "Pat"
        self.name = self.sub = self.value = self.lo = self.hi = None
        self.items, self.subs = [], []
        for k, v in kw.items():
            setattr(self, k, v)


class TryReturn(core.ReturnSignal):
    def __init__(self, value, loc):
        core.ReturnSignal.__init__(self, value, loc)
        self.loc = loc


class StopLoop(Exception):
    pass


class RT(Interp):
    def __init__(self):
        Interp.__init__(self, Loader())

    # ---------------------------------------------------------------- values
    def cp(self, v):
        return deep_copy(v) if is_big(v) else v

    def need_num(self, v, loc, word):
        if not is_num(v):
            self.no_maybe(v, loc, "used in math")
            self.err(loc, TYPE_P, "Only numbers can be %s, but this has %s." % (word, describe(v)),
                     "Convert text to a number first:  (x as number) or else 0")
        return v

    def add(self, a, b, loc):
        if is_num(a) and is_num(b):
            return a + b
        if isinstance(a, str) and isinstance(b, str):
            return a + b
        if isinstance(a, PList) and isinstance(b, PList):
            return PList([deep_copy(x) for x in a.items + b.items])
        if isinstance(a, PSet) and isinstance(b, PSet):
            return PSet(set(a.s | b.s))
        self.no_maybe(a, loc, "used in math")
        self.no_maybe(b, loc, "used in math")
        self.err(loc, TYPE_P, "Can't add %s and %s." % (describe(a), describe(b)),
                 "Put the value inside text instead:  \"Total: {total}\"")

    def sub(self, a, b, loc):
        if isinstance(a, PSet) and isinstance(b, PSet):
            return PSet(set(a.s - b.s))
        return self.need_num(a, loc, "subtracted") - self.need_num(b, loc, "subtracted")

    def mul(self, a, b, loc):
        return self.need_num(a, loc, "multiplied") * self.need_num(b, loc, "multiplied")

    def div(self, a, b, loc):
        self.need_num(a, loc, "divided")
        self.need_num(b, loc, "divided")
        if b == 0:
            self.err(loc, MATH_P, "Can't divide by zero.", "Check the number first:  if divisor is not 0: ...")
        if isinstance(a, int) and isinstance(b, int) and a % b == 0:
            return a // b
        return a / b

    def idiv(self, a, b, loc):
        self.need_num(a, loc, "divided")
        self.need_num(b, loc, "divided")
        if b == 0:
            self.err(loc, MATH_P, "Can't divide by zero.", "Check the number first:  if divisor is not 0: ...")
        return int(a // b)

    def mod(self, a, b, loc):
        self.need_num(a, loc, "used with mod")
        self.need_num(b, loc, "used with mod")
        if b == 0:
            self.err(loc, MATH_P, "Can't divide by zero.", "Check the number first:  if divisor is not 0: ...")
        return a % b

    def neg(self, a, loc):
        return -self.need_num(a, loc, "made negative")

    def T(self, v, loc, what="`if`"):
        if v is True or v is False:
            return v
        return self.truth(v, loc, what)

    def eq(self, a, b, loc):
        for x, y in ((a, b), (b, a)):
            if isinstance(x, (Some, Ok, Problem)) and not isinstance(y, (Some, Ok, Problem, NothingType)):
                self.err(loc, MISSING_P, "This might be %s (%s), so it can't be compared with %s directly." %
                         ("nothing" if isinstance(x, Some) else "a problem", show(x), show(y, True)),
                         "Give a fallback first:  (value or else 0) is %s" % show(y, True))
        if a is NOTHING or b is NOTHING:
            return a is b
        if kind_of(a) != kind_of(b) and not (isinstance(a, (Some, Ok, Problem)) and isinstance(b, (Some, Ok, Problem))):
            self.err(loc, TYPE_P, "You're comparing %s with %s - those can never be equal." % (describe(a), describe(b)))
        return eq_struct(a, b)

    def order(self, a, b, op, loc):
        self.no_maybe(a, loc, "compared")
        self.no_maybe(b, loc, "compared")
        if not ((is_num(a) and is_num(b)) or (isinstance(a, str) and isinstance(b, str))):
            self.err(loc, TYPE_P, "Only two numbers (or two texts) can be compared by size, but this has %s and %s." % (describe(a), describe(b)))
        if op == ">":
            return a > b
        if op == "<":
            return a < b
        if op == ">=":
            return a >= b
        return a <= b

    def contains(self, a, b, loc):
        self.no_maybe(a, loc, "searched")
        if isinstance(a, PList):
            return any(eq_struct(x, b) for x in a.items)
        if isinstance(a, str):
            if not isinstance(b, str):
                self.err(loc, TYPE_P, "Text can only contain text, not %s." % describe(b))
            return b in a
        if isinstance(a, PMap):
            return (isinstance(b, str) or is_num(b)) and not isinstance(b, bool) and b in a.d
        if isinstance(a, PSet):
            return b in a.s
        if isinstance(a, Tuple):
            return any(eq_struct(x, b) for x in a.items)
        self.err(loc, TYPE_P, "`contains` works with lists, text, maps and sets, but got %s." % describe(a))

    def starts(self, a, b, which, loc):
        if not (isinstance(a, str) and isinstance(b, str)):
            self.no_maybe(a, loc, "checked")
            self.err(loc, TYPE_P, "`%s with` works with text, but got %s and %s." % (which, describe(a), describe(b)))
        return a.startswith(b) if which == "starts" else a.endswith(b)

    def between(self, v, lo, hi, loc):
        for x in (v, lo, hi):
            self.no_maybe(x, loc, "compared")
        if not ((is_num(v) and is_num(lo) and is_num(hi)) or all(isinstance(x, str) for x in (v, lo, hi))):
            self.err(loc, TYPE_P, "`is between` needs three numbers (or three texts).")
        return lo <= v <= hi

    def test_wrap(self, v, what, loc):
        if what in ("nothing", "some"):
            if not isinstance(v, (Some, NothingType)):
                return what == "some"
            return (v is NOTHING) if what == "nothing" else isinstance(v, Some)
        if not isinstance(v, (Ok, Problem)):
            self.err(loc, TYPE_P, "`is %s` checks a result (ok/problem), but this is %s." % (what, describe(v)))
        return isinstance(v, Ok) if what == "ok" else isinstance(v, Problem)

    def replace_me(self, me, new):
        if isinstance(me, Record) and isinstance(new, Record):
            me.rtype, me.fields = new.rtype, new.fields
        elif isinstance(me, Variant) and isinstance(new, Variant):
            me.vtype, me.fields = new.vtype, new.fields
        else:
            raise LekhError(TYPE_P, "`me` can only be changed to another value of the same kind.", None, None, None)

    def type_test(self, v, tname):
        return type_test_value(v, tname)

    def or_else(self, v, fallback):
        if isinstance(v, (Some, Ok)):
            return v.value
        if v is NOTHING or isinstance(v, Problem):
            return fallback()
        return v

    def try_(self, v, loc):
        if isinstance(v, (Some, Ok)):
            return v.value
        if v is NOTHING or isinstance(v, Problem):
            raise TryReturn(v, loc)
        self.err(loc, TYPE_P, "`try` is for values that might be a problem or nothing, but this is %s." % describe(v))

    def text(self, v, loc):
        if isinstance(v, str):
            return v
        return self.showable(v, loc)

    def say(self, v, loc):
        t = v if isinstance(v, str) else self.showable(v, loc)
        with self.print_lock:
            print(t, flush=True)

    def ask(self, prompt, loc):
        p = self.text(prompt, loc) if prompt is not None else ""
        if p and not p.endswith(" "):
            p += " "
        with self.print_lock:
            sys.stdout.write(p)
            sys.stdout.flush()
            line = sys.stdin.readline()
            if not sys.stdin.isatty():
                sys.stdout.write(line if line.endswith("\n") else line + "\n")
        return line.rstrip("\r\n")

    def fail(self, v, loc):
        raise LekhError(FAIL_P, self.showable(v, loc), loc.line,
                        "This came from a `fail` line in the program. Handle the situation before it, or change the message.", loc.file)

    def chk(self, v, t, loc, what):
        if not matches_type(v, t):
            self.check_type(v, t, loc, what)
        return v

    # ---------------------------------------------------------------- collections
    def mklist(self, items, loc, elem_type=None):
        out = PList()
        if elem_type is not None:
            out.elem_type = elem_type
        for v in items:
            self.no_maybe(v, loc, "put in a list") if v is None else None
            self.check_elem(out, v, loc, "this list")
            out.items.append(v)
        return out

    def mkmap(self, pairs, loc, val_type=None):
        out = PMap()
        if val_type is not None:
            out.val_type = val_type
        for k, v in pairs:
            self.check_key(out, k, loc, "this map")
            if val_type is not None:
                if not matches_type(v, val_type):
                    self.err(loc, TYPE_P, "This map holds %s values, so it can't hold %s." % (type_desc(val_type), describe(v)))
            elif out.d:
                k0 = kind_of(next(iter(out.d.values())))
                if kind_of(v) != k0:
                    self.err(loc, TYPE_P, "This map holds %s values, so it can't also hold %s." % (kind_words(k0), describe(v)))
            out.d[k] = v
        return out

    def mkset(self, items, loc):
        out = PSet()
        for v in items:
            out.s.add(self.set_value(out, v, loc))
        return out

    def items(self, it, loc):
        if isinstance(it, PList):
            return list(it.items)
        if isinstance(it, PMap):
            return list(it.d.keys())
        if isinstance(it, PSet):
            return sorted_items(it)
        if isinstance(it, str):
            return list(it)
        if isinstance(it, Tuple):
            return list(it.items)
        self.no_maybe(it, loc, "looped over")
        self.err(loc, TYPE_P, "`for each` needs a list, map, set or text, but got %s." % describe(it),
                 "To count, write:  for each n from 1 to 10:")

    def channel_items(self, ch, loc):
        while True:
            got = self.receive(ch, loc)
            if got is NOTHING:
                return
            yield got.value

    def index(self, obj, idx, loc, name="the list"):
        if isinstance(obj, PList):
            return obj.items[self.index_of(obj, idx, loc, name)]
        if isinstance(obj, str):
            return obj[self.index_of(obj, idx, loc, name)]
        if isinstance(obj, Tuple):
            return obj.items[self.index_of(PList(list(obj.items)), idx, loc, name)]
        self.no_maybe(obj, loc, "indexed")
        self.err(loc, TYPE_P, "`item ... of` needs a list or text, but `%s` is %s." % (name, describe(obj)))

    def key(self, obj, k, loc, name="the map"):
        if isinstance(obj, PMap):
            self.no_maybe(k, loc, "used as a key")
            if isinstance(k, (str, int, float)) and not isinstance(k, bool) and k in obj.d:
                return Some(obj.d[k])
            return NOTHING
        self.no_maybe(obj, loc, "looked up")
        self.err(loc, TYPE_P, "`at` works with maps, but `%s` is %s." % (name, describe(obj)))

    def field(self, obj, name, loc):
        if isinstance(obj, (Record, Variant)) and name in obj.fields:
            return obj.fields[name]
        m = self.find_method(obj, name)
        if m is not None:
            return self.call_task(m, [obj], loc)
        if name in BUILTINS and not isinstance(obj, (Record, Variant)):
            fn, lo, hi = BUILTINS[name]
            if lo <= 1 <= hi:
                self.no_maybe(obj, loc, "asked for `%s`" % name)
                return fn(self, loc, [obj])
        self.no_maybe(obj, loc, "asked for a field")
        self.err(loc, NAME_P if isinstance(obj, (Record, Variant)) else TYPE_P,
                 "%s has no field called `%s`." % (describe(obj)[0].upper() + describe(obj)[1:], name))

    def set_field(self, obj, name, v, loc):
        if not isinstance(obj, Record):
            self.no_maybe(obj, loc, "changed")
            self.err(loc, TYPE_P, "Only the fields of a record can be changed, not of %s." % describe(obj))
        ftype = dict(obj.rtype.fields).get(name)
        if ftype is not None:
            self.chk(v, ftype, loc, "The field `%s`" % name)
        obj.fields[name] = v

    def set_index(self, obj, idx, v, loc, name="the list"):
        if not isinstance(obj, PList):
            self.no_maybe(obj, loc, "changed")
            self.err(loc, TYPE_P, "`item ... of` needs a list, but `%s` is %s." % (name, describe(obj)))
        i = self.index_of(obj, idx, loc, name)
        self.check_kind(kind_of(obj.items[i]), v, loc, "items of " + name)
        obj.items[i] = v

    def set_key(self, obj, k, v, loc, name="the map"):
        if not isinstance(obj, PMap):
            self.no_maybe(obj, loc, "changed")
            self.err(loc, TYPE_P, "`at` works with maps, but `%s` is %s." % (name, describe(obj)))
        self.check_key(obj, k, loc, name)
        vt = getattr(obj, "val_type", None)
        if vt is not None:
            if not matches_type(v, vt):
                self.err(loc, TYPE_P, "`%s` holds %s values, so it can't hold %s." % (name, type_desc(vt), describe(v)))
        elif obj.d:
            k0 = obj.d[k] if k in obj.d else next(iter(obj.d.values()))
            self.check_kind(kind_of(k0), v, loc, "values of " + name)
        if k not in obj.d:
            self.check_looping(obj, loc, name, "add new keys to")
        obj.d[k] = v

    def add_to(self, tv, v, loc, name):
        if isinstance(tv, PList):
            self.check_looping(tv, loc, name, "add to")
            self.check_elem(tv, v, loc, name)
            tv.items.append(v)
            return tv
        if isinstance(tv, PSet):
            tv.s.add(self.set_value(tv, v, loc))
            return tv
        if isinstance(tv, str):
            if not isinstance(v, str):
                self.err(loc, TYPE_P, "`%s` is text, so only text can be added to it, not %s." % (name, describe(v)))
            return tv + v
        self.no_maybe(tv, loc, "added to")
        self.err(loc, TYPE_P, "You can only add to a list, set or text, but `%s` is %s." % (name, describe(tv)))

    def remove_from(self, tv, v, by_pos, loc, name):
        if isinstance(tv, PList):
            self.check_looping(tv, loc, name, "remove from")
            if by_pos:
                tv.items.pop(self.index_of(tv, v, loc, name))
                return
            for i, x in enumerate(tv.items):
                if eq_struct(x, v):
                    tv.items.pop(i)
                    return
            self.err(loc, RANGE_P, "%s isn't in `%s`, so it can't be removed." % (show(v, True), name))
        if isinstance(tv, PSet):
            if v not in tv.s:
                self.err(loc, RANGE_P, "%s isn't in the set `%s`, so it can't be removed." % (show(v, True), name))
            tv.s.discard(v)
            return
        if isinstance(tv, PMap):
            if v not in tv.d:
                self.err(loc, RANGE_P, "The map `%s` has no key %s." % (name, show(v, True)))
            del tv.d[v]
            return
        self.no_maybe(tv, loc, "removed from")
        self.err(loc, TYPE_P, "You can only remove from a list, set or map, but `%s` is %s." % (name, describe(tv)))

    def take_from(self, tv, which, loc, name):
        if isinstance(tv, PList):
            self.check_looping(tv, loc, name, "take from")
            if not tv.items:
                return NOTHING
            return Some(tv.items.pop(0) if which == "first" else tv.items.pop())
        self.no_maybe(tv, loc, "taken from")
        self.err(loc, TYPE_P, "`take %s from` needs a list, but `%s` is %s." % (which, name, describe(tv)))

    def incr(self, cur, amt, sign, loc):
        verb = "increase" if sign > 0 else "decrease"
        for v in (cur, amt):
            self.no_maybe(v, loc, "%sd" % verb)
            if not is_num(v):
                self.err(loc, TYPE_P, "Only numbers can be %sd, but this is %s." % (verb, describe(v)))
        return cur + amt * sign

    def range_list(self, a, b, step, loc):
        a, b = self.whole(a, loc, "A range"), self.whole(b, loc, "A range")
        step = self.whole(step, loc, "A range") if step is not None else None
        return PList(list(self.counting(a, b, step, loc)))

    def count_range(self, a, b, step, loc):
        a, b = self.whole(a, loc), self.whole(b, loc)
        step = self.whole(step, loc) if step is not None else None
        return self.counting(a, b, step, loc)

    def repeat_count(self, n, loc):
        self.no_maybe(n, loc, "used as a count")
        if not is_num(n) or (isinstance(n, float) and not n.is_integer()) or n < 0:
            self.err(loc, TYPE_P, "`repeat` needs a whole number of times (0 or more), but got %s." % describe(n))
        return range(int(n))

    def convert(self, v, t, loc):
        if t == "text":
            self.no_maybe(v, loc, "turned into text")
            return show(v)
        if t in ("number", "integer", "decimal"):
            if isinstance(v, str):
                s = v.strip().replace("_", "")
                try:
                    v = int(s)
                except ValueError:
                    try:
                        v = float(s)
                        if v != v or v in (float("inf"), float("-inf")):
                            raise ValueError
                    except ValueError:
                        return Problem("\"%s\" is not a number" % v if isinstance(v, str) else s)
            if not is_num(v):
                self.no_maybe(v, loc, "turned into a number")
                return Problem("%s can't be turned into a number" % describe(v))
            if t == "integer":
                return Ok(int(v))
            if t == "decimal":
                return Ok(float(v))
            return Ok(v)
        if t == "list":
            return PList([deep_copy(x) for x in self.hof_items(v, loc)])
        if t == "set":
            return self.mkset(self.hof_items(v, loc), loc)
        self.err(loc, TYPE_P, "`as` can't turn %s into `%s`." % (describe(v), t))

    def construct(self, t, fields, loc):
        declared = t.fields
        out = {}
        for fn, ftype in declared:
            v = fields[fn]
            if ftype is not None:
                self.chk(v, ftype, loc, "The field `%s` of %s %s" % (fn, "an" if t.name[:1] in "AEIOU" else "a", t.name))
            out[fn] = v
        return Record(t, out) if isinstance(t, RecordType) else Variant(t, out)

    # ---------------------------------------------------------------- list forms
    def sort_by(self, items, keyfn, desc, loc):
        keyed = []
        for x in items:
            kv = keyfn(x)
            self.no_maybe(kv, loc, "used to sort")
            keyed.append((sort_key(kv, self, loc), x))
        keyed.sort(key=lambda t: t[0], reverse=desc)
        return PList([deep_copy(x) for _, x in keyed])

    def find_first(self, items, cond):
        for x in items:
            if cond(x):
                return Some(deep_copy(x))
        return NOTHING

    def combine(self, items, init, step):
        acc = self.cp(init)
        for x in items:
            acc = step(acc, x)
        return self.cp(acc)

    def turn(self, items, fn, loc):
        out = PList()
        for x in items:
            v = self.cp(fn(x))
            self.check_elem(out, v, loc, "the new list")
            out.items.append(v)
        return out

    # ---------------------------------------------------------------- tasks
    def call_task(self, fn, values, loc, want=True):
        if isinstance(fn, PyTask):
            if len(values) != fn.nparams:
                self.err(loc, CALL_P, "`%s` needs %d input%s, but got %d." % (fn.name, fn.nparams, "" if fn.nparams == 1 else "s", len(values)))
            r = fn.fn(*values)
            if want and r is None:
                self.err(loc, TYPE_P, "`%s` doesn't give back a value, so there's nothing to use here." % fn.name)
            return r
        if isinstance(fn, Builtin):
            return fn.fn(self, loc, values)
        self.no_maybe(fn, loc, "called")
        self.err(loc, TYPE_P, "Expected a task here, but got %s." % describe(fn))

    def method(self, obj, name, args, loc, want=True):
        m = self.find_method(obj, name)
        if m is not None:
            return self.call_task(m, [obj] + args, loc, want)
        if isinstance(obj, (Record, Variant)) and name in obj.fields and isinstance(obj.fields[name], (PyTask, Builtin)):
            return self.call_task(obj.fields[name], args, loc, want)
        if name in BUILTINS:
            fn, lo, hi = BUILTINS[name]
            return fn(self, loc, [obj] + args)
        self.no_maybe(obj, loc, "asked to `%s`" % name)
        self.err(loc, NAME_P, "%s has no field or task called `%s`." % (describe(obj)[0].upper() + describe(obj)[1:], name))

    def depth_in(self, loc, name):
        d = self.depth + 1
        self.depth = d
        if d > core.MAX_DEPTH:
            self.depth = 0
            self.err(loc, LIMIT_P, "`%s` called itself (or other tasks) more than %d levels deep." % (name, core.MAX_DEPTH),
                     "Make sure the task has a stopping case, e.g.  if n is 0: give back 1")

    def ret_check(self, v, t, loc, name):
        if v is None:
            self.err(loc, TYPE_P, "`%s` promises to give back %s, but it finished without `give back`." % (name, type_desc(t)))
        if t is not None and not matches_type(v, t):
            self.check_type(v, t, loc, "The value given back by `%s`" % name)
        return v

    # ---------------------------------------------------------------- patterns
    def when_match(self, p, v, loc, binds):
        return self.match(p, v, loc, binds)

    def no_case(self, v, loc):
        self.err(loc, CASE_P, "No case in this `when` matches %s." % describe(v), "Add `otherwise:` at the end to handle everything else.")

    # ---------------------------------------------------------------- concurrency
    def parallel(self, fns, loc):
        self.run_parallel(fns, loc)

    def send(self, ch, v, loc):
        if not isinstance(ch, Channel):
            self.err(loc, TYPE_P, "Expected a channel, but got %s." % describe(ch))
        if ch.closed:
            self.err(loc, PLACE_P, "This channel was closed, so nothing more can be sent to it.")
        v = deep_copy(v) if is_big(v) else v
        with self.worker_lock:
            if ch.kind is None:
                ch.kind = kind_of(v)
        if ch.kind != kind_of(v):
            self.err(loc, TYPE_P, "This channel carries %s, so it can't also carry %s." % (kind_words(ch.kind), describe(v)))
        ch.q.put(v)

    def close(self, ch, loc):
        if not isinstance(ch, Channel):
            self.err(loc, TYPE_P, "Expected a channel, but got %s." % describe(ch))
        ch.closed = True

    def recv(self, ch, loc):
        if not isinstance(ch, Channel):
            self.err(loc, TYPE_P, "Expected a channel, but got %s." % describe(ch))
        return self.receive(ch, loc)

    def start(self, fn, values, loc):
        values = [deep_copy(v) if is_big(v) else v for v in values]
        job = Job(getattr(fn, "name", "job"))

        def run():
            self.tl.worker = True
            try:
                job.result = self.call_task(fn, values, loc, want=False)
            except LekhError as ex:
                job.error = ex
            except TryReturn as t:
                job.result = t.value
            finally:
                job.done = True
                with self.worker_lock:
                    self.workers -= 1
        with self.worker_lock:
            self.workers += 1
        job.thread = threading.Thread(target=run, daemon=True)
        job.thread.start()
        return job

    def wait_for(self, job, loc, want=True):
        if isinstance(job, PList):
            return PList([self.finish_job(j, loc, want) for j in job.items])
        return self.finish_job(job, loc, want)

    def sleep(self, n, loc):
        if not is_num(n) or n < 0:
            self.err(loc, TYPE_P, "`wait` needs a number of seconds, but got %s." % describe(n))
        time.sleep(min(n, 3600))

    def expect(self, a, how, b, neg, loc, src):
        if how == "be":
            ok = (abs(a - b) < 1e-9) if (is_num(a) and is_num(b)) else (kind_of(a) == kind_of(b) and eq_struct(a, b))
            words = "to be %s" % show(b, True)
        elif how == "contain":
            ok = self.contains(a, b, loc)
            words = "to contain %s" % show(b, True)
        else:
            ok = {"ok": isinstance(a, Ok), "problem": isinstance(a, Problem), "nothing": a is NOTHING, "some": isinstance(a, Some)}[how]
            words = "to be %s" % how
        if neg:
            ok = not ok
        if not ok:
            raise LekhError(TEST_P, "Expected `%s` %s%s, but it was %s." % (src, "not " if neg else "", words, show(a, True)), loc.line, None, loc.file)


R = RT()


def run_main(main_fn, sources, args):
    for f, text in sources.items():
        SOURCES[f] = text.split("\n")
    R.program_args = list(args)
    sys.setrecursionlimit(100000)
    try:
        threading.stack_size(64 * 1024 * 1024)
    except (ValueError, RuntimeError):
        pass
    result = {}

    def go():
        try:
            main_fn()
            result["code"] = 0
        except LekhError as e:
            sys.stdout.flush()
            sys.stderr.write(format_error(e))
            result["code"] = 1
        except TryReturn as t:
            sys.stdout.flush()
            why = show(t.value.value) if isinstance(t.value, Problem) else "nothing"
            sys.stderr.write(format_error(LekhError(UNHANDLED_P, "A `try` here got %s, and there's no task around it to pass the problem up to." %
                                                    ("the problem: " + why if isinstance(t.value, Problem) else "nothing (a missing value)"),
                                                    t.loc.line, "Handle it right here with `when`, or give a fallback with `or else`.", t.loc.file)))
            result["code"] = 1
        except ExitSignal as x:
            sys.stdout.flush()
            result["code"] = x.code
        except RecursionError:
            sys.stderr.write(format_error(LekhError(LIMIT_P, "The program went too deep (a task probably calls itself forever).")))
            result["code"] = 1
    # run on a big-stack thread so deep recursion works like `lekh run`
    t = threading.Thread(target=go)
    t.start()
    try:
        t.join()
    except KeyboardInterrupt:
        sys.stderr.write("\nStopped.\n")
        return 130
    return result.get("code", 1)
