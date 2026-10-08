# Lekh cheat sheet

Everything on one page. Each block is a complete program that runs as is.
Details are in the [reference](reference.md); the [guide](guide/README.md) explains it all slowly.

## Basics

```lekh
-- comment
say "Hello, {1 + 1} worlds"            -- {} puts a value in text
let name be "Asha"                     -- can't change
let changeable n be 1                  -- can change
change n to 5
increase n by 2                        -- also: decrease
constant MAX be 10
let label be if n is at least MAX then "full" otherwise "ok"
say "{name} {n} {label}"
```

```output
Hello, 2 worlds
Asha 7 ok
```

## Values and conversion

```lekh
let whole be 12345678901234567890 * 10   -- no overflow
let dec be 7 / 2                          -- 3.5;  7 div 2 = 3;  7 mod 2 = 1
let typed be ("42" as number) or else 0   -- text -> number can fail
say "{whole} {dec} {typed + 1} {3.5 as text} {(9.7 as integer) or else 0}"
say "{true and not false} {type_of of "x"}"
```

```output
123456789012345678900 3.5 43 3.5 9
true text
```

## Comparing

```lekh
let x be 5
say x is 5                      -- also: is not
say x is greater than 3         -- is less than, is at least, is at most
say x is between 1 and 10
say "lekh" contains "ek"        -- lists, sets, map keys, text
say "a.csv" ends with ".csv"    -- starts with
say (list of 1, 2) is (list of 1, 2)
```

```output
true
true
true
true
true
true
```

## Decisions

```lekh
let t be 25
if t is greater than 30:
    say "hot"
otherwise if t is less than 10:
    say "cold"
otherwise:
    say "nice"

when t:
    is 0: say "freezing"
    is from 1 to 20: say "cool"
    is n if n mod 5 is 0: say "multiple of five"
    otherwise: say "other"
```

```output
nice
multiple of five
```

## Loops

```lekh
repeat 2 times:
    say "hi"
for each i from 1 to 9 by 4:
    say i
for each fruit and pos in list of "fig", "kiwi":
    say "{pos}. {fruit}"
let changeable k be 0
while k is less than 3:
    increase k by 1
    if k is 2: skip                -- next round;  `stop` leaves the loop
    say "k={k}"
```

```output
hi
hi
1
5
9
1. fig
2. kiwi
k=1
k=3
```

## Lists, maps, sets, groups

```lekh
let changeable xs be list of 3, 1, 2
add 4 to xs
remove 1 from xs
say "{xs} {item 1 of xs} {first of xs} {last of xs} {length of xs} {sorted of xs}"
let changeable m be map of "a" to 1
change m at "b" to 2
say "{(m at "a") or else 0} {(m at "z") or else 0} {keys of m}"
for each key and value in m:
    say "{key}={value}"
let s be set of "x", "y", "x"
let (left, right) be (1, 2)
say "{length of s} {left + right}"
let changeable q be list of "a", "b"
say (take first from q) or else "-"   -- queue; `take last from` = stack
```

```output
[3, 2, 4] 3 3 4 3 [2, 3, 4]
1 0 ["a", "b"]
a=1
b=2
2 3
a
```

## List operations in English

```lekh
let xs be list of 4, 9, 2
say keep each x in xs where x is greater than 3
say turn each x in xs into x * 10
say count each x in xs where x is less than 5
say (find first x in xs where x is greater than 5) or else 0
say any x in xs where x is 9
say every x in xs where x is greater than 0
say sort each x in xs by x descending
say combine each x in xs into total starting at 0 using total + x
```

```output
[4, 9]
[40, 90, 20]
2
9
true
true
[9, 4, 2]
15
```

## Tasks

```lekh
to area w as number, h as number gives number:
    give back w * h

to shout word:
    say uppercase of word

to hello gives text:
    give back "hello"

say area with 2, 3        -- several inputs
shout of "hey"            -- one input
say run hello             -- no inputs
let double be given x: x * 2
say double with 4
```

