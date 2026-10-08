"""Lekh's static type checker (gradual).

Runs after the ownership/name Checker and before the program starts. It infers a type for
every expression and reports mismatches with friendly messages:

  * known types flow from literals, annotations, record fields, task results and built-ins;
  * generic tasks (`items as list of T gives T`) are instantiated at each call by unifying
    the type variables with the argument types;
  * anything it can't know (an unannotated task input, JSON data, ...) is `anything`,
    and is still checked when the program runs.  So a program that type-checks can never be
    wrong about a type the checker *did* know.
"""
from .core import LekhError, TYPE_P, CALL_P, NAME_P, MISSING_P, KNOWN_ABILITIES, BUILTINS


class Ty:
    __slots__ = ("name", "args", "ret")

    def __init__(self, name, args=(), ret=None):
        self.name, self.args, self.ret = name, tuple(args), ret

    def __repr__(self):
        return show_ty(self)


ANY = Ty("anything")
NUM, TEXT, TRUTH = Ty("number"), Ty("text"), Ty("truth")
PRIMS = ("number", "text", "truth")


def L(t):
    return Ty("list", [t])


def M(k, v):
    return Ty("map", [k, v])


def MAYBE(t):
    return Ty("maybe", [t])


def RES(t, e=None):
    return Ty("result", [t, e or ANY])


def is_var(t):
    return len(t.name) == 1 and t.name.isupper()


def show_ty(t):
    n = t.name
    if n in ("list", "set", "channel", "job"):
        return "%s of %s" % (n, show_ty(t.args[0]))
    if n == "map":
        return "map of %s to %s" % (show_ty(t.args[0]), show_ty(t.args[1]))
    if n == "maybe":
        return "maybe " + show_ty(t.args[0])
    if n == "result":
        e = t.args[1] if len(t.args) > 1 else ANY
        return "result of " + show_ty(t.args[0]) + ("" if e.name == "anything" else " or " + show_ty(e))
    if n == "tuple":
        return "(" + ", ".join(show_ty(a) for a in t.args) + ")"
    if n == "task":
        r = "task"
        if t.args:
            r += " of " + " and ".join(show_ty(a) for a in t.args)
        if t.ret is not None:
            r += " gives " + show_ty(t.ret)
        return r
    if t.args:
        return n + " of " + " and ".join(show_ty(a) for a in t.args)
    return n


def words(t):
    n = t.name
    if n == "number":
        return "a number"
    if n == "text":
        return "text"
    if n == "truth":
        return "true/false"
    if n in ("integer", "decimal"):
        return "a whole number" if n == "integer" else "a decimal number"
    if n in ("list", "map", "set", "task", "channel", "job"):
        return "a " + show_ty(t)
    if n in ("maybe", "result"):
        return "a " + show_ty(t)
    if n == "tuple":
        return "a group " + show_ty(t)
    return ("an " if n[:1].lower() in "aeiou" else "a ") + show_ty(t)


def from_node(t, tparams=()):
    """Convert a parser Type node into a Ty."""
    if t is None:
        return ANY
    n = t.name
    if n == "anything":
        return ANY
    if n in ("integer", "decimal"):
        return NUM
    if n == "task":
        return Ty("task", [from_node(a) for a in t.args], from_node(t.ret) if getattr(t, "ret", None) is not None else None)
    if n == "result" and len(t.args) == 1:
        return RES(from_node(t.args[0]))
    return Ty(n, [from_node(a) for a in t.args])


# ------------------------------------------------------------------------- built-in signatures
def _sig(params, ret, rest=None):
    return (params, ret)


