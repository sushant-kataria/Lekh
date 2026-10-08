# 10. Ownership: who owns a value

Lekh borrows Rust's best idea, in plain words. **Every list, map, set and
record has exactly one owner.** Small values (numbers, text, truths) are simply
copied, so they never cause trouble.

When you pass a value to a task, you choose one of three words:

| You write | The task may | Afterwards, you |
|---|---|---|
| `f with x` | only **look** at `x` | still have `x`, unchanged |
| `f with lend x` | **change** `x` | have the changed `x` back |
| `f with give x` | **keep** `x` for good | can't use `x` any more |

```lekh
to total prices as list of number gives number:
    give back sum of prices

to add_tax changeable prices as list of number:
    for each changeable p in prices:
        change p to p * 1.1

to archive owned as list of number gives text:
    give back "archived {length of owned} prices"

let changeable prices be list of 100, 200
say total of prices
add_tax with lend prices
say prices
say archive with give prices
```

```output
300
[110.0, 220.0]
archived 2 prices
```

After `give prices`, using `prices` again is caught before the program runs:

```lekh error
let changeable prices be list of 100, 200
let basket be prices
say prices
```

```output

-- Lekh: Ownership rule ----------------------------------------------
In sample_2.lekh, line 3:

    3 | say prices

`prices` can't be used here because it was given away on line 2 (moved into `basket`). Each list, map or record has exactly one owner at a time.

How to fix:
    If you still need `prices`, give away a copy on line 2 instead:
        copy of prices
```

When you need two independent lists, say so with `copy of`:

```lekh
let original be list of 1, 2, 3
let changeable mine be copy of original
add 4 to mine
say original
say mine
```

```output
[1, 2, 3]
[1, 2, 3, 4]
```

That's all you need day to day. [The safety guide](../safety.md) explains the
full set of rules, why they exist, and how they keep concurrent code safe.

Next: [11. Abilities and generics](11-abilities-and-generics.md)
