"""Lekh command line.

    lekh <file.lekh> [words...]       run a program (the words become `arguments`)
    lekh run [file.lekh] [words...]   same; inside a project, runs its main file
    lekh check <file.lekh>            only run the safety and type checks
    lekh test [file-or-folder]        run `test "...":` blocks (default: the project's tests/ folder)
    lekh format <file-or-folder> [--check]   tidy spacing and indentation (--check: only report)
    lekh build <file.lekh> [-o out.py]       translate to a fast Python program (release build)
    lekh new <name>                   create a new project folder
    lekh repl                         interactive mode (also: just `lekh`)
    lekh help | lekh version
"""
import glob
import json
import os
import sys

from . import core
from .core import (Loader, Checker, Interp, LekhError, format_error, display_path, VERSION, EXT, LIMIT_P,
                   find_project_root, PROJECT_FILE)

COMMANDS = ("run", "check", "test", "format", "build", "new", "repl", "help", "version")


def load_and_check(path):
    from .typecheck import typecheck
    loader = Loader()
    mod = loader.load(path)
    for m in list(loader.modules.values()):
        Checker(m, loader).check()
    for m in list(loader.modules.values()):
        typecheck(m, loader)
    return loader, mod


def report(e):
    sys.stdout.flush()
    sys.stderr.write(format_error(e))
    return 1


def project_main(start="."):
    root = find_project_root(start)
    if not root:
        return None
    try:
        with open(os.path.join(root, PROJECT_FILE), encoding="utf-8") as f:
            info = json.load(f)
    except (OSError, ValueError):
        return None
    return os.path.join(root, info.get("main", "src/main.lekh"))


def cmd_run(args, check_only=False):
    if not args or not args[0].endswith(EXT):
        main = project_main()
        if main is None:
            print("Which program should I run?  lekh run program%s" % EXT)
            return 2
        path, rest = main, args
    else:
        path, rest = args[0], args[1:]
    from .stdlib import ExitSignal
    try:
        loader, mod = load_and_check(path)
        if check_only:
            print("No problems found in %s." % display_path(os.path.abspath(path)))
            return 0
        interp = Interp(loader)
        interp.program_args = list(rest)
        interp.run_module(mod)
        return 0
    except LekhError as e:
        return report(e)
    except ExitSignal as x:
        sys.stdout.flush()
        return x.code
    except RecursionError:
        return report(LekhError(LIMIT_P, "The program went too deep (a task probably calls itself forever).", None,
                                "Make sure recursive tasks have a stopping case."))
    except KeyboardInterrupt:
        sys.stderr.write("\nStopped.\n")
        return 130


# ------------------------------------------------------------------------------------- lekh test
def collect_files(target, default_sub="tests"):
    if target is None:
        root = find_project_root(".") or "."
        target = os.path.join(root, default_sub) if os.path.isdir(os.path.join(root, default_sub)) else root
    if os.path.isdir(target):
        return sorted(p for p in glob.glob(os.path.join(target, "**", "*" + EXT), recursive=True))
    return [target]


def cmd_test(args):
    target = args[0] if args else None
    files = collect_files(target)
    total = passed = 0
    problems = 0
    for path in files:
        try:
            with open(path, encoding="utf-8") as f:
                if "test \"" not in f.read():
                    continue
            loader, mod = load_and_check(path)
            results = Interp(loader).run_tests(mod)
        except LekhError as e:
            print("%s: could not run" % display_path(os.path.abspath(path)))
            sys.stdout.write(format_error(e))
            problems += 1
            continue
        if not results:
            continue
        print(display_path(os.path.abspath(path)))
        for node, err in results:
            total += 1
            if err is None:
                passed += 1
                print("  PASS  %s" % node.name)
            else:
                print("  FAIL  %s" % node.name)
                where = " (line %d)" % err.line if err.line else ""
                print("        %s%s" % (err.message, where))
                if err.title != core.TEST_P:
                    print("        (%s)" % err.title)
    failed = total - passed
    print("\n%d test%s, %d passed, %d failed%s" % (total, "" if total == 1 else "s", passed, failed,
                                                   ", %d file%s couldn't run" % (problems, "" if problems == 1 else "s") if problems else ""))
    if total == 0 and not problems:
        print('No tests found. Write one like:\n    test "adding works":\n        expect 1 + 1 to be 2')
    return 1 if failed or problems else 0


# ------------------------------------------------------------------------------------- lekh format
def cmd_format(args):
    from .formatter import format_file_text
    check = "--check" in args
    targets = [a for a in args if not a.startswith("--")]
    if not targets:
        targets = [find_project_root(".") or "."]
    files = []
    for t in targets:
        files += collect_files(t, default_sub="") if os.path.isdir(t) else [t]
    changed, bad = [], 0
    for path in files:
        try:
            with open(path, encoding="utf-8") as f:
                src = f.read()
            new = format_file_text(src, os.path.abspath(path))
        except LekhError as e:
            sys.stdout.write(format_error(e))
            bad += 1
            continue
        except OSError as e:
            print("Can't read %s: %s" % (path, e.strerror))
            bad += 1
            continue
        if new != src:
            changed.append(path)
            if not check:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new)
    for p in changed:
        print(("needs tidying: %s" if check else "tidied: %s") % p)
    if not changed and not bad:
        print("Everything is already tidy (%d file%s)." % (len(files), "" if len(files) == 1 else "s"))
    if bad:
        return 1
    return 1 if (check and changed) else 0


