# 11. Abilities and generics

## Abilities: things different kinds of value can all do

An *ability* (a trait or interface in other languages) lists tasks a kind of
value promises to have. `Type can Ability` makes the promise, and Lekh checks
that it's kept.

```lekh
ability Describable:
    to describe gives text
    to shout gives text:
        give back uppercase of (me's describe)

record Dog:
    name as text

record Car:
    model as text
    year as number

to Dog's describe gives text:
    give back "{my name} the dog"

to Car's describe gives text:
    give back "a {my year} {my model}"

Dog can Describable
Car can Describable

let things as list of Describable be list of (Dog with name "Tommy"), (Car with model "Nano", year 2010)
for each t in things:
    say t's describe
    say t's shout
```

```output
Tommy the dog
TOMMY THE DOG
a 2010 Nano
A 2010 NANO
```

`shout` has a *default*: every Describable gets it for free, and any type
can write its own version instead.

Forgetting a promised task is caught:

```lekh error
ability Priced:
    to price gives number

record Pen:
    colour as text

Pen can Priced
```

```output

-- Lekh: Ability not met ---------------------------------------------
In sample_2.lekh, line 7:

    7 | Pen can Priced

`Pen` says it can `Priced`, but it has no task called `price`.

How to fix:
    Add it:
        to Pen's price gives number:
            ...
```

A task can ask for "anything with this ability" by using the ability's name
as a type (`item as Describable`), and a list can hold different record types
that share an ability (`list of Describable`), as above.

## Generics: one task for many kinds

A single capital letter in a type stands for "any type, as long as it's the
same one everywhere":

```lekh
to first_or items as list of T, fallback as T gives T:
    if length of items is 0: give back fallback
    give back first of items

say first_or with (list of 5, 6), 0
say first_or with (empty list), "none"

record Pair of A and B:
    left as A
    right as B

let p be Pair with left "age", right 30
say "{p's left} = {p's right}"
```

```output
5
none
age = 30
```

Lekh checks the letters line up:

```lekh error
to first_or items as list of T, fallback as T gives T:
    if length of items is 0: give back fallback
    give back first of items

say first_or with (list of 5, 6), "none"
```

```output

-- Lekh: Type mix-up -------------------------------------------------
In sample_4.lekh, line 5:

    5 | say first_or with (list of 5, 6), "none"

The input `fallback` of `first_or` should be a number, but here it's text.
```

Next: [12. Files, JSON, dates and the outside world](12-outside-world.md)
