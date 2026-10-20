"""tap: get and send things on the web from Tuff, like Python's requests. Only Python's own library is used,
so there's nothing to install.

Tuff has no dictionaries, so a JSON object comes back as a "data object": user:get("name"), :has, :keys,
:set and :size. Objects inside it are data objects too, and arrays are Tuff lists.
"""
import http.client
import json
import os
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request

try:
    import ssl
except ImportError:  # a Python built without OpenSSL: http:// still works
    ssl = None

TIMEOUT = 15  # seconds to wait for a server, for connecting and for each read
AGENT = "TuffCode-tap/1.0"
DATA = "data object"
URL_SAFE = "!#$%&'()*+,/:;=?@[]~"  # left alone when spaces and other letters in a web address are %-escaped
MAC_CERTS = "/etc/ssl/cert.pem"  # macOS's own list of certificates, used when certifi isn't there


def data_of(v):
    """The Data behind a data object, or None for anything else."""
    d = getattr(v, "tap", None)
    return d if isinstance(d, Data) else None


class Data:
    """A JSON object: named values. Read one with :get, change one with :set."""

    def __init__(self, lib, values):
        self.lib, self.values = lib, values

    def key(self, name, method):
        name = self.lib.rt.plain(name)
        if not isinstance(name, str):
            raise self.lib.rt.error(f"data:{method} needs a name as text, like \"name\", not {self.lib.rt.what(name)}.")
        return name

    def get(self, name):
        return self.values.get(self.key(name, "get"))

    def has(self, name):
        return self.key(name, "has") in self.values

    def keys(self):
        return list(self.values)

    def set(self, name, value):
        name = self.key(name, "set")
        self.lib.to_json(value, "A data object")  # a value JSON can't hold is reported on this line, not later
        self.values[name] = self.lib.rt.plain(value)
        return self.native

    def size(self):
        return len(self.values)

    def show(self, nested=False):
        return json.dumps(self.lib.to_json(self.native, "A data object"), ensure_ascii=False, indent=None if nested else 2)

    def methods(self):
        return {"get": self.get, "has": self.has, "keys": self.keys, "set": self.set, "size": self.size}


class Response:
    """What a server sent back. HTTP errors (404, 500...) are normal responses: check :ok."""

    def __init__(self, lib, status, headers, body):
        self.lib, self.code, self.headers, self.body = lib, status, headers, body
        self.decoded = None

    def status(self):
        return self.code

    def ok(self):
        return 200 <= self.code <= 299

    def text(self):
        if self.decoded is None:
            charset = (self.headers.get_content_charset() if self.headers is not None else None) or "utf-8"
            try:
                self.decoded = self.body.decode(charset, errors="replace")
            except LookupError:
                self.decoded = self.body.decode("utf-8", errors="replace")
        return self.decoded

    def json(self):
        text = self.text()
        if not text.strip():
            raise self.lib.rt.error(f"The response is empty, so there's no JSON in it (its status is {self.code}).")
        try:
            value = json.loads(text)
        except ValueError as exc:
            where = f" ({exc.msg}, line {exc.lineno}, column {exc.colno})" if isinstance(exc, json.JSONDecodeError) else ""
            raise self.lib.rt.error(f"The response isn't JSON{where}. Use :text to see what came back.")
        return self.lib.from_json(value)

    def header(self, name):
        values = self.headers.get_all(self.lib.rt.text(name)) if self.headers is not None else None
        return ", ".join(values) if values else None

    def methods(self):
        return {"status": self.status, "ok": self.ok, "text": self.text, "json": self.json, "header": self.header}


