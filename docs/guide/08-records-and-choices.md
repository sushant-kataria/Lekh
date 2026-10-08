# 8. Records and choices

## Records: your own kinds of value

```lekh
record Book:
    title as text
    pages as number
    read as truth

let changeable book be Book with title "Godaan", pages 312, read false
say "{book's title} has {book's pages} pages"
change book's read to true
say book
```

```output
Godaan has 312 pages
Book(title: "Godaan", pages: 312, read: true)
```

## Methods: tasks that belong to a record

Write `to Type's name`. Inside, `me` is the record and `my field` reads a field.
A method that changes its record says `changes me`:

```lekh
record Counter:
    count as number

to Counter's describe gives text:
    give back "counted {my count} times"

to Counter's click by as number changes me:
    increase my count by by

let changeable c be Counter with count 0
c's click with 1
c's click with 5
say c's describe
```

```output
counted 6 times
```

## Choices: a value that is one of several kinds

```lekh
choice Shape:
    Circle with radius as number
    Rectangle with width as number, height as number
    Dot

to area s as Shape gives number:
    when s:
        is Circle with r: give back round with 3.14159 * r * r, 2
        is Rectangle with w, h: give back w * h
        is Dot: give back 0

let shapes be list of (Circle with radius 1), (Rectangle with width 2, height 5), Dot
for each s in shapes:
    say area of s
```

```output
3.14
10
0
```

If you forget a case, Lekh tells you before running, so adding a new kind of
shape can never be half-finished:

```lekh error
choice Light:
    Red
    Amber
    Green

to action l as Light gives text:
    when l:
        is Red: give back "stop"
        is Green: give back "go"

say action of Red
```

```output

-- Lekh: Unhandled case ----------------------------------------------
In sample_4.lekh, line 7:

    7 |     when l:

This `when` doesn't say what to do for: Amber. Every option of `Light` must be handled, so nothing slips through.

How to fix:
    Add a case for each, e.g.:
        is Amber: ...
    or add `otherwise:` at the end.
```

## Patterns in `when`

Cases can look inside values and add an `if` guard:

```lekh
choice Order:
    Pizza with size as text, extra_cheese as truth
    Drink with name as text

let orders be list of (Pizza with size "large", extra_cheese true), (Pizza with size "small", extra_cheese false), (Drink with name "lassi")
for each o in orders:
    when o:
        is Pizza with size, cheese if cheese: say "{size} pizza, extra cheese"
        is Pizza with size, cheese: say "{size} pizza"
        is Drink with "lassi": say "a sweet lassi"
        is Drink with name: say name
```

```output
large pizza, extra cheese
small pizza
a sweet lassi
```

Next: [9. Missing values and errors](09-maybe-and-result.md)
