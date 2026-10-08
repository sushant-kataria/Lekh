#!/usr/bin/env python3
"""Lekh test runner.

  python3 tests/run_tests.py           run everything
  python3 tests/run_tests.py --update  re-record expected example output

1. Every program in examples/ must run without errors (exit code 0). Its output is saved to
   examples/output/<name>.txt and compared with tests/expected/<name>.txt.
2. Every program in tests/errors/ must FAIL with a friendly error. Each `-- expect: <text>` line
   at the top of the file is a piece of text that must appear in the error message.
3. A quick REPL smoke test.
"""
import glob, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEKH = os.path.join(ROOT, "lekh.py")
INPUTS = {"greeter": "Sushant\n30\n",
          "text_adventure": "help\nlook\ngo east\nnorth\ntake brass key\ntake spoon\nuse biscuit\nsouth\nuse brass key\nbag\ndance\neast\ntake treasure\n"}  # programs that use `ask`
FEATURE_INPUTS = {}
UPDATE = "--update" in sys.argv

passed, failed = 0, []


def run(args, stdin=""):
    p = subprocess.run([sys.executable, LEKH] + args, input=stdin, capture_output=True, text=True, cwd=ROOT, timeout=30)
    return p.returncode, p.stdout, p.stderr


def ok(name):
    global passed
    passed += 1
    print("  PASS  " + name)


def bad(name, why):
    failed.append(name)
    print("  FAIL  %s\n        %s" % (name, why.replace("\n", "\n        ")))


print("Examples (must run cleanly):")
for path in sorted(glob.glob(os.path.join(ROOT, "examples", "*.lekh"))):
    name = os.path.splitext(os.path.basename(path))[0]
    rel = os.path.relpath(path, ROOT)
    code, out, err = run([rel], INPUTS.get(name, ""))
    with open(os.path.join(ROOT, "examples", "output", name + ".txt"), "w") as f:
        f.write(out + err)
    if code != 0:
        bad(rel, "exit code %d\n%s" % (code, err))
        continue
    code2, out2, err2 = run(["--check", rel])
    if code2 != 0:
        bad(rel + " (--check)", err2)
        continue
    exp = os.path.join(ROOT, "tests", "expected", name + ".txt")
    if UPDATE or not os.path.exists(exp):
        with open(exp, "w") as f:
            f.write(out)
    elif open(exp).read() != out:
        bad(rel, "output differs from tests/expected/%s.txt" % name)
        continue
    ok(rel)

print("\nFeature programs (tests/features, output must match tests/expected/features):")
os.makedirs(os.path.join(ROOT, "tests", "expected", "features"), exist_ok=True)
for path in sorted(glob.glob(os.path.join(ROOT, "tests", "features", "*.lekh"))):
    name = os.path.splitext(os.path.basename(path))[0]
    rel = os.path.relpath(path, ROOT)
    first = open(path).readline()
    args = first.split("-- args:", 1)[1].split() if first.startswith("-- args:") else []
    code, out, err = run([rel] + args, FEATURE_INPUTS.get(name, ""))
    if code != 0:
        bad(rel, "exit code %d\n%s" % (code, err))
        continue
    exp = os.path.join(ROOT, "tests", "expected", "features", name + ".txt")
    if UPDATE or not os.path.exists(exp):
        with open(exp, "w") as f:
            f.write(out)
    elif open(exp).read() != out:
        bad(rel, "output differs from tests/expected/features/%s.txt\n--- got ---\n%s" % (name, out))
        continue
    ok(rel)

print("\nError cases (must fail with a friendly message):")
for path in sorted(glob.glob(os.path.join(ROOT, "tests", "errors", "*.lekh"))):
    rel = os.path.relpath(path, ROOT)
    expects = [l.split("-- expect:", 1)[1].strip() for l in open(path) if l.startswith("-- expect:")]
    code, out, err = run([rel])
    msg = out + err
    if code != 1:
        bad(rel, "expected exit code 1, got %d\n%s" % (code, msg))
        continue
    missing = [e for e in expects if e not in msg]
    if "-- Lekh:" not in msg:
        missing.append("-- Lekh: (error header)")
    if missing:
        bad(rel, "missing in error message: %s\n--- got ---%s" % (missing, msg))
        continue
    if any(l.strip() == "-- static" for l in open(path)):
        c2, o2, e2 = run(["--check", rel])
        if c2 != 1:
            bad(rel, "should be caught by `lekh check` before running, but wasn't\n%s" % (o2 + e2))
            continue
    ok(rel)

