# 2. Your first real program

## Saying things

`say` prints a line. Text goes in double quotes. Anything inside `{ }` in a
text is worked out and put in its place:

```lekh
say "Namaste!"
say "2 + 3 is {2 + 3}"
let name be "Sushant"
say "Hello, {name}. Your name has {length of name} letters."
```

```output
Namaste!
2 + 3 is 5
Hello, Sushant. Your name has 7 letters.
```

You can print a number, list or anything else as well: `say 42`.
To show a real `{` write `{{`. Inside text, `\"` is a quote and `\n` starts a new line.

## Comments

Everything after `--` on a line is a note for humans. Lekh ignores it.

```lekh
-- this whole line is a comment
say "hi"   -- and so is this part
```

```output
hi
```

## Asking questions

`ask` shows a question and waits for the person to type an answer.
The answer is always text, so use `as number` to turn it into a number.
That might fail if someone types "abc", so Lekh makes you say what to do then
(here: use 0 instead, with `or else`).

```lekh stdin=Asha|29
let name be ask "What is your name?"
let age be ((ask "How old are you?") as number) or else 0
say "Hi {name}! Next year you will be {age + 1}."
```

```output
What is your name? Asha
How old are you? 29
Hi Asha! Next year you will be 30.
```

## How Lekh tells you about mistakes

Lekh checks the whole program before running it. When something is wrong, it
says where, why, and how to fix it:

```lekh error
let total be 10
change total to 20
```

```output

-- Lekh: This can't be changed ---------------------------------------
In sample_4.lekh, line 2:

    2 | change total to 20

You tried to change `total`, but it was created with plain `let` on line 1, so it can never change.

How to fix:
    If it really needs to change, create it as changeable:
        let changeable total be ...
```

Lekh also understands words from other languages and points you to the Lekh way:

```lekh error
print("hello")
```

```output

-- Lekh: I couldn't understand this line -----------------------------
In sample_5.lekh, line 1:

    1 | print("hello")

I don't know the word `print`.

How to fix:
    Lekh says `say` instead of `print`.
```

Next: [3. Values and variables](03-values-and-variables.md)
