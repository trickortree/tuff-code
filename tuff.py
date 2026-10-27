"""Tuff - the language behind TuffCode. Run a program with: python tuff.py file.tuf"""
import base64
import colorsys
import decimal
import difflib
import inspect
import json
import math
import os
import random
import re
import sys
import tempfile
import threading
import time
import types

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
        # 1.5.0: the file the line is in. None until it leaves a function or an imported file (see file_of), then ""
        # for the program itself, or the full path of one of its own files it imported (import money).
        self.file = None


# ---------------------------------------------------------------- tokenizer

class Tok:
    __slots__ = ("kind", "value", "line", "col", "part")

    def __init__(self, kind, value, line, col, part=False):
        self.kind, self.value, self.line, self.col = kind, value, line, col
        self.part = part  # a glued ':' right inside an index's [ ]: a method's ':' or a part's (s[a:b]), the parser decides

    def show(self):
        if self.kind == "STR":
            return f'"{self.value}"'
        if self.kind == "FSTR":
            return 'f"..."'
        if self.kind == "EOF" and self.value:  # the end of the code in a text template's { }: its } or its format's ':'
            return self.value
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


def tokenize(src, first=1):
    """The program's tokens. first: the number of src's first line (the code in a template's { } is read on its own
    line, see template_code)."""
    toks = []
    indents = [0]
    brackets = []  # the open ( [ { a line is inside (a line only continues inside brackets)
    lines = source_lines(src)
    for ln, raw in enumerate(lines, first):
        stripped = raw.lstrip(" \t")
        if not brackets:
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
                if word == "f" and j < n and raw[j] in "\"'":  # a text template: f"{name} has {score} points" (1.5.0)
                    tok, i = template(raw, j, n, ln)
                    toks.append(tok)
                    continue
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
                # In an index's [ ], a:b can be a part (s[a:b]) or, as in 1.3.6, a method (names[order:pop]), and in
                # { } a key and its value ({name:age}) or a method ({"k": box:value}): Parser.part_colon decides. In a
                # list's [ ] and in ( ) it's always a method ([slider:value]).
                part = glued and bool(brackets) and brackets[-1] in ("[i", "{")
                toks.append(Tok("METHOD" if glued else "COLON", ":", ln, col, part=part))
                i += 1
            elif raw[i:i + 2] in ("==", "!=", "<=", ">=", "+=", "-=", "*=", "/="):
                toks.append(Tok("OP", raw[i:i + 2], ln, col))
                i += 2
            elif c in "+-*/%^<>=()[]{},.":
                if c == "[":  # an index's [ ] (after a value: s[1:3]) or a list's ([a, b])
                    after_value = toks and (toks[-1].kind in ("NAME", "STR", "FSTR") or (toks[-1].kind == "OP" and toks[-1].value in ")]}"))
                    if after_value and len(toks) >= 2 and toks[-1].kind == "NAME" and toks[-2].kind == "METHOD" and raw[i - 1] in " \t":
                        after_value = False  # pairs:add [word:upper, 1]: after a method's name and a space, [ starts its input
                    brackets.append("[i" if after_value else "[l")
                elif c in "({":
                    brackets.append(c)
                elif c in ")]}" and brackets:
                    brackets.pop()
                toks.append(Tok("OP", c, ln, col))
                i += 1
            elif not c.isprintable():  # U+2028, a form feed, a no-break space: nothing to see between the quotes
                raise TuffError(f"There's a hidden character here (U+{ord(c):04X}) that Tuff doesn't understand. "
                                "Delete it, or type this line again.", ln, col)
            else:
                raise TuffError(f"I don't understand the character '{c}'.", ln, col)
        if not brackets:
            toks.append(Tok("NEWLINE", None, ln, n + 1))
    end = len(lines) + first
    while len(indents) > 1:
        indents.pop()
        toks.append(Tok("DEDENT", None, end, 1))
    toks.append(Tok("EOF", None, end, 1))
    return toks


# ---- text templates (1.5.0): f"{name} has {score + 1} points", f"Total: {price * qty:money}"

# The formats, by example: 0.00 (2 decimals), 000 (at least 3 digits; 000.0 both), money ($1,234.50) and a width:
# 12 pads to 12 letters (text on the left, numbers on the right), and >12 or <12 says which side the value goes.
TEMPLATE_FORMAT = re.compile(r"(0+)(?:\.(0+))?|money|([<>]?)([1-9][0-9]*)")
FORMAT_HELP = "Formats look like 0.00 (2 decimals), 000 (3 digits or more), money ($12.50) or a width like 10."


def is_template(raw, i):
    """Is the quote at raw[i] the start of a text template, with an f of its own just before it?"""
    return i > 0 and raw[i - 1] == "f" and (i < 2 or not (raw[i - 2].isalnum() or raw[i - 2] == "_"))


def skip_text(raw, i, n):
    """Just past the "text" whose quote is at raw[i], read as tokenize reads it, or None if the line ends first."""
    quote, j = raw[i], i + 1
    while j < n and raw[j] != quote:
        j += 2 if raw[j] == "\\" else 1
    return j + 1 if j < n else None


def skip_template(raw, i, n, ln):
    """Just past the text template whose quote is at raw[i] (one inside another's { }), or None."""
    quote, j = raw[i], i + 1
    while j < n and raw[j] != quote:
        if raw[j] == "\\" and j + 1 < n and raw[j + 1] in ESCAPES:
            j += 2
        elif raw.startswith("{{", j) or raw.startswith("}}", j):
            j += 2
        elif raw[j] == "{":
            end = code_end(raw, j + 1, n, ln)[0]
            if end is None:
                return None
            j = end + 1
        else:
            j += 1
    return j + 1 if j < n else None


def code_end(raw, i, n, ln):
    """Where the code in a template's { } that starts at raw[i] ends: the index of its own } (past any brackets and
    text in it), or None if the line ends first. Also gives the ':'s outside its brackets and text: the last one
    can start a format."""
    opened, colons = [], []
    while i < n:
        c = raw[i]
        if c in "\"'":
            i = skip_template(raw, i, n, ln) if is_template(raw, i) else skip_text(raw, i, n)
            if i is None:
                return None, colons
            continue
        if c == "#":
            raise TuffError("A # comment can't go inside the { } of a text template.", ln, i + 1)
        if c in "([{":
            opened.append(i)
        elif c in ")]}":
            if not opened:
                if c == "}":
                    return i, colons
            elif raw[opened[-1]] + c in ("()", "[]", "{}"):
                opened.pop()
            elif c == "}":  # f"{len(name}": the ( is still open where the { } ends
                at = opened[-1]
                closer = ")]"["([".index(raw[at])]
                raise TuffError(f"This {raw[at]} needs a {closer} before the }} that ends the {{ }}.", ln, at + 1)
        elif c == ":" and not opened:
            colons.append(i)
        i += 1
    return None, colons


def template(raw, q, n, ln):
    """Reads the text template whose quote is at raw[q], with its f just before it. Gives back its token and where
    it ends. The token's value is its parts in order: text, and for each { } a (tokens, format, format's column)."""
    quote, j = raw[q], q + 1
    parts, text = [], []
    while True:
        if j >= n:
            raise TuffError(f"This text is missing its closing {quote}", ln, q)
        c = raw[j]
        if c == quote:
            break
        if c == "\\" and j + 1 < n and raw[j + 1] in ESCAPES:  # "\n" and the rest, as in any text
            text.append(ESCAPES[raw[j + 1]])
            j += 2
        elif raw.startswith("{{", j) or raw.startswith("}}", j):  # {{ and }} show one brace
            text.append(c)
            j += 2
        elif c == "}":
            raise TuffError("A } on its own can't go in a text template. To show one, write }}.", ln, j + 1)
        elif c == "{":
            end, colons = code_end(raw, j + 1, n, ln)
            if end is None:
                raise TuffError("This { has no } to close it. To show a { itself, write {{.", ln, j + 1)
            if text:
                parts.append("".join(text))
                text = []
            parts.append(template_code(raw, j, end, colons, ln))
            j = end + 1
        else:
            text.append(c)  # (a backslash before anything else stays, as in any text: f"C:\{folder}" is C:\ and folder)
            j += 1
    if text or not parts:
        parts.append("".join(text))
    return Tok("FSTR", parts, ln, q), j + 1


def python_format(spec, code):
    """How Tuff writes a Python format (.2f, 05d, ,.2f), for the message about it, or ""."""
    m = re.fullmatch(r"[<>^]?(0?)([0-9]*)(,?)(?:\.([0-9]+))?[dfs%]?", spec)
    if not m:
        return ""
    zero, width, commas, places = m.groups()
    if commas and places == "2":
        better = "money"
    elif places is not None:
        better = "0." + "0" * min(int(places), 100) if int(places) else "0"
    elif zero and width:
        better = "0" * min(int(width), 100)
    else:
        return ""
    return f" Here, write {{{code or 'x'}:{better}}}."


def template_code(raw, brace, end, colons, ln):
    """One { } of a template (raw[brace] is its {, raw[end] its }): the tokens of its code, ended by an EOF token,
    and its format and the format's column (or None, None). The format starts at the last ':' outside brackets and
    text, when what follows that ':' is a format (f"{price * qty:money}"). Otherwise it's a method's ':'
    (f"{name:upper()}"), so f"{d:get("k")}" and f"{ {"a": 1}["a"] }" are code all through."""
    stop, fmt, fmt_col = end, None, None
    if colons:
        at = colons[-1]
        tail = raw[at + 1:end]
        spec = tail.strip()
        method = raw[at - 1] not in " \t" and (tail[:1].isalpha() or tail[:1] == "_")  # glued to a word: name:upper
        m = TEMPLATE_FORMAT.fullmatch(spec)
        if m:
            stop, fmt, fmt_col = at, spec, at + 2 + len(tail) - len(tail.lstrip())
            zeros, decimals, _side, width = m.groups()
            if width and int(width) > 1000:
                raise TuffError(f"{width} is too wide: a width can be up to 1000.", ln, fmt_col)
            if len(zeros or "") > 100 or len(decimals or "") > 100:
                raise TuffError("That format has too many 0s: it can show up to 100 digits on each side of the point.", ln, fmt_col)
        elif not spec:
            raise TuffError("Put a format after the ':', like {price:0.00}, or take the ':' away.", ln, at + 1)
        elif not method:
            raise TuffError(f"'{spec}' isn't a format. {FORMAT_HELP}{python_format(spec, raw[brace + 1:at].strip())}",
                            ln, at + 2 + len(tail) - len(tail.lstrip()))
    if not raw[brace + 1:stop].strip():
        raise TuffError("These { } have nothing in them. Put a value in them, like {name}, or write {{ to show a {.", ln, brace + 1)
    # The code is read by tokenize itself, as a line of its own with spaces before it, so its tokens keep their
    # columns in the real line (and a template in it is read the same way).
    toks = [t for t in tokenize(" " * (brace + 1) + raw[brace + 1:stop], ln) if t.kind not in ("INDENT", "DEDENT", "NEWLINE", "EOF")]
    toks.append(Tok("EOF", ":" if fmt else "}", ln, stop + 1))
    return toks, fmt, fmt_col


# ---------------------------------------------------------------- parser

class N:
    def __init__(self, kind, tok, **fields):
        self.kind = kind
        self.line = tok.line
        self.col = tok.col
        self.__dict__.update(fields)


EXPR_STARTS = {"NUM", "STR", "FSTR", "NAME"}
EXPR_START_KWS = {"say", "input", "not", "true", "false", "nil"}
ASSIGN_OPS = {"=", "+=", "-=", "*=", "/="}
COMPARE_OPS = {"==", "!=", "<", ">", "<=", ">="}


class Parser:
    def __init__(self, toks):
        self.toks = toks
        self.i = 0
        self.converted = []  # the glued ':'s chosen as a part's ':' (see index), so a reparse can undo them
        # The names the program gives a value (x = ..., for x in): a variable called try or catch stays one.
        self.given = {t.value for t, nxt in zip(toks, toks[1:]) if t.kind == "NAME" and nxt.kind == "OP" and nxt.value in ASSIGN_OPS}
        self.given |= {nxt.value for t, nxt in zip(toks, toks[1:]) if t.kind == "KW" and t.value == "for" and nxt.kind == "NAME"}
        inputs = False  # func f(catch): its inputs
        self.funcs = {nxt.value for t, nxt in zip(toks, toks[1:]) if t.kind == "KW" and t.value == "func" and nxt.kind == "NAME"}
        for t, nxt in zip(toks, toks[1:]):
            if t.kind == "KW" and t.value == "func":
                inputs = None
            elif inputs is None and t.kind == "OP" and t.value == "(":
                inputs = True
            elif inputs and t.kind == "NAME":
                self.given.add(t.value)
            elif inputs is not False and t.kind == "OP" and t.value == ")":
                inputs = False
        self.values = self.given | self.funcs | BUILTIN_NAMES | OWN_NAME_BUILTINS | {"err", "pi", "all"}
        # What this file imports or mentions: its libraries and its own files (money.rate = 2 says so, see simple_statement).
        self.imported = {nxt.value for t, nxt in zip(toks, toks[1:]) if t.kind == "KW" and t.value in ("import", "mention") and nxt.kind == "NAME"}
        self.depth = 0  # how many blocks in the statement being read is (a kind is made at the top: depth 0)
        self.kinds = {}  # the kinds read so far: name -> line (1.5.0)
        self.kind_name = None  # the kind whose block is being read
        self.in_action = None  # the kind whose action is being read: its my is that kind's object

    def block_word(self, ahead, catch=False):
        """Is the try or catch here (ahead tokens before the ':') the start of a block? try: and catch: with a
        ':' that ends the line or has a space after it are, and catch problem: is. try:say "hi" (the ':' glued to
        a word) is too, unless the program has its own variable called try."""
        word = self.toks[self.i + ahead - 1].value
        nxt = self.toks[self.i + ahead]
        if nxt.kind == "COLON":
            return True
        if catch and nxt.kind == "NAME":
            return self.toks[self.i + ahead + 1].kind in ("COLON", "METHOD")
        return nxt.kind == "METHOD" and word not in self.given

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
            or (tok.kind == "OP" and tok.value in ("(", "[", "{", "-"))
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
        self.depth += 1
        try:
            return self.block_lines(opener_optional)
        finally:
            self.depth -= 1

    def block_lines(self, opener_optional):
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
                name = self.expect("NAME", msg=f"Expected a library's name, like: {tok.value} anims, or one of your files' (without .tuf), "
                                               f"like: {tok.value} money").value
                self.end_line()
                return N("import", tok, name=name, word=tok.value)
        # kind Pet: (1.5.0). A soft word too: kind followed by a name can't be anything else, so a program's own
        # variable called kind (kind = "dog", kind:upper()) keeps working.
        if tok.kind == "NAME" and tok.value == "kind" and self.toks[self.i + 1].kind == "NAME":
            return self.kind_def()
        if tok.kind == "NAME" and tok.value == "class" and self.toks[self.i + 1].kind == "NAME":
            name = self.toks[self.i + 1].value
            raise TuffError(f"Tuff has no classes. To make your own kind of object, write: kind {name}: then its fields "
                            "and actions, indented under it.", tok.line, tok.col)
        # try: ... catch: (or catch problem:) ... (1.4.0). Soft words: they only count at the start of a line with a
        # ':' after them, and a program that gives try or catch a value (catch = [], then catch:add(fish)) keeps them.
        if tok.kind == "NAME" and tok.value == "try" and self.block_word(1):
            self.next()
            body = self.block()
            if not (self.at("NAME", "catch") and self.block_word(1, catch=True)):
                nxt = self.peek()
                if nxt.kind == "NAME" and nxt.value in ("except", "catch", "rescue"):
                    raise TuffError("Write the catch line as catch: or catch problem: (a name for the problem, no brackets).",
                                    nxt.line, nxt.col)
                raise TuffError("A try: block needs a catch: block right after it, for when something goes wrong.", nxt.line, nxt.col)
            self.next()
            name = None
            if self.at("NAME"):
                name_tok = self.next()
                name = name_tok.value
                if name in BUILTIN_NAMES or name in OWN_NAME_BUILTINS or name in ("err", "pi", "all"):
                    what = "value" if name in ("err", "pi", "all") else "function"
                    raise TuffError(f"{name} is Tuff's own {what}, so catch can't use it for the problem. "
                                    "Call it something else, like: catch problem:", name_tok.line, name_tok.col)
            return N("try", tok, body=body, name=name, handler=self.block())
        if tok.kind == "NAME" and tok.value == "catch" and self.block_word(1, catch=True):
            raise TuffError("'catch' needs a 'try:' block right above it.", tok.line, tok.col)
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
        kind = self.kind_name if self.depth == 1 else None
        if kind is None:
            return N("func", tok, name=name, params=params, body=self.block())
        # One of a kind's actions (1.5.0): in it, my is the object. Its name is Pet:feed, so it's never mixed up with
        # a function of the program's own called feed.
        if "my" in params:
            raise TuffError("An action's inputs can't be called my: inside an action, my is the object itself.", tok.line, tok.col)
        outer, self.in_action = self.in_action, kind
        try:
            body = self.block()
        finally:
            self.in_action = outer
        for x in nodes(body):
            if (x.kind == "assign" and x.target.kind == "var" and x.target.name == "my") or \
                    (x.kind in ("for", "try") and x.name == "my") or (x.kind == "func" and "my" in x.params):
                raise TuffError(f"Inside an action, my is this {kind} itself, so it can't be given a value. Use another name.",
                                x.line, x.col)
        return N("func", tok, name=f"{kind}:{name}", params=params, body=body, action=name)

    def kind_def(self):
        """kind Pet: (1.5.0), then its fields (name = "?", each with the value a new Pet starts with) and its
        actions (func feed():), indented under it. Only at the top of the program, like the functions should be."""
        tok = self.next()
        name_tok = self.next()
        name = name_tok.value
        if self.depth:
            raise TuffError("Make a kind at the top of the program, not inside a function or a block.", tok.line, tok.col)
        if name in BUILTIN_NAMES or name in OWN_NAME_BUILTINS or name in ("err", "pi", "all", "my", "kind") or name in LIBRARIES:
            what = "library" if name in LIBRARIES or name == "file" else "word" if name in ("my", "kind") else \
                "value" if name in ("err", "pi", "all") else "function"
            like = f", like {name.capitalize()}" if name.capitalize() != name else ""
            raise TuffError(f"{name} is Tuff's own {what}, so a kind can't be called that. Give it a name of its own{like}.",
                            name_tok.line, name_tok.col)
        if name in self.kinds:
            raise TuffError(f"There are two kinds called {name}. This one would replace the one on line {self.kinds[name]}. "
                            "Give them different names.", name_tok.line, name_tok.col)
        if self.at("OP", "("):
            nxt = self.peek()
            raise TuffError(f"A kind can't be made from another kind: Tuff has no inheritance. Write kind {name}: and give it "
                            "fields of its own.", nxt.line, nxt.col)
        if not (self.at("COLON") or self.at("METHOD")):
            nxt = self.peek()
            raise TuffError(f"Expected ':' after the kind's name, like: kind {name}:", nxt.line, nxt.col)
        self.kinds[name] = tok.line
        self.kind_name = name
        try:
            body = self.block()
        finally:
            self.kind_name = None
        fields, actions, made = [], [], {}  # made: each field's and action's name -> what it is
        for s in body:
            if s.kind == "assign" and s.target.kind == "var" and s.op == "=":
                field = s.target.name
                if field == "my":
                    raise TuffError("A field can't be called my: inside an action, my is the object itself.", s.line, s.col)
                if field in made:
                    raise TuffError(f"{name} already has {made[field]} called {field}. Give each field a name of its own.", s.line, s.col)
                made[field] = "a field"
                fields.append(s)
            elif s.kind == "func":
                if s.action in made:
                    raise TuffError(f"{name} already has {made[s.action]} called {s.action}. Give each action a name of its own.",
                                    s.line, s.col)
                made[s.action] = "an action"
                actions.append(s)
            elif s.kind == "assign" and s.target.kind == "var":
                raise TuffError(f"A field gets the value a new {name} starts with, using =, like {s.target.name} = 0.", s.line, s.col)
            else:
                raise TuffError(f"A kind holds fields (like name = \"?\") and actions (like func feed():), and nothing else. "
                                "Put other code outside the kind.", s.line, s.col)
        return N("kind", tok, name=name, fields=fields, actions=actions)

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
            owner = target.obj.name if target.kind == "attr" and target.obj.kind == "var" else None
            if owner in LIBRARIES or owner == "file":
                raise TuffError(f"{owner}.{target.name} is part of Tuff's {owner} library, so it can't be given a value.", tok.line, tok.col)
            if owner in self.imported:  # money.rate = 2 (1.5.0): another file's names are its own
                name = target.name
                raise TuffError(f"{owner}.{name} belongs to {owner}.tuf, so it can't be changed from this file. Give {owner}.tuf a "
                                f"function that changes it, like func set_{name}(new_{name}):, then call {owner}.set_{name}(...).",
                                tok.line, tok.col)
            if target.kind not in ("var", "index", "attr") and not (target.kind == "slice" and target.alt is not None):
                raise TuffError("You can only store a value in a variable, a list item or an object's field.", tok.line, tok.col)
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
            if self.at("METHOD"):  # say:ascii("Hi"), say:color(...): print's methods, by say's name
                return self.postfix(N("sayfn", tok))
            return N("say", tok, value=self.expr())
        if self.at("KW", "input"):
            self.next()
            if self.at("METHOD"):  # input:color("Name? ", "green"): the question in a look, like say:color (1.4.1)
                self.next()
                name_tok = self.peek()
                name = self.member_name('Expected a method name after "input:", like input:color("Name? ", "green").')
                if name not in ("color", "colour"):
                    tip = " For big letters, say them first with say:ascii(...), then ask with input." if name == "ascii" else ""
                    raise TuffError(f'input has one method, :color, like input:color("Name? ", "green"), not :{name}.{tip}',
                                    name_tok.line, name_tok.col)
                if not self.at("OP", "("):
                    raise TuffError('Put input:color\'s question and look in brackets, like input:color("Name? ", "green").',
                                    name_tok.line, name_tok.col)
                self.next()
                args = self.call_args(")")
                if not args:
                    raise TuffError('input:color needs the question first, like input:color("Name? ", "green").', name_tok.line, name_tok.col)
                return N("input", tok, prompt=args[0], looks=args[1:])
            if self.at("OP", "("):
                self.next()
                prompt = None if self.at("OP", ")") else self.expr()
                self.expect("OP", ")")
            else:
                prompt = self.expr() if self.starts_expr() else None
            return N("input", tok, prompt=prompt, looks=None)
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

    def postfix(self, node=None):
        node = self.primary() if node is None else node
        while True:
            tok = self.peek()
            if self.at("OP", "("):
                self.next()
                node = N("call", tok, fn=node, args=self.call_args(")"))
            elif self.at("OP", "["):
                self.next()
                node = self.index(node, tok)
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

    def part_colon(self, in_dict=False):
        """Where the glued ':' that starts this [ ]'s part (s[a:b], s[:n]) is, or this { } entry's value ({name:age}),
        when there's no spaced one at the bracket's own level. With several: the one after a number (or right
        after the bracket), else one followed by the program's own name or a built-in (s[s:find(" "):n],
        email[email:find("@"):len(email) - 1]), else the first that isn't a method call with brackets, else the first."""
        depth, j, found = 0, self.i, []
        while self.toks[j].kind not in ("NEWLINE", "EOF"):
            t = self.toks[j]
            if t.kind == "OP" and t.value in ("(", "[", "{"):
                depth += 1
            elif t.kind == "OP" and t.value in (")", "]", "}"):
                if depth == 0:
                    break
                depth -= 1
            elif depth == 0 and in_dict and t.kind == "OP" and t.value == ",":
                break
            elif depth == 0 and t.kind == "COLON":
                return None
            elif depth == 0 and t.kind == "METHOD" and t.part:
                found.append(j)
            j += 1
        for j in found:
            before = self.toks[j - 1]
            if j == self.i or before.kind == "NUM" or (in_dict and before.kind in ("STR", "FSTR")):
                return j
        for j in found:
            if self.toks[j + 1].kind == "NAME" and self.toks[j + 1].value in self.values:
                return j
        for j in found:
            if not (self.toks[j + 2].kind == "OP" and self.toks[j + 2].value == "("):
                return j
        return found[0] if found else None

    def index(self, obj, tok):
        """x[i], or a part: s[1:3], s[:3], s[2:] (both ends included, like range). A glued a:b here was a method
        call in 1.3.6 (names[order:pop], items[p:index()]). When the start is one value (names[order:pop]), the
        part keeps that reading too, in alt: the value is worked out first either way, and when the program runs a
        number makes it a part. A start worked out from several (items[1 + stack:pop]) is decided here: a part when
        what follows the ':' is the program's own name or a built-in (s[i + 1:j]), else 1.3.6's method call, which
        keeps 1.3.6's order (and what and/or skip)."""
        j = self.part_colon()
        if j is None:
            start = None if self.at("COLON") else self.expr()
            if not self.at("COLON"):
                self.expect("OP", "]")
                return N("index", tok, obj=obj, index=start)
            self.next()
            end = None if self.at("OP", "]") else self.expr()
            self.expect("OP", "]")
            return N("slice", tok, obj=obj, start=start, end=end, recv=None, alt=None, mname=None)
        colon = self.toks[j]
        back, mark = self.i, len(self.converted)
        colon.kind = "COLON"
        self.converted.append(colon)
        try:
            start = None if self.at("COLON") else self.expr()
            self.expect("COLON")
            end = None if self.at("OP", "]") else self.expr()
            self.expect("OP", "]")
        except TuffError:  # not a part after all (names[d:get "k"]): read it as 1.3.6 did
            self.unconvert(mark)
            self.i = back
            start = self.expr()
            self.expect("OP", "]")
            return N("index", tok, obj=obj, index=start)
        node = N("slice", tok, obj=obj, start=start, end=end, recv=None, alt=None, mname=None)
        if start is None or self.toks[j - 1].kind == "NUM":
            return node  # s[:n], s[2:n]: nothing before the ':' can have methods
        single = start.kind in ("var", "call", "index", "slice", "attr", "method") or (start.kind == "const" and isinstance(start.value, str))
        after = self.toks[j + 1]
        if not single and after.kind == "NAME" and after.value in self.values:
            return node  # s[i + 1:j]
        done = self.i
        self.unconvert(mark)
        self.i = back
        try:
            old = self.expr()
            ok = self.at("OP", "]") and self.i + 1 == done
        except TuffError:
            ok = False
        self.i = done
        if not ok:
            return node
        if not single:  # items[1 + stack:pop], x[ok and stack:pop or 0]: 1.3.6's reading
            return N("index", tok, obj=obj, index=old)
        method = next((m for m in nodes(old) if m.kind == "method" and (m.line, m.col) == (colon.line, colon.col)), None)
        if method is None:
            return node
        held = N("held", colon, of=start)
        method.obj = held
        node.start, node.recv, node.alt, node.mname = held, start, old, method.name
        return node

    def unconvert(self, mark):
        """Give the part ':'s chosen since mark back their method meaning."""
        while len(self.converted) > mark:
            self.converted.pop().kind = "METHOD"

    def template(self, tok):
        """f"{name} has {score + 1} points" (1.5.0): its text, and the code in each { } read like any other code.
        That code has tokens of its own (see template_code), with their own columns, so a mistake in it points
        inside the text."""
        parts = []
        for piece in tok.value:
            if isinstance(piece, str):
                parts.append(piece)
                continue
            toks, fmt, fmt_col = piece
            outer = self.toks, self.i
            self.toks, self.i = toks, 0
            try:
                value = self.expr()
                if not self.at("EOF"):
                    extra = self.peek()
                    raise TuffError(f"I didn't expect {extra.show()} here. The {{ }} in a text template hold one value each, "
                                    "like {score + 1}.", extra.line, extra.col)
            finally:
                self.toks, self.i = outer
            parts.append(N("fpart", Tok("FORMAT", fmt, tok.line, fmt_col) if fmt else toks[0], value=value, fmt=fmt))
        return N("fstr", tok, parts=parts)

    def primary(self):
        tok = self.next()
        if tok.kind in ("NUM", "STR"):
            return N("const", tok, value=tok.value)
        if tok.kind == "FSTR":
            return self.template(tok)
        if tok.kind == "NAME":
            if tok.value == "my" and self.in_action:  # an action's my: that kind's object (the checker knows its fields)
                return N("var", tok, name="my", of_kind=self.in_action)
            return N("var", tok, name=tok.value)
        if tok.kind == "KW" and tok.value in ("true", "false", "nil"):
            return N("const", tok, value={"true": True, "false": False, "nil": None}[tok.value])
        if tok.kind == "OP" and tok.value == "(":
            inner = self.expr()
            self.expect("OP", ")")
            return inner
        if tok.kind == "OP" and tok.value == "[":
            return N("list", tok, items=self.call_args("]"))
        if tok.kind == "OP" and tok.value == "{":  # a dictionary: {"sam": 14, "ann": 12}
            keys, values = [], []
            while not self.at("OP", "}"):
                colon = self.part_colon(in_dict=True)  # {name:age}, {names[0]:ages[0]}
                if colon is not None:
                    self.toks[colon].kind = "COLON"
                keys.append(self.expr())
                self.expect("COLON", msg='Expected a \':\' between a key and its value, like {"sam": 14}.')
                values.append(self.expr())
                if not self.at("OP", "}"):
                    self.expect("OP", ",", msg="Expected ',' or '}'.")
            self.next()
            return N("dict", tok, keys=keys, values=values)
        raise TuffError(f"I expected a value here, but found {tok.show()}.", tok.line, tok.col)


# ---------------------------------------------------------------- runtime

class Func:
    def __init__(self, name, params, body, env, line=None, code=None):
        self.name, self.params, self.body, self.env, self.line = name, params, body, env, line
        self.code = code  # 1.5.0: its body compiled (Interpreter.compile_block), or None under the old tree walker


class Kind:
    """A kind of object the program makes (1.5.0): kind Pet:, with its fields in order, the code of each one's
    starting value (worked out again for every new object, so two Pets never share a list), and its actions (Funcs
    that run with my as the object). env: where the starting values are worked out and the actions run."""

    def __init__(self, name, fields, defaults, actions, env, line=None):
        self.name, self.fields, self.defaults, self.actions, self.env, self.line = name, fields, defaults, actions, env, line


class Instance:
    """An object made from a kind: rex = Pet("Rex"). fields holds its fields' values, in the kind's order. Two
    objects are the same (is, ==) only when they are one object, like the same pet."""
    __slots__ = ("kind", "fields")

    def __init__(self, kind, fields):
        self.kind, self.fields = kind, fields


# file.save keeps an object as a dictionary with this key first: {"$kind": "Pet", "name": "Rex", "hunger": 3}. No field
# can have this name, so it never takes one's place, and file.load knows which kind to make again.
SAVED_KIND = "$kind"


def an(word):
    """'a Pet', 'an Owl'."""
    return f"{'an' if word[:1].lower() in 'aeiou' else 'a'} {word}"


def and_list(names):
    """'name', 'name and hunger', 'name, hunger and age'."""
    names = list(names)
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def kind_inputs_help(kind, fields, count):
    """Pet("a", "b", "c") with more inputs than Pet has fields (the run and the checker say the same)."""
    if not fields:
        return f"{kind} has no fields, so {kind}() takes no inputs, but got {count}."
    return (f"{kind} has {len(fields)} field{'s' if len(fields) != 1 else ''} ({and_list(fields)}), so {kind}() takes "
            f"up to {len(fields)} input{'s' if len(fields) != 1 else ''}, one for each field in order, but got {count}.")


def field_help(kind, fields, actions, name, owner):
    """rex.hungr: the field isn't one of the kind's (owner: how the code names the object, or None)."""
    owner = owner or "thing"
    if name in actions:
        return f"{name} is an action of {kind}, so it's called with ':', like {owner}:{name}()"
    hint = difflib.get_close_matches(name, list(fields), n=1, cutoff=0.6)
    if hint:
        return f"{kind} doesn't have a field '{name}'. Did you mean '{hint[0]}'?"
    if fields:
        return f"{kind} doesn't have a field '{name}'. Its fields are: {', '.join(fields)}."
    return f"{kind} doesn't have a field '{name}': it has no fields."


def action_help(kind, fields, actions, name, owner):
    """rex:fead(): the action isn't one of the kind's."""
    owner = owner or "thing"
    if name in fields:
        return f"{name} is a field of {kind}, not an action, so it's read with a dot, like {owner}.{name}"
    hint = difflib.get_close_matches(name, list(actions), n=1, cutoff=0.6)
    if hint:
        return f"{kind} doesn't have an action '{name}'. Did you mean '{hint[0]}'?"
    if actions:
        return f"{kind} doesn't have an action '{name}'. Its actions are: {', '.join(actions)}."
    return f"{kind} doesn't have an action '{name}'. Give it one inside kind {kind}:, like func {name}():"


def action_inputs_help(owner, name, want, got, bare):
    """rex:feed(1) when feed takes no inputs (bare: rex:feed - 1, where rule 1 made "- 1" its input)."""
    if bare and not want:
        return f"{owner}:{name} doesn't take an input, so what comes after it was read as one. Write {owner}:{name}() instead."
    return f"{owner}:{name}() needs {want} input{'s' if want != 1 else ''}, but got {got}."


def kind_not_object(kind, use):
    """Pet.name or Pet:feed(): the kind itself, not an object made from it. use is what was tried, like .name."""
    one = kind.lower() if kind.lower() != kind else "thing"
    return f"{kind} is a kind, not an object made from it. Make one first, like {one} = {kind}(...), then use {one}{use}."


def own_field_help(name, kind, fields):
    """A name that's never given a value: inside an action of kind, one of its fields written on its own (hunger,
    not my.hunger), and my outside every action. None for any other name."""
    if kind and name in fields:
        return f"I don't know what '{name}' is. To use this {kind}'s field, write my.{name}"
    if name == "my":
        return "I don't know what 'my' is. my is the object itself, so it only works inside a kind's actions, like: " \
               "func feed(): my.hunger -= 1"
    return None


def object_brackets(kind, fields, owner, key, then=""):
    """The tip for rex["name"]: an object's fields are read (and set) with a dot. key: the key written, when known."""
    field = key if isinstance(key, str) and key in fields else fields[0] if fields else "name"
    return f"Use its fields with a dot, like {owner or 'thing'}.{field}{then}"


def where_text(e):
    """node_text, and an object's fields too: rex.owner.name (1.5.0)."""
    if e.kind == "attr":
        obj = where_text(e.obj)
        return None if obj is None else f"{obj}.{e.name}"
    return node_text(e)


class Builtin:
    def __init__(self, name, fn, takes_err=False):
        self.name, self.fn = name, fn
        self.takes_err = takes_err  # number(), text(), print()...: an err given to them doesn't stop the program
        self.fits = {}  # 1.5.0: whether fn takes this many inputs, worked out once for each count (see call_python)


class Line:
    def __init__(self, id_, text, row):
        self.id, self.text, self.row = id_, text, row
        self.look, self.art, self.height = None, False, text.count("\n") + 1  # look: say:color, say:ascii, print:pen


class Module:
    def __init__(self, name, members):
        self.name, self.members = name, members


class FileModule(Module):
    """One of the program's own files, loaded with import money (1.5.0). Its functions and top-level values are used
    with a dot, money.as_money(6.375) and money.rate: they're its top level's names as they are right now, so a
    function in it that changes rate changes money.rate too. Every file has a top level of its own (with its own
    built-ins), so its names never clash with the program's."""

    def __init__(self, name, path, shown, env, base):
        self.name, self.path, self.shown, self.env = name, path, shown, env
        self.base = base  # the built-ins every file starts with: they aren't the file's own names
        self.ready = False  # its top-level code has run to the end (until then, importing it again is a circle)

    @property
    def members(self):
        """Its own names: what its top level made (functions, values and its imports)."""
        base = self.base
        return {n: v for n, v in self.env.vars.items() if base.get(n, base) is not v}


class Native:
    """An object made by a library (like a tgui button) with its own :methods."""

    def __init__(self, kind, methods, show=None):
        self.kind, self.methods = kind, methods
        self.show = show  # show(nested) gives the text say shows for it, like a tap response's <response 200>


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
TOO_BIG = "That's too big to work out: a number or text this large doesn't fit in memory."  # inside a method
# 1.5.0: a sum whose answer is too big for a decimal (10 ^ 400 / 3, 2 ^ 99999 * 1.5), which stopped with Python's
# OverflowError before. Whole numbers have no limit, so this is the only number that's too big to work out.
TOO_BIG_NUMBER = ("That number is too big to work out. Whole numbers can be any size, but a decimal (what / gives, or "
                  "a sum with a decimal in it) only goes up to about 1 followed by 308 zeros.")
LIBRARIES = ("anims", "tgui", "mtgui", "tap", "atgui", "tgame", "tdraw")
# Libraries whose windows are web views (tuff_view.py). A program that uses one runs its Tuff code on a
# second thread, because the web view needs the main thread.
VIEW_LIBRARIES = ("atgui", "tgame")
VIEW_IMPORT = re.compile(r"^[ \t]*(?:import|mention)[ \t]+(?:" + "|".join(VIEW_LIBRARIES) + r")\b", re.M)
# The first line a tgame program shows, in yellow, before anything it prints. In TuffCode the line gets an
# "Open Tuff Engine" button (ide.js handleOsc). --check, --scene and --windowed apps never show it.
TGAME_NOTICE = "Tuff Engine is here: open this game in TuffCode's Tuff Engine tab (Ctrl+Shift+G) to build it visually."
TGAME_IMPORT = re.compile(r"^[ \t]*(?:import|mention)[ \t]+tgame\b", re.M)
BUILTIN_NAMES = {"print", "number", "num", "text", "str", "int", "len", "round", "random", "wait", "range", "clear", "sqrt", "abs",
                 "floor", "ceil", "min", "max", "sum", "average",
                 "now", "today", "time", "date", "sin", "cos", "tan", "log"}  # 1.4.0
# Built-ins that are new in Tuff 1.0.4 and that people already use as their own variables (num = 0, err = "...").
# Giving one a value inside a function makes that function's own variable, as it did before they were built in,
# and the built-in stays for the rest of the program. At the top of the program it still replaces the built-in.
OWN_NAME_BUILTINS = {"num", "int", "str", "err",
                     "now", "today", "time", "date", "log", "file", "sin", "cos", "tan"}  # 1.4.0's: names programs already used for their own things


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


