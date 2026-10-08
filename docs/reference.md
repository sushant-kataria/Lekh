# Lekh reference

Every keyword, type, operator and built-in task in Lekh 0.2, each with an
example you can run. All samples are checked by the test suite
(`python3 tools/docs_check.py`), and the outputs shown are real.

New to Lekh? Start with [the guide](guide/README.md). For a one-page summary,
see [the cheat sheet](cheatsheet.md).

**Contents:**
* [Program layout](#program-layout)
* [Types](#types)
* [Variables](#variables)
* [Operators](#operators)
* [Text](#text-values)
* [Control flow](#control-flow)
* [Tasks](#tasks)
* [Collections](#collections)
* [List operations in English](#list-operations-in-english)
* [Records, choices and methods](#records-choices-and-methods)
* [Patterns (`when`)](#patterns)
* [Maybe and result](#maybe-and-result)
* [Abilities](#abilities)
* [Generics](#generics)
* [Ownership words](#ownership-words)
* [Concurrency](#concurrency)
* [Modules](#modules)
* [Tests](#tests)
* [Built-in tasks](#built-in-tasks)
* [Command line](#command-line)
* [Keyword index](#keyword-index)

---

## Program layout

* One statement per line. A block (the body of an `if`, a loop, a task...)
  is the indented lines after a line ending in `:`. Use 4 spaces.
* A block of one statement may go on the same line: `if x is 0: say "zero"`.
* `--` starts a comment that runs to the end of the line.
* Names use letters, digits and `_`. Records, choices and abilities start
  with a capital letter by convention; single capital letters (`T`, `A`) are
  type variables in generics.
* The program runs from top to bottom. Tasks and types can be used before
  the line that defines them.

```lekh
-- a comment
let x be 3   -- another comment
if x is 3: say "one-line block"
if x is greater than 1:
    say "an indented"
    say "block"
```

```output
one-line block
an indented
block
```

## Types

| Type | Write it as | Example values |
|---|---|---|
| number | `number` (also `integer`, `decimal`) | `42`, `-3.5`, `10000000000000000000000` |
| text | `text` | `"hi"`, `""` |
| truth | `truth` | `true`, `false` |
| list | `list of T` | `list of 1, 2`, `empty list` |
| map | `map of K to V` | `map of "a" to 1`, `empty map` |
| set | `set of T` | `set of 1, 2`, `empty set` |
| group | `(T1, T2)` | `(1, "one")` |
| maybe | `maybe T` | `some 3`, `nothing` |
| result | `result of T` or `result of T or E` | `ok 3`, `problem "bad"` |
| task | `task of A gives R` | `given x: x + 1`, a task's name |
| channel | `channel` | `a new channel` |
| job | `job` | `start f with x` |
| record / choice | its name | `Point with x 1, y 2`, `Circle with radius 2` |
| ability | its name | any value whose type `can` it |
| anything | `anything` | any value (checked while running) |
| type variable | `T`, `A`, `B`... | in generic tasks and records |

Whole numbers have no size limit. A decimal like `2.0` prints as `2`.
`type_of` tells you the type of a value while the program runs, and
`is a <type>` tests it:

```lekh
say type_of of 42
say type_of of "hi"
say type_of of (list of 1)
say type_of of (some 1)
say 42 is a number
say "42" is a number
say power with 3, 50
```

```output
integer
text
list
maybe
true
false
717897987691852588770249
```

## Variables

| Statement | Meaning |
|---|---|
| `let x be value` | name a value that never changes |
| `let changeable x be value` | a name whose value can change |
| `let x as type be value` | with a type label (checked) |
| `constant X be value` | a fixed setting (cannot change) |
| `let (a, b) be group` | unpack a group |
| `change x to value` | give a changeable name a new value |
| `increase x by n` / `decrease x by n` | add / subtract |
| `change x's field to v`, `change item 2 of xs to v`, `change m at k to v` | change part of a value |

```lekh
constant LIMIT be 3
let name be "Asha"
let changeable count be 0
increase count by 5
decrease count by 1
change count to count * 10
let scores as list of number be list of 70, 85
let (low, high) be (smallest of scores, largest of scores)
say "{name} {count} {LIMIT} {low}-{high}"
```

```output
Asha 40 3 70-85
```

## Operators

From loosest to tightest binding:

| Operator | Meaning | Example |
|---|---|---|
| `if c then a otherwise b` | pick a value | `if n is 1 then "item" otherwise "items"` |
| `a or b` | either is true | `x is 0 or y is 0` |
| `a and b` | both are true | `age is at least 18 and member` |
| `not a` | the opposite | `not finished` |
| `a is b`, `a is not b` | equal / not equal (compares whole lists, records...) | `colour is "red"` |
| `is greater than`, `is less than`, `is at least`, `is at most` | ordering (numbers or text) | `n is at least 10` |
| `is between a and b` | `a <= x <= b` | `age is between 13 and 19` |
| `contains`, `does not contain` | in a list, set, map's keys or text | `names contains "Bo"` |
| `starts with`, `ends with` | text | `file ends with ".csv"` |
| `is nothing`, `is some`, `is ok`, `is problem` | test a maybe or result | `(m at k) is nothing` |
| `is a T` | type test | `x is a number` |
| `a + b`, `a - b` | add, subtract; `+` also joins text and lists | `"a" + "b"` |
| `a * b`, `a / b`, `a div b`, `a mod b` | multiply, divide, whole division, remainder | `7 div 2` |
| `-a` | negative | `-x` |
| `x or else y` | fallback for maybe/result | `(m at k) or else 0` |
| `try x` | unwrap or pass the problem up | `try parse of t` |
| `x as T` | convert | `"42" as number` |
| `x's field`, `x at key`, `item n of xs` | parts of values | `p's name` |
| `(` `)` | grouping | `(a + b) * c` |

```lekh
let n be 7
say n + 3 * 2
say (n + 3) * 2
say n / 2
say n div 2
say n mod 2
say -n
say "con" + "cat"
say (list of 1) + (list of 2, 3)
say n is between 1 and 10 and not (n is 5)
say "lekh.py" ends with ".py" or "lekh.py" starts with "x"
say (list of 1, 2) is (list of 1, 2)
say "apple" is less than "banana"
say "team" does not contain "i"
say if n mod 2 is 0 then "even" otherwise "odd"
```

```output
13
20
3.5
3
1
-7
concat
[1, 2, 3]
true
true
true
true
true
odd
```

**`of` takes the value right after it.** `square of 3 + 1` means
`(square of 3) + 1`; write `square of (3 + 1)` when you mean that. A `with`
call takes everything up to the end of the line, separated by commas, so wrap a
call in parentheses when it's one input among several:
`join with (list of "a", "b"), "-"`.

Mixing types, such as `"a" + 1`, is an error (use `{}` inside text, or
`as text`). Dividing by zero stops the program with a clear message.

### Conversions with `as`

| Conversion | Gives |
|---|---|
| `t as number`, `t as integer`, `t as decimal` | a result (text might not be a number) |
| `n as integer` | a result with the decimal part dropped |
| `x as text` | text |
| `xs as list`, `xs as set` | a list or set (from a list, set, map keys or text letters) |

```lekh
say ("12.5" as number) or else 0
say ("12.5" as integer) or else 0
say ("twelve" as number) or else -1
say 99 as text
say (set of 3, 1) as list
say (list of 1, 1, 2) as set
say "abc" as list
```

```output
12.5
12
-1
99
[1, 3]
set of 1, 2
["a", "b", "c"]
```

## Text values

* Double quotes: `"hello"`. Escapes: `\"` quote, `\\` backslash, `\n` new line, `\t` tab.
* `{expression}` inside text inserts a value: `"total {a + b}"`.
* `{{` makes a literal `{`. Braces holding only digits (`{4}`, `{2,5}`) are
  left as they are, so patterns like `[0-9]{4}` just work.
* Lekh won't print a maybe or result directly: unwrap it first.

```lekh
let item be "chai"
let price be 15
say "One {item} costs ₹{price}. Two cost ₹{price * 2}."
say "She said \"hi\"\tand left."
say "literal {{braces}} and a pattern [0-9]{4}"
say "line one\nline two"
```

```output
One chai costs ₹15. Two cost ₹30.
She said "hi"	and left.
literal {braces} and a pattern [0-9]{4}
line one
line two
```

See [text tasks](#text) for `uppercase`, `split`, `replace` and the rest.

## Control flow

| Statement | Meaning |
|---|---|
| `if c:` ... `otherwise if c:` ... `otherwise:` | choose a block |
| `when x:` with `is pattern:` cases and `otherwise:` | match a value ([patterns](#patterns)) |
| `repeat n times:` | run a block n times |
| `while c:` | run while c is true |
| `for each x in xs:` | each item of a list, set, map (keys), channel or text |
| `for each x and position in xs:` | with its position (from 1) |
| `for each key and value in m:` | each entry of a map |
| `for each (a, b) in pairs:` | unpack groups |
| `for each changeable x in xs:` | change items in place |
| `for each i from a to b:` / `... by step:` | count (`b` included) |
| `stop` | leave the loop |
| `skip` | go to the next round |
| `give back value` / `give back` | leave the task |
| `at the end:` | run a block when the task finishes ([cleanup](#cleanup-at-the-end)) |
| `fail "message"` | stop the program with an error |

```lekh
let changeable total be 0
for each i from 1 to 10:
    if i is 3: skip
    if i is greater than 6: stop
    increase total by i
say total
let changeable n be 3
while n is greater than 0:
    decrease n by 1
repeat 2 times:
    say "again"
let changeable xs be list of 1, 2
for each changeable x in xs:
    change x to x * 10
say xs
for each word and pos in list of "a", "b":
    say "{pos}:{word}"
for each k and v in map of "x" to 1:
    say "{k}={v}"
for each i from 6 to 0 by -3:
    say i
```

```output
18
again
again
[10, 20]
1:a
2:b
x=1
6
3
0
```

## Tasks

```lekh
-- inputs can have type labels; `gives` labels the answer
to area w as number, h as number gives number:
    give back w * h

-- inputs without labels accept anything (checked while running)
to describe thing:
    say "it is {thing}"

-- a task with no inputs is called with `run`
to banner gives text:
    give back "== Lekh =="

say area with 3, 4
describe of "blue"
say run banner
```

```output
12
it is blue
== Lekh ==
```

| Form | Meaning |
|---|---|
| `to name a, b:` | define a task (a function) |
| `to name a as T gives R:` | with type labels |
| `to name changeable a as T:` | the task may change `a` (call with `lend`) |
| `name with x, y` | call with inputs |
| `name of x` | call with one input |
| `run name` | call with no inputs |
| `give back v` | answer and leave |
| `given x: expr` / `given a, b: expr` | an unnamed task (lambda) |
| `given x:` + indented block | a longer unnamed task |
| `task of A gives R` | the type of a task |
| `share to ...` | make it usable from other files ([modules](#modules)) |

Unnamed tasks take a read-only copy of the outside values they use:

```lekh
let rate be 2
let scale be given x: x * rate
let classify be given n:
    if n is greater than 5:
        give back "big"
    give back "small"
say scale with 21
say classify with 9
to apply f as task of number gives number, x as number gives number:
    give back f with x
say apply with scale, 5
```

```output
42
big
10
```

## Collections

### Lists

| Form | Meaning |
|---|---|
| `list of a, b, c` / `empty list` | make a list |
| `item n of xs` | the item at position n (from 1) |
| `first of xs`, `last of xs` | first / last item (error if empty) |
| `add x to xs` | add at the end |
| `remove x from xs` | remove the first matching item |
| `remove item n from xs` | remove by position |
| `change item n of xs to v` | replace an item |
| `take first from xs` / `take last from xs` | remove and give the front / back item, as a maybe |
| `xs contains x` | is it in the list? |
| `range from a to b [by s]` | a list of numbers |

```lekh
let changeable xs be list of "a", "b", "c", "d"
add "e" to xs
remove "b" from xs
remove item 1 from xs
change item 1 of xs to "C"
say xs
say "{item 2 of xs} {first of xs} {last of xs} {length of xs}"
say (take first from xs) or else "-"
say (take last from xs) or else "-"
say xs
say range from 0 to 10 by 5
```

```output
["C", "d", "e"]
d C e 3
C
e
["d"]
[0, 5, 10]
```

### Maps

| Form | Meaning |
|---|---|
| `map of k to v, ...` / `empty map` | make a map |
| `m at k` | the value for key k, as a maybe |
| `change m at k to v` | set a value (adds the key if needed) |
| `remove k from m` | remove a key |
| `m contains k` | is the key there? |
| `keys of m`, `values of m`, `pairs of m` | lists of keys, values, (key, value) groups |

```lekh
let changeable m be map of "a" to 1
change m at "b" to 2
change m at "a" to 10
say m
say (m at "a") or else 0
say (m at "z") or else 0
remove "a" from m
say "{keys of m} {values of m} {pairs of m} {m contains "b"}"
```

```output
{"a": 10, "b": 2}
10
0
["b"] [2] [("b", 2)] true
```

### Sets

`set of a, b` / `empty set`, `add x to s`, `remove x from s`, `s contains x`,
plus `union`, `intersection`, `difference`, `is_subset`. Sets print sorted.

```lekh
let changeable s be set of 3, 1, 3
add 2 to s
remove 3 from s
say s
say s contains 2
say is_subset with (set of 1), s
```

```output
set of 1, 2
true
true
```

### Groups

`(a, b, ...)` makes a group (a tuple); `let (x, y) be g` and
`for each (x, y) in gs` unpack them. A group's parts can't be changed.

```lekh
let g be ("Asha", 31)
let (who, age) be g
say "{who} is {age}"
say g
```

```output
Asha is 31
("Asha", 31)
```

## List operations in English

These work on lists, sets and ranges. The name after `each` stands for each
item in turn.

| Form | Gives |
|---|---|
| `keep each x in xs where cond` | the items where cond is true |
| `turn each x in xs into expr` | a new list of expr for each item |
| `count each x in xs where cond` | how many match |
| `find first x in xs where cond` | the first match, as a maybe |
| `any x in xs where cond` | true if at least one matches |
| `every x in xs where cond` | true if all match |
| `sort each x in xs by key [descending]` | sorted by a key |
| `combine each x in xs into acc starting at v using expr` | fold into one value |

```lekh
let xs be list of 4, 9, 2, 7
say keep each x in xs where x is greater than 3
say turn each x in xs into x * x
say count each x in xs where x mod 2 is 1
say (find first x in xs where x is greater than 5) or else 0
say any x in xs where x is 2
say every x in xs where x is less than 10
say sort each x in xs by x descending
say sort each w in (list of "kiwi", "fig", "banana") by length of w
say combine each x in xs into acc starting at 1 using acc * x
```

```output
[4, 9, 7]
[16, 81, 4, 49]
2
9
true
true
[9, 7, 4, 2]
["fig", "kiwi", "banana"]
504
```

## Records, choices and methods

```lekh
record Point:
    x as number
    y as number

-- a method: `me` is the record, `my field` reads a field
to Point's distance_to other as Point gives number:
    let dx be my x - other's x
    let dy be my y - other's y
    give back sqrt of (dx * dx + dy * dy)

-- a method that changes its record says `changes me`
to Point's shift by as number changes me:
    increase my x by by

choice Weather:
    Sunny
    Rainy with mm as number

let changeable p be Point with x 0, y 0
p's shift with 3
say p
say p's distance_to with (Point with x 3, y 4)
say p's distance_to of (Point with x 0, y 4)
let today be Rainy with mm 12
when today:
    is Sunny: say "sunny"
    is Rainy with mm: say "rain: {mm} mm"
```

```output
Point(x: 3, y: 0)
4
5
rain: 12 mm
```

| Form | Meaning |
|---|---|
| `record Name:` + `field as type` lines | define a record |
| `Name with field v, field v` | make one (every field is required) |
| `x's field` | read a field |
| `change x's field to v` | change a field (x must be changeable) |
| `choice Name:` + one kind per line, `Kind with field as type, ...` | define a choice |
| `to Type's name inputs gives T:` | define a method |
| `x's name with a, b` / `x's name of a` / `x's name` | call a method |
| `changes me` | the method may change its record |
| `me`, `my field` | inside a method |

## Patterns

`when value:` tries each `is` case in order. A case can be followed by
`if condition` (a guard). Lekh checks that choices, maybes and results are
fully handled.

| Pattern | Matches |
|---|---|
| `is 3`, `is "yes"`, `is true` | that exact value |
| `is "a" or "b"` | any of several values |
| `is from 1 to 9` | a number in a range |
| `is name` | anything, and names it |
| `is Kind` / `is Kind with a, b` | a choice kind, naming its fields in order |
| `is Kind with "x", n` | a kind whose first field is "x" |
| `is some v` / `is nothing` | a maybe |
| `is ok v` / `is problem why` | a result |
| `is problem (Kind with n)` | a result whose problem is a choice kind |
| `is (a, b)` / `is (0, y)` | a group |
| `is pattern if condition` | only when the condition is true |
| `otherwise:` | everything else |

```lekh
choice Msg:
    Text with body as text
    Ping

for each n in list of 0, 5, 50, 51:
    when n:
        is 0: say "zero"
        is from 1 to 9: say "digit"
        is m if m mod 2 is 0: say "even {m}"
        otherwise: say "something else"
for each word in list of "hi", "bye":
    when word:
        is "hi" or "hello": say "greeting"
        is other: say "not a greeting: {other}"
for each m in list of (some 3), nothing:
    when m:
        is some v: say "some {v}"
        is nothing: say "nothing"
for each r in list of (ok 1), (problem "x"):
    when r:
        is ok v: say "ok {v}"
        is problem why: say "problem {why}"
when (2, 0):
    is (0, 0): say "origin"
    is (x, 0): say "on the x axis at {x}"
    otherwise: say "elsewhere"
for each msg in list of (Text with body "yo"), Ping:
    when msg:
        is Text with b: say "text {b}"
        is Ping: say "ping"
```

```output
zero
digit
even 50
something else
greeting
not a greeting: bye
some 3
nothing
ok 1
problem x
on the x axis at 2
text yo
ping
```

## Maybe and result

| Form | Meaning |
|---|---|
| `some v`, `nothing` | a maybe |
| `ok v`, `problem why` | a result (`why` is often text or a choice) |
| `maybe T` | type of a maybe |
| `result of T` / `result of T or E` | type of a result (problem type E, text by default) |
| `x or else fallback` | the value inside, or the fallback |
| `try x` | the value inside, or leave this task passing the nothing/problem up |
| `x is nothing`, `x is some`, `x is ok`, `x is problem` | tests |

```lekh
to half n as number gives result of number or text:
    if n mod 2 is 1: give back problem "{n} is odd"
    give back ok n / 2

to quarter n as number gives result of number or text:
    let h be try half of n
    give back half of h

say (quarter of 12) or else -1
say (quarter of 6) or else -1
say (quarter of 6) is problem
when quarter of 10:
    is ok v: say v
    is problem why: say "no: {why}"
```

```output
3
-1
true
no: 5 is odd
```

### Cleanup: `at the end`

`at the end:` inside a task runs its block when the task finishes, however
it finishes. Several `at the end` blocks run last-first.

```lekh
to job gives number:
    at the end:
        say "cleanup 1"
    at the end:
        say "cleanup 2"
    say "working"
    give back 1

say run job
```

```output
working
cleanup 2
cleanup 1
1
```

### `fail`

`fail "message"` stops the program with an error message. Use it for
situations that should be impossible.

```lekh error
fail "this should never happen"
```

```output

-- Lekh: The program stopped on purpose ------------------------------
In sample_19.lekh, line 1:

    1 | fail "this should never happen"

this should never happen

How to fix:
    This came from a `fail` line in the program. Handle the situation before it, or change the message.
```

## Abilities

```lekh
ability Greeter:
    to name gives text                  -- must be written by each type
    to greet gives text:                -- has a default
        give back "Hello from {me's name}"

record Bot:
    id as number

to Bot's name gives text:
    give back "bot-{my id}"

Bot can Greeter

to welcome g as Greeter:
    say g's greet

welcome of (Bot with id 7)
```

```output
Hello from bot-7
```

| Form | Meaning |
|---|---|
| `ability Name:` + task signatures | define an ability |
| a signature with a block | a default that types get for free |
| `Type can Ability` | promise that Type has the ability (checked) |
| an ability name as a type | any value whose type has the ability |

## Generics

A single capital letter is a type variable: it can be any type, but must be
the same type everywhere it appears in one call.

```lekh
to last_or xs as list of T, fallback as T gives T:
    if length of xs is 0: give back fallback
    give back last of xs

record Box of T:
    content as T

record Pair of A and B:
    left as A
    right as B

say last_or with (list of "a", "b"), "-"
let b be Box with content 5
let p be Pair with left "x", right true
say b
say p
```

```output
b
Box(content: 5)
Pair(left: "x", right: true)
```

## Ownership words

| Word | Meaning |
|---|---|
| `let b be a` | moves a list/map/set/record from `a` to `b` (`a` is gone) |
| `copy of a` | a deep copy (both stay usable) |
| `f with a` | the task may only look at `a` |
| `f with lend a` | the task may change `a` (a must be changeable, the input marked `changeable`) |
| `f with give a` | hand `a` over; you can't use it afterwards |
| `changeable` | on a variable or a task input: it may change |

```lekh
to grow changeable xs as list of number:
    add 0 to xs

to consume xs as list of number gives number:
    give back length of xs

let changeable a be list of 1, 2
let backup be copy of a
grow with lend a
say a
say consume with give a
say backup
```

```output
[1, 2, 0]
3
[1, 2]
```

The full rules, with the errors they prevent, are in [safety.md](safety.md).

## Concurrency

| Form | Meaning |
|---|---|
| `at the same time:` + lines | run each line side by side; wait for all |
| `for each x in xs at the same time:` | run every round side by side |
| `a new channel` | make a channel |
| `send v to ch` | put a value in (it moves) |
| `receive from ch` | take the next value, as a maybe (waits if needed) |
| `close ch` | no more values; `for each x in ch` then ends |
| `start f with x` / `start f of x` | run a task in the background, giving a job |
| `wait for job` / `wait for jobs` | its answer / a list of answers |
| `wait 0.5 seconds` | pause |

Code running at the same time may read outside values but never change or
give them away; jobs get copies of their inputs and can't `lend`.

```lekh
to cube n as number gives number:
    give back n * n * n

let ch be a new channel
at the same time:
    send 1 to ch
    send 2 to ch
close ch
let changeable got be empty list
for each v in ch:
    add v to got
say sorted of got
let out be a new channel
for each n in list of 1, 2, 3 at the same time:
    send cube of n to out
close out
let changeable cubes be empty list
for each c in out:
    add c to cubes
say sorted of cubes
let j be start cube of 4
wait 0.01 seconds
say wait for j
say wait for (list of (start cube of 1), (start cube of 2))
let inbox be a new channel
send "hi" to inbox
say (receive from inbox) or else "-"
```

```output
[1, 2]
[1, 8, 27]
64
[1, 8]
hi
```

## Modules

| Form | Meaning |
|---|---|
| `share to ...`, `share let ...`, `share constant ...`, `share record ...`, `share choice ...`, `share ability ...` | make it usable from other files |
| `use "file"` | bring in everything `file.lekh` shares |
| `use a, b from "file"` | bring in only some names |

Lekh looks for `file.lekh` next to the current file, then in the project's
`src/` and `lib/` folders. Everything not marked `share` is private.

```lekh file=geometry.lekh
share constant UNIT be "cm"

share record Square:
    side as number

share to area s as Square gives number:
    give back s's side * s's side
```

```lekh
use area, Square, UNIT from "geometry"
say "{area of (Square with side 3)} square {UNIT}"
```

```output
9 square cm
```

## Tests

| Form | Meaning |
|---|---|
| `test "name":` + block | a test, run by `lekh test` (skipped by `lekh run`) |
| `expect a to be b` | equal |
| `expect a not to be b` | not equal |
| `expect xs to contain x` | contains (lists, sets, maps, text) |
| `expect x to be ok` / `problem` / `some` / `nothing` | test a result or maybe |

```lekh test
test "maths":
    expect 2 + 2 to be 4
    expect 2 + 2 not to be 5

test "collections and results":
    expect list of 1, 2 to contain 2
    expect "lekh" to contain "ek"
    expect ("x" as number) to be problem
    expect (map of "a" to 1) at "a" to be some
```

```output
sample_26.lekh
  PASS  maths
  PASS  collections and results

2 tests, 2 passed, 0 failed
```

## Built-in tasks

Call them like any task: `name of x` for one input, `name with a, b` for
several, or `run name`/plain `name` for none (`now`, `today`, `pi`,
`arguments`...). Tasks that can fail give back a result; tasks that might
find nothing give back a maybe.

### Text

| Task | Example and meaning |
|---|---|
| `length` | `length of cart` |
| `uppercase` | `uppercase of name` |
| `lowercase` | `lowercase of name` |
| `capitalized` | `capitalized of name` |
| `title_case` | `title_case of "hello world"` → "Hello World" |
| `trimmed` | `trimmed of answer` |
| `trim_start` | `trim_start of "  hi"` → "hi" |
| `trim_end` | `trim_end of "hi  "` → "hi" |
| `split` | `split with line, ","` |
| `join` | `join with names, ", "` |
| `replace` | `replace with text, "old", "new"` |
| `letters` | `letters of word` |
| `words` | `words of sentence` |
| `lines` | `lines of text` |
| `slice` | `slice with "abcdef", 2, 4` → "bcd" (positions start at 1, both ends included) |
| `pad_left` | `pad_left with "7", 3, "0"` → "007" |
| `pad_right` | `pad_right with "name", 10` → "name  " |
| `centered` | `centered with "hi", 6, "*"` → "**hi**" |
| `repeat_text` | `repeat_text with "-", 10` → "----------" |
| `count_of` | `count_of with "banana", "a"` → 3 (also works on lists) |
| `is_number` | `is_number of "42"` → true |
| `is_blank` | `is_blank of "   "` → true |
| `letter_code` | `letter_code of "A"` → 65 |
| `letter_from_code` | `letter_from_code of 65` → "A" |
| `type_of` | `type_of of 42` → "number" |

```lekh
let s be "  hello lekh world  "
say length of s
say uppercase of (trimmed of s)
say lowercase of "LeKh"
say capitalized of "asha"
say title_case of "hello lekh world"
say "[{trim_start of s}]"
say "[{trim_end of s}]"
say split with "a-b-c", "-"
say join with (list of "x", "y", "z"), "/"
say replace with "1,000,000", ",", ""
say letters of "abc"
say words of "  two   words "
say lines of "first\nsecond"
say slice with "language", 3, 5
say pad_left with "42", 6, "0"
say "[{pad_right with "ab", 5}]"
say centered with "hi", 8, "*"
say repeat_text with "ab", 3
say count_of with "mississippi", "ss"
say is_number of "3.14"
say is_blank of " \t "
say letter_code of "a"
say letter_from_code of 97
```

```output
20
HELLO LEKH WORLD
lekh
Asha
Hello Lekh World
[hello lekh world  ]
[  hello lekh world]
["a", "b", "c"]
x/y/z
1000000
["a", "b", "c"]
["two", "words"]
["first", "second"]
ngu
000042
[ab   ]
***hi***
ababab
2
true
true
97
a
```

### Numbers and maths

| Task | Example and meaning |
|---|---|
| `absolute` | `absolute of -5` |
| `round` | `round of 3.7   or   round with price, 2` |
| `sqrt` | `sqrt of 16` |
| `power` | `power with 2, 10` → 1024 (whole numbers can be as big as you like) |
| `floor` | `floor of 7.9` → 7 |
| `ceiling` | `ceiling of 7.1` → 8 |
| `whole` | `whole of 7.9` → 7 (drops the decimal part) |
| `is_whole` | `is_whole of 4.0` → true |
| `smaller` | `smaller with 3, 8` → 3 |
| `larger` | `larger with 3, 8` → 8 |
| `clamp` | `clamp with 15, 0, 10` → 10 |
| `sign` | `sign of -4` → -1 |
| `pi` | `pi` → 3.141592653589793 |
| `sine` | `sine of (pi / 2)` → 1 (angles in radians) |
| `cosine` | `cosine of 0` → 1 |
| `tangent` | `tangent of 0` → 0 |
| `log` | `log of 10` → 2.302585 (natural log) |
| `log10` | `log10 of 1000` → 3 |
| `exp` | `exp of 1` → 2.718281828 |
| `radians` | `radians of 180` → 3.14159 |
| `degrees` | `degrees of pi` → 180 |
| `hex` | `hex of 255` → "ff" |
| `binary` | `binary of 5` → "101" |
| `format_number` | `format_number with 3.14159, 2` → "3.14" |
| `with_commas` | `with_commas of 1234567.5` → "1,234,567.5" (with_commas with x, 2 fixes the decimals) |
| `average` | `average of (list of 2, 4, 9)` → 5 |
| `sum` | `sum of prices` |
| `largest` | `largest of scores` |
| `smallest` | `smallest of scores` |

```lekh
say absolute of -5
say round of 2.5
say round with 3.14159, 3
say sqrt of 2
say power with 2, 64
say floor of -2.5
say ceiling of 2.1
say whole of -2.7
say is_whole of 3.0
say smaller with 3, 8
say larger with 3, 8
say clamp with -4, 0, 10
say sign of -9
say round with pi, 5
say sine of 0
say cosine of 0
say round with (tangent of (pi / 4)), 6
say round with (log of 10), 4
say log10 of 1000
say round with (exp of 1), 4
say round with (radians of 90), 4
say degrees of pi
say hex of 255
say binary of 10
say format_number with 1.5, 3
say with_commas of 98765432.1
say with_commas with 1234.5, 2
say average of (list of 1, 2, 3, 4)
say sum of (list of 1.5, 2.5)
say largest of (list of 3, 9, 2)
say smallest of (list of 3, 9, 2)
```

```output
5
2
3.142
1.4142135624
18446744073709551616
-3
3
-2
true
3
8
0
-1
3.14159
0
1
1
2.3026
3
2.7183
1.5708
180
ff
1010
1.500
98,765,432.1
1,234.50
2.5
4
9
2
```

### Random numbers

| Task | Example and meaning |
|---|---|
| `random` | `random with 1, 6` |
| `random_decimal` | `random_decimal` → a decimal between 0 and 1 |
| `random_item` | `random_item of (list of "rock", "paper", "scissors")` |
| `shuffled` | `shuffled of cards` → a new list in random order |
| `seed_random` | `seed_random with 42   (makes random results repeatable)` |

`seed_random` makes the sequence repeatable, which is useful in tests:

```lekh
seed_random with 42
let a be random with 1, 100
let b be random_decimal
let c be random_item of (list of "rock", "paper", "scissors")
let d be shuffled of (list of 1, 2, 3, 4)
seed_random with 42
say a is (random with 1, 100)
say b is between 0 and 1
say (list of "rock", "paper", "scissors") contains c
say sorted of d
```

```output
true
true
true
[1, 2, 3, 4]
```

### Lists and maps

| Task | Example and meaning |
|---|---|
| `first` | `first of cart` |
| `last` | `last of cart` |
| `sorted` | `sorted of scores` |
| `reversed` | `reversed of cart` |
| `position` | `position with cart, "milk"   (gives some 2, or nothing)` |
| `unique` | `unique of (list of 1, 2, 2, 3)` → [1, 2, 3] (keeps the first of each) |
| `flatten` | `flatten of (list of (list of 1, 2), (list of 3))` → [1, 2, 3] |
| `chunks` | `chunks with (list of 1, 2, 3, 4, 5), 2` → [[1, 2], [3, 4], [5]] |
| `numbered` | `numbered of (list of "a", "b")` → [(1, "a"), (2, "b")] |
| `pairs_of` | `pairs_of with names, ages` → [("Ann", 31), ("Bo", 25)] |
| `pairs` | `pairs of ages` → [("Ann", 31), ("Bo", 25)] (a map as a list of (key, value) groups) |
| `map_from` | `map_from of (list of ("a", 1), ("b", 2))` → {"a": 1, "b": 2} |
| `merged` | `merged with defaults, settings` → a new map; the second one wins on clashes |
| `keys` | `keys of ages` |
| `values` | `values of ages` |
| `sorted_using` | `sorted_using with people, given a, b: a's age is less than b's age` |
| `transform` | `transform with numbers, given n: n * 2` |
| `select` | `select with numbers, given n: n is greater than 2` |
| `reduce` | `reduce with numbers, 0, given total, n: total + n` |

```lekh
let xs be list of 3, 1, 2, 3
say first of xs
say last of xs
say sorted of xs
say reversed of xs
say (position with xs, 2) or else 0
say unique of xs
say flatten of (list of (list of 1), (list of 2, 3))
say chunks with (range from 1 to 5), 2
say numbered of (list of "a", "b")
say pairs_of with (list of "a", "b"), (list of 1, 2)
say pairs of (map of "k" to "v")
say map_from of (list of ("x", 1), ("y", 2))
say merged with (map of "a" to 1, "b" to 2), (map of "b" to 20)
say keys of (map of "a" to 1)
say values of (map of "a" to 1)
say sorted_using with xs, given a, b: a is greater than b
say transform with xs, given x: x * 10
say select with xs, given x: x is not 3
say reduce with xs, 0, given total, x: total + x
say reversed of "stressed"
```

```output
3
3
[1, 2, 3, 3]
[3, 2, 1, 3]
3
[3, 1, 2]
[1, 2, 3]
[[1, 2], [3, 4], [5]]
[(1, "a"), (2, "b")]
[("a", 1), ("b", 2)]
[("k", "v")]
{"x": 1, "y": 2}
{"a": 1, "b": 20}
["a"]
[1]
[3, 3, 2, 1]
[30, 10, 20, 30]
[1, 2]
9
desserts
```

`sorted`, `largest` and `smallest` work on numbers, text, or groups of those.
To sort records, use `sort each p in people by p's age` or `sorted_using`.

### Sets

| Task | Example and meaning |
|---|---|
| `union` | `union with a, b` → everything in either set |
| `intersection` | `intersection with a, b` → only what both sets have |
| `difference` | `difference with a, b` → what's in a but not in b |
| `is_subset` | `is_subset with small, big` → true if every item of small is in big |

```lekh
let a be set of 1, 2, 3
let b be set of 3, 4
say union with a, b
say intersection with a, b
say difference with a, b
say is_subset with (set of 1, 2), a
```

```output
set of 1, 2, 3, 4
set of 3
set of 1, 2
true
```

### Patterns (regular expressions)

These use the usual regular expression syntax (Python's `re`): `[0-9]`,
`\w`, `+`, `*`, `?`, `{2,4}`, `(...)` groups, `^` and `$`, `|` for "or".

| Task | Example and meaning |
|---|---|
| `matches` | `matches with "2026-10-08", "[0-9]{4}-[0-9]{2}-[0-9]{2}"` → true (the WHOLE text must match) |
| `contains_pattern` | `contains_pattern with line, "ERROR\|FATAL"` → true if any part matches |
| `find_all` | `find_all with "a1b22c333", "[0-9]+"` → ["1", "22", "333"] |
| `find_groups` | `find_groups with "user=ann id=7", "(\\w+)=(\\w+)"` → [["user", "ann"], ["id", "7"]] |
| `replace_pattern` | `replace_pattern with "a1b22", "[0-9]+", "#"` → "a#b#" |
| `split_pattern` | `split_pattern with "a, b;c", "[,;] *"` → ["a", "b", "c"] |
| `matches_wildcard` | `matches_wildcard with "app.log", "*.log"` → true (* = anything, ? = one letter) |

```lekh
say matches with "AB-1234", "[A-Z]{2}-[0-9]{4}"
say matches with "xAB-1234", "[A-Z]{2}-[0-9]{4}"
say contains_pattern with "ERROR: disk full", "ERROR|FATAL"
say find_all with "tea 20, coffee 35", "[0-9]+"
say find_groups with "a=1, b=2", "(\w)=(\d)"
say replace_pattern with "too    many   spaces", " +", " "
say split_pattern with "a1b22c", "[0-9]+"
say matches_wildcard with "photo_2026.jpg", "photo_*.jpg"
say matches_wildcard with "notes.txt", "?otes.*"
```

```output
true
false
true
["20", "35"]
[["a", "1"], ["b", "2"]]
too many spaces
["a", "b", "c"]
true
true
```

### Files and folders

All give back results except `file_exists`, `is_folder` and the path tasks.
Paths are relative to the folder you run the program from.

| Task | Example and meaning |
|---|---|
| `read_file` | `read_file of "notes.txt"` → ok "the text" or problem "no file ..." |
| `read_lines` | `read_lines of "data.csv"` → ok ["line 1", "line 2"] |
| `write_file` | `write_file with "out.txt", "hello"` → ok 5 (letters written) (replaces the file) |
| `append_file` | `append_file with "log.txt", "one more line\n"` → ok 14 |
| `file_exists` | `file_exists of "notes.txt"` → true / false (also true for folders) |
| `is_folder` | `is_folder of "src"` → true / false |
| `list_folder` | `list_folder of "."` → ok ["a.txt", "src"] (sorted names) |
| `make_folder` | `make_folder of "reports/2026"` → ok "reports/2026" (makes parents too) |
| `delete_file` | `delete_file of "old.txt"` → ok "old.txt" (files only, never folders) |
| `file_size` | `file_size of "photo.jpg"` → ok 20480 (bytes) |
| `join_path` | `join_path with "reports", "june.csv"` → "reports/june.csv" (any number of parts) |
| `file_name` | `file_name of "/tmp/report.csv"` → "report.csv" |
| `folder_of` | `folder_of of "/tmp/report.csv"` → "/tmp" |
| `extension` | `extension of "report.csv"` → "csv" |

```lekh
let folder be "ref_demo"
make_folder of folder
let path be join_path with folder, "data.txt"
write_file with path, "one\ntwo\n"
append_file with path, "three\n"
say (read_file of path) or else ""
say (read_lines of path) or else (empty list)
say file_exists of path
say is_folder of folder
say (list_folder of folder) or else (empty list)
say (file_size of path) or else 0
say file_name of path
say folder_of of path
say extension of path
say (delete_file of path) or else "?"
say file_exists of path
say (read_file of "nope.txt") is problem
```

```output
one
two
three

["one", "two", "three"]
true
true
["data.txt"]
14
data.txt
ref_demo
txt
ref_demo/data.txt
false
true
```

### JSON

| Task | Example and meaning |
|---|---|
| `to_json` | `to_json of data` → "{\"name\": \"Ann\"}" (to_json with data, true  makes it pretty) |
| `from_json` | `from_json of text` → ok value, or problem "bad JSON ..." (objects become maps, null becomes nothing) |
| `json_get` | `json_get with data, "user.address.city"` → some value or nothing (numbers pick list items, from 1) |

```lekh
let data as map of text to anything be map of "name" to "Asha", "tags" to (list of "a", "b"), "age" to 31
let text be to_json of data
say text
say to_json with (map of "x" to 1), true
let back be (from_json of text) or else nothing
say (json_get with back, "tags.1") or else "?"
say (json_get with back, "missing") or else "?"
say (from_json of "{{not json") is problem
say (from_json of "[1, null, true]") or else (empty list)
```

```output
{"name": "Asha", "tags": ["a", "b"], "age": 31}
{
  "x": 1
}
a
?
true
[1, nothing, true]
```

### Dates and times

Moments are numbers of seconds (Unix time, in the computer's local time zone).
`format_time` patterns: `YYYY` year, `MM` month number, `MMM` short month
name, `MMMM` full month name, `DD` day, `DDD` short weekday, `DDDD` weekday,
`hh` hour (24h), `mm` minutes, `ss` seconds.

| Task | Example and meaning |
|---|---|
| `now` | `now` → the current moment as seconds (use it with format_time, add_days, ...) |
| `today` | `today` → "2026-10-08" |
| `current_time` | `current_time` → "14:03:22" |
| `format_time` | `format_time with now, "DD MMM YYYY, hh:mm"` → "08 Oct 2026, 14:03" |
| `parse_date` | `parse_date of "2026-10-08"` → ok moment (also "2026-10-08 14:30") |
| `add_days` | `add_days with now, 7` → the moment one week later |
| `days_between` | `days_between with start, finish` → whole days from start to finish |
| `year_of` | `year_of of now` → 2026 |
| `month_of` | `month_of of now` → 10 |
| `day_of` | `day_of of now` → 8 |
| `hour_of` | `hour_of of now` → 14 |
| `minute_of` | `minute_of of now` → 3 |
| `weekday_of` | `weekday_of of now` → "Thursday" |
| `seconds_since` | `seconds_since of started` → how long ago that moment was, in seconds |

```lekh
let t be (parse_date of "2026-03-15 09:05") or else 0
say format_time with t, "DDDD DD MMMM YYYY, hh:mm"
say format_time with t, "DDD DD MMM"
say "{year_of of t}-{month_of of t}-{day_of of t} {hour_of of t}:{minute_of of t}"
say weekday_of of t
let later be add_days with t, 10
say days_between with t, later
say (parse_date of "next Tuesday") is problem
say (now) is greater than t
say length of today
say length of current_time
say (seconds_since of now) is less than 5
```

```output
Sunday 15 March 2026, 09:05
Sun 15 Mar
2026-3-15 9:5
Sunday
10
true
true
10
8
true
```

### The program and the system

| Task | Example and meaning |
|---|---|
| `arguments` | `arguments` → the words after the file name:  lekh run app.lekh add milk  ->  ["add", "milk"] |
| `environment` | `environment of "HOME"` → some "/home/sushant" or nothing |
| `read_all_input` | `read_all_input` → everything typed or piped into the program, as text |
| `exit_program` | `exit_program with 1   (stops at once; 0 means success)` |
| `run_command` | `run_command of "git status"` → ok CommandOutput(output, errors, code) or a problem (run_command with "ls", "/tmp" runs it in a folder) |

`run_command` splits the command into words and starts the program directly,
never through a shell, so `;`, `|`, `&&` and `$(...)` are just ordinary
characters. A second input sets the folder to run in. The `CommandOutput`
record has `output`, `errors` and `code`. Commands time out after 60 seconds.

```lekh stdin="line one|line two"
say arguments
say (environment of "SURELY_NOT_SET_123") or else "unset"
say lines of read_all_input
when run_command of "echo safe; rm -rf /":
    is ok r: say "printed: {trimmed of r's output} (code {r's code})"
    is problem why: say why
when run_command of "no-such-program-xyz":
    is ok r: say r's code
    is problem why: say "problem: {why}"
exit_program with 0
say "never printed"
```

```output
[]
unset
["line one", "line two"]
printed: safe; rm -rf / (code 0)
problem: no program called "no-such-program-xyz" was found
```

### The web

| Task | Example and meaning |
|---|---|
| `http_get` | `http_get of "https://example.com"` → ok Response(status, body, headers) or a problem |
| `http_post` | `http_post with url, (to_json of data)` → ok Response (3rd input: content type) |

Only `http://` and `https://` addresses are allowed; requests time out after
15 seconds. The `Response` record has `status`, `body` and `headers` (a map).
A status like 404 is still `ok` (the server answered); a problem means no
answer at all. This sample needs the internet, so it is only checked:

```lekh check
when http_get of "https://example.com":
    is ok r:
        say r's status
        say (r's headers at "Content-Type") or else "?"
        say length of r's body
    is problem why: say why
let body be to_json of (map of "q" to "lekh")
when http_post with "https://httpbin.org/post", body, "application/json":
    is ok r: say r's status
    is problem why: say why
```

And this one runs anywhere, showing what happens with a bad address:

```lekh
say (http_get of "ftp://example.com") or else (Response with status 0, body "refused", headers empty map)
when http_get of "file:///etc/passwd":
    is ok r: say r's status
    is problem why: say why
```

```output
Response(status: 0, body: "refused", headers: {})
only http:// and https:// addresses are allowed, not "file:///etc/passwd"
```

## Command line

| Command | What it does |
|---|---|
| `lekh run file.lekh [args...]` or `lekh file.lekh` | check and run (args go to `arguments`) |
| `lekh run` | in a project, run the `main` file from `project.json` |
| `lekh check file.lekh` | all checks, no running |
| `lekh test [file or folder]` | run `test` blocks (default: the project's `tests/`) |
| `lekh format file-or-folder` | tidy layout in place; `--check` to only report |
| `lekh build file.lekh [-o out.py]` | translate to Python after checking |
| `lekh new name` | create a project |
| `lekh repl` | interactive prompt (`:help`, `:vars`, `:type`, `:load`, `:reset`, `:quit`) |
| `lekh version`, `lekh help` | information |

## Keyword index

Reserved keywords and the other words with special meaning in some statements:

[`ability`](#abilities) · [`add`](#lists) · [`and`](#operators) · [`any`](#list-operations-in-english) · [`anything`](#types) · [`as`](#conversions-with-as) · [`ask`](#text-values) · [`at`](#maps)

[`back`](#tasks) · [`be`](#variables) · [`between`](#operators) · [`by`](#control-flow) · [`can`](#abilities) · [`change`](#variables) · [`changeable`](#variables) · [`changes`](#records-choices-and-methods)

[`channel`](#concurrency) · [`choice`](#records-choices-and-methods) · [`close`](#concurrency) · [`combine`](#list-operations-in-english) · [`constant`](#variables) · [`contains`](#operators) · [`copy`](#ownership-words) · [`count`](#list-operations-in-english)

[`decrease`](#variables) · [`descending`](#list-operations-in-english) · [`div`](#operators) · [`each`](#control-flow) · [`else`](#maybe-and-result) · [`empty`](#collections) · [`end`](#cleanup-at-the-end) · [`ends`](#operators)

[`every`](#list-operations-in-english) · [`expect`](#tests) · [`fail`](#fail) · [`false`](#types) · [`find`](#list-operations-in-english) · [`for`](#control-flow) · [`from`](#control-flow) · [`give`](#tasks)

[`given`](#tasks) · [`gives`](#tasks) · [`if`](#control-flow) · [`in`](#control-flow) · [`increase`](#variables) · [`is`](#operators) · [`item`](#lists) · [`keep`](#list-operations-in-english)

[`lend`](#ownership-words) · [`let`](#variables) · [`list`](#lists) · [`map`](#maps) · [`maybe`](#maybe-and-result) · [`me`](#records-choices-and-methods) · [`mod`](#operators) · [`my`](#records-choices-and-methods)

[`not`](#operators) · [`nothing`](#maybe-and-result) · [`of`](#tasks) · [`ok`](#maybe-and-result) · [`or`](#operators) · [`otherwise`](#control-flow) · [`position`](#control-flow) · [`problem`](#maybe-and-result)

[`range`](#lists) · [`receive`](#concurrency) · [`record`](#records-choices-and-methods) · [`remove`](#lists) · [`repeat`](#control-flow) · [`result`](#maybe-and-result) · [`run`](#tasks) · [`same`](#concurrency)

[`say`](#text-values) · [`send`](#concurrency) · [`set`](#sets) · [`share`](#modules) · [`skip`](#control-flow) · [`some`](#maybe-and-result) · [`sort`](#list-operations-in-english) · [`start`](#concurrency)

[`starts`](#operators) · [`stop`](#control-flow) · [`take`](#lists) · [`test`](#tests) · [`then`](#operators) · [`times`](#control-flow) · [`to`](#tasks) · [`true`](#types)

[`try`](#maybe-and-result) · [`turn`](#list-operations-in-english) · [`use`](#modules) · [`value`](#control-flow) · [`wait`](#concurrency) · [`when`](#patterns) · [`where`](#list-operations-in-english) · [`while`](#control-flow)

[`with`](#tasks)

