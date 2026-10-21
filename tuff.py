"""Tuff - the language behind TuffCode. Run a program with: python tuff.py file.tuf"""
import base64
import difflib
import inspect
import math
import os
import random
import re
import sys
import tempfile
import time

IDE = os.environ.get("TUFF_IDE") == "1"
# Echo typed answers back, so a run fed from a file reads like a real session (the MCP tuff_run tool).
ECHO_INPUT = os.environ.get("TUFF_ECHO_INPUT") == "1"

KEYWORDS = {
    "func", "return", "if", "elif", "else", "then", "while", "for", "in", "break", "continue",
    "and", "or", "not", "is", "true", "false", "nil", "say", "input", "flush", "import", "mention",
}


class TuffError(Exception):
    def __init__(self, msg, line=None, col=None):
        super().__init__(msg)
        self.msg = msg
        self.line = line
        self.col = col


# ---------------------------------------------------------------- tokenizer

class Tok:
    __slots__ = ("kind", "value", "line", "col")

    def __init__(self, kind, value, line, col):
        self.kind, self.value, self.line, self.col = kind, value, line, col

    def show(self):
        if self.kind == "STR":
            return f'"{self.value}"'
        if self.kind in ("NEWLINE", "EOF"):
            return "the end of the line"
        if self.kind in ("INDENT", "DEDENT"):
            return "indentation"
        return str(self.value)


ESCAPES = {"n": "\n", "t": "\t", "\\": "\\", '"': '"', "'": "'"}


def source_lines(src):
    """The program's lines, numbered as the editor numbers them. Only a newline ends a line: splitlines() would
    also break at U+2028, U+0085, a form feed and others, cutting a text that holds one in two."""
    lines = src.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if lines[-1] == "":  # a newline at the very end doesn't start another line
        lines.pop()
    return lines


def tokenize(src):
    toks = []
    indents = [0]
    depth = 0
    lines = source_lines(src)
    for ln, raw in enumerate(lines, 1):
        stripped = raw.lstrip(" \t")
        if depth == 0:
            if not stripped or stripped.startswith("#"):
                continue
            width = sum(4 if ch == "\t" else 1 for ch in raw[: len(raw) - len(stripped)])
            if width > indents[-1]:
                indents.append(width)
                toks.append(Tok("INDENT", None, ln, 1))
            else:
                while width < indents[-1]:
                    indents.pop()
                    toks.append(Tok("DEDENT", None, ln, 1))
                if width != indents[-1]:
                    raise TuffError("This line's indentation doesn't line up with any block above it.", ln, 1)
        i = len(raw) - len(stripped)
        n = len(raw)
        while i < n:
            c = raw[i]
            col = i + 1
            if c in " \t":
                i += 1
            elif c == "#":
                break
            elif c.isdigit():
                j = i
                while j < n and raw[j].isdigit():
                    j += 1
                if j + 1 < n and raw[j] == "." and raw[j + 1].isdigit():
                    j += 1
                    while j < n and raw[j].isdigit():
                        j += 1
                    toks.append(Tok("NUM", float(raw[i:j]), ln, col))
                else:
                    toks.append(Tok("NUM", int(raw[i:j]), ln, col))
                i = j
            elif c.isalpha() or c == "_":
                j = i
                while j < n and (raw[j].isalnum() or raw[j] == "_"):
                    j += 1
                word = raw[i:j]
                toks.append(Tok("KW" if word in KEYWORDS else "NAME", word, ln, col))
                i = j
            elif c in "\"'":
                j = i + 1
                out = []
                while j < n and raw[j] != c:
                    if raw[j] == "\\" and j + 1 < n:
                        out.append(ESCAPES.get(raw[j + 1], "\\" + raw[j + 1]))  # unknown escapes stay as written, like C:\Users
                        j += 2
                    else:
                        out.append(raw[j])
                        j += 1
                if j >= n:
                    raise TuffError(f"This text is missing its closing {c}", ln, col)
                toks.append(Tok("STR", "".join(out), ln, col))
                i = j + 1
            elif c == ":":
                glued = i > 0 and raw[i - 1] not in " \t" and i + 1 < n and (raw[i + 1].isalpha() or raw[i + 1] == "_")
                toks.append(Tok("METHOD" if glued else "COLON", ":", ln, col))
                i += 1
            elif raw[i:i + 2] in ("==", "!=", "<=", ">=", "+=", "-=", "*=", "/="):
                toks.append(Tok("OP", raw[i:i + 2], ln, col))
                i += 2
            elif c in "+-*/%^<>=()[],.":
                if c in "([":
                    depth += 1
                elif c in ")]":
                    depth = max(0, depth - 1)
                toks.append(Tok("OP", c, ln, col))
                i += 1
            elif not c.isprintable():  # U+2028, a form feed, a no-break space: nothing to see between the quotes
                raise TuffError(f"There's a hidden character here (U+{ord(c):04X}) that Tuff doesn't understand. "
                                "Delete it, or type this line again.", ln, col)
            else:
                raise TuffError(f"I don't understand the character '{c}'.", ln, col)
        if depth == 0:
            toks.append(Tok("NEWLINE", None, ln, n + 1))
    end = len(lines) + 1
    while len(indents) > 1:
        indents.pop()
        toks.append(Tok("DEDENT", None, end, 1))
    toks.append(Tok("EOF", None, end, 1))
    return toks


# ---------------------------------------------------------------- parser

class N:
    def __init__(self, kind, tok, **fields):
        self.kind = kind
        self.line = tok.line
        self.col = tok.col
        self.__dict__.update(fields)


EXPR_STARTS = {"NUM", "STR", "NAME"}
EXPR_START_KWS = {"say", "input", "not", "true", "false", "nil"}
ASSIGN_OPS = {"=", "+=", "-=", "*=", "/="}
COMPARE_OPS = {"==", "!=", "<", ">", "<=", ">="}


class Parser:
    def __init__(self, toks):
        self.toks = toks
        self.i = 0

    def peek(self):
        return self.toks[self.i]

    def next(self):
        tok = self.toks[self.i]
        self.i += 1
        return tok

    def at(self, kind, value=None):
        tok = self.toks[self.i]
        return tok.kind == kind and (value is None or tok.value == value)

    def expect(self, kind, value=None, msg=None):
        if not self.at(kind, value):
            tok = self.peek()
            raise TuffError(msg or f"Expected '{value or kind}' but found {tok.show()}.", tok.line, tok.col)
        return self.next()

    def starts_expr(self):
        tok = self.peek()
        return (
            tok.kind in EXPR_STARTS
            or (tok.kind == "OP" and tok.value in ("(", "[", "-"))
            or (tok.kind == "KW" and tok.value in EXPR_START_KWS)
        )

    def program(self):
        body = []
        while not self.at("EOF"):
            if self.at("NEWLINE"):
                self.next()
            elif self.at("INDENT"):
                tok = self.peek()
                raise TuffError("This line is indented, but it isn't inside a block.", tok.line, tok.col)
            else:
                body.append(self.statement())
        return body

    def block(self, opener_optional=False):
        tok = self.peek()
        # A ':' glued to the next word (then:say "hi", else:say, func f():say) is read as a method's ':', but no
        # method call can start here, so it's this block's ':'.
        if self.at("COLON") or self.at("METHOD") or self.at("KW", "then"):
            # "then:" works too: people often write both.
            if self.next().kind == "KW" and (self.at("COLON") or self.at("METHOD")):
                self.next()
        elif not (opener_optional and self.at("NEWLINE")):
            # if x:say "hi" -> x:say was read as a method call, so the block's ':' seems to be missing
            j = self.i - 1
            while j >= 0 and self.toks[j].line == tok.line and self.toks[j].kind != "METHOD":
                j -= 1
            after = self.toks[j + 1] if j >= 0 and self.toks[j].kind == "METHOD" and self.toks[j].line == tok.line else None
            tip = " Put a space after the ':' that starts the block (with a word right after it, ':' is read as a method)." \
                if after is not None and ((after.kind == "KW" and after.value in ("say", "return", "break", "continue", "flush"))
                                          or (tok.kind == "OP" and tok.value in ASSIGN_OPS)) else ""
            raise TuffError(f"Expected ':' or 'then' to start a block, but found {tok.show()}.{tip}", tok.line, tok.col)
        if not self.at("NEWLINE"):
            stmt = self.simple_statement()
            self.end_line()
            return [stmt]
        self.next()
        if not self.at("INDENT"):
            nxt = self.peek()
            raise TuffError("This block is empty. Indent the lines that belong inside it.", nxt.line, nxt.col)
        self.next()
        body = []
        while not self.at("DEDENT") and not self.at("EOF"):
            if self.at("NEWLINE"):
                self.next()
            else:
                body.append(self.statement())
        if self.at("DEDENT"):
            self.next()
        return body

    def statement(self):
        tok = self.peek()
        if tok.kind == "KW":
            if tok.value == "func":
                return self.func_def()
            if tok.value == "if":
                return self.if_stmt()
            if tok.value == "while":
                self.next()
                cond = self.expr()
                return N("while", tok, cond=cond, body=self.block())
            if tok.value == "for":
                self.next()
                name = self.expect("NAME", msg="Expected a variable name after 'for'.").value
                self.expect("KW", "in", msg="Expected 'in' after the loop variable, like: for item in items:")
                items = self.expr()
                return N("for", tok, name=name, items=items, body=self.block())
            if tok.value in ("elif", "else"):
                raise TuffError(f"'{tok.value}' needs an 'if' right above it.", tok.line, tok.col)
            if tok.value in ("import", "mention"):
                self.next()
                name = self.expect("NAME", msg=f"Expected a library name, like: {tok.value} anims").value
                self.end_line()
                return N("import", tok, name=name)
        stmt = self.simple_statement()
        self.end_line()
        return stmt

    def func_def(self):
        tok = self.next()
        name = self.expect("NAME", msg="Expected a name for the function, like: func greet(name):").value
        params = []
        if self.at("OP", "("):
            self.next()
            while not self.at("OP", ")"):
                params.append(self.expect("NAME", msg="Function inputs must be simple names.").value)
                if not self.at("OP", ")"):
                    self.expect("OP", ",", msg="Separate function inputs with commas.")
            self.next()
        return N("func", tok, name=name, params=params, body=self.block())

    def if_stmt(self):
        tok = self.next()
        branches = [(self.expr(), self.block())]
        else_body = None
        while True:
            if self.at("KW", "elif"):
                self.next()
                branches.append((self.expr(), self.block()))
            elif self.at("KW", "else"):
                self.next()
                if self.at("KW", "if"):
                    self.next()
                    branches.append((self.expr(), self.block()))
                    continue
                else_body = self.block(opener_optional=True)
                break
            else:
                break
        return N("if", tok, branches=branches, else_body=else_body)

    def simple_statement(self):
        tok = self.peek()
        if self.at("KW", "return"):
            self.next()
            value = self.expr() if self.starts_expr() else None
            return N("return", tok, value=value)
        if self.at("KW", "break") or self.at("KW", "continue"):
            self.next()
            return N(tok.value, tok)
        if self.at("KW", "flush"):
            self.next()
            if self.at("OP", "("):
                self.next()
                self.expect("OP", ")", msg="flush doesn't take any inputs. Use clear(3) to remove just a few lines.")
            return N("flush", tok)
        target = self.expr()
        if self.at("OP") and self.peek().value in ASSIGN_OPS:
            op = self.next().value
            if target.kind not in ("var", "index"):
                raise TuffError("You can only store a value in a variable or a list item.", tok.line, tok.col)
            return N("assign", tok, target=target, op=op, value=self.expr())
        return N("expr", tok, expr=target)

    def end_line(self):
        if self.at("NEWLINE"):
            self.next()
        elif not (self.at("EOF") or self.at("DEDENT")):
            tok = self.peek()
            raise TuffError(f"I didn't expect {tok.show()} here.", tok.line, tok.col)

    # expressions, lowest precedence first
    def expr(self):
        tok = self.peek()
        if self.at("KW", "say"):
            self.next()
            return N("say", tok, value=self.expr())
        if self.at("KW", "input"):
            self.next()
            if self.at("OP", "("):
                self.next()
                prompt = None if self.at("OP", ")") else self.expr()
                self.expect("OP", ")")
            else:
                prompt = self.expr() if self.starts_expr() else None
            return N("input", tok, prompt=prompt)
        return self.or_expr()

    def or_expr(self):
        left = self.and_expr()
        while self.at("KW", "or"):
            tok = self.next()
            left = N("or", tok, left=left, right=self.and_expr())
        return left

    def and_expr(self):
        left = self.not_expr()
        while self.at("KW", "and"):
            tok = self.next()
            left = N("and", tok, left=left, right=self.not_expr())
        return left

    def not_expr(self):
        if self.at("KW", "not"):
            tok = self.next()
            return N("not", tok, value=self.not_expr())
        return self.compare()

    def compare(self):
        left = self.add()
        while True:
            tok = self.peek()
            if tok.kind == "OP" and tok.value in COMPARE_OPS:
                self.next()
                op = tok.value
            elif self.at("KW", "is"):
                self.next()
                op = "=="
                if self.at("KW", "not"):
                    self.next()
                    op = "!="
            else:
                return left
            left = N("binop", tok, op=op, left=left, right=self.add())

    def add(self):
        left = self.mul()
        while self.at("OP", "+") or self.at("OP", "-"):
            tok = self.next()
            left = N("binop", tok, op=tok.value, left=left, right=self.mul())
        return left

    def mul(self):
        left = self.unary()
        while self.at("OP", "*") or self.at("OP", "/") or self.at("OP", "%"):
            tok = self.next()
            left = N("binop", tok, op=tok.value, left=left, right=self.unary())
        return left

    def unary(self):
        if self.at("OP", "-"):
            tok = self.next()
            return N("neg", tok, value=self.unary())
        return self.power()

    def power(self):
        base = self.postfix()
        if self.at("OP", "^"):
            tok = self.next()
            return N("binop", tok, op="^", left=base, right=self.unary())
        return base

    def call_args(self, closer):
        args = []
        while not self.at("OP", closer):
            args.append(self.expr())
            if not self.at("OP", closer):
                self.expect("OP", ",", msg=f"Expected ',' or '{closer}'.")
        self.next()
        return args

    def member_name(self, msg):
        if self.at("NAME") or self.at("KW"):
            return self.next().value
        tok = self.peek()
        raise TuffError(msg, tok.line, tok.col)

    def postfix(self):
        node = self.primary()
        while True:
            tok = self.peek()
            if self.at("OP", "("):
                self.next()
                node = N("call", tok, fn=node, args=self.call_args(")"))
            elif self.at("OP", "["):
                self.next()
                index = self.expr()
                self.expect("OP", "]")
                node = N("index", tok, obj=node, index=index)
            elif self.at("OP", "."):
                self.next()
                name = self.member_name("Expected a name after '.', like: anims.loading()")
                node = N("attr", tok, obj=node, name=name)
            elif self.at("METHOD"):
                self.next()
                name_tok = self.peek()
                name = self.member_name("Expected a method name after ':'.")
                bare = spaced = False  # bare: an input without brackets takes the rest of the expression
                if self.at("OP", "("):
                    nxt = self.peek()
                    spaced = nxt.line == name_tok.line and nxt.col > name_tok.col + len(name)  # name (x): a space before the bracket
                    self.next()
                    args = self.call_args(")")
                elif self.starts_expr():
                    args = [self.expr()]
                    bare = True
                else:
                    args = []
                node = N("method", tok, obj=node, name=name, args=args, bare=bare, spaced=spaced)
            else:
                return node

    def primary(self):
        tok = self.next()
        if tok.kind in ("NUM", "STR"):
            return N("const", tok, value=tok.value)
        if tok.kind == "NAME":
            return N("var", tok, name=tok.value)
        if tok.kind == "KW" and tok.value in ("true", "false", "nil"):
            return N("const", tok, value={"true": True, "false": False, "nil": None}[tok.value])
        if tok.kind == "OP" and tok.value == "(":
            inner = self.expr()
            self.expect("OP", ")")
            return inner
        if tok.kind == "OP" and tok.value == "[":
            return N("list", tok, items=self.call_args("]"))
        raise TuffError(f"I expected a value here, but found {tok.show()}.", tok.line, tok.col)


