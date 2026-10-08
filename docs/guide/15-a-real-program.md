# 15. Building a real program: an expense tracker

Let's put it all together and build a small expense tracker that:

* stores expenses in a JSON file,
* adds expenses from the command line,
* checks the input and reports clear errors,
* prints a monthly report by category.

## Step 1: the data

An expense is a record. Errors get their own choice, so every caller must
handle each kind.

```lekh
record Expense:
    date as text
    category as text
    amount as number
    note as text

choice InputError:
    BadAmount with given as text
    BadDate with given as text
    MissingWords

let e be Expense with date "2026-10-01", category "food", amount 250, note "thali"
say e
```

```output
Expense(date: "2026-10-01", category: "food", amount: 250, note: "thali")
```

## Step 2: reading input safely

`parse_expense` turns words like `2026-10-02 travel 120 auto` into an Expense,
or a precise problem. `try` passes conversion problems up as our own error type.

```lekh
record Expense:
    date as text
    category as text
    amount as number
    note as text

choice InputError:
    BadAmount with given as text
    BadDate with given as text
    MissingWords

to parse_expense words as list of text gives result of Expense or InputError:
    if length of words is less than 3: give back problem MissingWords
    let date be item 1 of words
    if not (matches with date, "[0-9]{4}-[0-9]{2}-[0-9]{2}"):
        give back problem (BadDate with given date)
    let amount_text be item 3 of words
    when amount_text as number:
        is ok amount if amount is greater than 0:
            let note be join with (slice with words, 4, length of words), " "
            give back ok (Expense with date date, category item 2 of words, amount amount, note note)
        otherwise: give back problem (BadAmount with given amount_text)

to explain err as InputError gives text:
    when err:
        is BadAmount with t: give back "\"{t}\" is not a positive amount"
        is BadDate with t: give back "\"{t}\" is not a date like 2026-10-08"
        is MissingWords: give back "write: <date> <category> <amount> [note]"

for each line in list of "2026-10-02 travel 120 auto", "2026-10-02 travel abc", "yesterday food 50", "food":
    when parse_expense of (words of line):
        is ok e: say "ok: {e's category} {e's amount}"
        is problem err: say "error: {explain of err}"
```

```output
ok: travel 120
error: "abc" is not a positive amount
error: "yesterday" is not a date like 2026-10-08
error: write: <date> <category> <amount> [note]
```

## Step 3: saving and loading

Files and JSON can fail, so loading gives back a list and falls back to
an empty one when the file doesn't exist yet.

```lekh
record Expense:
    date as text
    category as text
    amount as number
    note as text

to load path as text gives list of Expense:
    let changeable out be empty list
    let data be (from_json of ((read_file of path) or else "[]")) or else (empty list)
    for each item in data:
        let date be (json_get with item, "date") or else ""
        let category be (json_get with item, "category") or else "other"
        let amount be (json_get with item, "amount") or else 0
        let note be (json_get with item, "note") or else ""
        add (Expense with date date, category category, amount amount, note note) to out
    give back out

to save path as text, expenses as list of Expense:
    write_file with path, to_json with expenses, true

let start be list of (Expense with date "2026-10-01", category "food", amount 250, note "thali")
save with "expenses.json", start
let back be load of "expenses.json"
say "{length of back} expense, first is {(first of back)'s note}"
```

```output
1 expense, first is thali
```

## Step 4: the report

Group by category with a map, sort by total, and format the money:

```lekh
record Expense:
    date as text
    category as text
    amount as number
    note as text

to report expenses as list of Expense, month as text:
    let these be keep each e in expenses where e's date starts with month
    let changeable totals be empty map
    for each e in these:
        change totals at e's category to ((totals at e's category) or else 0) + e's amount
    let ranked be sort each c in (keys of totals) by (totals at c) or else 0 descending
    say "Spending for {month}"
    for each c in ranked:
        let amount be (totals at c) or else 0
        let bar be repeat_text with "#", whole of (amount / 100)
        say "  {pad_right with c, 10}{pad_left with "₹" + (with_commas of amount), 8}  {bar}"
    say "  {pad_right with "total", 10}{pad_left with "₹" + (with_commas of (sum of (values of totals))), 8}"

let all be list of (Expense with date "2026-10-01", category "food", amount 250, note "thali"), (Expense with date "2026-10-02", category "travel", amount 120, note "auto"), (Expense with date "2026-10-03", category "food", amount 640, note "groceries"), (Expense with date "2026-10-05", category "rent", amount 1500, note ""), (Expense with date "2026-09-30", category "food", amount 99, note "last month")
report with all, "2026-10"
```

```output
Spending for 2026-10
  rent        ₹1,500  ###############
  food          ₹890  ########
  travel        ₹120  #
  total       ₹2,510
```

## Step 5: the whole program

Putting the pieces together, with commands from the command line
(`lekh run expenses.lekh add 2026-10-08 food 80 chai`, `... report 2026-10`).
With no command it runs a short demo, which is what you see below.

