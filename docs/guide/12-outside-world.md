# 12. Files, JSON, dates and the outside world

Anything that touches the outside world can fail (a missing file, no
network), so these tasks give back a **result**, and Lekh makes you handle it.

## Files

```lekh
write_file with "notes.txt", "buy milk\ncall mum\n"
append_file with "notes.txt", "pay rent\n"
when read_lines of "notes.txt":
    is ok lines:
        for each line and n in lines:
            say "{n}: {line}"
    is problem why: say "couldn't read: {why}"
say file_exists of "notes.txt"
say (file_size of "notes.txt") or else 0
say (read_file of "missing.txt") or else "(no such file)"
say extension of "photo.jpg"
say join_path with "reports", "2026", "june.csv"
```

```output
1: buy milk
2: call mum
3: pay rent
true
27
(no such file)
jpg
reports/2026/june.csv
```

Folders: `make_folder`, `list_folder`, `is_folder`, `delete_file` (files only,
never folders, to keep accidents small).

## JSON

`to_json` turns any Lekh value into JSON text. A map usually holds one kind of
value; label it `map of text to anything` when it mixes kinds, as JSON often does. `from_json` reads JSON back:
objects become maps, arrays become lists, and `null` becomes `nothing`.
`json_get` digs into nested data with a dotted path:

```lekh
let order as map of text to anything be map of "id" to 7, "items" to (list of "tea", "toast"), "paid" to true
let text be to_json of order
say text
let data be (from_json of "{{\"user\": {{\"name\": \"Asha\", \"langs\": [\"hi\", \"en\"]}}}") or else nothing
say (json_get with data, "user.name") or else "?"
say (json_get with data, "user.langs.2") or else "?"
say to_json with (list of 1, 2), true
```

```output
{"id": 7, "items": ["tea", "toast"], "paid": true}
Asha
en
[
  1,
  2
]
```

## Dates and times

A moment in time is a number of seconds. `format_time` shows it with a
pattern (`YYYY MM DD hh mm ss`, `MMMM` = month name, `DDDD` = weekday name):

```lekh
let start be (parse_date of "2026-10-08") or else 0
say format_time with start, "DDDD, DD MMMM YYYY"
let deadline be add_days with start, 30
say format_time with deadline, "DD MMM YYYY"
say days_between with start, deadline
say weekday_of of deadline
```

```output
Thursday, 08 October 2026
07 Nov 2026
30
Saturday
```

`now`, `today` and `current_time` read the clock; `seconds_since of t` measures
how long something took.

## Maths and random numbers

```lekh
say sqrt of 144
say round with (sine of (pi / 6)), 3
say clamp with 120, 0, 100
say average of (list of 3, 4, 8)
seed_random with 7
let roll be random with 1, 6
say roll is between 1 and 6
```

```output
12
0.5
100
5
true
```

## Patterns (simple regular expressions)

```lekh
say matches with "2026-10-08", "[0-9]{4}-[0-9]{2}-[0-9]{2}"
say find_all with "Order 12 has 3 items costing 450", "[0-9]+"
say replace_pattern with "call 98200-11111 now", "[0-9]{5}-[0-9]{5}", "XXXXX-XXXXX"
say find_groups with "user=asha role=admin", "(\w+)=(\w+)"
say matches_wildcard with "backup.tar.gz", "*.gz"
```

```output
true
["12", "3", "450"]
call XXXXX-XXXXX now
[["user", "asha"], ["role", "admin"]]
true
```

`{4}` in a text is left alone (it's not a name), so patterns read naturally.

## Program arguments and environment

```lekh
let args be arguments
if length of args is 0:
    say "no arguments; try: lekh run app.lekh hello"
otherwise:
    say "first argument: {first of args}"
say (environment of "LEKH_SURELY_UNSET") or else "not set"
```

```output
no arguments; try: lekh run app.lekh hello
not set
```

`read_all_input` reads everything piped in (`cat data.txt | lekh run app.lekh`),
and `exit_program with 1` stops with an exit code.

## Running other programs

`run_command` runs a program and captures what it prints:

```lekh
when run_command of "echo hello from the shell":
    is ok out: say "code {out's code}: {trimmed of out's output}"
    is problem why: say "failed: {why}"
```

```output
code 0: hello from the shell
```

> **Safety note.** `run_command` never goes through a shell: the text is split
> into words and the program is started directly. So `;`, `|`, `&&`, `$(...)`
> and `*` have no special meaning, and text from users can't sneak in extra
> commands. Each command has a 60-second limit. Even so, only run programs you
> trust, and never pass passwords on the command line.

## The web

`http_get` and `http_post` give back a `Response` with `status`, `body` and
`headers`. Only `http://` and `https://` addresses are allowed, with a
15-second limit. This sample needs the internet, so it is only *checked* here:

```lekh check
when http_get of "https://example.com":
    is ok page:
        say "status {page's status}, {length of page's body} bytes"
    is problem why:
        say "no luck: {why}"

let reply be http_post with "https://httpbin.org/post", (to_json of (map of "name" to "Asha"))
when reply:
    is ok r: say r's status
    is problem why: say why
```

Next: [13. Doing things at the same time](13-concurrency.md)
