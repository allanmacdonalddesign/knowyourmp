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
.hero{display:flex;gap:16px;align-items:center}.hero img{width:96px;height:120px;object-fit:cover;border-radius:8px;border:1px solid var(--line)}
.hero h1{margin:0}.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin:14px 0}
.stat{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 12px}.stat b{display:block;font-size:1.35rem}
.chip{display:inline-block;padding:1px 8px;border-radius:99px;border:1px solid var(--line);font-size:.8rem;margin:0 4px 0 0;color:var(--muted)}
.chip.good{border-color:var(--accent);color:var(--accent)}.item{padding:8px 0;border-top:1px solid var(--line)}.item:first-of-type{border-top:0}
.chips label{display:inline-block;font-weight:400;margin:3px 10px 3px 0}h2{font-size:1.15rem;margin:26px 0 4px}
.sticky{position:sticky;top:0;background:var(--bg);padding:8px 0;z-index:2}.hidden{display:none}button:disabled{opacity:.5;cursor:not-allowed}
"""

TOPIC_LABELS = {
    "housing": "Housing", "health": "Health", "climate_environment": "Climate & environment", "immigration": "Immigration",
    "justice": "Justice & public safety", "indigenous_affairs": "Indigenous affairs", "economy_cost_of_living": "Economy & cost of living",
    "defence_foreign_affairs": "Defence & foreign affairs", "transportation_infrastructure": "Transportation & infrastructure",
    "education_children_families": "Education, children & families", "seniors_pensions": "Seniors & pensions",
    "technology_privacy": "Technology & privacy", "agriculture_rural": "Agriculture & rural", "arts_culture_sport": "Arts, culture & sport",
    "democracy_government": "Democracy & government", "gender_equality_rights": "Gender equality & rights",
}
assert set(TOPIC_LABELS) == set(load_taxonomy()) - {"other"}, "web labels out of sync with civic/topics.json"


def page(title: str, body: str) -> bytes:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><style>{CSS}</style></head><body><main>{body}</main></body></html>""".encode()


def linkify(text: str) -> str:
    return re.sub(r"(https://[^\s<)]+)", r'<a href="\1" target="_blank" rel="noopener noreferrer">\1</a>', escape(text))


def home(msg: str = "", postal: str = "") -> bytes:
    err = f'<div class="note err">{escape(msg)}</div>' if msg else ""
    return page("Civic Leverage Tool", f"""<h1>Civic Leverage Tool</h1>
<p class="sub">Meet your MP, see what they actually do, then find where you can make a difference.</p>{err}
<form method="post" action="/mp">
<label for="postal">Where do you live? (postal code)</label><input type="text" id="postal" name="postal" value="{escape(postal)}" placeholder="M5V 3L9" required maxlength="10" autocomplete="off">
<p class="why">The first lookup for an MP can take a minute while it reads public records; after that it is fast. Your postal code is not stored or logged.</p>
<button type="submit">Find my MP</button></form>""")


def hidden(postal, interests, pick, extra: dict | None = None) -> str:
    fields = {"postal": postal, "pick": pick or ""}
    fields.update(extra or {})
    out = "".join(f'<input type="hidden" name="{k}" value="{escape(str(v))}">' for k, v in fields.items())
    return out + "".join(f'<input type="hidden" name="interests" value="{escape(i)}">' for i in interests)


def _topics_attr(topics) -> str:
    return escape(" ".join(t for t in topics if t != "other"))


def _item(topics, text: str, inner: str) -> str:
    return f'<div class="item" data-item data-topics="{_topics_attr(topics)}" data-text="{escape(text.lower())}">{inner}</div>'


def _link(url: str, label: str = "source") -> str:
    return f'<a href="{escape(url)}" target="_blank" rel="noopener noreferrer">{escape(label)}</a>'


def _tags(topics) -> str:
    return "".join(f'<span class="chip">{escape(TOPIC_LABELS.get(t, t))}</span>' for t in topics if t != "other")


