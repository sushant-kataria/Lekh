# Lekh: language design

> **Lekh** (लेख, Hindi/Sanskrit for "a piece of writing"). A program should read like something
> you *wrote*, not something you *encoded*.

## 0. The name

| Option | Meaning | Clash check (web search, Oct 2026) | Verdict |
|---|---|---|---|
| **Lekh** | "writing / an essay" (Hindi, Sanskrit) | No programming language found. Only a whiteboard app (Lekh Board) uses the name. | **Chosen** |
| Kathan | "a statement / an utterance" (Hindi) | No programming language, but an enterprise voice-AI product already uses the name. | Runner-up |
| Plume | a quill pen | Already taken: `plume-lang` is an existing small programming language. | Rejected |

Why Lekh: it's short, easy to say in any accent, and means exactly what the language is
for: code you write the way you write a sentence. File extension: `.lekh`.

## 1. Philosophy

1. **It reads like English.** `let name be "Sushant"`, `say "Hello, {name}"`,
   `for each item in cart:`, `if age is at least 18:`. Most of the work is done by words,
   and there are very few symbols.
2. **Little punctuation.** No semicolons, braces or `==`. Blocks are shown by indentation
   (4 spaces) after a line ending in `:`. The only symbols are `+ - * / ( ) , :`, plus
   the optional `< > <= >=`.
3. **A small set of keywords** (54 reserved words), and only one way to do each thing.
4. **Safe like Rust, without Rust's learning curve.** Values are immutable by default. There
   is no null. Errors are ordinary values. Every value has one owner, and the borrow
   rules use three words, with no lifetimes.
5. **Errors teach.** Every error names the line, explains the problem in plain English and
   suggests a fix you can copy. It even recognises words from other languages
   (`print` → `say`, `else` → `otherwise`, `=` → `be`/`to`).
6. **Two safety nets.** A *checker* reads the whole program before it runs and catches most
   mistakes, such as use-after-move, changing something immutable, unknown names, missing
   `when` cases, wrong inputs, obvious type mix-ups and unchecked maybe values. The runtime
   catches the rest with the same friendly messages.

## 2. Syntax tour

### Variables: immutable by default
```
let name be "Sushant"              -- can never change
let changeable score be 0          -- opt in to change
change score to 10
increase score by 5                -- also: decrease score by 1
let age as number be 30            -- optional type annotation
```
Changing a plain `let` gives this error: *"You tried to change `name`, but it was created with plain
`let` on line 1, so it can never change. How to fix: `let changeable name be ...`"*.

### Types (inferred, and optional to write)
`number` (whole or decimal), `text`, `truth` (`true`/`false`), `list of T`, `map of K to V`,
`maybe T`, `result of T`, plus your own records and choices. Lekh infers each type from the
first value: a variable that starts as a number stays a number, and a list holds one kind of thing.
Annotations (`as number`) are checked if you write them.

### Text, printing, input
```
say "Hello, {name}! Next year you'll be {age + 1}."   -- {anything} is interpolated
let answer be ask "What's your name?"                  -- ask returns text
let n be answer as number                              -- gives ok 42 / problem "..."
```

### Tasks (functions)
```
to greet person:
    say "Hi {person}"

to add a as number, b as number gives number:
    give back a + b

greet with "Asha"                  -- `with` for inputs
say add with 2, 3
say square of 4                    -- `of` reads better for a single input
run show_menu                      -- a task with no inputs
```
Tasks can call themselves (recursion). `give back` returns a value.

### Decisions and loops
```
if age is at least 18:
    say "adult"
otherwise if age is at least 13:
    say "teen"
otherwise:
    say "child"

for each item in cart:              for each n from 1 to 10:
for each item and position in cart: repeat 3 times:
for each key and value in ages:     while count is less than 10:
stop       -- leave the loop        skip      -- go to the next round
```
Comparisons are words: `is`, `is not`, `is greater than`, `is less than`, `is at least`,
`is at most`, `contains`, `does not contain`, `starts with`, `ends with`, `is a Circle`.
Logic: `and`, `or`, `not`.

### Lists and maps (positions start at 1)
```
let changeable cart be list of "milk", "bread"      -- or: an empty list
add "eggs" to cart
remove "milk" from cart
say item 1 of cart
change item 1 of cart to "butter"

let changeable ages be map of "Asha" to 30, "Ravi" to 25    -- or: an empty map
change ages at "Sushant" to 31
let age be ages at "Ravi" or else 0        -- lookups give a maybe value
```