# ---------------------------------------------------------------- runtime

class Func:
    def __init__(self, name, params, body, env, line=None):
        self.name, self.params, self.body, self.env, self.line = name, params, body, env, line


class Builtin:
    def __init__(self, name, fn, takes_err=False):
        self.name, self.fn = name, fn
        self.takes_err = takes_err  # number(), text(), print()...: an err given to them doesn't stop the program


class Line:
    def __init__(self, id_, text, row):
        self.id, self.text, self.row = id_, text, row


class Module:
    def __init__(self, name, members):
        self.name, self.members = name, members


class Native:
    """An object made by a library (like a tgui button) with its own :methods."""

    def __init__(self, kind, methods, show=None):
        self.kind, self.methods = kind, methods
        self.show = show  # show(nested) gives the text say shows for it, like a tap data object's JSON


class AllLines:
    pass


ALL = AllLines()


# err: what number(), int() and num() give back for text that isn't a number, so a program can check
# (if num(bet) is err:) instead of stopping. Every err is "is err". Using one in maths, or anywhere a value
# is needed, stops the program with the reason it's an err.
class Err:
    def __init__(self, why=""):
        self.why = why

    def stop(self, doing=""):
        tip = " Check for it first with: if x is err" if self.why else ""
        raise TuffError(f"{doing or 'That value'} is err{': ' + self.why if self.why else ''}.{tip}")


ERR = Err()
LIBRARIES = ("anims", "tgui", "mtgui", "tap", "atgui", "tgame")
# Libraries whose windows are web views (tuff_view.py). A program that uses one runs its Tuff code on a
# second thread, because the web view needs the main thread.
VIEW_LIBRARIES = ("atgui", "tgame")
VIEW_IMPORT = re.compile(r"^[ \t]*(?:import|mention)[ \t]+(?:" + "|".join(VIEW_LIBRARIES) + r")\b", re.M)
# The first line a tgame program shows, in yellow, before anything it prints. In TuffCode the line gets an
# "Open Tuff Engine" button (ide.js handleOsc). --check, --scene and --windowed apps never show it.
TGAME_NOTICE = "Tuff Engine is here: open this game in TuffCode's Tuff Engine tab (Ctrl+Shift+G) to build it visually."
TGAME_IMPORT = re.compile(r"^[ \t]*(?:import|mention)[ \t]+tgame\b", re.M)
BUILTIN_NAMES = {"print", "number", "num", "text", "str", "int", "len", "round", "random", "wait", "range", "clear", "sqrt", "abs",
                 "floor", "ceil", "min", "max", "sum", "average"}
# Built-ins that are new in Tuff 1.0.4 and that people already use as their own variables (num = 0, err = "...").
# Giving one a value inside a function makes that function's own variable, as it did before they were built in,
# and the built-in stays for the rest of the program. At the top of the program it still replaces the built-in.
OWN_NAME_BUILTINS = {"num", "int", "str", "err"}


# return, break and continue on their way out. They keep their line, for when there's nothing to catch them.
class ReturnSignal(Exception):
    def __init__(self, value, line=None, col=None):
        self.value, self.line, self.col = value, line, col


class BreakSignal(Exception):
    def __init__(self, line=None, col=None):
        self.line, self.col = line, col


class ContinueSignal(Exception):
    def __init__(self, line=None, col=None):
        self.line, self.col = line, col


def b64(text):
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def to_text(v, nested=False):
    if v is None:
        return "nil"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else repr(v)
    if isinstance(v, str):
        return f'"{v}"' if nested else v
    if isinstance(v, list):
        return "[" + ", ".join(to_text(x, True) for x in v) + "]"
    if isinstance(v, Line):
        return to_text(v.text, nested)
    if isinstance(v, (Func, Builtin)):
        return f"<func {v.name}>"
    if isinstance(v, Module):
        return f"<library {v.name}>"
    if isinstance(v, Native):
        return v.show(nested) if v.show else f"<{v.kind}>"
    if v is ALL:
        return "all"
    if isinstance(v, Err):
        return "err"
    return str(v)


def type_name(v):
    if v is None:
        return "nil"
    if isinstance(v, bool):
        return "true/false"
    if isinstance(v, (int, float)):
        return "a number"
    if isinstance(v, str):
        return "text"
    if isinstance(v, list):
        return "a list"
    if isinstance(v, Line):
        return "a line"
    if isinstance(v, Module):
        return "a library"
    if isinstance(v, Native):
        return f"a {v.kind}"
    if v is ALL:
        return "all"
    if isinstance(v, Err):
        return "err"
    return "a function"


def truthy(v):
    if isinstance(v, Line):
        return True
    if isinstance(v, Err):
        return False
    return v not in (None, False, 0, "") and v != []


def plain(v):
    return v.text if isinstance(v, Line) else v


def call_python(label, fn, args, takes_err=False):
    """Call a built-in written in Python, turning Python problems into friendly Tuff errors."""
    try:
        inspect.signature(fn).bind(*args)
    except TypeError:
        raise TuffError(f"{label} got the wrong number of inputs ({len(args)}).")
    except ValueError:
        pass
    if not takes_err:  # an err stops here with the reason it's an err, before Python can say something confusing
        for a in args:
            if isinstance(plain(a), Err):
                plain(a).stop(f"The input to {label}")
    try:
        return fn(*args)
    except (TuffError, ReturnSignal, BreakSignal, ContinueSignal, KeyboardInterrupt, SystemExit, RecursionError):
        raise
    except Exception as exc:
        raise TuffError(f"{label} failed: {exc}")


class Console:
    def __init__(self, first_id=1):
        self.next_id = first_id
        self.rows = 0

    def write(self, text):
        sys.stdout.write(text)
        sys.stdout.flush()

    def say(self, text, style=None):
        """Show a line. style "notice" shows it in yellow: through the line protocol in the IDE, with an ANSI
        color in a terminal, and as plain text when the output goes to a file or a pipe."""
        line = Line(self.next_id, text, self.rows)
        self.next_id += 1
        if IDE:
            self.write(f"\x1b]tuff;say;{line.id};{b64(text)}{';' + style if style else ''}\x07\n")
        elif style == "notice" and sys.stdout.isatty():
            self.write(f"\x1b[33m{text}\x1b[0m\n")
        else:
            self.write(text + "\n")
        self.rows += text.count("\n") + 1
        return line

    def rewrite(self, line, text):
        line.text = text
        if IDE:
            self.write(f"\x1b]tuff;rewrite;{line.id};{b64(text)}\x07")
            return
        up = self.rows - line.row
        if up > 0:
            self.write(f"\x1b[{up}A\r\x1b[2K{text}\x1b[{up}B\r")

    def clear(self, count=None):
        if IDE:
            self.write(f"\x1b]tuff;clear;{'all' if count is None else count}\x07")
        elif count is None:
            self.write("\x1b[2J\x1b[H")
        else:
            self.write("\x1b[1A\x1b[2K" * min(count, self.rows) + "\r")
        self.rows = 0 if count is None else max(0, self.rows - count)

    def input(self, prompt):
        self.write(prompt)
        data = sys.stdin.readline()
        if data == "":
            raise TuffError("The program asked for an answer, but there was no more input to read.")
        self.rows += 1
        answer = data.lstrip("﻿").rstrip("\r\n")
        if ECHO_INPUT:
            self.write(answer + "\n")
        return answer


class Env:
    def __init__(self, parent=None, own_names=False):
        self.vars = {}
        self.parent = parent
        self.own_names = own_names  # holds OWN_NAME_BUILTINS: giving one of them a value makes a new variable

    def find(self, name):
        env = self
        while env is not None:
            if name in env.vars:
                return env
            env = env.parent
        return None

    def get(self, name):
        env = self.find(name)
        if env is None:
            known = []
            e = self
            while e is not None:
                known.extend(e.vars)
                e = e.parent
            if name in LIBRARIES:
                raise TuffError(f"'{name}' is a library. Add  import {name}  at the top of your file to use it.")
            hint = difflib.get_close_matches(name, known, n=1, cutoff=0.6)
            extra = f" Did you mean '{hint[0]}'?" if hint else " Give it a value first, like: " + name + " = 5"
            raise TuffError(f"I don't know what '{name}' is.{extra}")
        return env.vars[name]

    def set(self, name, value):
        env = self.find(name)
        if env is None or env.own_names:
            env = self
        env.vars[name] = value


class Runtime:
    """The small toolbox libraries (like tgui) use to talk to the interpreter."""

    def __init__(self, interp):
        self.interp = interp
        self.finish_hooks = []

    def text(self, v):
        return to_text(plain(v))

    def plain(self, v):
        return plain(v)

    def what(self, v):
        """'text', 'a number', 'a data object'... for messages."""
        return type_name(plain(v))

    def number(self, v, what="This"):
        v = plain(v)
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise TuffError(f"{what} needs a number, not {type_name(v)}.")
        return v

    def truthy(self, v):
        return truthy(v)

    def callable(self, v):
        return isinstance(v, (Func, Builtin))

    def error(self, msg):
        return TuffError(msg)

    def native(self, kind, methods, show=None):
        return Native(kind, methods, show)

    def builtin(self, name, fn):
        return Builtin(name, fn)

    def path(self, p):
        p = self.text(p)
        return p if os.path.isabs(p) else os.path.join(self.interp.base_dir, p)

    def on_finish(self, fn):
        self.finish_hooks.append(fn)

    def call(self, fn, *args):
        """Run a Tuff function from a library callback. Errors are reported, not raised."""
        try:
            return True, self.interp.invoke(fn, list(args), loose=True)
        except TuffError as err:
            if err.line is None and getattr(fn, "line", None):  # e.g. a click function asking for inputs
                err.line = fn.line
            report(err, self.interp.src)
        except RecursionError:
            report(TuffError(f"{getattr(fn, 'name', 'This function')}() called itself too many times."), self.interp.src)
        except (BreakSignal, ContinueSignal) as sig:
            report(TuffError("'break' and 'continue' can only be used inside a loop.", sig.line, sig.col), self.interp.src)
        return False, None


