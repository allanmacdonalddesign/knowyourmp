"""Local web UI (stdlib only): postal code -> MP baseball card. Runs on this machine; nothing stored, logged or sent.

Design: mint paper, deep-green ink, hairline-bordered boxes, mono labels with arrows, big light type.
No external fonts, scripts or images from third parties except the MP's official photo.
"""
import re
from datetime import date
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from . import service

TOPIC_LABELS = {
    "housing": "Housing", "health": "Health", "climate_environment": "Climate & environment", "immigration": "Immigration",
    "justice": "Justice & public safety", "indigenous_affairs": "Indigenous affairs", "economy_cost_of_living": "Economy & cost of living",
    "defence_foreign_affairs": "Defence & foreign affairs", "transportation_infrastructure": "Transportation & infrastructure",
    "education_children_families": "Education, children & families", "seniors_pensions": "Seniors & pensions",
    "technology_privacy": "Technology & privacy", "agriculture_rural": "Agriculture & rural", "arts_culture_sport": "Arts, culture & sport",
    "democracy_government": "Democracy & government", "gender_equality_rights": "Gender equality & rights",
}

CSS = """
:root{--bg:#e7f1ec;--ink:#1c4a3a;--soft:#4b7566;--line:#2d7a62;--wash:rgba(255,255,255,.45);--paper:#fff;
--sans:"Manrope","Inter",ui-sans-serif,system-ui,-apple-system,"Helvetica Neue",Arial,sans-serif;
--mono:"JetBrains Mono","SF Mono",ui-monospace,Menlo,Consolas,monospace}
@media (prefers-color-scheme:dark){:root{--bg:#0e1b16;--ink:#bfe6d3;--soft:#85b5a0;--line:#2c6b55;--wash:rgba(255,255,255,.05);--paper:#0e1b16}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}body{overflow-wrap:break-word}
body{margin:0;background:var(--bg);color:var(--ink);font:300 17px/1.55 var(--sans)}
a{color:inherit}.wrap{max-width:1560px;margin:0 auto;border-left:1px solid var(--line);border-right:1px solid var(--line)}
.mono{font-family:var(--mono);text-transform:uppercase;letter-spacing:.09em;font-size:.74rem;font-weight:400}
.soft{color:var(--soft)}.fine{font-size:.78rem;color:var(--soft);margin-top:6px;line-height:1.45}
.grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));border-top:1px solid var(--line)}
.cell{border-right:1px solid var(--line);border-bottom:1px solid var(--line);padding:30px 32px;min-width:0}
.cell:last-child{border-right:0}.s12{grid-column:span 12;border-right:0}.s8{grid-column:span 8}.s6{grid-column:span 6}.s4{grid-column:span 4}.s3{grid-column:span 3}.s5{grid-column:span 5}.s7{grid-column:span 7}
.hidden{display:none!important}
.topbar{display:flex;flex-wrap:wrap;gap:6px 16px;justify-content:space-between;align-items:center;padding:18px 32px;border-bottom:1px solid var(--line)}
.topbar a{text-decoration:none}
.bar{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:20px 32px;border-bottom:1px solid var(--line);background:var(--wash);text-decoration:none;color:inherit;cursor:pointer;border-left:0;border-top:0;border-right:0;width:100%;font:inherit}
a.bar:hover,button.bar:hover{background:var(--ink);color:var(--bg)}
.arrow{font-family:var(--mono);font-size:1.1rem}
.name{font-size:clamp(2.8rem,7.4vw,6.4rem);font-weight:300;line-height:.98;letter-spacing:-.03em;margin:14px 0 18px}
.lead{font-size:clamp(1.2rem,2.2vw,1.7rem);font-weight:300;line-height:1.35;margin:0 0 6px;max-width:30ch}
.big{overflow-wrap:anywhere;font-size:clamp(2.6rem,5.2vw,4.6rem);font-weight:300;line-height:1;letter-spacing:-.03em;margin:14px 0 10px}
.photo{padding:0;position:relative;min-height:340px;background:var(--wash)}
.photo img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;filter:grayscale(1) contrast(1.05)}
.photo .tag{position:absolute;left:24px;bottom:24px;background:var(--paper);color:#111;padding:12px 20px;border:1px solid var(--ink);text-decoration:none}
.photo .initials{position:absolute;inset:0;display:grid;place-items:center;font-size:6rem;font-weight:200;color:var(--soft)}
.marq{overflow:hidden;white-space:nowrap;border-bottom:1px solid var(--line);padding:22px 0}
.marq .t{display:inline-flex;animation:slide 32s linear infinite}
.marq span{font-size:clamp(3rem,9vw,7.5rem);font-weight:500;letter-spacing:-.02em;text-transform:uppercase;line-height:1;padding-right:.6em}
.marq span.o{color:transparent;-webkit-text-stroke:1.5px var(--ink);font-weight:300}
@keyframes slide{to{transform:translateX(-50%)}}
@media (prefers-reduced-motion:reduce){.marq .t{animation:none}}
.sec{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;gap:8px 16px;padding:22px 32px;border-bottom:1px solid var(--line);border-top:1px solid var(--line)}
.sec h2{margin:0;font-size:clamp(1.6rem,3.2vw,2.6rem);font-weight:300;letter-spacing:-.02em}
.item{padding:20px 0;border-top:1px solid var(--line)}.item:first-child{border-top:0;padding-top:4px}
.item p{margin:0 0 6px;font-size:1.12rem;line-height:1.4;font-weight:400}
.meta{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center}
.tagz{display:inline-block;border:1px solid var(--line);padding:2px 9px;font-family:var(--mono);font-size:.68rem;letter-spacing:.06em;text-transform:uppercase;margin:2px 6px 2px 0}
.tagz.fill{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.glance p{font-size:clamp(1.15rem,1.9vw,1.5rem);line-height:1.35;margin:0;font-weight:300}
sup a{font-family:var(--mono);font-size:.62rem;text-decoration:none;margin-left:2px;border-bottom:1px solid var(--line)}
.filter{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line)}
.filter input[type=text]{width:100%;background:transparent;border:0;border-bottom:1px solid var(--ink);color:var(--ink);font:300 clamp(1.3rem,2.4vw,2rem)/1.3 var(--sans);padding:6px 0 10px;outline:0}
.filter input[type=text]::placeholder{color:var(--soft)}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}
.chip{cursor:pointer}.chip input{position:absolute;opacity:0;pointer-events:none}
.chip span{display:inline-block;border:1px solid var(--ink);padding:6px 12px;font-family:var(--mono);font-size:.72rem;letter-spacing:.05em;text-transform:uppercase}
.chip input:checked+span{background:var(--ink);color:var(--bg)}.chip input:focus-visible+span{outline:2px solid var(--ink);outline-offset:2px}
.chip.off span{opacity:.35;cursor:not-allowed}
details summary{cursor:pointer;list-style:none;padding:14px 0}details summary::-webkit-details-marker{display:none}
.note{border:1px solid var(--ink);padding:14px 18px;margin:0 0 14px;background:var(--wash)}
input.postal{width:100%;background:transparent;border:0;border-bottom:2px solid var(--ink);color:var(--ink);font:300 clamp(2.4rem,7vw,5.5rem)/1.1 var(--sans);letter-spacing:.04em;padding:6px 0 14px;outline:0;text-transform:uppercase}
input.postal::placeholder{color:var(--soft);opacity:.6}
.radio{display:flex;gap:16px;align-items:center;padding:22px 32px;border-bottom:1px solid var(--line);cursor:pointer}.radio:hover{background:var(--wash)}
.radio input{accent-color:var(--ink);width:20px;height:20px}
@media (max-width:600px){.big{font-size:2.2rem}.name{font-size:clamp(2.4rem,13vw,3.4rem)}.cell{padding:22px 18px}.chip span{padding:5px 9px}}
@media (max-width:900px){.s8,.s6,.s4,.s5,.s7{grid-column:span 12}.s3{grid-column:span 6}.cell{border-right:0;padding:24px 20px}.topbar,.sec,.bar,.radio{padding-left:20px;padding-right:20px}.photo{min-height:300px}
.s3.cell:nth-child(odd){border-right:1px solid var(--line)}}
"""