FILTER_JS = """
const form=document.getElementById('filter'),q=document.getElementById('q'),items=[...document.querySelectorAll('[data-item]')],
 boxes=[...form.querySelectorAll('input[name=interests]')],go=document.getElementById('go'),count=document.getElementById('count');
function apply(){const want=boxes.filter(b=>b.checked).map(b=>b.value),text=q.value.trim().toLowerCase();let n=0;
 items.forEach(it=>{const t=(it.dataset.topics||'').split(' ').filter(Boolean);
  const ok=(!want.length||want.some(w=>t.includes(w)))&&(!text||it.dataset.text.includes(text));it.classList.toggle('hidden',!ok);if(ok)n++;});
 count.textContent=(want.length||text)?('Showing '+n+' of '+items.length+' items'):'';go.disabled=!want.length;}
form.addEventListener('input',apply);form.addEventListener('submit',e=>{if(!boxes.some(b=>b.checked))e.preventDefault();});apply();
"""


def card_page(c, postal, pick) -> bytes:
    from .analysis.card import RECENT_VOTES  # noqa: F401

    mp, p = c.mp, c.profile
    contact = []
    if mp.email:
        contact.append(f'<a href="mailto:{escape(mp.email)}">{escape(mp.email)}</a>')
    const = next((o for o in mp.offices if o.get("type") == "constituency"), None)
    if const:
        contact.append(escape(" ".join((const.get("postal") or "").split())) + (f" &middot; {escape(const['tel'])}" if const.get("tel") else ""))
    links = []
    if mp.ourcommons_url:
        links.append(_link(mp.ourcommons_url, "Official House of Commons page"))
    if c.slug:
        links.append(_link(f"https://openparliament.ca/politicians/{c.slug}/", "Full voting record"))
    photo = f'<img src="{escape(c.photo_url)}" alt="" referrerpolicy="no-referrer">' if c.photo_url else ""
    since = f" &middot; MP since {escape(c.mp_since[:4])}" if c.mp_since else ""
    hero = f"""<div class="hero">{photo}<div><h1>{escape(mp.name)}</h1><div>{escape(mp.party)} &middot; {escape(mp.riding)}{since}</div>
<div class="why">{' &middot; '.join(links)}</div><div class="why">{' &middot; '.join(contact)}</div></div></div>"""

    # --- stats
    stats = []
    if c.votes_total:
        y, n, pr = c.ballots_cast.get("Yes", 0), c.ballots_cast.get("No", 0), c.ballots_cast.get("Paired", 0)
        stats.append(f'<div class="stat"><b>{y} yes &middot; {n} no</b>on {c.votes_total} House votes this session ({pr} paired)</div>')
    with_p, comparable = c.party_line
    if comparable:
        against = comparable - with_p
        stats.append(f'<div class="stat"><b>{with_p} of {comparable} with their party</b>in their {len(c.recent)} most recent votes'
                     + (f" ({against} against)" if against else "") + "</div>")
    if c.bills:
        stats.append(f'<div class="stat"><b>{sum(1 for b in c.bills if b.became_law)} became law</b>of {len(c.bills)} bills they sponsored (all sessions on record)</div>')
    else:
        stats.append('<div class="stat"><b>No sponsored bills</b>on record</div>')
    discipline = ('<div class="note">In Canada MPs almost always vote with their party, so a voting record says less than what an MP chooses to '
                  "speak about and sponsor. That is why the sections below separate those choices from votes.</div>")

    # --- topic chips with how much the MP has done on each
    counts: dict[str, int] = {}
    for topics in ([x.topics for x in p.champions if x.quote] + [x.topics for x in c.recent] + list(c.bill_topics.values())):
        for t in set(topics) - {"other"}:
            counts[t] = counts.get(t, 0) + 1
    tagged = bool(counts) or any(x.topics for x in p.champions)
    boxes = "".join(
        f'<label><input type="checkbox" name="interests" value="{escape(k)}"{"" if tagged else " disabled"}> {escape(v)}'
        f'{f" <span class=why>({counts[k]})</span>" if counts.get(k) else ""}</label>'
        for k, v in TOPIC_LABELS.items()
    )
    notag = "" if tagged else '<p class="why">Topic filtering needs ANTHROPIC_API_KEY set when the server starts.</p>'
    filt = f"""<div class="sticky"><form id="filter" method="post" action="/opportunities" class="card">
<input type="hidden" name="postal" value="{escape(postal)}"><input type="hidden" name="pick" value="{escape(str(pick or ''))}">
<label for="q" style="margin-top:0">What do you care about? Filter {escape(mp.name)}'s record</label>
<input type="text" id="q" placeholder="Search words, e.g. rent, clinics, transit" autocomplete="off">
<div class="chips" style="margin-top:6px">{boxes}</div>{notag}
<div class="why" id="count"></div>
<button type="submit" id="go" disabled style="margin-top:8px">Find ways to act on these topics &rarr;</button></form></div>"""

    # --- sections
    bills_html = ""
    for b in c.bills:
        topics = c.bill_topics.get(b.url, [])
        badge = '<span class="chip good">became law</span>' if b.became_law else ""
        kind = "private member's bill" if b.is_private_member_bill else "government bill"
        bills_html += _item(topics, f"{b.number} {b.title}", f"<div>{badge}<strong>Bill {escape(b.number)}</strong>: {escape(b.title)}</div>"
                            f'<div class="why">{kind}, {escape(b.session)}: {escape(b.status)} &middot; {_tags(topics)} {_link("https://openparliament.ca" + b.url)}</div>')
    bills_html = bills_html or '<p class="why">No sponsored bills on record.</p>'

    stmts = [x for x in p.champions if x.quote]
    stmts_html = "".join(
        _item(x.topics, x.text + " " + x.quote, f"<div>{escape(x.text)}</div><div class=\"why\">{escape(x.quote[:200])}{'…' if len(x.quote) > 200 else ''} &middot; {_tags(x.topics)} {_link(x.url)}</div>")
        for x in stmts) or '<p class="why">No members\' statements on record.</p>'

    def vote_row(v) -> str:
        side = {True: '<span class="chip good">with party</span>', False: '<span class="chip">against party</span>', None: ""}[v.with_party]
        return _item(v.topics, v.description, f'<div><span class="chip">{escape(v.ballot)}</span>{side}{escape(v.description)}</div>'
                     f'<div class="why">{escape(v.date)} &middot; {escape(v.result)} &middot; {_tags(v.topics)} {_link("https://openparliament.ca" + v.url)}</div>')
    shown = "".join(vote_row(v) for v in c.recent[:10])
    more = "".join(vote_row(v) for v in c.recent[10:])
    votes_html = shown + (f"<details><summary>Show {len(c.recent) - 10} more votes</summary>{more}</details>" if more else "")
    votes_html = votes_html or '<p class="why">No votes on record.</p>'

    roles = "".join(f"<li>{escape(x.text)}</li>" for x in p.responsible_for)
    other = ", ".join(f"{escape(k)} ({n})" for k, n in p.assigned_activity.most_common(5))
    notes = "".join(f'<div class="note">{escape(n)}</div>' for n in c.notes + p.notes)

    body = f"""{hero}<div class="stats">{"".join(stats)}</div>{discipline}{notes}{filt}
<h2>Bills they've sponsored</h2><div class="why">Whether they became law is shown on each bill.</div>{bills_html}
<h2>What they choose to speak about</h2><div class="why">Members' statements are 60-second speeches each MP picks the subject of.</div>{stmts_html}
<h2>Recent votes</h2><div class="why">Newest first. "Against party" means they voted differently from their party's position.</div>{votes_html}
<h2>Roles and committees</h2><div class="why">Assigned by position or party, so weighted lightly as a sign of personal interest.</div><ul>{roles}</ul>
{f'<div class="why">Other activity: {other}</div>' if other else ''}
<p style="margin-top:28px"><a href="/">&larr; Look up another postal code</a></p><script>{FILTER_JS}</script>"""
    return page(f"{mp.name}", body)


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
    body += f'<form method="post" action="/mp">{hidden(postal, [], pick)}<button class="alt" type="submit">&larr; Back to {escape(r.mp.name)}</button></form>'
    return page("Opportunities", body)


def choose_riding(e: service.SplitPostcode, postal) -> bytes:
    opts = "".join(
        f'<label><input type="radio" name="pick" value="{i}" required> {escape(m.name)} ({escape(m.party)}), {escape(m.riding)}</label>'
        for i, m in enumerate(e.mps, 1)
    )
    return page("Choose your riding", f'<h1>Which riding are you in?</h1><p class="sub">{escape(str(e))}</p>'
                f'<form method="post" action="/mp"><input type="hidden" name="postal" value="{escape(postal)}">{opts}<br><button type="submit">Continue</button></form>')


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
            if self.path == "/mp":
                return self._send(card_page(service.card(postal, pick), postal, pick))
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
            return self._send(choose_riding(e, postal))
        except service.UserError as e:
            return self._send(home(str(e), postal), 400)
        except Exception:
            return self._send(home("Something went wrong reading the public records. Please try again in a minute.", postal), 500)


def serve(port: int = 8000):
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)  # localhost only
    print(f"Open http://127.0.0.1:{port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