# 1.5.0: return, break and continue in compiled code (see Interpreter.compile_stmt). The statement gives back its Jump
# instead of raising a signal, and each block hands it straight up to the loop or the function call it's for, which
# is many times quicker than an exception. Where one would leave compiled code it becomes the signal again
# (Interpreter.unjump), so everything outside sees what it always did.
J_RETURN, J_BREAK, J_CONTINUE = "return", "break", "continue"


class Jump:
    __slots__ = ("kind", "line", "col", "value")

    def __init__(self, kind, line, col):
        self.kind, self.line, self.col = kind, line, col
        self.value = None  # what a return gives back: set just before, and taken (and cleared) at once


def b64(text):
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def to_text(v, nested=False, inside=()):
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
    if isinstance(v, (list, dict)) and any(v is x for x in inside):  # a list that holds itself: [1, [...]]
        return "[...]" if isinstance(v, list) else "{...}"
    if isinstance(v, list):
        return "[" + ", ".join(to_text(x, True, inside + (v,)) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ", ".join(f"{to_text(k, True)}: {to_text(x, True, inside + (v,))}" for k, x in v.items()) + "}"
    if isinstance(v, Line):
        return to_text(v.text, nested)
    if isinstance(v, (Func, Builtin)):
        return f"<func {v.name}>"
    if isinstance(v, FileModule):
        return f"<file {v.shown}>"
    if isinstance(v, Module):
        return f"<library {v.name}>"
    if isinstance(v, Native):
        return v.show(nested) if v.show else f"<{v.kind}>"
    if isinstance(v, Instance):  # Pet(name: "Rex", hunger: 3), and Pet(...) inside itself (rex.best_friend = rex)
        if any(v is x for x in inside):
            return f"{v.kind.name}(...)"
        return v.kind.name + "(" + ", ".join(f"{k}: {to_text(x, True, inside + (v,))}" for k, x in v.fields.items()) + ")"
    if isinstance(v, Kind):
        return f"<kind {v.name}>"
    if v is ALL:
        return "all"
    if isinstance(v, Err):
        return "err"
    return str(v)


def format_value(v, fmt):
    """A value in a text template's format (1.5.0). 0.00 rounds to 2 decimals and 000 shows at least 3 digits, both
    half up, the way people round (2.675 is 2.68, not Python's 2.67), and money is $1,234.50. A width (12) pads text
    on the right and numbers on the left; >12 and <12 choose."""
    v = plain(v)
    zeros, decimals, side, width = TEMPLATE_FORMAT.fullmatch(fmt).groups()
    is_number = isinstance(v, (int, float)) and not isinstance(v, bool)
    if width:
        shown = to_text(v)
        return shown.rjust(int(width)) if side == ">" or (not side and is_number) else shown.ljust(int(width))
    if isinstance(v, Err):
        v.stop(f"The value for the format {fmt}")
    if not is_number:
        shown = to_text(v, True)
        shown = f" ({shown})" if len(shown) <= 30 and shown.isprintable() else ""
        tip = f" Turn text that holds a number into one first, like {{num(answer):{fmt}}}." \
            if isinstance(v, str) and re.fullmatch(r"\s*-?[0-9]+(\.[0-9]+)?\s*", v) else ""
        raise TuffError(f"The format {fmt} only works on numbers, but this is {type_name(v)}{shown}.{tip}")
    if isinstance(v, float) and not math.isfinite(v):
        return to_text(v)
    places = 2 if fmt == "money" else len(decimals or "")
    d = decimal.Decimal(v if isinstance(v, int) else repr(v))  # repr: 2.675 is the 2.675 that was written
    room = decimal.Context(prec=max(d.adjusted() + 1, 1) + places + 2)
    d = d.quantize(decimal.Decimal(1).scaleb(-places), rounding=decimal.ROUND_HALF_UP, context=room)
    sign = "-" if d < 0 else ""  # -0.001 to 2 places is 0.00
    if fmt == "money":
        return f"{sign}${d.copy_abs():,f}"
    whole, dot, rest = f"{d.copy_abs():f}".partition(".")
    return sign + whole.zfill(len(zeros)) + dot + rest


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
    if isinstance(v, dict):
        return "a dictionary"
    if isinstance(v, Line):
        return "a line"
    if isinstance(v, FileModule):
        return f"the file {v.shown}"
    if isinstance(v, Module):
        return "a library"
    if isinstance(v, Native):
        return f"a {v.kind}"
    if isinstance(v, Instance):
        return an(v.kind.name)
    if isinstance(v, Kind):
        return f"the kind {v.name}"
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
    return v not in (None, False, 0, "") and v != [] and v != {}


def make_file_members(interp):
    """file (1.4.0): text files and saved data, in the program's own folder unless the path says otherwise. When
    interp.writes is False (Tuff Engine's preview, and tuff_run for AI agents: TUFF_NO_WRITES=1) the writes are kept
    in memory for this run only: later reads see them, and nothing on disk changes."""
    rt = interp.rt
    memory = {}  # with writes off: a file's text as this run left it, or None for one it deleted

    def where(path, what):
        p = rt.text(path)
        if not p.strip():
            raise TuffError(f"{what} needs a file name, like \"notes.txt\".")
        return rt.path(p), p

    def spot(full):
        return os.path.normcase(os.path.abspath(full))

    def read(path, what="file.read"):
        full, p = where(path, what)
        if spot(full) in memory:
            if memory[spot(full)] is None:
                raise TuffError(f"Couldn't find {p} in your project folder. Check first with file.exists(\"{p}\").")
            return memory[spot(full)]
        try:
            interp.room(os.path.getsize(full))
            with open(full, "rb") as f:
                data = f.read()
        except FileNotFoundError:
            raise TuffError(f"Couldn't find {p} in your project folder. Check first with file.exists(\"{p}\").")
        except OSError as exc:
            raise TuffError(f"Couldn't read {p}: {exc.strerror or exc}.")
        return decode(data, p, what)[0].replace("\r\n", "\n")

    def decode(data, p, what):
        """A file's text and how it's saved: UTF-8, UTF-16 (PowerShell's >), or the old Windows way (Excel's CSV)."""
        if data[:2] == b"\xff\xfe":
            return data[2:].decode("utf-16-le", errors="replace"), "utf-16-le"
        if data[:2] == b"\xfe\xff":
            return data[2:].decode("utf-16-be", errors="replace"), "utf-16-be"
        if b"\x00" in data:
            raise TuffError(f"{p} isn't a text file, so {what} can't read it.")
        try:
            return data.decode("utf-8-sig"), "utf-8"
        except UnicodeDecodeError:
            return data.decode("cp1252", errors="replace"), "cp1252"

    def write_text(path, text, mode, what):
        full, p = where(path, what)
        if not interp.writes:
            had = memory.get(spot(full)) if spot(full) in memory else (read(path, what) if mode == "a" and os.path.isfile(full) else "")
            memory[spot(full)] = (had or "") + text if mode == "a" else text
            interp.room(len(memory[spot(full)]))  # Tuff Engine's preview counts what it keeps
            return None
        try:
            folder = os.path.dirname(full)
            if folder:
                os.makedirs(folder, exist_ok=True)
            with open(full, mode, encoding="utf-8", newline="") as f:
                f.write(text)
        except OSError as exc:
            raise TuffError(f"Couldn't write {p}: {exc.strerror or exc}.")
        return None

    def write(path, text):
        return write_text(path, rt.text(text), "w", "file.write")

    def add(path, text):  # adds a line to the end (makes the file if it isn't there), on a line of its own
        full, p = where(path, "file.add")
        line = rt.text(text)
        if not interp.writes:
            had = read(path, "file.add") if exists(path) else ""
            return write_text(path, ("\n" if had and not had.endswith("\n") else "") + line + "\n", "a", "file.add")
        try:  # in the file's own way of saving text and ending lines, so a UTF-16 or Excel file stays readable
            with open(full, "rb") as f:
                had, how = decode(f.read(), p, "file.add")
        except FileNotFoundError:
            had, how = "", "utf-8"
        except OSError as exc:
            raise TuffError(f"Couldn't read {p}: {exc.strerror or exc}.")
        end = "\r\n" if "\r\n" in had else "\n"
        chunk = ("" if not had or had.endswith("\n") else end) + line.replace("\n", end) + end
        try:
            folder = os.path.dirname(full)
            if folder:
                os.makedirs(folder, exist_ok=True)
            with open(full, "ab") as f:
                f.write(chunk.encode(how, errors="replace"))
        except OSError as exc:
            raise TuffError(f"Couldn't write {p}: {exc.strerror or exc}.")
        return None

    def lines(path):
        text = read(path, "file.lines")
        return text.split("\n")[:-1] if text.endswith("\n") else (text.split("\n") if text else [])

    def exists(path):
        full = where(path, "file.exists")[0]
        if spot(full) in memory:
            return memory[spot(full)] is not None
        return os.path.isfile(full)

    def delete(path):
        full, p = where(path, "file.delete")
        if not interp.writes:
            if not exists(path):
                raise TuffError(f"Couldn't find {p} to delete it.")
            memory[spot(full)] = None
            return None
        try:
            os.remove(full)
        except FileNotFoundError:
            raise TuffError(f"Couldn't find {p} to delete it.")
        except OSError as exc:
            raise TuffError(f"Couldn't delete {p}: {exc.strerror or exc}.")
        return None

    def to_json(v, seen=()):
        v = plain(v)
        if v is None or isinstance(v, (bool, int, float, str)):
            if isinstance(v, float) and not math.isfinite(v):
                raise TuffError(f"file.save can't keep {to_text(v)}: JSON only has ordinary numbers.")
            return v
        if isinstance(v, (list, dict)):
            if any(v is s for s in seen):
                raise TuffError(f"file.save can't save a {'list' if isinstance(v, list) else 'dictionary'} that holds itself.")
            seen = seen + (v,)
            if isinstance(v, list):
                return [to_json(x, seen) for x in v]
            keys = [to_text(k) for k in v]  # JSON's keys are text, so number keys come back as text
            if len(set(keys)) < len(keys):
                same = next(k for k in keys if keys.count(k) > 1)
                raise TuffError(f"file.save can't keep both {same} and \"{same}\" as keys: saved, every key is text, so they'd be one.")
            return {k: to_json(x, seen) for k, x in zip(keys, v.values())}
        if isinstance(v, Instance):  # an object (1.5.0): a dictionary that starts with its kind's name, for file.load
            if any(v is s for s in seen):
                raise TuffError(f"file.save can't save {type_name(v)} that holds itself.")
            seen = seen + (v,)
            return {SAVED_KIND: v.kind.name, **{k: to_json(x, seen) for k, x in v.fields.items()}}
        raise TuffError(f"file.save keeps text, numbers, true/false, nil, lists, dictionaries and objects made from a kind, "
                        f"not {type_name(v)}.")

    def save(path, value):  # any data, as JSON
        try:
            text = json.dumps(to_json(value), indent=2, ensure_ascii=False)
        except RecursionError:
            raise TuffError("file.save can't save data with lists or dictionaries inside each other this many times.")
        return write_text(path, text, "w", "file.save")

    def load(path, default=None):
        full, p = where(path, "file.load")
        if not exists(path) and default is not None:
            return default
        text = read(path, "file.load")

        def made(d):  # a saved object whose kind this program has comes back as that kind's object (1.5.0)
            kind = d.get(SAVED_KIND)
            return interp.saved_object(interp.kinds[kind], d) if isinstance(kind, str) and kind in interp.kinds else d
        try:
            return json.loads(text, object_hook=made if interp.kinds else None)
        except RecursionError:
            raise TuffError(f"{p} has lists or dictionaries inside each other too many times for file.load.")
        except ValueError:
            raise TuffError(f"{p} isn't saved data (JSON), so file.load can't read it. Use file.read for text.")

    b = rt.builtin
    return {"read": b("file.read", read), "write": b("file.write", write), "add": b("file.add", add),
            "lines": b("file.lines", lines), "exists": b("file.exists", exists), "delete": b("file.delete", delete),
            "save": b("file.save", save), "load": b("file.load", load)}


def method_names(v):
    """The :methods a value has, or None when that can't be told here (a library's object knows its own)."""
    if isinstance(v, Line):
        return SIMPLE_METHODS["line"]
    if isinstance(v, str):
        return SIMPLE_METHODS["text"]
    if isinstance(v, list):
        return SIMPLE_METHODS["list"]
    if isinstance(v, dict):
        return SIMPLE_METHODS["dict"]
    if isinstance(v, Native):
        return tuple(v.methods)
    if isinstance(v, Builtin):
        return ("ascii", "color", "colour", "pen") if v.name == "print" else ()
    if isinstance(v, Instance):
        return tuple(v.kind.actions)
    if isinstance(v, (bool, Module, Func, Kind)) or v is ALL:
        return ()
    return None


def sort_key(v):
    """How :sort compares: numbers with numbers, text with text (alphabetically, any case), true/false with themselves."""
    v = plain(v)
    if isinstance(v, bool):
        return (0, v)
    if isinstance(v, (int, float)):
        return (1, v)
    if isinstance(v, str):
        return (2, v.lower(), v)
    raise TypeError("can't sort")


def dict_key(k):
    """A dictionary's key: text or a number. Not a list (it can change), and not true/false, which would be the
    same key as 1 and 0."""
    k = plain(k)
    if isinstance(k, Err):
        k.stop("A dictionary's key")
    if isinstance(k, (str, int, float)) and not isinstance(k, bool):
        return k
    raise TuffError(f"A dictionary's keys can be text or numbers, not {type_name(k)}.")


def plain(v):
    return v.text if isinstance(v, Line) else v


# 1.5.0: how many inputs each Python function takes, by its code: (the inputs before any *args, whether it has
# *args, how many inputs after it must be given by name). inspect.signature is slow to ask on every call, and a
# game asks 60 times a second (game:frame(), player:move(5, 0)): a library makes new functions for each sprite,
# but they share their code, so this is worked out once for each def in a library.
INPUT_SHAPES = {}
PY_FUNCTION, PY_METHOD = types.FunctionType, types.MethodType


def fits_inputs(fn, count):
    """Can fn, a function or method written in Python, be called with this many inputs? True or False (the answer
    inspect.signature would give), or None when only inspect can tell (a function written in C, a partial...)."""
    bound = fn.__class__ is PY_METHOD  # a method of a Python object: the object is its first input
    if bound:
        fn, count = fn.__func__, count + 1
    if fn.__class__ is not PY_FUNCTION:
        return None
    for _ in range(100):
        extra = fn.__dict__
        if not extra:
            break
        if "__signature__" in extra or "_partialmethod" in extra or "__partialmethod__" in extra:
            return None
        inner = extra.get("__wrapped__")  # functools.wraps (tdraw's guard): it takes what the function inside takes
        if inner is None:
            break  # (attributes of its own don't change its inputs)
        if inner.__class__ is PY_METHOD and not bound:
            bound, fn, count = True, inner.__func__, count + 1
        elif inner.__class__ is PY_FUNCTION:
            fn = inner
        else:
            return None
    else:
        return None  # wrapped in itself
    code = fn.__code__
    shape = INPUT_SHAPES.get(code)
    if shape is None:
        shape = INPUT_SHAPES[code] = (code.co_argcount, bool(code.co_flags & inspect.CO_VARARGS), code.co_kwonlyargcount)
    most, more, named = shape
    if bound and not most and not more:
        return None  # a method with no place for its object: inspect can't say
    defaults = fn.__defaults__
    if count < (most - len(defaults) if defaults else most) or (count > most and not more):
        return False
    if named:  # inputs that must be given by name, which a call from Tuff never does, unless they have defaults
        given = fn.__kwdefaults__
        return given is not None and len(given) == named
    return True


def call_python(label, fn, args, takes_err=False, fits=None):
    """Call a built-in written in Python, turning Python problems into friendly Tuff errors. fits: whether fn takes
    this many inputs, when that's known already (a Builtin keeps it); otherwise fits_inputs works it out."""
    if fits is None:
        fits = fits_inputs(fn, len(args))
    if fits is None:
        try:
            inspect.signature(fn).bind(*args)
        except TypeError:
            raise TuffError(f"{label} got the wrong number of inputs ({len(args)}).")
        except ValueError:
            pass
    elif not fits:
        raise TuffError(f"{label} got the wrong number of inputs ({len(args)}).")
    if not takes_err:  # an err stops here with the reason it's an err, before Python can say something confusing
        for a in args:
            if isinstance(plain(a), Err):
                plain(a).stop(f"The input to {label}")
    try:
        return fn(*args)
    except (TuffError, ReturnSignal, BreakSignal, ContinueSignal, KeyboardInterrupt, SystemExit, RecursionError):
        raise
    except OverflowError:  # sqrt(2 ^ 99999), round() of a decimal that went past the biggest one...
        raise TuffError(f"That number is too big for {label} to work out.") from None
    except MemoryError:  # range(1, 10 ^ 12): Python gives no reason, so "range() failed:" would say nothing
        raise TuffError(f"The program ran out of memory inside {label}. Is it making something far too big?") from None
    except Exception as exc:
        raise TuffError(f"{label} failed: {exc}")


# ---------------------------------------------------------------- text looks (1.3.2): say:color, say:ascii, print:pen
# A said line can have colours, styles, rainbow letters, big ASCII-art letters and an animation. In TuffCode it's a
# say/rewrite with the style "rich:<base64 JSON>" (ide.js richLine draws it), in a terminal ANSI colours, and in a file
# or a pipe plain text (an animation shows only how it ends there).
TEXT_COLORS = {  # tgame's COLORS, so a name is the same colour in a game and in the Run panel
    "blue": "#3574f0", "purple": "#8b5cf6", "pink": "#ec4899", "red": "#e5484d", "orange": "#f97316",
    "yellow": "#e2a508", "green": "#22a35a", "teal": "#14b8a6", "white": "#ffffff", "black": "#000000",
    "gray": "#8a8d94", "grey": "#8a8d94",
    "brown": "#8b5a2b", "gold": "#f2c230", "lime": "#84cc16", "cyan": "#22d3ee", "navy": "#1e3a8a",
    "sky": "#87ceeb", "sand": "#e8d39a", "grass": "#5fa83f", "leaf": "#4f9d3a", "wood": "#a0703c",
    "stone": "#9a9a92", "water": "#2f7fc8", "snow": "#f4f7fb", "silver": "#c0c6cf",
    "dark green": "#2f6b2f", "dark gray": "#3b3f46", "dark grey": "#3b3f46", "light gray": "#c9ccd1",
    "light grey": "#c9ccd1", "dark blue": "#1d3f8f", "light blue": "#8ec5ff",
}
TEXT_STYLES = ("bold", "dim", "italic", "underline")
ART_FONTS = ("block", "wide", "small", "shadow", "led", "hash")
ART_EFFECTS = ("fade", "build", "explode", "assemble", "type", "glitch", "drop", "wave")
ART_FPS = 25
HEX_COLOR = re.compile(r"#?(?:[0-9a-f]{6}|[0-9a-f]{3})")
# Each character's 5 rows, '#' for ink. Lowercase letters are drawn as capitals, é as E, anything else as ?.
ART_GLYPHS = {
    "A": ".###. #...# ##### #...# #...#", "B": "####. #...# ####. #...# ####.", "C": ".#### #.... #.... #.... .####",
    "D": "####. #...# #...# #...# ####.", "E": "##### #.... ####. #.... #####", "F": "##### #.... ####. #.... #....",
    "G": ".#### #.... #.### #...# .####", "H": "#...# #...# ##### #...# #...#", "I": "### .#. .#. .#. ###",
    "J": "....# ....# ....# #...# .###.", "K": "#...# #..#. ###.. #..#. #...#", "L": "#.... #.... #.... #.... #####",
    "M": "#...# ##.## #.#.# #...# #...#", "N": "#...# ##..# #.#.# #..## #...#", "O": ".###. #...# #...# #...# .###.",
    "P": "####. #...# ####. #.... #....", "Q": ".###. #...# #.#.# #..#. .##.#", "R": "####. #...# ####. #..#. #...#",
    "S": ".#### #.... .###. ....# ####.", "T": "##### ..#.. ..#.. ..#.. ..#..", "U": "#...# #...# #...# #...# .###.",
    "V": "#...# #...# #...# .#.#. ..#..", "W": "#...# #...# #.#.# ##.## #...#", "X": "#...# .#.#. ..#.. .#.#. #...#",
    "Y": "#...# .#.#. ..#.. ..#.. ..#..", "Z": "##### ...#. ..#.. .#... #####",
    "0": ".###. #..## #.#.# ##..# .###.", "1": ".#. ##. .#. .#. ###", "2": ".###. #...# ..##. .#... #####",
    "3": "####. ....# .###. ....# ####.", "4": "#...# #...# ##### ....# ....#", "5": "##### #.... ####. ....# ####.",
    "6": ".###. #.... ####. #...# .###.", "7": "##### ....# ...#. ..#.. ..#..", "8": ".###. #...# .###. #...# .###.",
    "9": ".###. #...# .#### ....# .###.",
    " ": "... ... ... ... ...", "!": "# # # . #", "?": ".###. #...# ..##. ..... ..#..", ".": ". . . . #",
    ",": ".. .. .. .# #.", ":": ". # . # .", ";": ".. .# .. .# #.", "'": "# # . . .", '"': "#.# #.# ... ... ...",
    "-": ".... .... #### .... ....", "+": "... .#. ### .#. ...", "=": ".... #### .... #### ....",
    "_": "..... ..... ..... ..... #####", "/": "....# ...#. ..#.. .#... #....", "\\": "#.... .#... ..#.. ...#. ....#",
    "(": ".# #. #. #. .#", ")": "#. .# .# .# #.", "[": "## #. #. #. ##", "]": "## .# .# .# ##",
    "<": "..# .#. #.. .#. ..#", ">": "#.. .#. ..# .#. #..", "#": ".#.#. ##### .#.#. ##### .#.#.",
    "*": "..... #.#.# .###. #.#.# .....", "&": ".##.. #..#. .##.. #..## .##.#", "@": ".###. #.### #.#.# #.### .##..",
    "%": "##..# ##.#. ..#.. .#.## #..##", "$": ".#### #.#.. .###. ..#.# ####.", "^": ".#. #.# ... ... ...",
    "~": "..... .#... #.#.# ...#. .....", "|": "# # # # #", "`": "#. .# .. .. ..", "{": ".## .#. ##. .#. .##",
    "}": "##. .#. .## .#. ##.",
}
ART_LED_OFF = "#464a52"  # an led sign's dark lights
ART_HEAD = "#ffd23f"  # build's printer head
ART_CURSOR = "#9da0a8"  # type's cursor
ART_FIRE = ["#ffffff", "#fff3a0", "#ffd23f", "#ff9f1c", "#ff5a1f", "#d62828", "#7a1c1c"]  # explode's sparks, as they burn out


def art_glyph(ch):
    up = ch.upper()
    if up not in ART_GLYPHS:
        base = unicodedata_base(ch).upper()
        up = base if base in ART_GLYPHS else "?"
    return ART_GLYPHS[up].split()


def unicodedata_base(ch):
    import unicodedata  # only for letters with accents
    return unicodedata.normalize("NFKD", ch)[:1]


def art_font_rows(bits, font):
    """One banner's 5 rows of ink bits, drawn in a font: (rows, how many characters wide one bit is, how tall it is)."""
    width = len(bits[0])
    if font == "hash":
        return ["".join("#" if b else " " for b in row).rstrip() for row in bits], 1, 5
    if font == "led":  # a sign of lights: the dark ones show too
        return ["".join("●" if b else "·" for b in row) for row in bits], 1, 5
    if font == "wide":
        return ["".join("██" if b else "  " for b in row).rstrip() for row in bits], 2, 5
    if font == "small":  # two rows of bits in each row of text, with half blocks
        padded = bits + [[0] * width]
        return ["".join("█" if t and b else "▀" if t else "▄" if b else " " for t, b in zip(padded[r], padded[r + 1])).rstrip()
                for r in range(0, 6, 2)], 1, 3
    if font == "shadow":  # wide blocks with a shadow one row down and one character right
        ink = {(r, c * 2 + k) for r in range(5) for c in range(width) if bits[r][c] for k in (0, 1)}
        grid = [[" "] * (width * 2 + 1) for _ in range(6)]
        for r, c in ink:
            if (r + 1, c + 1) not in ink:
                grid[r + 1][c + 1] = "░"
        for r, c in ink:
            grid[r][c] = "█"
        return ["".join(row).rstrip() for row in grid], 2, 6
    return ["".join("█" if b else " " for b in row).rstrip() for row in bits], 1, 5


def art_render(text, font):
    """Big letters: their rows, and each letter's box (top, bottom, left, right) for the effects that go letter by
    letter. Each line of the text is a banner of its own, one blank row below the one before."""
    rows, boxes = [], []
    for n, part in enumerate(text.split("\n")):
        if n:
            rows.append("")
        top = len(rows)
        bits, spans = [[] for _ in range(5)], []
        for i, ch in enumerate(part):
            g = art_glyph(ch)
            start = len(bits[0]) + (1 if i else 0)
            for r in range(5):
                if i:
                    bits[r].append(0)
                bits[r].extend(1 if c == "#" else 0 for c in g[r])
            spans.append((start, len(bits[0])))
        if not part:
            bits = [[] for _ in range(5)]
        drawn, scale, height = art_font_rows(bits, font or "block") if part else ([""] * 5, 1, 5)
        rows.extend(drawn)
        boxes.extend((top, top + height, a * scale, b * scale + (scale - 1 if font == "shadow" else 0)) for a, b in spans)
    return rows, boxes


def hue_color(hue, sat=0.75, val=1.0):
    r, g, b = colorsys.hsv_to_rgb(hue % 1.0, sat, val)
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


class Look:
    """How a said line looks: its letters' colour (#rrggbb, or rainbow), the bar behind it, its styles, and for
    say:ascii the font. effect is the animation it plays when it's said."""

    def __init__(self, fg=None, bg=None, styles=(), rainbow=False, font=None, effect=None):
        self.fg, self.bg, self.styles, self.rainbow = fg, bg, set(styles), rainbow
        self.font, self.effect = font, effect

    def __bool__(self):
        return bool(self.fg or self.bg or self.styles or self.rainbow or self.effect)

    def with_pen(self, pen):
        """What print:pen set, for what this line doesn't say itself."""
        if pen is None:
            return self
        own_letters = self.fg or self.rainbow
        return Look(self.fg if own_letters else pen.fg, self.bg or pen.bg, self.styles | pen.styles,
                    self.rainbow if own_letters else pen.rainbow, self.font, self.effect)

    def letters(self, rows):
        """The colour of each letter that isn't the line's own: rainbow across the text, and an led sign's dark lights.
        (row, column) -> colour."""
        colors = {}
        if self.font == "led":
            colors = {(r, c): ART_LED_OFF for r, row in enumerate(rows) for c, ch in enumerate(row) if ch == "·"}
        if self.rainbow:
            width = max((len(r) for r in rows), default=1)
            colors.update({(r, c): hue_color(c / max(width, 8) * 0.8 + r * 0.02) for r, row in enumerate(rows)
                           for c, ch in enumerate(row) if ch not in " ·"})
        return colors


def read_look(owner, words, art=False, pen=False):
    """The words after the text (in any order): colours (a name or #rrggbb; the first is the letters', a second the
    bar behind them), rainbow, styles, and for say:ascii a font. Animations go on say:color and say:ascii."""
    look, colors = Look(), []
    for w in words:
        w = plain(w)
        if not isinstance(w, str):
            raise TuffError(f'{owner} takes words like "red", "bold" or "fade" after the text, not {type_name(w)}.')
        word = " ".join(w.lower().split())
        if word in TEXT_COLORS:
            colors.append(TEXT_COLORS[word])
        elif HEX_COLOR.fullmatch(word):
            h = word.lstrip("#")
            colors.append("#" + (h if len(h) == 6 else "".join(c * 2 for c in h)))
        elif word == "rainbow":
            look.rainbow = True
        elif word in TEXT_STYLES:
            look.styles.add(word)
        elif word in ART_FONTS and art:
            if look.font:
                raise TuffError(f'{owner} takes one font, but got "{look.font}" and "{word}".')
            look.font = word
        elif word in ART_EFFECTS and not pen:
            if look.effect:
                raise TuffError(f'{owner} plays one animation, but got "{look.effect}" and "{word}".')
            look.effect = word
        else:
            raise TuffError(look_help(owner, w, word, art, pen))
    most = 1 if look.rainbow else 2
    if len(colors) > most:
        raise TuffError(f"{owner} takes {'one colour with rainbow (for the bar behind the letters)' if look.rainbow else 'two colours at most: the letters, then the bar behind them'}.")
    if look.rainbow:
        look.bg = colors[0] if colors else None
    else:
        look.fg, look.bg = (colors + [None, None])[:2]
    return look


def look_help(owner, given, word, art, pen):
    if word in ART_FONTS:
        return f'"{word}" is a font for big letters: use it with say:ascii("Hi", "{word}").'
    if word in ART_EFFECTS:
        return f'{owner} sets colours and styles. Animations like "{word}" go on say:ascii or say:color.'
    known = list(TEXT_COLORS) + ["rainbow", *TEXT_STYLES] + (list(ART_FONTS) if art else []) + ([] if pen else list(ART_EFFECTS))
    hint = difflib.get_close_matches(word, known, n=1, cutoff=0.6)
    kinds = ["colours (red, gold, sky... or \"#ff8800\")", "rainbow", "styles (" + ", ".join(TEXT_STYLES) + ")"]
    if art:
        kinds.append("fonts (" + ", ".join(ART_FONTS) + ")")
    if not pen:
        kinds.append("animations (" + ", ".join(ART_EFFECTS) + ")")
    return f'{owner} doesn\'t know "{given}".' + (f' Did you mean "{hint[0]}"?' if hint else "") + " It takes " + ", ".join(kinds[:-1]) + " and " + kinds[-1] + "."


def look_text(text, look, art):
    """What a line shows, as rows, and each letter's box (top, bottom, left, right) for the animations."""
    if art:
        rows, boxes = art_render(text, look.font)
    else:
        rows = text.split("\n")
        boxes = [(r, r + 1, c, c + 1) for r, row in enumerate(rows) for c, ch in enumerate(row) if ch != " "]
    return rows, boxes


class ArtCanvas:
    """A frame being drawn: a grid of characters and their colours (None: the line's own colour)."""

    def __init__(self, h, w):
        self.h, self.w = h, w
        self.ch = [[" "] * w for _ in range(h)]
        self.col = [[None] * w for _ in range(h)]

    def put(self, r, c, ch, color=None):
        r, c = int(round(r)), int(round(c))
        if 0 <= r < self.h and 0 <= c < self.w:
            self.ch[r][c], self.col[r][c] = ch, color

    def frame(self):
        return frame_of(["".join(row) for row in self.ch], self.col)


def frame_of(rows, colors):
    """(text, runs): rows with their ends trimmed, and a [row, start, length, colour] run for each stretch of letters in
    a colour that isn't the line's own. colors is a grid like the rows' (or a {(row, column): colour} map)."""
    get = (lambda r, c: colors.get((r, c))) if isinstance(colors, dict) else (lambda r, c: colors[r][c] if c < len(colors[r]) else None)
    runs, out = [], []
    for r, row in enumerate(rows):
        row = row.rstrip()
        out.append(row)
        start = None
        for c in range(len(row) + 1):
            cur = get(r, c) if c < len(row) and row[c] not in " " else None
            if start is not None and cur != get(r, start):
                runs.append([r, start, c - start, get(r, start)])
                start = None
            if cur is not None and start is None:
                start = c
    return "\n".join(out), runs


def art_ink(rows):
    return [(r, c, ch) for r, row in enumerate(rows) for c, ch in enumerate(row) if ch not in " ·"]


def art_ramp(ch):
    """What a letter shows while it fades in, by what it becomes."""
    return "·•" if ch == "●" else ".:+" if ch == "#" else "░" if ch in "░▒" else "░▒▓"


def art_frames(rows, boxes, look):
    """The animation's frames, each (text, runs). The program waits while they play (1-2 seconds)."""
    effect, base_map = look.effect, look.letters(rows)
    base = lambda r, c: base_map.get((r, c))
    rnd = random.Random(7)
    h, w = len(rows), max((len(r) for r in rows), default=0)
    cells = art_ink(rows)
    dim = [(r, c) for r, row in enumerate(rows) for c, ch in enumerate(row) if ch == "·"]  # an led sign's dark lights
    frames = []

    def steps(seconds):
        return range(int(ART_FPS * seconds) + 1)

    if effect == "fade":
        start = {(r, c): rnd.uniform(0, 0.6) for r, c, _ in cells}
        for f in steps(1.0):
            t, cv = f / ART_FPS, ArtCanvas(h, w)
            for r, c in dim:
                cv.put(r, c, "·", ART_LED_OFF)
            for r, c, ch in cells:
                p = (t - start[r, c]) / 0.4
                if p > 0:
                    ramp = art_ramp(ch)
                    cv.put(r, c, ch if p >= 1 else ramp[min(len(ramp) - 1, int(p * len(ramp)))], base(r, c))
            frames.append(cv.frame())
    elif effect == "build":  # a printer head lays each row, from the bottom up
        order = [r for r in reversed(range(h)) if rows[r].strip()]
        per = 0.9 / max(1, len(order)) + 0.06
        for f in steps(per * len(order)):
            t, cv = f / ART_FPS, ArtCanvas(h, w)
            for i, r in enumerate(order):
                done = (t - i * per) / per
                if done <= 0:
                    continue
                head = int(done * w) if done < 1 else w
                for c, ch in enumerate(rows[r]):
                    if ch != " " and c < head:
                        cv.put(r, c, ch, base(r, c))
                if done < 1:
                    cv.put(r, min(head, w - 1), "▌", ART_HEAD)
            frames.append(cv.frame())
    elif effect in ("explode", "assemble"):
        pad = 3  # rows below, for the sparks to fall into
        cy = sum(r for r, _, _ in cells) / max(1, len(cells))
        cx = sum(c for _, c, _ in cells) / max(1, len(cells))
        sparks = []
        for r, c, ch in cells:
            dx, dy = c - cx, (r - cy) * 2.2
            d = math.hypot(dx, dy) or 1
            speed = rnd.uniform(14, 34)
            sparks.append((r, c, ch, dx / d * speed + rnd.uniform(-6, 6), dy / d * speed / 2.2 + rnd.uniform(-5, 2), rnd.uniform(0.55, 1.05)))

        def spark(cv, s, t, color_override=None):
            r, c, ch, vx, vy, life = s
            age = t / life
            looks = [ch, "▓", "*", "+", "·"]
            cv.put(r + vy * t + 4.5 * t * t, c + vx * t, looks[min(4, int(age * 5))],
                   color_override or ART_FIRE[min(len(ART_FIRE) - 1, int(age * len(ART_FIRE)))])

        if effect == "explode":  # it holds, flashes, then bursts into sparks that fly, fall and burn out
            for f in steps(1.6):
                t, cv = f / ART_FPS - 0.45, ArtCanvas(h + pad, w + 10)
                if t <= 0:
                    for r, c, ch in cells:
                        cv.put(r, c, ch, "#ffffff" if t > -0.12 else base(r, c))
                else:
                    for s in sparks:
                        if t < s[5]:
                            spark(cv, s, t)
                frames.append(cv.frame())
        else:  # an explosion played backwards: sparks fly in and become the letters
            for f in steps(1.15):
                t, cv = 0.9 - f / ART_FPS, ArtCanvas(h + pad, w + 10)
                for s in sparks:
                    if t <= 0:
                        cv.put(s[0], s[1], s[2], base(s[0], s[1]))
                    else:
                        tt = t * s[5] / 0.9
                        spark(cv, s, tt * 0.8, None if tt >= 0.06 else (base(s[0], s[1]) or "#ffffff"))
                frames.append(cv.frame())
    elif effect == "type":  # letter by letter, with a blinking cursor
        order = sorted(boxes)
        per = min(0.09, 1.4 / max(1, len(order)))
        for f in steps(per * len(order) + 0.5):
            t, cv = f / ART_FPS, ArtCanvas(h, w + 2)
            shown = min(len(order), int(t / per))
            for top, bottom, left, right in order[:shown]:
                for r in range(top, bottom):
                    for c in range(left, min(right, len(rows[r]))):
                        if rows[r][c] != " ":
                            cv.put(r, c, rows[r][c], base(r, c))
            if shown < len(order) or int(t * 4) % 2 == 0:
                top, bottom, _, right = order[shown - 1] if shown else (order[0][0], order[0][1], 0, -1) if order else (0, 1, 0, -1)
                for r in range(top, bottom):
                    cv.put(r, right + 1, "▌", ART_CURSOR)
            frames.append(cv.frame())
    elif effect == "glitch":  # scrambled and shaking, then it snaps clean
        junk = "#$%&@*+=?/\\<>!01"
        for f in steps(1.3):
            t, cv = f / ART_FPS, ArtCanvas(h, w + 2)
            noise = max(0.0, 1 - t / 1.05)
            shift = {r: (rnd.choice([-1, 1, 2]) if rnd.random() < noise * 0.5 else 0) for r in range(h)}
            for r, c, ch in cells:
                if rnd.random() < noise * 0.25:
                    continue
                if rnd.random() < noise * 0.7:
                    cv.put(r, c + shift[r], rnd.choice(junk), rnd.choice(["#22d3ee", "#ff3ea5", base(r, c) or "#ffffff"]))
                else:
                    cv.put(r, c + shift[r], ch, base(r, c))
            frames.append(cv.frame())
    elif effect == "drop":  # each letter slides down into place, one after another, and bounces
        order = sorted(boxes, key=lambda b: (b[0], b[2]))
        per, fall = min(0.07, 0.9 / max(1, len(order))), 0.4
        for f in steps(per * len(order) + fall + 0.3):
            t, cv = f / ART_FPS, ArtCanvas(h, w)
            for i, (top, bottom, left, right) in enumerate(order):
                lt = t - i * per
                if lt <= 0:
                    continue
                height = bottom - top
                if lt < fall:
                    dy = -height * (1 - (lt / fall) ** 2)
                else:
                    bt = min(1.0, (lt - fall) / 0.25)
                    dy = -math.sin(bt * math.pi) * 0.6 * (1 - bt)
                for r in range(top, bottom):
                    for c in range(left, min(right, len(rows[r]))):
                        if rows[r][c] not in " ":
                            cv.put(r + dy, c, rows[r][c], base(r, c))
            frames.append(cv.frame())
    elif effect == "wave":  # a rainbow sweeps across, then the letters settle into their own colours
        for f in steps(1.6):
            t, cv = f / ART_FPS, ArtCanvas(h, w)
            for r, c in dim:
                cv.put(r, c, "·", ART_LED_OFF)
            for r, c, ch in cells:
                cv.put(r, c, ch, hue_color((c * 4.0 + r * 6.0 - t * 260.0) / 360))
            frames.append(cv.frame())
    return frames


# A Mac's Terminal app shows only 256 colours (24-bit codes come out wrong there): it gets the nearest of those.
ANSI_256 = os.environ.get("TERM_PROGRAM") == "Apple_Terminal" and os.environ.get("COLORTERM", "").lower() not in ("truecolor", "24bit")


def ansi_color(hex_color, ground=38):
    r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
    if not ANSI_256:
        return f"\x1b[{ground};2;{r};{g};{b}m"
    steps = [0, 95, 135, 175, 215, 255]  # xterm's 6 x 6 x 6 colour cube, or its 24 greys, whichever is closer
    near = lambda v: min(range(6), key=lambda i: abs(steps[i] - v))
    cube = (near(r), near(g), near(b))
    grey = min(23, max(0, round(((r + g + b) / 3 - 8) / 10)))
    dist = lambda c: (c[0] - r) ** 2 + (c[1] - g) ** 2 + (c[2] - b) ** 2
    use_grey = dist((8 + grey * 10,) * 3) < dist(tuple(steps[i] for i in cube))
    n = 232 + grey if use_grey else 16 + 36 * cube[0] + 6 * cube[1] + cube[2]
    return f"\x1b[{ground};5;{n}m"


def ansi_rows(text, runs, look):
    """A styled line for a real terminal: ANSI colours, and a bar that reaches the edge (erase to the end of the line
    fills it with the bar's colour)."""
    sgr = "".join({"bold": "\x1b[1m", "dim": "\x1b[2m", "italic": "\x1b[3m", "underline": "\x1b[4m"}[s] for s in sorted(look.styles))
    own = ansi_color(look.fg) if look.fg else "\x1b[39m"
    head = sgr + own + (ansi_color(look.bg, 48) if look.bg else "")
    by_row = {}
    for r, start, n, color in runs:
        by_row.setdefault(r, []).append((start, n, color))
    out = []
    for r, row in enumerate(text.split("\n")):
        s, pos = head, 0
        for start, n, color in sorted(by_row.get(r, [])):
            s += row[pos:start] + ansi_color(color) + row[start:start + n] + own
            pos = start + n
        out.append(s + row[pos:] + ("\x1b[K" if look.bg else "") + "\x1b[0m")
    return out


class Console:
    animate = True  # SceneConsole: no animations in Tuff Engine's preview

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

    def say_look(self, text, look, art=False):
        """say:color, say:ascii, and a line said with print:pen on: it plays its animation, then shows how it ends."""
        line = Line(self.next_id, text, self.rows)
        self.next_id += 1
        line.look, line.art, line.height = look, art, 0
        self.animate_line(line, text, look.effect)
        return line

    def animate_line(self, line, text, effect):
        """Plays effect (or nothing) on a line's text, then shows how it ends. A new line (height 0) is said by its
        first frame; one already there changes in place."""
        rows, boxes = look_text(text, line.look, line.art)
        playing = Look(line.look.fg, line.look.bg, line.look.styles, line.look.rainbow, line.look.font, effect)
        frames = art_frames(rows, boxes, playing) if effect and self.animate and (IDE or sys.stdout.isatty()) else []
        start = time.perf_counter()
        for i, (shown, runs) in enumerate(frames):
            self.show(line, shown, runs, anim=True)
            pause = start + (i + 1) / ART_FPS - time.perf_counter()
            if pause > 0:
                time.sleep(pause)
        shown, runs = ("", []) if effect == "explode" else frame_of(rows, line.look.letters(rows))
        self.show(line, shown, runs)

    def play(self, line, effect):
        """line:play("explode"): the animation on the line where it is (a plain line gets a look of its own)."""
        if line.look is None:
            line.look = Look()
        self.animate_line(line, line.text, effect)

    def rewrite_look(self, line, text, change):
        """:rewrite("GO!", "glitch", "lime"): new text, colours, styles or font from the words (the rest stays as it
        was), and the animation plays on the new text."""
        base = line.look or Look()
        own_letters = change.fg or change.rainbow
        line.look = Look(change.fg if own_letters else base.fg, change.bg or base.bg, base.styles | change.styles,
                         change.rainbow if own_letters else base.rainbow, change.font or base.font)
        line.text = text
        self.animate_line(line, text, change.effect)

    def show(self, line, shown, runs, anim=False):
        """Puts a styled line on the screen, or changes it if it's there: the first call says it."""
        look, new = line.look, not line.height
        height = shown.count("\n") + 1
        if IDE:
            # TuffCode keeps a rainbow's colours moving, on one clock: through an animation's frames too, so
            # line:play("explode") on a rainbow line carries on at the colours it had instead of starting again
            data = {"fg": look.fg, "bg": look.bg, "runs": runs or None, "art": 1 if line.art else None, "anim": 1 if anim else None,
                    "rainbow": 1 if look.rainbow else None}
            data = {k: v for k, v in data.items() if v}
            data.update({s: 1 for s in look.styles})
            style = "rich:" + b64(json.dumps(data, separators=(",", ":")))
            self.write(f"\x1b]tuff;{'say' if new else 'rewrite'};{line.id};{b64(shown)};{style}\x07" + ("\n" if new else ""))
        elif sys.stdout.isatty():
            rows = ansi_rows(shown, runs, look)
            if new:
                self.write("\n".join(rows) + "\n")
            else:
                height = self.redraw(line, rows)
        elif new:
            self.write(shown + "\n")
        else:
            return
        if new:
            line.row = self.rows
            self.rows += height
        elif IDE:
            self.rows += height - line.height
        line.height = height

    def redraw(self, line, rows):
        """A terminal: draws a line's rows again where it is. The last thing said can grow or shrink; a line with
        others below it keeps its height. Gives its height now."""
        old = line.height
        up = self.rows - line.row
        last = line.row + old == self.rows
        if not last:
            rows = (rows + [""] * old)[:old]
        out = f"\x1b[{up}A" if up > 0 else ""
        out += "".join("\r\x1b[2K" + row + "\n" for row in rows)
        if last:
            if len(rows) < old:
                out += "\x1b[J"
            self.rows += len(rows) - old
        elif up - old > 0:
            out += f"\x1b[{up - old}B"
        self.write(out + "\r")
        return len(rows)

    def rewrite(self, line, text):
        line.text = text
        if getattr(line, "look", None) is not None:  # it keeps its look (and big letters stay big)
            rows, _ = look_text(text, line.look, line.art)
            self.show(line, *frame_of(rows, line.look.letters(rows)))
            return
        if IDE:
            self.write(f"\x1b]tuff;rewrite;{line.id};{b64(text)}\x07")
            return
        up = self.rows - line.row
        if up > 0:
            self.write(f"\x1b[{up}A\r\x1b[2K{text}\x1b[{up}B\r")

    def ask(self, prompt, look):
        """input:color's question (and input's with print:pen on): in its look, on the line the answer is typed on."""
        rows, _ = look_text(prompt, look, False)
        runs = frame_of(rows, look.letters(rows))[1]
        if IDE:
            data = {"fg": look.fg, "bg": look.bg, "runs": runs or None, "rainbow": 1 if look.rainbow else None}
            data = {k: v for k, v in data.items() if v}
            data.update({s: 1 for s in look.styles})
            self.write(f"\x1b]tuff;prompt;{b64(prompt)};rich:{b64(json.dumps(data, separators=(',', ':')))}\x07")
        elif sys.stdout.isatty():  # (no bar to the window's edge: the answer is typed after it)
            self.write("\n".join(row.replace("\x1b[K", "") for row in ansi_rows(prompt, runs, look)))
        else:
            self.write(prompt)

    def clear(self, count=None):
        if IDE:
            self.write(f"\x1b]tuff;clear;{'all' if count is None else count}\x07")
        elif count is None:
            self.write("\x1b[2J\x1b[H")
        else:
            self.write("\x1b[1A\x1b[2K" * min(count, self.rows) + "\r")
        self.rows = 0 if count is None else max(0, self.rows - count)

    def input(self, prompt, look=None):
        if look and prompt:
            self.ask(prompt, look)
        else:
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
    def __init__(self, parent=None, own_names=False):  # (a function call's is made without this: see make_call)
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
            me = self.find("my")
            me = me.vars["my"] if me is not None else None
            msg = own_field_help(name, *((me.kind.name, me.kind.fields) if isinstance(me, Instance) else (None, ())))
            if msg:
                raise TuffError(msg)
            hint = difflib.get_close_matches(name, known, n=1, cutoff=0.6)
            extra = f" Did you mean '{hint[0]}'?" if hint else " Give it a value first, like: " + name + " = 5"
            raise TuffError(f"I don't know what '{name}' is.{extra}")
        return env.vars[name]

    def set(self, name, value):
        env = self.find(name)
        if env is None or env.own_names:
            env = self
        env.vars[name] = value


def file_of(env):
    """The file whose names env is in (1.5.0): an imported file's full path, or "" for the program itself. The
    outermost Env of an imported file has its path (see Interpreter.load)."""
    while env.parent is not None:
        env = env.parent
    return getattr(env, "file", "")


# ---- your own files as libraries (1.5.0): import money loads money.tuf, from the importing file's folder or the libs
# folder there. A library's name (tgame, tap...) always means the library.
MODULE_FOLDER = "libs"
# Read and shown by report(): each imported file's full path -> (its text, its name as shown, like libs/money.tuf).
OWN_FILES = {}


def module_file(folder, name):
    """name.tuf next to a file (in its folder) or in the libs folder there, spelled the way the import spells it (so
    a program works the same on every system), or None."""
    want = name + ".tuf"
    for where in (folder, os.path.join(folder, MODULE_FOLDER)):
        try:
            if want in os.listdir(where) and os.path.isfile(os.path.join(where, want)):
                return os.path.join(where, want)
        except OSError:
            pass
    return None


def module_names(folder):
    """The names of the .tuf files next to a file and in its libs folder, for "did you mean"."""
    found = []
    for where in (folder, os.path.join(folder, MODULE_FOLDER)):
        try:
            found += [n[:-4] for n in os.listdir(where) if n.endswith(".tuf") and n[:-4].isidentifier()]
        except OSError:
            pass
    return found


def import_problem(name, folder, who, others=()):
    """Why import name can't load a file: it's a built-in's name, or there's no name.tuf there. who: the importing
    file's name as shown (like shop.tuf). others: names close matches shouldn't offer (the importing file's own)."""
    path = module_file(folder, name) if folder else None
    if name in BUILTIN_NAMES or name in OWN_NAME_BUILTINS or name in ("err", "pi", "all"):
        what = "value" if name in ("err", "pi", "all") else "function"
        if path:
            return (f"{name} is one of Tuff's built-in {what}s, so a file called {name}.tuf can't be imported by that name. "
                    f"Give the file another name, like my_{name}.tuf.")
        return f"{name} is built into Tuff, so there's nothing to import: use it straight away{', like ' + name + '()' if what == 'function' else ''}."
    if path:
        return None
    nearby = [n for n in module_names(folder) if n not in others] if folder else []
    hint = difflib.get_close_matches(name, nearby + list(LIBRARIES), n=1, cutoff=0.6)
    msg = f"There's no {name}.tuf next to {who} (or in a {MODULE_FOLDER} folder there)"
    if name in PY_NAMES:
        return f"{msg}, and Tuff doesn't need {name}: {PY_NAMES[name]}"
    if hint and hint[0] in LIBRARIES:
        return f"{msg}. Did you mean Tuff's library {hint[0]}?"
    if hint:
        return f"{msg}. Did you mean {hint[0]} ({hint[0]}.tuf)?"
    return f"{msg}, and {name} isn't one of Tuff's libraries ({', '.join(LIBRARIES)})."


def circle_problem(chain):
    """chain: the files importing each other, as shown, from the first back to it again (shop.tuf, money.tuf, shop.tuf)."""
    if len(chain) == 2:
        return f"{chain[0]} imports itself. A file can use its own names straight away, without importing itself."
    loop = " → ".join(chain)
    if len(chain) == 3:
        return (f"{chain[0]} and {chain[1]} import each other ({loop}), so neither can finish loading. Put what they both "
                "need in a third file, and import that from both.")
    return (f"These files import each other in a circle ({loop}), so none of them can finish loading. Put what they "
            "need in another file that doesn't import them.")


def module_help(mod, name):
    """money.as_mony: what money.tuf has instead."""
    own = sorted(mod.members)  # (A to Z, as the checker lists them)
    hint = difflib.get_close_matches(name, own, n=1, cutoff=0.6)
    if hint:
        return f"{mod.shown} doesn't have '{name}'. Did you mean '{hint[0]}'?"
    if own:
        return f"{mod.shown} doesn't have '{name}'. It has: {', '.join(own)}."
    return f"{mod.shown} doesn't have '{name}': it doesn't make any functions or values at its top level."


class Runtime:
    """The small toolbox libraries (like tgui) use to talk to the interpreter."""

    def __init__(self, interp):
        self.interp = interp
        self.finish_hooks = []
        self.wait_hooks = []

    def text(self, v):
        return to_text(plain(v))

    def plain(self, v):
        return plain(v)

    def what(self, v):
        """'text', 'a number', 'a dictionary'... for messages."""
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

    def on_wait(self, fn):
        """fn runs over and over while the program waits (wait(1)), so a library's window keeps drawing."""
        self.wait_hooks.append(fn)

    def call(self, fn, *args):
        """Run a Tuff function from a library callback. Errors are reported, not raised."""
        try:
            return True, self.interp.invoke(fn, list(args), loose=True)
        except TuffError as err:
            if err.line is None and getattr(fn, "line", None):  # e.g. a click function asking for inputs
                err.line = fn.line
                err.file = file_of(fn.env)  # (where it's written: one of the program's own files, 1.5.0)
            report(err, self.interp.src)
        except RecursionError:
            report(TuffError(f"{getattr(fn, 'name', 'This function')}() called itself too many times."), self.interp.src)
        except (BreakSignal, ContinueSignal) as sig:
            report(TuffError("'break' and 'continue' can only be used inside a loop.", sig.line, sig.col), self.interp.src)
        return False, None


# ---------------------------------------------------------------- for the compiled runtime (1.5.0)

def jumps_out(s):
    """The returns, breaks and continues that can come out of statement s (a loop keeps its own break and continue,
    and a function's own are its own)."""
    k = s.kind
    if k in (J_RETURN, J_BREAK, J_CONTINUE):
        return {k}
    if k == "if":
        out = set()
        for _, body in s.branches:
            out |= block_jumps(body)
        return out | block_jumps(s.else_body or [])
    if k == "try":
        return block_jumps(s.body) | block_jumps(s.handler)
    if k in ("while", "for"):
        return block_jumps(s.body) - {J_BREAK, J_CONTINUE}
    return set()


def block_jumps(body):
    out = set()
    for s in body:
        out |= jumps_out(s)
    return out


# The quick sums: for each operator, the functions that make a sum's function (a + b, and a + 5, 5 + a, a == "yes"
# with a number or text written in the program) and a += statement's. Numbers (and two texts, for + and the
# comparisons) are worked out right there, the way Interpreter.binop would; anything else goes to binop itself
# (slow), which gives the same answers and the same messages. A / or % by 0 goes there too, and so does a sum
# whose answer is too big for a decimal (10 ^ 400 / 3: Python's OverflowError). They're written once below and
# made for each operator, so each one has its operator in it.
QUICK_SUM = '''
def @NAME@(@ARGS@, slow, line, col):
    def binop(env):
@GET@        if @QUICK@:
@DO@@TEXTS@        try:
            return slow("@OP@", a, b)
        except TuffError as err:
            if err.line is None:
                err.line, err.col = line, col
            raise
    return binop
'''
QUICK_STORE = '''
def @NAME@(s, get, @ARGS@, slow, hooks, step):
    name, line, col = s.target.name, s.line, s.col

    def assign(env):
        if hooks:
            step(s, env)
@GET@        names = env.vars
        if name in names:
            a = names[name]
        else:
            a = get(env)
            names = None
        ta = a.__class__
        if @QUICK@:
            try:
                a = a @OP@ b
            except OverflowError:  # too big for a decimal: binop says so
                try:
                    a = slow("@OP@", a, b)
                except TuffError as err:
                    if err.line is None:
                        err.line, err.col = line, col
                    raise
@TEXTS@        else:
            try:
                a = slow("@OP@", a, b)
            except TuffError as err:
                if err.line is None:
                    err.line, err.col = line, col
                raise
        if names is None:
            env.set(name, a)
        else:
            names[name] = a
        return a
    return assign
'''
QUICK_TEXTS = ("+", "<", ">", "<=", ">=", "==", "!=")  # text with text works the same as in Python
NUMBER_A, NUMBER_B = "(ta is int or ta is float)", "(tb is int or tb is float)"


def quick_makers(op):
    """One operator's makers: both, number_right, number_left, text_right and text_left (where text is quick), and
    for +, -, * and /: store, store_number and store_text (+= only)."""
    nonzero = " and b" if op in ("/", "%") else ""
    texts = op in QUICK_TEXTS
    get_a, get_b = "        a = left(env)\n        ta = a.__class__\n", "        b = right(env)\n        tb = b.__class__\n"
    kinds = [("both", "left, right", get_a + get_b, f"{NUMBER_A} and {NUMBER_B}{nonzero}",
              "        if ta is str and tb is str:\n            return a @OP@ b\n" if texts else ""),
             ("number_right", "left, b", get_a, NUMBER_A, ""), ("number_left", "a, right", get_b, NUMBER_B + nonzero, "")]
    if texts:
        kinds += [("text_right", "left, b", get_a, "ta is str", ""), ("text_left", "a, right", get_b, "tb is str", "")]
    do = "            return a @OP@ b\n"
    if op in ("+", "-", "*", "/", "%"):  # (a comparison is never too big)
        do = ("            try:\n                return a @OP@ b\n            except OverflowError:  # too big for a decimal: "
              "binop says so, below\n                pass\n")
    src = "".join(QUICK_SUM.replace("@NAME@", n).replace("@ARGS@", a).replace("@GET@", g).replace("@QUICK@", q)
                  .replace("@DO@", do).replace("@TEXTS@", t) for n, a, g, q, t in kinds)
    if op in ("+", "-", "*", "/"):  # x += 1 and the rest: the value is worked out first, then x, as the tree walker does
        kinds = [("store", "value", "        b = value(env)\n        tb = b.__class__\n", f"{NUMBER_A} and {NUMBER_B}{nonzero}",
                  "        elif ta is str and tb is str:\n            a = a @OP@ b\n" if op == "+" else ""),
                 ("store_number", "b", "", NUMBER_A, "")]
        if op == "+":
            kinds.append(("store_text", "b", "", "ta is str", ""))
        src += "".join(QUICK_STORE.replace("@NAME@", n).replace("@ARGS@", a).replace("@GET@", g).replace("@QUICK@", q)
                       .replace("@TEXTS@", t) for n, a, g, q, t in kinds)
    made = {"TuffError": TuffError}
    exec(compile(src.replace("@OP@", op), f"<tuff quick {op}>", "exec"), made)
    return made


QUICK = {op: quick_makers(op) for op in ("+", "-", "*", "/", "%", "<", ">", "<=", ">=", "==", "!=")}


class Interpreter:
    writes = True  # file.write and the rest (Tuff Engine's preview writes nothing)

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
            "text": self.b_text,
            # The names people bring from Python: str is text, int is a whole number.
            "str": self.b_text,
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
            # 1.4.0: date and time, and more maths (angles in degrees, like tdraw's and tgame's turns)
            "now": lambda: time.strftime("%H:%M:%S"),
            "today": lambda: time.strftime("%Y-%m-%d"),
            "time": lambda: round(time.perf_counter() - self.started, 3),
            "date": self.b_date,
            "sin": lambda deg: self.trig("sin", deg, math.sin),
            "cos": lambda deg: self.trig("cos", deg, math.cos),
            "tan": lambda deg: self.trig("tan", deg, math.tan),
            "log": self.b_log,
        }
        self.started = time.perf_counter()
        self.held = []  # the starts of the names[order:pop] being worked out (see eval "slice")
        self.depth = 0  # Tuff functions running inside each other (see MAX_DEPTH)
        # 1.5.0: each statement and expression is compiled once into a Python function (see compile_stmt), several
        # times quicker than walking the tree. TUFF_SLOW=1 runs the old tree walker instead, for one release.
        self.fast = os.environ.get("TUFF_SLOW") != "1"
        self.codes = {}  # id(node): (node, its compiled function)
        # A subclass that runs each statement itself (Tuff Engine's preview keeps the line it's on) gets every
        # statement through its run(), and one with its own binop gets every sum through it (see own).
        self.routed = type(self).run is not Interpreter.run
        # The debugger's hook point (1.5.0): functions run as hook(statement, env) just before each statement, in
        # both runtimes. atgui's app:closed time limit is one. While it's empty it costs one check per statement.
        self.step_hooks = []
        self.kinds = {}  # 1.5.0: the program's kinds by name (file.load makes their objects again)
        self.made_kinds = {}  # id(kind node): (node, its Kind), made once (see s_kind)
        if os.environ.get("TUFF_NO_WRITES") == "1":  # tuff_run for AI agents: file writes stay in memory
            self.writes = False
        takes_err = {"number", "num", "int", "text", "str", "print"}  # they hand an err back, or show it as "err"
        for name, fn in builtins.items():
            (self.own_names if name in OWN_NAME_BUILTINS else self.globals).vars[name] = Builtin(name, fn, name in takes_err)
        self.own_names.vars["file"] = Module("file", make_file_members(self))
        self.print_builtin = self.globals.vars["print"]  # say:ascii(...) is print's, even in a program with its own print
        self.pen = None  # print:pen's look, for every line said after it
        self.globals.vars["all"] = ALL
        self.globals.vars["pi"] = math.pi
        self.own_names.vars["err"] = ERR
        # 1.5.0: the program's own files it imports (import money). Each gets a top level of its own, starting with
        # these built-ins, and is loaded once: files holds them by their full path (see load).
        self.path = None  # the program's own file (run_file sets it), so a file that imports it back is a circle
        self.files = {}
        self.loading = []  # the files whose top-level code is running right now, the first imported first
        self.base_globals, self.base_own = dict(self.globals.vars), dict(self.own_names.vars)

    def b_text(self, v, decimals=None):
        """text(value), and text(3.14159, 2) is "3.14" (a number with that many decimals, 1.4.0)."""
        v = plain(v)
        if decimals is None:
            return to_text(v)
        d = self.num_arg("text", decimals)
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise TuffError(f"text(value, decimals) needs a number to show with decimals, not {type_name(v)}.")
        if d > 100:
            raise TuffError(f"text(value, {to_text(d)}): the most decimals it shows is 100.")
        places = max(0, int(d))
        if isinstance(v, int):  # every digit, even of 10 ^ 25 or 2 ^ 99999 (as a decimal it would be rounded, or too big)
            return str(v) + ("." + "0" * places if places else "")
        shown = f"{v:.{places}f}"
        return shown[1:] if shown.startswith("-") and not shown.strip("-0.") else shown  # -0.001 to 2 places is 0.00

    def b_date(self):
        """date(): today and now as a dictionary: year, month, day, weekday, hour, minute, second."""
        t = time.localtime()
        return {"year": t.tm_year, "month": t.tm_mon, "day": t.tm_mday, "weekday": time.strftime("%A", t),
                "hour": t.tm_hour, "minute": t.tm_min, "second": t.tm_sec}

    def trig(self, name, deg, fn):
        deg = self.num_arg(name, deg)
        if isinstance(deg, float) and not math.isfinite(deg):  # a decimal that went past the biggest one (inf)
            raise TuffError(f"{name}({to_text(deg)}) has no answer.")
        if name == "tan" and deg % 180 == 90:
            raise TuffError(f"tan({to_text(deg)}) has no answer: at 90 degrees (and 270) the line is straight up.")
        result = fn(math.radians(deg))
        return round(result, 12) + 0.0  # sin(180) is 0, not 1.2e-16

    def b_log(self, v, base=None):
        v = self.num_arg("log", v)
        if v <= 0:
            raise TuffError("log() needs a number above 0.")
        if base is None:
            return math.log(v)
        base = self.num_arg("log", base)
        if base <= 0 or base == 1:
            raise TuffError("log(number, base): the base must be above 0 and not 1, like log(100, 10).")
        if base == 10:  # exact for powers: log(1000, 10) is 3, not 2.9999999999999996
            return math.log10(v)
        if base == 2:
            return math.log2(v)
        return round(math.log(v, base), 12) + 0.0

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

    def lib_tdraw(self):
        try:
            import tuff_tdraw
        except ImportError:
            raise TuffError("tdraw needs Python's tkinter, which isn't installed. Reinstall Python and tick 'tcl/tk and IDLE'.")
        return tuff_tdraw.make_library(self.rt, TEXT_COLORS)

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

        def looked(name, inputs, texts, most):
            """anims' usual inputs, then look words after them, like say:color's (1.4.1):
            anims.loading("Pulling info...", "green"). A word where a number goes is a look word too; texts are the
            places that take text. With print:pen on, the pen's look is the starting point."""
            usual, words = [], []
            for i, a in enumerate(inputs):
                if words or (isinstance(plain(a), str) and i not in texts):
                    words.append(a)
                else:
                    usual.append(a)
            if len(usual) > most:
                raise TuffError(f"anims.{name} takes {most} inputs before its look words, not {len(usual)}.")
            look = read_look(f"anims.{name}", words, pen=True) if words else None  # (an anim is an animation already)
            if look is not None or self.pen:
                look = (look or Look()).with_pen(self.pen)
            return usual, look

        def start(text, look):
            return con.say_look(text, look) if look else con.say(text)

        def loading(*inputs):
            usual, look = looked("loading", inputs, {0}, 2)
            return loading_(*usual, look=look)

        def loading_(text="Loading", seconds=2, look=None):
            text = to_text(text)
            line = start(f"/ {text}", look)
            frames = max(1, round(float(seconds) / 0.1))
            for i in range(frames):
                con.rewrite(line, f"{spin[i % 4]} {text}{'.' * (i // 3 % 4)}")
                time.sleep(0.1)
            con.rewrite(line, f"✓ {text}... done")
            return line

        def bar(*inputs):
            usual, look = looked("bar", inputs, {0}, 3)
            return bar_(*usual, look=look)

        def bar_(text="Working", seconds=2, width=20, look=None):
            text = to_text(text)
            width = max(5, int(width))
            line = start("", look)
            steps = max(1, round(float(seconds) / 0.05))
            for i in range(steps + 1):
                filled = round(width * i / steps)
                con.rewrite(line, f"{text} [{'█' * filled}{'░' * (width - filled)}] {round(100 * i / steps):>3}%")
                if i < steps:
                    time.sleep(0.05)
            return line

        def type_(*inputs):
            usual, look = looked("type", inputs, {0}, 2)
            return type__(*usual, look=look)

        def type__(text, speed=0.04, look=None):
            text = to_text(text)
            line = start("", look)
            for i in range(1, len(text) + 1):
                con.rewrite(line, text[:i])
                time.sleep(max(0, float(speed)))
            return line

        def countdown(*inputs):
            usual, look = looked("countdown", inputs, {1}, 2)
            return countdown_(*usual, look=look)

        def countdown_(begin=3, then="Go!", look=None):
            n = int(plain(begin))
            line = start(str(n), look)
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
        return self.say_text(" ".join(to_text(a) for a in args))

    def say_text(self, text):
        """say and print: with print:pen on, the line has the pen's look."""
        return self.console.say_look(text, Look().with_pen(self.pen)) if self.pen else self.console.say(text)

    def print_method(self, said, name, args):
        """print:ascii, print:color and print:pen (and say:ascii, say:color, say:pen: the same)."""
        who = "say" if said else "print"
        owner = f"{who}:{name}"
        if name in ("ascii", "color", "colour"):
            if not args:
                raise TuffError(f'{owner} needs the text first, like: {owner}("Hello"{", " + chr(34) + "red" + chr(34) if name != "ascii" else ""})')
            art = name == "ascii"
            look = read_look(owner, args[1:], art=art).with_pen(self.pen)
            return self.console.say_look(to_text(args[0]), look, art=art)
        if name == "pen":
            look = read_look(owner, args, pen=True)
            self.pen = look if look else None
            return None
        raise TuffError(method_help(who.capitalize(), name, ["ascii", "color", "pen"]))

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
            n = float(s) if "." in s else int(s)
        except ValueError:
            return Err(f"{name}() couldn't turn '{to_text(v)}' into a number")
        if n.__class__ is float and not math.isfinite(n):  # "1.0e999": past the biggest decimal there is
            return Err(f"{name}() couldn't turn '{to_text(v)}' into a number: it's too big for a decimal")
        return n

    def b_int(self, v):
        # A whole number, dropping any decimals toward zero: int("42") is 42, int(3.7) and int("3.7") are 3.
        n = self.b_number(v, "int")
        return n if isinstance(n, Err) else int(n)

    def b_len(self, v):
        v = plain(v)
        if not isinstance(v, (str, list, dict)):
            raise TuffError(f"len() needs text, a list or a dictionary, not {type_name(v)}.")
        return len(v)

    def b_random(self, *ends):
        """random(1, 6) and random(6): a whole number. random() is a decimal from 0 to 1, and random(0.5, 2.5) (a
        decimal in it) a decimal in that range (1.4.0)."""
        if not ends:
            return random.random()
        if len(ends) > 2:
            raise TuffError("random() needs a range, like random(1, 6), or just the top, like random(6).")
        nums = [self.num_arg("random", v) for v in ends]
        # A decimal is one with digits after the point: random(1, 12 / 2) still gives whole numbers, as in 1.3.6.
        decimal = any(isinstance(v, float) and not v.is_integer() for v in nums)
        low, high = ((0 if decimal else 1), nums[0]) if len(nums) == 1 else nums  # random(0.5): from 0 to 0.5
        if low > high:
            shown = to_text(high) if len(nums) == 1 else f"{to_text(low)}, {to_text(high)}"
            raise TuffError(f"random({shown}): the first number must be the smaller one." if len(nums) > 1 else
                            f"random({shown}) gives a number from {to_text(low)} up to {shown}, so {shown} has to be at least {to_text(low)}.")
        if decimal:
            return random.uniform(low, high)
        return random.randint(int(low), int(high))

    def b_wait(self, seconds):
        sys.stdout.flush()
        end = time.perf_counter() + max(0, float(seconds))
        while True:
            for hook in self.rt.wait_hooks:  # a tdraw window keeps drawing while the program waits
                hook()
            left = end - time.perf_counter()
            if left <= 0:
                return
            # short naps: Ctrl+C reaches a program on its own thread (run_deep) between them
            time.sleep(min(0.02 if self.rt.wait_hooks else 0.1, left))

    def b_range(self, a, b=None, step=1):
        if b is None:
            a, b = 1, a
        a, b, step = int(a), int(b), int(step)
        if step == 0:
            raise TuffError("range() can't count in steps of 0.")
        return list(range(a, b + (1 if step > 0 else -1), step))

    # statements
    def run_block(self, body, env):
        if self.fast:
            return self.unjump(self.compile_block(body)(env))
        result = None
        for stmt in body:
            result = self.run(stmt, env)
        return result

    def run(self, s, env):
        if self.fast:
            return self.unjump(self.compile_stmt(s)(env))
        if self.step_hooks:
            self.step(s, env)
        try:
            return getattr(self, "s_" + s.kind)(s, env)
        except TuffError as e:
            if e.line is None:
                e.line, e.col = s.line, s.col
            raise

    def step(self, s, env):
        """The step hooks, just before statement s runs (see step_hooks)."""
        try:
            for hook in tuple(self.step_hooks):
                hook(s, env)
        except TuffError as err:
            if err.line is None:
                err.line, err.col = s.line, s.col
            raise

    def s_expr(self, s, env):
        return self.eval(s.expr, env)

    def s_assign(self, s, env):
        value = self.eval(s.value, env)
        t = s.target
        if t.kind == "var":
            if s.op != "=":
                value = self.binop(s.op[0], self.eval(t, env), value)
            env.set(t.name, value)
            return value
        if t.kind == "attr":  # rex.hunger = 3, my.hunger -= 1 (1.5.0)
            return self.set_field(s, self.eval(t.obj, env), value)
        obj = plain(self.eval(t.obj, env))  # the list or dictionary and the key are worked out once: votes[input()] += 1
        key = self.part_key(t, env) if t.kind == "slice" else self.eval(t.index, env)
        return self.store(s, obj, key, value)

    def part_key(self, t, env):
        """board[moves:pop] = "X": only 1.3.6's method reading of a part can be stored into."""
        which, key, _ = self.part(t, env)
        if which != "key":
            raise TuffError("A part like [1:3] can't be changed with =. Make the new text or list with + instead.")
        return key

    def store(self, s, obj, key, value):
        """obj[key] = value, +=, -=...: a list's item, or a dictionary's key."""
        if s.op != "=":
            value = self.binop(s.op[0], self.item(obj, key, s.target.obj), value)
        if isinstance(obj, dict):  # ages["sam"] = 15 sets (or adds) a key
            obj[dict_key(key)] = value
            return value
        if not isinstance(obj, list):
            tip = f" {object_brackets(obj.kind.name, obj.kind.fields, where_text(s.target.obj), key, ' = ...')}" \
                if isinstance(obj, Instance) else ""
            raise TuffError(f"You can only set items in a list, not in {type_name(obj)}.{tip}")
        obj[self.list_index(obj, key)] = value
        return value

    def s_try(self, s, env):
        """try: ... catch problem: ... (1.4.0): a Tuff error inside try runs catch instead of stopping the program.
        problem (optional) is the error's message."""
        try:
            return self.run_block(s.body, env)
        except TuffError as err:
            if s.name:
                env.set(s.name, err.msg)
            return self.run_block(s.handler, env)

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
        for item in self.for_items(s, plain(self.eval(s.items, env))):
            env.set(s.name, item)
            try:
                self.run_block(s.body, env)
            except BreakSignal:
                break
            except ContinueSignal:
                continue
        return None

    def for_items(self, s, items):
        """What a for loop goes through: a copy of the list or text (so the loop can change it), or a dictionary's keys."""
        if isinstance(items, bool) or isinstance(items, (int, float)):
            raise TuffError(f"Can't loop over a number. Try: for {s.name} in range({to_text(items)}):")
        if isinstance(items, dict):  # a dictionary: its keys
            items = list(items)
        if not isinstance(items, (list, str)):
            raise TuffError(f"Can't loop over {type_name(items)}.")
        return list(items)

    def s_func(self, s, env):
        env.vars[s.name] = Func(s.name, s.params, s.body, env, s.line)
        return None

    # ---- kinds (1.5.0): kind Pet:, rex = Pet("Rex"), rex.hunger, rex:feed()
    def s_kind(self, s, env):
        """kind Pet: makes the kind. run_file runs it before the rest of the program, like a func, and again where it's
        written; it's made only once, so every Pet comes from the same kind."""
        got = self.made_kinds.get(id(s))
        if got is None or got[0] is not s:
            actions = {f.action: Func(f.name, f.params, f.body, env, f.line, self.compile_block(f.body) if self.fast else None)
                       for f in s.actions}
            kind = Kind(s.name, tuple(f.target.name for f in s.fields), tuple(f.value for f in s.fields), actions, env, s.line)
            got = self.made_kinds[id(s)] = (s, kind)
        env.vars[s.name] = self.kinds[s.name] = got[1]
        return None

    def make_object(self, kind, args, loose=False):
        """Pet("Rex"): a new Pet. The inputs fill its fields in order; any left over start with their kind's value,
        worked out now, for this object. loose (a library calling back): extra inputs are dropped."""
        fields = kind.fields
        if len(args) > len(fields):
            if not loose:
                raise TuffError(kind_inputs_help(kind.name, fields, len(args)))
            args = args[:len(fields)]
        made = dict(zip(fields, args))
        if len(args) < len(fields):
            self.starting_values(kind, made, fields[len(args):], kind.defaults[len(args):])
        return Instance(kind, made)

    def starting_values(self, kind, made, names, defaults):
        """Work out these fields' starting values, for a new object. A field that starts with a new object of its own
        kind (kind Node: next = Node()) would make objects without end: that stops like a function calling itself."""
        stop = f"{kind.name}() was made inside itself too many times. Does a field of {kind.name} start with a new {kind.name}()? Start it with nil."
        if self.depth >= MAX_DEPTH:
            raise TuffError(stop)
        self.depth += 1
        try:
            for name, default in zip(names, defaults):
                made[name] = self.eval(default, kind.env)
        except RecursionError:
            raise TuffError(stop)
        finally:
            self.depth -= 1

    def saved_object(self, kind, saved):
        """file.load's object, from the dictionary file.save made of it: a field the save doesn't have (the kind got
        a new one since) starts with its kind's value, and a key that isn't one of the kind's fields is left out."""
        made = {name: saved[name] for name in kind.fields if name in saved}
        missing = [(name, default) for name, default in zip(kind.fields, kind.defaults) if name not in saved]
        if missing:
            self.starting_values(kind, made, *zip(*missing))
        return Instance(kind, {name: made[name] for name in kind.fields})

    def call_action(self, e, obj, args):
        """rex:feed(): one of the object's actions, run with my as the object."""
        kind = obj.kind
        fn = kind.actions.get(e.name)
        if fn is None:
            raise TuffError(action_help(kind.name, kind.fields, kind.actions, e.name, where_text(e.obj)))
        if len(args) != len(fn.params):
            raise TuffError(action_inputs_help(where_text(e.obj) or kind.name, e.name, len(fn.params), len(args), getattr(e, "bare", False)))
        return self.invoke(fn, args, me=obj)

    def set_field(self, s, obj, value):
        """rex.hunger = 3 and my.hunger -= 1 (value is already worked out): one of the object's fields. An object
        only has its kind's fields, so a typo is an error instead of a new field."""
        t = s.target
        if obj.__class__ is not Instance:
            if isinstance(obj, Kind):
                raise TuffError(kind_not_object(obj.name, f".{t.name} = ..."))
            tip = f" A dictionary's values are set with [ ], like {where_text(t.obj) or 'd'}[\"{t.name}\"] = ..." if isinstance(obj, dict) else ""
            raise TuffError(f"Only objects made from a kind have fields to set with '.', and this is {type_name(obj)}.{tip}")
        fields = obj.fields
        if t.name not in fields:
            raise TuffError(field_help(obj.kind.name, fields, obj.kind.actions, t.name, where_text(t.obj)))
        if s.op != "=":
            value = self.binop(s.op[0], fields[t.name], value)
        fields[t.name] = value
        return value

    def s_import(self, s, env):
        if s.name == "file":  # built in, so there's nothing to load
            return None
        if s.name in LIBRARIES:  # a library's name is always the library, even with a file of that name nearby
            env.set(s.name, Module(s.name, getattr(self, "lib_" + s.name)()))
            return None
        env.set(s.name, self.load(s.name, env))  # 1.5.0: one of the program's own files
        return None

    def shown(self, path):
        """A file's name as messages show it: from the program's folder, like libs/money.tuf."""
        try:
            rel = os.path.relpath(path, self.base_dir)
        except ValueError:  # on another drive
            return os.path.basename(path)
        return os.path.basename(path) if rel.startswith("..") else rel.replace(os.sep, "/")

    def program_name(self):
        """The program's own file as shown (its imports are found in the program's folder), or "the program"."""
        if self.path and os.path.normcase(os.path.dirname(os.path.abspath(self.path))) == os.path.normcase(os.path.abspath(self.base_dir)):
            return os.path.basename(self.path)
        return "the program"

    def load(self, name, env):
        """import money (1.5.0): money.tuf, from the folder of the file that imports it (or the libs folder there), as a
        FileModule. Its top-level code runs the first time it's imported, and every import after that gets the same
        one. An error in it is reported in it (err.file), with its own line."""
        here = file_of(env)
        folder = os.path.dirname(here) if here else self.base_dir
        who = OWN_FILES[here][1] if here in OWN_FILES else self.program_name()
        problem = import_problem(name, folder, who, (os.path.basename(here or self.path or "")[:-4],))
        if problem:
            raise TuffError(problem)
        path = os.path.abspath(module_file(folder, name))
        key = os.path.normcase(path)
        mod = self.files.get(key)
        running = [self.program_name()] + [m.shown for m in self.loading]
        if running[-1] != who:  # (an import in a function of a file that has loaded)
            running.append(who)
        if self.path and key == os.path.normcase(os.path.abspath(self.path)):  # the program itself, which is running
            raise TuffError(circle_problem(running + [running[0]]))
        if mod is not None:
            if not mod.ready:  # still running its top-level code: an import further in came back to it
                raise TuffError(circle_problem(running[1 + self.loading.index(mod):] + [mod.shown]))
            return mod
        shown = self.shown(path)
        try:
            src = source_text(path)
        except (OSError, UnicodeDecodeError) as exc:
            raise TuffError(unreadable(path, exc, shown))
        OWN_FILES[path] = (src, shown)
        try:
            program = Parser(tokenize(src)).program()
        except TuffError as err:
            err.file = path
            raise
        own = Env(own_names=True)
        own.vars.update(self.base_own)
        own.file = path  # (see file_of)
        top = Env(own)
        top.vars.update(self.base_globals)
        mod = self.files[key] = FileModule(name, path, shown, top, self.base_globals)
        self.loading.append(mod)
        try:
            for stmt in program:  # its functions can be used anywhere in it, even above where they're written
                if stmt.kind == "func":
                    self.run(stmt, top)
            self.run_block(program, top)
        except TuffError as err:
            del self.files[key]
            if err.file is None and err.line is not None:
                err.file = path
            raise
        except (ReturnSignal, BreakSignal, ContinueSignal) as sig:
            del self.files[key]
            word = {ReturnSignal: "return", BreakSignal: "break", ContinueSignal: "continue"}[type(sig)]
            err = TuffError(f"'{word}' can only be used inside a {'function' if word == 'return' else 'loop'}.", sig.line, sig.col)
            err.file = path
            raise err
        except BaseException:
            del self.files[key]
            raise
        finally:
            self.loading.pop()
        mod.ready = True
        return mod

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
        if self.fast:
            return self.compile_expr(e)(env)
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
            return self.say_text(to_text(self.eval(e.value, env)))
        if k == "sayfn":
            return self.print_builtin
        if k == "input":
            prompt = "" if e.prompt is None else to_text(self.eval(e.prompt, env))
            looks = getattr(e, "looks", None)  # input:color("Name? ", "green")
            return self.ask(prompt, None if looks is None else [self.eval(a, env) for a in looks])
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
            return self.negative(self.eval(e.value, env))
        if k == "list":
            return [self.eval(x, env) for x in e.items]
        if k == "dict":
            return {dict_key(self.eval(key, env)): self.eval(value, env) for key, value in zip(e.keys, e.values)}
        if k == "index":
            obj = plain(self.eval(e.obj, env))
            return self.item(obj, self.eval(e.index, env), e.obj)
        if k == "held":  # the start of names[order:pop], already worked out (see "slice")
            return self.held[-1]
        if k == "slice":  # s[1:3]: positions 1 to 3, both included (like range); s[:3] from the start, s[2:] to the end
            obj = plain(self.eval(e.obj, env))
            return self.cut(e, obj, *self.part(e, env))
        if k == "fstr":  # a text template: f"{name} has {score + 1} points" (1.5.0)
            pieces = [p if isinstance(p, str) else self.shape(p, self.eval(p.value, env)) for p in e.parts]
            self.room(sum(sys.getsizeof(p) for p in pieces))
            return "".join(pieces)
        if k == "call":
            return self.call(e, env)
        if k == "method":
            try:
                return self.method(e, env)
            except (OverflowError, MemoryError):  # a number or text too big for the computer, inside a method
                raise TuffError(TOO_BIG)
        if k == "attr":
            return self.member(e, self.eval(e.obj, env))
        raise TuffError(f"Internal error: unknown expression '{k}'.")

    # what the expressions above do once their parts are worked out (the compiled runtime uses them too)
    def ask(self, prompt, looks):
        """input's question (with input:color's look words, already worked out), then the answer."""
        look = None
        if looks is not None:
            look = read_look("input:color", looks, pen=True)  # (no animations)
        if look is not None or self.pen:  # with print:pen on, the question has the pen's look too
            look = (look or Look()).with_pen(self.pen)
        return self.console.input(prompt, look)

    def negative(self, v):
        v = plain(v)
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            raise TuffError(f"Can't make {type_name(v)} negative.")
        return -v

    def cut(self, e, obj, which, first, last):
        """x[a:b] once x and part(e) are worked out."""
        if which == "key":  # names[order:pop]: 1.3.6's method call gave the position or key
            return self.item(obj, first, e.obj)
        if not isinstance(obj, (list, str)):
            raise TuffError(f"Only text and lists have parts like [1:3], not {type_name(obj)}.")
        size = len(obj)
        a, b = max(0, self.spot(e, first, 0, size)), min(size - 1, self.spot(e, last, size - 1, size))
        return obj[a:b + 1] if a <= b else obj[0:0]

    def member(self, e, obj):
        """library.name, and an object's field: rex.hunger (1.5.0)"""
        if obj.__class__ is Instance:
            if e.name in obj.fields:
                return obj.fields[e.name]
            raise TuffError(field_help(obj.kind.name, obj.kind.fields, obj.kind.actions, e.name, where_text(e.obj)))
        if isinstance(obj, Kind):
            raise TuffError(kind_not_object(obj.name, f".{e.name}"))
        if isinstance(obj, Builtin) and e.obj.kind == "var" and e.obj.name in PY_NAMES:  # time.sleep(1)
            raise TuffError(f"Tuff has no {e.obj.name}.{e.name}. {PY_NAMES[e.obj.name]}")
        if not isinstance(obj, Module):
            kind = "list" if isinstance(obj, list) else "text" if isinstance(obj, str) else "dict" if isinstance(obj, dict) else None
            raise TuffError(dot_help(type_name(obj), e.obj, e.name, kind))
        if obj.__class__ is FileModule:  # money.rate: its top level's value as it is now (1.5.0)
            v = obj.env.vars.get(e.name, obj)
            if v is obj or obj.base.get(e.name, obj) is v:
                raise TuffError(module_help(obj, e.name))
            return v
        if e.name not in obj.members:
            raise TuffError(f"{obj.name} doesn't have '{e.name}'. It has: {', '.join(obj.members)}.")
        return obj.members[e.name]

    def room(self, size):
        """Something about size bytes big is about to be made. Only Tuff Engine's preview keeps count."""

    def shape(self, part, v):
        """One { } of a text template, shown: as say shows the value, or in the { }'s format (0.00, money...)."""
        if part.fmt is None:
            return to_text(v)
        try:
            return format_value(v, part.fmt)
        except TuffError as err:
            if err.line is None:
                err.line, err.col = part.line, part.col  # at the format
            raise

    def repeat(self, text, times):
        if not text or times <= 0:  # (Python can't repeat even "" more times than a list can hold)
            return ""
        size = len(text) * times
        if size > 500_000_000:
            raise TuffError(f"That text would be {size} characters long, too long to make." if size < 10 ** 15 else
                            "That text would be far too long to make.")  # (not a number with thousands of digits)
        return text * times

    LEFT_OUT = object()  # a part's end that isn't written: s[:3], s[2:]

    def part(self, e, env):
        """Works out x[a:b]'s ends: ("part", start, end), or ("key", k, None) when it's 1.3.6's method call
        (names[order:pop], see Parser.index): a, worked out once, isn't a number, and it has that method."""
        if e.alt is None:
            first = self.LEFT_OUT if e.start is None else plain(self.eval(e.start, env))
            return "part", first, self.LEFT_OUT if e.end is None else plain(self.eval(e.end, env))
        a = self.eval(e.recv, env)
        v = plain(a)
        self.held.append(a)
        try:
            if isinstance(v, Err):
                v.stop(f"{node_text(e.recv) or 'The value before the :'}")
            if v is None:  # names[order:pop] with order nil: neither a position nor something with :pop
                raise TuffError(f"{node_text(e.recv) or 'The value before the :'} is nil, so it's not a position, and it has no :{e.mname}.")
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                first = plain(self.eval(e.start, env))
                return "part", first, plain(self.eval(e.end, env))
            names = method_names(a)
            if names is not None and e.mname not in names:  # word[first:last] with first some text
                who = node_text(e.recv)
                tip = f" {who} is text: turn it into a number first, like int({who})." if who and isinstance(v, str) else ""
                raise TuffError(f"The positions in [start:end] must be whole numbers, not {type_name(v)}.{tip}")
            return "key", self.eval(e.alt, env), None
        finally:
            self.held.pop()

    def spot(self, e, v, default, size):
        """A part's position, counted from the end when it's below 0."""
        if v is self.LEFT_OUT:
            return default
        if isinstance(v, Err):
            v.stop("A part's position")
        if isinstance(v, bool) or not isinstance(v, int):
            tip = " (For a method call inside [ ], put brackets around it, like (stack:pop).)" \
                if e.alt is None and isinstance(v, (list, str, dict, Native)) else ""
            raise TuffError(f"The positions in [start:end] must be whole numbers, not {type_name(v)}.{tip}")
        return v + size if v < 0 else v

    def item(self, obj, key, obj_node):
        """obj[key]: a dictionary's value, or the item at a position in a list or text."""
        if isinstance(obj, dict):
            key = dict_key(key)
            if key not in obj:
                owner = node_text(obj_node) or "the dictionary"
                shown = to_text(key, True)
                as_text = to_text(key) if isinstance(key, (int, float)) else None
                if as_text in obj:  # {"1": ...}: from file.load, which gives keys back as text (JSON's keys are)
                    named = node_text(obj_node)
                    use = f"{named}[\"{as_text}\"] or {named}[text({shown})]" if named else f"[\"{as_text}\"] or [text({shown})]"
                    raise TuffError(f"{owner} doesn't have the number {shown}, but it has \"{as_text}\" (text). Keys that "
                                    f"come back from file.load or a web page's JSON are always text: use {use}.")
                tip = f" Check first with {owner}:has({shown}), or use {owner}:get({shown}, default)." if node_text(obj_node) else ""
                raise TuffError(f"{owner} doesn't have {shown}.{tip}")
            return obj[key]
        if not isinstance(obj, (list, str)):
            tip = f" {object_brackets(obj.kind.name, obj.kind.fields, where_text(obj_node), plain(key))}." \
                if isinstance(obj, Instance) else ""
            raise TuffError(f"Can't use [ ] on {type_name(obj)}.{tip}")
        return obj[self.list_index(obj, key)]

    def list_index(self, obj, index):
        index = plain(index)
        if not isinstance(index, int) or isinstance(index, bool):
            raise TuffError(f"List positions must be whole numbers, not {type_name(index)}.")
        if not -len(obj) <= index < len(obj):
            where = f"Position {index} is" if abs(index) < 10 ** 15 else "That position is far"  # (not thousands of digits)
            raise TuffError(f"{where} outside this {'list' if isinstance(obj, list) else 'text'} (it has {len(obj)} items, starting at 0).")
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
        try:  # a whole number too big to be a decimal (10 ^ 400 / 3, 2 ^ 99999 * 1.5) is an OverflowError in Python
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
                    return self.repeat(a, b)
                if isinstance(b, str) and isinstance(a, int) and not isinstance(a, bool):
                    return self.repeat(b, a)
            elif num(a) and num(b):
                if op == "-":
                    return a - b
                if op == "^":
                    try:
                        result = a ** b
                    except ZeroDivisionError:  # 0 ^ -1 is 1 / 0
                        raise TuffError(f"0 ^ {to_text(b)} has no answer: it's the same as dividing by zero.")
                    if isinstance(result, complex):
                        raise TuffError("A negative number can't be raised to a fraction.")
                    return result
                if b == 0:
                    raise TuffError("You can't divide by zero.")
                if op == "/":
                    return a / b
                if op == "%":
                    return a % b
        except OverflowError:
            raise TuffError(TOO_BIG_NUMBER) from None
        verb = {"+": "add", "-": "subtract", "*": "multiply", "/": "divide", "%": "use % on", "^": "use ^ on"}[op]
        raise TuffError(f"Can't {verb} {type_name(a)} and {type_name(b)}.")

    def call(self, e, env):
        fn = self.eval(e.fn, env)
        if e.fn.kind == "var" and e.fn.name in BUILTIN_NAMES and not isinstance(fn, (Builtin, Func)):
            self.not_builtin(e, fn)
        args = [self.eval(a, env) for a in e.args]
        return self.invoke(fn, args)

    def not_builtin(self, e, fn):
        raise TuffError(f"'{e.fn.name}' was given a value ({to_text(fn, True)}), so it isn't the built-in {e.fn.name}() any more. Use another name for your variable.")

    def invoke(self, fn, args, loose=False, me=None):
        """Call fn with args. me: the object, for one of its kind's actions (my in it)."""
        if isinstance(fn, Builtin):
            if self.fast:  # how many inputs it takes is worked out once for each count (see Builtin.fits)
                fits = fn.fits.get(len(args))
                if fits is None:
                    fits = fn.fits[len(args)] = accepts(fn.fn, len(args))
                return call_python(fn.name + "()", fn.fn, args, fn.takes_err, fits)
            return call_python(fn.name + "()", fn.fn, args, fn.takes_err)
        if isinstance(fn, Func):
            if loose and len(args) > len(fn.params):
                args = args[: len(fn.params)]
            if len(args) != len(fn.params):
                want = len(fn.params)
                raise TuffError(f"{fn.name}() needs {want} input{'s' if want != 1 else ''}, but got {len(args)}.")
            local = Env(fn.env)
            local.vars.update(zip(fn.params, args))
            if me is not None:
                local.vars["my"] = me
            if self.depth >= MAX_DEPTH:  # (deep enough for real work; a runaway stops here before it eats the memory)
                raise TuffError(f"{fn.name}() called itself too many times.")
            self.depth += 1
            try:
                if fn.code is None:
                    return self.run_block(fn.body, local)
                out = fn.code(local)
                if out.__class__ is Jump:
                    if out.kind is J_RETURN:
                        value, out.value = out.value, None
                        return value
                    self.unjump(out)  # a break or continue outside any loop in it: on to a loop around the call, as before
                return out
            except ReturnSignal as r:
                return r.value
            except TuffError as err:  # (1.5.0) its line is in the file the function is written in
                if err.file is None and err.line is not None:  # (one without a line gets the call's, in the caller's file)
                    err.file = file_of(fn.env)
                raise
            except RecursionError:
                raise TuffError(f"{fn.name}() called itself too many times.")
            except MemoryError:
                raise TuffError(f"The program ran out of memory inside {fn.name}(). Is something growing without end?")
            finally:
                self.depth -= 1
        if isinstance(fn, Kind):  # Pet("Rex"): a new object (1.5.0)
            return self.make_object(fn, args, loose)
        raise TuffError(f"{to_text(fn, True)} isn't a function, so it can't be called with ( ).")

    def method(self, e, env):
        obj = self.eval(e.obj, env)
        args = [self.eval(a.value if a.kind == "say" else a, env) for a in e.args]
        return self.method_call(e, obj, args)

    def method_call(self, e, obj, args):
        """obj:name(args), once obj and args are worked out."""
        if obj.__class__ is Instance:  # rex:feed(), one of its kind's actions (1.5.0)
            return self.call_action(e, obj, args)
        name = e.name
        if isinstance(obj, Kind):
            raise TuffError(kind_not_object(obj.name, f":{name}()"))
        if isinstance(obj, Native):  # a library's object, like game:frame() (first: a game calls these all the time)
            fn = obj.methods.get(name)
            if fn is None:
                options = [m for m in obj.methods if m != "page" or obj.kind == "window"]
                raise TuffError(method_help(a_kind(obj.kind).capitalize(), name, options))
            return call_python(f"{obj.kind}:{name}", fn, args)
        if isinstance(obj, Builtin) and obj.name == "print":
            return self.print_method(e.obj.kind == "sayfn", name, args)

        def need(count):
            if len(args) != count:
                raise TuffError(f":{name} needs {count} input{'s' if count != 1 else ''}.")

        def no_inputs():
            if args:
                raise TuffError(f":{name} doesn't take an input. Write :{name}() or just :{name}.")

        if isinstance(obj, Line):
            if name in ("rewrite", "append"):
                if not args:
                    raise TuffError(f":{name} needs the new text, like :{name}(\"Done!\")")
                text = to_text(args[0]) if name == "rewrite" else obj.text + to_text(args[0])
                if len(args) > 1:  # :rewrite("GO!", "glitch", "lime"): a new look, and an animation it plays here
                    self.console.rewrite_look(obj, text, read_look(f"line:{name}", args[1:], art=obj.art))
                else:
                    self.console.rewrite(obj, text)
                return obj
            if name == "play":  # line:play("explode"): an animation on the line where it is
                need(1)
                word = " ".join(to_text(args[0]).lower().split())
                if word not in ART_EFFECTS:
                    hint = difflib.get_close_matches(word, ART_EFFECTS, n=1, cutoff=0.6)
                    raise TuffError(f'line:play doesn\'t know "{to_text(args[0])}".' + (f' Did you mean "{hint[0]}"?' if hint else "") + f" Animations: {', '.join(ART_EFFECTS)}.")
                self.console.play(obj, word)
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
            # 1.4.0's text tools
            if name == "split":  # "a,b":split(",") is ["a", "b"]; with nothing, it splits at spaces
                if len(args) > 1:
                    raise TuffError(':split takes what to split at, like :split(","), or nothing (spaces).')
                sep = to_text(args[0]) if args else None
                if sep == "":
                    return list(obj)
                return obj.split(sep)
            if name == "replace":
                need(2)
                old, new = to_text(args[0]), to_text(args[1])
                if old and len(new) > len(old):
                    self.room(len(obj) + obj.count(old) * (len(new) - len(old)))
                elif not old:
                    self.room(len(obj) + (len(obj) + 1) * len(new))
                return obj.replace(old, new)
            if name in ("starts", "ends"):
                need(1)
                return (obj.startswith if name == "starts" else obj.endswith)(to_text(args[0]))
            if name == "find":  # where it first is, or -1
                need(1)
                return obj.find(to_text(args[0]))
            if name == "count":
                need(1)
                return obj.count(to_text(args[0]))
            if name in ("pad_left", "pad_right"):  # "7":pad_left(3, "0") is "007"
                if not 1 <= len(args) <= 2:
                    raise TuffError(f':{name} takes a width and, if you like, what to fill with: :{name}(5) or :{name}(3, "0").')
                width = self.num_arg(name, args[0])
                fill = to_text(args[1]) if len(args) > 1 else " "
                if len(fill) != 1:
                    raise TuffError(f":{name} fills with one character, like \"0\" or \" \".")
                if not math.isfinite(width):
                    raise TuffError(f":{name} needs a width that's a number, not {to_text(width)}.")
                if width > 10_000_000:
                    raise TuffError(f":{name}({to_text(width)}) is too wide: the most is 10000000.")
                self.room(int(width) * (4 if ord(fill) > 255 else 1))
                return obj.rjust(int(width), fill) if name == "pad_left" else obj.ljust(int(width), fill)
            what, kind = "Text", "text"
        elif isinstance(obj, dict):  # 1.4.0's dictionaries
            if name == "has":
                need(1)
                return dict_key(args[0]) in obj
            if name == "get":  # ages:get("bob", 0): the value, or the default (nil) when it isn't there
                if not 1 <= len(args) <= 2:
                    raise TuffError(':get takes a key and, if you like, what to give when it isn\'t there: :get("sam", 0).')
                return obj.get(dict_key(args[0]), args[1] if len(args) > 1 else None)
            if name == "set":
                need(2)
                obj[dict_key(args[0])] = args[1]
                return obj
            if name == "remove":
                need(1)
                key = dict_key(args[0])
                if key not in obj:
                    raise TuffError(f"{to_text(key, True)} isn't in this dictionary.")
                del obj[key]
                return obj
            if name in ("keys", "values"):
                no_inputs()
                return list(obj) if name == "keys" else list(obj.values())
            if name == "size":  # like len(d), and like tap's data objects had before 1.4.1
                no_inputs()
                return len(obj)
            what, kind = "A dictionary", "dict"
        elif isinstance(obj, list):
            if name == "add":
                need(1)
                obj.append(args[0])
                return obj
            if name == "sort":  # in place; :sort(by) sorts by what by(item) gives back
                if len(args) > 1:
                    raise TuffError(":sort takes nothing, or a function to sort by, like :sort(by_score).")
                if args and not isinstance(args[0], (Func, Builtin)):
                    raise TuffError(":sort takes a function name to sort by, like :sort(by_score) (without brackets).")
                keyed = [(self.invoke(args[0], [x]) if args else x, x) for x in obj]
                try:
                    keyed.sort(key=lambda kx: sort_key(kx[0]))
                except TypeError:
                    bad = next((plain(k) for k, _ in keyed if not isinstance(plain(k), (int, float, str))), None)
                    by = f"{args[0].name}() gave back" if args else "The list has"
                    raise TuffError(f":sort sorts numbers, text and true/false (numbers first, then text A to Z). {by} {type_name(bad)}"
                                    + (", which can't be sorted." if args else ", which can't be sorted. Give :sort a function that says what to sort it by, like :sort(by_score)."))
                obj[:] = [x for _, x in keyed]
                return obj
            if name == "reverse":
                no_inputs()
                obj.reverse()
                return obj
            if name == "join":  # ["a", "b"]:join(", ") is "a, b"
                if len(args) > 1:
                    raise TuffError(':join takes what to put between the items, like :join(", "), or nothing.')
                parts = [to_text(x) for x in obj]
                between = to_text(args[0]) if args else ""
                self.room(sum(len(x) for x in parts) + len(between) * len(parts))
                return between.join(parts)
            if name == "find":
                need(1)
                return next((i for i, x in enumerate(obj) if self.binop("==", x, args[0])), -1)
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
        msg = method_help(what, name, SIMPLE_METHODS[kind], kind)
        tip = PY_ONLY.get(name.lower())
        raise TuffError(msg + (f" {tip}" if tip and "instead" not in msg else ""))

    # ---------------------------------------------------------------- the compiled runtime (1.5.0)
    # compile_stmt and compile_expr turn a node, once, into a Python function of the env it runs in. It does just that
    # node's job and calls its parts' functions straight away: nothing works out what kind of node it is each time,
    # and numbers, names, comparisons and loops have quick paths. Everything else goes through the helpers the tree
    # walker uses (binop, item, store, method_call...), so the answers and messages are the same, and each function
    # puts its node's line and column on an error that has none, just where eval and run do. return, break and
    # continue give back a Jump. A subclass keeps its hooks: with its own run() (Tuff Engine's preview), every
    # statement goes through it, and with its own binop, item, store or method_call, there's no quick path past it.

    def compile_stmt(self, s):
        """Statement s as a function of env, made once: it gives back what the statement gives, or a Jump."""
        got = self.codes.get(id(s))
        if got is None or got[0] is not s:
            got = self.codes[id(s)] = (s, self.make_stmt(s))
        return got[1]

    def compile_expr(self, e):
        """Expression e as a function of env, made once."""
        got = self.codes.get(id(e))
        if got is None or got[0] is not e:
            got = self.codes[id(e)] = (e, self.make_expr(e))
        return got[1]

    def compile_block(self, body):
        """A block as one function of env: it gives back its last statement's value (a function with no return gives
        that back), or the Jump on its way out."""
        if self.routed:  # each statement through the subclass's run(), which gives back no Jumps (see unjump)
            run, stmts = self.run, tuple(body)

            def block(env):
                result = None
                for s in stmts:
                    result = run(s, env)
                return result
            return block
        fns = tuple(self.compile_stmt(s) for s in body)
        jumps = bool(block_jumps(body))
        if not fns:
            return lambda env: None
        if len(fns) == 1:
            return fns[0]
        if len(fns) == 2:
            first, second = fns
            if jumps:
                def block(env):
                    out = first(env)
                    if out.__class__ is Jump:
                        return out
                    return second(env)
            else:
                def block(env):
                    first(env)
                    return second(env)
            return block
        if jumps:
            def block(env):
                result = None
                for fn in fns:
                    result = fn(env)
                    if result.__class__ is Jump:
                        return result
                return result
        else:
            def block(env):
                result = None
                for fn in fns:
                    result = fn(env)
                return result
        return block

    def unjump(self, out):
        """Where a Jump would leave compiled code, it becomes the signal the tree walker raises."""
        if out.__class__ is Jump:
            value, out.value = out.value, None
            if out.kind is J_RETURN:
                raise ReturnSignal(value, out.line, out.col)
            raise (BreakSignal if out.kind is J_BREAK else ContinueSignal)(out.line, out.col)
        return out

    def own(self, name):
        """Does this interpreter use Interpreter's own helper called name? (Then a quick path can skip it.)"""
        return getattr(type(self), name) is getattr(Interpreter, name)

    def make_stmt(self, s):
        k = s.kind
        hooks, step = self.step_hooks, self.step
        if k == "expr":
            value = self.compile_expr(s.expr)

            def run(env):
                if hooks:
                    step(s, env)
                return value(env)
            return run
        if k == "assign":
            return self.make_assign(s)
        if k == "if":
            tests = tuple((self.compile_expr(c), self.compile_block(b)) for c, b in s.branches)
            other = None if s.else_body is None else self.compile_block(s.else_body)
            if len(tests) == 1:
                ((test, then),) = tests

                def run(env):
                    if hooks:
                        step(s, env)
                    v = test(env)
                    if v is True or (v is not False and truthy(v)):
                        return then(env)
                    return None if other is None else other(env)
                return run
            if len(tests) == 2:  # if, elif
                (test, then), (test2, then2) = tests

                def run(env):
                    if hooks:
                        step(s, env)
                    v = test(env)
                    if v is True or (v is not False and truthy(v)):
                        return then(env)
                    v = test2(env)
                    if v is True or (v is not False and truthy(v)):
                        return then2(env)
                    return None if other is None else other(env)
                return run

            def run(env):
                if hooks:
                    step(s, env)
                for test, then in tests:
                    v = test(env)
                    if v is True or (v is not False and truthy(v)):
                        return then(env)
                return None if other is None else other(env)
            return run
        if k in ("while", "for"):
            return self.make_loop(s)
        if k == "try":
            body, handler, name = self.compile_block(s.body), self.compile_block(s.handler), s.name

            def run(env):
                if hooks:
                    step(s, env)
                try:
                    return body(env)
                except TuffError as err:
                    if name:
                        env.set(name, err.msg)
                    return handler(env)
            return run
        if k == "func":
            name, params, body, line = s.name, s.params, s.body, s.line
            code = self.compile_block(body)

            def run(env):
                if hooks:
                    step(s, env)
                env.vars[name] = Func(name, params, body, env, line, code)
                return None
            return run
        if k in (J_RETURN, J_BREAK, J_CONTINUE):
            jump = Jump(J_RETURN if k == J_RETURN else J_BREAK if k == J_BREAK else J_CONTINUE, s.line, s.col)  # (kinds are checked with is)
            value = self.compile_expr(s.value) if k == J_RETURN and s.value is not None else None
            if value is None:
                def run(env):
                    if hooks:
                        step(s, env)
                    return jump
                return run

            def run(env):
                if hooks:
                    step(s, env)
                jump.value = value(env)
                return jump
            return run

        def run(env):  # import, flush, kind: the tree walker's own (they're run once, or seldom)
            if hooks:
                step(s, env)
            try:
                return getattr(self, "s_" + k)(s, env)
            except TuffError as err:
                if err.line is None:
                    err.line, err.col = s.line, s.col
                raise
        return run

    def make_assign(self, s):
        hooks, step = self.step_hooks, self.step
        t, op = s.target, s.op
        value = self.compile_expr(s.value)
        if t.kind == "var" and op == "=":
            name = t.name

            def run(env):
                if hooks:
                    step(s, env)
                v = value(env)
                names = env.vars
                if name in names:
                    names[name] = v
                else:
                    env.set(name, v)
                return v
            return run
        if t.kind == "var":  # x += 1 (the value first, then x, as the tree walker does)
            get, binop, sign = self.compile_expr(t), self.binop, op[0]
            if self.own("binop"):
                make, b = QUICK[sign], s.value
                if b.kind == "const" and b.value.__class__ in (int, float) and (b.value != 0 or sign != "/"):
                    return make["store_number"](s, get, b.value, binop, hooks, step)  # x += 1
                if b.kind == "const" and b.value.__class__ is str and "store_text" in make:
                    return make["store_text"](s, get, b.value, binop, hooks, step)  # s += "!"
                return make["store"](s, get, value, binop, hooks, step)

            def run(env):
                if hooks:
                    step(s, env)
                v = value(env)
                try:
                    v = binop(sign, get(env), v)
                except TuffError as err:
                    if err.line is None:
                        err.line, err.col = s.line, s.col
                    raise
                env.set(t.name, v)
                return v
            return run
        if t.kind == "attr":  # rex.hunger = 3, my.hunger -= 1 (1.5.0): the value first, then the object, as set_field does
            obj_of, set_field, name = self.compile_expr(t.obj), self.set_field, t.name
            quick = op == "=" and self.own("set_field")

            def run(env):
                if hooks:
                    step(s, env)
                try:
                    v = value(env)
                    obj = obj_of(env)
                    if quick and obj.__class__ is Instance:
                        fields = obj.fields
                        if name in fields:
                            fields[name] = v
                            return v
                    return set_field(s, obj, v)
                except TuffError as err:
                    if err.line is None:
                        err.line, err.col = s.line, s.col
                    raise
            return run
        obj_of = self.compile_expr(t.obj)  # the list or dictionary and the key are worked out once: votes[input()] += 1
        if t.kind == "slice":
            part_key = self.part_key

            def key_of(env):
                return part_key(t, env)
        else:
            key_of = self.compile_expr(t.index)
        store = self.store
        quick = op == "=" and t.kind == "index" and self.own("store")

        def run(env):
            if hooks:
                step(s, env)
            try:
                v = value(env)
                obj = plain(obj_of(env))
                key = key_of(env)
                if quick:  # (what store does for a list's position or a dictionary's text or whole-number key)
                    if obj.__class__ is list:
                        if key.__class__ is int and -len(obj) <= key < len(obj):
                            obj[key] = v
                            return v
                    elif obj.__class__ is dict and (key.__class__ is str or key.__class__ is int):
                        obj[key] = v
                        return v
                return store(s, obj, key, v)
            except TuffError as err:
                if err.line is None:
                    err.line, err.col = s.line, s.col
                raise
        return run

    def make_loop(self, s):
        hooks, step = self.step_hooks, self.step
        body = self.compile_block(s.body)
        jumps = bool(block_jumps(s.body))  # a return in it can come out (its own break and continue stop here)
        if s.kind == "while":
            test = self.compile_expr(s.cond)

            def run(env):
                if hooks:
                    step(s, env)
                while True:
                    v = test(env)
                    if not (v is True or (v is not False and truthy(v))):
                        return None
                    try:
                        out = body(env)
                    except BreakSignal:  # from a function called in the loop, as with the tree walker
                        return None
                    except ContinueSignal:
                        continue
                    if jumps and out.__class__ is Jump:
                        if out.kind is J_BREAK:
                            return None
                        if out.kind is J_RETURN:
                            return out
            return run
        items_of, for_items, name = self.compile_expr(s.items), self.for_items, s.name

        def run(env):
            if hooks:
                step(s, env)
            try:
                items = for_items(s, plain(items_of(env)))
            except TuffError as err:
                if err.line is None:
                    err.line, err.col = s.line, s.col
                raise
            names = env.vars
            for item in items:
                if name in names:
                    names[name] = item
                else:
                    env.set(name, item)
                try:
                    out = body(env)
                except BreakSignal:
                    return None
                except ContinueSignal:
                    continue
                if jumps and out.__class__ is Jump:
                    if out.kind is J_BREAK:
                        return None
                    if out.kind is J_RETURN:
                        return out
            return None
        return run

    def make_expr(self, e):
        k = e.kind
        line, col = e.line, e.col
        if k == "const":
            value = e.value
            return lambda env: value
        if k == "var":
            name = e.name

            def var(env):
                names = env.vars
                if name in names:
                    return names[name]
                up = env.parent
                while up is not None:
                    names = up.vars
                    if name in names:
                        return names[name]
                    up = up.parent
                try:
                    return env.get(name)  # it isn't anywhere: Env.get says so, with a "did you mean"
                except TuffError as err:
                    if err.line is None:
                        err.line, err.col = line, col
                    raise
            return var
        if k == "binop":
            return self.make_binop(e)
        if k in ("and", "or"):
            left, right = self.compile_expr(e.left), self.compile_expr(e.right)
            if k == "and":
                def both(env):
                    v = left(env)
                    return right(env) if v is True or (v is not False and truthy(v)) else v
                return both

            def either(env):
                v = left(env)
                return v if v is True or (v is not False and truthy(v)) else right(env)
            return either
        if k == "not":
            value = self.compile_expr(e.value)

            def opposite(env):
                v = value(env)
                return not (v is True or (v is not False and truthy(v)))
            return opposite
        if k == "list":
            items = tuple(self.compile_expr(x) for x in e.items)
            return lambda env: [item(env) for item in items]
        if k == "index":
            return self.make_index(e)
        if k == "call":
            return self.make_call(e)
        if k == "method":
            return self.make_method(e)
        if k == "neg":
            value, negative = self.compile_expr(e.value), self.negative

            def neg(env):
                v = value(env)
                if v.__class__ is int or v.__class__ is float:
                    return -v
                try:
                    return negative(v)
                except TuffError as err:
                    if err.line is None:
                        err.line, err.col = line, col
                    raise
            return neg
        if k == "say":
            value, say_text = self.compile_expr(e.value), self.say_text

            def say(env):
                try:
                    return say_text(to_text(value(env)))
                except TuffError as err:
                    if err.line is None:
                        err.line, err.col = line, col
                    raise
            return say
        if k == "dict":
            pairs = tuple((self.compile_expr(key), self.compile_expr(v)) for key, v in zip(e.keys, e.values))

            def table(env):
                try:
                    return {dict_key(key(env)): value(env) for key, value in pairs}
                except TuffError as err:
                    if err.line is None:
                        err.line, err.col = line, col
                    raise
            return table
        if k == "slice":
            return self.make_slice(e)
        if k == "attr":
            obj_of, member, name, quick = self.compile_expr(e.obj), self.member, e.name, self.own("member")

            def attr(env):
                try:
                    obj = obj_of(env)
                    if quick and obj.__class__ is Instance:  # rex.hunger (1.5.0)
                        fields = obj.fields
                        if name in fields:
                            return fields[name]
                    return member(e, obj)
                except TuffError as err:
                    if err.line is None:
                        err.line, err.col = line, col
                    raise
            return attr
        if k == "input":
            prompt = None if e.prompt is None else self.compile_expr(e.prompt)
            looks = getattr(e, "looks", None)
            looks = None if looks is None else tuple(self.compile_expr(a) for a in looks)
            ask = self.ask

            def answer(env):
                try:
                    shown = "" if prompt is None else to_text(prompt(env))
                    return ask(shown, None if looks is None else [look(env) for look in looks])
                except TuffError as err:
                    if err.line is None:
                        err.line, err.col = line, col
                    raise
            return answer
        if k == "held":  # the start of names[order:pop], already worked out (see part)
            held = self.held
            return lambda env: held[-1]

        def other(env):  # sayfn, and anything new: the tree walker's own
            try:
                return self.eval_node(e, env)
            except TuffError as err:
                if err.line is None:
                    err.line, err.col = line, col
                raise
        return other

    def make_binop(self, e):
        op, line, col = e.op, e.line, e.col
        left, right, binop = self.compile_expr(e.left), self.compile_expr(e.right), self.binop
        if op in QUICK and self.own("binop"):
            make = QUICK[op]
            kind = lambda x: x.kind == "const" and {int: "number", float: "number", str: "text"}.get(x.value.__class__)
            right_kind, left_kind = kind(e.right), kind(e.left)  # a number or text written in the program
            if right_kind and right_kind + "_right" in make and (e.right.value != 0 or op not in ("/", "%")):
                return make[right_kind + "_right"](left, e.right.value, binop, line, col)
            if left_kind and left_kind + "_left" in make:
                return make[left_kind + "_left"](e.left.value, right, binop, line, col)
            return make["both"](left, right, binop, line, col)

        def sums(env):  # ^, or a subclass's own binop
            a = left(env)
            b = right(env)
            try:
                return binop(op, a, b)
            except TuffError as err:
                if err.line is None:
                    err.line, err.col = line, col
                raise
        return sums

    def make_index(self, e):
        line, col = e.line, e.col
        obj_of, key_of, item = self.compile_expr(e.obj), self.compile_expr(e.index), self.item
        quick = self.own("item") and self.own("list_index")

        def index(env):
            try:
                obj = plain(obj_of(env))
                key = key_of(env)
                if quick:  # (what item does for a list's or a text's position, or a dictionary's key that's there)
                    if obj.__class__ is list or obj.__class__ is str:
                        if key.__class__ is int and -len(obj) <= key < len(obj):
                            return obj[key]
                    elif obj.__class__ is dict and (key.__class__ is str or key.__class__ is int) and key in obj:
                        return obj[key]
                return item(obj, key, e.obj)
            except TuffError as err:
                if err.line is None:
                    err.line, err.col = line, col
                raise
        return index

    def make_slice(self, e):
        line, col = e.line, e.col
        obj_of, cut, part = self.compile_expr(e.obj), self.cut, self.part
        if e.alt is None and self.own("part"):  # s[1:3], s[:n]: what part works out, without looking anything up
            start = None if e.start is None else self.compile_expr(e.start)
            end = None if e.end is None else self.compile_expr(e.end)
            left_out = self.LEFT_OUT

            def piece(env):
                try:
                    obj = plain(obj_of(env))
                    first = left_out if start is None else plain(start(env))
                    return cut(e, obj, "part", first, left_out if end is None else plain(end(env)))
                except TuffError as err:
                    if err.line is None:
                        err.line, err.col = line, col
                    raise
            return piece

        def piece(env):  # names[order:pop]: both readings (part works it out)
            try:
                obj = plain(obj_of(env))
                return cut(e, obj, *part(e, env))
            except TuffError as err:
                if err.line is None:
                    err.line, err.col = line, col
                raise
        return piece

    def make_call(self, e):
        line, col = e.line, e.col
        fn_of, args = self.compile_expr(e.fn), tuple(self.compile_expr(a) for a in e.args)
        shadowable = e.fn.kind == "var" and e.fn.name in BUILTIN_NAMES  # len = 5, then len(x)
        not_builtin, invoke, interp = self.not_builtin, self.invoke, self
        quick = self.own("invoke")
        new_env = object.__new__

        def call(env):
            try:
                fn = fn_of(env)
                kind = fn.__class__
                if shadowable and kind is not Builtin and not isinstance(fn, (Builtin, Func)):
                    not_builtin(e, fn)
                values = [arg(env) for arg in args]
                if quick and kind is Func:  # what invoke does, once its checks pass, without the call to it
                    names, code = fn.params, fn.code
                    if code is not None and len(values) == len(names) and interp.depth < MAX_DEPTH:
                        local = new_env(Env)
                        local.vars = {names[0]: values[0]} if len(names) == 1 else dict(zip(names, values))
                        local.parent, local.own_names = fn.env, False
                        interp.depth += 1
                        try:
                            out = code(local)
                        except ReturnSignal as r:
                            return r.value
                        except TuffError as err:  # (1.5.0) its line is in the file the function is written in
                            if err.file is None and err.line is not None:
                                err.file = file_of(fn.env)
                            raise
                        except RecursionError:
                            raise TuffError(f"{fn.name}() called itself too many times.")
                        except MemoryError:
                            raise TuffError(f"The program ran out of memory inside {fn.name}(). Is something growing without end?")
                        finally:
                            interp.depth -= 1
                        if out.__class__ is Jump:
                            if out.kind is J_RETURN:
                                value, out.value = out.value, None
                                return value
                            interp.unjump(out)  # a break or continue outside any loop in it: on to a loop around the call
                        return out
                elif quick and kind is Builtin:
                    fits = fn.fits.get(len(values))
                    if fits is not None:
                        return call_python(fn.name + "()", fn.fn, values, fn.takes_err, fits)
                return invoke(fn, values)
            except TuffError as err:
                if err.line is None:
                    err.line, err.col = line, col
                raise
        return call

    def make_method(self, e):
        line, col = e.line, e.col
        obj_of = self.compile_expr(e.obj)
        args = tuple(self.compile_expr(a.value if a.kind == "say" else a) for a in e.args)
        method_call = self.method_call
        quick = QUICK_METHODS.get((e.name, len(args))) if self.own("method_call") else None
        if quick is not None:  # items:add(x), d:has(k), name:upper()...: done here for a list, a dictionary or text
            def method(env):
                try:
                    try:
                        obj = obj_of(env)
                        values = [arg(env) for arg in args]
                        fn = quick.get(obj.__class__)
                        if fn is not None:
                            return fn(obj, *values)
                        return method_call(e, obj, values)
                    except (OverflowError, MemoryError):
                        raise TuffError(TOO_BIG)
                except TuffError as err:
                    if err.line is None:
                        err.line, err.col = line, col
                    raise
            return method

        def method(env):
            try:
                try:
                    obj = obj_of(env)
                    return method_call(e, obj, [arg(env) for arg in args])
                except (OverflowError, MemoryError):  # a number or text too big for the computer, inside a method
                    raise TuffError(TOO_BIG)
            except TuffError as err:
                if err.line is None:
                    err.line, err.col = line, col
                raise
        return method


