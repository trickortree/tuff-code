"""Tuff - the language behind TuffCode. Run a program with: python tuff.py file.tuf"""
import base64
import difflib
import inspect
import math
import os
import random
import sys
import time

IDE = os.environ.get("TUFF_IDE") == "1"

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


def tokenize(src):
    toks = []
    indents = [0]
    depth = 0
    lines = src.splitlines()
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
                        out.append(ESCAPES.get(raw[j + 1], raw[j + 1]))
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
        if self.at("COLON") or self.at("KW", "then"):
            self.next()
        elif not (opener_optional and self.at("NEWLINE")):
            raise TuffError(f"Expected ':' or 'then' to start a block, but found {tok.show()}.", tok.line, tok.col)
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
                name = self.member_name("Expected a method name after ':'.")
                if self.at("OP", "("):
                    self.next()
                    args = self.call_args(")")
                elif self.starts_expr():
                    args = [self.expr()]
                else:
                    args = []
                node = N("method", tok, obj=node, name=name, args=args)
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
    def __init__(self, name, params, body, env):
        self.name, self.params, self.body, self.env = name, params, body, env


class Builtin:
    def __init__(self, name, fn):
        self.name, self.fn = name, fn


class Line:
    def __init__(self, id_, text, row):
        self.id, self.text, self.row = id_, text, row


class Module:
    def __init__(self, name, members):
        self.name, self.members = name, members


class Native:
    """An object made by a library (like a tgui button) with its own :methods."""

    def __init__(self, kind, methods):
        self.kind, self.methods = kind, methods


class AllLines:
    pass


ALL = AllLines()
LIBRARIES = ("anims", "tgui", "mtgui")


class ReturnSignal(Exception):
    def __init__(self, value):
        self.value = value


class BreakSignal(Exception):
    pass


class ContinueSignal(Exception):
    pass


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
        return f"<{v.kind}>"
    if v is ALL:
        return "all"
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
    return "a function"


def truthy(v):
    if isinstance(v, Line):
        return True
    return v not in (None, False, 0, "") and v != []


def plain(v):
    return v.text if isinstance(v, Line) else v


def call_python(label, fn, args):
    """Call a built-in written in Python, turning Python problems into friendly Tuff errors."""
    try:
        inspect.signature(fn).bind(*args)
    except TypeError:
        raise TuffError(f"{label} got the wrong number of inputs ({len(args)}).")
    except ValueError:
        pass
    try:
        return fn(*args)
    except (TuffError, ReturnSignal, BreakSignal, ContinueSignal, KeyboardInterrupt, SystemExit, RecursionError):
        raise
    except Exception as exc:
        raise TuffError(f"{label} failed: {exc}")


class Console:
    def __init__(self):
        self.next_id = 1
        self.rows = 0

    def write(self, text):
        sys.stdout.write(text)
        sys.stdout.flush()

    def say(self, text):
        line = Line(self.next_id, text, self.rows)
        self.next_id += 1
        if IDE:
            self.write(f"\x1b]tuff;say;{line.id};{b64(text)}\x07\n")
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
        self.rows += 1
        return data.lstrip("﻿").rstrip("\r\n")


class Env:
    def __init__(self, parent=None):
        self.vars = {}
        self.parent = parent

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
        env = self.find(name) or self
        env.vars[name] = value


class Runtime:
    """The small toolbox libraries (like tgui) use to talk to the interpreter."""

    def __init__(self, interp):
        self.interp = interp
        self.finish_hooks = []

    def text(self, v):
        return to_text(plain(v))

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

    def native(self, kind, methods):
        return Native(kind, methods)

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
            report(err, self.interp.src)
        except RecursionError:
            report(TuffError(f"{getattr(fn, 'name', 'This function')}() called itself too many times."), self.interp.src)
        except (BreakSignal, ContinueSignal):
            report(TuffError("'break' and 'continue' can only be used inside a loop."), self.interp.src)
        return False, None


