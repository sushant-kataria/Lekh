# 14. Modules, tests and tools

## Splitting a program into files

Any `.lekh` file can be used by another. Inside a file, everything is
**private** unless marked `share`, so a module decides what others can use.

Here is a module, `shop_tools.lekh`:

```lekh file=shop_tools.lekh
-- shop_tools: helpers for prices
share constant GST be 0.18

share to with_gst price as number gives number:
    give back round with price * (1 + GST), 2

to secret_margin gives number:
    give back 0.3
```

And a program that uses it:

```lekh
use with_gst, GST from "shop_tools"
say "GST is {GST * 100}%"
say with_gst of 1000
```

```output
GST is 18%
1180
```

`use "shop_tools"` (without a list of names) brings in everything the module
shares. Using something it doesn't share is an error:

```lekh error
use secret_margin from "shop_tools"
say run secret_margin
```

```output

-- Lekh: Unknown name ------------------------------------------------
In sample_3.lekh, line 1:

    1 | use secret_margin from "shop_tools"

`secret_margin` is private to the module `shop_tools`.

How to fix:
    In shop_tools.lekh, put `share` in front of it to make it public:
        share to secret_margin ...
```

Lekh looks for a module next to the file that uses it, then in the project's
`src/` and `lib/` folders.

## Projects

```bash
lekh new my_app
cd my_app
lekh run          # runs src/main.lekh
lekh test         # runs everything in tests/
```

`lekh new` creates:

```text
my_app/
  project.json        name, version, main file
  src/main.lekh       the program
  src/greetings.lekh  an example module
  tests/greetings_test.lekh
  README.md
  .gitignore
```

## Tests

A `test` block checks that code does what you expect. `expect` lines say what
should be true:

```lekh test
to add_gst price as number gives number:
    give back price * 1.18

test "GST is added":
    expect add_gst of 100 to be 118

test "text and lists":
    expect uppercase of "lekh" to be "LEKH"
    expect list of 1, 2, 3 to contain 2
    expect ("abc" as number) to be problem
    expect (map of "a" to 1) at "b" to be nothing
```

```output
sample_4.lekh
  PASS  GST is added
  PASS  text and lists

2 tests, 2 passed, 0 failed
```

`lekh test` runs all test blocks in a file, a folder, or the whole project,
and shows exactly what differed when one fails. When you run a file normally,
its test blocks are skipped.

## Formatting

`lekh format app.lekh` tidies the layout: 4-space indents, single spaces
around operators and after commas, blank lines between tasks. It never changes
what the program means (it refuses if it ever would).
`lekh format --check .` lists untidy files without touching them, which is handy in CI.

## Checking without running

`lekh check app.lekh` runs every safety check (names, types, ownership,
missing cases) without running anything.

## Building a fast version

```bash
lekh build app.lekh            # writes app_built.py
python3 app_built.py
```

`lekh build` translates the program into Python after all the checks pass.
The built file runs about **17 times faster** than `lekh run` on a
number-crunching benchmark, and prints exactly the same output. It needs the
`lekhlib` folder (it finds it automatically, or set `LEKH_HOME`).
See [the roadmap](../roadmap.md) for what is and isn't supported in builds.

Next: [15. Building a real program](15-a-real-program.md)