# ---------------------------------------------------------------- checking without running

# Python habits that are plain names in Tuff, and what to write instead.
PY_NAMES = {
    "True": "Tuff writes true in lowercase.",
    "False": "Tuff writes false in lowercase.",
    "None": "Tuff writes nil for 'nothing'.",
    "float": "To turn text into a number, use number(text).",
    "math": "sqrt, floor, ceil, abs, round, pi, sin, cos, tan and log are built in, so there's nothing to import.",
    "time": "Tuff's time() is the seconds since the program started. Use wait(seconds) to pause. In an app, app:every(seconds, fn) runs something again and again.",
    "json": "file.save(\"data.json\", value) and file.load(\"data.json\") keep lists and dictionaries as JSON.",
    "open": "Use file.read(\"notes.txt\") and file.write(\"notes.txt\", text). They work in your program's folder.",
    "datetime": "now(), today() and date() give the time and the date.",
    "length": "Use len(value) for how long some text or a list is.",
    "self": "Tuff has no classes: make a kind (kind Pet:), and in its actions the object itself is my, like my.hunger.",
}
# Methods from other languages, and the Tuff method that does the same job.
PY_METHODS = {
    "list": {"append": "add", "push": "add", "insert": "add", "contains": "has", "includes": "has", "delete": "remove", "discard": "remove",
             "index": "find", "sorted": "sort", "indexof": "find"},
    "text": {"strip": "trim", "contains": "has", "includes": "has", "upper_case": "upper", "lower_case": "lower",
             "uppercase": "upper", "lowercase": "lower", "toupper": "upper", "tolower": "lower",
             "startswith": "starts", "endswith": "ends", "index": "find", "indexof": "find", "ljust": "pad_right", "rjust": "pad_left"},
    "dict": {"contains": "has", "includes": "has", "pop": "remove", "delete": "remove", "update": "set", "items": "keys", "length": "size", "count": "size"},
}
SIMPLE_METHODS = {"text": ("upper", "lower", "trim", "has", "split", "replace", "starts", "ends", "find", "count", "pad_left", "pad_right"),
                  "list": ("add", "remove", "pop", "has", "sort", "reverse", "join", "find"),
                  "dict": ("has", "get", "set", "remove", "keys", "values", "size"),
                  "line": ("rewrite", "append", "clear", "text", "play")}


