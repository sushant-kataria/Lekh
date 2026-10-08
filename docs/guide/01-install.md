# 1. Installing Lekh and running your first file

Lekh is a small programming language that reads like plain English but has the
safety rules of Rust: no crashes from missing values, no accidental sharing of data.

## What you need

* **Python 3.8 or newer**. Check with `python3 --version`.
* Nothing else. Lekh has no extra packages to install.

## Get Lekh

```bash
git clone https://github.com/sushant-kataria/Lekh.git
cd Lekh
python3 lekh.py version
```

Instead of typing `python3 lekh.py` every time, you can add a short command:

```bash
# Linux / macOS: put this in ~/.bashrc or ~/.zshrc
alias lekh="python3 /path/to/lekh/lekh.py"
```

On Windows, use `py lekh.py ...` in place of `lekh ...`.
The rest of this guide writes `lekh`.

## Your first program

Make a file called `hello.lekh`:

```lekh
say "Hello, world!"
```

```output
Hello, world!
```

Then run it:

```bash
lekh run hello.lekh        # or simply: lekh hello.lekh
```

## The commands you will use

| Command | What it does |
|---|---|
| `lekh run app.lekh` | run a program (anything after the file name goes to the program) |
| `lekh check app.lekh` | look for mistakes without running |
| `lekh test` | run the `test` blocks in a project or folder |
| `lekh format app.lekh` | tidy the layout (`--check` only reports) |
| `lekh build app.lekh` | turn the program into a fast Python file |
| `lekh new my_app` | start a new project folder |
| `lekh repl` | try lines out one at a time |
| `lekh help` | list everything |

## Trying things in the REPL

`lekh repl` gives you a prompt where each line runs straight away:

```text
lekh> let price be 250
lekh> say price * 2
500
lekh> :vars
  let price = 250
lekh> :quit
```

Type `:help` to see the other commands: `:type`, `:load`, `:reset`.

Next: [2. Your first real program](02-first-program.md)
