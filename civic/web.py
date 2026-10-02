"""Tiny local web UI (stdlib only). Runs on this machine; nothing is stored or logged, nothing is sent anywhere."""
import re
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from . import service
from .analysis.classify import load_taxonomy

CSS = """
:root{--bg:#fff;--fg:#1d2327;--muted:#5b6770;--card:#f5f6f7;--line:#d6dadd;--accent:#1f5fbf}
@media (prefers-color-scheme:dark){:root{--bg:#14181b;--fg:#e8eaec;--muted:#98a2ab;--card:#1d2226;--line:#333b41;--accent:#7ab0ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif}
main{max-width:760px;margin:0 auto;padding:24px 16px 64px}h1{font-size:1.5rem;margin:0 0 4px}
p.sub{color:var(--muted);margin:0 0 20px}a{color:var(--accent)}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px 16px;margin:14px 0}
.why{color:var(--muted);font-size:.92rem}.score{font-weight:700;color:var(--accent)}
label{display:block;margin:10px 0 4px;font-weight:600}input[type=text],textarea{width:100%;padding:8px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg);font:inherit}
textarea{min-height:90px}button{font:inherit;padding:8px 14px;border-radius:6px;border:1px solid var(--accent);background:var(--accent);color:var(--bg);cursor:pointer}
button.alt{background:transparent;color:var(--accent)}.topics label{display:inline-block;font-weight:400;margin:4px 14px 4px 0}
pre{white-space:pre-wrap;word-wrap:break-word;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px;font:inherit}
.note{border-left:4px solid var(--accent);padding:6px 12px;margin:14px 0;color:var(--muted)}.err{border-color:#c0392b;color:inherit}
details{margin-top:8px}summary{cursor:pointer;color:var(--accent)}
"""

TOPIC_LABELS = {k: k.replace("_", " ").replace("economy cost of living", "economy / cost of living") for k in load_taxonomy() if k != "other"}


def page(title: str, body: str) -> bytes:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><style>{CSS}</style></head><body><main>{body}</main></body></html>""".encode()


def linkify(text: str) -> str:
    return re.sub(r"(https://[^\s<)]+)", r'<a href="\1" target="_blank" rel="noopener noreferrer">\1</a>', escape(text))


def home(msg: str = "", postal: str = "", chosen: set[str] | None = None) -> bytes:
    chosen = chosen or set()
    boxes = "".join(
        f'<label><input type="checkbox" name="interests" value="{escape(k)}"{" checked" if k in chosen else ""}> {escape(v)}</label>'
        for k, v in TOPIC_LABELS.items()
    )
    err = f'<div class="note err">{escape(msg)}</div>' if msg else ""
    return page("Civic Leverage Tool", f"""<h1>Civic Leverage Tool</h1>
<p class="sub">Where can you, specifically, still change an outcome, and what should you do?</p>{err}
<form method="post" action="/opportunities">
<label for="postal">Your postal code</label><input type="text" id="postal" name="postal" value="{escape(postal)}" placeholder="M5V 3L9" required maxlength="10" autocomplete="off">
<label>What do you care about?</label><div class="topics">{boxes}</div>
<p class="why">The first search can take a few minutes while it reads public records (later ones are fast). Your postal code is not stored or logged.</p>
<button type="submit">Find opportunities</button></form>""")


def hidden(postal, interests, pick, extra: dict | None = None) -> str:
    fields = {"postal": postal, "pick": pick or ""}
    fields.update(extra or {})
    out = "".join(f'<input type="hidden" name="{k}" value="{escape(str(v))}">' for k, v in fields.items())
    return out + "".join(f'<input type="hidden" name="interests" value="{escape(i)}">' for i in interests)


def results(r: service.Ranked, postal, interests, pick) -> bytes:
    cards = []
    for n, o in enumerate(r.shown[:12], 1):
        reasons = escape("; ".join(o.reasons))
        deadline = f" &middot; deadline {o.deadline}" if o.deadline else ""
        actions = ""
        if o.kind in ("committee_study", "bill"):
            actions += f'<form method="post" action="/letter" style="display:inline">{hidden(postal, interests, pick, {"item": n})}' \
                       f'<details><summary>Draft a letter to {escape(r.mp.name)}</summary><label>Why does this matter to you? (your own words)</label>' \
                       f'<textarea name="why"></textarea><button type="submit">Draft letter</button></details></form>'
        if o.kind == "committee_study":
            actions += f'<form method="post" action="/brief" style="margin-top:8px">{hidden(postal, interests, pick, {"item": n})}<button class="alt" type="submit">How to submit a brief</button></form>'
        cards.append(f"""<div class="card"><div><span class="score">{o.score}</span> &nbsp;<strong>{escape(o.title)}</strong></div>
