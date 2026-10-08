#!/usr/bin/env python3
"""Check that every Lekh code sample in the docs really works.

Fences understood in README.md and docs/**/*.md:

    ```lekh                  run it; it must finish without an error
    ```lekh check            only check it (lekh check), e.g. it needs the network
    ```lekh error            it must FAIL (used to show Lekh's error messages)
    ```lekh test             run it with `lekh test`
    ```lekh stdin=Ann|30     run it, typing "Ann" then "30" (| separates lines;
                             quote it if it has spaces: stdin="Ann Rao|30")
    ```lekh file=tools.lekh  save it as tools.lekh next to the doc's other samples
                             (so a later sample can `use` it); it is checked too

A ```output block straight after a sample must match what the sample prints.
`python3 tools/docs_check.py --update` rewrites those output blocks with the
real output, so the docs never show made-up results.

Each doc runs in its own temporary folder, so samples can create files freely.
"""
import os, re, shlex, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEKH = os.path.join(ROOT, "lekh.py")
FENCE = re.compile(r"^```(\w*)(.*)$")


def doc_files():
    out = [os.path.join(ROOT, "README.md")]
    for base, _, files in os.walk(os.path.join(ROOT, "docs")):
        out += [os.path.join(base, f) for f in files if f.endswith(".md")]
    return sorted(out)


def parse(path):
    """Return (lines, samples). A sample is a dict with its options, code and output block span."""
    lines = open(path, encoding="utf-8").read().split("\n")
    samples, i = [], 0
    while i < len(lines):
        m = FENCE.match(lines[i])
        if m and m.group(1) == "lekh":
            opts = shlex.split(m.group(2))
            start = i
            j = i + 1
            while j < len(lines) and lines[j] != "```":
                j += 1
            code = "\n".join(lines[i + 1:j]) + "\n"
            s = {"line": start + 1, "opts": opts, "code": code, "out": None}
            k = j + 1
            while k < len(lines) and lines[k].strip() == "":
                k += 1
            if k < len(lines) and lines[k] == "```output":
                e = k + 1
                while e < len(lines) and lines[e] != "```":
                    e += 1
                s["out"] = (k + 1, e)        # lines[k+1:e] is the expected output
                j = e
            samples.append(s)
            i = j + 1
        elif m and lines[i].startswith("```"):
            j = i + 1                         # skip other fenced blocks whole
            while j < len(lines) and lines[j] != "```":
                j += 1
            i = j + 1
        else:
            i += 1
    return lines, samples


def run_sample(s, folder, n):
    opts = s["opts"]
    stdin = ""
    name = "sample_%d.lekh" % n
    mode = "run"
    for o in opts:
        if o.startswith("stdin="):
            stdin = o[6:].replace("|", "\n") + "\n"
        elif o.startswith("file="):
            name, mode = o[5:], "check"
        elif o in ("check", "error", "test"):
            mode = o
    path = os.path.join(folder, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(s["code"])
    cmd = {"run": ["run"], "check": ["check"], "error": ["run"], "test": ["test"]}[mode]
    env = dict(os.environ, NO_COLOR="1")
    p = subprocess.run([sys.executable, LEKH] + cmd + [path], input=stdin, capture_output=True,
                       text=True, cwd=folder, timeout=120, env=env)
    out = (p.stdout + p.stderr).replace(folder + os.sep, "")
    if mode == "error":
        ok = p.returncode != 0 and "Lekh" in out
        why = "" if ok else "this sample should fail with a Lekh error, but it didn't"
    else:
        ok = p.returncode == 0
        why = "" if ok else "exit code %d" % p.returncode
    return ok, why, out


def check_doc(path, update=False):
    """Returns (number of samples, list of failure messages)."""
    lines, samples = parse(path)
    fails = []
    rel = os.path.relpath(path, ROOT)
    edits = []
    with tempfile.TemporaryDirectory() as folder:
        for n, s in enumerate(samples, 1):
            try:
                ok, why, out = run_sample(s, folder, n)
            except subprocess.TimeoutExpired:
                ok, why, out = False, "timed out", ""
            if not ok:
                fails.append("%s line %d: %s\n%s" % (rel, s["line"], why, indent(out)))
                continue
            if s["out"] is not None:
                a, b = s["out"]
                want = "\n".join(lines[a:b]).rstrip("\n")
                got = out.rstrip("\n")
                if got != want:
                    if update:
                        edits.append((a, b, got.split("\n") if got else []))
                    else:
                        fails.append("%s line %d: the output block doesn't match.\n--- expected\n%s\n--- got\n%s"
                                     % (rel, s["line"], indent(want), indent(got)))
    if edits:
        for a, b, new in sorted(edits, reverse=True):
            lines[a:b] = new
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    return len(samples), fails


def indent(t):
    return "\n".join("    " + x for x in t.split("\n"))


def main():
    update = "--update" in sys.argv
    files = [os.path.abspath(a) for a in sys.argv[1:] if not a.startswith("--")] or doc_files()
    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(lambda p: (p, check_doc(p, update)), files))
    total, bad = 0, 0
    for p, (n, fails) in results:
        total += n
        status = "PASS" if not fails else "FAIL"
        print("  %s  %s (%d samples)" % (status, os.path.relpath(p, ROOT), n))
        for f in fails:
            bad += 1
            print(indent(f))
    print("%d samples, %d problems" % (total, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