class Interpreter:
    def __init__(self, src="", base_dir="."):
        self.src = src
        self.base_dir = base_dir
        self.rt = Runtime(self)
        self.console = Console()
        self.own_names = Env(own_names=True)  # OWN_NAME_BUILTINS, just above the program's own top-level names
        self.globals = Env(self.own_names)
        builtins = {
            "print": self.b_print,
            "number": self.b_number,
            "text": lambda v: to_text(plain(v)),
            # The names people bring from Python: str is text, int is a whole number.
            "str": lambda v: to_text(plain(v)),
            "int": self.b_int,
            "num": lambda v: self.b_number(v, "num"),
            "len": self.b_len,
            "round": lambda v, digits=0: round(self.num_arg("round", v), int(digits)) if digits else round(self.num_arg("round", v)),
            "random": self.b_random,
            "wait": self.b_wait,
            "range": self.b_range,
            "clear": self.b_clear,
            "sqrt": lambda v: self.math1("sqrt", v, math.sqrt, lambda x: x >= 0, "can't take the square root of a negative number"),
            "abs": lambda v: abs(self.num_arg("abs", v)),
            "floor": lambda v: math.floor(self.num_arg("floor", v)),
            "ceil": lambda v: math.ceil(self.num_arg("ceil", v)),
            "min": lambda *v: min(self.num_list("min", v)),
            "max": lambda *v: max(self.num_list("max", v)),
            "sum": lambda *v: sum(self.num_list("sum", v, allow_empty=True)),
            "average": lambda *v: (lambda nums: sum(nums) / len(nums))(self.num_list("average", v)),
        }
        takes_err = {"number", "num", "int", "text", "str", "print"}  # they hand an err back, or show it as "err"
        for name, fn in builtins.items():
            (self.own_names if name in OWN_NAME_BUILTINS else self.globals).vars[name] = Builtin(name, fn, name in takes_err)
        self.globals.vars["all"] = ALL
        self.globals.vars["pi"] = math.pi
        self.own_names.vars["err"] = ERR

    # math helpers
    def num_arg(self, name, v):
        v = plain(v)
        if isinstance(v, Err):
            v.stop(f"The input to {name}()")
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise TuffError(f"{name}() needs a number, not {type_name(v)}.")
        return v

    def math1(self, name, v, fn, ok, why):
        v = self.num_arg(name, v)
        if not ok(v):
            raise TuffError(f"{name}() {why}.")
        result = fn(v)
        return int(result) if isinstance(result, float) and result.is_integer() else result

    def num_list(self, name, values, allow_empty=False):
        if len(values) == 1 and isinstance(plain(values[0]), list):
            values = plain(values[0])
        nums = [self.num_arg(name, v) for v in values]
        if not nums and not allow_empty:
            raise TuffError(f"{name}() needs at least one number, like {name}(3, 8, 5) or {name}(scores).")
        return nums

    # libraries
    def lib_tgui(self):
        try:
            import tuff_tgui
        except ImportError:
            raise TuffError("tgui needs Python's tkinter, which isn't installed. Reinstall Python and tick 'tcl/tk and IDLE'.")
        return tuff_tgui.make_library(self.rt)

    def lib_mtgui(self):
        try:
            import tuff_tgui
        except ImportError:
            raise TuffError("mtgui needs Python's tkinter, which isn't installed. Reinstall Python and tick 'tcl/tk and IDLE'.")
        return tuff_tgui.make_library(self.rt, modern=True)

    def lib_tap(self):
        try:
            import tuff_tap
        except ImportError as exc:
            raise TuffError(f"tap couldn't load ({exc}). Reinstall TuffCode.")
        return tuff_tap.make_library(self.rt)

    def lib_atgui(self):
        try:
            import tuff_atgui
        except ImportError as exc:
            raise TuffError(f"atgui couldn't load ({exc}). Reinstall TuffCode.")
        return tuff_atgui.make_library(self.rt)
    def lib_tgame(self):
        try:
            import tuff_tgame
        except ImportError as exc:
            raise TuffError(f"tgame couldn't load ({exc}). Reinstall TuffCode.")
        return tuff_tgame.make_library(self.rt)

    def lib_anims(self):
        con = self.console
        spin = "/-\\|"

        def loading(text="Loading", seconds=2):
            text = to_text(text)
            line = con.say(f"/ {text}")
            frames = max(1, round(float(seconds) / 0.1))
            for i in range(frames):
                con.rewrite(line, f"{spin[i % 4]} {text}{'.' * (i // 3 % 4)}")
                time.sleep(0.1)
            con.rewrite(line, f"✓ {text}... done")
            return line

        def bar(text="Working", seconds=2, width=20):
            text = to_text(text)
            width = max(5, int(width))
            line = con.say("")
            steps = max(1, round(float(seconds) / 0.05))
            for i in range(steps + 1):
                filled = round(width * i / steps)
                con.rewrite(line, f"{text} [{'█' * filled}{'░' * (width - filled)}] {round(100 * i / steps):>3}%")
                if i < steps:
                    time.sleep(0.05)
            return line

        def type_(text, speed=0.04):
            text = to_text(text)
            line = con.say("")
            for i in range(1, len(text) + 1):
                con.rewrite(line, text[:i])
                time.sleep(max(0, float(speed)))
            return line

        def countdown(start=3, then="Go!"):
            n = int(plain(start))
            line = con.say(str(n))
            for i in range(n - 1, 0, -1):
                time.sleep(1)
                con.rewrite(line, str(i))
            time.sleep(1)
            con.rewrite(line, to_text(then))
            return line

        fns = {"loading": loading, "bar": bar, "type": type_, "countdown": countdown}
        return {name: Builtin(f"anims.{name}", fn) for name, fn in fns.items()}

    def b_clear(self, count=ALL):
        count = plain(count)
        if count is ALL:
            self.console.clear(None)
            return None
        if not isinstance(count, (int, float)) or isinstance(count, bool) or count < 0:
            raise TuffError("clear() needs a number of lines, like clear(2), or clear(all).")
        self.console.clear(int(count))
        return None

    # builtins
    def b_print(self, *args):
        return self.console.say(" ".join(to_text(a) for a in args))

    def b_number(self, v, name="number"):
        # Text that isn't a number gives err (check with: if number(t) is err) instead of stopping the program.
        # Anything else that isn't a number (a text box, nil, a list...) is a mistake in the program, so it stops.
        v = plain(v)
        if isinstance(v, Err):
            return v
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return v
        if isinstance(v, Native) and "value" in v.methods:  # a text box, a slider... (or a tgame text sprite)
            thing = "sprite" if v.kind == "sprite" else f"{v.kind} widget"
            raise TuffError(f"{name}() needs text or a number, not the {thing}. Add :value() to get what's in it.")
        if not isinstance(v, str):
            raise TuffError(f"{name}() needs text or a number, not {type_name(v)}.")
        try:
            s = v.strip()
            return float(s) if "." in s else int(s)
        except ValueError:
            return Err(f"{name}() couldn't turn '{to_text(v)}' into a number")

    def b_int(self, v):
        # A whole number, dropping any decimals toward zero: int("42") is 42, int(3.7) and int("3.7") are 3.
        n = self.b_number(v, "int")
        return n if isinstance(n, Err) else int(n)

    def b_len(self, v):
        v = plain(v)
        if not isinstance(v, (str, list)):
            raise TuffError(f"len() needs text or a list, not {type_name(v)}.")
        return len(v)

    def b_random(self, *ends):
        if not 1 <= len(ends) <= 2:
            raise TuffError("random() needs a range, like random(1, 6), or just the top, like random(6).")
        nums = [self.num_arg("random", v) for v in ends]
        if any(isinstance(v, float) and not v.is_integer() for v in nums):
            raise TuffError("random() needs whole numbers, like random(1, 6). For a decimal, divide: random(0, 100) / 100.")
        low, high = (1, nums[0]) if len(nums) == 1 else nums
        if low > high:
            raise TuffError(f"random({to_text(low)}, {to_text(high)}): the first number must be the smaller one.")
        return random.randint(int(low), int(high))

    def b_wait(self, seconds):
        sys.stdout.flush()
        time.sleep(max(0, float(seconds)))

    def b_range(self, a, b=None, step=1):
        if b is None:
            a, b = 1, a
        a, b, step = int(a), int(b), int(step)
        if step == 0:
            raise TuffError("range() can't count in steps of 0.")
        return list(range(a, b + (1 if step > 0 else -1), step))

    # statements
    def run_block(self, body, env):
        result = None
        for stmt in body:
            result = self.run(stmt, env)
        return result

    def run(self, s, env):
        try:
            return getattr(self, "s_" + s.kind)(s, env)
        except TuffError as e:
            if e.line is None:
                e.line, e.col = s.line, s.col
            raise

    def s_expr(self, s, env):
        return self.eval(s.expr, env)

    def s_assign(self, s, env):
        value = self.eval(s.value, env)
        if s.op != "=":
            value = self.binop(s.op[0], self.eval(s.target, env), value)
        if s.target.kind == "var":
            env.set(s.target.name, value)
        else:
            obj = plain(self.eval(s.target.obj, env))
            if not isinstance(obj, list):
                raise TuffError(f"You can only set items in a list, not in {type_name(obj)}.")
            obj[self.list_index(obj, self.eval(s.target.index, env))] = value
        return value

    def s_if(self, s, env):
        for cond, body in s.branches:
            if truthy(self.eval(cond, env)):
                return self.run_block(body, env)
        if s.else_body is not None:
            return self.run_block(s.else_body, env)
        return None

    def s_while(self, s, env):
        while truthy(self.eval(s.cond, env)):
            try:
                self.run_block(s.body, env)
            except BreakSignal:
                break
            except ContinueSignal:
                continue
        return None

    def s_for(self, s, env):
        items = plain(self.eval(s.items, env))
        if isinstance(items, bool) or isinstance(items, (int, float)):
            raise TuffError(f"Can't loop over a number. Try: for {s.name} in range({to_text(items)}):")
        if not isinstance(items, (list, str)):
            owner = s.items.name if s.items.kind == "var" else "thing"
            tip = f" Loop over its names instead: for {s.name} in {owner}:keys():" if isinstance(items, Native) and "keys" in items.methods else ""
            raise TuffError(f"Can't loop over {type_name(items)}.{tip}")
        for item in list(items):
            env.set(s.name, item)
            try:
                self.run_block(s.body, env)
            except BreakSignal:
                break
            except ContinueSignal:
                continue
        return None

    def s_func(self, s, env):
        env.vars[s.name] = Func(s.name, s.params, s.body, env, s.line)
        return None

    def s_import(self, s, env):
        if s.name not in LIBRARIES:
            hint = difflib.get_close_matches(s.name, LIBRARIES, n=1, cutoff=0.5)
            extra = f" Did you mean '{hint[0]}'?" if hint else f" Available libraries: {', '.join(LIBRARIES)}."
            raise TuffError(f"There's no library called '{s.name}'.{extra}")
        env.set(s.name, Module(s.name, getattr(self, "lib_" + s.name)()))
        return None

    def s_flush(self, s, env):
        self.console.clear(None)
        return None

    def s_return(self, s, env):
        raise ReturnSignal(None if s.value is None else self.eval(s.value, env), s.line, s.col)

    def s_break(self, s, env):
        raise BreakSignal(s.line, s.col)

    def s_continue(self, s, env):
        raise ContinueSignal(s.line, s.col)

    # expressions
    def eval(self, e, env):
        try:
            return self.eval_node(e, env)
        except TuffError as err:
            if err.line is None:
                err.line, err.col = e.line, e.col
            raise

    def eval_node(self, e, env):
        k = e.kind
        if k == "const":
            return e.value
        if k == "var":
            return env.get(e.name)
        if k == "say":
            return self.console.say(to_text(self.eval(e.value, env)))
        if k == "input":
            prompt = "" if e.prompt is None else to_text(self.eval(e.prompt, env))
            return self.console.input(prompt)
        if k == "binop":
            return self.binop(e.op, self.eval(e.left, env), self.eval(e.right, env))
        if k == "and":
            left = self.eval(e.left, env)
            return self.eval(e.right, env) if truthy(left) else left
        if k == "or":
            left = self.eval(e.left, env)
            return left if truthy(left) else self.eval(e.right, env)
        if k == "not":
            return not truthy(self.eval(e.value, env))
        if k == "neg":
            v = plain(self.eval(e.value, env))
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                raise TuffError(f"Can't make {type_name(v)} negative.")
            return -v
        if k == "list":
            return [self.eval(x, env) for x in e.items]
        if k == "index":
            obj = plain(self.eval(e.obj, env))
            if not isinstance(obj, (list, str)):
                owner = e.obj.name if e.obj.kind == "var" else "thing"
                tip = f" Use :get instead, like {owner}:get(\"name\")." if isinstance(obj, Native) and "keys" in obj.methods else ""
                raise TuffError(f"Can't use [ ] on {type_name(obj)}.{tip}")
            return obj[self.list_index(obj, self.eval(e.index, env))]
        if k == "call":
            return self.call(e, env)
        if k == "method":
            return self.method(e, env)
        if k == "attr":
            obj = self.eval(e.obj, env)
            if not isinstance(obj, Module):
                kind = "list" if isinstance(obj, list) else "text" if isinstance(obj, str) else None
                raise TuffError(dot_help(type_name(obj), e.obj, e.name, kind))
            if e.name not in obj.members:
                raise TuffError(f"{obj.name} doesn't have '{e.name}'. It has: {', '.join(obj.members)}.")
            return obj.members[e.name]
        raise TuffError(f"Internal error: unknown expression '{k}'.")

    def list_index(self, obj, index):
        index = plain(index)
        if not isinstance(index, int) or isinstance(index, bool):
            raise TuffError(f"List positions must be whole numbers, not {type_name(index)}.")
        if not -len(obj) <= index < len(obj):
            raise TuffError(f"Position {index} is outside this {'list' if isinstance(obj, list) else 'text'} (it has {len(obj)} items, starting at 0).")
        return index

    def binop(self, op, a, b):
        a, b = plain(a), plain(b)
        if isinstance(a, Err) or isinstance(b, Err):
            # "x is err" is true for every err; anything else done with an err stops with its reason.
            if op == "==":
                return isinstance(a, Err) and isinstance(b, Err)
            if op == "!=":
                return not (isinstance(a, Err) and isinstance(b, Err))
            (a if isinstance(a, Err) else b).stop(f"Can't use {op} here, because one side")
        num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
        if op == "+":
            if isinstance(a, str) or isinstance(b, str):
                return to_text(a) + to_text(b)
            if num(a) and num(b):
                return a + b
            if isinstance(a, list) and isinstance(b, list):
                return a + b
        elif op == "==":
            return a == b and type(a) is type(b) or (num(a) and num(b) and a == b)
        elif op == "!=":
            return not self.binop("==", a, b)
        elif op in ("<", ">", "<=", ">="):
            if (num(a) and num(b)) or (isinstance(a, str) and isinstance(b, str)):
                return {"<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[op]
            raise TuffError(f"Can't compare {type_name(a)} with {type_name(b)} using {op}.")
        elif op == "*":
            if num(a) and num(b):
                return a * b
            if isinstance(a, str) and isinstance(b, int) and not isinstance(b, bool):
                return a * b
            if isinstance(b, str) and isinstance(a, int) and not isinstance(a, bool):
                return b * a
        elif num(a) and num(b):
            if op == "-":
                return a - b
            if op == "^":
                try:
                    result = a ** b
                except (OverflowError, ZeroDivisionError):
                    raise TuffError("That number is too big (or impossible) to work out.")
                if isinstance(result, complex):
                    raise TuffError("A negative number can't be raised to a fraction.")
                return result
            if b == 0:
                raise TuffError("You can't divide by zero.")
            if op == "/":
                return a / b
            if op == "%":
                return a % b
        verb = {"+": "add", "-": "subtract", "*": "multiply", "/": "divide", "%": "use % on", "^": "use ^ on"}[op]
        raise TuffError(f"Can't {verb} {type_name(a)} and {type_name(b)}.")

    def call(self, e, env):
        fn = self.eval(e.fn, env)
        if e.fn.kind == "var" and e.fn.name in BUILTIN_NAMES and not isinstance(fn, (Builtin, Func)):
            raise TuffError(f"'{e.fn.name}' was given a value ({to_text(fn, True)}), so it isn't the built-in {e.fn.name}() any more. Use another name for your variable.")
        args = [self.eval(a, env) for a in e.args]
        return self.invoke(fn, args)

    def invoke(self, fn, args, loose=False):
        if isinstance(fn, Builtin):
            return call_python(fn.name + "()", fn.fn, args, fn.takes_err)
        if isinstance(fn, Func):
            if loose and len(args) > len(fn.params):
                args = args[: len(fn.params)]
            if len(args) != len(fn.params):
                want = len(fn.params)
                raise TuffError(f"{fn.name}() needs {want} input{'s' if want != 1 else ''}, but got {len(args)}.")
            local = Env(fn.env)
            local.vars.update(zip(fn.params, args))
            try:
                return self.run_block(fn.body, local)
            except ReturnSignal as r:
                return r.value
            except RecursionError:
                raise TuffError(f"{fn.name}() called itself too many times.")
        raise TuffError(f"{to_text(fn, True)} isn't a function, so it can't be called with ( ).")

    def method(self, e, env):
        obj = self.eval(e.obj, env)
        args = [self.eval(a.value if a.kind == "say" else a, env) for a in e.args]
        name = e.name

        def need(count):
            if len(args) != count:
                raise TuffError(f":{name} needs {count} input{'s' if count != 1 else ''}.")

        def no_inputs():
            if args:
                raise TuffError(f":{name} doesn't take an input. Write :{name}() or just :{name}.")

        if isinstance(obj, Native):
            fn = obj.methods.get(name)
            if fn is None:
                options = [m for m in obj.methods if m != "page" or obj.kind == "window"]
                raise TuffError(method_help(a_kind(obj.kind).capitalize(), name, options))
            return call_python(f"{obj.kind}:{name}", fn, args)

        if isinstance(obj, Line):
            if name == "rewrite":
                need(1)
                self.console.rewrite(obj, to_text(args[0]))
                return obj
            if name == "append":
                need(1)
                self.console.rewrite(obj, obj.text + to_text(args[0]))
                return obj
            if name == "clear":
                no_inputs()
                self.console.rewrite(obj, "")
                return obj
            if name == "text":
                no_inputs()
                return obj.text
            what, kind = "A line", "line"
        elif isinstance(obj, str):
            simple = {"upper": str.upper, "lower": str.lower, "trim": str.strip}
            if name in simple:
                no_inputs()
                return simple[name](obj)
            if name == "has":
                need(1)
                return to_text(args[0]) in obj
            what, kind = "Text", "text"
        elif isinstance(obj, list):
            if name == "add":
                need(1)
                obj.append(args[0])
                return obj
            # Same matching as 'is': true and 1 are different things.
            spot = lambda: next((i for i, x in enumerate(obj) if self.binop("==", x, args[0])), None)
            if name == "remove":
                need(1)
                i = spot()
                if i is None:
                    raise TuffError(f"{to_text(args[0], True)} isn't in this list.")
                del obj[i]
                return obj
            if name == "pop":
                if args:
                    raise TuffError(":pop doesn't take a position: it always takes the last item. Read another item with items[...] and take it out with :remove.")
                if not obj:
                    raise TuffError("Can't pop from an empty list.")
                return obj.pop()
            if name == "has":
                need(1)
                return spot() is not None
            what, kind = "A list", "list"
        else:
            raise TuffError(f"{type_name(obj).capitalize()} doesn't have any :methods.")
        raise TuffError(method_help(what, name, SIMPLE_METHODS[kind], kind))


# ---------------------------------------------------------------- checking without running

# Python habits that are plain names in Tuff, and what to write instead.
PY_NAMES = {
    "True": "Tuff writes true in lowercase.",
    "False": "Tuff writes false in lowercase.",
    "None": "Tuff writes nil for 'nothing'.",
    "float": "To turn text into a number, use number(text).",
    "math": "sqrt, floor, ceil, abs, round and pi are built in, so there's nothing to import.",
    "time": "Use wait(seconds) to pause. In an app, app:every(seconds, fn) runs something again and again.",
    "length": "Use len(value) for how long some text or a list is.",
    "self": "Tuff has no classes. Keep things in variables and functions.",
}
# Methods from other languages, and the Tuff method that does the same job.
PY_METHODS = {
    "list": {"append": "add", "push": "add", "insert": "add", "contains": "has", "includes": "has", "delete": "remove", "discard": "remove"},
    "text": {"strip": "trim", "contains": "has", "includes": "has", "upper_case": "upper", "lower_case": "lower",
             "uppercase": "upper", "lowercase": "lower", "toupper": "upper", "tolower": "lower"},
}
SIMPLE_METHODS = {"text": ("upper", "lower", "trim", "has"), "list": ("add", "remove", "pop", "has"), "line": ("rewrite", "append", "clear", "text")}
ONE_INPUT = {"has", "add", "remove", "rewrite", "append"}


def a_kind(kind):
    return f"{'an' if kind[:1] in 'aeiou' else 'a'} {kind}"


def method_help(what, name, options, kind=None):
    """'A list doesn't have :append. Use :add instead.' (or a close match, or every option)."""
    alt = PY_METHODS.get(kind, {}).get(name.lower())
    if alt in options:
        return f"{what} doesn't have :{name}. Use :{alt} instead."
    hint = difflib.get_close_matches(name, list(options), n=1, cutoff=0.6)
    if hint:
        return f"{what} doesn't have :{name}. Did you mean :{hint[0]}?"
    return f"{what} doesn't have :{name}. Try one of: {', '.join(options)}."


def dot_help(what, obj_node, name, kind=None):
    """For thing.name when thing isn't a library: methods use ':'."""
    alt = PY_METHODS.get(kind, {}).get(name.lower(), name)
    owner = obj_node.name if getattr(obj_node, "kind", None) == "var" else "thing"
    return f"Only libraries use '.', and this is {what}. For methods use ':', like {owner}:{alt}"


def leaves_folder(path, folder):
    """Does this file path point outside the folder ("../cat.png", or a full path somewhere else)? A relative path
    is judged on its own; a full path only when the folder is known."""
    if not os.path.isabs(path):
        return os.path.normpath(path).replace("\\", "/").split("/")[0] == ".."
    if not folder:
        return False
    folder = os.path.normcase(os.path.abspath(folder))
    try:
        return os.path.commonpath([os.path.normcase(os.path.abspath(path)), folder]) != folder
    except ValueError:  # on another drive
        return True


def accepts(fn, count):
    """Can fn be called with this many inputs? (True when we can't tell.)"""
    try:
        inspect.signature(fn).bind(*([None] * count))
        return True
    except TypeError:
        return False
    except ValueError:
        return True


_GUI = None


class Anything:
    """Stands in for whatever a widget touches while it lists its methods, so no window is made."""

    def __getattr__(self, name):
        if name.startswith("__"):  # let Python's own lookups (like __signature__) fail normally
            raise AttributeError(name)
        return Anything()

    def __call__(self, *args, **kwargs):
        return Anything()


def gui_tables():
    """The methods of every tgui/mtgui window and widget (name -> the function behind it), read from
    the library itself without opening a window, plus the styles and colors it accepts.
    None when tkinter isn't available."""
    global _GUI
    if _GUI is None:
        _GUI = {}
        try:
            import tuff_tgui as tg

            class FakeRt(Anything):
                def native(self, kind, methods):
                    return methods

                def builtin(self, name, fn):
                    return fn

            lib = Anything()
            lib.rt = FakeRt()

            def probe_attr(self, name):
                if name.startswith("__"):
                    raise AttributeError(name)
                return Anything()

            def probe(cls, **fields):
                obj = object.__new__(type("Probe", (cls,), {"__getattr__": probe_attr}))
                obj.__dict__.update(lib=lib, app=obj, children=[], hidden=False, **fields)
                return obj

            kinds = {"window": tg.App.native(probe(tg.App))}
            for style in ("heading", "text", "small"):
                kinds[style] = probe(tg.Label, kind=style, style=style).methods()
            for cls in (tg.Button, tg.Input, tg.Dropdown, tg.Toggle, tg.Checkbox, tg.Slider, tg.Progress, tg.Spinner,
                        tg.Clock, tg.Image, tg.Divider, tg.Space, tg.Row, tg.Card, tg.Page):
                kinds[cls.kind] = probe(cls).methods()
            libs = {name: tg.make_library(FakeRt(), modern=name == "mtgui") for name in ("tgui", "mtgui")}
            _GUI = {"kinds": kinds, "libs": libs, "styles": tuple(tg.BUTTON_STYLES), "clocks": tuple(tg.CLOCK_STYLES),
                    "colors": set(tg.NAMED_COLORS) | set(tg.GRADIENTS) | {"accent", "text", "muted"},
                    "accents": list(tg.ACCENTS), "themes": set(tg.THEMES)}
        except Exception:
            _GUI = {}
    return _GUI or None


_TAP = None


def tap_tables():
    """tap's functions ("lib") and the methods of its responses and data objects ("kinds"), read from
    the library itself without going online. None when it can't be loaded."""
    global _TAP
    if _TAP is None:
        try:
            import tuff_tap
            _TAP = tuff_tap.tables()
        except Exception:
            _TAP = {}
    return _TAP or None


_ATGUI = None


def atgui_tables():
    """atgui's functions, every kind's methods ("kinds"), what makers make, and the styles, icons, themes and
    animations it knows, read from the library itself without opening a window. None when it can't be loaded."""
    global _ATGUI
    if _ATGUI is None:
        try:
            import tuff_atgui
            _ATGUI = tuff_atgui.tables()
        except Exception:
            _ATGUI = {}
    return _ATGUI or None


_TGAME = None


def tgame_tables():
    """tgame's functions ("lib"), the methods of everything it makes ("kinds"), what they give back, its events,
    hints for guessed names and a check for text inputs, read from the library without opening a window.
    None when it can't be loaded."""
    global _TGAME
    if _TGAME is None:
        try:
            import tuff_tgame
            _TGAME = tuff_tgame.tables()
        except Exception:
            _TGAME = {}
    return _TGAME or None


def nodes(x):
    """Every node inside a node, or inside a list of nodes."""
    if isinstance(x, N):
        yield x
        for v in x.__dict__.values():
            yield from nodes(v)
    elif isinstance(x, (list, tuple)):
        for v in x:
            yield from nodes(v)


def is_hex_color(text):
    return len(text) == 7 and text[0] == "#" and all(c in "0123456789abcdef" for c in text[1:])


class Scope:
    """The names a function (or the top of the program) makes for itself."""

    def __init__(self, parent=None, name=None):
        self.parent, self.name = parent, name
        self.names = set()
        self.funcs = {}

    def chain(self):
        s = self
        while s is not None:
            yield s
            s = s.parent


# Methods that other languages have, with the Tuff way to do it, for "nothing in Tuff has :x".
PY_ONLY = {
    "split": "Tuff can't split text. Go through it letter by letter with a for loop.",
    "join": "Join text with +.",
    "replace": "Tuff can't replace inside text. Build new text with + in a loop.",
    "format": "Join text with +, like \"Hi \" + name.",
    "startswith": "Compare the first letter: t[0] is \"a\".",
    "endswith": "Compare the last letter: t[-1] is \"a\".",
    "find": "Use :has to check, like t:has(\"a\").",
    "index": "Loop with a counter to find a position.",
    "count": "Loop and count with a variable.",
    "sort": "Tuff has no sort. Sort with a loop, or keep the list in order as you add.",
    "reverse": "Build a reversed list with a loop.",
    "keys": "Tuff has no dictionaries. Keep two lists side by side.",
    "items": "Tuff has no dictionaries. Keep two lists side by side.",
    "values": "Tuff has no dictionaries. Keep two lists side by side.",
    "get": "Tuff has no dictionaries. Keep two lists side by side.",
    "extend": "Join lists with +, like items = items + more.",
    "isdigit": "Use the is_number pattern from the guide.",
    "capitalize": "Use t[0]:upper() + the rest built with a loop.",
}


class Checker:
    """Finds mistakes without running the program. It only reports what is certain to go wrong
    when that line runs, so correct code is never flagged. It knows which names each function
    makes for itself, what kind of value most names hold, and every window and widget method."""

    CONTAINERS = ("window", "row", "card", "page")
    TYPE = {"$text": "text", "$list": "a list", "$line": "a line", "$number": "a number", "$bool": "true/false",
            "$nil": "nil", "$func": "a function", "$builtin": "a function"}
    NUMBER_FNS = {"number", "num", "int", "len", "random", "round", "sqrt", "abs", "floor", "ceil", "min", "max", "sum", "average"}
    NUMBER_INPUT_FNS = {"round", "floor", "ceil", "abs", "sqrt", "min", "max", "sum", "average"}  # these fail on text
    MATHS = ("+", "-", "*", "/", "%", "^")
    COMPARE = ("==", "!=", "<", ">", "<=", ">=")
    ORDER = ("<", ">", "<=", ">=")
    ZERO_INPUT = {"upper", "lower", "trim", "pop", "clear", "text"}  # list/text/line methods without inputs
    TEXT_VALUE = {"input", "heading", "text", "small", "button", "dropdown", "clock"}  # :value() gives text
    # What each event hands its function, and where the function goes in the call. A function may
    # take fewer inputs than it's given (extras are dropped), not more.
    EVENT_GIVES = {"click": (0, "a button click"), "button": (0, "a button click"), "opened": (0, ":opened"),
                   "every": (0, ":every"), "after": (0, ":after"), "change": (1, ":change"), "enter": (1, ":enter")}
    HANDLER_POS = {"click": 0, "opened": 0, "change": 0, "enter": 0, "button": 1, "every": 1, "after": 1,
                   "every_frame": 0, "on_key": 1, "clicked": 0, "game_over": 1}
    TGAME_KINDS = ("game", "world", "sprite", "object", "player", "hud", "group")  # what tgame makes
    # What tap's functions make, and what the methods of those give back (left out: it depends, like :json).
    TAP_MAKES = {"get": "response", "post": "response", "put": "response", "delete": "response", "data": "data object"}
    TAP_GIVES = {"response": {"status": "$number", "ok": "$bool", "text": "$text"},
                 "data object": {"has": "$bool", "keys": "$list", "size": "$number", "set": "data object"}}

    def __init__(self, program, base_dir=None):
        self.program = program
        self.problems = []
        self.funcs = {}  # top-level functions: name -> params (made at the top, or in a top-level block)
        self.func_nodes = {}
        self.func_count = {}
        self.assigned = {}
        self.params = set()
        self.loop_vars = set()
        self.imports = set()
        self.interp = Interpreter()
        self.builtins = {**self.interp.own_names.vars, **self.interp.globals.vars}
        self.memo = {}
        self.anims = None
        self.calls = {}  # name -> every line it's called on, like name(...)
        self.top = Scope()
        self.scope_of = {}  # id(func node) -> its Scope
        self.everywhere = set()  # every name made anywhere
        self.makes_window = False
        self.handlers_seen = set()
        self.statement_call = None  # a call on a line of its own: its answer isn't used
        self.base_dir = base_dir

    # ---- what the program makes, and where
    def collect(self, body, scope, top_level=True):
        for s in body:
            k = s.kind
            if k == "func":
                scope.names.add(s.name)
                inner = Scope(scope, s.name)
                inner.names.update(s.params)
                self.scope_of[id(s)] = inner
                self.everywhere.add(s.name)
                self.everywhere.update(s.params)
                self.params.update(s.params)
                if scope is self.top:
                    self.funcs[s.name] = s.params
                    self.func_nodes[s.name] = s
                    self.func_count[s.name] = self.func_count.get(s.name, 0) + 1
                self.collect(s.body, inner, False)
            elif k == "assign" and s.target.kind == "var":
                self.assigned.setdefault(s.target.name, []).append(s)
                if s.op == "=":
                    scope.names.add(s.target.name)
                    self.everywhere.add(s.target.name)
            elif k == "for":
                self.loop_vars.add(s.name)
                scope.names.add(s.name)
                self.everywhere.add(s.name)
                self.collect(s.body, scope, False)
            elif k == "while":
                self.collect(s.body, scope, False)
            elif k == "if":
                for _, b in s.branches:
                    self.collect(b, scope, False)
                if s.else_body:
                    self.collect(s.else_body, scope, False)
            elif k == "import":
                scope.names.add(s.name)
                self.everywhere.add(s.name)
                self.imports.add(s.name)

    def run(self):
        self.collect(self.program, self.top)
        self.user = self.everywhere | set(self.func_count)
        kinds = [self.kind(n) for n in nodes(self.program) if n.kind == "call" and n.fn.kind == "attr"]
        self.makes_window = "window" in kinds
        self.body(self.program, self.top, in_loop=False)
        self.check_top_level()
        seen, out = set(), []
        for p in sorted(self.problems):
            if p not in seen:
                seen.add(p)
                out.append(p)
        return out

    def problem(self, node, msg):
        self.problems.append((node.line, node.col, msg))

    def what(self, kind):
        return "a function" if kind.startswith("$libfn:") else self.TYPE.get(kind) or a_kind(kind.lstrip("@"))

    def only_func(self, name):
        """True when name is one top-level function and never anything else."""
        return self.func_count.get(name) == 1 and name not in self.assigned and name not in self.params and name not in self.loop_vars

    def returns_function(self, name):
        """Does this function give back another function? (Then calling it in a handler spot is fine.)"""
        node = self.func_nodes.get(name)
        if node is None:
            return True
        for x in nodes(node.body):
            if x.kind == "func":
                return True
            if x.kind == "return" and x.value is not None and x.value.kind == "var" and (x.value.name in self.func_count or x.value.name in self.builtins):
                return True
        last = node.body[-1] if node.body else None
        return bool(last is not None and last.kind == "expr" and last.expr.kind == "var" and last.expr.name in self.func_count)

    # ---- what kind of value something is ("$text", "$list", "button", "window", "$module:anims"...), or None
    def var_kind(self, name, seen):
        if name in self.memo:
            return self.memo[name]
        if name in seen:
            return None
        if name in OWN_NAME_BUILTINS and name in self.everywhere and name not in self.top.names:
            return None  # only functions make their own variables with this name; everywhere else it's the built-in
        kinds = set()
        if name in self.imports:
            kinds.add("$module:" + name)
        if name in self.func_count:
            kinds.add("$func")
        if name in self.params or name in self.loop_vars:
            kinds.add(None)
        for s in self.assigned.get(name, []):
            vk = self.kind(s.value, seen | {name})
            if s.op == "=":
                kinds.add(vk)
            elif vk is None:
                kinds.add(None)  # x += something unknown: x could become anything
            elif vk == "$text" and s.op in ("+=", "*="):
                kinds.add("$text")
            elif vk == "$list" and s.op == "+=":
                kinds.add("$list")
        if not kinds and name in self.builtins:
            kinds.add("$builtin" if isinstance(self.builtins[name], Builtin) else "$number" if name == "pi" else None)
        result = kinds.pop() if len(kinds) == 1 else None
        if not seen:
            self.memo[name] = result
        return result

    def kind(self, e, seen=frozenset()):
        k = e.kind
        if k == "const":
            v = e.value
            return "$text" if isinstance(v, str) else "$bool" if isinstance(v, bool) else "$nil" if v is None else "$number"
        if k == "list":
            return "$list"
        if k == "say":
            return "$line"
        if k == "input":
            return "$text"
        if k == "var":
            return self.var_kind(e.name, seen)
        if k == "not" or (k == "binop" and e.op in self.COMPARE):
            return "$bool"
        if k == "neg":
            return "$number" if self.kind(e.value, seen) == "$number" else None
        if k == "binop" and e.op in ("+", "*"):
            a, b = self.kind(e.left, seen), self.kind(e.right, seen)
            if "$text" in (a, b):
                return "$text"
            if a == b and a in ("$number", "$list") and (e.op == "+" or a == "$number"):
                return a
            return None
        if k == "binop" and e.op in ("-", "/", "%", "^"):
            return "$number" if self.kind(e.left, seen) == self.kind(e.right, seen) == "$number" else None
        if k == "attr":
            lib = self.kind(e.obj, seen)
            return f"$libfn:{lib[8:]}.{e.name}" if lib and lib.startswith("$module:") else None
        if k == "call" and e.fn.kind == "var" and e.fn.name not in self.user:
            name = e.fn.name
            return "$text" if name in ("text", "str") else "$list" if name == "range" else "$number" if name in self.NUMBER_FNS else None
        if k == "call" and e.fn.kind == "attr":
            lib = self.kind(e.fn.obj, seen)
            if lib in ("$module:tgui", "$module:mtgui") and e.fn.name == "window":
                return "window"
            if lib == "$module:tap":
                return self.TAP_MAKES.get(e.fn.name)
            if lib == "$module:atgui":
                return "@window" if e.fn.name == "window" else None
            if lib == "$module:tgame":
                return {"window": "game", "world": "world"}.get(e.fn.name)
            return None
        if k == "method":
            obj = self.kind(e.obj, seen)
            if obj and obj.startswith("@"):
                return self.atgui_kind(obj[1:], e)
            if obj in self.TAP_GIVES:
                return self.TAP_GIVES[obj].get(e.name)
            if obj in self.TGAME_KINDS:
                tg = tgame_tables()
                return tg["gives"].get(obj, {}).get(e.name) if tg else None
            gui = gui_tables()
            if obj in self.CONTAINERS and gui and e.name in gui["kinds"] and e.name != "window" and (e.name != "page" or obj == "window"):
                return e.name
            if obj == "$text":
                return "$bool" if e.name == "has" else "$text" if e.name in ("upper", "lower", "trim") else None
            if obj == "$list":
                return "$list" if e.name in ("add", "remove") else "$bool" if e.name == "has" else None
            if obj == "$line" and e.name == "text":
                return "$text"
            if e.name == "value" and not e.args and obj:
                return "$text" if obj in self.TEXT_VALUE else "$bool" if obj in ("toggle", "checkbox") else "$number" if obj in ("slider", "progress") else None
        return None

    def typed(self, e):
        """Text that came from someone typing (input, or a widget's :value), even through a variable."""
        if e.kind == "input" or (e.kind == "method" and e.name == "value" and self.kind(e) == "$text"):
            return True
        if e.kind == "var" and self.var_kind(e.name, frozenset()) == "$text":
            sets = [s for s in self.assigned.get(e.name, []) if s.op == "="]
            return bool(sets) and all(self.typed(s.value) for s in sets)
        return False

    def describe(self, e):
        return e.name if e.kind == "var" else f"{e.obj.name}:{e.name}()" if e.kind == "method" and e.obj.kind == "var" else None

    # ---- walking the program
    def body(self, body, scope, in_loop, in_func=False):
        for i, s in enumerate(body):
            last_of_func = in_func and i == len(body) - 1
            self.stmt(s, scope, in_loop, in_func, last_of_func)

    def stmt(self, s, scope, in_loop, in_func, last_of_func):
        k = s.kind
        if k == "func":
            self.body(s.body, self.scope_of[id(s)], False, True)
        elif k == "import":
            if s.name not in LIBRARIES:
                hint = difflib.get_close_matches(s.name, LIBRARIES, n=1, cutoff=0.5)
                extra = f" Did you mean '{hint[0]}'?" if hint else f" Available libraries: {', '.join(LIBRARIES)}."
                self.problem(s, f"There's no library called '{s.name}'.{extra}")
        elif k == "assign":
            target = s.target.name if s.target.kind == "var" else None
            if s.op != "=" and target:
                self.expr(s.target, scope)
                if s.op == "+=" and self.kind(s.target) == "$list" and self.kind(s.value) == "$text":
                    self.problem(s, f"This turns the list {target} into text. To add one item, use {target}:add(...).")
                if s.op == "+=" and s.value.kind == "input" and any(t.op == "=" and self.kind(t.value) == "$number" for t in self.assigned.get(target, [])):
                    self.problem(s, f"input gives text, so += sticks it onto {target} as text (0, then \"05\", then \"0510\"). Use {target} += number(input \"...\").")
            elif s.target.kind == "index":
                self.expr(s.target.obj, scope)
                self.expr(s.target.index, scope)
                if self.kind(s.target.obj) == "$text":
                    self.problem(s, "You can only set items in a list, not in text. Build new text with + instead.")
            if s.op == "=" and target in self.func_count and target not in self.params and target not in self.loop_vars \
                    and self.kind(s.value) not in ("$func", "$builtin"):
                self.problem(s, f"{target} is a function, and giving it a value replaces it, so {target}() won't work afterwards. Use another name for the value.")
            self.expr(s.value, scope)
        elif k == "expr":
            self.statement_call = s.expr
            self.expr(s.expr, scope)
            if not last_of_func:
                self.check_useless(s.expr)
        elif k == "if":
            for cond, b in s.branches:
                self.expr(cond, scope)
                self.check_condition(cond)
                self.body(b, scope, in_loop, in_func)
            if s.else_body:
                self.body(s.else_body, scope, in_loop, in_func)
        elif k == "while":
            self.expr(s.cond, scope)
            self.check_condition(s.cond)
            self.body(s.body, scope, True, in_func)
        elif k == "for":
            self.expr(s.items, scope)
            if self.kind(s.items) == "$number":
                self.problem(s, f"Can't loop over a number. Try: for {s.name} in range(...):")
            elif self.kind(s.items) == "data object":
                owner = s.items.name if s.items.kind == "var" else "thing"
                self.problem(s, f"Can't loop over a data object. Loop over its names instead: for {s.name} in {owner}:keys():")
            self.check_range_len(s)
            self.body(s.body, scope, True, in_func)
        elif k == "return":
            if not in_func:
                self.problem(s, "'return' can only be used inside a function.")
            if s.value is not None:
                self.expr(s.value, scope)
        elif k in ("break", "continue") and not in_func and not in_loop:
            self.problem(s, f"'{k}' can only be used inside a loop.")

    def expr(self, e, scope):
        if e is None:
            return
        k = e.kind
        if k == "var":
            self.use(e, scope)
        elif k == "say":
            self.expr(e.value, scope)
        elif k == "input":
            self.expr(e.prompt, scope)
            if e.prompt is not None and (e.prompt.kind in ("and", "or") or (e.prompt.kind == "binop" and e.prompt.op in self.COMPARE)):
                self.problem(e, "input took everything after it as its question, so it asks the wrong thing. Store the answer first: answer = input \"...\", then compare answer.")
        elif k in ("binop", "and", "or"):
            self.expr(e.left, scope)
            self.expr(e.right, scope)
            if k == "binop":
                self.check_binop(e)
            if k == "binop" and e.op in self.MATHS and e.left.kind == "method" and getattr(e.left, "spaced", False):
                m = e.left
                owner = m.obj.name if m.obj.kind == "var" else "thing"
                self.problem(m, f"With a space before the bracket, {owner}:{m.name} still takes only what's inside the brackets as its input, and the rest is worked out afterwards. Put the whole input in brackets: {owner}:{m.name}(... + ...)")
        elif k in ("not", "neg"):
            self.expr(e.value, scope)
        elif k == "list":
            for x in e.items:
                self.expr(x, scope)
        elif k == "index":
            self.expr(e.obj, scope)
            self.expr(e.index, scope)
            self.check_index(e)
        elif k == "call":
            if e.fn.kind == "var":
                self.use(e.fn, scope, func=True)
                self.calls.setdefault(e.fn.name, []).append(e.line)
            else:
                self.expr(e.fn, scope)
            for a in e.args:
                self.expr(a, scope)
            self.check_call(e, scope)
        elif k == "attr":
            self.expr(e.obj, scope)
            self.check_attr(e)
        elif k == "method":
            self.expr(e.obj, scope)
            pos = self.HANDLER_POS.get(e.name)
            for i, a in enumerate(e.args):
                if i == pos and a.kind == "var":
                    self.use(a, scope, func=True)
                else:
                    self.expr(a, scope)
            self.check_method(e)

    def use(self, e, scope, func=False):
        name = e.name
        if name in self.builtins or any(name in s.names for s in scope.chain()):
            return
        if name in self.everywhere:
            owners = sorted({f"{n}()" for n, sc in self.scope_names() if name in sc})
            where = owners[0] if len(owners) == 1 else "other functions"
            self.problem(e, f"'{name}' is only set inside {where}, so it only exists there. Give it a value at the top of the program (like {name} = 0) so this line can use it.")
            return
        if name in LIBRARIES:
            msg = f"'{name}' is a library. Add  import {name}  at the top of your file to use it."
        elif name in PY_NAMES:
            msg = f"I don't know what '{name}' is. {PY_NAMES[name]}"
        else:
            visible = set(self.builtins) | set().union(*(s.names for s in scope.chain()))
            hint = difflib.get_close_matches(name, sorted(visible), n=1, cutoff=0.6)
            fix = f" Make it with func, like: func {name}():" if func else f" Give it a value first, like: {name} = 5"
            msg = f"I don't know what '{name}' is." + (f" Did you mean '{hint[0]}'?" if hint else fix)
        self.problem(e, msg)

    def scope_names(self):
        seen = set()
        for sc in self.scope_of.values():
            if id(sc) not in seen:
                seen.add(id(sc))
                yield sc.name, sc.names

    def lib_members(self, lib):
        if lib == "anims":
            if self.anims is None:
                self.anims = {n: b.fn for n, b in self.interp.lib_anims().items()}
            return self.anims
        if lib == "tap":
            tap = tap_tables()
            return tap["lib"] if tap else None
        if lib == "atgui":
            at = atgui_tables()
            return at["lib"] if at else None
        if lib == "tgame":
            tg = tgame_tables()
            return tg["lib"] if tg else None
        gui = gui_tables()
        return gui["libs"].get(lib) if gui else None

    # ---- checks
    def check_top_level(self):
        """A built-in's name given a value at the top replaces it, so later uses of it fail: calls of a built-in
        function, and "is err" checks of what number() gave. And a function made twice at the top: the second
        replaces the first."""
        made = {}
        owner = {}  # id(node) -> the top-level function it's written in (nodes at the top aren't in here)
        for f in nodes(self.program):
            if f.kind == "func" and id(f) not in owner:
                for x in nodes(f.body):
                    owner[id(x)] = f.name
        calls, uses = {}, {}  # name -> its calls; function name -> (call or event input, given to an event?)
        for x in nodes(self.program):
            if x.kind == "call" and x.fn.kind == "var":
                calls.setdefault(x.fn.name, []).append(x)
                uses.setdefault(x.fn.name, []).append((x, False))
            elif x.kind == "method":
                for a in x.args:
                    if a.kind == "var":
                        uses.setdefault(a.name, []).append((a, True))

        def runs_after(fname, after, seen):
            """Can the function fname run after line `after`? Yes when it's called on a later line, given to an
            event at the top (events happen after the top of the program has run), or used in a function that can."""
            for x, event in uses.get(fname, []):
                where = owner.get(id(x))
                if where is None:
                    if x.line > after or event:
                        return True
                elif where not in seen and runs_after(where, after, seen | {where}):
                    return True
            return False

        def later(found, after):
            """The first line of these that can run after line `after`, or None."""
            lines = [x.line for x in found if (x.line > after if owner.get(id(x)) is None else runs_after(owner[id(x)], after, {owner[id(x)]}))]
            return min(lines) if lines else None

        def replaces(s, name, after):
            """s sets the built-in called name; any call of it that runs after line `after` breaks."""
            if self.kind(s.value) in ("$func", "$builtin") or (self.kind(s.value) or "").startswith("$libfn:"):
                return
            line = later(calls.get(name, []), after)
            if line:
                self.problem(s, f"'{name}' is a built-in function, and giving it a value replaces it everywhere, so {name}() on line {line} won't work. Use another name, like my_{name}.")

        def replaces_err(s):
            """s gives err a value, so a later "is err" check of what number() gave never finds one."""
            if self.gives_err(s.value) or (s.value.kind == "var" and s.value.name == "err"):
                return
            checks = [x for x in nodes(self.program) if x.kind == "binop" and x.op in ("==", "!=") and self.err_check(x)]
            line = later(checks, s.line)
            if line:
                self.problem(s, f"'err' is built in (number() and num() give it for text that isn't a number), and giving it a value replaces it everywhere, so the is err check on line {line} won't work. Use another name, like my_err.")

        for s in self.program:
            if s.kind == "assign" and s.op == "=" and s.target.kind == "var" and isinstance(self.builtins.get(s.target.name), Builtin):
                replaces(s, s.target.name, s.line)
            elif s.kind == "assign" and s.op == "=" and s.target.kind == "var" and s.target.name == "err":
                replaces_err(s)
            # f() at the top runs f, and f setting a built-in's name (not one of its inputs) replaces it for everyone
            # (except the OWN_NAME_BUILTINS: there it's f's own variable)
            if s.kind == "expr" and s.expr.kind == "call" and s.expr.fn.kind == "var" and self.only_func(s.expr.fn.name):
                f = self.func_nodes[s.expr.fn.name]
                for t in f.body:
                    if t.kind == "assign" and t.op == "=" and t.target.kind == "var" and t.target.name not in f.params \
                            and t.target.name not in OWN_NAME_BUILTINS and isinstance(self.builtins.get(t.target.name), Builtin):
                        replaces(t, t.target.name, s.line)
            if s.kind == "func":
                if s.name in made:
                    self.problem(s, f"There are two functions called {s.name}. This one replaces the one on line {made[s.name]}. Give them different names.")
                made[s.name] = s.line

    def check_useless(self, e):
        """A line that works something out but throws the answer away."""
        if e.kind == "var" and e.name in self.func_count:
            self.problem(e, f"{e.name} on its own does nothing. Call it with brackets: {e.name}()")
        elif e.kind == "attr" and (self.kind(e) or "").startswith("$libfn:"):
            self.problem(e, f"{self.kind(e)[7:]} on its own does nothing. Call it with brackets: {self.kind(e)[7:]}(...)")
        elif e.kind == "method" and e.name in ("upper", "lower", "trim") and self.kind(e.obj) == "$text" and e.obj.kind == "var":
            v = e.obj.name
            self.problem(e, f"{v}:{e.name}() gives back new text but doesn't change {v}. Write {v} = {v}:{e.name}()")

    def check_condition(self, cond):
        """if answer is "yes" or "y": the "y" part is always true on its own."""
        if cond.kind == "or":
            for side in (cond.left, cond.right):
                if side.kind == "const" and isinstance(side.value, str) and side.value:
                    other = cond.left if side is cond.right else cond.right
                    subject = other.left.name if other.kind == "binop" and other.left.kind == "var" else "answer"
                    self.problem(side, f"or \"{side.value}\" on its own is always true. Compare again: {subject} is \"{side.value}\"")
        if cond.kind == "method" and cond.name == "has" and getattr(cond, "bare", False) and cond.args and (
                cond.args[0].kind in ("and", "or") or (cond.args[0].kind == "binop" and cond.args[0].op in self.COMPARE)):
            owner = cond.obj.name if cond.obj.kind == "var" else "thing"
            self.problem(cond, f"Everything after {owner}:has was read as the thing to look for. Put brackets around its input, like: {owner}:has(x) and ...")

    def gives_err(self, x, seen=frozenset()):
        """Could x be the err that number(), num() or int() give for text that isn't a number?"""
        if x.kind == "call" and x.fn.kind == "var":
            return x.fn.name in ("number", "num", "int") and x.fn.name not in self.func_count
        if x.kind == "var" and x.name not in seen:
            return any(self.gives_err(t.value, seen | {x.name}) for t in self.assigned.get(x.name, []) if t.op == "=")
        return False

    def err_check(self, e):
        """e compares err with something that could really be err, like: if num(t) is err"""
        sides = (e.left, e.right)
        return any(x.kind == "var" and x.name == "err" for x in sides) and any(self.gives_err(x) for x in sides)

    def check_binop(self, e):
        op, a, b = e.op, self.kind(e.left), self.kind(e.right)
        typed = next((x for x in (e.left, e.right) if self.typed(x)), None)
        tip = f" {self.describe(typed)} is typed text, so turn it into a number first: number({self.describe(typed)})." if typed is not None and self.describe(typed) else ""
        other = e.right if e.left.kind == "var" and e.left.name == "err" else e.left if e.right.kind == "var" and e.right.name == "err" else None
        if op in self.ORDER and e.left.kind == "binop" and e.left.op in self.COMPARE:
            self.problem(e, "Tuff can't chain comparisons like 1 < x < 9: the first part gives true or false. Write x > 1 and x < 9.")
        elif op in self.ORDER and {a, b} == {"$text", "$number"}:
            self.problem(e, f"Can't compare text with a number using {op}.{tip}")
        elif op in ("==", "!=") and other is not None and "err" not in self.everywhere and self.kind(other) == "$text":
            # answer is err: only number(), num() and int() give err, so typed text never is
            who, word, check = self.describe(other), "never" if op == "==" else "always", "is" if op == "==" else "is not"
            self.problem(e, f"{who} is text, so it's never err and this is {word} true. Use num({who}) {check} err to check whether it's a number." if who
                         else f"Text is never err, so this is {word} true. Use num(...) {check} err to check whether it's a number.")
        elif op in ("==", "!=") and other is not None and self.err_check(e):
            pass  # num(t) is err: if err was given a value, check_top_level says so
        elif op in ("==", "!=") and {a, b} == {"$text", "$number"}:
            word = "never" if op == "==" else "always"
            self.problem(e, f"Text is never equal to a number, so this is {word} true.{tip or ' Turn the text into a number with number(...) first.'}")
        elif op in ("-", "/", "%", "^") and "$text" in (a, b) and None not in (a, b):
            verb = {"-": "subtract", "/": "divide", "%": "use % on", "^": "use ^ on"}[op]
            first, second = self.TYPE[a], self.TYPE.get(b, self.what(b))
            hint = tip
            if e.left.kind == "binop" and e.left.op == "+" and a == "$text":
                hint = " The + before it already joined the text, so put the maths in brackets, like \"Lives: \" + (lives - 1)."
            self.problem(e, f"Can't {verb} {first} and {second}.{hint}")
        elif op == "*" and "$list" in (a, b) and None not in (a, b):
            self.problem(e, "Can't multiply a list. Write the items out, like [0, 0, 0], or add them with :add in a loop.")
        elif op == "*" and a == b == "$text":
            self.problem(e, f"Can't multiply text and text.{tip}")
        elif op == "+" and a == "$list" and b == "$text":
            self.problem(e, "This turns the list into text. To add one item, use :add, or join two lists: items + [\"jam\"].")
        elif op == "+" and b == "$number" and e.left.kind == "binop" and e.left.op == "+" and self.kind(e.left) == "$text" \
                and self.kind(e.left.right) == "$number" and not (e.left.right.kind == "const" and e.right.kind == "const"):
            self.problem(e, "+ works left to right, and the text before has already turned the numbers into text, so they're stuck together (\"Total: \" + 10 + 2 gives \"Total: 102\"). Put the sum in brackets: \"Total: \" + (a + b)")
        elif op == "+" and {a, b} == {"$text", "$number"} and typed is not None and self.describe(typed):
            self.problem(e, f"{self.describe(typed)} is typed text, so + sticks them together (\"5\" + 1 gives \"51\"). Use number({self.describe(typed)}) to add.")
        if op == "*" and "$text" in (a, b):
            n = e.right if a == "$text" else e.left
            if self.is_decimal(n):
                self.problem(n, "This is a decimal (it comes from /), even if it looks whole, so it can't repeat text. Use floor(...) around the division.")

    def check_index(self, e):
        idx = self.kind(e.index)
        if idx == "$text":
            who = self.describe(e.index)
            self.problem(e, "List positions must be whole numbers, not text." + (f" Use number({who})." if who and self.typed(e.index) else ""))
        elif self.is_decimal(e.index):
            self.problem(e.index, "This is a decimal (it comes from /), even if it looks whole, so it can't be a position. Use floor(...) around the division.")
        elif e.index.kind == "method" and not e.index.args and not self.method_exists(e.index.name):
            self.problem(e, "Tuff has no slices like word[a:b]. Build the part you need with a loop.")
        elif e.index.kind == "call" and e.index.fn.kind == "var" and e.index.fn.name == "random" and "random" not in self.user and e.obj.kind == "var":
            args = e.index.args
            ends_at_len = args and args[-1].kind == "call" and args[-1].fn.kind == "var" and args[-1].fn.name == "len" and len(args[-1].args) == 1 and \
                args[-1].args[0].kind == "var" and args[-1].args[0].name == e.obj.name
            if ends_at_len:
                lst = e.obj.name
                self.problem(e.index, f"random(...len({lst})) can give len({lst}), which is past the last position (positions go from 0 to len({lst}) - 1). Use {lst}[random(0, len({lst}) - 1)].")

    def method_exists(self, name):
        gui = gui_tables()
        if gui is None:
            return True
        at = atgui_tables()
        if at is not None and any(name in m for m in at["kinds"].values()):
            return True
        tap = tap_tables()
        tg = tgame_tables()
        return name in SIMPLE_METHODS["text"] or name in SIMPLE_METHODS["list"] or name in SIMPLE_METHODS["line"] or \
            any(name in m for m in gui["kinds"].values()) or (tap is None or any(name in m for m in tap["kinds"].values())) or \
            (tg is None or any(name in m for m in tg["kinds"].values()))

    def check_call(self, e, scope):
        fn, n = e.fn, len(e.args)
        if fn.kind == "var":
            name = fn.name
            local = any(name in s.names for s in scope.chain() if s is not self.top)
            if self.only_func(name) and not local:
                want = len(self.funcs[name])
                if n != want:
                    self.problem(e, f"{name}() needs {want} input{'s' if want != 1 else ''}, but got {n}.")
                elif e is not self.statement_call:
                    self.check_gives_back(e, name)
            elif name not in self.user and isinstance(self.builtins.get(name), Builtin):
                if not accepts(self.builtins[name].fn, n):
                    self.problem(e, f"{name}() got the wrong number of inputs ({n}).")
                elif name == "random" and not 1 <= n <= 2:
                    self.problem(e, "random() needs a range, like random(1, 6), or just the top, like random(6). For a decimal, use random(0, 100) / 100.")
                elif name == "random" and any(a.kind == "const" and isinstance(a.value, float) and not a.value.is_integer() for a in e.args):
                    self.problem(e, "random() needs whole numbers, like random(1, 6). For a decimal, divide: random(0, 100) / 100.")
                elif name in self.NUMBER_INPUT_FNS:
                    for a in e.args:
                        if self.kind(a) == "$text":
                            who = self.describe(a)
                            tip = f" Use number({who})." if who and self.typed(a) else ""
                            self.problem(a, f"{name}() needs a number, not text.{tip}")
                            break
                elif name in ("number", "num", "int") and n == 1:
                    self.check_number_input(e.args[0], name)
            elif name not in self.builtins and not local:
                kind = self.var_kind(name, frozenset())
                if kind and not kind.startswith(("$module:", "$libfn:")) and kind not in ("$func", "$builtin"):
                    self.problem(e, f"'{name}' is {self.what(kind)}, not a function, so it can't be called with ( ).")
        elif fn.kind == "attr":
            lib = self.kind(fn.obj)
            if lib and lib.startswith("$module:"):
                members = self.lib_members(lib[8:]) or {}
                if fn.name in members and not accepts(members[fn.name], n):
                    self.problem(e, f"{lib[8:]}.{fn.name}() got the wrong number of inputs ({n}).")

    def check_number_input(self, a, name):
        """number(), num() and int() give err for text that isn't a number, but anything else that isn't text or a
        number (a text box itself, a list, nil...) stops the program."""
        kind = self.kind(a)
        if kind is None or kind in ("$text", "$number", "$line"):
            return
        widget = kind.lstrip("@")
        gui, at = gui_tables(), atgui_tables()
        kinds = (at or {}).get("kinds", {}) if kind.startswith("@") else (gui or {}).get("kinds", {})
        if "value" in kinds.get(widget, {}) and a.kind == "var":
            self.problem(a, f"{name}() needs text or a number, not the {widget} widget. Use {name}({a.name}:value()) to get what's in it.")
        else:
            self.problem(a, f"{name}() needs text or a number, not {'a library' if kind.startswith('$module:') else self.what(kind)}.")

    def check_gives_back(self, e, name):
        """The answer of name() is used, but name() can't give one back."""
        f = self.func_nodes[name]
        if not f.body or any(x.kind == "return" for x in nodes(f.body)):
            return
        last = f.body[-1]
        if last.kind in ("for", "while"):
            self.problem(e, f"{name}() ends with a loop, so it gives back nil here. Add a return line at its end, like return total.")
        elif last.kind == "expr" and last.expr.kind == "say":
            self.problem(e, f"{name}() ends with say, so it gives back the shown line, not a value. Use return instead of say for the answer.")

    def is_decimal(self, x):
        """A / always gives a decimal, even when it looks whole (10 / 5 is 2.0)."""
        if x.kind == "binop" and x.op == "/":
            return True
        if x.kind == "var" and x.name not in self.params and x.name not in self.loop_vars:
            sets = self.assigned.get(x.name, [])
            return len(sets) == 1 and sets[0].op == "=" and sets[0].value.kind == "binop" and sets[0].value.op == "/"
        return False

    def check_file_input(self, arg, what):
        """A picture file named in the program: right kind of file, and there (when we know the folder)."""
        if arg is None or arg.kind != "const" or not isinstance(arg.value, str):
            return
        path = arg.value
        ok = (".png", ".gif") if what == "image" else (".png", ".gif", ".ico")
        if not path.lower().endswith(ok):
            msg = f"Couldn't open the image '{path}'. Put a .png or .gif file in your project folder." if what == "image" \
                else f"Couldn't use '{path}' as an icon. Use a .png, .gif or .ico file."
            self.problem(arg, msg)
            return
        base = self.base_dir
        if base and not os.path.isabs(path) and not os.path.abspath(base).lower().startswith(os.path.abspath(tempfile.gettempdir()).lower()):
            if not os.path.isfile(os.path.join(base, path)):
                msg = f"Couldn't open the image '{path}'. Put a .png or .gif file in your project folder." if what == "image" \
                    else f"Couldn't find the icon '{path}'. Put the image in your project folder."
                self.problem(arg, msg)

    def check_attr(self, e):
        obj = self.kind(e.obj)
        if obj is not None and obj.startswith("$module:"):
            members = self.lib_members(obj[8:])
            if members is not None and e.name not in members:
                self.problem(e, f"{obj[8:]} doesn't have '{e.name}'. It has: {', '.join(members)}.")
            return
        if obj is not None:
            self.problem(e, dot_help(self.what(obj), e.obj, e.name, obj.lstrip("$")))
            return
        # Unknown value: only a library can use '.', and libraries only have these.
        gui = gui_tables()
        members = {"window"} | set(self.lib_members("anims") or {}) | set(self.lib_members("tap") or {}) | \
            set(self.lib_members("tgame") or {})
        if gui is not None and e.name not in members and e.obj.kind == "var" and e.obj.name not in self.imports:
            self.problem(e, dot_help("not a library", e.obj, e.name))

    def check_method(self, e):
        obj = self.kind(e.obj)
        name, n = e.name, len(e.args)
        owner = e.obj.name if e.obj.kind == "var" else "thing"
        if obj is None:
            if not self.method_exists(name):
                tip = PY_ONLY.get(name.lower())
                self.problem(e, f"Nothing in Tuff has :{name}." + (f" {tip}" if tip else ""))
            return
        bare_fix = f"{owner}:{name} doesn't take an input, so what comes after it was read as one. Write {owner}:{name}() instead."
        if obj.startswith("$libfn:"):
            self.problem(e, f"'{owner}' is the function {obj[7:]} itself, not what it makes. Add brackets, like: {owner} = {obj[7:]}(...)")
            return
        if obj.startswith("@"):
            self.check_atgui(e, obj[1:])
            return
        simple = SIMPLE_METHODS.get(obj[1:]) if obj.startswith("$") else None
        if simple:
            kind = obj[1:]
            if name not in simple:
                what = "Text" if kind == "text" else a_kind(kind).capitalize()
                tip = PY_ONLY.get(name.lower())
                msg = method_help(what, name, simple, kind)
                self.problem(e, msg + (f" {tip}" if tip and "instead" not in msg else ""))
            elif name in ONE_INPUT and n != 1:
                self.problem(e, f":{name} needs 1 input.")
            elif name in self.ZERO_INPUT and e.bare:
                self.problem(e, bare_fix)
            elif name in self.ZERO_INPUT and n:
                if name == "pop":
                    self.problem(e, f"{owner}:pop doesn't take a position: it always takes the last item. To take another item, read it with {owner}[...] and then :remove it.")
                else:
                    self.problem(e, f"{owner}:{name} doesn't take an input. Write {owner}:{name}()")
            return
        if obj.startswith("$module:"):
            lib = obj[8:]
            first = next(iter(self.lib_members(lib) or {"window": None}))
            self.problem(e, f"A library doesn't have any :methods. Library functions use a dot, like: {lib}.{first}(...)")
            return
        if obj in self.TYPE:
            self.problem(e, f"{self.TYPE[obj].capitalize()} doesn't have any :methods.")
            return
        if obj in self.TGAME_KINDS:
            self.check_tgame(e, obj, bare_fix)
            return
        gui = gui_tables()
        tap = tap_tables() if obj in self.TAP_GIVES else None
        methods = tap["kinds"].get(obj) if tap else gui["kinds"].get(obj) if gui else None
        if methods is None:
            return
        if name == "page" and obj in ("row", "card", "page"):
            self.problem(e, f"A {obj} doesn't have :page. Pages go straight on the window, like: home = app:page \"Home\"")
        elif name not in methods:
            options = [m for m in methods if m != "page" or obj == "window"]
            self.problem(e, method_help(a_kind(obj).capitalize(), name, options))
        elif not accepts(methods[name], n):
            self.problem(e, bare_fix if e.bare and accepts(methods[name], 0) else f"{obj}:{name} got the wrong number of inputs ({n}).")
        else:
            self.check_values(e, obj)
            self.check_handler(e)
            self.check_maker_inputs(e, obj)
            if name == "image" and obj in self.CONTAINERS or name == "set" and obj == "image":
                self.check_file_input(e.args[0] if e.args else None, "image")
            elif name == "icon" and obj == "window":
                self.check_file_input(e.args[0] if e.args else None, "icon")
            elif name == "set" and obj == "dropdown" and e.obj.kind == "var" and e.args:
                self.check_dropdown_set(e)

    def check_dropdown_set(self, e):
        """box:set "Large" on a dropdown whose choices are written out and never changed."""
        v = e.obj.name
        sets = self.assigned.get(v, [])
        arg = e.args[0]
        if len(sets) != 1 or sets[0].op != "=" or v in self.params or v in self.loop_vars or arg.kind != "const":
            return
        made = sets[0].value
        if not (made.kind == "method" and made.name == "dropdown" and made.args and made.args[0].kind == "list"
                and all(x.kind == "const" for x in made.args[0].items)):
            return
        if any(x.kind == "method" and x.name == "options" and x.obj.kind == "var" and x.obj.name == v for x in nodes(self.program)):
            return
        choices = [to_text(x.value) for x in made.args[0].items]
        if to_text(arg.value) not in choices:
            self.problem(arg, f"'{to_text(arg.value)}' isn't one of this dropdown's choices: {', '.join(choices)}.")

    def check_tgame(self, e, obj, bare_fix):
        """A method of something tgame made: its name, its input count, the function an event runs, and inputs
        written as text that have to be a color, a sky, a key, a sound or a file tgame knows."""
        tg = tgame_tables()
        methods = tg["kinds"].get(obj) if tg else None
        if methods is None:
            return
        name, n = e.name, len(e.args)
        what = a_kind(obj).capitalize()
        if name not in methods:
            alt = tg["hints"].get(obj, {}).get(name.lower())
            self.problem(e, f"{what} doesn't have :{name}. Use :{alt} instead." if alt in methods else method_help(what, name, list(methods)))
            return
        if not accepts(methods[name], n):
            self.problem(e, bare_fix if e.bare and accepts(methods[name], 0) else f"{obj}:{name} got the wrong number of inputs ({n}).")
            return
        event = tg["handlers"].get(obj, {}).get(name)
        fn = e.args[event[0]] if event and len(e.args) > event[0] else None
        if fn is not None:
            owner = e.obj.name if e.obj.kind == "var" else obj
            if fn.kind == "call" and fn.fn.kind == "var" and self.only_func(fn.fn.name) and not self.returns_function(fn.fn.name):
                self.problem(fn, f"Pass the function's name without brackets: {fn.fn.name}, not {fn.fn.name}(). With brackets it runs once at the start instead of when it should.")
            elif fn.kind == "method":
                target = f"{fn.obj.name}:{fn.name}" if fn.obj.kind == "var" else f":{fn.name}"
                self.problem(fn, f"{target} runs right away here, while this line runs. Make a small function (func do_it(): {target}) and pass its name.")
            elif fn.kind == "const" and isinstance(fn.value, str):
                self.problem(fn, f"This needs a function name, not text. Write {fn.value} without the quotes, and make it with func {fn.value}():")
            elif fn.kind == "var" and self.only_func(fn.name):
                want, gives, given = len(self.funcs[fn.name]), event[1], event[2]
                if want > gives:
                    fix = f" Write it as: func {fn.name}():" if gives == 0 else f" Write it as: func {fn.name}({', '.join(self.funcs[fn.name][:gives])}):"
                    self.problem(fn, f"{fn.name}() needs {want} input{'s' if want != 1 else ''}, but {owner}:{name} gives it {given}.{fix}")
                node = self.func_nodes.get(fn.name)
                if node is not None and id(node) not in self.handlers_seen:
                    self.handlers_seen.add(id(node))
                    for x in nodes(node.body):
                        if x.kind == "call" and x.fn.kind == "var" and x.fn.name == "wait" and "wait" not in self.user:
                            self.problem(x, f"wait() freezes the game: nothing moves or redraws until it's over. To do something later, use {owner}:after(seconds, fn).")
                        elif x.kind == "input":
                            self.problem(x, "input reads from the console and freezes the game while it waits.")
        base = self.base_dir
        if base and os.path.abspath(base).lower().startswith(os.path.abspath(tempfile.gettempdir()).lower()):
            base = None  # a snippet in a temporary folder: its files aren't next to it
        for i, a in enumerate(e.args):
            if a.kind == "const" and isinstance(a.value, str):
                msg = tg["check"](obj, name, i, a.value, base)
                if msg:
                    self.problem(a, msg)

    def check_values(self, e, obj):
        """Styles, colors and themes written as text must be ones the library knows."""
        gui = gui_tables()
        name = e.name
        checks = []
        if name == "button" and obj in self.CONTAINERS:
            checks.append((2, "style"))
        elif name == "style" and obj in ("button", "clock"):
            checks.append((0, "style" if obj == "button" else "clock"))
        elif name == "clock" and obj in self.CONTAINERS:
            checks.append((0, "clock"))
        elif name in ("accent", "color", "gradient"):
            checks.append((0, "color"))  # tgui ignores a gradient's second color, so only the first is certain
        elif name == "theme":
            checks.append((0, "theme"))
        for i, what in checks:
            arg = e.args[i] if len(e.args) > i else None
            if arg is None or arg.kind != "const" or not isinstance(arg.value, str):
                continue
            low = arg.value.lower()
            if what == "style" and low not in gui["styles"]:
                self.problem(arg, f"'{low}' isn't a button style. Use one of: {', '.join(gui['styles'])}.")
            elif what == "clock" and low not in gui["clocks"]:
                self.problem(arg, "A clock can be \"analog\" or \"digital\".")
            elif what == "theme" and low not in gui["themes"]:
                self.problem(arg, "The theme can be \"dark\" or \"light\".")
            elif what == "color" and low.strip() not in gui["colors"] and not is_hex_color(low.strip()):
                self.problem(arg, f"'{low.strip()}' isn't a color I know. Try {', '.join(gui['accents'])} or a hex code like \"#ff8800\".")

    def check_maker_inputs(self, e, obj):
        """Inputs to widget makers that can't be right: a function where a value goes, text where a list goes."""
        if obj not in self.CONTAINERS:
            return
        kinds = [self.kind(a) for a in e.args]
        name = e.name
        if name in ("toggle", "checkbox") and len(kinds) > 1 and kinds[1] in ("$func", "$builtin"):
            self.problem(e.args[1], f"The second input is whether it starts on (true or false). To run a function when it's switched, use the widget's :change, like: box = app:{name}(\"...\") then box:change fn")
        elif name == "slider" and any(k in ("$func", "$builtin", "$text", "$list") for k in kinds):
            bad = next(k for k in kinds if k in ("$func", "$builtin", "$text", "$list"))
            self.problem(e, f"A slider needs a number, not {self.what(bad)}. To run a function when it moves, use its :change.")
        elif name == "dropdown" and kinds and kinds[0] not in (None, "$list"):
            self.problem(e.args[0], "A dropdown needs a list, like [\"One\", \"Two\"].")

    def check_handler(self, e):
        name = e.name
        if name not in self.EVENT_GIVES:
            return
        pos = self.HANDLER_POS[name]
        fn = e.args[pos] if len(e.args) > pos else None
        if fn is None:
            return
        if fn.kind == "call" and fn.fn.kind == "var" and self.only_func(fn.fn.name) and not self.returns_function(fn.fn.name):
            f = fn.fn.name
            self.problem(fn, f"Pass the function's name without brackets: {f}, not {f}(). With brackets it runs once at the start instead of when it should.")
            return
        if fn.kind == "method":
            target = f"{fn.obj.name}:{fn.name}" if fn.obj.kind == "var" else f":{fn.name}"
            self.problem(fn, f"{target} runs right away here, while this line runs. Make a small function (func do_it(): {target}) and pass its name.")
            return
        if fn.kind == "const" and isinstance(fn.value, str):
            self.problem(fn, f"This needs a function name, not text. Write {fn.value} without the quotes, and make it with func {fn.value}():")
            return
        if fn.kind != "var" or not self.only_func(fn.name):
            return
        gives, what = self.EVENT_GIVES[name]
        want = len(self.funcs[fn.name])
        if want > gives:
            given = "doesn't give it any" if gives == 0 else "only gives it 1 (the new value)"
            fix = f" Write it as: func {fn.name}():" if gives == 0 else ""
            self.problem(fn, f"{fn.name}() needs {want} input{'s' if want != 1 else ''}, but {what} {given}.{fix}")
        node = self.func_nodes.get(fn.name)
        if node is not None and id(node) not in self.handlers_seen:
            self.handlers_seen.add(id(node))
            for x in nodes(node.body):
                if x.kind == "call" and x.fn.kind == "var" and x.fn.name == "wait" and "wait" not in self.user:
                    self.problem(x, "wait() freezes the window: nothing redraws or runs until it's over. To do something later, use app:after(seconds, fn).")
                elif x.kind == "input":
                    self.problem(x, "input reads from the console and freezes the window while it waits. In a window app, ask with app:ask \"...\" instead.")

    def check_range_len(self, s):
        """for i in range(len(items)) with items[i] inside: Tuff's range includes both ends, so i reaches len(items)."""
        it = s.items
        if not (it.kind == "call" and it.fn.kind == "var" and it.fn.name == "range" and "range" not in self.user and 1 <= len(it.args) <= 3):
            return
        ends = [it.args[0]] if len(it.args) == 1 else [it.args[0], it.args[1]]

        def len_of(x):
            if x.kind == "call" and x.fn.kind == "var" and x.fn.name == "len" and "len" not in self.user and len(x.args) == 1 and x.args[0].kind == "var":
                return x.args[0].name
            if x.kind == "var":
                sets = self.assigned.get(x.name, [])
                if len(sets) == 1 and sets[0].op == "=" and x.name not in self.params and x.name not in self.loop_vars:
                    return len_of(sets[0].value)
            return None

        body = list(nodes(s.body))
        indexed = {x.obj.name for x in body if x.kind == "index" and x.obj.kind == "var" and x.index.kind == "var" and x.index.name == s.name}
        if not indexed:
            return
        compared = any(x.kind == "binop" and x.op in self.COMPARE and any(y.kind == "var" and y.name == s.name for y in (x.left, x.right)) for x in body)

        def changed(lst, where):
            return any(x.kind == "assign" and x.target.kind == "var" and x.target.name in (s.name, lst) for x in body) or \
                any(x.kind == "method" and x.obj.kind == "var" and x.obj.name == lst and x.name in ("add", "remove", "pop") for x in where)

        if compared:
            return

        def fixed_literal(lst):
            """How long lst is, if it's a list written out once and never grown or shrunk."""
            sets = self.assigned.get(lst, [])
            if len(sets) == 1 and sets[0].op == "=" and sets[0].value.kind == "list" and lst not in self.params and lst not in self.loop_vars:
                return len(sets[0].value.items)
            return None

        everything = list(nodes(self.program))
        for lst in sorted(indexed):
            if changed(lst, body):
                continue
            by_len = lst in [len_of(x) for x in ends]
            size = None if changed(lst, everything) else fixed_literal(lst)
            by_size = size is not None and any(x.kind == "const" and x.value == size for x in ends)
            if by_len or by_size:
                top = f"len({lst})" if by_len else str(size)
                self.problem(s, f"Tuff's range includes both ends, so {s.name} reaches {top}, and {lst}[{s.name}] goes past the last item "
                                f"(positions go from 0 to len({lst}) - 1). Use  for item in {lst}:  or  range(0, len({lst}) - 1).")
                return
            if any(x.kind == "neg" and x.value.kind == "const" and x.value.value == 1 for x in ends):
                self.problem(s, f"Tuff's range includes both ends, so {s.name} reaches -1, and {lst}[-1] is the last item again. "
                                f"Stop at 0 instead, like range(len({lst}) - 1, 0, -1).")
                return

    # ---- atgui (its tables come from tuff_atgui.tables(); its kinds are written "@button", "@window"...)
    def atgui_kind(self, kind, e):
        """What an atgui method gives back: another widget, the same one (so calls can be chained), or a value."""
        at = atgui_tables()
        if at is None:
            return None
        name = e.name
        made = at["makes_on"].get(kind, {}).get(name)
        if made:
            return "@" + made
        methods = at["kinds"].get(kind, {})
        if name in at["makes"] and "heading" in methods:
            if name == "icon" and kind == "window" and self.atgui_file(e.args[0] if e.args else None):
                return None
            return "@" + at["makes"][name]
        if name == "value" and not e.args:
            return ("$text" if kind in at["text_values"] else "$bool" if kind in at["bool_values"]
                    else "$number" if kind in at["number_values"] else None)
        if name in ("confirm", "showing"):
            return "$bool"
        if name == "ask":
            return "$text"
        if name == "items":
            return "$list"
        if name in at["self_methods"] and name in methods:
            return "@" + kind
        return None

    def atgui_file(self, arg):
        """Is this input a picture file's name (rather than a built-in icon's)?"""
        if arg is None or arg.kind != "const" or not isinstance(arg.value, str):
            return False
        text = arg.value.strip().lower()
        return text.endswith(atgui_tables()["image_exts"]) or "/" in text or "\\" in text

    def check_atgui(self, e, kind):
        at = atgui_tables()
        methods = at["kinds"].get(kind) if at else None
        if methods is None:
            return
        name, n = e.name, len(e.args)
        owner = e.obj.name if e.obj.kind == "var" else "thing"
        if name not in methods:
            self.problem(e, method_help(a_kind(kind).capitalize(), name, list(methods)))
            return
        if not accepts(methods[name], n):
            if e.bare and accepts(methods[name], 0):
                self.problem(e, f"{owner}:{name} doesn't take an input, so what comes after it was read as one. Write {owner}:{name}() instead.")
            else:
                self.problem(e, f"{kind}:{name} got the wrong number of inputs ({n}).")
            return
        self.atgui_values(e, kind, at)
        self.atgui_handler(e, at)
        if kind == "dropdown" and name == "set" and e.obj.kind == "var" and e.args:
            self.check_dropdown_set(e)

    def atgui_values(self, e, kind, at):
        """Styles, icons, themes, colors, animations and keys written as text must be ones atgui knows."""
        name = e.name
        container = "heading" in at["kinds"].get(kind, {})

        def const(i):
            a = e.args[i] if len(e.args) > i else None
            ok = a is not None and a.kind == "const" and isinstance(a.value, str)
            return a, a.value.strip().lower() if ok else None

        def one_of(i, choices, msg, aliases=()):
            a, v = const(i)
            if v is not None and v not in choices and v not in aliases:
                self.problem(a, msg.replace("{}", v))

        buttons = "'{}' isn't a button style. Use one of: " + ", ".join(at["button_styles"]) + "."
        badges = "'{}' isn't a badge style. Use one of: " + ", ".join(at["badge_styles"]) + "."
        if name == "button" and container:
            one_of(2, at["button_styles"], buttons)
        elif name == "badge" and container:
            one_of(1, at["badge_styles"], badges, at["badge_aliases"])
        elif name == "style" and len(e.args) == 1:
            if kind == "button":
                one_of(0, at["button_styles"], buttons)
            elif kind == "badge":
                one_of(0, at["badge_styles"], badges, at["badge_aliases"])
            elif kind == "spinner":
                one_of(0, at["spinner_styles"], "A spinner's style can be \"ring\" or \"dots\".")
            else:
                self.problem(e, f"{kind}:style needs a name and a value, like box:style(\"radius\", 12).")
        elif name == "style":
            a, v = const(0)
            first, _, rest = (v or "").partition(" ")
            prop = rest.strip() if first in at["states"] and rest else v
            if v is not None and prop not in at["styles"] and "-" not in prop:
                hint = difflib.get_close_matches(prop, list(at["styles"]), n=1, cutoff=0.6)
                self.problem(a, f"'{prop}' isn't a style I know." + (f" Did you mean \"{hint[0]}\"?" if hint else
                             " Try: background, color, radius, padding, border, shadow, size, bold, opacity, glass, gradient, width or height."))
        elif name == "theme":
            one_of(0, at["themes"], "The theme can be \"dark\", \"light\" or \"system\".")
        elif name == "accent":
            a, v = const(0)
            if v is not None and v not in at["accents"] and not re.fullmatch(r"#(?:[0-9a-f]{3}|[0-9a-f]{6})", v):
                self.problem(a, f"'{v}' isn't an accent color. Try {', '.join(at['accents'])} or a hex code like \"#ff8800\".")
        elif name == "icon" and kind == "window" and self.atgui_file(e.args[0] if e.args else None):
            self.atgui_picture(e.args[0], icon=True)
        elif name == "icon":
            a, v = const(0)
            if v is not None and v not in at["icons"]:
                hint = difflib.get_close_matches(v, list(at["icons"]), n=1, cutoff=0.6)
                self.problem(a, f"There's no icon called '{v}'." + (f" Did you mean \"{hint[0]}\"?" if hint else
                             " Try home, search, settings, user, chat, send, plus, check, x, star, heart, trash, edit or bell."))
        elif (name == "image" and container) or (name == "set" and kind == "image"):
            self.atgui_picture(e.args[0] if e.args else None)
        elif name == "animate":
            one_of(0, at["animations"], "There's no animation called '{}'. Try one of: " + ", ".join(at["animations"]) + ".")
        elif name == "toast":
            one_of(1, at["toast_styles"], "A toast's style can be " + ", ".join(at["toast_styles"]) + ".", at["toast_aliases"])
        elif name == "chart" and container:
            one_of(1, at["charts"], "A chart can be \"line\" or \"bar\".")
        elif name == "key" and kind == "window":
            a, v = const(0)
            if v is not None and at["key_combo"](v) is None:
                self.problem(a, f"'{v}' isn't a key I know. Write keys like \"ctrl+s\", \"escape\", \"f5\" or \"ctrl+shift+n\".")
        elif name == "sidebar":
            one_of(1, ("left", "right"), "A sidebar goes on the \"left\" or the \"right\".")
        elif name == "align":
            one_of(0, at["align"], "align can be start, center, end or stretch.")
        elif name == "justify":
            one_of(0, at["justify"], "justify can be start, center, end, between, around or evenly.")

    def atgui_picture(self, arg, icon=False):
        """A picture named in the program: a kind of file atgui can show, and there (when we know the folder)."""
        if arg is None or arg.kind != "const" or not isinstance(arg.value, str):
            return
        path = arg.value.strip()
        if not icon and re.match(r"^(https?:|data:)", path, re.I):
            return
        if not path.lower().endswith((".png", ".ico") if icon else atgui_tables()["image_exts"]):
            self.problem(arg, f"Couldn't use '{path}' as the window's icon. Use a .png or .ico file." if icon
                         else f"'{path}' isn't a picture. Use a .png, .jpg, .gif, .webp or .svg file.")
            return
        base = self.base_dir
        if base and os.path.abspath(base).lower().startswith(os.path.abspath(tempfile.gettempdir()).lower()):
            base = None  # a snippet in a temporary folder: its files aren't next to it
        # atgui's window shows pictures from the .tuf's folder and the folders inside it (a window icon can be anywhere).
        if not icon and leaves_folder(path, base):
            self.problem(arg, f"'{path}' is outside the folder your .tuf file is in, so atgui can't show it. "
                              "Put the picture next to your .tuf file, or in a folder inside it.")
            return
        if base and not os.path.isabs(path):
            if not os.path.isfile(os.path.join(base, path)):
                what = "icon" if icon else "image"
                self.problem(arg, f"Couldn't find the {what} '{path}'. Put the picture in your project folder (next to your .tuf file).")

    def atgui_handler(self, e, at):
        """Event functions are passed by name, and don't ask for more inputs than their event gives."""
        name = e.name
        if name not in at["events"]:
            return
        gives, what, pos, given = at["events"][name]
        fn = e.args[pos] if len(e.args) > pos else None
        if fn is None:
            return
        if fn.kind == "call" and fn.fn.kind == "var" and self.only_func(fn.fn.name) and not self.returns_function(fn.fn.name):
            f = fn.fn.name
            self.problem(fn, f"Pass the function's name without brackets: {f}, not {f}(). With brackets it runs once at the start instead of when it should.")
            return
        if fn.kind == "method":
            target = f"{fn.obj.name}:{fn.name}" if fn.obj.kind == "var" else f":{fn.name}"
            self.problem(fn, f"{target} runs right away here, while this line runs. Make a small function (func do_it(): {target}) and pass its name.")
            return
        if fn.kind == "const" and isinstance(fn.value, str):
            self.problem(fn, f"This needs a function name, not text. Write {fn.value} without the quotes, and make it with func {fn.value}():")
            return
        if fn.kind != "var" or not self.only_func(fn.name):
            return
        want = len(self.funcs[fn.name])
        if want > gives:
            how = "doesn't give it any. Write it as: func " + fn.name + "():" if gives == 0 else f"only gives it 1 ({given})."
            self.problem(fn, f"{fn.name}() needs {want} input{'s' if want != 1 else ''}, but {what} {how}")
        node = self.func_nodes.get(fn.name)
        if node is not None and id(node) not in self.handlers_seen:
            self.handlers_seen.add(id(node))
            for x in nodes(node.body):
                if x.kind == "call" and x.fn.kind == "var" and x.fn.name == "wait" and "wait" not in self.user:
                    self.problem(x, "wait() freezes the window: nothing redraws or runs until it's over. To do something later, use app:after(seconds, fn).")
                elif x.kind == "input":
                    self.problem(x, "input reads from the console and freezes the window while it waits. In a window app, ask with app:ask \"...\" instead.")


# atgui's event methods too, so a missing event function gets "Make it with func" (atgui's checks are just above).
Checker.HANDLER_POS = {**Checker.HANDLER_POS, "clicked": 0, "hover": 0, "focus": 0, "key": 1, "closed": 0, "item": 1}


# ---------------------------------------------------------------- Tuff Engine's preview (tuff.py --scene)
class SceneConsole(Console):
    """Prints nothing and answers input() with "", so a preview never shows output or waits."""
    def write(self, text):
        pass

    def input(self, prompt):
        return ""


class SceneInterpreter(Interpreter):
    """Keeps the stack of lines being run (lines[0] is the top-level line), so tgame can tell which line made
    each thing. wait() returns at once."""
    def __init__(self, src, base_dir):
        super().__init__(src, base_dir)
        self.console = SceneConsole()
        self.lines = []

    def run(self, s, env):
        self.lines.append(s.line)
        try:
            return super().run(s, env)
        finally:
            self.lines.pop()

    def b_wait(self, seconds):
        return None

    def lib_anims(self):
        """anims' lines show at once (they would sleep): a preview never waits."""
        names = list(super().lib_anims())
        console = self.console
        return {name: Builtin(f"anims.{name}", lambda *_a: console.say("")) for name in names}


OTHER_WINDOW = re.compile(r"^[ \t]*(?:import|mention)[ \t]+(?:tgui|mtgui|atgui)\b", re.M)


def scene_file(game_path, source_path, out_path):
    """Runs a tgame program's setup with no window and writes what it made as JSON. Always exits 0."""
    import json
    import tuff_tgame
    data = {"v": 1, "mode": None, "batch": [], "things": [], "player": None, "error": None,
            "tables": tuff_tgame.editor_tables()}
    src = read_source(source_path)
    if src is None:
        data["stopped"] = "unreadable"
    elif not TGAME_IMPORT.search(src):
        data["stopped"] = "nogame"
    elif OTHER_WINDOW.search(src):
        data["stopped"] = "other-window"   # runs nothing: those libraries open real windows
    else:
        os.environ["TUFF_SCENE"] = "1"
        random.seed(0)
        interp = SceneInterpreter(src, os.path.dirname(os.path.abspath(game_path)))
        scene = tuff_tgame.start_scene(interp)
        error = None
        try:
            program = Parser(tokenize(src)).program()
            for stmt in program:
                if stmt.kind == "func":
                    interp.run(stmt, interp.globals)
            interp.run_block(program, interp.globals)
            for hook in interp.rt.finish_hooks:
                hook()
        except tuff_tgame.SceneDone:
            pass
        except TuffError as err:
            error = {"line": err.line, "col": err.col, "message": err.msg}
        except (ReturnSignal, BreakSignal, ContinueSignal) as sig:
            word = {"ReturnSignal": "return", "BreakSignal": "break", "ContinueSignal": "continue"}[type(sig).__name__]
            error = {"line": sig.line, "col": sig.col, "message": f"'{word}' can't be used here."}
        except RecursionError:
            error = {"line": None, "col": None, "message": "A function called itself too many times."}
        except Exception as exc:  # a bug in scene mode must never hang the editor
            error = {"line": None, "col": None, "message": f"Tuff Engine's preview had a problem: {exc}"}
        try:
            data.update(scene.dump(error))
        except Exception as exc:
            data.update(stopped="error", batch=[], things=[],
                        error={"line": None, "col": None, "message": f"Tuff Engine's preview had a problem: {exc}"})
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"), default=list)
    return 0


# ---------------------------------------------------------------- entry point

def report(err, src):
    lines = source_lines(src)
    out = [f"Tuff error on line {err.line}: {err.msg}" if err.line else f"Tuff error: {err.msg}"]
    if err.line and 0 < err.line <= len(lines):
        code = lines[err.line - 1]
        gutter = f"  {err.line} | "
        out.append(gutter + code)
        if err.col:
            out.append(" " * (len(gutter) + err.col - 1) + "^")
    if IDE and err.line:
        sys.stdout.write(f"\x1b]tuff;error;{err.line};{err.col or 1};{b64(err.msg)}\x07")
        sys.stdout.flush()
    sys.stderr.write("\n".join(out) + "\n")
    sys.stderr.flush()
    if WINDOWED:
        try:
            from tkinter import messagebox
            messagebox.showerror("Something went wrong", "\n".join(out[:2]))
        except Exception:
            pass


WINDOWED = False


def setup_streams():
    global WINDOWED
    if sys.stdout is None:
        WINDOWED = True
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
        sys.stdin = open(os.devnull, encoding="utf-8")
    elif IDE:
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
        sys.stderr.reconfigure(encoding="utf-8", newline="\n")
        sys.stdin.reconfigure(encoding="utf-8")
    else:
        # Piped (an agent's tuff_run, a test, `> out.txt`): UTF-8 both ways, as in the IDE. The built runtime
        # ignores PYTHONIOENCODING, so on Windows a pipe would otherwise get the old code page and "°" or "…"
        # would come out as "�". A real terminal keeps its own encoding.
        for stream in (sys.stdout, sys.stderr, sys.stdin):
            try:
                if stream is not None and not stream.isatty():
                    stream.reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, OSError, ValueError):  # a closed or unusual stream: leave it as it is
                pass
        sys.stdout.reconfigure(errors="replace")
        if os.name == "nt":
            os.system("")