<div class="why">{escape(o.kind.replace('_', ' '))}; {escape(o.detail)}{deadline}</div>
<p class="why"><strong>Ranked high because:</strong> {reasons}</p>
<p><strong>Do this:</strong> {escape(o.action)}</p>
<p><a href="{escape(o.url)}" target="_blank" rel="noopener noreferrer">Official page</a></p>{actions}</div>""")
    body = f'<h1>Opportunities for {escape(r.mp.name)}</h1><p class="sub">{escape(r.mp.party)}, {escape(r.mp.riding)}</p>'
    body += "".join(cards) or '<div class="note">Nothing open matches those interests right now. Try other interests.</div>'
    body += '<p><a href="/">&larr; Start over</a></p>'
    return page("Opportunities", body)


def choose_riding(e: service.SplitPostcode, postal, interests) -> bytes:
    opts = "".join(
        f'<label><input type="radio" name="pick" value="{i}" required> {escape(m.name)} ({escape(m.party)}), {escape(m.riding)}</label>'
        for i, m in enumerate(e.mps, 1)
    )
    return page("Choose your riding", f'<h1>Which riding are you in?</h1><p class="sub">{escape(str(e))}</p>'
                f'<form method="post" action="/opportunities">{hidden(postal, interests, None)}{opts}<br><button type="submit">Continue</button></form>')


def text_page(title: str, text: str, editable: bool = False) -> bytes:
    if editable:
        body = f'<h1>{escape(title)}</h1><div class="note">This is a starting point. Rewrite it in your own words (you can edit it right here), fill in the [brackets], and send it yourself. Nothing is sent from this page.</div><textarea style="min-height:420px" spellcheck="true">{escape(text)}</textarea>'
    else:
        body = f"<h1>{escape(title)}</h1><pre>{linkify(text)}</pre>"
    return page(title, body + '<p><a href="javascript:history.back()">&larr; Back to results</a></p>')


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # never log requests: they contain postal codes
        pass

    def _send(self, body: bytes, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def _host_ok(self) -> bool:  # guards against DNS-rebinding attacks on a local server
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost")

    def do_GET(self):
        if not self._host_ok():
            return self._send(page("Forbidden", "<h1>Forbidden</h1>"), 403)
        if self.path == "/":
            return self._send(home())
        self._send(page("Not found", "<h1>Not found</h1>"), 404)

    def do_POST(self):
        if not self._host_ok():
            return self._send(page("Forbidden", "<h1>Forbidden</h1>"), 403)
        length = min(int(self.headers.get("Content-Length") or 0), 20000)
        form = parse_qs(self.rfile.read(length).decode("utf-8", "replace"))
        one = lambda k, d="": (form.get(k) or [d])[0].strip()
        postal, interests = one("postal"), form.get("interests", [])
        pick = int(one("pick")) if one("pick").isdigit() else None
        try:
            if not interests:
                raise service.UserError("Pick at least one thing you care about.")
            r = service.rank(postal, ",".join(interests), pick)
            if self.path == "/opportunities":
                return self._send(results(r, postal, interests, pick))
            n = int(one("item", "0") or 0)
            if self.path == "/letter":
                return self._send(text_page("Draft letter", service.letter_text(r, n, one("why")), editable=True))
            if self.path == "/brief":
                return self._send(text_page("How to submit a brief", service.brief_text(r, n)))
            return self._send(page("Not found", "<h1>Not found</h1>"), 404)
        except service.SplitPostcode as e:
            return self._send(choose_riding(e, postal, interests))
        except service.UserError as e:
            return self._send(home(str(e), postal, set(interests)), 400)
        except Exception:
            return self._send(home("Something went wrong reading the public records. Please try again in a minute.", postal, set(interests)), 500)


def serve(port: int = 8000):
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)  # localhost only
    print(f"Open http://127.0.0.1:{port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