# ------------------------------------------------------------------------------------- lekh build
def cmd_build(args):
    from .build import build_file
    if not args:
        main = project_main()
        if main is None:
            print("Which program should I build?  lekh build program%s [-o out.py]" % EXT)
            return 2
        args = [main]
    path = args[0]
    out = None
    if "-o" in args:
        i = args.index("-o")
        out = args[i + 1] if i + 1 < len(args) else None
    if out is None:
        out = os.path.splitext(path)[0] + ".py"
    try:
        load_and_check(path)
        build_file(path, out)
    except LekhError as e:
        return report(e)
    print("Built %s -> %s\nRun it with:  python3 %s" % (path, out, out))
    return 0


# ------------------------------------------------------------------------------------- lekh new
MAIN_TEMPLATE = '''-- {name}: the main program.  Run it with:  lekh run   (or: lekh run src/main.lekh Sushant)
use greet from "greetings"

let words be arguments
let changeable who be "world"
if length of words is greater than 0:
    change who to item 1 of words
say greet with who
'''

LIB_TEMPLATE = '''-- greetings: a module.  Only things marked `share` can be used by other files.

share to greet name as text gives text:
    give back "Hello, {name}! " + (cheer of 1)

to cheer level as number gives text:
    give back repeat_text with "*", level
'''

TEST_TEMPLATE = '''-- Tests for the greetings module.  Run them with:  lekh test
use greet from "greetings"

test "greet says hello":
    expect greet with "Asha" to be "Hello, Asha! *"

test "greet mentions the name":
    expect greet with "Ravi" to contain "Ravi"
'''

README_TEMPLATE = '''# {name}

A [Lekh](https://example.invalid/lekh) project.

    lekh run                 # runs src/main.lekh
    lekh run src/main.lekh Asha
    lekh test                # runs tests/
    lekh format              # tidies every .lekh file
    lekh build               # makes a fast Python version: src/main.py
'''


def cmd_new(args):
    if not args:
        print("Give the project a name:  lekh new my_app")
        return 2
    name = args[0]
    if os.path.exists(name):
        print("There's already a file or folder called `%s`. Pick another name." % name)
        return 1
    base = os.path.basename(os.path.normpath(name))
    os.makedirs(os.path.join(name, "src"))
    os.makedirs(os.path.join(name, "tests"))
    files = {
        PROJECT_FILE: json.dumps({"name": base, "version": "0.1.0", "main": "src/main.lekh", "lekh": VERSION}, indent=2) + "\n",
        os.path.join("src", "main.lekh"): MAIN_TEMPLATE.format(name=base),
        os.path.join("src", "greetings.lekh"): LIB_TEMPLATE,
        os.path.join("tests", "greetings_test.lekh"): TEST_TEMPLATE,
        "README.md": README_TEMPLATE.format(name=base),
        ".gitignore": "__pycache__/\n*.pyc\n",
    }
    for rel, content in files.items():
        with open(os.path.join(name, rel), "w", encoding="utf-8") as f:
            f.write(content)
    print("Created %s/" % name)
    for rel in sorted(files):
        print("  " + rel)
    print("\nNext:\n  cd %s\n  lekh run\n  lekh test" % name)
    return 0


# ------------------------------------------------------------------------------------- REPL
def cmd_repl(args):
    from .repl import repl
    repl()
    return 0


def main(argv):
    try:
        return _main(argv)
    except BrokenPipeError:
        # output was piped into something like `head` that stopped reading - not an error
        try:
            sys.stdout = open(os.devnull, "w")
        except OSError:
            pass
        return 0


def _main(argv):
    sys.setrecursionlimit(100000)
    try:
        import threading
        threading.stack_size(64 * 1024 * 1024)
    except (ValueError, RuntimeError):
        pass
    args = argv[1:]
    if not args:
        return cmd_repl([])
    first = args[0]
    if first in ("-h", "--help", "help"):
        print(__doc__.strip())
        return 0
    if first in ("-v", "--version", "version"):
        print("Lekh", VERSION)
        return 0
    if first == "--check":
        return cmd_run(args[1:], check_only=True)
    if first == "check":
        return cmd_run(args[1:], check_only=True)
    if first == "run":
        return cmd_run(args[1:])
    if first == "test":
        return cmd_test(args[1:])
    if first == "format":
        return cmd_format(args[1:])
    if first == "build":
        return cmd_build(args[1:])
    if first == "new":
        return cmd_new(args[1:])
    if first == "repl":
        return cmd_repl(args[1:])
    if first.endswith(EXT) or os.path.exists(first):
        return cmd_run(args)
    print("I don't know the command `%s`.\n" % first)
    print(__doc__.strip())
    return 2