def _added(items, x):
    items.append(x)
    return items


def _set(d, k, v):
    d[dict_key(k)] = v
    return d


# 1.5.0: the methods the compiled runtime does itself, by (name, how many inputs): {the kind of value: what
# method_call would do for it}. Anything else (another kind, a Line, a library's object) goes to method_call.
QUICK_METHODS = {
    ("add", 1): {list: _added},
    ("has", 1): {dict: lambda d, k: dict_key(k) in d, str: lambda s, x: to_text(x) in s},
    ("get", 1): {dict: lambda d, k: d.get(dict_key(k), None)},
    ("get", 2): {dict: lambda d, k, default: d.get(dict_key(k), default)},
    ("set", 2): {dict: _set},
    ("upper", 0): {str: str.upper}, ("lower", 0): {str: str.lower}, ("trim", 0): {str: str.strip},
    ("keys", 0): {dict: list}, ("values", 0): {dict: lambda d: list(d.values())}, ("size", 0): {dict: len},
    ("starts", 1): {str: lambda s, x: s.startswith(to_text(x))}, ("ends", 1): {str: lambda s, x: s.endswith(to_text(x))},
    ("find", 1): {str: lambda s, x: s.find(to_text(x))}, ("count", 1): {str: lambda s, x: s.count(to_text(x))},
}
ONE_INPUT = {"has", "add", "remove", "play"}
INPUTS = {"replace": (2, 2), "set": (2, 2), "get": (1, 2), "pad_left": (1, 2), "pad_right": (1, 2), "split": (0, 1), "join": (0, 1),
          "sort": (0, 1), "starts": (1, 1), "ends": (1, 1), "find": (1, 1), "count": (1, 1)}  # 1.4.0's: (fewest, most) inputs
