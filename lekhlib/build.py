"""`lekh build`: translate a checked Lekh program into a Python program (a transpiler).

Why a transpiler and not a bytecode VM?  See DESIGN.md, "Performance path".  In short: the
generated Python runs on CPython's own (already optimised) bytecode VM, so every Lekh
statement becomes a handful of Python operations instead of a walk over AST nodes with
scope objects.  All the static checks run first, so the output keeps Lekh's safety while
dropping the ownership bookkeeping the checker already proved.

The output imports `lekhlib.rt` for Lekh values, the standard library and friendly errors.
"""
import os

from .core import Node, FRESH, iter_names, LekhError, SYNTAX, SOURCES, VERSION
from .typecheck import Ty

PY_KEYWORDS = {"False", "None", "True", "and", "as", "assert", "async", "await", "break", "class", "continue", "def", "del",
               "elif", "else", "except", "finally", "for", "from", "global", "if", "import", "in", "is", "lambda", "nonlocal",
               "not", "or", "pass", "raise", "return", "try", "while", "with", "yield"}


def contains_kind(x, kinds, stop=("FuncDef", "Lambda")):
    if isinstance(x, Node):
        if x.kind in kinds:
            return True
        if x.kind in stop:
            return False
        return any(contains_kind(v, kinds, stop) for k, v in x.__dict__.items() if k not in ("kind", "line", "file", "ty"))
    if isinstance(x, (list, tuple)):
        return any(contains_kind(v, kinds, stop) for v in x)
    return False


class Unsupported(Exception):
    pass


