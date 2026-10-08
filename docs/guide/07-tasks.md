# 7. Tasks (functions)

A *task* is a named piece of work. Define it with `to`:

```lekh
to greet person:
    say "Hello, {person}!"

greet with "Asha"
greet of "Ravi"
```

```output
Hello, Asha!
Hello, Ravi!
```

* `with` passes inputs, separated by commas: `area with 3, 4`.
* `of` reads nicely for one input: `square of 5`.
* `run` calls a task with no inputs: `run show_menu`.

## Giving back a value

```lekh
to area width as number, height as number gives number:
    give back width * height

to square n as number gives number:
    give back n * n

say area with 3, 4
say square of 5
say (square of 3) + (area with 2, 2)
```

```output
12
25
13
```

`as number` and `gives number` are optional *type labels*. They are worth
writing: Lekh then checks every call before the program starts.

```lekh error
to square n as number gives number:
    give back n * n

say square of "five"
```

```output

-- Lekh: Type mix-up -------------------------------------------------
In sample_3.lekh, line 4:

    4 | say square of "five"

The input `n` of `square` should be a number, but here it's text.

How to fix:
    Turn text into a number with a fallback:  (value as number) or else 0
```

## Leaving early

`give back` ends the task straight away. In a task that gives nothing back,
plain `give back` just leaves:

```lekh
to check_password p as text:
    if length of p is less than 8:
        say "too short"
        give back
    say "looks fine"

check_password with "abc"
check_password with "correct horse"
```

```output
too short
looks fine
```

## Tasks without names: `given`

`given` makes a small task you can store in a variable or pass to another task:

```lekh
let double be given x: x * 2
say double with 21

to apply_twice f, x:
    give back f with (f with x)

say apply_twice with double, 5

to make_adder amount as number gives task of number gives number:
    give back given x: x + amount

let add_gst be make_adder with 18
say add_gst with 100
```

```output
42
20
118
```

A `given` task gets a read-only *copy* of the outside values it uses, so it
can never change them behind your back.

## Built-in tasks

Lekh comes with over 150 built-in tasks: text, maths, files, JSON, dates,
web requests and more. They are all listed, with examples, in the
[reference](../reference.md#built-in-tasks).

Next: [8. Records and choices](08-records-and-choices.md)