LOOK_INPUTS = {"rewrite", "append"}  # the new text, then look and animation words (1.3.6)


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
    if kind == "dict" and alt not in SIMPLE_METHODS["dict"]:  # ages.sam: a dictionary's values are read with [ ]
        return f"Only libraries use '.', and this is {what}. Read a value with [ ], like {owner}[\"{name}\"]"
    return f"Only libraries use '.', and this is {what}. For methods use ':', like {owner}:{alt}"


def node_text(e):
    """Short code as it was written, for messages: user, "name", 3, user:get("address"), users[0]. None if it's longer."""
    if e.kind == "var":
        return e.name
    if e.kind == "const" and isinstance(e.value, str):
        return f'"{e.value}"' if e.value.isprintable() and '"' not in e.value and len(e.value) <= 30 else None
    if e.kind == "const" and isinstance(e.value, int) and not isinstance(e.value, bool):
        return str(e.value)
    if e.kind in ("method", "index"):
        obj = node_text(e.obj)
        parts = [node_text(a) for a in (e.args if e.kind == "method" else [e.index])]
        if obj is None or None in parts:
            return None
        return f"{obj}:{e.name}({', '.join(parts)})" if e.kind == "method" else f"{obj}[{parts[0]}]"
    return None


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
    fits = fits_inputs(fn, count)
    if fits is not None:
        return fits
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
    """tap's functions ("lib") and the methods of its responses ("kinds"), read from the library itself
    without going online. None when it can't be loaded."""
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
    animations it knows, read from the library itself without opening a window, with tgame's panels and screens
    added (with_game_ui_kinds). None when it can't be loaded."""
    global _ATGUI
    if _ATGUI is None:
        try:
            import tuff_atgui
            _ATGUI = with_game_ui_kinds(tuff_atgui.tables())
        except Exception:
            _ATGUI = {}
    return _ATGUI or None


def with_game_ui_kinds(at):
    """atgui's tables with tgame's panel and screen (game:panel, game:screen, game:start_screen) as atgui kinds:
    a panel is a column pinned to the game, and a screen a column over all of it that also has :shown, so their
    widgets are checked like atgui's. The methods tgame's own tables list for them are added, and atgui's own
    "panel" or "screen", if it ever has one, wins."""
    def shown():
        return None

    own = (tgame_tables() or {}).get("kinds", {})
    column = at["kinds"]["column"]
    ui = {"panel": {**column, **own.get("panel", {})}, "screen": {**column, "shown": shown, **own.get("screen", {})}}
    return {**at, "kinds": {**ui, **at["kinds"]}}


_TGAME = None

# tgame's land (land = world:terrain(200)) as the checker knows it: each of the land's methods and its inputs. A
# spot ([x, z]) can go in place of an x and z, and the brushes (raise, lower, smooth, flatten) take a stroke there
# too: a list of [x, z] spots. Then the styles, the lightings, and names people guess with the ones tgame uses.
TERRAIN_INPUTS = {
    "style": ("the style",), "hill": ("x", "z", "size", "height"), "mountain": ("x", "z", "size", "height"),
    "dip": ("x", "z", "size", "depth"), "lake": ("x", "z", "size", "depth"), "valley": ("x1", "z1", "x2", "z2", "width", "depth"),
    "raise": ("x", "z", "size", "amount"), "lower": ("x", "z", "size", "amount"), "smooth": ("x", "z", "size"),
    "flatten": ("x", "z", "size", "height"), "water": ("the sea's height",), "height_at": ("x", "z"),
}
TERRAIN_BRUSHES = ("raise", "lower", "smooth", "flatten")
TERRAIN_STYLES = ("grass", "desert", "snow", "rocky", "autumn")
LIGHTINGS = ("modern", "simple")
TERRAIN_HINTS = {
    "world": {"land": "terrain", "landscape": "terrain", "heightmap": "terrain", "lights": "lighting", "shading": "lighting",
              "graphics": "lighting"},
    "terrain": {"mound": "hill", "bump": "hill", "peak": "mountain", "hole": "dip", "pit": "dip", "crater": "dip", "pond": "lake",
                "pool": "lake", "river": "valley", "canyon": "valley", "trench": "valley", "dig": "lower", "sculpt": "raise",
                "blur": "smooth", "level": "flatten", "flat": "flatten", "sea": "water", "ocean": "water", "texture": "style",
                "paint": "style", "theme": "style", "height": "height_at", "get_height": "height_at", "elevation": "height_at",
                "ground_y": "height_at"},
}
VALUE_HINTS = {
    "style": {"sand": "desert", "sandy": "desert", "beach": "desert", "ice": "snow", "icy": "snow", "snowy": "snow", "winter": "snow",
              "rock": "rocky", "stone": "rocky", "stony": "rocky", "fall": "autumn", "green": "grass", "grassy": "grass", "meadow": "grass"},
    "lighting": {"realistic": "modern", "real": "modern", "pbr": "modern", "hd": "modern", "fancy": "modern", "advanced": "modern",
                 "new": "modern", "basic": "simple", "default": "simple", "normal": "simple", "old": "simple", "classic": "simple",
                 "flat": "simple"},
}


# tgame's menus, buttons and screens as the checker knows them: the places a panel can go (and places people
# guess, with the one tgame uses), names people guess for the three makers, and how each one is used, for messages.
ANCHORS = ("top left", "top", "top right", "left", "center", "right", "bottom left", "bottom", "bottom right")
ANCHOR_HINTS = {"middle": "center", "centre": "center", "centered": "center", "centred": "center", "top center": "top",
                "top centre": "top", "top middle": "top", "bottom center": "bottom", "bottom centre": "bottom",
                "bottom middle": "bottom", "middle left": "left", "center left": "left", "left center": "left",
                "middle right": "right", "center right": "right", "right center": "right", "upper left": "top left",
                "upper right": "top right", "lower left": "bottom left", "lower right": "bottom right",
                "left top": "top left", "right top": "top right", "left bottom": "bottom left", "right bottom": "bottom right",
                "topleft": "top left", "topright": "top right", "bottomleft": "bottom left", "bottomright": "bottom right",
                "up": "top", "down": "bottom", "north": "top", "south": "bottom", "east": "right", "west": "left",
                "middle top": "top", "middle bottom": "bottom"}
GAME_UI = ("panel", "screen", "start_screen", "main_menu")
GAME_UI_HINTS = {"overlay": "screen", "popup": "screen", "pop_up": "screen", "dialog": "screen",
                 "modal": "screen", "page": "screen", "shop": "screen", "ui": "panel", "gui": "panel", "toolbar": "panel",
                 "sidebar": "panel", "bar": "panel", "start_menu": "start_screen",
                 "click_to_play": "start_screen", "click_to_start": "start_screen",
                 "startscreen": "start_screen", "start_page": "start_screen",
                 # splash screens and main menus (game:splash, game:main_menu)
                 "title_screen": "splash", "intro": "splash", "logo": "splash", "splash_screen": "splash",
                 "splashscreen": "splash", "logo_screen": "splash", "intro_screen": "splash", "menu": "main_menu",
                 "home_screen": "main_menu", "menu_screen": "main_menu", "mainmenu": "main_menu", "title_menu": "main_menu",
                 "home_menu": "main_menu"}
GAME_UI_METHOD_HINTS = {"close": "hide", "dismiss": "hide", "open": "show", "visible": "shown", "is_visible": "shown",
                        "is_shown": "shown", "showing": "shown", "is_open": "shown", "is_showing": "shown", "empty": "clear"}
GAME_UI_USE = {"panel": 'bar = {owner}:panel("top left")', "screen": 'shop = {owner}:screen("Shop") or {owner}:screen("Shop", false)',
               "start_screen": 'start = {owner}:start_screen("My Game", "Click to play")',
               "main_menu": 'menu = {owner}:main_menu("My Game")'}
GAME_UI_TAKES = {"panel": "where the panel goes", "screen": "a title, then whether it pauses the game",
                 "start_screen": "a title, then a hint", "main_menu": "its title"}

# The mouse in a 3D world (world:lock_mouse...), filled in where tgame's tables leave it out (with_mouse): each
# method's inputs, what mouse_locked gives back, and names people guess.
MOUSE_INPUTS = {"lock_mouse": (), "unlock_mouse": (), "mouse_locked": (), "auto_lock": ("on",)}
MOUSE_HINTS = {"release_mouse": "unlock_mouse", "free_mouse": "unlock_mouse", "show_cursor": "unlock_mouse",
               "unlock_cursor": "unlock_mouse", "unlock_pointer": "unlock_mouse", "exit_pointer_lock": "unlock_mouse",
               "capture_mouse": "lock_mouse", "hide_cursor": "lock_mouse", "lock_cursor": "lock_mouse",
               "lock_pointer": "lock_mouse", "pointer_lock": "lock_mouse", "request_pointer_lock": "lock_mouse",
               "is_mouse_locked": "mouse_locked", "is_locked": "mouse_locked", "locked": "mouse_locked",
               "click_to_lock": "auto_lock", "lock_on_click": "auto_lock", "autolock": "auto_lock"}
MOUSE_NEEDS_3D = ("Locking the mouse is for looking around in a 3D world. Make the game with tgame.world(...) and "
                  "give it a player: world:player(\"first person\").")


# tgame's physics as the checker knows it, filled in where tgame's own tables leave it out (with_physics): what each
# method takes, for messages, an example ({o} is the thing's name), the input counts that fit, and how many inputs a
# spot ([x, y, z] in 3D, [x, y] in 2D) can stand in for. A car and a ragdoll have an object's methods too.
_THING_PHYSICS = {
    "physics": ("nothing, or the kind of physics", '{o}:physics() or {o}:physics("static")', (0, 1), 0),
    "weight": ("nothing (to read it), or how heavy it is, in kg", "{o}:weight(50)", (0, 1), 0),
    "mass": ("nothing (to read it), or how heavy it is, in kg", "{o}:mass(2)", (0, 1), 0),
    "bounce": ("how bouncy it is, from 0 to 1", "{o}:bounce(0.6)", (1,), 0),
    "friction": ("how grippy it is, from 0 up", "{o}:friction(0.4)", (1,), 0),
    "on_hit": ("the name of a function to run when something hits it", "{o}:on_hit(bumped)", (1,), 0),
    "sleep": ("nothing", "{o}:sleep()", (0,), 0),
    "wake": ("nothing", "{o}:wake()", (0,), 0),
}
_PHYSICS_3D = {
    **_THING_PHYSICS,
    "push": ("x, y and z: how hard to push it each way", "{o}:push(0, 5, -3)", (3,), 3),
    "spin": ("how fast it keeps turning, or x, y and z to give it a spin", "{o}:spin(0, 2, 0)", (1, 3), 3),
    "velocity": ("nothing (to read it), or x, y and z", "{o}:velocity(0, 0, -4)", (0, 3), 3),
}
PHYSICS_INPUTS = {
    "world": {
        "gravity": ("how strong gravity is (-9.8 is like on Earth)", "{o}:gravity(-9.8)", (1,), 0),
        "explode": ("x, y and z, then how strong and how far", "{o}:explode(0, 0, 0, 12, 8)", (3, 4, 5), 3),
        "car": ("x, y, z and a color", '{o}:car(0, 1, 10, "red")', (0, 1, 2, 3, 4), 3),
        "ragdoll": ("x, y, z and a color", '{o}:ragdoll(5, 0, 0, "blue")', (0, 1, 2, 3, 4), 3),
    },
    "game": {
        "gravity": ("how strong gravity is, in pixels a second each second (down the screen)", "{o}:gravity(900)", (1,), 0),
        "walls": ("true or false: whether the edges of the screen are walls", "{o}:walls(true)", (0, 1), 0),
        "explode": ("x and y, then how strong and how far", "{o}:explode(400, 300, 600, 200)", (2, 3, 4), 2),
    },
    "object": {**_PHYSICS_3D, "animate": ('an animation: "walk", "idle", "wave" or "none"', '{o}:animate("walk")', (1,), 0)},
    "sprite": {
        **_THING_PHYSICS,
        "push": ("x and y: how hard to push it each way", "{o}:push(200, -300)", (2,), 2),
        "velocity": ("nothing (to read it), or x and y", "{o}:velocity(0, -200)", (0, 2), 2),
    },
    "player": {"on_hit": _THING_PHYSICS["on_hit"],
               "weight": ("nothing (to read it), or how heavy the player is, in kg", "{o}:weight(70)", (0, 1), 0)},
    "car": {
        **_PHYSICS_3D,
        "drive": ("nothing, or false to stop driving it", "{o}:drive()", (0, 1), 0),
        "engine": ("how strong its engine is (1 is normal)", "{o}:engine(1.5)", (1,), 0),
        "speed": ("nothing: it gives back how fast it goes, in km/h", "say {o}:speed()", (0,), 0),
        "flip": ("nothing", "{o}:flip()", (0,), 0),
        "on_enter": ("the name of a function to run when the player gets in", "{o}:on_enter(got_in)", (1,), 0),
        "on_exit": ("the name of a function to run when the player gets out", "{o}:on_exit(got_out)", (1,), 0),
        "driven": ("nothing: it gives back whether the player is in it", "if {o}:driven():", (0,), 0),
    },
    "ragdoll": _PHYSICS_3D,
}
PHYSICS_KINDS = ("dynamic", "static", "kinematic", "off")
# Getting in and out of a car, by the names people guess (Checker: its own message, since F does it in a game).
_GET_IN = "The player gets in by pressing F next to it, or {o}:drive() starts the game with the player in it."
_GET_OUT = "The player gets out by pressing F again, or {o}:drive(false) gets it out."
CAR_DOORS = {**dict.fromkeys(("get_in", "enter", "board", "get_inside", "mount", "ride"), _GET_IN),
             **dict.fromkeys(("get_out", "exit", "leave", "get_off", "dismount", "unmount"), _GET_OUT)}
PHYSICS_SAYS = {"dynamic": "it falls and can be pushed", "static": "it stays where it is", "kinematic": "your code moves it"}
ANIMATIONS = ("walk", "idle", "wave", "none")
PHYSICS_HIT = (0, 2, "2 inputs (the thing that hit it, and how hard)")
_PUSHES = {"impulse": "push", "apply_impulse": "push", "add_impulse": "push", "kick": "push", "force": "push",
           "add_force": "push", "apply_force": "push", "shove": "push", "throw": "push", "launch": "push",
           "set_velocity": "velocity", "vel": "velocity", "linear_velocity": "velocity", "set_weight": "weight",
           "heaviness": "weight", "get_weight": "weight", "get_mass": "mass", "set_mass": "mass", "bounciness": "bounce", "restitution": "bounce", "elasticity": "bounce",
           "bouncy": "bounce", "set_bounce": "bounce", "grip": "friction", "set_friction": "friction",
           "rigidbody": "physics", "rigid_body": "physics", "body": "physics", "enable_physics": "physics",
           "use_physics": "physics", "add_physics": "physics", "set_physics": "physics", "collider": "physics",
           "physical": "physics", "dynamic": "physics", "collision": "on_hit", "on_collision": "on_hit",
           "on_collide": "on_hit", "oncollision": "on_hit", "on_touch": "on_hit", "on_contact": "on_hit",
           "on_bump": "on_hit", "on_hit_by": "on_hit", "when_hit": "on_hit", "hit": "on_hit", "collided": "on_hit",
           "freeze": "sleep", "rest": "sleep", "wakeup": "wake", "wake_up": "wake", "unfreeze": "wake",
           "torque": "spin", "apply_torque": "spin", "add_torque": "spin", "angular_impulse": "spin"}
PHYSICS_HINTS = {
    "world": {"set_gravity": "gravity", "explosion": "explode", "blast": "explode", "boom": "explode", "bomb": "explode",
              "kaboom": "explode", "vehicle": "car", "kart": "car", "truck": "car", "buggy": "car", "add_car": "car",
              "make_car": "car", "rag_doll": "ragdoll", "dummy": "ragdoll", "puppet": "ragdoll", "add_ragdoll": "ragdoll"},
    "game": {"set_gravity": "gravity", "edges": "walls", "borders": "walls", "bounds": "walls", "boundaries": "walls",
             "screen_walls": "walls", "edge_walls": "walls", "explosion": "explode", "blast": "explode", "boom": "explode",
             "bomb": "explode"},
    "object": {**_PUSHES, "anim": "animate", "animation": "animate", "play_animation": "animate",
               "set_animation": "animate", "play_anim": "animate"},
    "sprite": _PUSHES,
    "car": {**_PUSHES, "accelerate": "engine", "throttle": "engine", "power": "engine", "gas": "engine", "motor": "engine",
            "horsepower": "engine", "control": "drive", "controls": "drive", "on_get_in": "on_enter", "when_entered": "on_enter",
            "on_get_out": "on_exit", "on_leave": "on_exit", "when_left": "on_exit", "is_driven": "driven",
            "occupied": "driven", "in_use": "driven", "has_driver": "driven", "steer": "drive", "drivable": "drive", "reset": "flip", "unflip": "flip", "upright": "flip", "flip_over": "flip",
            "kmh": "speed", "mph": "speed", "get_speed": "speed"},
    "ragdoll": _PUSHES,
    "player": {"on_collision": "on_hit", "on_collide": "on_hit", "collision": "on_hit", "on_bump": "on_hit",
               "mass": "weight", "set_weight": "weight", "is_driving": "in_car", "driving": "in_car",
               "in_vehicle": "in_car", "is_in_car": "in_car"},
}
VALUE_HINTS["physics"] = {  # tgame itself takes "fixed", "on", "none"... (its physics_words, Checker.land_value)
    "frozen": "static", "wall": "static", "ground": "static", "immovable": "static", "stuck": "static", "stay": "static",
    "false": "off", "disabled": "off", "nothing": "off", "stop": "off", "yes": "dynamic", "true": "dynamic",
    "falling": "dynamic", "rigid": "dynamic", "moving": "dynamic", "normal": "dynamic", "default": "dynamic",
    "physics": "dynamic", "kinematics": "kinematic", "animated": "kinematic", "scripted": "kinematic", "code": "kinematic",
    "moved": "kinematic", "manual": "kinematic"}
VALUE_HINTS["animation"] = {
    "walking": "walk", "run": "walk", "running": "walk", "jog": "walk", "move": "walk", "stand": "idle",
    "standing": "idle", "rest": "idle", "breathe": "idle", "breathing": "idle", "still": "idle", "wait": "idle",
    "waving": "wave", "hello": "wave", "hi": "wave", "off": "none", "stop": "none", "nothing": "none", "no": "none"}


def tgame_tables():
    """tgame's functions ("lib"), the methods of everything it makes ("kinds"), what they give back, its events,
    hints for guessed names and a check for text inputs, read from the library without opening a window.
    None when it can't be loaded."""
    global _TGAME
    if _TGAME is None:
        try:
            import tuff_tgame
            _TGAME = with_mouse(with_game_ui(with_gamekit(with_physics(with_terrain(tuff_tgame.tables(), tuff_tgame),
                                                                     tuff_tgame), tuff_tgame), tuff_tgame), tuff_tgame)
        except Exception:
            _TGAME = {}
    return _TGAME or None


def with_game_ui(tg, lib):
    """tgame's tables with the menus, buttons and screens filled in where they leave them out: game:panel,
    game:screen and game:start_screen on a game and a world, what they give back (atgui_tables' "panel" and
    "screen", unless tgame names an atgui kind itself), the guessed names, and the places a panel can go
    (tgame's ANCHORS when it has them). Whatever tgame's own tables say wins."""
    def panel(anchor):
        return None

    def screen(title="", pauses=True):
        return None

    def start_screen(title, hint="Click to play"):
        return None

    def main_menu(title=None):
        return None

    def splash(what=None, seconds=2):
        return None

    makers = {"panel": panel, "screen": screen, "start_screen": start_screen, "main_menu": main_menu, "splash": splash}
    made = {"panel": "@panel", "screen": "@screen", "start_screen": "@screen", "main_menu": "@screen"}
    kinds, gives, hints = dict(tg["kinds"]), dict(tg["gives"]), dict(tg["hints"])
    for kind in ("game", "world"):
        kinds[kind] = {**makers, **tg["kinds"][kind]}
        own = tg["gives"].get(kind, {})
        gives[kind] = {**own, **{k: v for k, v in made.items() if not str(own.get(k, "")).startswith("@")}}
        hints[kind] = {**GAME_UI_HINTS, **tg["hints"].get(kind, {})}
    anchors = getattr(lib, "ANCHORS", ANCHORS)
    return {**tg, "kinds": kinds, "gives": gives, "hints": hints, "anchors": tuple(anchors)}


def with_mouse(tg, lib):
    """tgame's tables with the mouse in a 3D world filled in where they leave it out: world:lock_mouse,
    :unlock_mouse, :mouse_locked (true or false) and :auto_lock(on), the names people guess, and what a 2D game
    says about them (tgame's NEEDS_3D). Whatever tgame's own tables say wins."""
    def mouse():
        return None

    def auto_lock(on=True):
        return None

    world = {**{m: (auto_lock if m == "auto_lock" else mouse) for m in MOUSE_INPUTS}, **tg["kinds"]["world"]}
    gives = {**tg["gives"], "world": {"mouse_locked": "$bool", **tg["gives"]["world"]}}
    hints = {**tg["hints"], "world": {**MOUSE_HINTS, **tg["hints"].get("world", {})}}
    needs_3d = {**dict.fromkeys(MOUSE_INPUTS, MOUSE_NEEDS_3D), **tg.get("needs_3d", {})}
    return {**tg, "kinds": {**tg["kinds"], "world": world}, "gives": gives, "hints": hints, "needs_3d": needs_3d}


def with_terrain(tg, lib):
    """tgame's tables with the land filled in where they leave it out: world:terrain and world:lighting, the land's
    methods, what world:terrain and land:height_at give back, the guessed names, and the style and lighting names
    (tgame's TERRAIN_STYLES and LIGHTINGS when it has them). Whatever tgame's own tables say wins."""
    def terrain(size, style=None):
        return None

    def lighting(name):
        return None

    def land(*inputs):  # Checker.check_land_inputs counts these
        return None

    world = dict(tg["kinds"]["world"])
    world.setdefault("terrain", terrain)
    world.setdefault("lighting", lighting)
    kinds = {**tg["kinds"], "world": world, "terrain": tg["kinds"].get("terrain") or dict.fromkeys(TERRAIN_INPUTS, land)}
    gives = {**tg["gives"], "world": {"terrain": "terrain", **tg["gives"]["world"]},
             "terrain": {"height_at": "$number", **tg["gives"].get("terrain", {})}}
    hints = {**tg["hints"], **{k: {**v, **tg["hints"].get(k, {})} for k, v in TERRAIN_HINTS.items()}}
    return {**tg, "kinds": kinds, "gives": gives, "hints": hints, "styles": tuple(getattr(lib, "TERRAIN_STYLES", TERRAIN_STYLES)),
            "lightings": tuple(getattr(lib, "LIGHTINGS", LIGHTINGS))}


def physics_input(*inputs):  # stands in for a physics method tgame's tables leave out: Checker.check_physics_inputs counts
    return None


def with_physics(tg, lib):
    """tgame's tables with the physics filled in where they leave it out: the physics methods of games, worlds, sprites,
    objects and the player (thing:physics(), :push, :on_hit, world:car...), a car and a ragdoll (an object's methods
    and their own), what they give back (physics() gives back the thing, car:speed() a number), what on_hit gives its
    function, the guessed names, and the kinds of physics and the animations (tgame's PHYSICS_KINDS and ANIMATIONS
    when it has them). Whatever tgame's own tables say wins."""
    own_kinds, own_gives = tg["kinds"], tg["gives"]
    kinds, gives, handlers, hints = dict(own_kinds), dict(own_gives), dict(tg["handlers"]), dict(tg["hints"])
    for kind in ("car", "ragdoll"):  # an object, with its own methods on top
        mine = {**{m: (kind if v == "object" else v) for m, v in own_gives.get("object", {}).items()},
                **{m: kind for m in PHYSICS_INPUTS[kind] if m not in ("velocity", "weight", "mass")}}
        if kind == "car":
            mine["speed"] = "$number"
        kinds[kind] = own_kinds.get(kind) or {**own_kinds["object"], **dict.fromkeys(PHYSICS_INPUTS[kind], physics_input)}
        gives[kind] = {**mine, **own_gives.get(kind, {})}
    for kind, table in PHYSICS_INPUTS.items():
        kinds[kind] = {**dict.fromkeys(table, physics_input), **kinds.get(kind, {})}
        if kind in ("object", "sprite", "player"):  # the setters give back the thing (velocity() gives a list, and
            # weight() and mass() a number: with an input or not, it depends)
            gives[kind] = {**{m: kind for m in table if m not in ("velocity", "weight", "mass")}, **gives.get(kind, {})}
        if kind in ("object", "sprite", "player", "car", "ragdoll"):
            handlers[kind] = {"on_hit": PHYSICS_HIT, **handlers.get(kind, {})}
        hints[kind] = {**PHYSICS_HINTS.get(kind, {}), **hints.get(kind, {})}
    gives["world"] = {"car": "car", "ragdoll": "ragdoll", **gives["world"]}
    return {**tg, "kinds": kinds, "gives": gives, "handlers": handlers, "hints": hints, "physics_inputs": PHYSICS_INPUTS,
            "physics_kinds": tuple(getattr(lib, "PHYSICS_KINDS", PHYSICS_KINDS)),
            "animations": tuple(getattr(lib, "ANIMATIONS", ANIMATIONS))}


# tgame's saved game data as the checker knows it (Checker.check_saves): game:save, :load, :saved and :forget on a
# game or a world. For each, what it takes, for messages, an example ({o} is the game's name) and the input counts that
# fit. The name always comes first, as text; what :save keeps can be anything JSON can hold.
SAVE_INPUTS = {
    "save": ("a name, then what to save", '{o}:save("best", score)', (2,)),
    "load": ("the save's name, then what to give back when nothing was saved (if you like)", 'best = {o}:load("best", 0)', (1, 2)),
    "saved": ("the save's name", '{o}:saved("best")', (1,)),
    "forget": ("the save's name, or nothing to forget every save", '{o}:forget("best")', (0, 1)),
}
SAVE_KEEPS = "numbers, text, true/false, lists and tables"
SAVE_KINDS = ("$number", "$text", "$bool", "$nil", "$list", "$line", "$dict")  # what :save can keep
# tgame's multiplayer as the checker knows it (Checker.check_net): game:host, :join, :send, :share and the rest, on a
# game or a world. For each, what it takes, for messages, an example ({o} is the game's name), the input counts that
# fit, and what its first input is when that has to be text. :send and :share carry what :save keeps. on_message,
# on_join and on_leave are tgame's events (its HANDLERS), checked with the rest of its events.
NET_INPUTS = {
    "host": ("the room's name (or nothing: the game's title)", '{o}:host("Tag")', (0, 1), "the room's name"),
    "join": ("nothing (the first room it finds), a room's name or the host's address", '{o}:join() or {o}:join("Tag")',
             (0, 1), "the room's name or the host's address"),
    "leave": ("no inputs", "{o}:leave()", (0,), None),
    "connected": ("no inputs", "if {o}:connected():", (0,), None),
    "hosting": ("no inputs", "if {o}:hosting():", (0,), None),
    "players": ("no inputs", "names = {o}:players()", (0,), None),
    "others": ("no inputs", "for p in {o}:others():", (0,), None),
    "my_name": ("your player's name (or nothing, to get it)", '{o}:my_name("Sam")', (0, 1), "the name"),
    "send": ("a message, then a value to go with it (if you like)", '{o}:send("score", 10)', (1, 2), "the message"),
    "share": ("a name, then its value", '{o}:share("coins", 5)', (2,), "the name"),
    "shared": ("the name, then what to give back until someone shares it (if you like)", 'coins = {o}:shared("coins", 0)',
               (1, 2), "the name"),
}
NET_NEEDS_3D = ("The other players are people in a 3D world. Make the game with tgame.world(...) and give it a player, "
                "or in 2D use game:players() for their names and game:on_message to hear where they are.")
