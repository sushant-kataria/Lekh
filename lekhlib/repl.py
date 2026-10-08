"""Interactive Lekh (the REPL).

Improvements in 0.2: line editing and history (saved in ~/.lekh_history), blocks finish with an
empty line, and commands:
    :help            tips
    :vars            what you've defined so far
    :type <expr>     show the type Lekh works out for an expression
    :load <file>     run a file and keep its definitions
    :reset           forget everything
    :quit            leave (also: quit, exit, Ctrl-D)
"""
import os
import sys

from .core import (Loader, Checker, Interp, Env, LekhError, format_error, VERSION, VarInfo, Function, RecordType,
                   ChoiceType, AbilityType, show, describe)

REPL_HELP = """Type Lekh statements. Lines ending in ':' start a block; finish a block with an empty line.
  let name be "Sushant"          say "Hello, {name}"
  let changeable n be 1           increase n by 1
  to double x: give back x * 2   (then)  say double of 21
  turn each n in list of 1, 2, 3 into n * 10
Commands: :help  :vars  :type <expr>  :load <file>  :reset  :quit"""


class Session:
    def __init__(self):
        self.reset()

    def reset(self):
        self.loader = Loader()
        self.interp = Interp(self.loader)
        self.genv = Env(self.interp.builtins)
        self.types, self.tfields = set(), {}

    def run(self, src, name="<repl>", echo=True):
        mod = self.loader.load_source(src, name, extra_types=self.types, extra_fields=self.tfields)
        self.types |= set(mod.records) | set(mod.choices) | {v for vs in mod.choices.values() for v in vs}
        self.tfields.update(mod.fields)
        pre = {}
        for n, slot in self.genv.vars.items():
            role = {"function": "function", "type": "type"}.get(slot.role, "let")
            pre[n] = VarInfo(n, role, changeable=slot.changeable, line=slot.line)
        ch = Checker(mod, self.loader, predefined=pre, repl=echo)
        for n, slot in self.genv.vars.items():
            v = slot.get()
            if isinstance(v, Function):
                ch.funcs[n] = v.node
            elif isinstance(v, RecordType):
                ch.records[n] = [f for f, _ in v.fields]
            elif isinstance(v, ChoiceType):
                ch.choices[n] = list(v.variants)
                for vn, vt in v.variants.items():
                    ch.variants[vn] = (n, [f for f, _ in vt.fields])
            elif isinstance(v, AbilityType):
                ch.abilities[n] = v.node
        ch.check()
        self.interp.run_stmts(mod.ast, self.genv, repl=echo)

    def describe_vars(self):
        rows = []
        for n, slot in self.genv.vars.items():
            v = slot.get()
            if isinstance(v, Function):
                rows.append("  task    %s" % n)
            elif isinstance(v, (RecordType, ChoiceType, AbilityType)):
                rows.append("  type    %s" % n)
            elif slot.role in ("let", "item", "param"):
                rows.append("  %s %s = %s" % ("let changeable" if slot.changeable else "let", n, show(v, True)))
        return "\n".join(rows) or "  (nothing yet)"

    def type_of(self, expr_src):
        # evaluate without keeping it, then describe the value
        self.run("let __repl_probe__ be " + expr_src, echo=False)
        slot = self.genv.vars.pop("__repl_probe__", None)
        return describe(slot.get()) if slot else "(no value)"


def setup_readline():
    try:
        import readline
    except ImportError:
        return None
    hist = os.path.expanduser("~/.lekh_history")
    try:
        readline.read_history_file(hist)
    except OSError:
        pass
    readline.set_history_length(1000)
    import atexit

    def save():
        try:
            readline.write_history_file(hist)
        except OSError:
            pass
    atexit.register(save)
    return readline


def repl():
    interactive = sys.stdin.isatty()
    if interactive:
        setup_readline()
    print("Lekh %s - a language that reads like English. Type :help for tips, :quit to leave." % VERSION)
    s = Session()
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
            if cmd in ("quit", "exit", ":quit", ":q"):
                break
            if cmd in ("help", ":help"):
                print(REPL_HELP)
                continue
            if cmd == ":vars":
                print(s.describe_vars())
                continue
            if cmd == ":reset":
                s.reset()
                print("Forgot everything.")
                continue
            if cmd.startswith(":type "):
                try:
                    print(s.type_of(cmd[6:]))
                except LekhError as e:
                    sys.stdout.write(format_error(e))
                continue
            if cmd.startswith(":load "):
                path = cmd[6:].strip()
                try:
                    with open(path, encoding="utf-8") as f:
                        s.run(f.read(), os.path.abspath(path), echo=False)
                    print("Loaded %s." % path)
                except OSError as e:
                    print("Can't open %s: %s" % (path, e.strerror))
                except LekhError as e:
                    sys.stdout.write(format_error(e))
                continue
            if cmd.startswith(":"):
                print("Unknown command. Try :help")
                continue
            if not cmd:
                continue
        buf.append(line)
        if line.rstrip().endswith(":") or (len(buf) > 1 and line.strip()):
            continue
        src = "\n".join(buf)
        buf = []
        try:
            s.run(src)
        except LekhError as e:
            sys.stdout.write(format_error(e))
        except RecursionError:
            print("Too deep: a task probably calls itself forever.")