print("\nlekh build (transpiled programs must print exactly what `lekh run` prints):")
import tempfile
BUILD_DIR = tempfile.mkdtemp(prefix="lekh_build_")
for path in sorted(glob.glob(os.path.join(ROOT, "examples", "*.lekh")) + glob.glob(os.path.join(ROOT, "tests", "features", "*.lekh"))):
    name = os.path.splitext(os.path.basename(path))[0]
    rel = os.path.relpath(path, ROOT)
    out_py = os.path.join(BUILD_DIR, name + ".py")
    code, out, err = run(["build", rel, "-o", out_py])
    if code != 0:
        bad("build " + rel, err)
        continue
    first = open(path).readline()
    args = first.split("-- args:", 1)[1].split() if first.startswith("-- args:") else []
    inp = INPUTS.get(name, FEATURE_INPUTS.get(name, ""))
    p = subprocess.run([sys.executable, out_py] + args, input=inp, capture_output=True, text=True, cwd=ROOT, timeout=60)
    exp_dir = "features" if "/features/" in path.replace(os.sep, "/") else ""
    exp = os.path.join(ROOT, "tests", "expected", exp_dir, name + ".txt")
    if p.returncode != 0 or open(exp).read() != p.stdout:
        bad("build " + rel, "built program output differs (exit %d)\n%s%s" % (p.returncode, p.stdout[-800:], p.stderr[-800:]))
        continue
    ok("build " + rel)

print("\nlekh test (test blocks):")
code, out, err = run(["test", "tests/unit"])
n_unit = out.count("  PASS  ")
if code == 0 and "0 failed" in out and n_unit >= 20:
    ok("tests/unit (%d test blocks pass)" % n_unit)
else:
    bad("tests/unit", out + err)
code, out, err = run(["test", "tests/unit_fail"])
if code == 1 and "FAIL  shout adds an exclamation mark" in out and 'Expected `shout of "hi"` to be "HI!", but it was "HI".' in out \
        and "1 passed, 2 failed" in out:
    ok("tests/unit_fail (failures are reported clearly)")
else:
    bad("tests/unit_fail", out + err)

print("\nProject tools (new / run / test / format / build):")
proj_root = tempfile.mkdtemp(prefix="lekh_proj_")
proj = os.path.join(proj_root, "demo_app")
def runp(args, cwd):
    p = subprocess.run([sys.executable, LEKH] + args, capture_output=True, text=True, cwd=cwd, timeout=60)
    return p.returncode, p.stdout + p.stderr
c1, o1 = runp(["new", proj], proj_root)
c2, o2 = runp(["run"], proj)
c3, o3 = runp(["run", "src/main.lekh", "Sushant"], proj)
c4, o4 = runp(["test"], proj)
c5, o5 = runp(["format", "--check"], proj)
c6, o6 = runp(["build"], proj)
c7, o7 = (1, "")
if c6 == 0:
    pr = subprocess.run([sys.executable, os.path.join(proj, "src", "main.py"), "Asha"], capture_output=True, text=True, timeout=60)
    c7, o7 = pr.returncode, pr.stdout
if c1 == 0 and "Hello, world!" in o2 and "Hello, Sushant!" in o3 and c4 == 0 and "2 passed" in o4 and c5 == 0 and c7 == 0 and "Hello, Asha!" in o7:
    ok("lekh new demo_app -> run, test, format --check, build")
else:
    bad("project tools", "\n".join([o1, o2, o3, o4, o5, o6, o7]))
