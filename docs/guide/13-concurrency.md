# 13. Doing things at the same time

Lekh can run work side by side, for example fetching ten web pages at once
instead of one after another. The rule that keeps this safe is short:

> **Code running at the same time may read outside values, but never change
> them.** Results come back through *channels*.

This makes data races impossible: two jobs can never fight over the same list.

## `at the same time`

Every line in the block starts together; Lekh waits until they all finish:

```lekh
to slow_square n as number gives number:
    wait 0.2 seconds
    give back n * n

let results be a new channel
let started be now
at the same time:
    send (slow_square of 2) to results
    send (slow_square of 3) to results
    send (slow_square of 4) to results
close results
let changeable got be empty list
for each r in results:
    add r to got
say sorted of got
say "took less than 0.5s: {seconds_since of started is less than 0.5}"
```

```output
[4, 9, 16]
took less than 0.5s: true
```

## A loop where every round runs at once

```lekh
let names be list of "asha", "ravi", "mira"
let greeting be "hello"
let out be a new channel
for each name in names at the same time:
    send "{greeting} {name}" to out
close out
let changeable lines be empty list
for each line in out:
    add line to lines
say sorted of lines
```

```output
["hello asha", "hello mira", "hello ravi"]
```

## Channels

* `a new channel` makes one.
* `send x to ch` puts a value in (the value *moves* into the channel).
* `receive from ch` takes the next one out, as a maybe.
* `close ch` says no more is coming; `for each x in ch` then ends.

## Background jobs

`start` runs a task in the background and gives you a *job*; `wait for` gets
its answer. Jobs get their own copies of their inputs.

```lekh
to count_words text as text gives number:
    give back length of (words of text)

let job1 be start count_words with "the quick brown fox"
let job2 be start count_words with "jumps over the lazy dog today"
say "both jobs are running..."
say (wait for job1) + (wait for job2)
let jobs be turn each n in range from 1 to 3 into start count_words with repeat_text with "a ", n
say wait for jobs
```

```output
both jobs are running...
10
[1, 2, 3]
```

## What the safety rule catches

```lekh error
let changeable total be 0
for each n in list of 1, 2, 3 at the same time:
    increase total by n
say total
```

```output

-- Lekh: Ownership rule ----------------------------------------------
In sample_4.lekh, line 3:

    3 |     increase total by n

You can't increase `total` inside `at the same time` - several jobs would change it at once (a data race).

How to fix:
    Send results through a channel instead:
        let results be a new channel
        ... send value to results ...
        for each r in results: ...
```

Lending to a background job is refused too, because the job might outlive
the code that lent it. See [safety.md](../safety.md#doing-things-at-the-same-time).

Next: [14. Modules, tests and tools](14-modules-tests-tools.md)
