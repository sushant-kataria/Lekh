# 9. Missing values and errors (maybe and result)

Lekh has no `null`. A value that might be missing is a **maybe**: either
`some value` or `nothing`. Work that might fail gives a **result**: either
`ok value` or `problem why`. Lekh won't let you use either one as if it were
the plain value: you have to deal with the "missing" or "failed" case first.
That removes a whole family of crashes.

## Three ways to handle a maybe or result

```lekh
let phone_book be map of "Asha" to "98200 11111"

-- 1. a fallback with `or else`
say (phone_book at "Ravi") or else "unknown"

-- 2. `when`, to do different things
when phone_book at "Asha":
    is some number: say "Asha: {number}"
    is nothing: say "no number"

-- 3. a quick test
say (phone_book at "Ravi") is nothing
```

```output
unknown
Asha: 98200 11111
true
```

Using it directly is caught before the program runs:

```lekh error
let phone_book be map of "Asha" to "98200 11111"
let n be phone_book at "Asha"
say "Call " + n
```

```output

-- Lekh: Possibly missing value --------------------------------------
In sample_2.lekh, line 3:

    3 | say "Call " + n

`n` might be nothing, so it can't be used in math yet. Lekh has no null - a maybe value must be checked before use.

How to fix:
    Give a fallback:   (n or else 0)
    or check it first:
        when n:
            is some v: ...
            is nothing: ...
```

## Writing tasks that can fail

```lekh
to divide a as number, b as number gives result of number or text:
    if b is 0:
        give back problem "can't divide by zero"
    give back ok a / b

for each b in list of 4, 0:
    when divide with 12, b:
        is ok answer: say "12 / {b} = {answer}"
        is problem why: say "error: {why}"
```

```output
12 / 4 = 3
error: can't divide by zero
```

## Passing a problem along with `try`

`try` means: "if this is a problem (or nothing), stop here and hand it to
whoever called me; otherwise give me the value". It is Rust's `?`.

```lekh
to parse_price t as text gives result of number or text:
    let n be try (t as number)
    if n is less than 0: give back problem "price can't be negative"
    give back ok n

to total_of texts as list of text gives result of number or text:
    let changeable total be 0
    for each t in texts:
        increase total by try parse_price of t
    give back ok total

for each prices in list of (list of "10", "20.5"), (list of "10", "abc"), (list of "10", "-3"):
    when total_of of prices:
        is ok total: say "total {total}"
        is problem why: say "problem: {why}"
```

```output
total 30.5
problem: "abc" is not a number
problem: price can't be negative
```

## Your own error types

A choice makes errors precise, and `when` makes sure callers handle each one:

```lekh
choice LoginError:
    NoSuchUser with name as text
    WrongPassword with tries_left as number
    Locked

to login name as text, password as text gives result of text or LoginError:
    if name is not "asha": give back problem (NoSuchUser with name name)
    if password is "letmein": give back problem Locked
    if password is not "s3cret": give back problem (WrongPassword with tries_left 2)
    give back ok "welcome, {name}"

for each (n, p) in list of ("asha", "s3cret"), ("bob", "x"), ("asha", "nope"), ("asha", "letmein"):
    when login with n, p:
        is ok msg: say msg
        is problem (NoSuchUser with who): say "no user called {who}"
        is problem (WrongPassword with left): say "wrong password, {left} tries left"
        is problem Locked: say "account locked"
```

```output
welcome, asha
no user called bob
wrong password, 2 tries left
account locked
```

## Stopping on purpose: `fail`

`fail "message"` stops the program with a clear error. Use it for "this
should never happen" situations. For problems a caller could handle, give
back a `problem` instead.

```lekh error
to set_volume level as number:
    if level is greater than 100: fail "volume {level} is too loud"
    say "volume {level}"

set_volume with 50
set_volume with 150
```

```output
volume 50

-- Lekh: The program stopped on purpose ------------------------------
In sample_6.lekh, line 2:

    2 |     if level is greater than 100: fail "volume {level} is too loud"

volume 150 is too loud

How to fix:
    This came from a `fail` line in the program. Handle the situation before it, or change the message.
```

## Cleaning up: `at the end`

Lines under `at the end:` run when the task finishes, however it finishes
(normally, by `give back`, or by `try` passing a problem up):

```lekh
to process name as text gives result of number or text:
    say "open {name}"
    at the end:
        say "close {name}"
    if name is "": give back problem "no name"
    say "working on {name}"
    give back ok 1

say (process with "report.txt") or else 0
say (process with "") or else 0
```

```output
open report.txt
working on report.txt
close report.txt
1
open 
close 
0
```

Next: [10. Ownership: who owns a value](10-ownership.md)