```output
6
HEY
hello
8
```

## Records, methods, choices

```lekh
record Point:
    x as number
    y as number

to Point's moved dx as number gives Point:
    give back Point with x my x + dx, y my y

choice Shape:
    Circle with r as number
    Square with side as number

let p be Point with x 1, y 2
say p's moved with 5
say p's x
let s be Square with side 3
when s:
    is Circle with r: say "circle {r}"
    is Square with side: say "square {side}"
```

```output
Point(x: 6, y: 2)
1
square 3
```

## Maybe and result

```lekh
to safe_divide a as number, b as number gives result of number or text:
    if b is 0: give back problem "divide by zero"
    give back ok a / b

to twice_divided a as number, b as number gives result of number or text:
    let once be try safe_divide with a, b      -- a problem goes straight back
    give back safe_divide with once, b

say (safe_divide with 1, 0) or else 0
when twice_divided with 20, 2:
    is ok v: say "ok {v}"
    is problem why: say "problem: {why}"
let ages be map of "Bo" to 25
when ages at "Bo":
    is some a: say "Bo is {a}"
    is nothing: say "unknown"
```

```output
0
ok 5
Bo is 25
```

## Ownership

```lekh
to look xs as list of number gives number:
    give back length of xs

to grow changeable xs as list of number:
    add 0 to xs

to keep xs as list of number gives text:
    give back "kept {length of xs}"

let changeable xs be list of 1, 2
say look with xs              -- read-only borrow
grow with lend xs             -- may change it
let backup be copy of xs      -- an independent copy
say keep with give xs         -- xs is gone after this
say backup
```

```output
2
kept 3
[1, 2, 0]
```

## Abilities and generics

```lekh
ability Named:
    to name gives text

record Cat:
    nick as text

to Cat's name gives text:
    give back "cat {my nick}"

Cat can Named

to first_or xs as list of T, d as T gives T:
    if length of xs is 0: give back d
    give back first of xs

say (Cat with nick "Kitty")'s name
say first_or with (empty list), 7
```

```output
cat Kitty
7
```

## Errors and cleanup

```lekh
choice AppError:
    NotFound with what as text
    Denied

to open_file name as text gives result of text or AppError:
    at the end:
        say "(closed {name})"
    if name is "secret": give back problem Denied
    give back problem (NotFound with what name)

when open_file of "notes":
    is ok text: say text
    is problem (NotFound with w): say "missing {w}"
    is problem Denied: say "denied"
```

```output
(closed notes)
missing notes
```

## At the same time

```lekh
let out be a new channel
for each n in list of 1, 2, 3 at the same time:
    send n * n to out
close out
let changeable got be empty list
for each v in out:
    add v to got
say sorted of got

to slow n as number gives number:
    wait 0.05 seconds
    give back n + 1

let job be start slow with 1
say wait for job
```

```output
[1, 4, 9]
2
```

## Files, JSON, commands

```lekh
write_file with "cheat.txt", "hi\n"
say (read_file of "cheat.txt") or else ""
say to_json of (map of "ok" to true)
let data be (from_json of "{{\"a\": {{\"b\": 5}}}") or else nothing
say (json_get with data, "a.b") or else 0
when run_command of "echo shell-free":
    is ok r: say trimmed of r's output
    is problem why: say why
```

```output
hi

{"ok": true}
5
shell-free
```

## Modules and tests

```lekh file=mathx.lekh
share to cube n as number gives number:
    give back n * n * n
```

```lekh test
use cube from "mathx"

test "cube works":
    expect cube of 3 to be 27
    expect list of 1, 2 to contain 2
    expect ("x" as number) to be problem
```

```output
sample_17.lekh
  PASS  cube works

1 test, 1 passed, 0 failed
```

## Commands

```bash
lekh run app.lekh args...   # run          lekh check app.lekh   # check only
lekh test                   # run tests    lekh format .         # tidy code
lekh build app.lekh         # fast Python  lekh new my_app       # new project
lekh repl                   # try things   lekh help             # all commands
```
