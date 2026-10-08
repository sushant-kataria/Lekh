# 4. Making decisions

## if / otherwise

The lines that belong to an `if` are indented (4 spaces). There is no `end`.

```lekh
let temperature be 31
if temperature is greater than 30:
    say "Hot! Drink water."
otherwise if temperature is less than 10:
    say "Cold. Take a jacket."
otherwise:
    say "Nice weather."
```

```output
Hot! Drink water.
```

A short `if` can sit on one line: `if x is 0: say "zero"`.

## Comparing

| Lekh | Meaning |
|---|---|
| `a is b` | equal |
| `a is not b` | not equal |
| `a is greater than b` / `a is less than b` | `>` / `<` |
| `a is at least b` / `a is at most b` | `>=` / `<=` |
| `a is between 1 and 10` | `1 <= a <= 10` |
| `xs contains x` | x is in the list, set, map keys or text |
| `t starts with "a"` / `t ends with "z"` | text starts / ends with |
| `a and b`, `a or b`, `not a` | combine truths |

```lekh
let age be 20
let member be true
if age is at least 18 and member:
    say "welcome to the club"
if age is between 13 and 19:
    say "teenager"
if not member:
    say "please sign up"
```

```output
welcome to the club
```

## Choosing a value: `if ... then ... otherwise`

When you just need one value or another, write it in one line:

```lekh
let marks be 72
let result be if marks is at least 40 then "pass" otherwise "fail"
let grade be if marks is at least 80 then "A" otherwise if marks is at least 60 then "B" otherwise "C"
say "{result}, grade {grade}"
```

```output
pass, grade B
```

Both answers must be the same kind of value (both text, both numbers, ...).

## when: many cases at once

`when` compares one value against several cases, top to bottom.
`otherwise` catches everything else:

```lekh
to describe day as text gives text:
    when day:
        is "Saturday" or "Sunday": give back "weekend"
        is "Friday": give back "almost weekend"
        otherwise: give back "work day"

say describe with "Sunday"
say describe with "Tuesday"
```

```output
weekend
work day
```

Cases can be ranges and can have an extra `if` (a *guard*):

```lekh
for each n in list of 0, 7, 42, 99:
    when n:
        is 0: say "zero"
        is from 1 to 9: say "{n} is one digit"
        is m if m mod 2 is 0: say "{m} is big and even"
        otherwise: say "{n} is big and odd"
```

```output
zero
7 is one digit
42 is big and even
99 is big and odd
```

`when` really shines with choices (chapter 8) and with maybe/result values
(chapter 9), where Lekh checks that you handled every case.

Next: [5. Repeating things](05-loops.md)