class ModuleCompiler:
    def __init__(self, prog, mod, idx):
        self.prog, self.mod, self.idx = prog, mod, idx
        self.pre = "m%d_" % idx
        self.out = []
        self.ind = 0
        self.scopes = []
        self.globals = {}       # lekh name -> py name for this module's top level (vars, tasks, types)
        self.counter = 0
        self.fn_stack = []      # (FuncDef-like node, changeable param py names)
        self.in_top = False

    # ------------------------------------------------------------------ helpers
    def emit(self, line):
        self.out.append("    " * self.ind + line)

    def tmp(self, base="t"):
        self.counter += 1
        return "_%s%d" % (base, self.counter)

    def loc(self, node, name=None):
        return self.prog.loc(node.line, node.file, name)

    def declare(self, name):
        self.counter += 1
        py = "v_%s_%d" % (name, self.counter)
        self.scopes[-1][name] = py
        return py

    def lookup(self, name):
        for sc in reversed(self.scopes):
            if name in sc:
                return sc[name]
        return self.globals.get(name)

    def push(self):
        self.scopes.append({})

    def pop(self):
        self.scopes.pop()

    def ty(self, e):
        return getattr(e, "ty", None)

    def is_num(self, e):
        t = self.ty(e)
        return t is not None and t.name == "number"

    def type_expr(self, t):
        if t is None:
            return "None"
        args = ", ".join(self.type_expr(a) for a in t.args)
        ret = self.type_expr(t.ret) if getattr(t, "ret", None) is not None else "None"
        return "TY(%r, [%s], %s, %r)" % (t.name, args, ret, bool(getattr(t, "var", False)))

    def const_type(self, t):
        return self.prog.const(self.type_expr(t))

    # ------------------------------------------------------------------ top level
    def compile(self):
        ast = self.mod.ast
        self.push()                       # module scope (globals)
        self.scopes[-1] = self.globals
        self.globals["Response"] = "stdlib.RESPONSE"
        self.globals["CommandOutput"] = "stdlib.COMMAND_OUTPUT"
        for s in ast:
            if s.kind == "Use":
                src = self.prog.compilers[s.path]
                for n, py in src.exports.items():
                    if s.names is None or n in s.names or self.prog.is_variant_of(n, s.names, s.path):
                        self.globals[n] = py
        # types first
        for s in ast:
            if s.kind == "RecordDef":
                py = self.pre + "R_" + s.name
                self.globals[s.name] = py
                fields = ", ".join("(%r, %s)" % (f, self.type_expr(t) if t is not None else "None") for f, t in s.fields)
                self.prog.head.append("%s = RecordType(%r, [%s])" % (py, s.name, fields))
            elif s.kind == "ChoiceDef":
                py = self.pre + "C_" + s.name
                self.globals[s.name] = py
                self.prog.head.append("%s = ChoiceType(%r)" % (py, s.name))
                for vn, fields, _ in s.variants:
                    vpy = self.pre + "V_" + vn
                    self.globals[vn] = vpy
                    fl = ", ".join("(%r, %s)" % (f, self.type_expr(t) if t is not None else "None") for f, t in fields)
                    self.prog.head.append("%s = VariantType(%s, %r, [%s]); %s.variants[%r] = %s" % (vpy, py, vn, fl, py, vn, vpy))
            elif s.kind == "AbilityDef":
                py = self.pre + "A_" + s.name
                self.globals[s.name] = py
                self.prog.head.append("%s = AbilityType(%r, None)" % (py, s.name))
        for s in ast:
            if s.kind == "FuncDef" and not s.owner:
                self.globals[s.name] = self.pre + "T_" + s.name
        top_names = set()
        for s in ast:
            if s.kind in ("Let", "LetTuple"):
                for n in ([s.name] if s.kind == "Let" else s.names):
                    self.globals[n] = self.pre + "g_" + n
                    top_names.add(self.pre + "g_" + n)
        self.exports = {}
        for s in ast:
            if getattr(s, "shared", False) and s.kind in ("FuncDef", "RecordDef", "ChoiceDef", "AbilityDef", "Let"):
                self.exports[s.name] = self.globals[s.name]
                if s.kind == "ChoiceDef":
                    for vn, _, _ in s.variants:
                        self.exports[vn] = self.globals[vn]
        # tasks and methods
        for s in ast:
            if s.kind == "FuncDef":
                self.func(s)
            elif s.kind == "AbilityDef":
                for m in s.methods:
                    if m.body is not None:
                        self.func(m, owner_override=s.name)
        for s in ast:
            if s.kind == "Can":
                t, a = self.globals[s.tname], self.globals[s.ability]
                self.emit("for _k, _v in %s.methods.items():" % a)
                self.emit("    %s.methods.setdefault(_k, _v)" % t)
                self.emit("ABILITY_IMPLS.setdefault(%r, set()).add(%r)" % (s.tname, s.ability))
        # top-level statements
        self.emit("def %stop():" % self.pre)
        self.ind += 1
        if top_names:
            self.emit("global " + ", ".join(sorted(top_names)))
        self.in_top = True
        body = [s for s in ast if s.kind not in ("FuncDef", "RecordDef", "ChoiceDef", "AbilityDef", "Can", "Use", "TestBlock")]
        self.push()
        self.block_body(body, top=True)
        self.pop()
        self.emit("pass")
        self.ind -= 1
        self.in_top = False

    # ------------------------------------------------------------------ tasks
    def func(self, d, owner_override=None):
        owner = owner_override or d.owner
        if owner:
            fname = self.pre + "M_%s_%s" % (owner, d.name)
        else:
            fname = self.pre + "F_" + d.name
        self.push()
        params = []
        if owner:
            params.append(self.declare("me"))
        changeable = []
        for p in d.params:
            py = self.declare(p.name)
            params.append(py)
            if p.changeable:
                changeable.append(py)
        self.emit("def %s(%s):" % (fname, ", ".join(params)))
        self.ind += 1
        loc = self.loc(d, d.name)
        for p, py in zip(d.params, params[1:] if owner else params):
            if p.type is not None and p.type.name != "anything" and not getattr(p.type, "var", False):
                self.emit("chk(%s, %s, %s, %r)" % (py, self.const_type(p.type), loc, "The input `%s` of `%s`" % (p.name, d.name)))
        self.fn_stack.append((d, changeable, d.ret))
        has_try = contains_kind(d.body, ("Try",))
        if has_try:
            self.emit("try:")
            self.ind += 1
        self.block_body(d.body)
        self.emit_return(None, fall=True)
        if has_try:
            self.ind -= 1
            self.emit("except TryReturn as _tr:")
            self.emit("    return %s" % self.ret_tuple("_tr.value"))
        self.fn_stack.pop()
        self.ind -= 1
        self.pop()
        nparams = len(params)
        if owner:
            self.emit("%s.methods[%r] = PyTask(%s, %r, %d)" % (self.globals[owner], d.name, fname, d.name, nparams))
        else:
            self.emit("%s = PyTask(%s, %r, %d)" % (self.globals[d.name], fname, d.name, nparams))
            self.prog.direct[(self.mod.path, d.name)] = (fname, changeable and [i for i, p in enumerate(d.params) if p.changeable])

    def ret_tuple(self, val):
        d, changeable, ret = self.fn_stack[-1]
        if changeable:
            return "(%s, %s)" % (val, ", ".join(changeable))
        return val

    def emit_return(self, expr_code, fall=False, node=None):
        d, changeable, ret = self.fn_stack[-1]
        if fall:
            if ret is not None:
                self.emit("ret_check(None, %s, %s, %r)" % (self.const_type(ret), self.loc(d), getattr(d, "name", "task")))
            self.emit("return " + self.ret_tuple("None"))
            return
        val = expr_code
        if ret is not None and ret.name != "anything" and not getattr(ret, "var", False):
            val = "ret_check(%s, %s, %s, %r)" % (val, self.const_type(ret), self.loc(node), getattr(d, "name", "task"))
        self.emit("return " + self.ret_tuple(val))

    # ------------------------------------------------------------------ statements
    def block(self, stmts):
        self.push()
        n0 = len(self.out)
        self.block_body(stmts)
        if len(self.out) == n0:
            self.emit("pass")
        self.pop()

    def block_body(self, stmts, top=False):
        for i, s in enumerate(stmts):
            if s.kind == "Defer":
                self.emit("try:")
                self.ind += 1
                self.block(stmts[i + 1:] or [])
                self.ind -= 1
                self.emit("finally:")
                self.ind += 1
                self.block(s.body)
                self.ind -= 1
                return
            self.stmt(s, top)

    def stmt(self, s, top=False):
        fn = getattr(self, "s_" + s.kind, None)
        if fn is None:
            raise LekhError(SYNTAX, "`lekh build` doesn't support `%s` yet - use `lekh run` for this program." % s.kind, s.line, None, s.file)
        fn(s)

    def bind(self, name):
        """Python name for a new Lekh variable (top-level lets are module globals)."""
        if self.in_top and len(self.scopes) == 2 and name in self.globals and self.globals[name].startswith(self.pre + "g_"):
            return self.globals[name]
        return self.declare(name)

    def s_Let(self, s):
        if s.type is not None and s.type.name == "list" and s.expr.kind == "ListLit":
            val = self.list_lit(s.expr, self.const_type(s.type.args[0]))
        elif s.type is not None and s.type.name == "map" and s.expr.kind == "MapLit":
            val = self.map_lit(s.expr, self.const_type(s.type.args[1]))
        else:
            val = self.take(s.expr)
        py = self.bind(s.name)
        self.emit("%s = %s" % (py, val))
        if s.type is not None and s.type.name not in ("anything",) and not getattr(s.type, "var", False):
            self.emit("chk(%s, %s, %s, %r)" % (py, self.const_type(s.type), self.loc(s), "`%s`" % s.name))
            if s.type.name == "list":
                self.emit("%s.elem_type = %s" % (py, self.const_type(s.type.args[0])))
            if s.type.name == "map":
                self.emit("%s.val_type = %s" % (py, self.const_type(s.type.args[1])))

    def s_LetTuple(self, s):
        t = self.tmp()
        self.emit("%s = %s" % (t, self.take(s.expr)))
        self.emit("%s = split_group(%s, %d, %s)" % (t, t, len(s.names), self.loc(s)))
        for i, n in enumerate(s.names):
            self.emit("%s = %s[%d]" % (self.bind(n), t, i))

    def target_read(self, tg):
        return self.expr(tg)

    def assign(self, tg, val_code, node):
        loc = self.loc(node)
        if tg.kind == "Name":
            self.emit("%s = %s" % (self.lookup(tg.name), val_code))
        elif tg.kind == "Field":
            self.emit("set_field(%s, %r, %s, %s)" % (self.expr(tg.obj), tg.name, val_code, loc))
        elif tg.kind == "Index":
            self.emit("set_index(%s, %s, %s, %s)" % (self.expr(tg.obj), self.expr(tg.index), val_code, loc))
        elif tg.kind == "Key":
            self.emit("set_key(%s, %s, %s, %s)" % (self.expr(tg.obj), self.expr(tg.key), val_code, loc))

    def s_Change(self, s):
        if s.target.kind == "Name" and s.target.name == "me":
            # `change me to ...` in a `changes me` method: update the caller's value in place
            self.emit("replace_me(%s, %s)" % (self.lookup("me"), self.take(s.expr)))
            return
        self.assign(s.target, self.take(s.expr), s)

    def s_Increase(self, s):
        cur = self.target_read(s.target if s.target.kind != "Key" else s.target)
        if s.target.kind == "Key":
            cur = "or_else(%s, lambda: 0)" % cur
        if self.is_num(s.target) and self.is_num(s.expr) and s.target.kind == "Name":
            self.emit("%s %s= %s" % (self.lookup(s.target.name), "+" if s.sign > 0 else "-", self.expr(s.expr)))
            return
        self.assign(s.target, "incr(%s, %s, %d, %s)" % (cur, self.expr(s.expr), s.sign, self.loc(s)), s)

    def tname(self, tg):
        from .core import target_desc
        return target_desc(tg)

    def s_Add(self, s):
        val = self.take(s.expr)
        res = "add_to(%s, %s, %s, %r)" % (self.target_read(s.target), val, self.loc(s), self.tname(s.target))
        t = self.ty(s.target)
        if t is not None and t.name in ("list", "set"):
            self.emit(res)
        else:
            self.assign(s.target, res, s)

    def s_Remove(self, s):
        self.emit("remove_from(%s, %s, %r, %s, %r)" % (self.target_read(s.target), self.expr(s.expr), bool(s.by_pos), self.loc(s), self.tname(s.target)))

    def s_Say(self, s):
        if s.expr is None:
            self.emit("say('', None)")
        else:
            self.emit("say(%s, %s)" % (self.expr(s.expr), self.loc(s.expr)))

    def s_ExprStmt(self, s):
        self.emit(self.expr(s.expr, want=False))

    def s_Fail(self, s):
        self.emit("fail(%s, %s)" % (self.expr(s.expr), self.loc(s)))

    def cond(self, e, what="`if`"):
        if self.ty(e) is not None and self.ty(e).name == "truth":
            return self.expr(e)
        return "T(%s, %s, %r)" % (self.expr(e), self.loc(e), what)

    def s_If(self, s):
        for i, (c, body) in enumerate(s.branches):
            self.emit(("if %s:" if i == 0 else "elif %s:") % self.cond(c))
            self.ind += 1
            self.block(body)
            self.ind -= 1
        if s.other is not None:
            self.emit("else:")
            self.ind += 1
            self.block(s.other)
            self.ind -= 1

    def s_While(self, s):
        self.emit("while %s:" % self.cond(s.cond, "`while`"))
        self.ind += 1
        self.block(s.body)
        self.ind -= 1

    def s_Repeat(self, s):
        self.emit("for _ in repeat_count(%s, %s):" % (self.expr(s.count), self.loc(s)))
        self.ind += 1
        self.block(s.body)
        self.ind -= 1

    def s_Stop(self, s):
        self.emit("break")

    def s_Skip(self, s):
        self.emit("continue")

    def s_Return(self, s):
        if not self.fn_stack:
            raise LekhError(SYNTAX, "`give back` outside a task.", s.line, None, s.file)
        if s.expr is None:
            self.emit("return " + self.ret_tuple("None"))
            return
        e = s.expr
        code = self.expr(e) if (e.kind == "Name" or e.kind in FRESH) else "cp(%s)" % self.expr(e)
        self.emit_return(code, node=s)

    def loop_vars(self, s, item_code, it_ty):
        """Assign loop variables from the current item."""
        pass

    def s_ForEach(self, s):
        it = self.tmp("it")
        self.emit("%s = %s" % (it, self.expr(s.iterable)))
        loc = self.loc(s.iterable)
        self.push()
        if s.parallel:
            body_fn = self.tmp("job")
            names = s.tvars or [s.var] + ([s.var2] if s.var2 else [])
            pys = [self.declare(n) for n in names]
            self.emit("def %s(_x, _pos):" % body_fn)
            self.ind += 1
            self.unpack_loop(s, pys, "_x", "_pos", it)
            self.emit("try:")
            self.ind += 1
            self.block(s.body)
            self.ind -= 1
            self.emit("except StopLoop:")
            self.emit("    pass")
            self.ind -= 1
            self.emit("parallel([(lambda _x=_x, _p=_p: %s(_x, _p)) for _p, _x in enumerate(items(%s, %s), 1)], %s)" % (body_fn, it, loc, self.loc(s)))
            self.pop()
            return
        names = s.tvars or [s.var] + ([s.var2] if s.var2 else [])
        pys = [self.declare(n) for n in names]
        if s.changeable:
            pos = self.tmp("i")
            self.emit("for %s in range(len(%s.items) if isinstance(%s, PList) else 0):" % (pos, it, it))
            self.ind += 1
            self.emit("%s = %s.items[%s]" % (pys[0], it, pos))
            if s.var2:
                self.emit("%s = %s + 1" % (pys[1], pos))
            self.emit("try:")
            self.ind += 1
            self.block(s.body)
            self.ind -= 1
            self.emit("finally:")
            self.emit("    %s.items[%s] = %s" % (it, pos, pys[0]))
            self.ind -= 1
            self.pop()
            return
        x, p = self.tmp("x"), self.tmp("p")
        self.emit("%s.looping = getattr(%s, 'looping', 0) + 1 if hasattr(%s, 'looping') else 0" % (it, it, it))
        self.emit("try:")
        self.ind += 1
        self.emit("for %s, %s in enumerate(channel_items(%s, %s) if isinstance(%s, Channel) else items(%s, %s), 1):" % (p, x, it, loc, it, it, loc))
        self.ind += 1
        self.unpack_loop(s, pys, x, p, it)
        self.block(s.body)
        self.ind -= 1
        self.ind -= 1
        self.emit("finally:")
        self.emit("    if hasattr(%s, 'looping'): %s.looping -= 1" % (it, it))
        self.pop()

    def unpack_loop(self, s, pys, x, p, it):
        if s.tvars:
            self.emit("%s = split_group(%s, %d, %s)" % ("_g", x, len(s.tvars), self.loc(s)))
            for i, py in enumerate(pys):
                self.emit("%s = _g[%d]" % (py, i))
        else:
            self.emit("%s = %s" % (pys[0], x))
            if s.var2:
                self.emit("%s = %s.d[%s] if isinstance(%s, PMap) else %s" % (pys[1], it, x, it, p))

    def s_ForRange(self, s):
        rng = "count_range(%s, %s, %s, %s)" % (self.expr(s.start), self.expr(s.end), self.expr(s.step) if s.step is not None else "None", self.loc(s))
        self.push()
        py = self.declare(s.var)
        if s.parallel:
            fn = self.tmp("job")
            self.emit("def %s(%s):" % (fn, py))
            self.ind += 1
            self.emit("try:")
            self.ind += 1
            self.block(s.body)
            self.ind -= 1
            self.emit("except StopLoop:")
            self.emit("    pass")
            self.ind -= 1
            self.emit("parallel([(lambda _i=_i: %s(_i)) for _i in %s], %s)" % (fn, rng, self.loc(s)))
        else:
            self.emit("for %s in %s:" % (py, rng))
            self.ind += 1
            self.block(s.body)
            self.ind -= 1
        self.pop()

    def s_When(self, s):
        subj = self.tmp("s")
        done = self.tmp("done")
        self.emit("%s = %s" % (subj, self.expr(s.subject)))
        self.emit("%s = False" % done)
        loc = self.loc(s)
        for pats, body, line, guard in s.cases:
            for p in pats:
                b = self.tmp("b")
                pc = self.prog.const(self.pat_expr(p))
                self.emit("if not %s:" % done)
                self.ind += 1
                self.emit("%s = {}" % b)
                self.emit("if when_match(%s, %s, %s, %s):" % (pc, subj, loc, b))
                self.ind += 1
                self.push()
                for n in self.pat_names(p):
                    self.emit("%s = %s[%r]" % (self.declare(n), b, n))
                if guard is not None:
                    self.emit("if %s:" % self.cond(guard, "The `if` of a case"))
                    self.ind += 1
                self.emit("%s = True" % done)
                self.block(body)
                if guard is not None:
                    self.ind -= 1
                self.pop()
                self.ind -= 2
        self.emit("if not %s:" % done)
        self.ind += 1
        if s.other is not None:
            self.block(s.other)
        else:
            self.emit("no_case(%s, %s)" % (subj, loc))
        self.ind -= 1

    def pat_names(self, p):
        if p.pk == "bind":
            return [p.name]
        out = []
        for x in ([p.sub] if getattr(p, "sub", None) is not None else []) + list(getattr(p, "items", None) or []) + list(getattr(p, "subs", None) or []):
            out += self.pat_names(x)
        return out

    def pat_expr(self, p):
        kw = []
        for k in ("name", "value", "lo", "hi"):
            v = getattr(p, k, None)
            if v is not None:
                kw.append("%s=%r" % (k, v))
        if getattr(p, "sub", None) is not None:
            kw.append("sub=%s" % self.pat_expr(p.sub))
        if getattr(p, "items", None):
            kw.append("items=[%s]" % ", ".join(self.pat_expr(x) for x in p.items))
        if getattr(p, "subs", None):
            kw.append("subs=[%s]" % ", ".join(self.pat_expr(x) for x in p.subs))
        return "PAT(%r, %d, %r%s)" % (p.pk, p.line, p.file, "".join(", " + k for k in kw))

    def s_Parallel(self, s):
        fns = []
        for st in s.body:
            fn = self.tmp("job")
            self.emit("def %s():" % fn)
            self.ind += 1
            self.block([st])
            self.ind -= 1
            fns.append(fn)
        self.emit("parallel([%s], %s)" % (", ".join(fns), self.loc(s)))

    def s_Send(self, s):
        self.emit("send(%s, %s, %s)" % (self.expr(s.channel), self.take(s.expr), self.loc(s)))

    def s_Close(self, s):
        self.emit("close(%s, %s)" % (self.expr(s.expr), self.loc(s)))

    def s_Sleep(self, s):
        self.emit("sleep(%s, %s)" % (self.expr(s.expr), self.loc(s)))

    def s_Expect(self, s):
        src = "the value"
        try:
            import re
            m = re.match(r"expect (.*?) (not )?to (be|contain)\b", SOURCES[s.file][s.line - 1].strip())
            src = m.group(1) if m else src
        except (KeyError, IndexError):
            pass
        self.emit("expect(%s, %r, %s, %r, %s, %r)" % (self.expr(s.expr), s.how.replace("test:", ""),
                                                   self.expr(s.other) if s.other is not None else "None", bool(s.neg), self.loc(s), src))

    # ------------------------------------------------------------------ expressions
    def take(self, e):
        code = self.expr(e)
        if e.kind == "Name" or e.kind in FRESH or e.kind in ("Lambda", "HOF", "TupleLit", "SetLit", "EmptySet", "Range",
                                                            "NewChannel", "Start", "MethodCall", "Take", "Receive", "WaitFor",
                                                            "OrElse", "Try"):
            return code
        t = self.ty(e)
        if t is not None and t.name in ("number", "text", "truth"):
            return code
        return "cp(%s)" % code

    def expr(self, e, want=True):
        fn = getattr(self, "e_" + e.kind, None)
        if fn is None:
            raise LekhError(SYNTAX, "`lekh build` doesn't support `%s` yet - use `lekh run` for this program." % e.kind, e.line, None, e.file)
        if e.kind in ("Call", "RunCall", "MethodCall", "WaitFor"):
            return fn(e, want)
        return fn(e)

    def e_Num(self, e):
        return repr(e.value)

    def e_Bool(self, e):
        return "True" if e.value else "False"

    def e_NothingLit(self, e):
        return "NOTHING"

    def e_Str(self, e):
        parts = []
        for p in e.parts:
            if isinstance(p, str):
                parts.append(repr(p))
            else:
                t = self.ty(p)
                if t is not None and t.name == "text":
                    parts.append(self.expr(p))
                else:
                    parts.append("text(%s, %s)" % (self.expr(p), self.loc(p)))
        if not parts:
            return "''"
        if len(parts) == 1 and isinstance(e.parts[0], str):
            return parts[0]
        return "''.join((%s,))" % ", ".join(parts)

    def e_Name(self, e):
        py = self.lookup(e.name)
        if py is None:
            from .core import BUILTINS
            if e.name in BUILTINS:
                fn, lo, hi = BUILTINS[e.name]
                if hi == 0:
                    return "B[%r](R, %s, [])" % (e.name, self.loc(e, e.name))
                return "BV(%r)" % e.name
            raise LekhError(SYNTAX, "Build: unknown name `%s`." % e.name, e.line, None, e.file)
        return py

    def e_Wrap(self, e):
        return "%s(%s)" % ({"some": "Some", "ok": "Ok", "problem": "Problem"}[e.tag], self.take(e.expr))

    def e_Arith(self, e):
        a, b = self.expr(e.l), self.expr(e.r)
        fast = self.is_num(e.l) and self.is_num(e.r)
        op = e.op
        if fast and op in ("+", "-", "*"):
            return "(%s %s %s)" % (a, op, b)
        name = {"+": "add", "-": "sub", "*": "mul", "/": "div", "mod": "mod", "div": "idiv"}[op]
        return "%s(%s, %s, %s)" % (name, a, b, self.loc(e))

    def e_Neg(self, e):
        if self.is_num(e.expr):
            return "(-%s)" % self.expr(e.expr)
        return "neg(%s, %s)" % (self.expr(e.expr), self.loc(e))

    def e_Logic(self, e):
        return "(%s %s %s)" % (self.cond(e.l, "`%s`" % e.op), e.op, self.cond(e.r, "`%s`" % e.op))

    def e_Not(self, e):
        return "(not %s)" % self.cond(e.expr, "`not`")

    def e_Compare(self, e):
        a, b = self.expr(e.l), self.expr(e.r)
        op = e.op
        tl, tr = self.ty(e.l), self.ty(e.r)
        prim = tl is not None and tr is not None and tl.name == tr.name and tl.name in ("number", "text")
        if op == "is":
            r = "(%s == %s)" % (a, b) if prim else "eq(%s, %s, %s)" % (a, b, self.loc(e))
        elif op in (">", "<", ">=", "<="):
            r = "(%s %s %s)" % (a, op, b) if prim else "order(%s, %s, %r, %s)" % (a, b, op, self.loc(e))
        elif op == "contains":
            r = "contains(%s, %s, %s)" % (a, b, self.loc(e))
        else:
            r = "starts(%s, %s, %r, %s)" % (a, b, op, self.loc(e))
        return "(not %s)" % r if getattr(e, "neg", False) else r

    def e_Between(self, e):
        r = "between(%s, %s, %s, %s)" % (self.expr(e.expr), self.expr(e.lo), self.expr(e.hi), self.loc(e))
        return "(not %s)" % r if e.neg else r

    def e_Test(self, e):
        r = "test_wrap(%s, %r, %s)" % (self.expr(e.expr), e.what, self.loc(e))
        return "(not %s)" % r if e.neg else r

    def e_TypeTest(self, e):
        r = "type_test(%s, %r)" % (self.expr(e.expr), e.tname)
        return "(not %s)" % r if e.neg else r

    def e_OrElse(self, e):
        return "or_else(%s, lambda: %s)" % (self.expr(e.l), self.expr(e.r))

    def e_Try(self, e):
        return "try_(%s, %s)" % (self.expr(e.expr), self.loc(e))

    def e_Field(self, e):
        obj = self.expr(e.obj)
        t = self.ty(e.obj)
        if t is not None and t.name in self.prog.record_fields and e.name in self.prog.record_fields[t.name]:
            return "%s.fields[%r]" % (obj, e.name)
        return "field(%s, %r, %s)" % (obj, e.name, self.loc(e, e.name))

    def e_Key(self, e):
        return "key(%s, %s, %s, %r)" % (self.expr(e.obj), self.expr(e.key), self.loc(e), self.tname(e.obj) if e.obj.kind in ("Name", "Field") else "the map")

    def e_Index(self, e):
        return "index(%s, %s, %s, %r)" % (self.expr(e.obj), self.expr(e.index), self.loc(e), self.tname(e.obj) if e.obj.kind in ("Name", "Field") else "the list")

    def e_Convert(self, e):
        return "convert(%s, %r, %s)" % (self.expr(e.expr), e.type.name, self.loc(e))

    def list_lit(self, e, elem_type="None"):
        return "mklist([%s], %s, %s)" % (", ".join(self.take(x) for x in e.items), self.loc(e), elem_type)

    def map_lit(self, e, val_type="None"):
        return "mkmap([%s], %s, %s)" % (", ".join("(%s, %s)" % (self.expr(k), self.take(v)) for k, v in e.pairs), self.loc(e), val_type)

    def e_ListLit(self, e):
        return self.list_lit(e)

    def e_MapLit(self, e):
        return self.map_lit(e)

    def e_EmptyList(self, e):
        return "PList()"

    def e_EmptyMap(self, e):
        return "PMap()"

    def e_EmptySet(self, e):
        return "PSet()"

    def e_SetLit(self, e):
        return "mkset([%s], %s)" % (", ".join(self.expr(x) for x in e.items), self.loc(e))

    def e_TupleLit(self, e):
        return "Tuple((%s,))" % ", ".join(self.take(x) for x in e.items)

    def e_Copy(self, e):
        return "deep_copy(%s)" % self.expr(e.expr)

    def e_IfExpr(self, e):
        def side(x):
            c = self.expr(x)
            return "deep_copy(%s)" % c if x.kind in ("Name", "Field", "Key", "Index") else c
        return "(%s if %s else %s)" % (side(e.yes), self.cond(e.cond, "`if ... then`"), side(e.no))

    def e_Ask(self, e):
        return "ask(%s, %s)" % (self.expr(e.prompt) if e.prompt is not None else "None", self.loc(e))

    def e_Fail(self, e):
        return "fail(%s, %s)" % (self.expr(e.expr), self.loc(e))

    def e_Range(self, e):
        return "range_list(%s, %s, %s, %s)" % (self.expr(e.start), self.expr(e.end), self.expr(e.step) if e.step is not None else "None", self.loc(e))

    def e_Take(self, e):
        return "take_from(%s, %r, %s, %r)" % (self.expr(e.target), e.which, self.loc(e), self.tname(e.target))

    def e_NewChannel(self, e):
        return "Channel()"

    def e_Receive(self, e):
        return "recv(%s, %s)" % (self.expr(e.channel), self.loc(e))

    def e_WaitFor(self, e, want=True):
        return "wait_for(%s, %s, %r)" % (self.expr(e.job), self.loc(e), want)

    def e_Start(self, e):
        c = e.call
        fn = self.task_value(c.name, c)
        args = [self.take(a.expr) if a.mode == "give" else self.expr(a.expr) for a in (c.args if c.kind == "Call" else [])]
        return "start(%s, [%s], %s)" % (fn, ", ".join(args), self.loc(e))

    def task_value(self, name, node):
        py = self.lookup(name)
        if py is not None:
            return py
        return "BV(%r)" % name

    def e_Construct(self, e):
        t = self.lookup(e.tname)
        if not e.fields:
            vt = self.prog.variant_types.get(e.tname)
            if vt:
                return "Variant(%s, {})" % t
        fields = ", ".join("%r: %s" % (fn, self.take(fe)) for fn, fe in e.fields)
        return "construct(%s, {%s}, %s)" % (t, fields, self.loc(e))

    def call_args(self, args):
        return [self.take(a.expr) if a.mode == "give" else self.expr(a.expr) for a in args]

    def e_Call(self, e, want=True):
        loc = self.loc(e, e.name)
        py = self.lookup(e.name)
        direct = self.prog.find_direct(self.mod.path, e.name, py)
        if direct is not None:
            fname, lend_pos = direct
            args = self.call_args(e.args)
            if lend_pos:
                t = self.tmp("r")
                writes = ", ".join("(%s := %s[%d])" % (self.lookup(e.args[i].expr.name), t, k + 1) for k, i in enumerate(lend_pos))
                return "((%s := %s(%s)), %s, %s[0])[-1]" % (t, fname, ", ".join(args), writes, t)
            return "%s(%s)" % (fname, ", ".join(args))
        if py is not None and e.name in self.prog.type_names:
            return "construct(%s, {}, %s)" % (py, loc)
        if py is not None:
            return "call_task(%s, [%s], %s, %r)" % (py, ", ".join(self.call_args(e.args)), loc, want)
        return "B[%r](R, %s, [%s])" % (e.name, loc, ", ".join(self.call_args(e.args)))

    def e_RunCall(self, e, want=True):
        loc = self.loc(e, e.name)
        py = self.lookup(e.name)
        direct = self.prog.find_direct(self.mod.path, e.name, py)
        if direct is not None:
            return "%s()" % direct[0]
        if py is not None:
            return "call_task(%s, [], %s, %r)" % (py, loc, want)
        return "B[%r](R, %s, [])" % (e.name, loc)

    def e_MethodCall(self, e, want=True):
        return "method(%s, %r, [%s], %s, %r)" % (self.expr(e.obj), e.name, ", ".join(self.call_args(e.args)), self.loc(e, e.name), want)

    def free_locals(self, nodes, params):
        names = []
        for b in nodes:
            for x in iter_names(b):
                n = x.name
                if n in params or n in names:
                    continue
                # only true locals (not module globals) are captured by copy
                for sc in reversed(self.scopes[1:]):
                    if n in sc:
                        names.append(n)
                        break
        return names

    def e_Lambda(self, e):
        params = [p.name for p in e.params]
        body = [e.expr] if e.expr is not None else e.body
        caps = self.free_locals(body, set(params))
        self.push()
        cap_defaults = []
        for n in caps:
            outer = self.lookup(n)
            inner = self.declare(n)
            cap_defaults.append("%s=cp(%s)" % (inner, outer))
        pys = [self.declare(p) for p in params]
        if e.expr is not None and not contains_kind(e.expr, ("Try",)):
            code = "PyTask(lambda %s: %s, 'given task', %d)" % (", ".join(pys + cap_defaults), self.take(e.expr), len(pys))
            self.pop()
            return code
        fn = self.tmp("given")
        # emit a nested def before the current statement
        saved, saved_ind = self.out, self.ind
        self.out, self.ind = [], saved_ind
        self.emit("def %s(%s):" % (fn, ", ".join(pys + cap_defaults)))
        self.ind += 1
        self.fn_stack.append((e, [], None))
        self.emit("try:")
        self.ind += 1
        if e.expr is not None:
            self.emit("return %s" % self.take(e.expr))
        else:
            self.block_body(e.body)
            self.emit("return None")
        self.ind -= 1
        self.emit("except TryReturn as _tr:")
        self.emit("    return _tr.value")
        self.fn_stack.pop()
        lines = self.out
        self.out, self.ind = saved, saved_ind
        self.out.extend(lines)
        self.pop()
        return "PyTask(%s, 'given task', %d)" % (fn, len(pys))

    def e_HOF(self, e):
        src = "items(%s, %s)" % (self.expr(e.src), self.loc(e.src))
        self.push()
        x = self.declare(e.var)
        acc = self.declare(e.acc) if e.acc else None
        f = e.form
        loc = self.loc(e)
        if f in ("keep", "count", "find", "any", "every"):
            c = self.cond(e.body, "The `where` condition")
        else:
            body = self.expr(e.body)
        init = self.take(e.init) if e.init is not None else None
        self.pop()
        if f == "keep":
            seq = "[deep_copy(%s) for %s in %s if %s]" % (x, x, src, c)
            st = self.ty(e.src)
            if st is not None and st.name == "set":
                return "PSet(set(%s))" % seq
            return "keep_result(%s, %s)" % (self.expr(e.src), seq)
        if f == "turn":
            return "turn(%s, lambda %s: %s, %s)" % (src, x, body, loc)
        if f == "count":
            return "sum(1 for %s in %s if %s)" % (x, src, c)
        if f == "find":
            return "find_first(%s, lambda %s: %s)" % (src, x, c)
        if f == "any":
            return "any(%s for %s in %s)" % (c, x, src)
        if f == "every":
            return "all(%s for %s in %s)" % (c, x, src)
        if f == "sort":
            return "sort_by(%s, lambda %s: %s, %r, %s)" % (src, x, body, bool(e.desc), loc)
        if f == "combine":
            return "combine(%s, %s, lambda %s, %s: %s)" % (src, init, acc, x, body)
        raise LekhError(SYNTAX, "Unknown list form.", e.line, None, e.file)