def page(title: str, body: str) -> bytes:
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="referrer" content="no-referrer"><title>{escape(title)}</title><style>{CSS}</style></head>'
            f'<body><div class="wrap">{body}</div></body></html>').encode()


def marquee(word: str) -> str:
    unit = "".join(f'<span>{escape(word)}</span><span class="o">{escape(word)}</span>' for _ in range(2))
    return f'<div class="marq" aria-hidden="true"><div class="t">{unit}{unit}</div></div>'


def topbar(right: str = "") -> str:
    return f'<div class="topbar mono"><a href="/">MP Card</a><span class="soft">{right}</span></div>'


def link(url: str, label: str = "Source") -> str:
    return f'<a class="mono" href="{escape(url)}" target="_blank" rel="noopener noreferrer">{escape(label)} &#8599;</a>'


# ---------------------------------------------------------------- home / split riding
def home(msg: str = "", postal: str = "") -> bytes:
    err = f'<div class="note mono">{escape(msg)}</div>' if msg else ""
    return page("MP Card", f"""{topbar("Meet your MP")}
<div class="grid"><div class="cell s12" style="padding-top:56px;padding-bottom:56px">
<div class="mono soft">Your MP, as a baseball card</div>
<h1 class="name" style="font-size:clamp(3.4rem,10vw,9rem)">Meet<br>your MP.</h1>
<p class="lead">What they vote for, what they speak up about, what they put their name on. In plain words, with receipts.</p></div></div>
<form method="post" action="/mp"><div class="grid">
<div class="cell s8">{err}<label for="postal" class="mono soft">Where do you live? Postal code</label>
<input class="postal" id="postal" name="postal" value="{escape(postal)}" placeholder="M5V 3L9" required maxlength="10" autocomplete="off" autofocus>
<div class="fine">The first lookup for an MP can take a minute or two while it reads public records. After that it is fast. Your postal code is never stored or logged.</div></div>
<div class="cell s4" style="padding:0"><button class="bar mono" type="submit" style="height:100%;min-height:120px;border-bottom:0;font-size:.9rem">Find my MP <span class="arrow">&#8599;</span></button></div></div></form>
{marquee("Know your MP")}
<div class="grid"><div class="cell s12 mono soft" style="border-bottom:0">Data: openparliament.ca, ourcommons.ca, Parliament of Canada. Nonpartisan: every MP gets the same card.</div></div>""")