messy = os.path.join(proj_root, "messy.lekh")
with open(messy, "w") as f:
    f.write('to  greet name,greeting :\n\tsay "{greeting}, {name}!"   --says hi\n\n\n\tif name is "x" :\n\t\t\tsay  ( 1+2 )\nsay greet with "a", "b"\n')
c, o = runp(["format", "--check", messy], proj_root)
c2, o2 = runp(["format", messy], proj_root)
c3, o3 = runp(["format", "--check", messy], proj_root)
tidy = open(messy).read()
want = 'to greet name, greeting:\n    say "{greeting}, {name}!" -- says hi\n\n    if name is "x":\n        say (1 + 2)\nsay greet with "a", "b"\n'
if c == 1 and c2 == 0 and c3 == 0 and tidy == want:
    ok("lekh format tidies a messy file (and --check reports it)")
else:
    bad("lekh format", o + o2 + o3 + "\n---\n" + tidy)
c, o, e = run(["format", "--check", "examples"])
if c == 0:
    ok("lekh format --check examples (all examples are tidy)")
else:
    bad("format examples", o + e)

print("\nHTTP client (against a local test server):")
import http.server, json as _json, threading
class _H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass
    def _send(self, code, body):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    def do_GET(self):
        if self.path == "/hello":
            self._send(200, "hi there")
        else:
            self._send(404, "not found")
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        got = _json.loads(self.rfile.read(n) or b"{}")
        self._send(201, _json.dumps({"received": got}))
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = "http://127.0.0.1:%d" % srv.server_address[1]
code, out, err = run(["tests/http/http_client.lekh", base])
srv.shutdown()
want = ["GET status 200, body hi there", "missing page status 404", "POST status 201", "server saw qty 2",
        "bad scheme is a problem: true", "unreachable is a problem: true"]
if code == 0 and all(w in out for w in want):
    ok("tests/http/http_client.lekh")
else:
    bad("tests/http/http_client.lekh", out + err)

print("\nREPL:")
code, out, err = run([], 'let name be "Sushant"\nsay "Hi {name}"\nto double x:\n    give back x * 2\n\nsay double of 21\n2 + 3\nchange name to "x"\nquit\n')
if "Hi Sushant" in out and "42" in out and "5" in out and "can't be changed" in out.lower() + "can't be changed":
    if "This can't be changed" in out:
        ok("repl session")
    else:
        bad("repl session", out + err)
else:
    bad("repl session", out + err)

print("\nDocs (every code sample in README.md and docs/ runs, and shown output is real):")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import docs_check
from concurrent.futures import ThreadPoolExecutor as _Pool
with _Pool(8) as _ex:
    _results = list(_ex.map(lambda p: (p, docs_check.check_doc(p)), docs_check.doc_files()))
_total = 0
for _p, (_n, _fails) in _results:
    _total += _n
    _rel = os.path.relpath(_p, ROOT)
    if _n == 0:
        continue
    if _fails:
        bad("%s (%d samples)" % (_rel, _n), "\n".join(_fails))
    else:
        ok("%s (%d samples)" % (_rel, _n))
print("        (%d doc samples in total)" % _total)

# the reference must show every built-in task and keyword inside a runnable sample or table
sys.path.insert(0, ROOT)
from lekhlib import core as _core
_ref = open(os.path.join(ROOT, "docs", "reference.md"), encoding="utf-8").read()
_lines, _samples = docs_check.parse(os.path.join(ROOT, "docs", "reference.md"))
_code = "\n".join(x["code"] for x in _samples)
_missing = [b for b in sorted(_core.BUILTINS) if not re.search(r"\b%s\b" % re.escape(b), _code)]
_missing_kw = [k for k in sorted(_core.KEYWORDS) if "`%s`" % k not in _ref]
if _missing or _missing_kw:
    bad("docs/reference.md covers everything",
        "built-ins without a runnable example: %s\nkeywords not documented: %s" % (_missing, _missing_kw))
else:
    ok("docs/reference.md covers all %d built-in tasks and %d keywords" % (len(_core.BUILTINS), len(_core.KEYWORDS)))

print("\n%d passed, %d failed" % (passed, len(failed)))
sys.exit(1 if failed else 0)