HEADER = '''#!/usr/bin/env python3
# Built by Lekh %(version)s from %(source)s with `lekh build`.  Do not edit: change the .lekh file and build again.
import os, sys
_here = os.path.dirname(os.path.abspath(__file__))
for _p in (os.environ.get("LEKH_HOME"), %(lekh_home)r, _here):
    if _p and os.path.isdir(os.path.join(_p, "lekhlib")):
        sys.path.insert(0, _p)
        break
from lekhlib.rt import *
from lekhlib import stdlib
from lekhlib.core import BUILTINS as _BUILTINS
B = {_k: _v[0] for _k, _v in _BUILTINS.items()}


def BV(name):
    fn, lo, hi = _BUILTINS[name]
    return Builtin(name, fn, lo, hi)


def split_group(v, n, loc):
    items = v.items if isinstance(v, (Tuple, PList)) else None
    if items is None or len(items) != n:
        R.err(loc, TYPE_P, "Expected a group of %%d values here, but got %%s." %% (n, describe(v)))
    return items


def keep_result(src, seq):
    return PList(seq)


for _name in ("cp", "add", "sub", "mul", "div", "idiv", "mod", "neg", "T", "eq", "order", "contains", "starts", "between",
              "test_wrap", "type_test", "or_else", "try_", "text", "say", "ask", "fail", "chk", "mklist", "mkmap", "mkset",
              "items", "channel_items", "index", "key", "field", "set_field", "set_index", "set_key", "add_to", "remove_from",
              "take_from", "incr", "range_list", "count_range", "repeat_count", "convert", "construct", "sort_by",
              "find_first", "combine", "turn", "call_task", "method", "ret_check", "when_match", "no_case", "parallel",
              "send", "close", "recv", "start", "wait_for", "sleep", "expect", "replace_me"):
    globals()[_name] = getattr(R, _name)
'''