def read_source(path):
    """The program's text, or None after a one-line message when the file can't be read."""
    try:
        with open(path, "rb") as f:
            data = f.read()
        # UTF-8 (with or without a BOM), or UTF-16 with its BOM: Notepad's "Unicode", and what Windows
        # PowerShell's > and Out-File write.
        text = data.decode("utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig")
        return text.replace("\r\n", "\n").replace("\r", "\n")
    except FileNotFoundError:
        msg = f"There's no file called '{path}'."
    except UnicodeDecodeError:
        msg = f"'{path}' isn't a text file, so it can't be a Tuff program." if b"\x00" in data else \
            f"'{path}' isn't saved as UTF-8, so Tuff can't read it. Save it again as UTF-8, or copy its code into a new TuffCode file."
    except OSError as exc:
        msg = f"'{path}' is a folder, not a .tuf file." if os.path.isdir(path) else f"Couldn't open '{path}': {exc.strerror or exc}."
    report(TuffError(msg), "")
    return None


def run_file(path):
    src = read_source(path)
    if src is None:
        return 1
    try:
        program = Parser(tokenize(src)).program()
        interp = Interpreter(src, os.path.dirname(os.path.abspath(path)))
        for stmt in program:
            if stmt.kind == "func":
                interp.run(stmt, interp.globals)
        interp.run_block(program, interp.globals)
        for hook in interp.rt.finish_hooks:
            hook()
    except TuffError as err:
        report(err, src)
        return 1
    except (ReturnSignal, BreakSignal, ContinueSignal) as sig:
        word = {"ReturnSignal": "return", "BreakSignal": "break", "ContinueSignal": "continue"}[type(sig).__name__]
        report(TuffError(f"'{word}' can only be used inside a {'function' if word == 'return' else 'loop'}.", sig.line, sig.col), src)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