T, K, V = Ty("T"), Ty("K"), Ty("V")
SIGS = {
    "length": ([ANY], NUM), "first": ([L(T)], T), "last": ([L(T)], T),
    "uppercase": ([TEXT], TEXT), "lowercase": ([TEXT], TEXT), "trimmed": ([TEXT], TEXT), "capitalized": ([TEXT], TEXT),
    "title_case": ([TEXT], TEXT), "trim_start": ([TEXT], TEXT), "trim_end": ([TEXT], TEXT),
    "words": ([TEXT], L(TEXT)), "lines": ([TEXT], L(TEXT)), "letters": ([TEXT], L(TEXT)),
    "sum": ([L(NUM)], NUM), "average": ([L(NUM)], NUM), "keys": ([M(K, V)], L(K)), "values": ([M(K, V)], L(V)),
    "round": ([NUM, NUM], NUM), "absolute": ([NUM], NUM), "sqrt": ([NUM], NUM), "random": ([NUM, NUM], NUM),
    "join": ([L(ANY), TEXT], TEXT), "split": ([TEXT, TEXT], L(TEXT)), "replace": ([TEXT, TEXT, TEXT], TEXT),
    "pad_left": ([ANY, NUM, TEXT], TEXT), "pad_right": ([ANY, NUM, TEXT], TEXT), "centered": ([ANY, NUM, TEXT], TEXT),
    "repeat_text": ([TEXT, NUM], TEXT), "is_number": ([ANY], TRUTH), "letter_code": ([TEXT], NUM),
    "letter_from_code": ([NUM], TEXT), "is_blank": ([TEXT], TRUTH), "type_of": ([ANY], TEXT),
    "power": ([NUM, NUM], NUM), "format_number": ([NUM, NUM], TEXT), "with_commas": ([NUM, NUM], TEXT),
    "whole": ([NUM], NUM), "floor": ([NUM], NUM), "ceiling": ([NUM], NUM), "is_whole": ([NUM], TRUTH),
    "clamp": ([NUM, NUM, NUM], NUM), "sign": ([NUM], NUM), "pi": ([], NUM), "hex": ([NUM], TEXT), "binary": ([NUM], TEXT),
    "sine": ([NUM], NUM), "cosine": ([NUM], NUM), "tangent": ([NUM], NUM), "log": ([NUM], NUM), "log10": ([NUM], NUM),
    "exp": ([NUM], NUM), "radians": ([NUM], NUM), "degrees": ([NUM], NUM),
    "random_decimal": ([], NUM), "random_item": ([L(T)], T), "shuffled": ([L(T)], L(T)), "seed_random": ([NUM], None),
    "unique": ([L(T)], L(T)), "numbered": ([L(T)], L(Ty("tuple", [NUM, T]))), "chunks": ([L(T), NUM], L(L(T))),
    "pairs": ([M(K, V)], L(Ty("tuple", [K, V]))), "merged": ([M(K, V), M(K, V)], M(K, V)),
    "union": ([Ty("set", [T]), Ty("set", [T])], Ty("set", [T])),
    "intersection": ([Ty("set", [T]), Ty("set", [T])], Ty("set", [T])),
    "difference": ([Ty("set", [T]), Ty("set", [T])], Ty("set", [T])),
    "is_subset": ([Ty("set", [T]), Ty("set", [T])], TRUTH),
    "matches": ([TEXT, TEXT], TRUTH), "contains_pattern": ([TEXT, TEXT], TRUTH), "find_all": ([TEXT, TEXT], L(TEXT)),
    "find_groups": ([TEXT, TEXT], L(L(TEXT))), "replace_pattern": ([TEXT, TEXT, TEXT], TEXT),
    "split_pattern": ([TEXT, TEXT], L(TEXT)), "matches_wildcard": ([TEXT, TEXT], TRUTH),
    "read_file": ([TEXT], RES(TEXT, TEXT)), "read_lines": ([TEXT], RES(L(TEXT), TEXT)),
    "write_file": ([TEXT, ANY], RES(NUM, TEXT)), "append_file": ([TEXT, ANY], RES(NUM, TEXT)),
    "file_exists": ([TEXT], TRUTH), "is_folder": ([TEXT], TRUTH), "list_folder": ([TEXT], RES(L(TEXT), TEXT)),
    "make_folder": ([TEXT], RES(TEXT, TEXT)), "delete_file": ([TEXT], RES(TEXT, TEXT)), "file_size": ([TEXT], RES(NUM, TEXT)),
    "join_path": ([TEXT, TEXT], TEXT), "file_name": ([TEXT], TEXT), "folder_of": ([TEXT], TEXT), "extension": ([TEXT], TEXT),
    "to_json": ([ANY, TRUTH], TEXT), "from_json": ([TEXT], RES(ANY, TEXT)), "json_get": ([ANY, TEXT], MAYBE(ANY)),
    "now": ([], NUM), "today": ([], TEXT), "current_time": ([], TEXT), "format_time": ([NUM, TEXT], TEXT),
    "parse_date": ([TEXT], RES(NUM, TEXT)), "add_days": ([NUM, NUM], NUM), "days_between": ([NUM, NUM], NUM),
    "year_of": ([NUM], NUM), "month_of": ([NUM], NUM), "day_of": ([NUM], NUM), "hour_of": ([NUM], NUM),
    "minute_of": ([NUM], NUM), "weekday_of": ([NUM], TEXT), "seconds_since": ([NUM], NUM),
    "arguments": ([], L(TEXT)), "environment": ([TEXT], MAYBE(TEXT)), "read_all_input": ([], TEXT),
    "exit_program": ([NUM], None),
    "run_command": ([TEXT, TEXT], RES(Ty("CommandOutput"), TEXT)),
    "http_get": ([TEXT], RES(Ty("Response"), TEXT)), "http_post": ([TEXT, ANY, TEXT], RES(Ty("Response"), TEXT)),
    "position": ([ANY, ANY], MAYBE(NUM)), "count_of": ([ANY, ANY], NUM), "slice": ([T, NUM, NUM], T),
    "flatten": ([L(L(T))], L(T)), "pairs_of": ([L(T), L(V)], L(Ty("tuple", [T, V]))),
    "map_from": ([L(Ty("tuple", [K, V]))], M(K, V)),
    "sorted_using": ([L(T), ANY], L(T)), "transform": ([L(ANY), ANY], L(ANY)), "select": ([L(T), ANY], L(T)),
    "reduce": ([L(ANY), T, ANY], T), "smaller": ([T, T], T), "larger": ([T, T], T),
    "reversed": ([T], T), "sorted": ([L(T)], L(T)), "largest": ([L(T)], T), "smallest": ([L(T)], T),
}
BUILTIN_FIELDS = {
    "CommandOutput": {"output": TEXT, "errors": TEXT, "code": NUM},
    "Response": {"status": NUM, "body": TEXT, "headers": M(TEXT, TEXT)},
}


