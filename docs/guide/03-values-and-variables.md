# 3. Values and variables

## Kinds of value

| Kind | Examples |
|---|---|
| number | `42`, `-7`, `3.5`, `123456789012345678901234567890` |
| text | `"hello"`, `"line one\nline two"` |
| truth | `true`, `false` |
| list | `list of 1, 2, 3`, `empty list` |
| map | `map of "Ann" to 31, "Bo" to 25`, `empty map` |
| set | `set of "red", "green"`, `empty set` |
| group (tuple) | `(3, "three")` |
| maybe | `some 5`, `nothing` |
| result | `ok 5`, `problem "it broke"` |

## Naming values with `let`

```lekh
let city be "Pune"
let population be 7400000
let is_big be population is greater than 1000000
say "{city}: {with_commas of population} people, big city: {is_big}"
```

```output
Pune: 7,400,000 people, big city: true
```

A name made with `let` never changes. That makes programs easier to follow.
When something really does need to change, say so with `let changeable`:

```lekh
let changeable score be 10
change score to 15
increase score by 5
decrease score by 2
say score
```

```output
18
```

`constant` is for fixed settings, usually written in capitals:

```lekh
constant MAX_TRIES be 3
say "You get {MAX_TRIES} tries."
```

```output
You get 3 tries.
```

## Numbers

Whole numbers (integers) can be as big as you like. Decimals are ordinary
floating-point numbers. Arithmetic uses `+ - * /`, plus `div` (whole-number
division), `mod` (remainder) and `power`:

```lekh
say 7 / 2
say 7 div 2
say 7 mod 2
say power with 2, 100
say round with 3.14159, 2
say format_number with 2.5, 2
say with_commas of 1234567
```

```output
3.5
3
1
1267650600228229401496703205376
3.14
2.50
1,234,567
```

## Changing one kind into another

`as` converts. Turning text into a number can fail, so it gives a *result*
(see chapter 9). `or else` supplies a value to use when it fails:

```lekh
let typed be "42"
let n be (typed as number) or else 0
let bad be ("forty" as number) or else 0
say n + 1
say bad
say 3.9 as text
say (7.9 as integer) or else 0
```

```output
43
0
3.9
7
```

## Text basics

```lekh
let word be "Lekh"
say uppercase of word
say length of word
say word + " is fun"
say "Lekh" contains "ek"
say "report.csv" ends with ".csv"
say split with "a,b,c", ","
say join with (list of "x", "y"), " + "
say replace with "I like tea", "tea", "chai"
say slice with "language", 1, 4
```

```output
LEKH
4
Lekh is fun
true
true
["a", "b", "c"]
x + y
I like chai
lang
```

Next: [4. Making decisions](04-decisions.md)