class Lib:
    def __init__(self, rt):
        self.rt = rt
        self.context = None

    # ---- Tuff values and JSON
    def data(self, values=None):
        d = Data(self, {} if values is None else values)
        d.native = self.rt.native(DATA, d.methods(), d.show)
        d.native.tap = d
        return d.native

    def from_json(self, v):
        if isinstance(v, dict):
            return self.data({str(k): self.from_json(x) for k, x in v.items()})
        if isinstance(v, list):
            return [self.from_json(x) for x in v]
        return v

    def to_json(self, v, what, inside=()):
        """The Python value json.dumps needs for a Tuff value; what names the thing that holds it, for errors."""
        v = self.rt.plain(v)
        if v is None or isinstance(v, (bool, str)):
            return v
        if isinstance(v, (int, float)):
            if v != v or v in (float("inf"), float("-inf")):
                raise self.rt.error(f"{what} can't hold {self.rt.text(v)}: JSON only has ordinary numbers.")
            return v
        d = data_of(v)
        if isinstance(v, list) or d is not None:
            if any(x is v for x in inside):
                raise self.rt.error(f"{what} can't hold itself.")
            inside = (*inside, v)
            if d is not None:
                return {k: self.to_json(x, what, inside) for k, x in d.values.items()}
            return [self.to_json(x, what, inside) for x in v]
        raise self.rt.error(f"{what} can only hold text, numbers, true/false, nil, lists and data objects, not {self.rt.what(v)}.")

    # ---- sending a request
    def ssl_context(self):
        if self.context is None:
            if ssl is None:
                raise self.rt.error("This copy of Tuff can't use https:// web addresses, because its Python has no ssl module.")
            context = None
            if sys.platform == "darwin":  # a Mac Python (and a built app) often can't find the system's certificates
                try:
                    import certifi
                    context = ssl.create_default_context(cafile=certifi.where())
                except Exception:
                    pass
            if context is None:
                context = ssl.create_default_context()
                if sys.platform == "darwin" and os.path.isfile(MAC_CERTS):
                    try:
                        context.load_verify_locations(MAC_CERTS)
                    except Exception:
                        pass
            self.context = context
        return self.context

    def check_url(self, label, url):
        url = self.rt.plain(url)
        if not isinstance(url, str):
            raise self.rt.error(f"{label} needs a web address as text, like \"https://example.com\", not {self.rt.what(url)}.")
        url = url.strip()
        try:
            parts = urllib.parse.urlsplit(url)
            good = parts.scheme.lower() in ("http", "https") and bool(parts.hostname)
        except ValueError:
            good = False
        if not good:
            hint = f" Try \"https://{url}\"." if url and "://" not in url and " " not in url else ""
            raise self.rt.error(f"{label} needs a web address that starts with http:// or https://, not \"{url}\".{hint}")
        return urllib.parse.quote(url, safe=URL_SAFE)

    def header_pairs(self, label, headers):
        headers = self.rt.plain(headers)
        if headers is None:
            return []
        d = data_of(headers)
        if d is None:
            raise self.rt.error(f"{label}'s headers have to be a data object (make one with tap.data() and :set), not {self.rt.what(headers)}.")
        return [(name, self.rt.text(value)) for name, value in d.values.items()]

    def encode_body(self, label, body):
        body = self.rt.plain(body)
        if body is None:
            return None, None
        if isinstance(body, str):
            return body.encode("utf-8"), "text/plain; charset=utf-8"
        if isinstance(body, list) or data_of(body) is not None:
            return json.dumps(self.to_json(body, "What you send"), ensure_ascii=False).encode("utf-8"), "application/json"
        raise self.rt.error(f"{label} sends text, a data object or a list, not {self.rt.what(body)}. For a number, use text(...).")

    def why(self, reason, host):
        """A friendly line for what went wrong while connecting."""
        if isinstance(reason, socket.gaierror):
            return f"Couldn't find {host}. Check the web address and your internet connection."
        if isinstance(reason, (TimeoutError, socket.timeout)):
            return f"{host} didn't answer within {TIMEOUT} seconds."
        if ssl is not None and isinstance(reason, ssl.SSLCertVerificationError):
            return f"Couldn't check {host}'s security certificate, so tap didn't connect ({reason.verify_message})."
        if ssl is not None and isinstance(reason, ssl.SSLError):
            return f"Couldn't make a secure connection to {host} ({reason.reason or reason})."
        if isinstance(reason, ConnectionRefusedError):
            return f"{host} refused the connection. Check the web address (and its port)."
        if isinstance(reason, (ConnectionError, http.client.HTTPException)):
            return f"{host} closed the connection before it answered."
        if isinstance(reason, OSError):
            return f"Couldn't connect to {host}: {reason.strerror or reason}."
        return f"Couldn't connect to {host}: {reason}."

    def request(self, method, url, headers, body=None):
        label = f"tap.{method.lower()}"
        url = self.check_url(label, url)
        data, kind = self.encode_body(label, body)
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("User-Agent", AGENT)
        if kind:
            req.add_header("Content-Type", kind)
        for name, value in self.header_pairs(label, headers):  # after ours, so yours win
            req.add_header(name, value)
        host = urllib.parse.urlsplit(url).hostname
        # Made for http:// too when it can be, in case the server sends tap on to an https:// address.
        context = self.ssl_context() if ssl is not None or url.lower().startswith("https:") else None
        try:
            try:
                with urllib.request.urlopen(req, timeout=TIMEOUT, context=context) as resp:
                    return self.response(resp.status, resp.headers, resp.read())
            except urllib.error.HTTPError as err:  # 404, 500...: still an answer
                return self.response(err.code, err.headers, err.read() if err.fp is not None else b"")
        except urllib.error.URLError as err:
            raise self.rt.error(self.why(err.reason, host))
        except (OSError, http.client.HTTPException) as err:  # a timeout or a dropped connection while reading
            raise self.rt.error(self.why(err, host))
        except ValueError as err:  # e.g. a header with a new line in it
            raise self.rt.error(f"{label} couldn't send that: {err}")

    def response(self, status, headers, body):
        r = Response(self, status, headers, body)
        return self.rt.native("response", r.methods(), lambda nested=False: f"<response {r.code}>")

    # ---- what Tuff calls
    def get(self, url, headers=None):
        return self.request("GET", url, headers)

    def post(self, url, body, headers=None):
        return self.request("POST", url, headers, body)

    def put(self, url, body, headers=None):
        return self.request("PUT", url, headers, body)

    def delete(self, url, headers=None):
        return self.request("DELETE", url, headers)

    def new_data(self):
        return self.data()


def make_library(rt):
    lib = Lib(rt)
    fns = {"get": lib.get, "post": lib.post, "put": lib.put, "delete": lib.delete, "data": lib.new_data}
    return {name: rt.builtin(f"tap.{name}", fn) for name, fn in fns.items()}


def tables():
    """For tuff.py --check, without going online: tap's functions, and the methods of what it makes."""

    class FakeRt:
        def builtin(self, name, fn):
            return fn

    lib = Lib(FakeRt())
    return {"lib": make_library(FakeRt()),
            "kinds": {"response": Response(lib, 200, None, b"").methods(), DATA: Data(lib, {}).methods()}}
