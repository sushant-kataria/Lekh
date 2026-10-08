#!/usr/bin/env python3
"""Compare `lekh run` (tree-walking interpreter) with `lekh build` (transpiled Python).

    python3 benchmarks/run_benchmark.py
"""
import os, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEKH = os.path.join(ROOT, "lekh.py")
SRC = os.path.join(ROOT, "benchmarks", "fib.lekh")
OUT = os.path.join(ROOT, "benchmarks", "fib_built.py")


def timed(cmd):
    t = time.perf_counter()
    p = subprocess.run(cmd, capture_output=True, text=True)
    return time.perf_counter() - t, p.stdout


subprocess.run([sys.executable, LEKH, "build", SRC, "-o", OUT], check=True, capture_output=True)
t1, o1 = timed([sys.executable, LEKH, "run", SRC])
t2, o2 = timed([sys.executable, OUT])
print(o1, end="")
print("same output: %s" % (o1 == o2))
print("lekh run   (interpreter): %.2f s" % t1)
print("lekh build (transpiled):  %.2f s" % t2)
print("speed-up: %.1fx" % (t1 / t2))