def choose_riding(e: service.SplitPostcode, postal) -> bytes:
    opts = "".join(
        f'<label class="radio"><input type="radio" name="pick" value="{i}" required><span><strong style="font-weight:400">{escape(m.name)}</strong>'
        f' <span class="soft">&middot; {escape(m.party)} &middot; {escape(m.riding)}</span></span></label>'
        for i, m in enumerate(e.mps, 1))
    return page("Choose your riding", f"""{topbar("One more step")}
<div class="grid"><div class="cell s12"><div class="mono soft">Split postal code</div><h1 class="name">Which riding<br>are you in?</h1><p class="lead">{escape(str(e))}</p></div></div>
<form method="post" action="/mp"><input type="hidden" name="postal" value="{escape(postal)}">{opts}
<button class="bar mono" type="submit">Continue <span class="arrow">&#8599;</span></button></form>""")


# ---------------------------------------------------------------- the card
def _topics_attr(topics) -> str:
    return escape(" ".join(t for t in topics if t != "other"))


def _tags(topics) -> str:
    return "".join(f'<span class="tagz">{escape(TOPIC_LABELS.get(t, t))}</span>' for t in topics if t != "other")


FILTER_JS = """
const form=document.getElementById('filter'),q=document.getElementById('q'),items=[...document.querySelectorAll('[data-item]')],
 boxes=[...form.querySelectorAll('input[name=topic]:not(:disabled)')],count=document.getElementById('count');
function apply(){const want=boxes.filter(b=>b.checked).map(b=>b.value),text=q.value.trim().toLowerCase();let n=0;
 items.forEach(it=>{const t=(it.dataset.topics||'').split(' ').filter(Boolean);
  const ok=(!want.length||want.some(w=>t.includes(w)))&&(!text||it.dataset.text.includes(text));it.classList.toggle('hidden',!ok);if(ok)n++;});
 count.textContent=(want.length||text)?('Showing '+n+' of '+items.length):'';}
form.addEventListener('input',apply);form.addEventListener('submit',e=>e.preventDefault());apply();
"""