# ---------------------------------------------------------------- the game kit (1.2.0)
# tgame's game kit as the checker knows it, filled in where tgame's own tables leave it out (with_gamekit): effects
# (slow_mo, shake, pop_text, weather, a day cycle), the HUD (health bars, a countdown, an arrow to a thing, a
# minimap), interaction (grabbing, people who talk, doors and keys) and level pieces (jump and boost pads, platforms
# that move along a path). Each method has what it takes, for messages, an example ({o} is the thing's name), the
# input counts that fit, and where a spot can stand in for x, y and z: (how many inputs, at which input), or 0.
_KIT_THING = {  # sprites and objects alike: a health bar
    "health_bar": ("the most health it can have", "{o}:health_bar(100)", (1,), 0),
    "hurt": ("how much health it loses", "{o}:hurt(10)", (1,), 0),
    "heal": ("how much health it gets back", "{o}:heal(5)", (1,), 0),
    "health": ("nothing: it gives back how much health it has", "say {o}:health()", (0,), 0),
    "on_death": ("the name of a function to run when its health reaches 0", "{o}:on_death(gone)", (1,), 0),
}
_KIT_TALKS = {  # 3D objects (a person, a door, a car, a ragdoll) talk and move along a path
    "say": ("the words, then how many seconds the bubble stays (0 keeps it)", '{o}:say("Hi! Find my lost cat.")', (1, 2), 0),
    "on_talk": ("the name of a function to run when the player talks to it (E)", "{o}:on_talk(talk)", (1,), 0),
    "path": ("a list of spots ([x, y, z]), how fast it moves (m/s), then \"loop\" to go round",
             "{o}:path([[0, 2, 0], [10, 2, 0]], 3)", (0, 1, 2, 3), 0),
}
_KIT_OBJECT = {**_KIT_THING, **_KIT_TALKS}  # and have health, all but a door (DOOR_NO_HEALTH)
_KIT_GAME = {  # a 2D game and a 3D world alike
    "slow_mo": ("how fast everything goes (0.3 is 30%), then for how many seconds", "{o}:slow_mo(0.3, 2)", (1, 2), 0),
    "shake": ("how hard the camera shakes (0 to 2), then for how many seconds", "{o}:shake(0.5)", (1, 2), 0),
    "countdown": ("how many seconds, then the name of a function to run at 0", "clock = {o}:countdown(60, times_up)", (1, 2), 0),
}
KIT_INPUTS = {
    "game": {**_KIT_GAME,
             "pop_text": ("the text, x and y, then a color and a size", '{o}:pop_text("+10", 400, 300)', (3, 4, 5), (2, 1))},
    "world": {
        **_KIT_GAME,
        "pop_text": ("the text, x, y and z, then a color and a size", '{o}:pop_text("+10", 0, 2, 0)', (4, 5, 6), (3, 1)),
        "weather": ('"rain", "snow" or "none", then how strong it is (0 to 2)', '{o}:weather("rain")', (1, 2), 0),
        "day_cycle": ("how many seconds a whole day takes (0 stops it)", "{o}:day_cycle(120)", (1,), 0),
        "time_of_day": ("the hour, from 0 to 24 (18 is 6 pm)", "{o}:time_of_day(18)", (1,), 0),
        "arrow_to": ("the thing to point at", "arrow = {o}:arrow_to(chest)", (1,), 0),
        "minimap": ('nothing, or its size in pixels and then a corner', 'map = {o}:minimap(180, "top right")', (0, 1, 2), 0),
        "door": ("x, y and z, then a color", "door = {o}:door(0, 0, -5)", (3, 4), (3, 0)),
        "jump_pad": ("x, y and z, then how hard it launches things up (m/s)", "pad = {o}:jump_pad(0, 0, 5, 15)", (3, 4), (3, 0)),
        "boost_pad": ("x, y and z, then how hard it shoots the player forward (m/s)", "boost = {o}:boost_pad(0, 0, 10, 20)", (3, 4), (3, 0)),
    },
    "sprite": _KIT_THING,
    "object": _KIT_OBJECT,
    "car": _KIT_OBJECT,
    "ragdoll": _KIT_OBJECT,
    "player": {
        "can_grab": ("nothing, or false to turn grabbing off", "{o}:can_grab()", (0, 1), 0),
        "holding": ("nothing: it gives back what the player is holding (or nil)", "held = {o}:holding()", (0,), 0),
    },
    "countdown": {
        "add": ("how many seconds to add", "{o}:add(5)", (1,), 0),
        "stop": ("nothing", "{o}:stop()", (0,), 0),
        "left": ("nothing: it gives back how many seconds are left", "say {o}:left()", (0,), 0),
    },
    "arrow": {"hide": ("nothing", "{o}:hide()", (0,), 0), "show": ("nothing", "{o}:show()", (0,), 0)},
    "minimap": {
        "mark": ("a thing, then the dot's color", '{o}:mark(coin, "gold")', (1, 2), 0),
        "unmark": ("the thing", "{o}:unmark(coin)", (1,), 0),
        "zoom": ("how close it shows (2 is twice as close)", "{o}:zoom(2)", (1,), 0),
    },
    "door": {
        **_KIT_TALKS,
        "open": ("nothing", "{o}:open()", (0,), 0),
        "close": ("nothing", "{o}:close()", (0,), 0),
        "needs": ("the key: a thing the player picks up", 'key = world:spawn("key", 3, 0, 3), then {o}:needs(key)', (1,), 0),
        "lock": ("nothing", "{o}:lock()", (0,), 0),
        "unlock": ("nothing", "{o}:unlock()", (0,), 0),
    },
}
# What the makers make (a jump pad and a boost pad are objects: they turn), and what each kit method gives back.
KIT_MAKES = {"countdown": "countdown", "arrow_to": "arrow", "minimap": "minimap", "door": "door", "jump_pad": "object",
             "boost_pad": "object"}
KIT_GIVES = {"health": "$number", "left": "$number", "holding": "object"}
KIT_HANDLERS = {"on_death": (0, 0, "no inputs"), "on_talk": (0, 0, "no inputs"), "countdown": (1, 0, "no inputs")}
# The kit's 3D-only makers, for a 2D game: what it is, and how it's used.
KIT_3D = {"weather": ("The weather", 'world:weather("rain")'), "day_cycle": ("A day and night cycle", "world:day_cycle(120)"),
          "time_of_day": ("The time of day", "world:time_of_day(18)"), "arrow_to": ("An arrow to a thing", "arrow = world:arrow_to(chest)"),
          "minimap": ("The minimap", "map = world:minimap()"), "door": ("A door", "door = world:door(0, 0, -5)"),
          "jump_pad": ("A jump pad", "pad = world:jump_pad(0, 0, 5, 15)"), "boost_pad": ("A boost pad", "boost = world:boost_pad(0, 0, 10, 20)")}
# What a door, a car and a ragdoll can't do though other objects can, and what to do instead: a door has no health,
# and a car or a ragdoll always uses physics, so it can't move along a path ({o}:path() to stop one is fine).
DOOR_NO_HEALTH = ("A door doesn't have health, so it can't have :{name}. It opens and closes ({o}:open(), {o}:close()), "
                  "and {o}:needs(key) locks it until the player has the key.")
NO_PATH = {"car": "A car always uses physics (it drives on its wheels), so it can't move along a path. Push it with "
                  "{o}:push(0, 4, -6), or let the player drive it with {o}:drive().",
           "ragdoll": "A ragdoll always uses physics (that's what makes it flop), so it can't move along a path. Push it "
                      "with {o}:push(0, 4, -6)."}
WEATHERS = ("rain", "snow", "none")
CORNERS = ("top right", "top left", "bottom left", "bottom right")
PATH_MODES = ("loop", "ping-pong")
# Inputs that are numbers, and the numbers that can't be right: (method, input position) -> (the lowest, whether the
# lowest itself is fine, the highest, what it needs, an example, and a number below the lowest that's fine too), like
# Checker.PHYSICS_NUMBERS. The same as tgame's own limits, so what passes runs.
KIT_NUMBERS = {
    ("slow_mo", 0): (0.05, True, 1, "a speed from 0.05 to 1 (0.3 is 30% of the speed, 1 is normal again)", "{o}:slow_mo(0.3, 2)"),
    ("slow_mo", 1): (0, True, None, "how many seconds it lasts, 0 or more", "{o}:slow_mo(0.3, 2)"),
    ("shake", 0): (0, True, 2, "a number from 0 to 2 (1 is a good shake)", "{o}:shake(0.5)"),
    ("shake", 1): (0, False, None, "how long it shakes, in seconds (more than 0)", "{o}:shake(1, 1.5)"),
    ("weather", 1): (0, True, 2, "a strength from 0 to 2 after the kind (1 is normal)", '{o}:weather("snow", 1.5)'),
    ("day_cycle", 0): (2, True, None, "how many seconds a whole day takes, 2 or more (0 stops it)", "{o}:day_cycle(120)", 0),
    ("time_of_day", 0): (0, True, 24, "an hour from 0 to 24 (18 is 6 pm)", "{o}:time_of_day(18)"),
    ("health_bar", 0): (0, False, None, "a number above 0: the most health it can have", "{o}:health_bar(100)"),
    ("jump_pad", 3): (0, False, None, "how hard it launches things, a number above 0", "{o}:jump_pad(0, 0, 5, 15)"),
    ("boost_pad", 3): (0, False, None, "how hard it boosts, a number above 0", "{o}:boost_pad(0, 0, 10, 20)"),
    ("zoom", 0): (0, False, None, "a number above 0 (2 shows twice as close)", "{o}:zoom(2)"),
    ("minimap", 0): (60, True, 600, "its size in pixels first, from 60 to 600 (180 is normal)", "map = {o}:minimap(180)"),
}
# pop_text's size, its last input (the 6th in 3D, the 5th in 2D): how tall the text is on screen, in pixels.
POP_SIZE = {"world": (0, False, None, "a size above 0: how tall the text is on screen, in pixels (34 is normal)",
                      '{o}:pop_text("+10", 0, 2, 0, "gold", 40)'),
            "game": (0, False, None, "a size above 0: how tall the text is on screen, in pixels (32 is normal)",
                     '{o}:pop_text("+10", 400, 300, "gold", 40)')}
# Inputs written as text that the checker checks itself: (method, input position) -> what it is (pop_text's color
# is the 4th input in 2D and the 5th in 3D, so Checker.check_kit_inputs finds it).
KIT_VALUES = {("weather", 0): "weather", ("minimap", 1): "corner", ("path", 2): "path", ("mark", 1): "color",
              ("door", 3): "color", ("needs", 0): "key"}
_KIT_THING_HINTS = {"hp": "health", "get_health": "health", "life": "health", "damage": "hurt", "take_damage": "hurt",
                    "harm": "hurt", "dmg": "hurt", "lose_health": "hurt", "add_health": "heal", "restore": "heal",
                    "cure": "heal", "heal_up": "heal", "healthbar": "health_bar", "hp_bar": "health_bar",
                    "life_bar": "health_bar", "show_health": "health_bar", "max_health": "health_bar",
                    "set_health": "health_bar", "on_die": "on_death", "on_dead": "on_death", "when_dead": "on_death",
                    "died": "on_death", "on_killed": "on_death", "on_zero": "on_death"}
_KIT_TALKS_HINTS = {"speak": "say", "talk": "say", "bubble": "say", "speech": "say",
                    "speech_bubble": "say", "dialog": "say", "dialogue": "say", "on_speak": "on_talk",
                    "on_interact": "on_talk", "interact": "on_talk", "on_chat": "on_talk", "when_talked_to": "on_talk",
                    "talked": "on_talk", "waypoints": "path", "route": "path", "patrol": "path", "move_along": "path",
                    "follow_path": "path", "platform": "path", "moving_platform": "path"}
_KIT_OBJECT_HINTS = {**_KIT_THING_HINTS, **_KIT_TALKS_HINTS}
_KIT_GAME_HINTS = {"slowmo": "slow_mo", "slow_motion": "slow_mo", "slowdown": "slow_mo", "slow": "slow_mo",
                   "bullet_time": "slow_mo", "time_scale": "slow_mo", "timescale": "slow_mo", "screen_shake": "shake",
                   "camera_shake": "shake", "shake_screen": "shake", "shake_camera": "shake", "quake": "shake",
                   "floating_text": "pop_text", "float_text": "pop_text", "popup_text": "pop_text", "damage_text": "pop_text",
                   "text_popup": "pop_text", "poptext": "pop_text", "timer": "countdown", "count_down": "countdown",
                   "countdown_timer": "countdown", "time_limit": "countdown", "clock": "countdown"}
KIT_HINTS = {
    "game": _KIT_GAME_HINTS,
    "world": {**_KIT_GAME_HINTS, "rain": "weather", "snow": "weather", "set_weather": "weather", "climate": "weather",
              "day_night": "day_cycle", "day_night_cycle": "day_cycle", "daynight": "day_cycle", "time_cycle": "day_cycle",
              "set_time": "time_of_day", "hour": "time_of_day", "time_of_the_day": "time_of_day", "waypoint": "arrow_to",
              "compass": "arrow_to", "pointer": "arrow_to", "arrow": "arrow_to", "point_to": "arrow_to",
              "objective": "arrow_to", "marker": "arrow_to", "map": "minimap", "mini_map": "minimap", "radar": "minimap",
              "gate": "door", "doorway": "door", "add_door": "door", "make_door": "door", "jumppad": "jump_pad",
              "bounce_pad": "jump_pad", "launch_pad": "jump_pad", "launchpad": "jump_pad", "trampoline": "jump_pad",
              "spring": "jump_pad", "booster": "boost_pad", "speed_pad": "boost_pad", "boostpad": "boost_pad",
              "dash_pad": "boost_pad", "speed_boost": "boost_pad", "boost": "boost_pad"},
    "sprite": _KIT_THING_HINTS,
    "object": _KIT_OBJECT_HINTS,
    "car": _KIT_OBJECT_HINTS,
    "ragdoll": _KIT_OBJECT_HINTS,
    "player": {"grab": "can_grab", "can_pick_up": "can_grab", "pick_up": "can_grab", "pickup": "can_grab",
               "grabbing": "can_grab", "enable_grab": "can_grab", "carry": "can_grab", "can_carry": "can_grab",
               "held": "holding", "held_item": "holding", "is_holding": "holding", "carrying": "holding", "grabbed": "holding"},
    "countdown": {"time_left": "left", "remaining": "left", "seconds": "left", "seconds_left": "left", "get": "left",
                  "value": "left", "pause": "stop", "cancel": "stop", "end": "stop", "add_time": "add", "extend": "add",
                  "more": "add", "plus": "add"},
    "arrow": {"off": "hide", "on": "show", "remove": "hide"},
    "minimap": {"add": "mark", "track": "mark", "dot": "mark", "marker": "mark", "add_marker": "mark", "pin": "mark",
                "remove": "unmark", "untrack": "unmark", "remove_marker": "unmark", "scale": "zoom", "zoom_in": "zoom"},
    "door": {**_KIT_TALKS_HINTS, "shut": "close", "unlock_with": "needs", "requires": "needs", "require": "needs",
             "need": "needs", "needs_key": "needs", "key": "needs", "locked_by": "needs", "set_key": "needs"},
}
VALUE_HINTS["weather"] = {
    "raining": "rain", "rainy": "rain", "storm": "rain", "stormy": "rain", "drizzle": "rain", "showers": "rain",
    "thunder": "rain", "wet": "rain", "snowing": "snow", "snowy": "snow", "blizzard": "snow", "snowfall": "snow",
    "winter": "snow", "flakes": "snow", "clear": "none", "sunny": "none", "sun": "none", "dry": "none", "off": "none",
    "stop": "none", "nothing": "none", "no": "none", "normal": "none", "fine": "none"}
VALUE_HINTS["corner"] = {k: v for k, v in ANCHOR_HINTS.items() if v in CORNERS}
VALUE_HINTS["path"] = {"round": "loop", "around": "loop", "go round": "loop", "circle": "loop", "repeat": "loop",
                       "cycle": "loop", "forever": "loop", "loops": "loop", "looping": "loop", "looped": "loop"}
PATH_SAYS = {"ping-pong": "there and back, the default"}


def kit_input(*inputs):  # stands in for a kit method tgame's tables leave out: Checker.check_physics_inputs counts
    return None


def with_gamekit(tg, lib):
    """tgame's tables with the game kit filled in where they leave it out: the effects, the HUD, interaction and the
    level pieces (game:slow_mo, world:weather, enemy:health_bar, game:countdown, world:minimap, player:can_grab,
    npc:say, world:door, world:jump_pad, lift:path...), what the countdown, the arrow, the minimap and a door have
    (under the names tgame gives them, once it makes them itself), what they give back, the functions they run, the
    guessed names, and the weathers, corners and path modes (tgame's own when it has them). "key" is a kit model
    from 1.2.0, so world:spawn("key") is fine before tgame lists it. Whatever tgame's own tables say wins."""
    own_kinds, own_gives = tg["kinds"], tg["gives"]
    kinds, gives, handlers, hints = dict(own_kinds), dict(own_gives), dict(tg["handlers"]), dict(tg["hints"])
    made = {k: k for k in ("countdown", "arrow", "minimap", "door")}  # the kit's own kinds, by the names tgame gives them
    for owner in ("game", "world"):
        for maker, kind in KIT_MAKES.items():
            theirs = own_gives.get(owner, {}).get(maker)
            if maker in KIT_INPUTS[owner] and kind in made and theirs and not theirs.startswith("$"):
                made[kind] = theirs
            if maker in KIT_INPUTS[owner]:
                gives[owner] = {maker: made.get(kind, kind), **gives.get(owner, {})}
    inputs = {}
    for name, table in KIT_INPUTS.items():
        kind = made.get(name, name)
        inputs[kind] = table
        base = own_kinds.get(kind) or (own_kinds["object"] if name == "door" else {})
        kinds[kind] = {**dict.fromkeys(table, kit_input), **base, **kinds.get(kind, {})}
        mine = {m: KIT_GIVES.get(m, kind) for m in table}
        if name == "door" and kind not in own_gives:  # a door is an object: its methods give back the door
            mine = {**{m: (kind if v == "object" else v) for m, v in own_gives.get("object", {}).items()}, **mine}
        gives[kind] = {**mine, **gives.get(kind, {})}
        handlers[kind] = {**{m: KIT_HANDLERS[m] for m in table if m in KIT_HANDLERS}, **handlers.get(kind, {})}
        hints[kind] = {**KIT_HINTS.get(name, {}), **hints.get(kind, {})}
    own_check, kit = tg["check"], tuple(getattr(lib, "KIT", ()))

    def check(kind, method, index, value, base_dir=None):
        if (kind, method, index) == ("world", "spawn", 0) and str(value).strip().lower() == "key" and "key" not in kit:
            return None
        return own_check(kind, method, index, value, base_dir)

    return {**tg, "kinds": kinds, "gives": gives, "handlers": handlers, "hints": hints, "check": check, "kit_inputs": inputs,
            "kit_kinds": tuple(made.values()),
            "weathers": tuple(getattr(lib, "WEATHERS", WEATHERS)), "corners": tuple(getattr(lib, "CORNERS", CORNERS)),
            "path_modes": tuple(getattr(lib, "PATH_MODES", PATH_MODES)),
            # the values tgame checks itself, with the other ways it understands them ("rainy", "around"...)
            "own_values": tuple(w for w, f in (("weather", "WEATHER_WORDS"), ("corner", "corner_name"), ("path", "path_mode"))
                                if hasattr(lib, f))}


def tdraw_pen_methods():
    """A tdraw pen's :methods, for the checker (None without tkinter)."""
    try:
        import tuff_tdraw
    except ImportError:
        return None
    return tuff_tdraw.PEN_METHODS


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
        self.kind = None  # an action's scope: the name of its kind (my is that kind's object)

    def chain(self):
        s = self
        while s is not None:
            yield s
            s = s.parent


# Methods that other languages have, with the Tuff way to do it, for "nothing in Tuff has :x".
PY_ONLY = {
    "format": "Join text with +, like \"Hi \" + name. For decimals, text(x, 2) gives \"3.14\".",
    "startswith": "Text has :starts, like t:starts(\"a\").",
    "endswith": "Text has :ends, like t:ends(\"a\").",
    "index": "Text and lists have :find, which gives the position (or -1).",
    "items": "Loop over a dictionary's keys: for key in ages: then ages[key].",
    "extend": "Join lists with +, like items = items + more.",
    "isdigit": "Use the is_number pattern from the guide.",
    "capitalize": "Use t[0]:upper() + t[1:] (a part from position 1 to the end).",
    "substring": "Take a part with [ ], like t[0:4] (positions 0 to 4, both included).",
    "substr": "Take a part with [ ], like t[0:4] (positions 0 to 4, both included).",
    "slice": "Take a part with [ ], like items[1:3] (positions 1 to 3, both included).",
}

# tgame's sprite-sheet animation (1.5.0): the sprite methods Checker.check_flipbook looks at.
FLIP_METHODS = ("frames", "frame", "animation", "play")


class OwnFile:
    """What the checker knows about one of the program's own files (import money, 1.5.0), read but never run: the
    names its top level makes, its functions and their inputs, and the imports it always runs first. Each file is
    checked on its own, so its other mistakes are for its own check."""

    VALUE_KINDS = ("$text", "$number", "$list", "$dict", "$bool")

    def __init__(self, path):
        self.path = path
        self.error = None  # a mistake that stops it before it runs (it can't be read, or a syntax mistake): a TuffError
        self.names = self.funcs = None  # None: not known
        self.first = []  # the names it imports before anything else can happen (only imports, functions and plain values above them)
        try:
            program = Parser(tokenize(source_text(path))).program()
        except TuffError as err:
            self.error = err
            return
        except (OSError, UnicodeDecodeError) as exc:
            self.error = TuffError(unreadable(path, exc, os.path.basename(path)))
            return
        self.checker = c = Checker(program)
        c.collect(program, c.top)
        c.user = c.everywhere | set(c.func_count)
        self.names = c.top.names | set(c.funcs)
        self.funcs = {name: params for name, params in c.funcs.items() if c.only_func(name)}  # certainly functions
        for s in program:
            if s.kind == "import":
                self.first.append(s.name)
            elif s.kind not in ("func", "assign", "expr") or any(n.kind in ("call", "method", "input") for n in nodes(s)):
                break

    def value_kind(self, name):
        """What its top-level value called name is ("$number"...), when that's certain and plain."""
        kind = self.checker.var_kind(name, frozenset())
        return kind if kind in self.VALUE_KINDS else None


