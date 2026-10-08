# How Lekh keeps your programs safe

Lekh promises that a program which passes its checks can't hit these bugs:

| Bug in other languages | How Lekh prevents it |
|---|---|
| `null` / `None` crashes | there is no null; a missing value is a **maybe** you must check |
| ignored errors | work that can fail gives a **result** you must handle |
| changing data that someone else is using | **ownership**: one owner at a time, borrowing is explicit |
| changing a list while looping over it | caught before the program runs |
| two threads changing the same data (data race) | code running **at the same time** can't change outside values |
| forgetting a case | `when` must handle every kind of a choice |
| mixing up types | type labels are checked before the program runs |
| silent wrong numbers | whole numbers never overflow; dividing by zero is a clear error |

Most of these are found by `lekh check` (and before every `lekh run`), so
you see them before anything happens. A few depend on values only known while
running (an empty list, a key that isn't there) and stop the program with a
clear message instead of carrying on with nonsense.

This page explains each idea in plain words.

## 1. Changing things is a choice you write down

A value made with `let` never changes. If it must, write `let changeable`.
Reading code is easier when you know most names stay put.

```lekh
let rate be 0.18
let changeable total be 100
increase total by total * rate
say total
```

```output
118
```

```lekh error
let rate be 0.18
change rate to 0.2
```

```output

-- Lekh: This can't be changed ---------------------------------------
In sample_2.lekh, line 2:

    2 | change rate to 0.2

You tried to change `rate`, but it was created with plain `let` on line 1, so it can never change.

How to fix:
    If it really needs to change, create it as changeable:
        let changeable rate be ...
```

## 2. Ownership: one owner at a time

Small values (numbers, text, truths) are copied whenever you use them, so
they're always safe. Bigger values (lists, maps, sets, records) have
**exactly one owner**. When you write `let b be a`, the list *moves* from `a`
to `b`; `a` can no longer be used. This prevents the classic surprise where
changing one name secretly changes another:

```lekh error
let changeable mine be list of 1, 2
let changeable yours be mine
add 3 to yours
say mine
```

```output

-- Lekh: Ownership rule ----------------------------------------------
In sample_3.lekh, line 4:

    4 | say mine

`mine` can't be used here because it was given away on line 2 (moved into `yours`). Each list, map or record has exactly one owner at a time.

How to fix:
    If you still need `mine`, give away a copy on line 2 instead:
        copy of mine
```

In Python or JavaScript, that program prints `[1, 2, 3]`, which is often a bug.
In Lekh you say what you mean: `copy of mine` for two separate lists.

```lekh
let changeable mine be list of 1, 2
let changeable yours be copy of mine
add 3 to yours
say mine
say yours
```

```output
[1, 2]
[1, 2, 3]
```

Values move into lists, maps, records and channels the same way
(`add e to all` moves `e` into `all`).

## 3. Borrowing: look, lend or give

Passing a value to a task doesn't move it. By default the task can only
**look** (a read-only borrow). To let it change the value, **lend** it. To
hand it over for good, **give** it.

```lekh
to show items as list of text:
    say join with items, ", "

to add_extra changeable items as list of text:
    add "extra" to items

to take_away owned as list of text gives number:
    give back length of owned

let changeable bag be list of "pen", "book"
show with bag
add_extra with lend bag
show with bag
say take_away with give bag
```

```output
pen, book
pen, book, extra
3
```

The rules for borrowing:

* A task can't change something it only got to look at.
* Only a `changeable` variable can be lent, and the task must ask for it
  (`changeable` in front of the input name).
* After `give`, the old name is gone.

```lekh error
to sneaky items as list of text:
    add "surprise" to items

let changeable bag be list of "pen"
sneaky with bag
```

```output

-- Lekh: This can't be changed ---------------------------------------
In sample_6.lekh, line 2:

    2 |     add "surprise" to items

You tried to add to `items`, but this task only *looks* at that input (it's shared, read-only).

How to fix:
    To let the task change it, mark the input changeable in the task header:
        to sneaky ... changeable items ...:
    and lend it when calling:  sneaky with lend <variable>
```

## 4. Loops can't pull the rug out

While a `for each` goes through a list, that list can't grow or shrink.

```lekh error
let changeable queue be list of 1, 2, 3
for each n in queue:
    remove n from queue
```

```output

-- Lekh: Ownership rule ----------------------------------------------
In sample_7.lekh, line 3:

    3 |     remove n from queue

You can't remove from `queue` while looping over it - the loop would lose its place.

How to fix:
    Collect the changes in a separate list during the loop, and apply them after it ends.
```

To change every item in place, use `for each changeable`:

```lekh
let changeable prices be list of 10, 20
for each changeable p in prices:
    change p to p * 2
say prices
```

```output
[20, 40]
```

## 5. No null: maybe

Looking up a key, searching a list, or taking from an empty queue gives a
**maybe**: `some value` or `nothing`. Lekh won't let you use it until you
say what happens when it's `nothing`.

```lekh
let capitals be map of "India" to "New Delhi", "Japan" to "Tokyo"
say (capitals at "India") or else "?"
say (capitals at "Mars") or else "?"
when capitals at "Japan":
    is some city: say "Japan's capital is {city}"
    is nothing: say "unknown"
```

```output
New Delhi
?
Japan's capital is Tokyo
```

```lekh error
let capitals be map of "India" to "New Delhi"
say "Capital: " + capitals at "India"
```

```output

-- Lekh: Possibly missing value --------------------------------------
In sample_10.lekh, line 2:

    2 | say "Capital: " + capitals at "India"

This value might be nothing, so it can't be used in math yet. Lekh has no null - a maybe value must be checked before use.

How to fix:
    Give a fallback:   (value or else 0)
    or check it first:
        when value:
            is some v: ...
            is nothing: ...
```

## 6. No ignored errors: result

Anything that can fail (reading a file, converting text, a web request, or
your own tasks) gives a **result**: `ok value` or `problem why`. Like a maybe,
it must be handled. `try` passes a problem on to the caller, like Rust's `?`.

```lekh
to read_age t as text gives result of number or text:
    let n be try (t as number)
    if n is less than 0 or n is greater than 150:
        give back problem "{n} is not a believable age"
    give back ok n

for each t in list of "34", "old", "200":
    when read_age of t:
        is ok age: say "age {age}"
        is problem why: say "problem: {why}"
```

```output
age 34
problem: "old" is not a number
problem: 200 is not a believable age
```

Using a choice as the problem type (`result of number or LoginError`) lets
`when` check that every kind of error is handled. See
[guide chapter 9](guide/09-maybe-and-result.md).

## 7. Every case handled

A `when` on a choice, maybe or result must handle every possibility (or have
an `otherwise`). Add a new kind to a choice and Lekh lists every `when` that
needs updating.

## 8. Doing things at the same time

Code inside `at the same time` (or a `for each ... at the same time` loop)
runs side by side. The rules:

* It may **read** outside values; each job sees its own copy.
* It may **not change** outside variables, or give them away.
* Results come back through **channels**; sending a value moves it.
* Background jobs (`start`) get copies of their inputs and can't borrow
  (`lend`), because a job might outlive the code that started it.

```lekh error
let changeable seen be empty list
for each n in list of 1, 2 at the same time:
    add n to seen
```

```output

-- Lekh: Ownership rule ----------------------------------------------
In sample_12.lekh, line 3:

    3 |     add n to seen

You can't add to `seen` inside `at the same time` - several jobs would change it at once (a data race).

How to fix:
    Send results through a channel instead:
        let results be a new channel
        ... send value to results ...
        for each r in results: ...
```

```lekh error
to fill changeable xs as list of number:
    add 1 to xs

let changeable data be empty list
let job be start fill with lend data
```

```output

-- Lekh: Ownership rule ----------------------------------------------
In sample_13.lekh, line 5:

    5 | let job be start fill with lend data

A background job can't borrow `data` - it might outlive this code.

How to fix:
    Pass it normally (the job gets its own copy) or hand it over with `give`.
```

## 9. Types

Type labels (`as number`, `gives text`, `list of Expense`) are optional, but
every one you write is checked before the program runs, including inside
generic tasks. Values without labels are checked as the program runs instead.
Lekh is *gradually typed*: the more labels you write, the more mistakes are
caught early.

```lekh error
record Item:
    name as text
    price as number

let pen be Item with name "pen", price "ten"
```

```output

-- Lekh: Type mix-up -------------------------------------------------
In sample_14.lekh, line 5:

    5 | let pen be Item with name "pen", price "ten"

The field `price` of an Item should be a number, but here it's text.
```

## 10. What Lekh does *not* protect against

To be clear about the limits:

* **Logic mistakes**: Lekh can't know you meant `+` and wrote `-`. Write tests.
* **Running out of memory or time**: an endless loop will loop forever.
* **Values only known while running**: `item 5 of` a 3-item list, dividing by
  a variable that is 0, or `fail` stop the program with a clear message. They
  don't crash silently, but they aren't caught ahead of time either.
* **Unlabelled code**: without type labels, type mistakes are found when
  that line runs, not before.
* **The outside world**: `run_command` and HTTP talk to real systems.
  `run_command` never uses a shell (no command injection through `;` or `|`),
  but the programs you run can still do anything your user account can.
* Lekh runs on Python, so the guarantees are enforced by Lekh's checker and
  runtime, not by hardware or a compiler like Rust's.