class Interpreter:
    def __init__(self, src="", base_dir="."):
        self.src = src
        self.base_dir = base_dir
        self.rt = Runtime(self)
        self.console = Console()
        self.globals = Env()
        builtins = {
            "print": self.b_print,
            "number": self.b_number,
            "text": lambda v: to_text(plain(v)),
            "len": self.b_len,
            "round": lambda v, digits=0: round(v, int(digits)) if digits else round(v),
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
        for name, fn in builtins.items():
            self.globals.vars[name] = Builtin(name, fn)
        self.globals.vars["all"] = ALL
        self.globals.vars["pi"] = math.pi

    # math helpers
    def num_arg(self, name, v):
        v = plain(v)
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

    def b_number(self, v):
        v = plain(v)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return v
        try:
            s = str(v).strip()
            return float(s) if "." in s else int(s)
        except ValueError:
            raise TuffError(f"'{to_text(v)}' isn't a number.")

    def b_len(self, v):
        v = plain(v)
        if not isinstance(v, (str, list)):
            raise TuffError(f"len() needs text or a list, not {type_name(v)}.")
        return len(v)

    def b_random(self, low=1, high=None):
        if high is None:
            low, high = 1, low
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
            raise TuffError(f"Can't loop over {type_name(items)}.")
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
        env.vars[s.name] = Func(s.name, s.params, s.body, env)
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
        raise ReturnSignal(None if s.value is None else self.eval(s.value, env))

    def s_break(self, s, env):
        raise BreakSignal()

    def s_continue(self, s, env):
        raise ContinueSignal()

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
                raise TuffError(f"Can't use [ ] on {type_name(obj)}.")
            return obj[self.list_index(obj, self.eval(e.index, env))]
        if k == "call":
            return self.call(e, env)
        if k == "method":
            return self.method(e, env)
        if k == "attr":
            obj = self.eval(e.obj, env)
            if not isinstance(obj, Module):
                raise TuffError(f"Only libraries use '.', and this is {type_name(obj)}. For methods use ':', like line:rewrite")
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
        verb = {"+": "add", "-": "subtract", "*": "multiply", "/": "divide", "%": "use %", "^": "use ^ on"}[op]
        raise TuffError(f"Can't {verb} {type_name(a)} and {type_name(b)}.")

    def call(self, e, env):
        fn = self.eval(e.fn, env)
        args = [self.eval(a, env) for a in e.args]
        return self.invoke(fn, args)

    def invoke(self, fn, args, loose=False):
        if isinstance(fn, Builtin):
            return call_python(fn.name + "()", fn.fn, args)
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

        if isinstance(obj, Native):
            fn = obj.methods.get(name)
            if fn is None:
                hint = difflib.get_close_matches(name, list(obj.methods), n=1, cutoff=0.6)
                extra = f" Did you mean :{hint[0]}?" if hint else f" Try one of: {', '.join(obj.methods)}."
                raise TuffError(f"A {obj.kind} doesn't have :{name}.{extra}")
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
                self.console.rewrite(obj, "")
                return obj
            if name == "text":
                return obj.text
            obj_kind, options = "line", "rewrite, append, clear, text"
        elif isinstance(obj, str):
            simple = {"upper": str.upper, "lower": str.lower, "trim": str.strip}
            if name in simple:
                return simple[name](obj)
            if name == "has":
                need(1)
                return to_text(args[0]) in obj
            obj_kind, options = "text", "upper, lower, trim, has"
        elif isinstance(obj, list):
            if name == "add":
                need(1)
                obj.append(args[0])
                return obj
            if name == "remove":
                need(1)
                if args[0] not in obj:
                    raise TuffError(f"{to_text(args[0], True)} isn't in this list.")
                obj.remove(args[0])
                return obj
            if name == "pop":
                if not obj:
                    raise TuffError("Can't pop from an empty list.")
                return obj.pop()
            if name == "has":
                need(1)
                return args[0] in obj
            obj_kind, options = "list", "add, remove, pop, has"
        else:
            raise TuffError(f"{type_name(obj).capitalize()} doesn't have any :methods.")
        raise TuffError(f"A {obj_kind} doesn't have :{name}. Try one of: {options}.")


# ---------------------------------------------------------------- entry point

def report(err, src):
    lines = src.splitlines()
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
        sys.stdout.reconfigure(errors="replace")
        if os.name == "nt":
            os.system("")


def run_file(path):
    with open(path, encoding="utf-8-sig") as f:
        src = f.read()
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
        report(TuffError(f"'{word}' can only be used inside a {'function' if word == 'return' else 'loop'}."), src)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


def check_file(path):
    with open(path, encoding="utf-8-sig") as f:
        src = f.read()
    try:
        Parser(tokenize(src)).program()
    except TuffError as err:
        report(err, src)
        return 1
    print("OK")
    return 0


def main():
    setup_streams()
    args = sys.argv[1:]
    if not args:
        print("Welcome to TuffCode, coding made easy.")
        print("TuffCode runs on its own coding language called Tuff, files end in .tuf")
        print("Run a program with: python tuff.py yourfile.tuf")
        return 0
    if args[0] == "--check" and len(args) > 1:
        return check_file(args[1])
    code = run_file(args[0])
    if getattr(sys, "frozen", False) and not WINDOWED:
        try:
            input("\nPress Enter to close...")
        except EOFError:
            pass
    return code


if __name__ == "__main__":
    sys.exit(main())