class Checker:
    """Finds mistakes without running the program. It only reports what is certain to go wrong
    when that line runs, so correct code is never flagged. It knows which names each function
    makes for itself, what kind of value most names hold, and every window and widget method."""

    CONTAINERS = ("window", "row", "card", "page")
    TYPE = {"$text": "text", "$list": "a list", "$line": "a line", "$number": "a number", "$bool": "true/false",
            "$nil": "nil", "$func": "a function", "$builtin": "a function", "$dict": "a dictionary"}
    NUMBER_FNS = {"number", "num", "int", "len", "random", "round", "sqrt", "abs", "floor", "ceil", "min", "max", "sum", "average",
                  "time", "sin", "cos", "tan", "log"}
    NUMBER_INPUT_FNS = {"round", "floor", "ceil", "abs", "sqrt", "min", "max", "sum", "average"}  # these fail on text
    MATHS = ("+", "-", "*", "/", "%", "^")
    COMPARE = ("==", "!=", "<", ">", "<=", ">=")
    ORDER = ("<", ">", "<=", ">=")
    ZERO_INPUT = {"upper", "lower", "trim", "pop", "clear", "text", "keys", "values", "reverse", "size"}  # list/text/line/dictionary methods without inputs
    TEXT_VALUE = {"input", "heading", "text", "small", "button", "dropdown", "clock"}  # :value() gives text
    # What each event hands its function, and where the function goes in the call. A function may
    # take fewer inputs than it's given (extras are dropped), not more.
    EVENT_GIVES = {"click": (0, "a button click"), "button": (0, "a button click"), "opened": (0, ":opened"),
                   "every": (0, ":every"), "after": (0, ":after"), "change": (1, ":change"), "enter": (1, ":enter")}
    HANDLER_POS = {"click": 0, "opened": 0, "change": 0, "enter": 0, "button": 1, "every": 1, "after": 1,
                   "every_frame": 0, "on_key": 1, "clicked": 0, "game_over": 1, "on_hit": 0}
    TGAME_KINDS = ("game", "world", "sprite", "object", "player", "hud", "group", "terrain", "car", "ragdoll", "countdown",
                   "arrow", "minimap", "door")  # what tgame makes (and the game kit's, by tgame's names: is_tgame)
    # tgame inputs written as text that the checker checks itself: (kind, method, input position) -> what it is.
    LAND_VALUES = {("world", "terrain", 1): "style", ("terrain", "style", 0): "style", ("world", "lighting", 0): "lighting",
                   **{(k, "physics", 0): "physics" for k in ("object", "sprite", "car", "ragdoll")}, ("object", "animate", 0): "animation"}
    # Physics inputs that are numbers, and the numbers that can't be right: method -> (the lowest, whether the lowest
    # itself is fine, the highest, what it needs, an example).
    PHYSICS_NUMBERS = {"mass": (0, False, None, "a number above 0", "{o}:mass(2)"),
                       "weight": (0, False, None, "a number above 0 (kg)", "{o}:weight(50)"),
                       "bounce": (0, True, 1, "a number from 0 (no bounce) to 1 (it bounces right back up)", "{o}:bounce(0.6)"),
                       "friction": (0, True, None, "a number from 0 (slippery, like ice) up", "{o}:friction(0.4)")}
    # What tap's functions make (tap.data() is an empty dictionary), and what a response's methods give back (left
    # out: it depends, like :json, which can be a dictionary, a list, text...).
    TAP_MAKES = {"get": "response", "post": "response", "put": "response", "delete": "response", "data": "$dict"}
    TAP_GIVES = {"response": {"status": "$number", "ok": "$bool", "text": "$text"}}

    def __init__(self, program, base_dir=None, path=None, folder=None):
        self.program = program
        # 1.5.0: the file being checked (where it is, or will be: TuffCode checks a copy of the editor's text), and the
        # folder its imports come from, or None when that isn't known. Then its own files aren't checked.
        self.path, self.folder = path, folder
        self.own_files = {}  # full path -> OwnFile
        self.own_by_name = {}  # an imported name -> its OwnFile, or None
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
        self.sums = {}  # id(binop node): its value, for sums of numbers written in the program (see number_sum)
        self.held = []  # the kinds of the starts of names[order:pop] being checked (see as_method)
        self.anims = None
        self.calls = {}  # name -> every line it's called on, like name(...)
        self.top = Scope()
        self.scope_of = {}  # id(func node) -> its Scope
        self.everywhere = set()  # every name made anywhere
        self.makes_window = self.makes_game = False
        self.handlers_seen = set()
        self.statement_call = None  # a call on a line of its own: its answer isn't used
        self.trying = 0  # inside how many try: blocks (a wrong key there may be on purpose: catch gets its message)
        self.base_dir = base_dir
        self.flip_names = None  # the animations the program's sprites make (run() fills it in: animation_names)
        self.kinds = {}  # the program's kinds (1.5.0): name -> its kind node, with its fields and actions

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
            elif k == "try":
                self.collect(s.body, scope, False)
                if s.name:  # catch problem: the error's message
                    self.loop_vars.add(s.name)
                    scope.names.add(s.name)
                    self.everywhere.add(s.name)
                self.collect(s.handler, scope, False)
            elif k == "if":
                for _, b in s.branches:
                    self.collect(b, scope, False)
                if s.else_body:
                    self.collect(s.else_body, scope, False)
            elif k == "import":
                scope.names.add(s.name)
                self.everywhere.add(s.name)
                self.imports.add(s.name)
            elif k == "kind":  # kind Pet: (1.5.0): its name is the program's, and each action is like a function with my
                scope.names.add(s.name)
                self.everywhere.add(s.name)
                self.kinds[s.name] = s
                for f in s.actions:
                    inner = Scope(scope, f.name)
                    inner.names.update(f.params)
                    inner.names.add("my")
                    inner.kind = s.name
                    self.scope_of[id(f)] = inner
                    self.everywhere.update(f.params)
                    self.params.update(f.params)
                    self.collect(f.body, inner, False)

    def run(self):
        self.collect(self.program, self.top)
        self.user = self.everywhere | set(self.func_count)
        kinds = [self.kind(n) for n in nodes(self.program) if n.kind == "call" and n.fn.kind == "attr"]
        self.makes_window = "window" in kinds
        self.makes_game = "game" in kinds or "world" in kinds  # tgame: atgui widgets on its panels and screens
        self.flip_names = self.animation_names()  # the animations sprite:play can play (None: can't know them all)
        self.body(self.program, self.top, in_loop=False)
        self.check_top_level()
        self.check_one_terrain()
        seen, out = set(), []
        for p in sorted(self.problems):
            if p not in seen:
                seen.add(p)
                out.append(p)
        return out

    def problem(self, node, msg):
        self.problems.append((node.line, node.col, msg))

    def what(self, kind):
        if kind.startswith("%"):  # an object made from a kind (1.5.0), and the kind itself
            return an(kind[1:])
        if kind.startswith("$kind:"):
            return f"the kind {kind[6:]}"
        if kind.startswith("$module:"):
            return "a library"
        return "a function" if kind.startswith("$libfn:") else self.TYPE.get(kind) or a_kind(kind.lstrip("@"))

    def only_func(self, name):
        """True when name is one top-level function and never anything else."""
        return self.func_count.get(name) == 1 and name not in self.assigned and name not in self.params and name not in self.loop_vars

    # ---- kinds (1.5.0)
    def only_kind(self, name):
        """True when name is one of the program's kinds and never anything else, so name(...) makes that kind's object."""
        return name in self.kinds and name not in self.assigned and name not in self.params and name not in self.loop_vars \
            and name not in self.func_count

    def fields_of(self, kind):
        return [f.target.name for f in self.kinds[kind].fields]

    def actions_of(self, kind):
        """{action's name: its inputs}"""
        return {f.action: f.params for f in self.kinds[kind].actions}

    def own_files(self):
        """Does the program import files of its own? (Their kinds can have any fields and actions.)"""
        return any(name not in LIBRARIES and name != "file" for name in self.imports)

    def is_field(self, name):
        """Could thing.name be an object's field? (One of the program's kinds has it, or it can't be told.)"""
        return self.own_files() or any(name in self.fields_of(k) for k in self.kinds)

    def brackets_tip(self, obj, target, index, then):
        """The tip after "Can't use [ ] on a Pet." (as Interpreter.item and store give it), or "" for a kind itself."""
        if not obj.startswith("%"):
            return ""
        key = index.value if index.kind == "const" else None
        return f" {object_brackets(obj[1:], self.fields_of(obj[1:]), where_text(target), key, then)}" + ("" if then else ".")

    def object_side(self, a, b):
        """Is one side of a sum certainly an object (or a kind), and the other certainly a value the run can name the
        same way (a number, text, a list...)?"""
        sure = lambda x: x in ("$number", "$text", "$list", "$dict", "$bool", "$nil") or (x or "").startswith(("%", "$kind:"))
        return any((x or "").startswith(("%", "$kind:")) for x in (a, b)) and sure(a) and sure(b)

    def field_hint(self, name):
        """' Did you mean 'hunger'?' with the closest field any of the program's kinds has, or ''."""
        hint = difflib.get_close_matches(name, sorted({f for k in self.kinds for f in self.fields_of(k)}), n=1, cutoff=0.6)
        return f" Did you mean '{hint[0]}'?" if hint else ""

    def check_kind_attr(self, e, obj, store=None):
        """rex.hunger where rex is certainly a Pet ("%Pet"), or Pet.name on the kind itself ("$kind:Pet"). store: the
        line, when e is what it stores into (rex.hunger = 3)."""
        if obj.startswith("$kind:"):
            self.problem(store or e, kind_not_object(obj[6:], f".{e.name}" + (" = ..." if store else "")))
            return
        kind = obj[1:]
        fields = self.fields_of(kind)
        if e.name not in fields:
            self.problem(store or e, field_help(kind, fields, self.actions_of(kind), e.name, where_text(e.obj)))

    def check_field_store(self, s):
        """rex.hunger = 3: rex is an object that has that field. Text, lists, dictionaries, libraries and the rest have
        no fields to set (as set_field says)."""
        t = s.target
        obj = self.kind(t.obj)
        if obj is None:
            return
        if obj.startswith(("%", "$kind:")):
            self.check_kind_attr(t, obj, store=s)
        elif obj in self.TYPE or obj.startswith(("$module:", "$libfn:")):
            tip = f" A dictionary's values are set with [ ], like {where_text(t.obj) or 'd'}[\"{t.name}\"] = ..." if obj == "$dict" else ""
            self.problem(s, f"Only objects made from a kind have fields to set with '.', and this is {self.what(obj)}.{tip}")

    def check_action(self, e, obj):
        """rex:feed() where rex is certainly a Pet: an action Pet has, with as many inputs as it takes."""
        if obj.startswith("$kind:"):
            self.problem(e, kind_not_object(obj[6:], f":{e.name}()"))
            return
        kind = obj[1:]
        actions = self.actions_of(kind)
        if e.name not in actions:
            self.problem(e, action_help(kind, self.fields_of(kind), actions, e.name, where_text(e.obj)))
        elif len(e.args) != len(actions[e.name]):
            self.problem(e, action_inputs_help(where_text(e.obj) or kind, e.name, len(actions[e.name]), len(e.args), e.bare))

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
        if name == "my" and self.kinds:
            return None  # in an action, my is its object (kind reads the node's of_kind); elsewhere, can't be sure
        kinds = set()
        if name in self.imports:
            kinds.add("$module:" + name)
        if name in self.func_count:
            kinds.add("$func")
        if name in self.kinds:
            kinds.add("$kind:" + name)
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
            b = self.builtins[name]
            kinds.add("$builtin" if isinstance(b, Builtin) else "$number" if name == "pi" else f"$module:{name}" if isinstance(b, Module) else None)
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
        if k == "dict":
            return "$dict"
        if k == "fstr":
            return "$text"
        if k == "held":  # the start of names[order:pop] (see Parser.index)
            return self.held[-1] if self.held else self.kind(e.of, seen)
        if k == "slice":  # a part of text is text, a part of a list a list
            if self.as_method(e) is not False:  # names[order:pop]: an item of names (or can't tell yet)
                return None
            obj = self.kind(e.obj, seen)
            return obj if obj in ("$text", "$list") else None
        if k == "say":
            return "$line"
        if k == "sayfn":
            return "$builtin"
        if k == "input":
            return "$text"
        if k == "var" and getattr(e, "of_kind", None):  # an action's my: its kind's object (1.5.0)
            return "%" + e.of_kind
        if k == "var":
            return self.var_kind(e.name, seen)
        if k == "call" and e.fn.kind == "var" and self.only_kind(e.fn.name):  # Pet("Rex"): a Pet
            return "%" + e.fn.name
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
            own = self.own_file(lib[8:]) if lib and lib.startswith("$module:") else None
            if own is not None and own.names is not None and e.name not in own.funcs:  # money.rate: a value in money.tuf
                return own.value_kind(e.name) if e.name in own.names else None
            return f"$libfn:{lib[8:]}.{e.name}" if lib and lib.startswith("$module:") else None
        if k == "call" and e.fn.kind == "var" and e.fn.name not in self.user:
            name = e.fn.name
            return "$text" if name in ("text", "str", "now", "today") else "$list" if name == "range" else "$dict" if name == "date"                 else "$number" if name in self.NUMBER_FNS else None
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
            if lib == "$module:tdraw":
                return "tdpen" if e.fn.name == "pen" else None
            return None
        if k == "method":
            if self.is_print(e.obj):  # say:ascii(...) and say:color(...) say a line, like say does
                return "$line" if e.name in ("ascii", "color", "colour") else None
            obj = self.kind(e.obj, seen)
            if obj and obj.startswith("@"):
                return self.atgui_kind(obj[1:], e)
            if obj in self.TAP_GIVES:
                return self.TAP_GIVES[obj].get(e.name)
            if self.is_tgame(obj):
                tg = tgame_tables()
                return tg["gives"].get(obj, {}).get(e.name) if tg else None
            gui = gui_tables()
            if obj in self.CONTAINERS and gui and e.name in gui["kinds"] and e.name != "window" and (e.name != "page" or obj == "window"):
                return e.name
            if obj == "$text":
                return "$bool" if e.name in ("has", "starts", "ends") else "$text" if e.name in ("upper", "lower", "trim", "replace", "pad_left", "pad_right")                     else "$list" if e.name == "split" else "$number" if e.name in ("find", "count") else None
            if obj == "$list":
                return "$list" if e.name in ("add", "remove", "sort", "reverse") else "$bool" if e.name == "has" else "$text" if e.name == "join"                     else "$number" if e.name == "find" else None
            if obj == "$dict":
                return "$bool" if e.name == "has" else "$list" if e.name in ("keys", "values") else "$dict" if e.name in ("set", "remove") \
                    else "$number" if e.name == "size" else None
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
        elif k == "kind":  # its fields' starting values (worked out at the top, for each new object) and its actions
            for f in s.fields:
                self.expr(f.value, self.top)
            for f in s.actions:
                self.body(f.body, self.scope_of[id(f)], False, True)
        elif k == "import":
            self.check_import(s)
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
                self.check_store(s, s.target.obj, s.target.index)
            elif s.target.kind == "slice":  # board[moves:pop] = "X": like the read form, then stored into
                self.check_slice(s.target, scope, store=s)
            elif s.target.kind == "attr":  # rex.hunger = 3, my.hunger -= 1 (1.5.0)
                self.expr(s.target.obj, scope)
                self.check_field_store(s)
            if s.op == "=" and target in self.func_count and target not in self.params and target not in self.loop_vars \
                    and self.kind(s.value) not in ("$func", "$builtin"):
                self.problem(s, f"{target} is a function, and giving it a value replaces it, so {target}() won't work afterwards. Use another name for the value.")
            elif s.op == "=" and target in self.kinds and target not in self.params and target not in self.loop_vars \
                    and s.line > self.kinds[target].line and not (self.kind(s.value) or "").startswith("$kind:") \
                    and any(x.kind == "call" and x.fn.kind == "var" and x.fn.name == target and x.line > s.line for x in nodes(self.program)):
                self.problem(s, f"{target} is a kind, and giving it a value replaces it, so {target}(...) won't make new objects "
                                "afterwards. Use another name for the value.")
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
        elif k == "try":
            self.trying += 1
            self.body(s.body, scope, in_loop, in_func)
            self.trying -= 1
            self.body(s.handler, scope, in_loop, in_func)
        elif k == "for":
            self.expr(s.items, scope)
            if self.kind(s.items) == "$number":
                self.problem(s, f"Can't loop over a number. Try: for {s.name} in range(...):")
            elif (self.kind(s.items) or "").startswith(("%", "$kind:")):  # for x in rex: (1.5.0)
                self.problem(s, f"Can't loop over {self.what(self.kind(s.items))}.")
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
            for a in getattr(e, "looks", None) or []:  # input:color("Name? ", "green"): the words written in quotes
                self.expr(a, scope)
                if a.kind == "const" and isinstance(a.value, str):
                    try:
                        read_look("input:color", [a.value], pen=True)
                    except TuffError as err:
                        self.problem(a, err.msg)
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
        elif k == "dict":
            for x in e.keys + e.values:
                self.expr(x, scope)
            for key in e.keys:
                self.check_key(key)
        elif k == "slice":
            self.check_slice(e, scope)
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
        elif k == "fstr":  # f"{name} has {score} points": the code in each { }, and its format (1.5.0)
            for part in e.parts:
                if not isinstance(part, str):
                    self.expr(part.value, scope)
                    self.check_format(part)
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
        kind = next((s.kind for s in scope.chain() if s.kind), None)  # inside an action: hunger for my.hunger (1.5.0)
        msg = own_field_help(name, kind, self.fields_of(kind) if kind else ())
        if msg:
            self.problem(e, msg)
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

    # ---- the program's own files (1.5.0): import money
    def own_file(self, name):
        """The OwnFile for name when it's one of the program's own files this file can import, else None (a library,
        no such file, or a folder that isn't known)."""
        if name in LIBRARIES or name == "file" or not self.folder:
            return None
        if name not in self.own_by_name:  # (kind() asks often: the folder is read once for each name)
            path = module_file(self.folder, name)
            self.own_by_name[name] = self.read_own(path) if path else None
        return self.own_by_name[name]

    def read_own(self, path):
        path = os.path.abspath(path)
        if path not in self.own_files:
            self.own_files[path] = OwnFile(path)
        return self.own_files[path]

    def own_name(self, path):
        """A file's name as messages show it: from this file's folder, like libs/money.tuf."""
        rel = os.path.relpath(path, self.folder) if self.folder else os.path.basename(path)
        return os.path.basename(path) if rel.startswith("..") else rel.replace(os.sep, "/")

    def check_import(self, s):
        """import money: there's a money.tuf to load (next to this file or in libs), it reads, and it doesn't come back
        here in a circle. A library's name always loads the library, even with a file of that name here."""
        name, me = s.name, os.path.normcase(os.path.abspath(self.path)) if self.path else None
        if self.trying:  # try: import extras, catch: ...: a file that may not be there, on purpose
            return
        if name in LIBRARIES or name == "file":
            found = module_file(self.folder, name) if self.folder else None
            if found and os.path.normcase(os.path.abspath(found)) != me:
                lib = "file library" if name == "file" else "library"
                self.problem(s, f"There's a file {self.own_name(found)} here, but {name} is Tuff's own {lib}, so {s.word} {name} "
                                f"loads the library, not your file. To use your file, give it another name, like my_{name}.tuf.")
            return
        who = os.path.basename(self.path) if self.path else "this file"
        problem = import_problem(name, self.folder, who, (os.path.basename(self.path or "")[:-4],))
        if problem or not self.folder:  # (with the folder unknown, only a built-in's name is certain)
            if problem and (self.folder or name in BUILTIN_NAMES or name in OWN_NAME_BUILTINS or name in ("err", "pi", "all")):
                self.problem(s, problem)
            return
        own = self.own_file(name)
        if own.error is not None:
            where = f" on line {own.error.line}" if own.error.line else ""
            self.problem(s, f"{self.own_name(own.path)} has a mistake{where}, so {s.word} {name} stops the program there: {own.error.msg}")
            return
        chain = self.circle(name, [(me, who)], self.folder)
        if chain:
            self.problem(s, circle_problem(chain))

    def circle(self, name, trail, folder):
        """Importing name from folder, with trail the files on the way here ((key, shown) each, this file first): the
        files of a circle of imports it starts, from the first file in it back to that file, or None. Only the imports
        each file always runs first count (see OwnFile.first)."""
        if name in LIBRARIES or name == "file" or len(trail) > 30:
            return None
        path = module_file(folder, name)
        if not path:
            return None
        key, shown = os.path.normcase(os.path.abspath(path)), self.own_name(path)
        for i, (k, _) in enumerate(trail):
            if k == key:
                return [s for _, s in trail[i:]] + [shown]
        own = self.read_own(path)
        for more in own.first:
            chain = self.circle(more, trail + [(key, shown)], os.path.dirname(os.path.abspath(path)))
            if chain:
                return chain
        return None

    def lib_members(self, lib):
        if lib == "anims":
            if self.anims is None:
                self.anims = {n: b.fn for n, b in self.interp.lib_anims().items()}
            return self.anims
        if lib == "file":  # the built-in file library (1.4.0)
            return {n: b.fn for n, b in self.builtins["file"].members.items()} if isinstance(self.builtins.get("file"), Module) else None
        if lib == "tdraw":  # its functions open nothing until they're called
            if getattr(self, "tdraw", None) is None:
                try:
                    self.tdraw = {n: b.fn for n, b in self.interp.lib_tdraw().items()}
                except TuffError:
                    return None
            return self.tdraw
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
        inputs = {f.name: set(f.params) for f in nodes(self.program) if f.kind == "func"}
        for x in nodes(self.program):
            if x.kind == "call" and x.fn.kind == "var" and x.fn.name not in inputs.get(owner.get(id(x)), ()):
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

        def replaces_by_loop(s):
            """s, a for loop at the top, gives each item in turn to a built-in's name (file, time, log...), so from then
            on that name is the item, everywhere: file.read and time() fail inside the loop (when it has items), and
            after it too when it certainly has some. Only when nothing else gives the name a value and no item is a
            function or a library."""
            name, b = s.name, self.builtins.get(s.name)
            if not isinstance(b, Builtin) and not (name == "file" and isinstance(b, Module)):
                return
            if name in self.assigned or sum(1 for x in nodes(self.program) if x.kind in ("for", "func", "try", "import") and x.name == name) != 1:
                return
            kinds, some = self.loop_items(s.items)
            if some is False or kinds is None or any(k is None or k in ("$func", "$builtin") or k.startswith(("$libfn:", "$module:")) for k in kinds):
                return
            if name == "file":
                used = [x for x in nodes(self.program) if x.kind == "attr" and x.obj.kind == "var" and x.obj.name == "file"
                        and "file" not in inputs.get(owner.get(id(x)), ())]
            else:
                used = calls.get(name, [])
            inside = {id(x) for x in nodes(s.body)}
            line = later(used, s.line) if some else min((x.line for x in used if id(x) in inside and id(x) not in owner), default=None)
            if line is None:
                return
            if name == "file":
                member = next(x.name for x in used if x.line == line)
                self.problem(s, f"'file' is the built-in file library, and this loop gives it each item in turn, which replaces it everywhere, so file.{member} on line {line} won't work. Use another name for the loop's variable, like my_file.")
            else:
                self.problem(s, f"'{name}' is a built-in function, and this loop gives it each item in turn, which replaces it everywhere, so {name}() on line {line} won't work. Use another name for the loop's variable, like my_{name}.")

        for s in self.program:
            if s.kind == "assign" and s.op == "=" and s.target.kind == "var" and isinstance(self.builtins.get(s.target.name), Builtin):
                replaces(s, s.target.name, s.line)
            elif s.kind == "assign" and s.op == "=" and s.target.kind == "var" and s.target.name == "err":
                replaces_err(s)
            elif s.kind == "for":
                replaces_by_loop(s)
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
                if s.name in self.kinds:  # (1.5.0)
                    self.problem(s, f"There's a kind called {s.name} on line {self.kinds[s.name].line}, and a function with the same "
                                    "name replaces it (or it replaces the function). Give them different names.")

    def loop_items(self, e, seen=frozenset()):
        """What a for loop over e gives its variable: the kinds of the items (None when that can't be told), and
        whether there are some (True or False, or None when that can't be told)."""
        if e.kind == "list":
            return {self.kind(x) for x in e.items}, bool(e.items)
        if e.kind == "dict":  # its keys
            return {self.kind(x) for x in e.keys}, bool(e.keys)
        if e.kind == "const" and isinstance(e.value, str):
            return {"$text"}, e.value != ""
        if e.kind == "call" and e.fn.kind == "var" and e.fn.name == "range" and "range" not in self.user:
            ends = [a.value for a in e.args if a.kind == "const" and isinstance(a.value, (int, float)) and not isinstance(a.value, bool)]
            some = None
            if len(ends) == len(e.args) and 1 <= len(ends) <= 3 and all(isinstance(x, int) or math.isfinite(x) for x in ends):  # like b_range, without the list
                a, b, step = [int(x) for x in ([1] + ends + [1] if len(ends) == 1 else ends + [1] * (3 - len(ends)))]
                some = step != 0 and bool(range(a, b + (1 if step > 0 else -1), step))
            return {"$number"}, some
        if e.kind == "call" and e.fn.kind == "attr" and e.fn.name == "lines" and e.fn.obj.kind == "var" and e.fn.obj.name == "file" \
                and "file" not in self.assigned and isinstance(self.builtins.get("file"), Module):
            return {"$text"}, None  # file.lines, worked out before the loop starts
        if self.kind(e) == "$text":  # its letters
            return {"$text"}, None
        if e.kind == "var" and e.name not in seen and e.name not in self.params and e.name not in self.loop_vars:
            sets = self.assigned.get(e.name, [])
            added = any((x.kind == "method" and x.name in ("add", "set") and x.obj.kind == "var" and x.obj.name == e.name)
                        or (x.kind == "assign" and x.target.kind != "var" and x.target.obj.kind == "var" and x.target.obj.name == e.name)
                        for x in nodes(self.program))
            found = [self.loop_items(t.value, seen | {e.name})[0] for t in sets if t.op == "="]
            if sets and not added and len(found) == len(sets) and None not in found:
                return set().union(*found), None
        return None, None

    def check_one_terrain(self):
        """A world has one terrain, so a second world:terrain for the same world at the top of the program fails
        when it runs (also when it starts a chain, like world:terrain(50):style "snow")."""
        made = {}  # the world's name -> the line that made its land, and the land's name
        for s in self.program:
            e = s.value if s.kind == "assign" else s.expr if s.kind == "expr" else None
            while e is not None and e.kind == "method" and e.name != "terrain":
                e = e.obj
            if e is None or e.kind != "method" or e.obj.kind != "var" or self.kind(e.obj) != "world":
                continue
            w = e.obj.name
            if len(self.assigned.get(w, [])) != 1 or w in self.params or w in self.loop_vars:
                continue  # it might be another world by now
            if w in made:
                line, land = made[w]
                self.problem(e, f"A world has one terrain, and line {line} already made it. Change it with {land}:hill, {land}:raise and so on.")
            else:
                named = s.kind == "assign" and s.value is e and s.target.kind == "var"
                made[w] = (s.line, s.target.name if named else "land")

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
        elif (op in self.MATHS or op in self.ORDER) and self.object_side(a, b) and not (op == "+" and "$text" in (a, b)):
            # rex + 1, rex < other (1.5.0): an object is never a number (only + with text works: it joins them)
            if op in self.ORDER:
                self.problem(e, f"Can't compare {self.what(a)} with {self.what(b)} using {op}.")
            else:
                verb = {"+": "add", "-": "subtract", "*": "multiply", "/": "divide", "%": "use % on", "^": "use ^ on"}[op]
                self.problem(e, f"Can't {verb} {self.what(a)} and {self.what(b)}.")
        elif op == "+" and a == "$list" and b == "$text":
            self.problem(e, "This turns the list into text. To add one item, use :add, or join two lists: items + [\"jam\"].")
        elif op == "+" and b == "$number" and e.left.kind == "binop" and e.left.op == "+" and self.kind(e.left) == "$text" \
                and self.kind(e.left.right) == "$number" and not (e.left.right.kind == "const" and e.right.kind == "const"):
            self.problem(e, "+ works left to right, and the text before has already turned the numbers into text, so they're stuck together (\"Total: \" + 10 + 2 gives \"Total: 102\"). Put the sum in brackets: \"Total: \" + (a + b), or use a text template: f\"Total: {a + b}\"")
        elif op == "+" and {a, b} == {"$text", "$number"} and typed is not None and self.describe(typed):
            self.problem(e, f"{self.describe(typed)} is typed text, so + sticks them together (\"5\" + 1 gives \"51\"). Use number({self.describe(typed)}) to add.")
        if op == "*" and "$text" in (a, b):
            n = e.right if a == "$text" else e.left
            if self.is_decimal(n):
                self.problem(n, "This is a decimal (it comes from /), even if it looks whole, so it can't repeat text. Use floor(...) around the division.")
        if op in self.MATHS and not self.trying:
            self.check_too_big(e)

    def check_too_big(self, e):
        """10 ^ 400 / 3: a sum of numbers written in the program whose answer is too big for a decimal (1.5.0). Only
        the part that goes too big is reported (in try:, it may be on purpose)."""
        try:
            if self.number_sum(e.left) is None or self.number_sum(e.right) is None:
                return
        except TuffError:
            return  # (a part of it is reported already)
        try:
            self.number_sum(e)
        except TuffError as err:
            if err.msg == TOO_BIG_NUMBER:
                self.problem(e, err.msg)

    def number_sum(self, e):
        """The value of a sum made only of numbers written in the program, like 2 ^ 10 * 1.5, worked out as the
        program would; None when it isn't one, or it's a whole number too long to work out quickly here. Raises the
        program's TuffError when it can't be worked out."""
        k = e.kind
        if k == "const":
            return e.value if e.value.__class__ in (int, float) else None
        if k == "neg":
            v = self.number_sum(e.value)
            return None if v is None else -v
        if k != "binop" or e.op not in self.MATHS:
            return None
        if id(e) in self.sums:
            return self.sums[id(e)]
        a = self.number_sum(e.left)
        b = None if a is None else self.number_sum(e.right)
        if b is None:
            return None
        if a.__class__ is int and b.__class__ is int and abs(a) > 1 and (
                (e.op == "^" and b * a.bit_length() > 1_000_000) or (e.op == "*" and a.bit_length() + b.bit_length() > 1_000_000)):
            value = None  # a whole number with hundreds of thousands of digits: fine, but slow to work out here
        else:
            value = self.interp.binop(e.op, a, b)
        self.sums[id(e)] = value
        return value

    def as_method(self, e):
        """For x[a:b] with a glued ':' (Parser.index): True when it's 1.3.6's method call (a is a list, text or a
        widget), False when it's a part, None when it can't be told before the program runs."""
        if getattr(e, "alt", None) is None:
            return False
        start = self.kind(e.recv)
        if start == "$number":
            return False
        if start is not None and start != "$bool":
            return True
        root = e.end
        while root.kind in ("call", "binop", "and", "or", "method", "index", "slice", "attr"):
            root = root.fn if root.kind == "call" else root.left if root.kind in ("binop", "and", "or") else root.obj
        # s[a:b] where b is one of the program's names (and not also a method's name): a part
        known = root.kind == "var" and (root.name in self.everywhere or root.name in self.func_count) and \
            not self.method_exists(root.name)
        return False if known and start is None else None

    def check_slice(self, e, scope, store=None):
        """x[a:b], read, or stored into (store: the line, like board[moves:pop] = "X"). With a glued ':' it's a
        part or 1.3.6's method call (as_method); when that can't be told yet, only what both get wrong is certain."""
        self.expr(e.obj, scope)
        if e.alt is None:
            self.expr(e.start, scope)
            self.expr(e.end, scope)
            self.check_part(e)
            return
        self.expr(e.recv, scope)
        method, recv = self.as_method(e), self.kind(e.recv)
        as_part = lambda: self.check_part(e) if store is None else None
        as_item = lambda: self.check_index(e, e.alt) if store is None else self.check_store(store, e.obj, e.alt)
        self.held.append(recv)
        try:
            simple = SIMPLE_METHODS.get(recv[1:]) if method and recv.startswith("$") else None
            if simple is not None and e.mname not in simple:  # word[first:last] with first some text
                self.problem(e, f"The positions in [start:end] must be whole numbers, not {self.TYPE.get(recv, 'that')}.")
            elif method:  # names[order:pop], as in 1.3.6: a method of what's before the ':' gives the position or key
                self.expr(e.alt, scope)
                as_item()
            elif method is False:
                self.expr(e.end, scope)
                if store is not None:
                    self.problem(store, "A part like [1:3] can't be changed with =. Make the new text or list with + instead.")
                as_part()
            else:
                self.both(lambda: (self.expr(e.end, scope), as_part()), lambda: (self.expr(e.alt, scope), as_item()))
        finally:
            self.held.pop()

    def both(self, *readings):
        """Checks each way something can be read when it runs (x[a:b] with a glued ':') and keeps only the problems
        all of them have: those go wrong whichever way it's read."""
        start, found = len(self.problems), []
        for read in readings:
            read()
            found.append(self.problems[start:])
            del self.problems[start:]
        self.problems += [p for p in found[0] if all(p in f for f in found[1:])]

    def check_store(self, s, target, index):
        """target[index] = value (s is the line): only lists and dictionaries have items that can be set."""
        obj = self.kind(target)
        if obj == "$text":
            self.problem(s, "You can only set items in a list, not in text. Build new text with + instead.")
        elif obj == "$dict":
            self.check_key(index)
        elif (obj or "").startswith(("%", "$kind:")):  # rex["name"] = "Rex" (1.5.0)
            self.problem(s, f"You can only set items in a list, not in {self.what(obj)}.{self.brackets_tip(obj, target, index, ' = ...')}")

    def check_key(self, key):
        """A dictionary's key is text or a number (dict_key), in { }, d[key] and d:get, :set, :has and :remove."""
        kk = self.kind(key)
        if (kk in ("$list", "$dict", "$bool", "$nil") or (kk or "").startswith(("%", "$kind:"))) and not self.trying:
            self.problem(key, f"A dictionary's keys can be text or numbers, not {self.what(kk)}.")

    def check_part(self, e):
        """s[a:b]: the positions are whole numbers, and only text and lists have parts."""
        obj = self.kind(e.obj)
        if obj in ("$dict", "$number", "$bool", "$nil", "$func", "$builtin") or (obj or "").startswith(("$module:", "%", "$kind:")):
            self.problem(e, f"Only text and lists have parts like [1:3], not {self.what(obj)}.")
            return
        for end in (e.start, e.end):
            if end is None:
                continue
            k = self.kind(end)
            if k in ("$text", "$list", "$dict", "$bool"):
                self.problem(end, f"The positions in [start:end] must be whole numbers, not {self.TYPE[k]}.")
                return
            if self.is_decimal(end):
                self.problem(end, "This is a decimal (it comes from /), even if it looks whole, so it can't be a position. Use floor(...) around the division.")
                return

    def check_index(self, e, index=None):
        """x[i], or 1.3.6's names[order:pop], where the method call gives i (index)."""
        index = e.index if index is None else index
        idx = self.kind(index)
        obj = self.kind(e.obj)
        if (obj or "").startswith(("%", "$kind:")):  # rex["name"]: an object's fields use a dot (1.5.0)
            self.problem(e, f"Can't use [ ] on {self.what(obj)}.{self.brackets_tip(obj, e.obj, index, '')}")
            return
        if idx == "$text" and self.kind(e.obj) in ("$list", "$text"):  # (a dictionary's keys are often text)
            who = self.describe(index)
            self.problem(e, "List positions must be whole numbers, not text." + (f" Use number({who})." if who and self.typed(index) else ""))
        elif self.kind(e.obj) == "$dict":  # (where a decimal is a fine key)
            self.check_key(index)
        elif self.is_decimal(index):
            self.problem(index, "This is a decimal (it comes from /), even if it looks whole, so it can't be a position. Use floor(...) around the division.")
        elif index.kind == "call" and index.fn.kind == "var" and index.fn.name == "random" and "random" not in self.user and e.obj.kind == "var":
            args = index.args
            ends_at_len = args and args[-1].kind == "call" and args[-1].fn.kind == "var" and args[-1].fn.name == "len" and len(args[-1].args) == 1 and \
                args[-1].args[0].kind == "var" and args[-1].args[0].name == e.obj.name
            if ends_at_len:
                lst = e.obj.name
                self.problem(index, f"random(...len({lst})) can give len({lst}), which is past the last position (positions go from 0 to len({lst}) - 1). Use {lst}[random(0, len({lst}) - 1)].")

    def method_exists(self, name):
        gui = gui_tables()
        if gui is None:
            return True
        if self.own_files() or any(name in self.actions_of(k) for k in self.kinds):  # an object's action (1.5.0)
            return True
        if name in (tdraw_pen_methods() or ()):
            return True
        at = atgui_tables()
        if at is not None and any(name in m for m in at["kinds"].values()):
            return True
        tap = tap_tables()
        tg = tgame_tables()
        return name in SIMPLE_METHODS["text"] or name in SIMPLE_METHODS["list"] or name in SIMPLE_METHODS["line"] or name in SIMPLE_METHODS["dict"] or \
            any(name in m for m in gui["kinds"].values()) or (tap is None or any(name in m for m in tap["kinds"].values())) or \
            (tg is None or any(name in m for m in tg["kinds"].values()))

    ANIMS_TEXTS = {"countdown": {1}}  # where each anims function takes text (others: the first input); see lib_anims

    def check_anims_looks(self, e):
        """anims.loading("Pulling info...", "green"): a word where text doesn't go is a look word (1.4.1)."""
        name, texts, looks = e.fn.name, self.ANIMS_TEXTS.get(e.fn.name, {0}), False
        for i, a in enumerate(e.args):
            looks = looks or (a.kind == "const" and isinstance(a.value, str) and i not in texts)
            if looks and a.kind == "const" and isinstance(a.value, str):
                try:
                    read_look(f"anims.{name}", [a.value], pen=True)
                except TuffError as err:
                    self.problem(a, err.msg)
                    return

    def check_call(self, e, scope):
        fn, n = e.fn, len(e.args)
        if fn.kind == "var":
            name = fn.name
            local = any(name in s.names for s in scope.chain() if s is not self.top)
            if name in self.kinds:  # Pet("Rex"): at most one input for each field (1.5.0)
                fields = self.fields_of(name)
                if self.only_kind(name) and not local and n > len(fields):
                    self.problem(e, kind_inputs_help(name, fields, n))
                return
            if self.only_func(name) and not local:
                want = len(self.funcs[name])
                if n != want:
                    self.problem(e, f"{name}() needs {want} input{'s' if want != 1 else ''}, but got {n}.")
                elif e is not self.statement_call:
                    self.check_gives_back(e, name)
            elif name not in self.user and isinstance(self.builtins.get(name), Builtin):
                if not accepts(self.builtins[name].fn, n):
                    self.problem(e, f"{name}() got the wrong number of inputs ({n}).")
                elif name == "random" and not 0 <= n <= 2:
                    self.problem(e, "random() needs a range, like random(1, 6), just the top, like random(6), or nothing for a decimal from 0 to 1.")
                elif name in self.NUMBER_INPUT_FNS:
                    for a in e.args:
                        if self.kind(a) == "$text":
                            who = self.describe(a)
                            tip = f" Use number({who})." if who and self.typed(a) else ""
                            self.problem(a, f"{name}() needs a number, not text.{tip}")
                            break
                elif name in ("number", "num", "int") and n == 1:
                    self.check_number_input(e.args[0], name)
                elif name == "len" and n == 1 and (self.kind(e.args[0]) or "").startswith(("%", "$kind:")):  # len(rex)
                    self.problem(e, f"len() needs text, a list or a dictionary, not {self.what(self.kind(e.args[0]))}.")
            elif name not in self.builtins and not local:
                kind = self.var_kind(name, frozenset())
                if kind and not kind.startswith(("$module:", "$libfn:", "$kind:")) and kind not in ("$func", "$builtin"):
                    self.problem(e, f"'{name}' is {self.what(kind)}, not a function, so it can't be called with ( ).")
        elif fn.kind == "attr":
            lib = self.kind(fn.obj)
            own = self.own_file(lib[8:]) if lib and lib.startswith("$module:") else None
            if own is not None:  # money.as_money(6.375) (1.5.0): one of the program's own files
                params = (own.funcs or {}).get(fn.name)
                value = own.names is not None and fn.name in own.names and params is None and own.value_kind(fn.name)
                if params is not None and len(params) != n:
                    want = len(params)
                    self.problem(e, f"{lib[8:]}.{fn.name}() needs {want} input{'s' if want != 1 else ''}, but got {n}.")
                elif value:
                    self.problem(e, f"{lib[8:]}.{fn.name} is {self.what(value)} in {self.own_name(own.path)}, not a function, so it "
                                    f"can't be called with ( ). Use it without brackets: {lib[8:]}.{fn.name}")
            elif lib and lib.startswith("$module:"):
                members = self.lib_members(lib[8:]) or {}
                if fn.name in members and not accepts(members[fn.name], n):
                    self.problem(e, f"{lib[8:]}.{fn.name}() got the wrong number of inputs ({n}).")
                elif lib == "$module:anims" and fn.name in members:
                    self.check_anims_looks(e)

    def check_format(self, part):
        """f"{name:0.00}": a number's format (0.00, 000 or money) on something that is never a number. (A width
        pads anything.)"""
        if part.fmt is None or TEMPLATE_FORMAT.fullmatch(part.fmt).group(4):
            return
        kind = self.kind(part.value)
        if kind not in ("$text", "$list", "$dict", "$bool", "$nil", "$line", "$func", "$builtin"):
            return
        name = node_text(part.value)
        what = f"{name} is" if name and part.value.kind != "const" else "this is"
        tip = ""
        if kind == "$text" and self.typed(part.value):
            tip = f" input gives text, so turn it into a number first: {{num({name or 'answer'}):{part.fmt}}}."
        self.problem(part, f"The format {part.fmt} only works on numbers, but {what} {self.what(kind)}.{tip}")

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
        own = self.own_file(obj[8:]) if obj and obj.startswith("$module:") else None
        if own is not None:  # money.as_mony (1.5.0): the names money.tuf makes at its top level
            if own.names is not None and e.name not in own.names:
                shown, names = self.own_name(own.path), sorted(own.names)
                hint = difflib.get_close_matches(e.name, names, n=1, cutoff=0.6)
                if hint:
                    self.problem(e, f"{shown} doesn't have '{e.name}'. Did you mean '{hint[0]}'?")
                elif names:
                    self.problem(e, f"{shown} doesn't have '{e.name}'. It has: {', '.join(names)}.")
                else:
                    self.problem(e, f"{shown} doesn't have '{e.name}': it doesn't make any functions or values at its top level.")
            return
        if obj is not None and obj.startswith("$module:"):
            members = self.lib_members(obj[8:])
            if members is not None and e.name not in members:
                self.problem(e, f"{obj[8:]} doesn't have '{e.name}'. It has: {', '.join(members)}.")
            return
        if obj is not None and obj.startswith(("%", "$kind:")):  # rex.hunger (1.5.0)
            self.check_kind_attr(e, obj)
            return
        if e.obj.kind == "var" and e.obj.name in PY_NAMES and obj in ("$builtin", None) and e.obj.name not in self.user:
            self.problem(e, f"Tuff has no {e.obj.name}.{e.name}. {PY_NAMES[e.obj.name]}")
            return
        if obj is not None:
            self.problem(e, dot_help(self.what(obj), e.obj, e.name, obj.lstrip("$")))
            return
        if e.obj.kind == "var" and e.obj.name in OWN_NAME_BUILTINS:  # a function's own `file`: here it's the file library
            members = self.lib_members(e.obj.name) if e.obj.name == "file" else None
            if members is not None and e.name not in members:
                self.problem(e, f"file doesn't have '{e.name}'. It has: {', '.join(members)}.")
            return
        # Unknown value: only a library can use '.', and libraries only have these.
        gui = gui_tables()
        members = {"window"} | set(self.lib_members("anims") or {}) | set(self.lib_members("tap") or {}) | \
            set(self.lib_members("tgame") or {})
        # (Since 1.5.0 an object has fields: p.name in a function given a Pet. Only a name no kind has is certain.)
        if gui is not None and e.name not in members and e.obj.kind == "var" and e.obj.name not in self.imports and not self.is_field(e.name) \
                and e.obj.name != "my":  # (a my outside every action is reported by use)
            self.problem(e, dot_help("not a library", e.obj, e.name) if not self.kinds else
                         f"Nothing in this program has a field '{e.name}'." + self.field_hint(e.name))

    def is_print(self, e):
        """The built-in print (or say, in say:ascii): its :methods are print:ascii, print:color and print:pen."""
        return e.kind == "sayfn" or (e.kind == "var" and e.name == "print" and "print" not in self.user)

    def check_print_method(self, e):
        """print:ascii, print:color and print:pen (and say:...): a method print has, the text first, and words after
        it that say:color and the rest know (only the ones written in quotes can be checked before it runs)."""
        who = "say" if e.obj.kind == "sayfn" else "print"
        owner = f"{who}:{e.name}"
        if e.name not in ("ascii", "color", "colour", "pen"):
            self.problem(e, method_help(who.capitalize(), e.name, ["ascii", "color", "pen"]))
            return
        if e.name != "pen" and not e.args:
            self.problem(e, f'{owner} needs the text first, like: {owner}("Hello")')
            return
        words = e.args if e.name == "pen" else e.args[1:]
        art, pen = e.name == "ascii", e.name == "pen"
        known = [a for a in words if a.kind == "const" and isinstance(a.value, str)]
        for a in words:
            if a.kind == "const" and not isinstance(a.value, str):
                self.problem(a, f'{owner} takes words like "red", "bold" or "fade" after the text, not {self.what(self.kind(a))}.')
                return
        for a in known:
            try:
                read_look(owner, [a.value], art=art, pen=pen)
            except TuffError as err:
                self.problem(a, err.msg)
                return
        try:
            read_look(owner, [a.value for a in known], art=art, pen=pen)  # two fonts, too many colours...
        except TuffError as err:
            self.problem(e, err.msg)

    def check_method(self, e):
        if self.is_print(e.obj):
            self.check_print_method(e)
            return
        obj = self.kind(e.obj)
        name, n = e.name, len(e.args)
        start = e.obj.of if e.obj.kind == "held" else e.obj  # names[q:pop x]: q
        owner = start.name if start.kind == "var" else "thing"
        if obj is not None and obj.startswith(("%", "$kind:")):  # rex:feed(), one of its kind's actions (1.5.0)
            self.check_action(e, obj)
            return
        if obj is None:
            if not self.method_exists(name):
                tip = PY_ONLY.get(name.lower())
                actions = sorted({a for k in self.kinds for a in self.actions_of(k)})  # p:fead() in a function given a Pet
                hint = difflib.get_close_matches(name, actions, n=1, cutoff=0.6)
                tip = f"Did you mean :{hint[0]}?" if hint else tip
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
                what = "Text" if kind == "text" else self.TYPE[obj].capitalize()  # "A dictionary", like the run says
                tip = PY_ONLY.get(name.lower())
                msg = method_help(what, name, simple, kind)
                self.problem(e, msg + (f" {tip}" if tip and "instead" not in msg else ""))
            elif kind == "line" and name in LOOK_INPUTS:
                if not n:
                    self.problem(e, f':{name} needs the new text, like {owner}:{name}("Done!")')
                # say:ascii(...) and say:color(...) say a line of their own (a plain say "text" as an input is just its text)
                elif e.args[0].kind == "method" and self.is_print(e.args[0].obj) and e.args[0].name in ("ascii", "color", "colour"):
                    self.problem(e.args[0], f"say:{e.args[0].name} shows a new line, so this {name}s {owner} with that line's text. To animate {owner} where it is, use {owner}:play(\"explode\") (or {owner}:{name}(\"new text\", \"glitch\")).")
                else:
                    for a in e.args[1:]:
                        if a.kind == "const" and isinstance(a.value, str):
                            try:
                                read_look(f"line:{name}", [a.value], art=True)
                            except TuffError as err:
                                self.problem(a, err.msg)
                                break
            elif kind == "line" and name == "play" and n == 1 and e.args[0].kind == "const" and isinstance(e.args[0].value, str) \
                    and " ".join(e.args[0].value.lower().split()) not in ART_EFFECTS:
                hint = difflib.get_close_matches(e.args[0].value.lower(), ART_EFFECTS, n=1, cutoff=0.6)
                self.problem(e.args[0], f'line:play doesn\'t know "{e.args[0].value}".' + (f' Did you mean "{hint[0]}"?' if hint else "") + f" Animations: {', '.join(ART_EFFECTS)}.")
            elif name in ONE_INPUT and n != 1:
                self.problem(e, f":{name} needs 1 input.")
            elif name in INPUTS and not INPUTS[name][0] <= n <= INPUTS[name][1]:
                lo, hi = INPUTS[name]
                count = f"{lo} input{'s' if lo != 1 else ''}" if lo == hi else f"{lo} or {hi} inputs"
                self.problem(e, f"{owner}:{name} takes {count}, not {n}.")
            elif name in self.ZERO_INPUT and e.bare:
                self.problem(e, bare_fix)
            elif name in self.ZERO_INPUT and n:
                if name == "pop":
                    self.problem(e, f"{owner}:pop doesn't take a position: it always takes the last item. To take another item, read it with {owner}[...] and then :remove it.")
                else:
                    self.problem(e, f"{owner}:{name} doesn't take an input. Write {owner}:{name}()")
            elif kind == "dict" and name in ("get", "set", "has", "remove"):
                self.check_key(e.args[0])
            return
        if obj.startswith("$module:"):
            lib = obj[8:]
            first = next(iter(self.lib_members(lib) or {"window": None}))
            self.problem(e, f"A library doesn't have any :methods. Library functions use a dot, like: {lib}.{first}(...)")
            return
        if obj in self.TYPE:
            self.problem(e, f"{self.TYPE[obj].capitalize()} doesn't have any :methods.")
            return
        if obj in ("game", "world") and self.check_saves(e, obj):  # game:save and the rest (saved game data)
            return
        if obj in ("game", "world") and self.check_net(e, obj):  # game:host and the rest (multiplayer)
            return
        if self.is_tgame(obj):
            self.check_tgame(e, obj, bare_fix)
            return
        if obj == "tdpen":  # a tdraw pen
            names = tdraw_pen_methods()
            if names and name not in names:
                self.problem(e, method_help("A pen", name, names))
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

    def fixed_text(self, x):
        """The text an input always is: written there, or in a variable set to it once and never changed (pic =
        "../cat.png", then game:image(pic)). None when the checker can't know."""
        if x is not None and x.kind == "var" and x.name not in self.params and x.name not in self.loop_vars:
            sets = self.assigned.get(x.name, [])
            x = sets[0].value if len(sets) == 1 and sets[0].op == "=" else None
        return x.value if x is not None and x.kind == "const" and isinstance(x.value, str) else None

    def check_saves(self, e, obj):
        """game:save, game:load, game:saved and game:forget (tgame's saved game data, SAVE_INPUTS): how many inputs
        they got, a name that isn't text (like the score written first: game:save(score, "best")), and what
        game:save can't keep: a function, a sprite, a widget... Also game:delete(enemy), written to take a thing out
        of the game. True when it was one of these: nothing else needs checking."""
        tg = tgame_tables()
        methods = tg["kinds"].get(obj, {}) if tg else {}
        name, n = e.name, len(e.args)
        owner = e.obj.name if e.obj.kind == "var" else obj
        if name == "delete" and name not in methods and n == 1 and self.kind(e.args[0]) in ("sprite", "object", "car", "ragdoll"):
            thing = e.args[0].name if e.args[0].kind == "var" else None
            how = f"To take {thing} out of the game, use {thing}:remove()." if thing else \
                "To take a thing out of the game, use its :remove(), like enemy:remove()."
            self.problem(e, f"{a_kind(obj).capitalize()} doesn't have :delete. {how} ({owner}:forget(\"best\") forgets a save.)")
            return True
        rule = SAVE_INPUTS.get(name)
        if rule is None or name not in methods:
            return False
        takes, example, counts = rule
        use = example.format(o=owner)
        if n not in counts:
            self.problem(e, f"{owner}:{name} got the wrong number of inputs ({n}). It takes {takes}, like: {use}")
            return True
        if e.args:
            a, k = e.args[0], self.kind(e.args[0])
            if a.kind == "const" and isinstance(a.value, str) and not a.value.strip():
                self.problem(a, f"A save needs a name, like \"best\": {use}")
            elif k is not None and k not in ("$text", "$line"):
                what = "a library" if k.startswith("$module:") else self.what(k)
                self.problem(a, f"{owner}:{name} needs the save's name as text first, like {use}, not {what}.")
        if name == "save":
            k = self.kind(e.args[1])
            if k is not None and k not in SAVE_KINDS:
                what = "a library" if k.startswith("$module:") else self.what(k)
                self.problem(e.args[1], f"{owner}:save can keep {SAVE_KEEPS}, not {what}.")
        return True
    def check_net(self, e, obj):
        """game:host, :join, :send, :share and the rest (tgame's multiplayer, NET_INPUTS): how many inputs they got, a
        name, message or address that isn't text (like game:send(score) with no message), and what :send and :share
        can't carry: a function, a sprite, a widget... Also world:others() in a 2D game. True when it was one of
        these: nothing else needs checking."""
        tg = tgame_tables()
        methods = tg["kinds"].get(obj, {}) if tg else {}
        name, n = e.name, len(e.args)
        owner = e.obj.name if e.obj.kind == "var" else obj
        if name == "others" and obj == "game" and name not in methods and "share" in methods:
            self.problem(e, tg.get("needs_3d", {}).get("others") or NET_NEEDS_3D)
            return True
        rule = NET_INPUTS.get(name)
        if rule is None or name not in methods:
            return False
        takes, example, counts, text = rule
        use = example.format(o=owner)
        if n not in counts:
            self.problem(e, f"{owner}:{name} got the wrong number of inputs ({n}). It takes {takes}, like: {use}")
            return True
        if n and text:
            a, k = e.args[0], self.kind(e.args[0])
            if a.kind == "const" and isinstance(a.value, str) and not a.value.strip():
                self.problem(a, f"{owner}:{name} needs {text}, like {use}")
            elif k is not None and k not in ("$text", "$line"):
                what = "a library" if k.startswith("$module:") else self.what(k)
                self.problem(a, f"{owner}:{name} needs {text} as text, like {use}, not {what}.")
        if name in ("send", "share") and n == 2:
            k = self.kind(e.args[1])
            if k is not None and k not in SAVE_KINDS:
                what = "a library" if k.startswith("$module:") else self.what(k)
                self.problem(e.args[1], f"{owner}:{name} can {name} {SAVE_KEEPS}, not {what}.")
        return True

    def is_tgame(self, kind):
        """Whether tgame made it: one of its kinds, or the game kit's under the names tgame gives them."""
        return kind in self.TGAME_KINDS or kind in ((tgame_tables() or {}).get("kit_kinds") or ())

    def check_tgame(self, e, obj, bare_fix):
        """A method of something tgame made: its name, its input count, the function an event runs, and inputs
        written as text that have to be a color, a sky, a key, a sound, a land style, a lighting or a file tgame knows."""
        tg = tgame_tables()
        methods = tg["kinds"].get(obj) if tg else None
        if methods is None:
            return
        name, n = e.name, len(e.args)
        what = a_kind(obj).capitalize()
        game_ui = obj in ("game", "world") and name in GAME_UI
        if name not in methods and obj == "game" and name in ("car", "ragdoll"):
            self.problem(e, f"The {name} needs a 3D world. Make the game with tgame.world, like: world = tgame.world(\"Physics Fun\"), "
                            f"then {name} = world:{name}(...)")
            return
        if name not in methods and obj == "game" and name in KIT_3D:
            noun, use = KIT_3D[name]
            self.problem(e, f"{noun} needs a 3D world. Make the game with tgame.world, like: world = tgame.world(\"My Game\"), then {use}")
            return
        health = name if name in _KIT_THING else _KIT_THING_HINTS.get(name.lower())
        if name not in methods and obj == "door" and health in _KIT_THING and health not in methods:  # door:health_bar
            self.problem(e, DOOR_NO_HEALTH.format(name=name, o=e.obj.name if e.obj.kind == "var" else obj))
            return
        if name == "path" and obj in NO_PATH and e.args:  # car:path([...]): path() stops nothing, which is fine
            self.problem(e, NO_PATH[obj].format(o=e.obj.name if e.obj.kind == "var" else obj))
            return
        if name not in methods and obj == "game" and name in MOUSE_INPUTS:  # world:lock_mouse... on a 2D game
            self.problem(e, tg.get("needs_3d", {}).get(name) or MOUSE_NEEDS_3D)
            return
        if name not in methods and obj in ("game", "world") and name == "physics":
            owner = e.obj.name if e.obj.kind == "var" else obj
            self.problem(e, f"{what} doesn't have :physics. Each thing turns its own on, like crate:physics(), and "
                            f"{owner}:gravity({'-9.8' if obj == 'world' else '900'}) changes how strong gravity is.")
            return
        if name not in methods and obj == "car" and name.lower() in CAR_DOORS:
            owner = e.obj.name if e.obj.kind == "var" else obj
            self.problem(e, f"{what} doesn't have :{name}. " + CAR_DOORS[name.lower()].format(o=owner))
            return
        if name not in methods:
            alt = tg["hints"].get(obj, {}).get(name.lower())
            at = atgui_tables()
            if alt in methods:
                self.problem(e, f"{what} doesn't have :{name}. Use :{alt} instead.")
            elif obj in ("game", "world", "hud") and at and name in at["makes"]:
                # game:button, world:slider, hud:input...: real widgets go on a panel or a screen
                draws, game = (" The HUD only draws.", "game") if obj == "hud" else ("", e.obj.name if e.obj.kind == "var" else obj)
                self.problem(e, f"{what} doesn't have :{name}.{draws} Buttons, text boxes and other widgets go on a panel "
                                f"or a screen: bar = {game}:panel(\"top left\"), then bar:{name}(...)")
            else:
                self.problem(e, method_help(what, name, list(methods)))
            return
        physics = tg.get("physics_inputs", {}).get(obj, {}).get(name) or tg.get("kit_inputs", {}).get(obj, {}).get(name)
        if obj == "terrain" and name in TERRAIN_INPUTS:
            if not self.check_land_inputs(e):
                return
        elif physics:
            if not self.check_physics_inputs(e, obj, methods[name], physics, bare_fix):
                return
        elif not accepts(methods[name], n):
            owner = e.obj.name if e.obj.kind == "var" else obj
            if game_ui:
                use = GAME_UI_USE[name].replace("{owner}", owner)
                self.problem(e, f"{owner}:{name} got the wrong number of inputs ({n}). It takes {GAME_UI_TAKES[name]}, like: {use}")
            else:
                self.problem(e, bare_fix if e.bare and accepts(methods[name], 0) else f"{obj}:{name} got the wrong number of inputs ({n}).")
            return
        if game_ui:
            self.check_game_ui(e, tg)
            return
        if obj in ("game", "world") and name in ("splash", "auto_lock") and not self.check_intro_inputs(e):
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
            value = self.fixed_text(a)
            if value is not None:
                land = self.LAND_VALUES.get((obj, name, i))
                msg = self.land_value(land, value, tg) if land else tg["check"](obj, name, i, value, base)
                if msg:
                    self.problem(a, msg)
        if physics and name in self.PHYSICS_NUMBERS and len(e.args) == 1:
            rule = self.PHYSICS_NUMBERS[name]
            if name == "weight" and obj in ("sprite", "player"):  # a sprite weighs about 1 kg, the player 70
                rule = (*rule[:4], "{o}:weight(2)" if obj == "sprite" else "{o}:weight(70)", *rule[5:])
            self.check_physics_number(e, rule)
        if obj in tg.get("kit_inputs", {}) and name in tg["kit_inputs"][obj]:
            self.check_kit_inputs(e, obj, tg)
        if obj == "sprite" and name in FLIP_METHODS:
            self.check_flipbook(e)

    def check_flipbook(self, e):
        """Sprite-sheet animation (1.5.0): sprite:frames, :frame, :animation and :play written with something that
        can't be right. Frames are numbered from 1, a picture is cut into 1 or more frames each way, an animation has a
        list of frames and a speed above 0, and :play's second input is true or false. :play with a name no
        sprite:animation in the program makes, but only when every one of them names its animation as text, and the
        program makes the game and imports no files of its own (they could make more: animation_names)."""
        name, args = e.name, e.args
        o = e.obj.name if e.obj.kind == "var" else "hero"
        example = f'{o}:animation("walk", [1, 2, 3, 4], 10)'

        def number(a):
            if a.kind == "neg" and a.value.kind == "const" and isinstance(a.value.value, (int, float)) and not isinstance(a.value.value, bool):
                return -a.value.value
            if a.kind == "const" and isinstance(a.value, (int, float)) and not isinstance(a.value, bool):
                return a.value
            return None

        def frame_no(a):  # a frame number written in the code that can't be one
            v = number(a)
            if v is not None and (v < 1 or v != int(v)):
                self.problem(a, f"Frames are numbered from 1 (the top left one), so there's no frame {to_text(v)}.")

        if name == "frames":
            for a in args:
                v = number(a)
                if v is not None and (v < 1 or v != int(v)):
                    self.problem(a, f"{o}:frames needs how many frames across, then how many down (1 if you leave it out), "
                                    f"as whole numbers from 1, like {o}:frames(4) or {o}:frames(4, 2).")
        elif name == "frame" and args:
            frame_no(args[0])
        elif name == "animation" and len(args) >= 2:
            first, frames = args[0], args[1]
            if first.kind == "const" and not isinstance(first.value, str):
                self.problem(first, f"{o}:animation needs a name as text first, like {example}.")
            if frames.kind == "list":
                if not frames.items:
                    self.problem(frames, f"An animation needs at least one frame, like {example}.")
                for a in frames.items:
                    frame_no(a)
            elif self.kind(frames) in ("$number", "$text", "$bool", "$dict"):
                self.problem(frames, f"{o}:animation needs its frames as a list, like {example}.")
            fps = number(args[2]) if len(args) > 2 else None
            if fps is not None and fps <= 0:
                self.problem(args[2], f"{o}:animation's last input is how many frames a second, above 0, like {example}.")
        elif name == "play" and args:
            if len(args) > 1 and args[1].kind == "const" and not isinstance(args[1].value, bool):
                self.problem(args[1], f"{o}:play's second input is true (again and again, the same as leaving it out) or "
                                      f"false (once), like {o}:play(\"jump\", false).")
            wanted = self.fixed_text(args[0])
            known = self.flip_names
            if wanted is not None and known is not None and wanted not in known:
                if known:
                    listed = ", ".join(f'"{n}"' for n in sorted(known))
                    close = difflib.get_close_matches(wanted, sorted(known), n=1, cutoff=0.6)
                    hint = f' Did you mean "{close[0]}"?' if close else ""
                    self.problem(args[0], f"There's no animation called \"{wanted}\". This program makes {listed}.{hint}")
                else:
                    self.problem(args[0], f"There's no animation called \"{wanted}\". Make it first, like "
                                          f"{o}:animation(\"{wanted}\", [1, 2, 3, 4], 10), then {o}:play(\"{wanted}\").")

    def animation_names(self):
        """Every name the program's sprite:animation calls give (as text), or None when the checker can't know them
        all: one is made from a variable or a sum, the program imports a file of its own, or it doesn't make the game
        itself (a file of functions another program imports, which may make the animations)."""
        if not self.makes_game or any(name not in LIBRARIES for name in self.imports):
            return None
        names = set()
        for n in nodes(self.program):
            if n.kind == "method" and n.name == "animation" and n.args:
                text = self.fixed_text(n.args[0])
                if text is None:
                    return None
                names.add(text)
        return names

    def check_physics_inputs(self, e, obj, fn, physics, bare_fix):
        """How many inputs a physics method got. A spot ([x, y, z], or [x, y] in 2D) can go in place of its x, y and z,
        and once tgame has the method itself, the ways it takes count too. True when the count can be right."""
        name, n = e.name, len(e.args)
        takes, example, counts, spot = physics
        spot, at = spot if isinstance(spot, tuple) else (spot, 0)  # the game kit's spots can come after other inputs
        at_list = len(e.args) > at and self.kind(e.args[at]) in ("$list", None)
        partial = spot > 1 and at < n < at + spot and self.kind(e.args[at]) == "$number"  # x without its y and z
        fits = (n in counts or (spot > 1 and at_list and n + spot - 1 in counts)
                or (fn not in (physics_input, kit_input) and accepts(fn, n) and not partial))
        if fits:
            return True
        owner = e.obj.name if e.obj.kind == "var" else obj
        if e.bare and 0 in counts:
            self.problem(e, bare_fix)
        else:
            self.problem(e, f"{owner}:{name} got the wrong number of inputs ({n}). It takes {takes}, like: {example.format(o=owner)}")
        return False

    def check_physics_number(self, e, rule, a=None):
        """thing:mass, :bounce and :friction (or the input a, like the game kit's numbers) written with a number that
        can't be right, or with text or true/false. A rule can have one more number that's fine (day_cycle's 0)."""
        low, low_ok, high, needs, example, *also = rule
        a = e.args[0] if a is None else a
        if a.kind == "neg" and a.value.kind == "const" and isinstance(a.value.value, (int, float)) and not isinstance(a.value.value, bool):
            v = -a.value.value
        elif a.kind == "const" and a.value is not None:
            v = a.value
        else:
            return
        number = isinstance(v, (int, float)) and not isinstance(v, bool)
        if number and v in also:
            return
        if not number or v < low or (v == low and not low_ok) or (high is not None and v > high):
            owner = e.obj.name if e.obj.kind == "var" else "thing"
            self.problem(a, f"{owner}:{e.name} needs {needs}, like {example.format(o=owner)}.")

    def check_kit_inputs(self, e, obj, tg):
        """The game kit's inputs that can't be right: numbers out of range (a shake from 0 to 2, an hour from 0 to 24,
        a health bar above 0...), a weather, a minimap's corner or a path's "loop" that tgame doesn't know (with "did
        you mean"), a color it doesn't know, the minimap's corner where its size goes, and the key's name where a door
        needs the key itself. After a spot ([x, y, z]), or the thing pop_text floats over, the inputs count as if x, y
        and z were written out."""
        name = e.name
        owner = e.obj.name if e.obj.kind == "var" else obj
        spot = tg["kit_inputs"][obj][name][3]
        spot, at = spot if isinstance(spot, tuple) else (spot, 0)
        first = self.kind(e.args[at]) if len(e.args) > at else None
        over = name == "pop_text" and first in ("sprite", "object", "car", "ragdoll", "door", "player")
        shift = spot - 1 if spot > 1 and (first == "$list" or over) else 0
        for i, a in enumerate(e.args):
            j = i + shift if i > at else i  # where it would be with x, y and z written out
            text = a.kind == "const" and isinstance(a.value, str)
            if text and tg["check"](obj, name, i, a.value, None):
                continue  # tgame's own check says so already
            what = KIT_VALUES.get((name, j)) or ("color" if name == "pop_text" and j == (4 if obj == "world" else 3) else None)
            if text and name == "minimap" and j == 0 and self.kit_value("corner", a.value, tg) is None:
                self.problem(a, f'{owner}:minimap takes its size first, then the corner, like: map = {owner}:minimap(180, "{a.value.strip().lower()}")')
            elif text and what == "key":
                self.problem(a, f'{owner}:needs takes the key itself, not its name, like: key = world:spawn("key", 3, 0, 3), then {owner}:needs(key)')
            elif text and what in tg.get("own_values", ()):
                continue  # tgame's own check found nothing wrong
            elif text and what:
                msg = self.kit_value(what, a.value, tg, owner)
                if msg:
                    self.problem(a, msg)
            elif (name, j) in KIT_NUMBERS:
                self.check_physics_number(e, KIT_NUMBERS[(name, j)], a)
            elif name == "pop_text" and j == (5 if obj == "world" else 4):
                self.check_physics_number(e, POP_SIZE["world" if obj == "world" else "game"], a)

    def kit_value(self, what, value, tg, owner="thing"):
        """A weather, a minimap's corner, a path's mode or a color written as text: one tgame knows (None), or what's
        wrong, with a "did you mean"."""
        if what == "color":
            return tg["check"]("object", "color", 0, value, None)
        names = {"weather": tg.get("weathers", WEATHERS), "corner": tg.get("corners", CORNERS), "path": tg.get("path_modes", PATH_MODES)}[what]
        low = " ".join(value.strip().lower().replace("_", " ").replace("-", " ").split()) if what == "corner" else value.strip().lower()
        if low in names:
            return None
        guess = VALUE_HINTS[what].get(low)
        hint = guess if guess in names else next(iter(difflib.get_close_matches(low, names, n=1, cutoff=0.6)), None)
        shown = [f'"{x}"' + (f" ({PATH_SAYS[x]})" if what == "path" and x in PATH_SAYS else "") for x in names]
        listed = f"{', '.join(shown[:-1])} or {shown[-1]}"
        msg = {"weather": f'The weather can be {listed}, not "{value}".',
               "corner": f'The minimap can go in the {listed} corner, not "{value}".',
               "path": f'{owner}:path\'s third input can be {listed}, not "{value}".'}[what]
        return msg + (f" Did you mean \"{hint}\"?" if hint else "")

    def check_land_inputs(self, e):
        """How many inputs one of the land's methods got. A spot ([x, z]) can go in place of each x and z, and a
        brush stroke (a list of spots) in place of a brush's x and z, so with a list (or something that could be
        one) fewer inputs can be right too. True when the count can be right."""
        name, n = e.name, len(e.args)
        inputs = TERRAIN_INPUTS[name]
        spots = len(inputs) - n  # how many x, z pairs a spot would have to stand in for
        could_be_lists = sum(1 for a in e.args if self.kind(a) in ("$list", None))
        spot_first = bool(e.args) and self.kind(e.args[0]) == "$list" and inputs[0] == "x"  # x can't be a list
        if spot_first:
            fits = spots == 1
        else:
            fits = spots == 0 or 0 < spots <= min(could_be_lists, sum(1 for i in inputs if i.startswith("x")))
        if fits:
            return True
        owner = e.obj.name if e.obj.kind == "var" else "land"
        if spot_first:
            inputs = ("the spots" if name in TERRAIN_BRUSHES else "the spot",) + inputs[2:]
        names = inputs[0] if len(inputs) == 1 else f"{', '.join(inputs[:-1])} and {inputs[-1]}"
        here = " here" if len(inputs) < len(TERRAIN_INPUTS[name]) else ""
        self.problem(e, f"{owner}:{name} needs {len(inputs)} input{'s' if len(inputs) != 1 else ''}{here} ({names}), but got {n}.")
        return False

    def land_value(self, what, value, tg):
        """A land style, a lighting, a kind of physics or an animation written as text: one tgame knows, or a "did you
        mean". A kind of physics can be one of tgame's other words for it too ("fixed" is "static", "on" is "dynamic")."""
        names = {"style": tg["styles"], "lighting": tg["lightings"], "physics": tg.get("physics_kinds", PHYSICS_KINDS),
                 "animation": tg.get("animations", ANIMATIONS)}[what]
        low = value.strip().lower()
        if what == "physics":
            low = tg.get("physics_words", {}).get(low, low)
        if low in names:
            return None
        guess = VALUE_HINTS[what].get(low)
        hint = guess if guess in names else next(iter(difflib.get_close_matches(low, names, n=1, cutoff=0.6)), None)
        if what == "style":
            thing, shown = "The land's style", list(names)
        elif what == "physics":
            thing, shown = "A thing's physics", [f'"{x}"' + (f" ({PHYSICS_SAYS[x]})" if x in PHYSICS_SAYS else "") for x in names]
        else:
            thing, shown = "The lighting" if what == "lighting" else "A character's animation", [f'"{x}"' for x in names]
        msg = f"{thing} can be {', '.join(shown[:-1])} or {shown[-1]}, not \"{value}\"."
        return msg + (f" Did you mean \"{hint}\"?" if hint else "")

    def check_game_ui(self, e, tg):
        """game:panel, game:screen and game:start_screen: where a panel goes (one of the places tgame knows, or a
        "did you mean"), and inputs that can't be right: a function or a number where a place goes, a function as a
        title or hint (people expect the start screen to take the function that starts the game), and text or a
        function where a screen's true or false goes."""
        name = e.name
        owner = e.obj.name if e.obj.kind == "var" else "game"
        kinds = [self.kind(a) for a in e.args]
        use = GAME_UI_USE[name].replace("{owner}", owner)
        funcs = ("$func", "$builtin")
        if name == "panel" and e.args:
            a = e.args[0]
            if a.kind == "const" and isinstance(a.value, str):
                msg = self.anchor_problem(a.value, tg["anchors"])
                if msg:
                    self.problem(a, msg)
            elif kinds[0] in funcs + ("$number", "$bool"):
                self.problem(a, f"A panel's input is where it goes, written as text, like: {use}")
        elif name == "screen":
            if kinds and kinds[0] in funcs + ("$list",):
                self.problem(e.args[0], f"A screen's first input is its title, like: {use}")
            if len(kinds) > 1 and kinds[1] in funcs + ("$text", "$list"):
                self.problem(e.args[1], "A screen's second input is whether it pauses the game while it shows: true or false (without quotes).")
        elif name == "start_screen":
            bad = next((a for a, k in zip(e.args, kinds) if k in funcs), None)
            if bad is not None:
                self.problem(bad, f"A start screen takes a title and a hint, both text, like: {use}. A click on it starts the game by itself.")
        elif name == "main_menu":
            if kinds and kinds[0] in funcs + ("$list", "$bool"):
                self.problem(e.args[0], f"A main menu's input is its title, like: {use}. Then add buttons to it: menu:button(\"Play\", play).")

    def check_intro_inputs(self, e):
        """game:splash(what, seconds) and world:auto_lock(on): a function, a list or true/false where the picture or
        text goes, seconds that aren't a number above 0, and text where true or false goes. True when they can be right."""
        owner = e.obj.name if e.obj.kind == "var" else ("world" if e.name == "auto_lock" else "game")
        kinds = [self.kind(a) for a in e.args]
        if e.name == "auto_lock":
            if kinds and kinds[0] in ("$text", "$number", "$list", "$func", "$builtin"):
                self.problem(e.args[0], f"{owner}:auto_lock takes true or false (without quotes), like: {owner}:auto_lock(false)")
                return False
            return True
        if kinds and kinds[0] in ("$func", "$builtin", "$list", "$bool"):
            self.problem(e.args[0], f"{owner}:splash takes a picture file or some text, then how many seconds it shows, like: "
                                    f"{owner}:splash(\"logo.png\", 3). The game starts by itself after the splash screens.")
            return False
        if len(e.args) > 1:
            a = e.args[1]
            inner = a.value if a.kind == "neg" else a
            v = getattr(inner, "value", None) if inner.kind == "const" else None
            number = isinstance(v, (int, float)) and not isinstance(v, bool)
            v = -v if number and a.kind == "neg" else v
            if kinds[1] in ("$text", "$bool", "$list", "$func", "$builtin") or (number and v <= 0):
                self.problem(a, f"{owner}:splash's second input is how many seconds it shows: a number above 0, like {owner}:splash(\"logo.png\", 3).")
                return False
        return True

    def anchor_problem(self, value, anchors):
        """Where a panel goes, written as text: one of the places tgame knows (in any case, with - or _ for the
        spaces), or a "did you mean"."""
        def plain(text):
            return " ".join(text.strip().lower().replace("-", " ").replace("_", " ").split())

        places = {plain(a) for a in anchors}
        low = plain(value)
        if low in places:
            return None
        guess = ANCHOR_HINTS.get(low) or ANCHOR_HINTS.get(low.replace(" ", ""))
        near = difflib.get_close_matches(low, sorted(places) + list(ANCHOR_HINTS), n=1, cutoff=0.6)  # "middel", "top lef"
        if guess not in places and near:
            guess = ANCHOR_HINTS.get(near[0], near[0])
        hint = guess if guess in places else None
        shown = [f'"{x}"' for x in ANCHORS if x in places] or [f'"{x}"' for x in sorted(places)]
        msg = f"A panel can go at {', '.join(shown[:-1])} or {shown[-1]}, not \"{value}\"."
        return msg + (f" Did you mean \"{hint}\"?" if hint else "")

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
                any(x.kind == "method" and (x.obj.of if x.obj.kind == "held" else x.obj).kind == "var" and
                    (x.obj.of if x.obj.kind == "held" else x.obj).name == lst and x.name in ("add", "remove", "pop") for x in where)

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
        if name in ("confirm", "showing") or (name == "shown" and name in methods):  # :shown is a game screen's
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
            alt = GAME_UI_METHOD_HINTS.get(name.lower()) if kind in ("panel", "screen") else None
            self.problem(e, f"{a_kind(kind).capitalize()} doesn't have :{name}. Use :{alt} instead." if alt in methods
                         else method_help(a_kind(kind).capitalize(), name, list(methods)))
            return
        if not accepts(methods[name], n):
            if e.bare and accepts(methods[name], 0):
                self.problem(e, f"{owner}:{name} doesn't take an input, so what comes after it was read as one. Write {owner}:{name}() instead.")
            elif name == "slider" and "heading" in methods and any(self.kind(a) in ("$func", "$builtin") for a in e.args):
                self.problem(e, f"A slider takes low, high and where it starts, not a function. To run a function when it moves, "
                                f"use its :change, like: volume = {owner}:slider(0, 100, 50) then volume:change fn")
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
        elif (name == "avatar" and container) or (name == "set" and kind == "avatar"):  # a picture, or initials
            text = self.fixed_text(e.args[0] if e.args else None)
            if text is not None and text.strip().lower().endswith(at["image_exts"]):
                self.atgui_picture(e.args[0])
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
        path = self.fixed_text(arg)
        if path is None:
            return
        path = path.strip()
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
                    self.problem(x, "wait() freezes the game: nothing moves or redraws until it's over. To do something later, use game:after(seconds, fn)."
                                 if self.makes_game else
                                 "wait() freezes the window: nothing redraws or runs until it's over. To do something later, use app:after(seconds, fn).")
                elif x.kind == "input":
                    self.problem(x, "input reads from the console and freezes the game while it waits. To ask for text, put a text box on a screen: name_box = shop:input(\"Your name\")."
                                 if self.makes_game else
                                 "input reads from the console and freezes the window while it waits. In a window app, ask with app:ask \"...\" instead.")


