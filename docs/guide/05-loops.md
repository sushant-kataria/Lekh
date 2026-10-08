# 5. Repeating things

## repeat

```lekh
repeat 3 times:
    say "hip hip hooray"
```

```output
hip hip hooray
hip hip hooray
hip hip hooray
```

## for each

Go through every item of a list (or set, or text letters, or a range):

```lekh
let fruits be list of "mango", "banana", "guava"
for each fruit in fruits:
    say "I like {fruit}"
for each fruit and position in fruits:
    say "{position}. {fruit}"
```

```output
I like mango
I like banana
I like guava
1. mango
2. banana
3. guava
```

Counting with numbers:

```lekh
for each i from 1 to 5:
    say "{i} squared is {i * i}"
for each i from 10 to 0 by -5:
    say "countdown {i}"
say range from 1 to 10 by 3
```

```output
1 squared is 1
2 squared is 4
3 squared is 9
4 squared is 16
5 squared is 25
countdown 10
countdown 5
countdown 0
[1, 4, 7, 10]
```

Going through a map gives each key and value:

```lekh
let stock be map of "pens" to 12, "books" to 3
for each item and amount in stock:
    say "{item}: {amount}"
```

```output
pens: 12
books: 3
```

## while

```lekh
let changeable money be 100
let changeable days be 0
while money is greater than 0:
    decrease money by 30
    increase days by 1
say "The money lasted {days} days."
```

```output
The money lasted 4 days.
```

## stop and skip

`stop` leaves the loop. `skip` jumps straight to the next round.

```lekh
for each n from 1 to 100:
    if n mod 2 is 0: skip
    if n is greater than 9: stop
    say n
```

```output
1
3
5
7
9
```

## Safety rule: don't change a list while going through it

Lekh stops you from adding to or removing from a list inside a loop over that
same list (a common bug in other languages). Collect changes first:

```lekh error
let changeable names be list of "a", "b"
for each n in names:
    add n + "!" to names
```

```output

-- Lekh: Ownership rule ----------------------------------------------
In sample_7.lekh, line 3:

    3 |     add n + "!" to names

You can't add to `names` while looping over it - the loop would lose its place.

How to fix:
    Collect the changes in a separate list during the loop, and apply them after it ends.
```

Next: [6. Lists, maps, sets and groups](06-collections.md)