class TypeChecker:
    def __init__(self, module, loader):
        self.m, self.loader = module, loader
        self.records, self.choices, self.variants = {}, {}, {}
        self.funcs, self.methods, self.abilities, self.impls = {}, {}, {}, {}
        self.scopes = [{}]
        self.ret_stack = []

    # ------------------------------------------------------------------ errors
    def err(self, node, msg, fix=None, title=TYPE_P):
        raise LekhError(title, msg, node.line, fix, node.file)

    # ------------------------------------------------------------------ setup
    def collect(self, ast, imported=False):
        for s in ast:
            if imported and not getattr(s, "shared", False) and s.kind != "Can" and not (s.kind == "FuncDef" and s.owner):
                continue
            k = s.kind
            if k == "RecordDef":
                self.records[s.name] = (list(s.tparams or []), {f: from_node(t) for f, t in s.fields})
            elif k == "ChoiceDef":
                self.choices[s.name] = list(s.tparams or [])
                for vn, fields, _ in s.variants:
                    self.variants[vn] = (s.name, [(f, from_node(t)) for f, t in fields])
            elif k == "FuncDef":
                if s.owner:
                    self.methods[(s.owner, s.name)] = s
                else:
                    self.funcs[s.name] = s
            elif k == "AbilityDef":
                self.abilities[s.name] = s
                for m in s.methods:
                    self.methods.setdefault((s.name, m.name), m)
            elif k == "Can":
                self.impls.setdefault(s.tname, set()).add(s.ability)

    def check(self):
        for s in self.m.ast:
            if s.kind == "Use":
                mod = self.loader.modules.get(s.path)
                if mod is not None:
                    self.collect(mod.ast, imported=True)
                    for d in mod.ast:
                        if d.kind == "Let" and getattr(d, "shared", False) and not d.changeable:
                            self.scopes[0][d.name] = ANY
        self.collect(self.m.ast)
        for s in self.m.ast:
            if s.kind not in ("FuncDef", "RecordDef", "ChoiceDef", "AbilityDef", "Can", "Use", "TestBlock"):
                self.stmt(s)
        # top-level names are visible (read-only) inside task bodies
        for s in self.m.ast:
            if s.kind == "FuncDef":
                self.func_body(s)
            elif s.kind == "AbilityDef":
                for m in s.methods:
                    if m.body is not None:
                        self.func_body(m, owner_override=s.name)
            elif s.kind == "TestBlock":
                self.push()
                self.block(s.body)
                self.pop()

    def func_body(self, d, owner_override=None):
        saved = self.scopes
        self.scopes = [saved[0], {}]
        owner = owner_override or d.owner
        if owner:
            self.declare("me", self.named_type(owner))
        for p in d.params:
            self.declare(p.name, from_node(p.type))
        self.ret_stack.append((d, from_node(d.ret) if d.ret is not None else None))
        self.block(d.body)
        self.ret_stack.pop()
        self.scopes = saved

    def named_type(self, name):
        if name in self.records:
            return Ty(name, [ANY] * len(self.records[name][0]))
        if name in self.choices:
            return Ty(name, [ANY] * len(self.choices[name]))
        return Ty(name)

    # ------------------------------------------------------------------ scopes
    def push(self):
        self.scopes.append({})

    def pop(self):
        self.scopes.pop()

    def declare(self, name, t):
        self.scopes[-1][name] = t

    def lookup(self, name):
        for sc in reversed(self.scopes):
            if name in sc:
                return sc[name]
        return None

    def block(self, stmts):
        self.push()
        for s in stmts:
            self.stmt(s)
        self.pop()

    # ------------------------------------------------------------------ compatibility
    def resolve(self, t, b):
        if is_var(t):
            return b.get(t.name, ANY)
        if not t.args and t.ret is None:
            return t
        return Ty(t.name, [self.resolve(a, b) for a in t.args], self.resolve(t.ret, b) if t.ret is not None else None)

    def fits(self, want, got, b=None):
        """Can a value of type `got` be used where `want` is expected? Binds type variables in b."""
        if b is None:
            b = {}
        if want.name == "anything" or got.name == "anything":
            return True
        if is_var(want):
            if want.name in b:
                prev = b[want.name]
                if prev.name == "anything":
                    b[want.name] = got
                    return True
                return self.fits(prev, got, {}) or self.fits(got, prev, {})
            b[want.name] = got
            return True
        if is_var(got):
            return True
        if want.name in self.abilities:
            if got.name == want.name:
                return True
            return want.name in self.impls.get(got.name, ()) or got.name in self.abilities
        if got.name in self.variants:
            got = Ty(self.variants[got.name][0])
        if want.name in self.variants:
            want = Ty(self.variants[want.name][0])
        if want.name != got.name:
            return False
        if want.name == "task":
            return True
        if len(want.args) != len(got.args):
            return want.name not in ("tuple",)
        return all(self.fits(w, g, b) for w, g in zip(want.args, got.args))

    def join(self, a, b):
        if a.name == "anything":
            return b
        if b.name == "anything":
            return a
        if self.fits(a, b) and self.fits(b, a):
            if a.args and any(x.name == "anything" for x in a.args):
                return b
            return a
        return ANY

    def mismatch(self, node, what, want, got, fix=None):
        if fix is None and got.name == "task" and want.name != "task" and getattr(node, "kind", "") == "Name":
            fix = "To call a task that takes nothing, write `(run %s)`." % node.name
        self.err(node, "%s should be %s, but here it's %s." % (what, words(want), words(got)), fix)

    # ------------------------------------------------------------------ statements
    def stmt(self, s):
        fn = getattr(self, "s_" + s.kind, None)
        if fn is not None:
            fn(s)

    def s_Let(self, s):
        if s.type is not None and s.expr.kind == "ListLit" and getattr(s.type, "args", None) \
                and s.type.name == "list" and s.type.args[0].name not in PRIMS:
            s.expr.mixed_ok = True      # `let xs as list of anything/Ability be list of ...`
        got = self.expr(s.expr)
        if s.type is not None:
            want = from_node(s.type)
            if not self.fits(want, got):
                self.mismatch(s, "`%s`" % s.name, want, got, self.convert_hint(want, got, s.name))
            got = want if want.name != "anything" else got
        self.declare(s.name, got)

    def convert_hint(self, want, got, name):
        if want.name == "number" and got.name == "text":
            return "Turn text into a number with a fallback:  (value as number) or else 0"
        if want.name == "text" and got.name == "number":
            return "Turn the number into text:  value as text"
        if want.name == "maybe" and got.name != "maybe":
            return "Wrap the value:  some value"
        if got.name in ("maybe", "result") and want.name not in ("maybe", "result"):
            return "Unwrap it first:  value or else <fallback>   or   try value"
        return None

    def s_LetTuple(self, s):
        got = self.expr(s.expr)
        if got.name == "tuple" and len(got.args) != len(s.names):
            self.err(s, "This gives a group of %d values, but you named %d (%s)." % (len(got.args), len(s.names), ", ".join(s.names)))
        for i, n in enumerate(s.names):
            self.declare(n, got.args[i] if got.name == "tuple" and i < len(got.args) else ANY)

    def s_Change(self, s):
        got = self.expr(s.expr)
        if s.target.kind == "Name":
            cur = self.lookup(s.target.name)
            if cur is not None and not self.fits(cur, got):
                self.err(s, "`%s` holds %s, so it can't become %s." % (s.target.name, words(cur), words(got)),
                         "Keep the same kind of value, or make a new variable:  let %s_new be ..." % s.target.name)
        else:
            cur = self.target_type(s.target)
            if not self.fits(cur, got):
                self.err(s, "This place holds %s, so it can't be set to %s." % (words(cur), words(got)))

    def target_type(self, tg):
        if tg.kind == "Key":
            objt = self.expr(tg.obj)
            self.expr(tg.key)
            return objt.args[1] if objt.name == "map" else ANY
        return self.expr(tg)

    def s_Increase(self, s):
        cur, amt = self.target_type(s.target), self.expr(s.expr)
        verb = "increase" if s.sign > 0 else "decrease"
        for t, n in ((cur, s.target), (amt, s.expr)):
            if t.name not in ("number", "anything") and not is_var(t):
                self.err(n, "Only numbers can be %sd, but this is %s." % (verb, words(t)),
                         "To add to text or a list, use:  add <value> to ..." if verb == "increase" else None)

    def s_Add(self, s):
        tv, v = self.expr(s.target), self.expr(s.expr)
        if tv.name in ("list", "set") and tv.args and not self.fits(tv.args[0], v):
            self.err(s, "`%s` holds %s, so you can't put %s in it." % (self.src(s.target), words(tv.args[0]), words(v)))
        if tv.name == "text" and v.name not in ("text", "anything"):
            self.err(s, "Only text can be added to text, not %s." % words(v), 'Put the value inside text:  add "{value}" to ...')

    def s_Remove(self, s):
        self.expr(s.target)
        self.expr(s.expr)

    def s_Say(self, s):
        if s.expr is not None:
            self.expr(s.expr)

    def s_ExprStmt(self, s):
        self.expr(s.expr)

    def cond(self, e, what):
        t = self.expr(e)
        if t.name not in ("truth", "anything") and not is_var(t):
            fix = None
            if t.name == "maybe":
                fix = "To check for a missing value:  if x is nothing: ...   or   if x is some: ..."
            elif t.name == "number":
                fix = "Compare it to something:  if count is greater than 0: ..."
            self.err(e, "%s needs true/false, but this is %s." % (what, words(t)), fix)

    def s_If(self, s):
        for c, body in s.branches:
            self.cond(c, "An `if` condition")
            self.block(body)
        if s.other is not None:
            self.block(s.other)

    def s_While(self, s):
        self.cond(s.cond, "A `while` condition")
        self.block(s.body)

    def s_Repeat(self, s):
        t = self.expr(s.count)
        if t.name not in ("number", "anything"):
            self.err(s.count, "`repeat` needs a number of times, but this is %s." % words(t))
        self.block(s.body)

    def elem_of(self, t):
        if t.name in ("list", "set", "channel") and t.args:
            return t.args[0]
        if t.name == "text":
            return TEXT
        return ANY

    def s_ForEach(self, s):
        it = self.expr(s.iterable)
        if it.name in PRIMS[:1] + ("truth",):
            self.err(s.iterable, "`for each` needs a list, map, set, text or channel, but this is %s." % words(it),
                     "To count, write:  for each n from 1 to 10:")
        self.push()
        if s.tvars:
            el = self.elem_of(it)
            for i, n in enumerate(s.tvars):
                self.declare(n, el.args[i] if el.name == "tuple" and i < len(el.args) else ANY)
        elif it.name == "map":
            self.declare(s.var, it.args[0])
            if s.var2:
                self.declare(s.var2, it.args[1])
        else:
            self.declare(s.var, self.elem_of(it))
            if s.var2:
                self.declare(s.var2, NUM)
        self.block(s.body)
        self.pop()

    def s_ForRange(self, s):
        for e in (s.start, s.end) + ((s.step,) if s.step is not None else ()):
            t = self.expr(e)
            if t.name not in ("number", "anything"):
                self.err(e, "Counting needs whole numbers, but this is %s." % words(t), "for each n from 1 to 10:")
        self.push()
        self.declare(s.var, NUM)
        self.block(s.body)
        self.pop()

    def s_Return(self, s):
        if not self.ret_stack:
            if s.expr is not None:
                self.expr(s.expr)
            return
        d, want = self.ret_stack[-1]
        if s.expr is None:
            return
        got = self.expr(s.expr)
        if want is not None and not self.fits(want, got):
            name = getattr(d, "name", None)
            self.err(s, "%s promises to give back %s, but this gives back %s." %
                     (("`%s`" % name) if name else "This task", words(want), words(got)), self.convert_hint(want, got, "value"))

    def s_When(self, s):
        subj = self.expr(s.subject)
        for pats, body, line, guard in s.cases:
            self.push()
            for p in pats:
                self.pat(p, subj)
            if guard is not None:
                self.cond(guard, "The `if` of a case")
            for st in body:
                self.stmt(st)
            self.pop()
        if s.other is not None:
            self.block(s.other)

    def pat(self, p, t):
        pk = p.pk
        if pk == "bind":
            self.declare(p.name, t)
        elif pk == "some":
            if t.name not in ("maybe", "anything"):
                self.err(p, "`is some ...` matches a maybe value, but this is %s." % words(t))
            self.pat(p.sub, t.args[0] if t.name == "maybe" else ANY)
        elif pk == "nothing":
            if t.name not in ("maybe", "anything"):
                self.err(p, "`is nothing` matches a maybe value, but this is %s." % words(t))
        elif pk in ("ok", "problem"):
            if t.name not in ("result", "anything"):
                self.err(p, "`is %s ...` matches a result, but this is %s." % (pk, words(t)))
            if p.sub is not None:
                inner = ANY
                if t.name == "result":
                    inner = t.args[0] if pk == "ok" else (t.args[1] if len(t.args) > 1 else ANY)
                self.pat(p.sub, inner)
        elif pk == "tuple":
            if t.name not in ("tuple", "anything"):
                self.err(p, "This case matches a group like (a, b), but the value is %s." % words(t))
            if t.name == "tuple" and len(t.args) != len(p.items):
                self.err(p, "This case expects a group of %d, but the value has %d parts." % (len(p.items), len(t.args)))
            for i, x in enumerate(p.items):
                self.pat(x, t.args[i] if t.name == "tuple" else ANY)
        elif pk == "variant":
            info = self.variants.get(p.name)
            if info is None:
                return
            cname, fields = info
            if t.name not in ("anything", cname) and t.name not in self.variants and t.name not in self.abilities and not is_var(t):
                self.err(p, "`%s` is an option of `%s`, but the value here is %s." % (p.name, cname, words(t)))
            for i, x in enumerate(p.subs):
                self.pat(x, fields[i][1] if i < len(fields) and not is_var(fields[i][1]) else ANY)
        elif pk == "lit":
            vt = {bool: TRUTH, str: TEXT}.get(type(p.value), NUM)
            if t.name in PRIMS and vt.name != t.name:
                self.err(p, "This case compares %s with %s, which can never match." % (words(t), words(vt)),
                         "Convert first, e.g.  when answer as number:")
        elif pk == "range":
            if t.name not in ("number", "anything"):
                self.err(p, "A `from ... to ...` case needs a number, but the value is %s." % words(t))

    def s_Defer(self, s):
        self.block(s.body)

    def s_Parallel(self, s):
        for st in s.body:
            self.block([st])

    def s_Send(self, s):
        ch, v = self.expr(s.channel), self.expr(s.expr)
        if ch.name not in ("channel", "anything"):
            self.err(s.channel, "`send ... to` needs a channel, but this is %s." % words(ch), "let results be a new channel")

    def s_Close(self, s):
        self.expr(s.expr)

    def s_Sleep(self, s):
        t = self.expr(s.expr)
        if t.name not in ("number", "anything"):
            self.err(s.expr, "`wait` needs a number of seconds, but this is %s." % words(t))

    def s_Expect(self, s):
        self.expr(s.expr)
        if s.other is not None:
            self.expr(s.other)

    def s_Fail(self, s):
        self.expr(s.expr)

    # ------------------------------------------------------------------ expressions
    def expr(self, e):
        fn = getattr(self, "e_" + e.kind, None)
        t = fn(e) if fn is not None else ANY
        t = t if t is not None else ANY
        e.ty = t
        return t

    def e_Num(self, e):
        return NUM

    def e_Str(self, e):
        for p in e.parts:
            if not isinstance(p, str):
                self.expr(p)
        return TEXT

    def e_Bool(self, e):
        return TRUTH

    def e_NothingLit(self, e):
        return MAYBE(ANY)

    def e_Ask(self, e):
        if e.prompt is not None:
            self.expr(e.prompt)
        return TEXT

    def e_Name(self, e):
        t = self.lookup(e.name)
        if t is not None:
            return t
        if e.name in self.funcs:
            d = self.funcs[e.name]
            return Ty("task", [from_node(p.type) for p in d.params], from_node(d.ret) if d.ret is not None else None)
        if e.name in SIGS and SIGS[e.name][0] == []:
            return SIGS[e.name][1] or ANY
        return ANY

    def e_Arith(self, e):
        a, b = self.expr(e.l), self.expr(e.r)
        op = e.op
        if a.name == "anything" or b.name == "anything" or is_var(a) or is_var(b):
            if op != "+" and (a.name in ("text", "list") or b.name in ("text", "list")):
                self.err(e, "Only numbers can be used with `%s`, but this has %s." % (op, words(a if a.name in ("text", "list") else b)))
            return NUM if (a.name == "number" or b.name == "number") and op != "+" else (a if a.name != "anything" else b) if op == "+" else NUM
        if a.name == "number" and b.name == "number":
            return NUM
        if op == "+" and a.name == b.name and a.name in ("text", "list", "set"):
            return a
        if op == "-" and a.name == b.name == "set":
            return a
        if op == "+" and "text" in (a.name, b.name):
            other = b if a.name == "text" else a
            self.err(e, "Can't add text and %s." % words(other),
                     "Put the value inside the text instead:  \"Total: {total}\"\nor turn text into a number:  (x as number) or else 0")
        if a.name in ("maybe", "result") or b.name in ("maybe", "result"):
            self.err(e, "This might be missing (%s), so it can't be used in math directly." % words(a if a.name in ("maybe", "result") else b),
                     "Give a fallback first:  (value or else 0) + 1", title=MISSING_P)
        word = {"+": "added", "-": "subtracted", "*": "multiplied", "/": "divided", "mod": "used with mod", "div": "divided"}[op]
        self.err(e, "Only numbers can be %s, but this has %s and %s." % (word, words(a), words(b)),
                 "Convert text to a number first:  (x as number) or else 0")

    def e_Neg(self, e):
        t = self.expr(e.expr)
        if t.name not in ("number", "anything"):
            self.err(e, "Only numbers can be negative, but this is %s." % words(t))
        return NUM

    def e_Logic(self, e):
        self.cond(e.l, "`%s`" % e.op)
        self.cond(e.r, "`%s`" % e.op)
        return TRUTH

    def e_Not(self, e):
        self.cond(e.expr, "`not`")
        return TRUTH

    def e_Compare(self, e):
        a, b = self.expr(e.l), self.expr(e.r)
        op = e.op
        known = a.name in PRIMS and b.name in PRIMS
        if op == "is" and known and a.name != b.name:
            self.err(e, "You're comparing %s with %s - those can never be equal." % (words(a), words(b)),
                     "Convert one side first:  (x as number) or else 0   or   x as text")
        if op in (">", "<", ">=", "<="):
            for t, n in ((a, e.l), (b, e.r)):
                if t.name not in ("number", "text", "anything") and not is_var(t):
                    self.err(n, "Only numbers (or texts) can be compared by size, but this is %s." % words(t),
                             "Give a fallback first:  (value or else 0) is greater than 3" if t.name in ("maybe", "result") else None)
            if known and a.name != b.name:
                self.err(e, "Can't compare %s with %s by size." % (words(a), words(b)), "Convert text to a number first:  (x as number) or else 0")
        return TRUTH

    def e_Between(self, e):
        for x in (e.expr, e.lo, e.hi):
            self.expr(x)
        return TRUTH

    def e_Test(self, e):
        self.expr(e.expr)
        return TRUTH

    def e_TypeTest(self, e):
        self.expr(e.expr)
        return TRUTH

    def e_Wrap(self, e):
        t = self.expr(e.expr)
        if e.tag == "some":
            return MAYBE(t)
        if e.tag == "ok":
            return RES(t)
        return RES(ANY, t)

    def e_OrElse(self, e):
        a, b = self.expr(e.l), self.expr(e.r)
        if a.name in ("maybe", "result"):
            inner = a.args[0]
            if inner.name != "anything" and b.name != "anything" and not self.fits(inner, b) and not self.fits(b, inner):
                self.err(e.r, "The fallback should be %s (like the value it replaces), but it's %s." % (words(inner), words(b)))
            return self.join(inner, b)
        if a.name in ("number", "text", "truth", "list", "map", "set", "tuple") or a.name in self.records:
            self.err(e, "`or else` is for values that might be missing (a maybe or a result), but this is always %s, so the fallback would never be used." % words(a),
                     "Remove `or else ...`, or check first:  if length of xs is 0 then ... otherwise first of xs")
        return a if a.name != "anything" else b

    def e_Try(self, e):
        t = self.expr(e.expr)
        if t.name in ("maybe", "result"):
            if self.ret_stack:
                d, want = self.ret_stack[-1]
                if want is not None and want.name not in ("maybe", "result", "anything") and not is_var(want):
                    self.err(e, "`try` passes a problem up to the caller, but this task gives back %s, not a result or maybe." % words(want),
                             "Change the task to `gives result of %s`, or handle the problem here with `or else`." % show_ty(want))
                if want is not None and t.name == "maybe" and want.name == "result":
                    self.err(e, "`try` here would pass `nothing` up, but this task gives back a result (ok/problem).",
                             "Give a fallback instead:  (value or else 0)   - note `try x or else y` means `(try x) or else y`.\n"
                             "Or turn it into a problem:  when value: ... is nothing: give back problem \"...\"")
                if want is not None and t.name == "result" and want.name == "maybe":
                    self.err(e, "`try` here would pass a problem up, but this task gives back a maybe (some/nothing).",
                             "Give a fallback instead:  (value or else 0)")
            return t.args[0]
        if t.name in PRIMS or t.name in ("list", "map"):
            self.err(e, "`try` is for values that might be a problem or nothing, but this is %s." % words(t),
                     "Just use the value directly (remove `try`).")
        return ANY

    def field_type(self, objt, name, node):
        n = objt.name
        if n in BUILTIN_FIELDS:
            if name in BUILTIN_FIELDS[n]:
                return BUILTIN_FIELDS[n][name]
            self.err(node, "A `%s` has no field called `%s`." % (n, name), "Its fields are: " + ", ".join(BUILTIN_FIELDS[n]), NAME_P)
        if n in self.records:
            tparams, fields = self.records[n]
            if name in fields:
                b = dict(zip(tparams, objt.args)) if objt.args else {}
                return self.resolve(fields[name], {k: v for k, v in b.items()})
        return None

    def method_of(self, objt, name):
        n = objt.name
        if n in self.variants:
            n = self.variants[n][0]
        m = self.methods.get((n, name))
        if m is None:
            for ab in self.impls.get(n, ()):
                m = self.methods.get((ab, name))
                if m is not None:
                    break
        if m is None and n in self.abilities:
            m = self.methods.get((n, name))
        return m

    def e_Field(self, e):
        objt = self.expr(e.obj)
        ft = self.field_type(objt, e.name, e)
        if ft is not None:
            return ft
        m = self.method_of(objt, e.name)
        if m is not None:
            if m.params:
                self.err(e, "`%s` needs %d input%s." % (e.name, len(m.params), "" if len(m.params) == 1 else "s"),
                         "%s's %s with ..." % ("x", e.name), CALL_P)
            return from_node(m.ret) if m.ret is not None else ANY
        if e.name in SIGS and objt.name in PRIMS + ("list", "map", "set", "tuple"):
            params, ret = SIGS[e.name]
            if params:
                b = {}
                if not self.fits(params[0], objt, b):
                    self.err(e, "`%s` works with %s, but `%s` is %s." % (e.name, words(params[0]), self.src(e.obj), words(objt)),
                             None)
                return self.resolve(ret, b) if ret is not None else ANY
        if objt.name in PRIMS and e.name not in BUILTINS:
            self.err(e, "%s has no field or task called `%s`." % (words(objt)[0].upper() + words(objt)[1:], e.name), None, NAME_P)
        return ANY

    def src(self, e):
        if e.kind == "Name":
            return e.name
        if e.kind == "Field":
            return "%s's %s" % (self.src(e.obj), e.name)
        return "the value"

    def e_Key(self, e):
        objt = self.expr(e.obj)
        kt = self.expr(e.key)
        if objt.name == "map":
            if not self.fits(objt.args[0], kt):
                self.err(e.key, "This map uses %s as keys, so %s can't be a key." % (words(objt.args[0]), words(kt)))
            return MAYBE(objt.args[1])
        if objt.name == "list":
            self.err(e, "`at` looks things up in a map. For a list, ask for a position.", "item 2 of %s" % self.src(e.obj))
        return MAYBE(ANY) if objt.name == "anything" else ANY

    def e_Index(self, e):
        objt = self.expr(e.obj)
        it = self.expr(e.index)
        if it.name not in ("number", "anything"):
            self.err(e.index, "A position must be a whole number, but this is %s." % words(it))
        if objt.name == "list":
            return objt.args[0]
        if objt.name == "text":
            return TEXT
        if objt.name == "tuple":
            if e.index.kind == "Num" and 1 <= e.index.value <= len(objt.args):
                return objt.args[int(e.index.value) - 1]
            return ANY
        if objt.name == "map":
            self.err(e, "`item ... of` needs a list or text, but `%s` is a map." % self.src(e.obj), "For maps use:  %s at key" % self.src(e.obj))
        return ANY

    def e_Convert(self, e):
        t = self.expr(e.expr)
        n = e.type.name
        if n == "text":
            return TEXT
        if n in ("number", "integer", "decimal"):
            return RES(NUM, TEXT)
        if n == "list":
            return L(self.elem_of(t) if t.name != "map" else t.args[0])
        if n == "set":
            return Ty("set", [self.elem_of(t)])
        return ANY

    def e_ListLit(self, e):
        el = ANY
        first = None
        for it in e.items:
            t = self.expr(it)
            if first is None:
                first, el = t, t
                continue
            if t.name in PRIMS and first.name in PRIMS and t.name != first.name and not getattr(e, "mixed_ok", False):
                self.err(it, "This list holds %s, so it can't also hold %s. A list holds one kind of thing." % (words(first), words(t)),
                         "If the list is an input to a task, wrap it in parentheses:  join with (list of 1, 2, 3), \"-\"")
            el = self.join(el, t)
        return L(el)

    def e_MapLit(self, e):
        kt, vt = ANY, ANY
        for k, v in e.pairs:
            kt = self.join(kt, self.expr(k))
            vt = self.join(vt, self.expr(v))
        return M(kt, vt)

    def e_EmptyList(self, e):
        return L(ANY)

    def e_EmptyMap(self, e):
        return M(ANY, ANY)

    def e_EmptySet(self, e):
        return Ty("set", [ANY])

    def e_SetLit(self, e):
        el = ANY
        for it in e.items:
            el = self.join(el, self.expr(it))
        return Ty("set", [el])

    def e_TupleLit(self, e):
        return Ty("tuple", [self.expr(it) for it in e.items])

    def e_Copy(self, e):
        return self.expr(e.expr)

    def e_IfExpr(self, e):
        self.cond(e.cond, "The condition of an `if ... then ... otherwise` value")
        a, b = self.expr(e.yes), self.expr(e.no)
        if not (self.fits(a, b) or self.fits(b, a)):
            self.err(e, "Both answers of an `if ... then ... otherwise` should be the same type, but one is %s and the other is %s." % (words(a), words(b)),
                     "Make both answers the same type, e.g. turn a number into text with  (n as text)")
        return self.join(a, b)

    def e_Fail(self, e):
        self.expr(e.expr)
        return ANY

    def e_Range(self, e):
        for x in (e.start, e.end) + ((e.step,) if e.step is not None else ()):
            t = self.expr(x)
            if t.name not in ("number", "anything"):
                self.err(x, "A range needs whole numbers, but this is %s." % words(t))
        return L(NUM)

    def e_Take(self, e):
        t = self.expr(e.target)
        return MAYBE(t.args[0] if t.name == "list" else ANY)

    def e_NewChannel(self, e):
        return Ty("channel", [ANY])

    def e_Receive(self, e):
        t = self.expr(e.channel)
        return MAYBE(t.args[0] if t.name == "channel" else ANY)

    def e_Start(self, e):
        r = self.expr(e.call)
        return Ty("job", [r])

    def e_WaitFor(self, e):
        t = self.expr(e.job)
        if t.name == "job":
            return t.args[0]
        if t.name == "list" and t.args[0].name == "job":
            return L(t.args[0].args[0])
        return ANY

    def e_Construct(self, e):
        if e.tname in self.records:
            tparams, fields = self.records[e.tname]
            b = {}
            for fn, fe in e.fields:
                got = self.expr(fe)
                want = fields.get(fn, ANY)
                if not self.fits(want, got, b):
                    self.mismatch(fe, "The field `%s` of %s %s" % (fn, "an" if e.tname[:1] in "AEIOU" else "a", e.tname), self.resolve(want, b), got)
            return Ty(e.tname, [b.get(p, ANY) for p in tparams])
        if e.tname in self.variants:
            cname, fields = self.variants[e.tname]
            fd = dict(fields)
            b = {}
            for fn, fe in e.fields:
                got = self.expr(fe)
                want = fd.get(fn, ANY)
                if not self.fits(want, got, b):
                    self.mismatch(fe, "The field `%s` of %s" % (fn, e.tname), self.resolve(want, b), got)
            return Ty(cname, [b.get(p, ANY) for p in self.choices.get(cname, [])])
        for fn, fe in e.fields:
            self.expr(fe)
        return ANY

    def check_call(self, e, name, params, ret, arg_nodes, arg_types):
        b = {}
        for i, (p, got, an) in enumerate(zip(params, arg_types, arg_nodes)):
            want = from_node(p.type) if hasattr(p, "type") else p
            if not self.fits(want, got, b):
                pname = getattr(p, "name", None)
                what = ("The input `%s` of `%s`" % (pname, name)) if pname else ("Input %d of `%s`" % (i + 1, name))
                self.err(an, "%s should be %s, but here it's %s." % (what, words(self.resolve(want, b)), words(got)),
                         self.convert_hint(want, got, pname or "value"))
        if ret is None:
            return ANY
        r = from_node(ret) if not isinstance(ret, Ty) else ret
        return self.resolve(r, b)

    def e_Call(self, e):
        arg_types = [self.expr(a.expr) for a in e.args]
        nodes = [a.expr for a in e.args]
        local = self.lookup(e.name)
        if local is not None:
            if local.name == "task" and local.ret is not None:
                return local.ret
            return ANY
        if e.name in self.funcs:
            d = self.funcs[e.name]
            return self.check_call(e, e.name, d.params, d.ret, nodes, arg_types)
        if e.name in self.records or e.name in self.variants:
            return self.named_type(e.name)
        if e.name in SIGS:
            params, ret = SIGS[e.name]
            if e.name == "join_path" and len(nodes) >= 2:
                params = [TEXT] * len(nodes)
            ret_t = self.check_call(e, e.name, params, ret, nodes, arg_types)
            if e.name in ("largest", "smallest", "first", "last", "reversed", "sorted", "slice") and ret_t.name == "anything":
                return ANY
            return ret_t if ret is not None else ANY
        return ANY

    def e_RunCall(self, e):
        local = self.lookup(e.name)
        if local is not None:
            return local.ret if local.name == "task" and local.ret is not None else ANY
        if e.name in self.funcs:
            d = self.funcs[e.name]
            return from_node(d.ret) if d.ret is not None else ANY
        if e.name in SIGS:
            return SIGS[e.name][1] or ANY
        return ANY

    def e_MethodCall(self, e):
        objt = self.expr(e.obj)
        arg_types = [self.expr(a.expr) for a in e.args]
        m = self.method_of(objt, e.name)
        if m is not None:
            if len(m.params) != len(e.args):
                return ANY
            return self.check_call(e, e.name, m.params, m.ret, [a.expr for a in e.args], arg_types)
        if e.name in SIGS and objt.name != "anything" and objt.name not in self.records and objt.name not in self.choices:
            params, ret = SIGS[e.name]
            if len(params) >= 1 + len(arg_types):
                return self.check_call(e, e.name, params, ret, [e.obj] + [a.expr for a in e.args], [objt] + arg_types)
        return ANY

    def e_Lambda(self, e):
        self.push()
        for p in e.params:
            self.declare(p.name, ANY)
        if e.expr is not None:
            r = self.expr(e.expr)
        else:
            self.ret_stack.append((e, None))
            self.block(e.body)
            self.ret_stack.pop()
            r = None
        self.pop()
        return Ty("task", [ANY] * len(e.params), r)

    def e_HOF(self, e):
        src = self.expr(e.src)
        el = src.args[0] if src.name == "map" else self.elem_of(src)
        init_t = self.expr(e.init) if e.init is not None else None
        self.push()
        self.declare(e.var, el)
        if e.acc:
            self.declare(e.acc, init_t or ANY)
        f = e.form
        if f in ("keep", "count", "find", "any", "every"):
            self.cond(e.body, "The `where` condition")
            body = TRUTH
        else:
            body = self.expr(e.body)
        self.pop()
        if f == "keep":
            return src if src.name in ("list", "set") else L(el)
        if f == "turn":
            return L(body)
        if f == "count":
            return NUM
        if f == "find":
            return MAYBE(el)
        if f in ("any", "every"):
            return TRUTH
        if f == "sort":
            if body.name not in ("number", "text", "tuple", "anything", "truth") and not is_var(body):
                self.err(e.body, "Things can only be sorted by numbers or text, but this key is %s." % words(body),
                         "Sort by a field instead, e.g.  sort each p in people by p's age")
            return L(el)
        if f == "combine":
            if init_t is not None and body.name != "anything" and init_t.name != "anything" and not self.fits(init_t, body):
                self.err(e.body, "Each step should give %s (like the starting value), but this gives %s." % (words(init_t), words(body)))
            return self.join(init_t or ANY, body)
        return ANY


def typecheck(module, loader):
    TypeChecker(module, loader).check()