def identity_line(c) -> str:
    """One line on who this MP is: what they choose to talk about, plus where they sit."""
    p = c.profile
    counts: dict[str, int] = {}
    for x in p.champions:
        for t in x.topics:
            if t != "other":
                counts[t] = counts.get(t, 0) + 1
    for topics in c.bill_topics.values():
        for t in topics:
            if t != "other":
                counts[t] = counts.get(t, 0) + 1
    top = [TOPIC_LABELS.get(t, t) for t, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:2]]
    codes = [m.group(1) for x in p.responsible_for if (m := re.search(r"\(([A-Z]{3,6})\)$", x.text))]
    parts = []
    if top:
        parts.append("Chooses to speak about " + " and ".join(top).lower())
    if codes:
        parts.append("Sits on " + ", ".join(codes))
    return (". ".join(parts) + ".") if parts else ""


def card_page(c, postal, pick) -> bytes:
    mp, p = c.mp, c.profile

    def item_attrs(topics, text):
        return f'data-item data-topics="{_topics_attr(topics)}" data-text="{escape(text.lower())}"'

    # --- hero
    if c.photo_url:
        photo = f'<img src="{escape(c.photo_url)}" alt="" referrerpolicy="no-referrer">'
    else:
        photo = f'<div class="initials">{escape("".join(w[0] for w in mp.name.split()[:2]))}</div>'
    tag = f'<a class="tag mono" href="{escape(mp.ourcommons_url)}" target="_blank" rel="noopener noreferrer">Official page &#8599;</a>' if mp.ourcommons_url else ""
    ident = identity_line(c)
    since = f"MP since {escape(c.mp_since[:4])}" if c.mp_since else ""
    notes = "".join(f'<div class="note" style="margin-top:18px">{escape(n)}</div>' for n in c.notes + p.notes)
    contact = []
    if mp.email:
        contact.append(f'<a class="bar mono" href="mailto:{escape(mp.email)}">Email {escape(mp.email)} <span class="arrow">&#8599;</span></a>')
    if c.slug:
        contact.append(f'<a class="bar mono" href="https://openparliament.ca/politicians/{escape(c.slug)}/" target="_blank" rel="noopener noreferrer">Full voting record <span class="arrow">&#8599;</span></a>')
    const = next((o for o in mp.offices if o.get("type") == "constituency"), None)
    office = ""
    if const:
        addr = escape(" ".join((const.get("postal") or "").split()))
        tel = f" &middot; {escape(const['tel'])}" if const.get("tel") else ""
        office = f'<div class="fine" style="margin-top:14px">Constituency office: {addr}{tel}</div>'
    hero = f"""{topbar("MP card")}
<div class="grid"><div class="cell photo s4">{photo}{tag}</div>
<div class="cell s8" style="padding:0;display:flex;flex-direction:column;justify-content:space-between">
<div style="padding:30px 32px 24px"><div class="mono soft">Your MP &middot; {escape(mp.party)} &middot; {escape(mp.riding)}</div>
<h1 class="name">{escape(mp.name)}</h1>{f'<p class="lead">{escape(ident)}</p>' if ident else ''}{notes}{office}</div>
<div>{"".join(contact)}</div></div></div>"""

    # --- stat boxes
    boxes = []
    if c.mp_since:
        yrs = max(0.0, (date.today() - date.fromisoformat(c.mp_since)).days / 365.25)
        boxes.append(("Time in office", f"{yrs:.0f}<span style='font-size:.4em'> yrs</span>" if yrs >= 1.5 else "&lt;2<span style='font-size:.4em'> yrs</span>", since))
    if c.votes_total:
        y, n = c.ballots_cast.get("Yes", 0), c.ballots_cast.get("No", 0)
        boxes.append(("House votes", f"{y}<span style='font-size:.4em'> yes</span> {n}<span style='font-size:.4em'> no</span>", f"of {c.votes_total} this session"))
    wp, comparable = c.party_line
    if comparable:
        boxes.append(("With their party", f"{wp}<span style='font-size:.4em'> of {comparable}</span>", f"in their {len(c.recent)} most recent votes"))
    law = sum(1 for b in c.bills if b.became_law)
    boxes.append(("Bills sponsored", f"{len(c.bills)}", f"{law} became law" if c.bills else "none on record"))
    stat_html = "".join(f'<div class="cell s3"><div class="mono soft">{escape(lbl)}</div><div class="big">{val}</div><div class="fine">{escape(sub)}</div></div>' for lbl, val, sub in boxes)

    # --- at a glance
    def refs(ids) -> str:
        return "".join(f'<sup><a href="{escape(c.ref_links[i][1])}" target="_blank" rel="noopener noreferrer" title="{escape(c.ref_links[i][0])}">{n}</a></sup>'
                       for n, i in enumerate(ids, 1) if i in c.ref_links)

    glance = ""
    if c.overview:
        span = "s6" if len(c.overview) > 1 else "s12"
        glance = (f'<div class="sec"><h2>At a glance</h2><span class="mono soft">AI-written from the linked records</span></div>'
                  f'<div class="grid glance">' + "".join(f'<div class="cell {span if i < 2 else "s6"}"><p>{escape(x["text"])}{refs(x["refs"])}</p></div>' for i, x in enumerate(c.overview))
                  + '</div>')

    # --- filter
    counts: dict[str, int] = {}
    for topics in ([x.topics for x in p.champions if x.quote] + [kv.topics for kv in c.key_votes] + list(c.bill_topics.values())):
        for t in set(topics) - {"other"}:
            counts[t] = counts.get(t, 0) + 1
    tagged = bool(counts)
    chips = "".join(
        f'<label class="chip{"" if tagged else " off"}"><input type="checkbox" name="topic" value="{escape(k)}"{"" if tagged else " disabled"}>'
        f'<span>{escape(v)}{f" &middot; {counts[k]}" if counts.get(k) else ""}</span></label>' for k, v in TOPIC_LABELS.items())
    notag = "" if tagged else '<div class="fine">Topic filters need ANTHROPIC_API_KEY set when the server starts. Search by words still works.</div>'
    filt = f"""<div class="filter"><form id="filter" class="cell s12" style="border-bottom:0">
<label for="q" class="mono soft">What do you care about? Filter {escape(mp.name)}'s record</label>
<input type="text" id="q" placeholder="Try: rent, clinics, transit&hellip;" autocomplete="off">
<div class="chips">{chips}</div>{notag}<div class="mono soft" id="count" style="margin-top:12px;min-height:1em"></div></form></div>"""

    # --- votes
    def kv_row(v) -> str:
        stage = "Final vote" if v.stage == "3rd reading" else "Moved forward (2nd reading)"
        result = "Passed" if v.result == "Passed" else v.result
        return (f'<div class="item" {item_attrs(v.topics, v.plain + " " + v.legal_title)}><p>{escape(v.plain)}</p>'
                f'<div class="meta"><span class="mono soft">Bill {escape(v.number)} &middot; {stage} &middot; {escape(v.date)} &middot; {escape(result)}</span>'
                f'{link("https://openparliament.ca" + v.vote_url, "Vote record")}</div><div>{_tags(v.topics)}</div>'
                f'<div class="fine">Official title: {escape(v.legal_title)}</div></div>')

    def kv_col(title: str, sub: str, vs) -> str:
        body = "".join(kv_row(v) for v in vs[:5]) or '<div class="soft">None on record.</div>'
        rest = "".join(kv_row(v) for v in vs[5:])
        more = f'<details><summary class="mono">Show {len(vs) - 5} more &#8599;</summary>{rest}</details>' if rest else ""
        return (f'<div class="cell s6"><div class="mono soft">{escape(title)} &middot; {len(vs)}</div>'
                f'<div class="fine" style="margin:6px 0 18px">{escape(sub)}</div>{body}{more}</div>')

    if c.key_votes:
        votes = (f'<div class="sec"><h2>How they voted</h2><span class="mono soft">Votes that decided a bill &middot; {c.other_votes} other votes on amendments and procedure not shown</span></div>'
                 f'<div class="grid">{kv_col("Voted for", "Yes on the bill.", c.backed)}'
                 f'{kv_col("Voted against", "No on the bill. It does not mean they oppose everything in it, and MPs usually follow their party.", c.opposed)}</div>'
                 '<div class="grid"><div class="cell s12 fine" style="border-bottom:1px solid var(--line)">Plain-language descriptions are written by AI from Parliament\'s official summary of each bill. The official title is under each one.</div></div>')
    else:
        votes = '<div class="sec"><h2>How they voted</h2></div><div class="grid"><div class="cell s12 soft">No bill-deciding votes on record this session.</div></div>'

    # --- sponsored bills
    bill_cells = ""
    for b in c.bills:
        topics = c.bill_topics.get(b.url, [])
        txt = c.bill_plain.get(b.url) or b.title
        law_tag = '<span class="tagz fill">Became law</span>' if b.became_law else ""
        bill_cells += (f'<div class="cell s6" {item_attrs(topics, b.number + " " + txt + " " + b.title)}><p style="margin:0 0 8px;font-size:1.2rem;font-weight:400;line-height:1.35">{escape(txt)}</p>'
                       f'<div class="meta"><span class="mono soft">Bill {escape(b.number)} &middot; {escape(b.session)} &middot; {escape(b.status)}</span>{link("https://openparliament.ca" + b.url, "Bill")}</div>'
                       f'<div>{law_tag}{_tags(topics)}</div><div class="fine">Official title: {escape(b.title)}</div></div>')
    bills = ('<div class="sec"><h2>Bills they put forward</h2><span class="mono soft">Sponsored by this MP</span></div>'
             f'<div class="grid">{bill_cells}</div>') if bill_cells else ""

    # --- speaks about
    stmt_cells = ""
    for x in [x for x in p.champions if x.quote]:
        q = x.quote[:230] + ("…" if len(x.quote) > 230 else "")
        title = x.text.split(": ", 1)[-1]
        date_ = re.search(r"\((\d{4}-\d{2}-\d{2})\)", x.text)
        stmt_cells += (f'<div class="cell s4" {item_attrs(x.topics, x.text + " " + x.quote)}><div class="mono soft">{escape(date_.group(1) if date_ else "Statement")}</div>'
                       f'<p style="margin:10px 0;font-size:1.25rem;font-weight:400;line-height:1.25">{escape(title)}</p>'
                       f'<div class="fine" style="font-size:.88rem">{escape(q)}</div><div style="margin-top:10px">{_tags(x.topics)}</div><div style="margin-top:8px">{link(x.url, "Read it")}</div></div>')
    speaks = ('<div class="sec"><h2>What they choose to speak about</h2><span class="mono soft">60-second statements the MP picks the subject of</span></div>'
              f'<div class="grid">{stmt_cells or "<div class=\'cell s12 soft\'>No members&#x27; statements on record.</div>"}</div>')

    # --- roles
    role_cells = "".join(f'<div class="cell s4"><div class="mono soft">Role</div><p style="margin:8px 0 0;font-size:1.05rem;font-weight:400">{escape(x.text)}</p></div>' for x in p.responsible_for)
    other = ", ".join(f"{escape(k)} ({n})" for k, n in p.assigned_activity.most_common(4))
    roles = ('<div class="sec"><h2>Roles &amp; committees</h2><span class="mono soft">Assigned by position or party</span></div>'
             f'<div class="grid">{role_cells}</div>' + (f'<div class="grid"><div class="cell s12 fine" style="border-bottom:1px solid var(--line)">Other activity: {other}</div></div>' if other else ""))

    footer = (f'{marquee("Know your MP")}<a class="bar mono" href="/">Look up another postal code <span class="arrow">&#8599;</span></a>'
              '<div class="grid"><div class="cell s12 fine" style="border-bottom:0">In Canada MPs almost always vote with their party, so a voting record says less than what an MP chooses to speak about and sponsor. '
              'Sources: openparliament.ca, ourcommons.ca, parl.ca. Descriptions are AI-written from those records; follow the links to check.</div></div>')

    body = f'{hero}<div class="grid">{stat_html}</div>{glance}{filt}{votes}{bills}{speaks}{roles}{footer}<script>{FILTER_JS}</script>'
    return page(mp.name, body)


# ---------------------------------------------------------------- server
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
        postal = one("postal")
        pick = int(one("pick")) if one("pick").isdigit() else None
        if self.path != "/mp":
            return self._send(page("Not found", "<h1>Not found</h1>"), 404)
        try:
            return self._send(card_page(service.card(postal, pick), postal, pick))
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