```lekh
-- expenses.lekh: a tiny expense tracker that keeps its data in expenses.json
record Expense:
    date as text
    category as text
    amount as number
    note as text

choice InputError:
    BadAmount with given as text
    BadDate with given as text
    MissingWords

to explain err as InputError gives text:
    when err:
        is BadAmount with t: give back "\"{t}\" is not a positive amount"
        is BadDate with t: give back "\"{t}\" is not a date like 2026-10-08"
        is MissingWords: give back "write: add <date> <category> <amount> [note]"

to parse_expense words as list of text gives result of Expense or InputError:
    if length of words is less than 3: give back problem MissingWords
    let date be item 1 of words
    if not (matches with date, "[0-9]{4}-[0-9]{2}-[0-9]{2}"):
        give back problem (BadDate with given date)
    let amount_text be item 3 of words
    when amount_text as number:
        is ok amount if amount is greater than 0:
            let note be join with (slice with words, 4, length of words), " "
            give back ok (Expense with date date, category item 2 of words, amount amount, note note)
        otherwise: give back problem (BadAmount with given amount_text)

to load path as text gives list of Expense:
    let changeable out be empty list
    let data be (from_json of ((read_file of path) or else "[]")) or else (empty list)
    for each item in data:
        let date be (json_get with item, "date") or else ""
        let category be (json_get with item, "category") or else "other"
        let amount be (json_get with item, "amount") or else 0
        let note be (json_get with item, "note") or else ""
        add (Expense with date date, category category, amount amount, note note) to out
    give back out

to save path as text, expenses as list of Expense:
    write_file with path, to_json with expenses, true

to report expenses as list of Expense, month as text:
    let these be keep each e in expenses where e's date starts with month
    if length of these is 0:
        say "No spending recorded for {month}."
        give back
    let changeable totals be empty map
    for each e in these:
        change totals at e's category to ((totals at e's category) or else 0) + e's amount
    let ranked be sort each c in (keys of totals) by (totals at c) or else 0 descending
    say "Spending for {month}"
    for each c in ranked:
        let amount be (totals at c) or else 0
        say "  {pad_right with c, 10}{pad_left with "₹" + (with_commas of amount), 8}  {repeat_text with "#", whole of (amount / 100)}"
    say "  {pad_right with "total", 10}{pad_left with "₹" + (with_commas of (sum of (values of totals))), 8}"

to handle words as list of text, path as text:
    let command be if length of words is 0 then "help" otherwise first of words
    let rest be slice with words, 2, length of words
    when command:
        is "add":
            when parse_expense of rest:
                is ok e:
                    say "Saved: {e's category} ₹{e's amount} on {e's date}"
                    let changeable all be load of path
                    add e to all
                    save with path, all
                is problem err: say "Sorry: {explain of err}"
        is "report":
            let month be if length of rest is 0 then slice with today, 1, 7 otherwise first of rest
            report with (load of path), month
        otherwise: say "Commands: add <date> <category> <amount> [note] | report [YYYY-MM]"

let args be arguments
if length of args is greater than 0:
    handle with args, "expenses.json"
otherwise:
    let demo be "demo_expenses.json"
    write_file with demo, "[]"
    for each line in list of "add 2026-10-01 food 250 thali", "add 2026-10-02 travel 120 auto", "add 2026-10-03 food 640 groceries", "add 2026-10-05 rent 1500", "add 2026-10-06 food lots", "report 2026-10", "report 2026-01":
        say "> {line}"
        handle with (words of line), demo
```

```output
> add 2026-10-01 food 250 thali
Saved: food ₹250 on 2026-10-01
> add 2026-10-02 travel 120 auto
Saved: travel ₹120 on 2026-10-02
> add 2026-10-03 food 640 groceries
Saved: food ₹640 on 2026-10-03
> add 2026-10-05 rent 1500
Saved: rent ₹1500 on 2026-10-05
> add 2026-10-06 food lots
Sorry: "lots" is not a positive amount
> report 2026-10
Spending for 2026-10
  rent        ₹1,500  ###############
  food          ₹890  ########
  travel        ₹120  #
  total       ₹2,510
> report 2026-01
No spending recorded for 2026-01.
```

Notice the order inside `is ok e:`: we print `e` *before* `add e to all`,
because adding moves `e` into the list (chapter 10). Printing it afterwards
would be caught as an ownership error.

## Where to go next

* Look at the bigger programs in [`examples/`](../../examples): a JSON to-do
  app, a concurrent web fetcher, a text adventure, a billing system with
  abilities and generics, a CSV report, an API client and a log analyzer.
* Keep the [cheat sheet](../cheatsheet.md) open while you write.
* Look things up in the [reference](../reference.md).
* Read [safety.md](../safety.md) to understand *why* Lekh stops you when it does.
* See what's coming in the [roadmap](../roadmap.md).