def run_program(path):
    src = read_source(path)
    if src is None:
        return 1
    if not VIEW_IMPORT.search(src):
        return run_file(path)
    if TGAME_IMPORT.search(src) and not WINDOWED:
        Console(first_id=0).say(TGAME_NOTICE, "notice")  # line 0: the program's own lines start at 1
    try:
        import tuff_view
    except ImportError:
        report(TuffError("This program needs Tuff's window engine (tuff_view.py), which isn't installed next to tuff.py."), src)
        return 1
    try:
        code = tuff_view.run(run_file, path)
    except KeyboardInterrupt:
        return 130
    except tuff_view.ViewError as err:
        report(TuffError(str(err)), src)
        return 1
    return 0 if code is None else code


def check_file(path):
    src = read_source(path)
    if src is None:
        return 1
    try:
        program = Parser(tokenize(src)).program()
    except TuffError as err:
        report(err, src)
        return 1
    try:
        problems = Checker(program, os.path.dirname(os.path.abspath(path))).run()
    except Exception:  # a bug in the checker must never block a correct program
        problems = []
    if problems:
        line, col, msg = problems[0]
        report(TuffError(msg, line, col), src)
        for line, col, msg in problems[1:10]:
            sys.stderr.write(f"Also on line {line}: {msg}\n")
        if len(problems) > 10:
            sys.stderr.write(f"...and {len(problems) - 10} more.\n")
        sys.stderr.flush()
        return 1
    print("OK")
    return 0