class Program:
    def __init__(self, loader):
        self.loader = loader
        self.consts = {}
        self.const_lines = []
        self.head = []
        self.locs = {}
        self.compilers = {}
        self.direct = {}
        self.record_fields = {}
        self.variant_types = {}
        self.type_names = set()

    def const(self, code):
        if code not in self.consts:
            name = "_K%d" % len(self.consts)
            self.consts[code] = name
            self.const_lines.append("%s = %s" % (name, code))
        return self.consts[code]

    def loc(self, line, file, name=None):
        key = (line, file, name)
        if key not in self.locs:
            n = "_L%d" % len(self.locs)
            self.locs[key] = n
            self.const_lines.append("%s = Loc(%r, %r, %r)" % (n, line, file, name))
        return self.locs[key]

    def is_variant_of(self, n, names, path):
        mod = self.loader.modules[path]
        return any(n in mod.choices.get(c, []) for c in names)

    def find_direct(self, path, name, py):
        """A direct Python call is possible when `name` refers to a known task (here or imported)."""
        if py is None:
            return None
        for (p, n), v in self.direct.items():
            comp = self.compilers.get(p)
            if n == name and comp is not None and comp.globals.get(n) == py:
                return v
        return None


def order_modules(loader, main_path):
    seen, out = set(), []

    def visit(p):
        if p in seen:
            return
        seen.add(p)
        for s in loader.modules[p].ast:
            if s.kind == "Use":
                visit(s.path)
        out.append(p)
    visit(main_path)
    return out