# atgui's event methods too, so a missing event function gets "Make it with func" (atgui's checks are just above).
Checker.HANDLER_POS = {**Checker.HANDLER_POS, "clicked": 0, "hover": 0, "focus": 0, "key": 1, "closed": 0, "item": 1}
# And the game kit's: enemy:on_death(gone), npc:on_talk(talk), game:countdown(60, times_up).
Checker.HANDLER_POS = {**Checker.HANDLER_POS, "on_death": 0, "on_talk": 0, "countdown": 1}
# 1.5.0: hero:on_done(landed), when an animation that plays once ends.
Checker.HANDLER_POS = {**Checker.HANDLER_POS, "on_done": 0}


# ---------------------------------------------------------------- Tuff Engine's preview (tuff.py --scene)
class SceneConsole(Console):
    """Prints nothing and answers input() with "", so a preview never shows output or waits."""
    animate = False

    def write(self, text):
        pass

    def input(self, prompt, look=None):
        return ""


class SceneInterpreter(Interpreter):
    """Keeps the stack of lines being run (lines[0] is the top-level line), so tgame can tell which line made
    each thing. wait() returns at once.

    The preview runs by itself whenever the code changes, so it keeps its memory small as well as its time (main.js
    stops it after 5 seconds), the same way on every system: the only things in Tuff that grow faster than a loop
    can fill a list (under 100 MB in those 5 seconds) are range(), text * a number, and + on two texts or two lists.
    Each of those is sized before it's made, and one over ONE bytes, or more than ALL of them together, stops the
    preview as "too-much" (Tuff Engine says so, and shows what was made before it)."""
    ONE = 100_000_000
    ALL = 400_000_000
    writes = False  # the preview runs by itself on every change: it never writes files

    def __init__(self, src, base_dir):
        super().__init__(src, base_dir)
        self.console = SceneConsole()
        self.lines = []
        self.big = 0  # bytes of the big ranges, texts and lists made so far

    def room(self, size):
        if size < 1_000_000:
            return
        self.big += size
        if size > self.ONE or self.big > self.ALL:
            import tuff_tgame
            tuff_tgame.SCENE.stop("too-much")

    def b_range(self, a, b=None, step=1):
        try:
            lo, hi = (1, a) if b is None else (a, b)
            st = int(step)
            if st:
                try:
                    n = len(range(int(lo), int(hi) + (1 if st > 0 else -1), st))
                except OverflowError:  # more numbers than a list can hold
                    n = self.ONE
                self.room(40 * n)  # a list of numbers: about 40 bytes each
        except (TypeError, ValueError):
            pass  # not numbers: Interpreter.b_range says what's wrong
        return super().b_range(a, b, step)

    def binop(self, op, a, b):
        x, y = plain(a), plain(b)
        whole = lambda v: isinstance(v, int) and not isinstance(v, bool)
        if op == "*" and isinstance(x, str) and x and whole(y):  # ("" * 2 ^ 99999 is just "")
            self.room(sys.getsizeof(x) * max(y, 0))
        elif op == "*" and isinstance(y, str) and y and whole(x):
            self.room(sys.getsizeof(y) * max(x, 0))
        elif op == "+" and isinstance(x, str) and isinstance(y, str):
            self.room(sys.getsizeof(x) + sys.getsizeof(y))
        elif op == "+" and isinstance(x, list) and isinstance(y, list):
            self.room(8 * (len(x) + len(y)))
        return super().binop(op, a, b)

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
    every = src and with_imports(game_path, src)  # (1.5.0) with the program's own files it imports
    if src is None:
        data["stopped"] = "unreadable"
    elif not TGAME_IMPORT.search(every):
        data["stopped"] = "nogame"
    elif OTHER_WINDOW.search(every):
        data["stopped"] = "other-window"   # runs nothing: those libraries open real windows
    else:
        os.environ["TUFF_SCENE"] = "1"
        random.seed(0)
        interp = SceneInterpreter(src, os.path.dirname(os.path.abspath(game_path)))
        interp.path = os.path.abspath(game_path)
        scene = tuff_tgame.start_scene(interp)
        error = None

        def setup():
            program = Parser(tokenize(src)).program()
            for stmt in program:
                if stmt.kind in ("func", "kind"):
                    interp.run(stmt, interp.globals)
            interp.run_block(program, interp.globals)
            for hook in interp.rt.finish_hooks:
                hook()

        try:
            run_deep(setup, main=bool(TK_IMPORT.search(every)))  # as deep as a real run
        except tuff_tgame.SceneDone:
            pass
        except TuffError as err:
            error = {"line": err.line, "col": err.col, "message": err.msg}
            if err.file in OWN_FILES:  # (1.5.0) in one of its own files: the line is that file's, so the message says it
                error = {"line": None, "col": None, "message": f"In {OWN_FILES[err.file][1]}, line {err.line}: {err.msg}"}
        except (ReturnSignal, BreakSignal, ContinueSignal) as sig:
            word = {"ReturnSignal": "return", "BreakSignal": "break", "ContinueSignal": "continue"}[type(sig).__name__]
            error = {"line": sig.line, "col": sig.col, "message": f"'{word}' can't be used here."}
        except RecursionError:
            error = {"line": None, "col": None, "message": "A function called itself too many times."}
        except MemoryError:  # the system ran out before SceneInterpreter's own limits did
            scene.stopped = scene.stopped or "too-much"
        except Exception as exc:  # a bug in scene mode must never hang the editor
            error = {"line": None, "col": None, "message": f"Tuff Engine's preview had a problem: {exc}"}
        try:
            data.update(scene.dump(error))
            if scene.stopped == "too-much" and not error:
                data["stopped"] = "too-much"  # even before the game's window was made
        except Exception as exc:
            data.update(stopped="error", batch=[], things=[],
                        error={"line": None, "col": None, "message": f"Tuff Engine's preview had a problem: {exc}"})
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"), default=list)
    return 0


# ---------------------------------------------------------------- entry point

def error_lines(err, src):
    """An error as it's shown: "Tuff error on line 3: ...", then that line of the code and a ^ under its column. One
    in another of the program's files (err.file, 1.5.0) says which, "Tuff error in money.tuf on line 3: ...", and
    shows that file's line."""
    where = ""
    if err.file in OWN_FILES:
        src, shown = OWN_FILES[err.file]
        where = f" in {shown}"
    lines = source_lines(src)
    out = [f"Tuff error{where} on line {err.line}: {err.msg}" if err.line else f"Tuff error{where}: {err.msg}"]
    if err.line and 0 < err.line <= len(lines):
        code = lines[err.line - 1]
        gutter = f"  {err.line} | "
        out.append(gutter + code)
        if err.col:
            out.append(" " * (len(gutter) + err.col - 1) + "^")
    return out


def report(err, src):
    out = error_lines(err, src)
    if IDE and err.line:  # TuffCode marks the line (ide.js handleOsc); one in another file adds that file's path
        other = f";{b64(err.file)}" if err.file in OWN_FILES else ""
        sys.stdout.write(f"\x1b]tuff;error;{err.line};{err.col or 1};{b64(err.msg)}{other}\x07")
        sys.stdout.flush()
    sys.stderr.write("\n".join(out) + "\n")
    sys.stderr.flush()
    if WINDOWED:
        SHOWING_BOX.set()
        try:
            from tkinter import messagebox
            messagebox.showerror("Something went wrong", "\n".join(out[:2]))
        except Exception:
            pass
        finally:
            SHOWING_BOX.clear()


WINDOWED = False
# An error box is up (a built app's): while it is, a window's close time limit (tuff_view's CLOSE_LIMIT) waits for it,
# so an error in app:closed stays on the screen until it's read.
SHOWING_BOX = threading.Event()


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


def source_text(path):
    """A .tuf file's text. UTF-8 (with or without a BOM), or UTF-16 with its BOM: Notepad's "Unicode", and what Windows
    PowerShell's > and Out-File write. Raises OSError or UnicodeDecodeError (see unreadable)."""
    with open(path, "rb") as f:
        data = f.read()
    text = data.decode("utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def unreadable(path, exc, shown=None):
    """Why source_text couldn't read path, for a message (shown: the name it gives the file, else 'path')."""
    shown = shown or f"'{path}'"
    if isinstance(exc, FileNotFoundError):
        return f"There's no file called {shown}."
    if isinstance(exc, UnicodeDecodeError):
        return f"{shown} isn't a text file, so it can't be a Tuff program." if b"\x00" in exc.object else \
            f"{shown} isn't saved as UTF-8, so Tuff can't read it. Save it again as UTF-8, or copy its code into a new TuffCode file."
    return f"{shown} is a folder, not a .tuf file." if os.path.isdir(path) else f"Couldn't open {shown}: {exc.strerror or exc}."


def read_source(path):
    """The program's text, or None after a one-line message when the file can't be read."""
    try:
        return source_text(path)
    except (OSError, UnicodeDecodeError) as exc:
        report(TuffError(unreadable(path, exc)), "")
    return None


def base_folder(path):
    """The folder a program's files are in: its own, or TUFF_BASE_DIR's (tuff_run gives a snippet the project's)."""
    return os.environ.get("TUFF_BASE_DIR") or os.path.dirname(os.path.abspath(path))


# 1.4.1: a Tuff call is 7 to 14 of Python's, and Python stops at 1000 calls deep, so a Tuff function used to stop after
# about 100 calls of itself. A program runs on a thread of its own with a big stack and a higher limit instead: a
# function can call itself over 10,000 times, and one that never stops still ends in under a second with "f() called
# itself too many times." Programs with tgui, mtgui or tdraw (tkinter) keep the main thread, which a Mac's windows need,
# and so do apps with no console (report's box is tkinter's).
MAX_DEPTH = 10_050  # Tuff calls inside each other (depth(10000) and a little more): 7 to 14 Python calls each
DEEP_CALLS = 200_000
DEEP_STACKS = (512 << 20, 255 << 20, 64 << 20)  # the first one a thread can start with (Windows takes under 256 MB)
# From Python 3.12 (what TuffCode's runtime is built with) Python's own calls don't use the stack, so the usual thread
# goes as deep: the program's thread gets the usual stack, not a big one that Windows would set aside in full for every run.
STACK_FREE = sys.version_info >= (3, 12)
TK_IMPORT = re.compile(r"^[ \t]*(?:import|mention)[ \t]+(?:tgui|mtgui|tdraw)\b", re.M)


def big_stack():
    """Makes the next thread Python starts a big-stack one, with the biggest size in DEEP_STACKS a thread can start
    with. Gives that size, or 0 when none can (it gets the usual stack). threading.stack_size(0) once it has started."""
    if STACK_FREE:
        return 0
    for size in DEEP_STACKS:
        try:
            threading.stack_size(size)
            probe = threading.Thread(target=int)
            probe.start()
            probe.join()
            return size
        except (ValueError, RuntimeError, MemoryError):
            pass
    threading.stack_size(0)
    return 0


def go_deep(stack):
    """Raises Python's limit on calls for a program on a thread with a stack this big (0: the usual one). From Python
    3.12 its own calls don't use the stack, so it's DEEP_CALLS; before that each takes up to 1 KB of it."""
    calls = DEEP_CALLS if sys.version_info >= (3, 12) else min(DEEP_CALLS, stack // 1024)
    if calls > sys.getrecursionlimit():
        sys.setrecursionlimit(calls)


def on_big_stack(stack, fn, *args):
    """What a big-stack thread runs (tuff_view.run starts the one a window program runs on)."""
    threading.stack_size(0)  # only this thread is big: the window's own threads keep the usual stack
    go_deep(stack)
    return fn(*args)


def run_deep(fn, *args, main=False):
    """fn(*args) on a big-stack thread (main=True: here, on the main thread), giving what it gives; its errors are
    raised again here. Ctrl+C only reaches the main thread, so it waits in short naps to let it in, then stops fn too."""
    if main:
        go_deep(0)
        return fn(*args)
    stack = big_stack()
    done, finished = {}, threading.Event()  # not worker.is_alive(): Ctrl+C during a join can leave that saying False

    def body():
        try:
            done["value"] = on_big_stack(stack, fn, *args)
        except BaseException as exc:
            done["error"] = exc
        finally:
            finished.set()

    worker = threading.Thread(target=body, name="tuff", daemon=True)
    try:
        worker.start()
    except RuntimeError:  # it couldn't start after all
        threading.stack_size(0)
        go_deep(0)
        return fn(*args)
    threading.stack_size(0)
    try:
        while not finished.wait(0.1):
            pass
    except KeyboardInterrupt:
        switch = sys.getswitchinterval()
        sys.setswitchinterval(0.0001)  # a busy program would slow the import below to half a second
        try:
            import ctypes
            ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_ulong(worker.ident), ctypes.py_object(KeyboardInterrupt))
        except Exception:
            pass
        finally:
            sys.setswitchinterval(switch)
        if not finished.wait(1.0):
            # Still inside something that can't be stopped, like reading input from a pipe: Python's own ending could
            # stop with "could not acquire lock for <stdin> at interpreter shutdown", so end the process here.
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(130)
        raise
    worker.join()
    if "error" in done:
        raise done["error"]
    return done.get("value")


IMPORT_LINE = re.compile(r"^[ \t]*(?:import|mention)[ \t]+([A-Za-z_]\w*)", re.M)


def with_imports(path, src):
    """The program's text, then the text of each of its own files it imports (and they import), for what only the
    whole program can say, like whether it opens a window (see run_program). A file that can't be read is left out."""
    texts, seen, todo = [src], set(), [(base_folder(path), src)]
    while todo:
        folder, text = todo.pop()
        for name in IMPORT_LINE.findall(text):
            found = None if name in LIBRARIES or name == "file" else module_file(folder, name)
            key = found and os.path.normcase(os.path.abspath(found))
            if not found or key in seen:
                continue
            seen.add(key)
            try:
                more = source_text(found)
            except (OSError, UnicodeDecodeError):
                continue
            texts.append(more)
            todo.append((os.path.dirname(found), more))
    return "\n".join(texts)


def run_file(path):
    src = read_source(path)
    if src is None:
        return 1
    try:
        program = Parser(tokenize(src)).program()
        interp = Interpreter(src, base_folder(path))
        interp.path = os.path.abspath(path)
        for stmt in program:
            if stmt.kind in ("func", "kind"):  # functions and kinds can be used above where they're written
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
    except MemoryError:  # (1.4.1) a list or text growing without end, outside any function
        report(TuffError("The program ran out of memory. Is a list or some text growing without end?"), src)
        return 1
    except OverflowError:  # (1.5.0) the maths says so itself, with the line; this is in case anything is missed
        report(TuffError(TOO_BIG_NUMBER), src)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


def run_program(path):
    src = read_source(path)
    if src is None:
        return 1
    every = with_imports(path, src)  # (1.5.0) a window library imported by one of its own files counts too
    if not VIEW_IMPORT.search(every):
        try:
            return run_deep(run_file, path, main=WINDOWED or bool(TK_IMPORT.search(every)))
        except KeyboardInterrupt:
            return 130
    if TGAME_IMPORT.search(every) and not WINDOWED:
        Console(first_id=0).say(TGAME_NOTICE, "notice")  # line 0: the program's own lines start at 1
    try:
        import tuff_view
    except ImportError:
        report(TuffError("This program needs Tuff's window engine (tuff_view.py), which isn't installed next to tuff.py."), src)
        return 1
    stack = big_stack()  # for the thread tuff_view.run starts
    try:
        code = tuff_view.run(on_big_stack, stack, run_file, path)
    except KeyboardInterrupt:
        return 130
    except tuff_view.ViewError as err:
        report(TuffError(str(err)), src)
        return 1
    finally:
        threading.stack_size(0)
    return 0 if code is None else code


def import_folder(path, real=None):
    """Where the file's imports are found (1.5.0): next to real (the file path is a copy of, see check_file), else where
    a run finds them (TUFF_BASE_DIR or the file's folder), or None for a file in the temp folder with no real one."""
    if real:
        return os.path.dirname(os.path.abspath(real))
    if os.environ.get("TUFF_BASE_DIR"):
        return os.environ["TUFF_BASE_DIR"]
    full = os.path.abspath(path)
    return None if os.path.normcase(full).startswith(os.path.normcase(os.path.abspath(tempfile.gettempdir()))) else os.path.dirname(full)


def check_file(path, real=None):
    """--check path, or --check path --as real: path is a copy of real's code (TuffCode checks the editor's text as it
    is, unsaved too, from a temp file), so its imports are checked from real's folder (1.5.0)."""
    src = read_source(path)
    if src is None:
        return 1
    try:
        program = Parser(tokenize(src)).program()
    except TuffError as err:
        report(err, src)
        return 1
    try:
        problems = Checker(program, base_folder(path), real or path, import_folder(path, real)).run()
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
    if hasattr(sys, "set_int_max_str_digits"):  # say 2 ^ 20000 shows every digit (Python stops at 4300)
        sys.set_int_max_str_digits(0)
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
        return check_file(args[1], args[3] if len(args) > 3 and args[2] == "--as" else None)
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