def usage():
    me = os.path.basename(sys.executable) if getattr(sys, "frozen", False) else "python tuff.py"
    return ("Usage:\n"
            f"  {me} yourfile.tuf            run a Tuff program\n"
            f"  {me} --check yourfile.tuf    check it for mistakes without running it")


def main():
    setup_streams()
    args = sys.argv[1:]
    if not args:
        print("Welcome to TuffCode, coding made easy.")
        print("TuffCode runs on its own coding language called Tuff, files end in .tuf")
        print("Run a program with: python tuff.py yourfile.tuf")
        return 0
    if args[0] in ("--help", "-h", "/?"):
        print(usage())
        return 0
    if args[0] == "--check":
        if len(args) < 2:
            sys.stderr.write("--check needs a file to check.\n" + usage() + "\n")
            return 2
        return check_file(args[1])
    if args[0] == "--scene":
        if len(args) < 4:
            sys.stderr.write("--scene needs the game file, the source file and the output file.\n")
            return 2
        return scene_file(args[1], args[2], args[3])
    if args[0].startswith("--") and not os.path.exists(args[0]):
        sys.stderr.write(f"Unknown option '{args[0]}'.\n" + usage() + "\n")
        return 2
    code = run_program(args[0])
    if getattr(sys, "frozen", False) and not WINDOWED and not IDE:
        try:
            input("\nPress Enter to close...")
        except EOFError:
            pass
    return code


if __name__ == "__main__":
    sys.exit(main())