def build_source(loader, main_path):
    prog = Program(loader)
    for m in loader.modules.values():
        for s in m.ast:
            if s.kind == "RecordDef":
                prog.record_fields[s.name] = [f for f, _ in s.fields]
                prog.type_names.add(s.name)
            elif s.kind == "ChoiceDef":
                prog.type_names.add(s.name)
                for vn, fields, _ in s.variants:
                    prog.variant_types[vn] = fields
                    prog.type_names.add(vn)
    prog.record_fields.update({"CommandOutput": ["output", "errors", "code"], "Response": ["status", "body", "headers"]})
    bodies = []
    order = order_modules(loader, main_path)
    for i, p in enumerate(order):
        mc = ModuleCompiler(prog, loader.modules[p], i)
        prog.compilers[p] = mc
        mc.compile()
        bodies.append("\n".join(mc.out))
    lekh_home = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sources = {p: "\n".join(SOURCES.get(p, [])) for p in order}
    parts = [HEADER % {"version": VERSION, "source": os.path.basename(main_path), "lekh_home": lekh_home}]
    parts.append("SOURCES_ = %r\n" % sources)
    parts.append("\n".join(prog.const_lines))
    parts.append("\n".join(prog.head))
    parts.extend(bodies)
    tops = "\n".join("    m%d_top()" % i for i in range(len(order)))
    parts.append("\n\ndef _lekh_main():\n%s\n\n\nif __name__ == '__main__':\n    sys.exit(run_main(_lekh_main, SOURCES_, sys.argv[1:]))\n" % tops)
    return "\n\n".join(parts)


def build_file(path, out):
    from .cli import load_and_check
    loader, mod = load_and_check(path)
    code = build_source(loader, mod.path)
    compile(code, out, "exec")   # make sure the output is valid Python
    with open(out, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        os.chmod(out, 0o755)
    except OSError:
        pass
    return out
