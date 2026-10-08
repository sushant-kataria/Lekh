# 6. Lists, maps, sets and groups

## Lists

A list keeps items in order. Positions start at **1**.

```lekh
let changeable cart be list of "rice", "dal"
add "ghee" to cart
say cart
say "first: {first of cart}, last: {last of cart}, second: {item 2 of cart}"
say "{length of cart} items, has dal: {cart contains "dal"}"
remove "rice" from cart
change item 1 of cart to "moong dal"
say cart
say sorted of (list of 5, 1, 4)
say reversed of (list of 1, 2, 3)
say sum of (list of 10, 20, 30)
```

```output
["rice", "dal", "ghee"]
first: rice, last: ghee, second: dal
3 items, has dal: true
["moong dal", "ghee"]
[1, 4, 5]
[3, 2, 1]
60
```

Asking for a position that doesn't exist is an error with a clear message,
never a silent wrong value. `position with` searches and gives a *maybe*:

```lekh
let names be list of "Ann", "Bo"
when position with names, "Bo":
    is some p: say "Bo is number {p}"
    is nothing: say "no Bo"
```

```output
Bo is number 2
```

## Working on whole lists in English

```lekh
let prices be list of 120, 45, 300, 80
let cheap be keep each p in prices where p is less than 100
let with_tax be turn each p in prices into p * 1.18
let pricey be count each p in prices where p is greater than 100
let total be combine each p in prices into acc starting at 0 using acc + p
let first_big be find first p in prices where p is greater than 200
say cheap
say with_tax
say "{pricey} pricey, total {total}, first big {first_big or else 0}"
say any p in prices where p is greater than 250
say every p in prices where p is greater than 10
say sort each p in prices by p descending
```

```output
[45, 80]
[141.6, 53.1, 354, 94.4]
2 pricey, total 545, first big 300
true
true
[300, 120, 80, 45]
```

## Maps

A map links keys to values. Looking up a key gives a *maybe*, because the key
might not be there: you must say what happens then.

```lekh
let changeable ages be map of "Ann" to 31, "Bo" to 25
change ages at "Cy" to 40
say (ages at "Ann") or else 0
say (ages at "Zed") or else 0
say keys of ages
say values of ages
remove "Bo" from ages
say ages
say ages contains "Ann"
```

```output
31
0
["Ann", "Bo", "Cy"]
[31, 25, 40]
{"Ann": 31, "Cy": 40}
true
```

## Sets

A set holds each item at most once, which is handy for "have I seen this?":

```lekh
let changeable seen be empty set
for each word in words of "the cat and the hat and the bat":
    add word to seen
say length of seen
say seen contains "cat"
let a be set of 1, 2, 3
let b be set of 2, 3, 4
say union with a, b
say intersection with a, b
say difference with a, b
```

```output
5
true
set of 1, 2, 3, 4
set of 2, 3
set of 1
```

## Queues and stacks

`take first from` removes and gives the front item (a queue);
`take last from` the back item (a stack). Both give a maybe, since the
list could be empty.

```lekh
let changeable queue be list of "Asha", "Ravi", "Mira"
let next be take first from queue
say "serving {next or else "nobody"}, waiting: {queue}"
let changeable stack be list of 1, 2, 3
say (take last from stack) or else 0
say stack
```

```output
serving Asha, waiting: ["Ravi", "Mira"]
3
[1, 2]
```

## Groups (tuples)

A group bundles a few values together without making a record:

```lekh
let point be (3, 4)
let (x, y) be point
say "x is {x}, y is {y}"
let scores be list of ("Ann", 90), ("Bo", 72)
for each (name, score) in scores:
    say "{name} scored {score}"
```

```output
x is 3, y is 4
Ann scored 90
Bo scored 72
```

Next: [7. Tasks (functions)](07-tasks.md)