### Records (structs)
```
record Task:
    title as text
    done as truth

let changeable t be a Task with title "Buy milk", done false
change t's done to true             -- fields use 's, like English
say t's title
```

### Choices (enums) and pattern matching
```
choice Shape:
    Circle with radius as number
    Rectangle with width as number, height as number
    Dot

when shape:
    is Circle with r: give back 3.14 * r * r
    is Rectangle with w, h: give back w * h
    is Dot: give back 0
```
`when` must be **exhaustive**. If you leave out `Dot`, the checker says *"This `when` doesn't
say what to do for: Dot"*. `when` also matches plain values (`is "y" or "yes":`,
`is from 90 to 100:`), in which case it needs an `otherwise:`.

### No null: `maybe` and `result`
* A **maybe** value is `some x` or `nothing` (Rust's `Option`). Map lookups and `position`
  give back maybe values.
* A **result** is `ok x` or `problem "why"` (Rust's `Result`). Use it for things that can fail.
* You **can't use either one without handling it.** `age + 1` on a maybe is an error that
  points you to the fix.

Three easy ways to handle them:
```
let age be ages at "Ravi" or else 0          -- 1. fallback

when withdraw with lend account, 50:         -- 2. match
    is ok left: say "Left: {left}"
    is problem why: say "Sorry: {why}"

to parse_amount input as text gives result of number:
    let amount be try input as number        -- 3. `try`: if it's a problem, pass it up
    give back ok amount                      --    (like Rust's `?`)
```
`fail "message"` stops the program on purpose, like Rust's `panic!`.

### Modules
```
use "lib/mathtools"                 -- everything from lib/mathtools.lekh
use square, factorial from mathtools
```
A module shares its tasks, records, choices and unchangeable top-level values.

### Comments
`-- like this`, either on its own line or at the end of a line.

## 3. Memory safety: "one owner, three words"

Rust is safe because of ownership and borrowing, and hard to learn because of lifetimes, `&` vs
`&mut`, and moves that happen quietly. Lekh keeps the guarantees and simplifies the model:

| Rule | In plain words |
|---|---|
| **One owner** | Every list, map or record belongs to exactly one variable. When that variable's block ends, the value is cleaned up. No garbage collector is needed, the same as in Rust. |
| **Small values are copied** | Numbers, text and truths are always copied, so you never think about them. |
| **Passing = looking (default)** | `total of prices` lets the task *read* `prices`. You write nothing extra. The task can't change it or give it away (Rust's `&T`). |
| **`lend` = may change** | `add_tax with lend prices, 0.18`. The task's input is marked `changeable prices`. The caller's variable must be changeable too (Rust's `&mut T`). |
| **`give` = hand over** | `archive with give backup` moves it into the task. Using `backup` afterwards is an error (Rust's move). |
| **`let b be a` moves** | Big values move to the new name. Use `copy of a` if you want two. |
| **One changer or many readers** | `swap with lend xs, lend xs` is rejected, because a value can't be lent and used again in the same call. |
| **No changing what you're looping over** | `add x to xs` inside `for each x in xs` is rejected (Rust's iterator invalidation). |
| **No hidden shared state** | Tasks can't change top-level variables. Pass them in with `lend`. |

**Why there are no lifetimes:** in Lekh a borrow (looking or lending) only lasts for the
call or loop that created it, and a borrow can never be stored in a variable, list or record. A
reference can't outlive its owner, so there is never anything to annotate. This is the
"second-class references" idea used by research languages such as Hylo/Val. Taking a part
out of a bigger value (`item 1 of tasks`) and storing it gives you your own copy.

The errors explain the rules as they come up. For example: *"`cart` can't be used here because
it was given away on line 5 (moved into `basket`). Each list, map or record has exactly one owner
at a time. How to fix: give away a copy on line 5 instead: `copy of cart`"*.

Future (designed, not built): `at the same time:` blocks for concurrency. Values would have to be
`give`n to a parallel job, so data races couldn't happen, the same reasoning as Rust's `Send`.

## 4. Rust vs Lekh: the same program

Both programs below print the same thing (`examples/rust_compare.lekh`; the Rust version was
compiled and run with `rustc` to check it). The only difference is that Rust prints `12.00`
where Lekh prints `12`.

<table>
<tr><th>Rust (36 non-blank lines)</th><th>Lekh (22 non-blank lines)</th></tr>
<tr><td>

```rust
use std::collections::HashMap;

enum Shape {
    Circle { radius: f64 },
    Rect { width: f64, height: f64 },
}

fn area(shape: &Shape) -> f64 {
    match shape {
        Shape::Circle { radius } =>
            3.14159 * radius * radius,
        Shape::Rect { width, height } =>
            width * height,
    }
}

fn withdraw(balance: &mut f64, amount: f64)
        -> Result<f64, String> {
    if amount > *balance {
        return Err(format!(
          "not enough money: have {}, asked {}",
          balance, amount));
    }
    *balance -= amount;
    Ok(*balance)
}

fn main() {
    let shapes = vec![
        Shape::Circle { radius: 2.0 },
        Shape::Rect { width: 3.0, height: 4.0 },
    ];
    for shape in &shapes {
        println!("Area: {:.2}", area(shape));
    }
    let mut balance = 100.0;
    match withdraw(&mut balance, 30.0) {
        Ok(left) => println!("Left: {}", left),
        Err(why) => println!("Failed: {}", why),
    }
    let mut ages: HashMap<&str, i32> =
        HashMap::new();
    ages.insert("Asha", 30);
    let age = ages.get("Ravi")
        .copied().unwrap_or(0);
    println!("Ravi is {}", age);
}
```

</td><td>

```
choice Shape:
    Circle with radius as number
    Rect with width as number, height as number

to area shape as Shape gives number:
    when shape:
        is Circle with r: give back 3.14159 * r * r
        is Rect with w, h: give back w * h

to withdraw changeable balance as number,
            amount as number gives result of number:
    if amount is greater than balance:
        give back problem "not enough money: have {balance}, asked {amount}"
    decrease balance by amount
    give back ok balance

let shapes be list of Circle with radius 2, Rect with width 3, height 4
for each shape in shapes:
    say "Area: {round with area of shape, 2}"

let changeable balance be 100
when withdraw with lend balance, 30:
    is ok left: say "Left: {left}"
    is problem why: say "Failed: {why}"

let ages be map of "Asha" to 30
let age be ages at "Ravi" or else 0
say "Ravi is {age}"
```

</td></tr></table>

(The Lekh task header is split over two lines here only to fit the table. In the actual file it
is a single line, because Lekh only continues a line inside parentheses.)

| Rust concept | Lekh |
|---|---|
| `let x = 5;` / `let mut x = 5;` | `let x be 5` / `let changeable x be 5` |
| `x = 6;` / `x += 1;` | `change x to 6` / `increase x by 1` |
| `fn f(a: i32) -> i32 { ... }` | `to f a as number gives number:` |
| `&T` / `&mut T` / move | *(nothing)* / `lend` / `give` |
| `.clone()` | `copy of x` |
| `struct` / `enum` / `match` | `record` / `choice` / `when` |
| `Option<T>`: `Some(x)`, `None` | `maybe T`: `some x`, `nothing` |
| `Result<T,E>`: `Ok(x)`, `Err(e)`, `?` | `result of T`: `ok x`, `problem e`, `try` |
| `.unwrap_or(d)` | `or else d` |
| `panic!("...")` | `fail "..."` |
| `vec![1,2]`, `v[0]`, `v.push(x)` | `list of 1, 2`, `item 1 of v`, `add x to v` |
| `println!("{}", x)` | `say "{x}"` |
| `use crate::m::f;` | `use f from m` |

## 5. Grammar summary (informal)

```
statement := let [changeable] NAME [as TYPE] be EXPR
           | change TARGET to EXPR | increase/decrease TARGET [by EXPR]
           | add EXPR to TARGET | remove [item] EXPR from TARGET
           | say [EXPR] | give back [EXPR] | stop | skip | fail EXPR
           | if EXPR: BLOCK {otherwise if EXPR: BLOCK} [otherwise: BLOCK]
           | for each [changeable] NAME [and NAME] in EXPR: BLOCK
           | for each NAME from EXPR to EXPR: BLOCK
           | repeat EXPR times: BLOCK | while EXPR: BLOCK
           | when EXPR: (is PATTERN {or PATTERN}: BLOCK)+ [otherwise: BLOCK]
           | to NAME [PARAM {, PARAM}] [gives TYPE]: BLOCK
           | record NAME: (NAME [as TYPE])+
           | choice NAME: (NAME [with NAME [as TYPE] {, ...}])+
           | use NAME | use NAME {, NAME} from NAME
           | constant NAME be EXPR | share (to|let|constant|record|choice|ability) ...
           | let (NAME, NAME ...) be EXPR | for each (NAME, NAME) in EXPR: BLOCK
           | for each NAME from EXPR to EXPR [by EXPR] [at the same time]: BLOCK
           | to TYPE's NAME [PARAM {, PARAM}] [gives TYPE] [changes me]: BLOCK
           | ability NAME: (to NAME ... [gives TYPE] [: BLOCK])+  |  TYPE can ABILITY
           | record NAME [of T {and T}]: ...
           | at the end: BLOCK | at the same time: BLOCK
           | send EXPR to EXPR | close EXPR | wait EXPR seconds
           | test TEXT: BLOCK | expect EXPR [not] to (be EXPR | contain EXPR | be ok/problem/some/nothing)
           | EXPR                                  (a task or method call)
PARAM     := [changeable] NAME [as TYPE]
TARGET    := NAME {'s FIELD | at KEY} | item EXPR of TARGET
EXPR precedence, lowest first:
   if E then E otherwise E  <  or else  <  or  <  and  <  not  <  is / is greater than / contains ...
   <  + -  <  * / mod  <  - (negative), try  <  's field, at key, as type  <  values
values: 5  "text {x}"  true  nothing  some/ok/problem X  (EXPR)  list of A, B  map of K to V
        empty list/map  copy of X  ask "prompt"  run TASK  item N of X
        TASK with A, B   TASK of A   Type with field V, field V   NAME
        (A, B)  set of A, B  given x: EXPR  X's method with A  range from A to B [by C]
        keep/turn/count each X in E ...  find first X in E where C  any/every X in E where C
        sort each X in E by K [descending]  combine each X in E into ACC starting at V using E
        a new channel  receive from CH  start TASK with A  wait for JOB  take first/last from TARGET
```
Small rules that keep parsing unambiguous:
* `with` takes everything up to the end of the line (or the `:`). Use parentheses to mix calls,
  e.g. `if (add with 1, 2) is 3:`.
* `or else` applies to the whole call: `withdraw with lend a, 50 or else 0`.
* `list of ...` also takes everything up to the end of the line. Inside another call, write
  `join with (list of 1, 2), "-"`.
* `a` / `an` before `list`, `map`, `empty`, `copy` or a type name are optional, for readability.

* `try` binds tighter than `or else`: `try x or else y` means `(try x) or else y`. The type
  checker flags the confusing cases (e.g. `try` on a maybe inside a task that gives a result).
* `of` takes the single value right after it: `square of 3 + 1` is `(square of 3) + 1`.

## 6. Status (v0.2)

v0.1 was the core language: variables, lists, maps, records, choices, maybe/result and
ownership. v0.2 extends it towards a general-purpose language in four stages, all implemented
and tested (`python3 tests/run_tests.py`: 133 checks, covering 148 documentation samples):

* **Stage 1, core:** gradual static typing with inference; generics; closures (`given`) and
  higher-order tasks; methods and abilities (traits); groups (tuples); ranges with steps; guards
  in patterns; constants; `if ... then ... otherwise` values; big integers; custom error types
  with `try` propagation; `at the end` cleanup; English list operations.
* **Stage 2, standard library:** files and folders, JSON, dates, maths, random, regular
  expressions, environment and arguments, stdin, shell-free commands, HTTP GET/POST, custom
  sorting, sets, queues and stacks (127 built-in tasks in total).
* **Stage 3, concurrency and tooling:** `at the same time`, parallel `for each`, channels, jobs,
  with no shared mutable state; `share` (private by default), projects and `lekh new`;
  `test`/`expect` and `lekh test`; `lekh format`; REPL history, `:vars`, `:type`, `:load`, `:reset`.
* **Stage 4, performance:** `lekh build` translates checked programs to Python (section 9).

## 7. Feature coverage

Status key: **Done** = implemented and tested. **Partial** = works, with the limits noted.
**Designed** = specified here, not built. **Planned** = on the [roadmap](docs/roadmap.md).

| Feature | Lekh syntax | Status |
|---|---|---|
| Variables, immutable by default | `let x be 1`, `let changeable x be 1`, `change x to 2` | Done |
| Constants | `constant MAX be 10` | Done |
| Integers, decimals, big integers | `7 div 2`, `7 / 2`, `power with 2, 200` | Done |
| Text, interpolation, escapes | `"Hi {name}\n"`, `{{` | Done |
| Truth values, logic | `true`, `a and not b` | Done |
| Conditional expression | `if c then a otherwise b` | Done |
| If / else-if / else | `if ...:` `otherwise if ...:` `otherwise:` | Done |
| Pattern matching | `when x:` `is Circle with r if r is greater than 1:` | Done (exhaustive for choices, maybe, result) |
| Ranges in patterns | `is from 1 to 9` | Done |
| Loops | `repeat 3 times:`, `while c:`, `for each x in xs:` | Done |
| Counting loops with steps | `for each i from 10 to 0 by -2:` | Done |
| Break / continue | `stop`, `skip` | Done |
| Early return | `give back x`, `give back` | Done |
| Functions | `to area w as number, h as number gives number:` | Done |
| Calls | `f with a, b`, `f of a`, `run f` | Done |
| Closures / lambdas | `given x: x * 2`, multi-line `given x:` | Done (capture read-only copies) |
| Higher-order functions | `task of number gives number` inputs, `transform`, `select`, `reduce` | Done |
| English collection operations | `keep each`, `turn each`, `count each`, `find first`, `any`, `every`, `sort each ... by`, `combine each` | Done |
| Lists | `list of 1, 2`, `item 1 of xs`, `add`, `remove`, `remove item n` | Done |
| Maps | `map of "a" to 1`, `m at k` (maybe), `change m at k to v` | Done |
| Sets | `set of 1, 2`, `union`, `intersection`, `difference` | Done |
| Tuples | `(a, b)`, `let (a, b) be ...`, `for each (a, b) in ...` | Done |
| Queues and stacks | `take first from q`, `take last from s` | Done |
| Records (structs) | `record Point:` `x as number` | Done |
| Choices (tagged unions) | `choice Shape:` `Circle with radius as number` | Done |
| Methods | `to Point's shift dx as number changes me:` and `p's shift with 3` / `p's reset` | Done |
| Traits / interfaces | `ability Named:`, defaults, `Robot can Named`, ability as a type | Done |
| Generics | `to first_or xs as list of T, d as T gives T:`, `record Pair of A and B:` | Done (no bounds yet) |
| Generic bounds | `where T can Compare` | Designed |
| Operator / display abilities | built-in `Compare`, `Show` | Designed |
| Static typing | type labels checked before running, inference from literals and labels | Partial (gradual: unlabelled code is checked at run time) |
| Type tests and conversion | `x is a number`, `t as number` (result), `xs as set` | Done |
| No null | `maybe T`, `some x`, `nothing`, `or else` | Done |
| Errors as values | `result of T or E`, `ok x`, `problem e` | Done |
| Error propagation | `try x` | Done |
| Custom error types | `choice BankError:` + `problem (NotEnough with 5)` | Done |
| Cleanup (defer / finally) | `at the end:` | Done |
| Panics | `fail "message"` | Done |
| Ownership and moves | `let b be a` moves; use-after-move is an error | Done |
| Borrowing | look (default), `lend`, `give`, `copy of` | Done |
| No mutation while iterating | (automatic) | Done |
| Concurrency | `at the same time:`, `for each ... at the same time:` | Done (threads; I/O-bound speed-ups) |
| Channels | `a new channel`, `send`, `receive from`, `close` | Done |
| Background jobs | `start f with x`, `wait for job` | Done |
| Data-race freedom | outside values read-only in parallel code; jobs can't `lend` | Done |
| Modules and visibility | `use f from "file"`, `share to ...` | Done |
| Packages / projects | `project.json`, `lekh new`, `src/`, `lib/` | Done (local only) |
| Package manager | `lekh add <url>` | Planned |
| Unit tests | `test "name":`, `expect ... to be ...`, `lekh test` | Done |
| Formatter | `lekh format [--check]` | Done |
| REPL | `lekh repl` with history and `:vars`, `:type`, `:load`, `:reset` | Done |
| Files and folders | `read_file`, `write_file`, `read_lines`, `list_folder`, ... | Done |
| JSON | `to_json`, `from_json`, `json_get` | Done |
| Dates and times | `now`, `parse_date`, `format_time`, `add_days`, ... | Done (local time zone only) |
| Maths and random | `sqrt`, `sine`, `log`, `random`, `seed_random`, ... | Done |
| Regular expressions | `matches`, `find_all`, `find_groups`, `replace_pattern`, ... | Done |
| Arguments, environment, stdin | `arguments`, `environment of "HOME"`, `read_all_input` | Done |
| Running commands | `run_command of "git status"` | Done (no shell, 60 s timeout) |
| HTTP client | `http_get`, `http_post` | Done (http/https only, 15 s timeout) |
| HTTP server | `serve on port 8080:` | Planned |
| Database | `open_database`, parameterised `query` | Planned |
| GUI / terminal UI | | Planned |
| Iterators / generators | | Designed (records with a `next` task) |
| Faster execution | `lekh build app.lekh` (to Python) | Done (17x faster than the interpreter) |
| Native compiler | Lekh → Rust / C / WebAssembly | Planned |
| Calling Python libraries | `use python "statistics"` | Planned |

## 8. How it's built

```
source.lekh
   │  lexer (indentation → INDENT/DEDENT, text interpolation parts)
   ▼
 Parser ──► syntax tree (Node objects)
   │
   ├─► Checker      names, immutability, ownership (moves, borrows, loops, parallel blocks),
   │                exhaustive `when`, private names, ability promises
   ├─► TypeChecker  gradual static types: labels, inference, generics, built-in signatures
   │
   ├─► Interp       tree-walking interpreter: `lekh run`, `lekh test`, the REPL
   └─► build.py     translator to Python, using rt.py (the same runtime classes): `lekh build`
```

All of it lives in `lekhlib/`: `core.py` (lexer, parser, Checker, interpreter, values),
`typecheck.py`, `stdlib.py` (built-in tasks), `build.py` + `rt.py`, `formatter.py`, `repl.py`
and `cli.py`. There are no dependencies beyond Python 3.8+.

Run-time values: numbers are Python `int`/`float` (so integers are unbounded), text is `str`,
and lists, maps and sets are Lekh's own `PList`/`PMap`/`PSet` (insertion-ordered, with
ownership bookkeeping). Records and variants hold their fields in dictionaries. Concurrency
uses threads with per-thread interpreter state, and every value crossing into a job or
channel is deep-copied or moved.

## 9. The performance path: transpiler vs bytecode VM

The tree-walking interpreter is simple and gives the best error messages, but it's slow:
about 5.2 s on `benchmarks/fib.lekh`. Two standard ways to speed it up were considered:

| | Bytecode VM (in Python) | Translate to Python (chosen) |
|---|---|---|
| Speed-up | 2-4x typical for a VM written in Python, since each instruction is still Python code | **17.1x measured** (5.16 s → 0.30 s); CPython's own VM runs the code |
| Work needed | a compiler to bytecode, plus an instruction loop and frames | one code generator; reuses the runtime classes and built-ins |
| Error messages | needs a line table | each operation carries its source location (`Loc`), so the same friendly messages appear |
| Safety checks | all of them, at run time | static checks run before building; run-time checks stay in `rt.py` helpers |
| Portability | needs only Python | needs only Python plus the `lekhlib` folder |
| Path to native code | a VM could later be rewritten in C/Rust | the same design (typed tree → source) carries over to emitting Rust or C |

The translator renames variables uniquely, turns top-level values into module globals, returns
changed `lend` inputs as tuples that are written back at the call site, compiles `try` to an
exception, `at the end` to `try/finally`, and runs on a thread with a large stack (deep
recursion works). When the type checker knows a value is a number or text it emits plain
Python operators; otherwise it calls a checking helper. The test suite runs every example and
feature program both ways and requires identical output.

**Limits of `lekh build` today:** the output imports `lekhlib` (it's not standalone); `test`
blocks are left out; a few rare constructs report "not supported yet". Built code is about 15x
slower than hand-written Python (0.30 s vs 0.02 s) because each operation still goes through
Lekh's safety checks. A native backend is on the [roadmap](docs/roadmap.md).
