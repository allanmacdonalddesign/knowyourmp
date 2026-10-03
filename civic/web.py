"""Local web UI (stdlib only): postal code -> MP baseball card. Runs on this machine; nothing stored, logged or sent.

Design: white paper, black ink, hairline-bordered boxes, mono labels with arrows, big light type. One colour per meaning:
the MP's party colour behind their photo, green for votes for a bill, red for votes against.
No external fonts, scripts or images from third parties except the MP's official photo.
"""
import json
import re
from datetime import date
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from . import service
from .analysis import words

TOPIC_LABELS = {
    "housing": "Housing", "health": "Health", "climate_environment": "Climate & environment", "immigration": "Immigration",
    "justice": "Justice & public safety", "indigenous_affairs": "Indigenous affairs", "economy_cost_of_living": "Economy & cost of living",
    "defence_foreign_affairs": "Defence & foreign affairs", "transportation_infrastructure": "Transportation & infrastructure",
    "education_children_families": "Education, children & families", "seniors_pensions": "Seniors & pensions",
    "technology_privacy": "Technology & privacy", "agriculture_rural": "Agriculture & rural", "arts_culture_sport": "Arts, culture & sport",
    "democracy_government": "Democracy & government", "gender_equality_rights": "Gender equality & rights",
}

# Party colours, matched on the start of the party name Represent gives us. Unknown parties get neutral grey.
PARTY_COLOURS = [("liberal", "#bc241a"), ("conservative", "#1a4782"), ("ndp", "#f37021"), ("new democratic", "#f37021"),
                 ("bloc", "#33b2cc"), ("green", "#3d9b35")]

LEAF_PATH = (
    "M27.251 198.389L25.689 198.389L26.012 191.071L15.238 191.025L16.693 187.558L6.512 179.759L8.935 178.458"
    "L7.481 172.609L12.598 173.638L14.322 170.28L21.164 176.184L18.201 164.43L22.942 166.164L26.444 159.71L26.444 159.61L26.47 159.66"
    "L26.497 159.61L26.497 159.71L29.999 166.164L34.74 164.43L31.776 176.184L38.618 170.28L40.342 173.638L45.459 172.609L44.005 178.458"
    "L46.43 179.759L36.247 187.558L37.701 191.025L26.928 191.071L27.251 198.389Z")
LEAF = ('<a href="/" class="leaf" aria-label="MP Card home"><svg width="40" height="39" viewBox="4.994 158.248 43.012 41.505" aria-hidden="true">'
        f'<path fill="#ce0908" d="{LEAF_PATH}"/></svg></a>')

CSS = """
:root{--bg:#fff;--ink:#0a0a0a;--soft:#666;--line:#0a0a0a;--rule:#d0d0d0;--wash:#f1f1f1;--paper:#fff;--red:#d80621;--pro:#218c77;
--sans:"Manrope","Inter",ui-sans-serif,system-ui,-apple-system,"Helvetica Neue",Arial,sans-serif;
--mono:"JetBrains Mono","SF Mono",ui-monospace,Menlo,Consolas,monospace}
@media (prefers-color-scheme:dark){:root{--bg:#000;--ink:#fff;--soft:#9b9b9b;--line:#d8d8d8;--rule:#333;--wash:#141414;--paper:#000;--red:#ff3347;--pro:#3fbf9f}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}body{overflow-wrap:break-word}
body{margin:0;background:var(--bg);color:var(--ink);font:300 17px/1.55 var(--sans)}
a{color:inherit}.wrap{max-width:1560px;margin:0 auto;border-left:1px solid var(--line);border-right:1px solid var(--line)}
.mono{font-family:var(--mono);text-transform:uppercase;letter-spacing:.09em;font-size:.74rem;font-weight:400}
.soft{color:var(--soft)}.fine{font-size:.78rem;color:var(--soft);margin-top:6px;line-height:1.45}
.grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr))}
.cell{border-right:1px solid var(--line);border-bottom:1px solid var(--line);padding:30px 32px;min-width:0}
.cell:last-child{border-right:0}.s12{grid-column:span 12;border-right:0}.s8{grid-column:span 8}.s6{grid-column:span 6}.s4{grid-column:span 4}.s3{grid-column:span 3}.s5{grid-column:span 5}.s7{grid-column:span 7}
.hidden{display:none!important}
.topbar{display:flex;flex-wrap:wrap;gap:6px 16px;justify-content:space-between;align-items:center;padding:18px 32px;border-bottom:1px solid var(--line)}
.topbar a{text-decoration:none}.leaf{display:block;line-height:0}
.bar{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:20px 32px;border-bottom:1px solid var(--line);background:var(--wash);text-decoration:none;color:inherit;cursor:pointer;border-left:0;border-top:0;border-right:0;width:100%;font:inherit}
a.bar:hover,button.bar:hover{background:var(--ink);color:var(--bg)}
.arrow{font-family:var(--mono);font-size:1.1rem}
.name{font-size:clamp(2.8rem,7.4vw,6.4rem);font-weight:300;line-height:.98;letter-spacing:-.03em;margin:14px 0 18px}
.lead{font-size:clamp(1.2rem,2.2vw,1.7rem);font-weight:300;line-height:1.35;margin:0 0 6px;max-width:30ch}
.big{overflow-wrap:anywhere;font-size:clamp(2.6rem,5.2vw,4.6rem);font-weight:300;line-height:1;letter-spacing:-.03em;margin:14px 0 10px}
.photo{padding:0;position:relative;min-height:420px;background:var(--party,#888)}
.photo .frame{position:absolute;top:24px;left:24px;right:24px;bottom:84px;outline:2px solid #000;background:#ccc;overflow:hidden}
.photo img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:50% 18%;filter:grayscale(1) contrast(1.05)}
.photo .tag{position:absolute;left:24px;bottom:22px;background:var(--paper);color:var(--ink);padding:10px 16px;border:1px solid var(--ink);text-decoration:none}
.photo .initials{position:absolute;inset:0;display:grid;place-items:center;font-size:6rem;font-weight:200;color:#666}
.marq{overflow:hidden;white-space:nowrap;border-bottom:1px solid var(--line);padding:22px 0}
.marq .t{display:inline-flex;animation:slide 32s linear infinite}
.marq span{font-size:clamp(3rem,9vw,7.5rem);font-weight:500;letter-spacing:-.02em;text-transform:uppercase;line-height:1;padding-right:.6em}
.marq span.o{font-family:"Helvetica Neue",Helvetica,Arial,sans-serif;color:var(--bg);-webkit-text-stroke:3px var(--ink);paint-order:stroke fill;font-weight:300}
/* searching state */
#searching{position:fixed;inset:0;z-index:50;background:var(--bg);display:none;flex-direction:column}
#searching.on{display:flex}
#searching .stage{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:30px;padding:40px 28px;border-bottom:1px solid var(--line);border-top:1px solid var(--line);text-align:center}
.ring{position:relative;width:220px;height:220px}.ring svg{position:absolute;inset:0}
.ring .spin{animation:spinring 7s linear infinite;transform-origin:110px 110px}
.ring .lbl{position:absolute;left:0;right:0;top:50%;transform:translateY(-50%);color:var(--soft);text-transform:lowercase}
@keyframes spinring{to{transform:rotate(360deg)}}
@media (prefers-reduced-motion:reduce){.ring .spin{animation:none}}
/* published site: MP directory */
.mplist{display:grid;grid-template-columns:repeat(3,1fr)}
.mprow{display:block;padding:18px 32px 20px;border-right:1px solid var(--line);border-bottom:1px solid var(--line);text-decoration:none;color:inherit;min-width:0}
.mprow:nth-child(3n){border-right:0}.mprow:hover .nm{color:var(--red)}
.mprow .nm{display:block;font-size:1.15rem;line-height:1.3}.mprow .soft{display:block;margin-top:4px}
.mprow.hidden{display:none}
@media (max-width:900px){.mplist{grid-template-columns:1fr 1fr}.mprow:nth-child(3n){border-right:1px solid var(--line)}.mprow:nth-child(2n){border-right:0}}
@media (max-width:600px){.mplist{grid-template-columns:1fr}.mprow{border-right:0!important;padding:16px 20px}}
@keyframes slide{to{transform:translateX(-50%)}}
@media (prefers-reduced-motion:reduce){.marq .t{animation:none}}
.sec{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:flex-end;gap:8px 16px;padding:22px 32px;border-bottom:1px solid var(--line)}
.sec h2{margin:0;font-size:clamp(1.6rem,3.2vw,2.6rem);font-weight:300;letter-spacing:-.02em}
.sec .mono+h2{margin-top:8px}
.item p{margin:0 0 6px;font-size:1.12rem;line-height:1.4;font-weight:400}
.meta{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center}
.tagz{display:inline-block;border:1px solid var(--line);padding:2px 9px;font-family:var(--mono);font-size:.68rem;letter-spacing:.06em;text-transform:uppercase;margin:2px 6px 2px 0}
.tagz.fill{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.tagz.pro{background:var(--pro);border-color:var(--pro);color:#fff}.tagz.anti{background:var(--red);border-color:var(--red);color:#fff}
sup a{font-family:var(--mono);font-size:.62rem;text-decoration:none;margin-left:2px;border-bottom:1px solid var(--line)}
.notice{background:var(--wash);padding:14px 16px;margin-top:14px;font-size:.8rem;line-height:1.45}
.note{border:1px solid var(--ink);padding:14px 18px;margin:0 0 14px;background:var(--wash)}
.dot{display:inline-block;width:14px;height:14px;border-radius:50%;flex-shrink:0}.dot.pro{background:var(--pro)}.dot.anti{background:var(--red)}
.side h3{display:flex;align-items:center;gap:16px;margin:0 0 14px;font-size:clamp(1.6rem,3vw,2.3rem);font-weight:300;letter-spacing:-.03em}
.side p{font-size:clamp(1.05rem,1.6vw,1.2rem);line-height:1.5;margin:0;font-weight:300}
@media (prefers-reduced-motion:no-preference){html{scroll-behavior:smooth}}
a.ul{display:inline-block;margin-top:16px;font-weight:600;text-decoration:underline;text-underline-offset:3px}
/* words they keep coming back to */
.bubwrap{position:relative;padding:28px 32px;border-bottom:1px solid var(--line)}
.bubbles{display:block;width:100%;height:auto}.bubbles.narrow{display:none}
.bub{transition:opacity .15s}.bub:focus{outline:none}.bub:focus-visible circle{stroke-width:3}
.bub circle{fill:var(--bg);stroke:var(--ink);stroke-width:1.5}
.bub text{fill:var(--ink);font-family:var(--sans);font-weight:500;text-anchor:middle;pointer-events:none}.bub .n{fill:var(--soft);font-family:var(--mono);font-weight:400}
.bub.top circle{fill:var(--ink)}.bub.top text,.bub.top .n{fill:var(--bg)}
.bubwrap.hov .bub{opacity:.22}.bubwrap.hov .bub.on{opacity:1}.bub.on circle{fill:var(--red);stroke:var(--red)}.bub.on text,.bub.on .n{fill:#fff}
.tip{position:absolute;z-index:3;background:var(--ink);color:var(--bg);padding:12px 14px 13px;min-width:230px;pointer-events:none}.tip[hidden]{display:none}
.tip .row{display:flex;justify-content:space-between;gap:16px;align-items:baseline}.tip .tt{font-size:1.1rem;font-weight:500}
.tip .mono{font-size:.6rem;opacity:.75;margin-top:6px;display:block}
.wrow{display:grid;grid-template-columns:56px minmax(0,2.2fr) minmax(0,3fr) 64px 84px 110px;gap:16px;align-items:center;padding:12px 32px;border-bottom:1px solid var(--rule)}
.whead{border-bottom:1px solid var(--line);padding-top:14px;padding-bottom:14px}
.wt{font-weight:400}.wb{display:block}.wbar{display:block;height:8px;background:var(--ink)}
.num{text-align:right;font-family:var(--mono);font-size:.8rem}.whead .num{font-size:inherit}
.wrow.on{background:var(--wash)}.wrow.on .wt{color:var(--red)}.wrow.on .wbar{background:var(--red)}
.wmore{border-bottom:1px solid var(--line)}.wmore summary{padding:16px 32px}
/* votes view */
.tabs{display:flex;flex-wrap:wrap;gap:8px 40px;margin:6px 0 30px}
.tabs a{display:flex;align-items:center;gap:14px;font-size:clamp(3rem,8vw,5rem);font-weight:300;letter-spacing:-.045em;line-height:1.05;text-decoration:none;opacity:.3;border-bottom:2px solid transparent}
.tabs a:hover{opacity:.6;color:inherit}.tabs a.on{opacity:1}
.tabs a.on[data-mode=all]{border-color:var(--ink)}.tabs a.on[data-mode=for]{color:var(--pro);border-color:var(--pro)}.tabs a.on[data-mode=against]{color:var(--red);border-color:var(--red)}
.back{text-decoration:none}
.hum{display:inline-flex;align-items:center;gap:12px;margin-top:18px;background:none;border:0;color:var(--ink);padding:0;cursor:pointer;font-family:var(--mono)}
.hum .sw{width:34px;height:20px;border-radius:10px;background:var(--rule);position:relative;flex-shrink:0;transition:background .15s}
.hum .sw:after{content:"";position:absolute;top:2px;left:2px;width:16px;height:16px;border-radius:50%;background:var(--bg);transition:left .15s}
.hum[aria-pressed=true] .sw{background:var(--ink)}.hum[aria-pressed=true] .sw:after{left:16px}
.hum:hover{color:var(--red)}.hum:focus-visible{outline:2px solid var(--ink);outline-offset:4px}
.t-human{display:none}.human-on .has-human .t-plain{display:none}.human-on .has-human .t-human{display:inline}
.sectoggle .hum{margin-top:14px}
.vgrid{display:grid;grid-template-columns:1fr 1fr}
.vitem{padding:24px 32px 28px;border-bottom:1px solid var(--line);min-width:0}.vitem.l{border-right:1px solid var(--line)}
.vitem p{margin:0 0 8px;font-size:1.12rem;line-height:1.4;font-weight:400}
.filter input[type=text]{width:100%;background:transparent;border:0;border-bottom:1px solid var(--ink);color:var(--ink);font:300 clamp(1.3rem,2.4vw,2rem)/1.3 var(--sans);padding:6px 0 10px;outline:0}
.filter input[type=text]::placeholder{color:var(--soft)}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}
.chip{cursor:pointer}.chip input{position:absolute;opacity:0;pointer-events:none}
.chip span{display:inline-block;border:1px solid var(--ink);padding:6px 12px;font-family:var(--mono);font-size:.72rem;letter-spacing:.05em;text-transform:uppercase}
.chip input:checked+span{background:var(--ink);color:var(--bg)}.chip input:focus-visible+span{outline:2px solid var(--ink);outline-offset:2px}
.chip.off span{opacity:.35;cursor:not-allowed}
details summary{cursor:pointer;list-style:none;padding:14px 0}details summary::-webkit-details-marker{display:none}
.hero{padding-top:56px;padding-bottom:56px}
.lookup{display:flex;flex-direction:column;justify-content:flex-end}
input.postal{width:100%;background:transparent;border:0;border-bottom:2px solid var(--ink);color:var(--ink);font:300 clamp(2.4rem,7vw,5.5rem)/1.1 var(--sans);letter-spacing:.04em;padding:6px 0 14px;outline:0;text-transform:uppercase}
input.postal.byname{text-transform:none;letter-spacing:0}
.mode{display:flex;gap:28px;margin-bottom:22px}.mode label{cursor:pointer}.mode input{position:absolute;opacity:0}
.mode span{display:inline-block;opacity:.35;padding-bottom:4px;border-bottom:2px solid transparent}.mode label:hover span{opacity:.7}
.mode input:checked+span{opacity:1;border-color:var(--ink)}.mode input:focus-visible+span{outline:2px solid var(--ink);outline-offset:4px}
input.postal::placeholder{color:var(--soft);opacity:.6}
button.go{display:flex;justify-content:space-between;align-items:center;width:100%;margin-top:22px;padding:30px 28px;border:0;font-size:.9rem;cursor:pointer}
.radio{display:flex;gap:16px;align-items:center;padding:22px 32px;border-bottom:1px solid var(--line);cursor:pointer}.radio:hover{background:var(--wash)}
.radio input{accent-color:var(--ink);width:20px;height:20px}
@media (max-width:600px){.big{font-size:2.2rem}.name{font-size:clamp(2.4rem,13vw,3.4rem)}.cell{padding:22px 18px}.chip span{padding:5px 9px}}
@media (max-width:700px){.bubbles.wide{display:none}.bubbles.narrow{display:block}.bubwrap{padding:20px}
.wrow{grid-template-columns:34px minmax(0,1fr) 56px;padding-left:20px;padding-right:20px}.wrow>.wb,.wrow>.ws,.wrow>.wl{display:none}.wmore summary{padding-left:20px}}
@media (max-width:900px){.fillcell{display:none}.s8,.s6,.s4,.s5,.s7{grid-column:span 12}.s3{grid-column:span 6}.cell{border-right:0;padding:24px 20px}.topbar,.sec,.bar,.radio{padding-left:20px;padding-right:20px}.photo{min-height:clamp(380px,82vw,660px)}
.s3.cell:nth-child(odd){border-right:1px solid var(--line)}.vgrid{grid-template-columns:1fr}.vitem.l{border-right:0}.vitem{padding:22px 20px}}
::selection{background:var(--red);color:#fff}
a:hover{color:var(--red)}
a.bar:hover,button.bar:hover,.radio:hover{background:var(--red);color:#fff}
.photo .tag:hover{background:var(--red);color:#fff;border-color:var(--red)}
.chip:hover span{border-color:var(--red);color:var(--red)}.chip:hover input:checked+span{background:var(--red);border-color:var(--red);color:#fff}
.chip input:focus-visible+span,a:focus-visible,button:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
.vitem:hover>p,.cell[data-bill]:hover>p{color:var(--red)}
details summary:hover,sup a:hover{color:var(--red)}sup a:hover{border-color:var(--red)}
input.postal:focus,.filter input[type=text]:focus{box-shadow:0 3px 0 var(--ink)}
.postal:focus-visible,.filter input[type=text]:focus-visible{outline:0}
.cta{background:#000;color:#fff}
@media (prefers-color-scheme:dark){.cta{background:#fff;color:#000}}
a.cta:hover,button.cta:hover{background:var(--red);color:#fff}
.red{color:var(--red)}
"""


def page(title: str, body: str, head: str = "") -> bytes:
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="referrer" content="no-referrer"><title>{escape(title)}</title>{head}<style>{CSS}</style></head>'
            f'<body><div class="wrap">{body}</div></body></html>').encode()


def marquee(word: str) -> str:
    unit = "".join(f'<span>{escape(word)}</span><span class="o">{escape(word)}</span>' for _ in range(2))
    return f'<div class="marq" aria-hidden="true"><div class="t">{unit}{unit}</div></div>'


def topbar(right: str = "", left: str = '<a href="/">MP Card</a>') -> str:
    return f'<div class="topbar mono">{left}<span class="soft">{right}</span></div>'


def link(url: str, label: str = "Source") -> str:
    return f'<a class="mono" href="{escape(url)}" target="_blank" rel="noopener noreferrer">{escape(label)} &#8599;</a>'


def party_colour(party: str) -> str:
    p = (party or "").casefold()
    return next((c for key, c in PARTY_COLOURS if p.startswith(key)), "#888888")


def searching_overlay() -> str:
    """Full-screen 'searching' state shown while a lookup runs; a ring of maple leaves spins around the word."""
    leaves = "".join(f'<use href="#lf" transform="translate(110 110) rotate({i * 30}) translate(0 -80) rotate(90) scale(.34)"/>' for i in range(12))
    return (f'<div id="searching" role="status" aria-live="polite" aria-hidden="true">{topbar("Meet your MP", LEAF)}'
            '<div class="stage"><div class="ring"><svg viewBox="0 0 220 220" aria-hidden="true">'
            f'<defs><path id="lf" fill="#ce0908" transform="translate(-26.5 -179)" d="{LEAF_PATH}"/></defs><g class="spin">{leaves}</g></svg>'
            '<div class="lbl mono">searching</div></div>'
            '<div><div class="mono soft">Reading public records for your MP</div>'
            '<p class="fine" style="max-width:420px;margin:12px auto 0">The first lookup for an MP can take a minute or two. After that it is fast. '
            'Your postal code is never stored or logged.</p></div></div>'
            '<div class="mono soft" style="padding:30px 28px 40px">Data: openparliament.ca, ourcommons.ca, Parliament of Canada. Nonpartisan: every MP gets the same card.</div></div>'
            "<script>(()=>{const o=document.getElementById('searching');"
            "document.querySelectorAll('form[action=\"/mp\"]').forEach(f=>f.addEventListener('submit',()=>{o.classList.add('on');o.setAttribute('aria-hidden','false');}));"
            "addEventListener('pageshow',e=>{if(e.persisted){o.classList.remove('on');o.setAttribute('aria-hidden','true');}});})();</script>")


# ---------------------------------------------------------------- home / split riding
LOOKUP_MODES = {
    "postal": ("Where do you live? Postal code", "M5V 3L9", 10, "Your postal code is never stored or logged."),
    "name": ("Who is your MP? Name", "Chi Nguyen", 60, "Any part of the name works, like just a last name."),
}


def home(msg: str = "", q: str = "", by: str = "postal") -> bytes:
    by = by if by in LOOKUP_MODES else "postal"
    err = f'<div class="note mono">{escape(msg)}</div>' if msg else ""
    modes = "".join(f'<label><input type="radio" name="by" value="{k}"{" checked" if k == by else ""}><span>{lbl}</span></label>'
                    for k, lbl in (("postal", "Postal code"), ("name", "MP name")))
    label, ph, maxlen, hint = LOOKUP_MODES[by]
    return page("MP Card", f"""{topbar("Meet your MP", LEAF)}
<div class="grid"><div class="cell s5 hero">
<div class="mono soft">Your MP, and their stats</div>
<h1 class="name" style="font-size:clamp(3.4rem,9vw,8.5rem)">Meet<br>your MP<span class="red">.</span></h1>
<p class="lead">What they vote for, what they speak up about, what they put their name on. In plain words, with receipts.</p></div>
<form class="cell s7 lookup" method="post" action="/mp" id="lookup">{err}<div class="mode mono" role="radiogroup" aria-label="Look up by">{modes}</div>
<label for="q" class="mono soft" id="qlabel">{label}</label>
<input class="postal{" byname" if by == "name" else ""}" id="q" name="q" value="{escape(q)}" placeholder="{ph}" required maxlength="{maxlen}" autocomplete="off" autofocus>
<div class="fine">The first lookup for an MP can take a minute or two while it reads public records. After that it is fast. <span id="qhint">{hint}</span></div>
<button class="cta mono go" type="submit">Find my MP <span class="arrow">&#8599;</span></button></form></div>
<script>(()=>{{const M={json.dumps(LOOKUP_MODES)},f=document.getElementById('lookup'),q=document.getElementById('q');
f.addEventListener('change',e=>{{if(e.target.name!=='by')return;const m=M[e.target.value];
document.getElementById('qlabel').textContent=m[0];q.placeholder=m[1];q.maxLength=m[2];document.getElementById('qhint').textContent=m[3];
q.classList.toggle('byname',e.target.value==='name');q.focus();}});}})();</script>
{searching_overlay()}{marquee("Know your MP")}
<div class="grid"><div class="cell s12 mono soft" style="border-bottom:0">Data: openparliament.ca, ourcommons.ca, Parliament of Canada. Nonpartisan: every MP gets the same card.</div></div>""")


SITE_NOTES = {"postal": "We could not read that postal code. Please check it.", "notfound": "No MP found for that postal code. Try searching by name.",
              "down": "The postal code lookup is not available right now. Search by name below."}


def site_home(mps: list[dict], updated: str, url: str) -> bytes:
    """The published directory page: lookup on top, every MP below as a plain link so it can be crawled.

    mps: dicts with name, party, riding, slug. A postal code is POSTed to /api/postal (a Cloudflare Pages function) and never put in a URL."""
    rows = "".join(
        f'<a class="mprow" href="/mp/{escape(m["slug"])}/" data-slug="{escape(m["slug"])}" data-text="{escape((m["name"] + " " + m["riding"] + " " + m["party"]).lower())}">'
        f'<span class="nm">{escape(m["name"])}</span><span class="mono soft">{escape(m["party"])} &middot; {escape(m["riding"])}</span></a>'
        for m in sorted(mps, key=lambda m: m["name"].casefold()))
    modes = "".join(f'<label><input type="radio" name="by" value="{k}"{" checked" if k == "postal" else ""}><span>{lbl}</span></label>'
                    for k, lbl in (("postal", "Postal code"), ("name", "MP name")))
    label, ph, maxlen, hint = LOOKUP_MODES["postal"]
    title = "Know Your MP: see how your Member of Parliament votes, in plain language"
    desc = ("Look up your Member of Parliament by postal code or name. See how they voted, the bills they sponsored and what they speak about, "
            "in plain language with links to the sources.")
    body = f"""{topbar("Meet your MP", LEAF)}
<div class="grid"><div class="cell s5 hero">
<div class="mono soft">Your MP, and their stats</div>
<h1 class="name" style="font-size:clamp(3.4rem,9vw,8.5rem)">Meet<br>your MP<span class="red">.</span></h1>
<p class="lead">What they vote for, what they speak up about, what they put their name on. In plain words, with receipts.</p></div>
<form class="cell s7 lookup" method="post" action="/api/postal" id="lookup"><div class="note mono hidden" id="note"></div>
<div class="mode mono" role="radiogroup" aria-label="Look up by">{modes}</div>
<label for="q" class="mono soft" id="qlabel">{label}</label>
<input class="postal" id="q" name="code" placeholder="{ph}" required maxlength="{maxlen}" autocomplete="off" autofocus>
<div class="fine"><span id="qhint">{hint}</span> A postal code is sent only to look up your riding. It is not stored or put in the address.</div>
<button class="cta mono go" type="submit">Find my MP <span class="arrow">&#8599;</span></button></form></div>
{marquee("Know your MP")}
<div class="sec" id="all"><div><h2 id="listh">All {len(mps)} MPs</h2></div><span class="mono soft">Updated {escape(updated)}</span></div>
<div class="mplist" id="mplist">{rows}</div>
<div class="grid"><div class="cell s12 fine" style="border-bottom:0">Data: openparliament.ca, ourcommons.ca, Parliament of Canada. Nonpartisan: every MP gets the same page. Descriptions are AI-written from those records; follow the links to check.</div></div>
<script>(()=>{{const M={json.dumps(LOOKUP_MODES)},N={json.dumps(SITE_NOTES)},f=document.getElementById('lookup'),q=document.getElementById('q'),
rows=[...document.querySelectorAll('.mprow')],h=document.getElementById('listh'),note=document.getElementById('note'),all=rows.length;
let mode='postal';
const show=fn=>{{let n=0;rows.forEach(r=>{{const ok=fn(r);r.classList.toggle('hidden',!ok);if(ok)n++;}});return n;}};
const count=n=>{{h.textContent=n===all?'All '+all+' MPs':n+(n===1?' MP':' MPs');}};
f.addEventListener('change',e=>{{if(e.target.name!=='by')return;mode=e.target.value;const m=M[mode];
document.getElementById('qlabel').textContent=m[0];q.placeholder=m[1];q.maxLength=m[2];document.getElementById('qhint').textContent=m[3];
q.name=mode==='name'?'q':'code';q.classList.toggle('byname',mode==='name');q.value='';count(show(()=>true));q.focus();}});
q.addEventListener('input',()=>{{if(mode!=='name')return;const w=q.value.toLowerCase().split(/\s+/).filter(Boolean);count(show(r=>w.every(x=>r.dataset.text.includes(x))));}});
f.addEventListener('submit',e=>{{if(mode!=='name')return;e.preventDefault();const v=rows.filter(r=>!r.classList.contains('hidden'));if(v.length===1)location.href=v[0].href;else document.getElementById('all').scrollIntoView();}});
const sp=new URLSearchParams(location.search);
if(sp.get('error')&&N[sp.get('error')]){{note.textContent=N[sp.get('error')];note.classList.remove('hidden');}}
if(sp.get('choose')){{const want=sp.get('choose').split(',');count(show(r=>want.includes(r.dataset.slug)));h.textContent='More than one MP covers that postal code. Choose yours.';document.getElementById('all').scrollIntoView();}}
}})();</script>"""
    return page(title, body, seo_head(title, desc, url + "/"))


def choose_riding(e: service.SplitPostcode, q, by: str = "postal") -> bytes:
    opts = "".join(
        f'<label class="radio"><input type="radio" name="pick" value="{i}" required><span><strong style="font-weight:400">{escape(m.name)}</strong>'
        f' <span class="soft">&middot; {escape(m.party)} &middot; {escape(m.riding)}</span></span></label>'
        for i, m in enumerate(e.mps, 1))
    head = ("Same name", "Which MP<br>do you mean?") if by == "name" else ("Split postal code", "Which riding<br>are you in?")
    return page("Choose your MP", f"""{topbar("One more step")}
<div class="grid"><div class="cell s12"><div class="mono soft">{head[0]}</div><h1 class="name">{head[1]}</h1><p class="lead">{escape(str(e))}</p></div></div>
<form method="post" action="/mp"><input type="hidden" name="q" value="{escape(q)}"><input type="hidden" name="by" value="{escape(by)}">{opts}
<button class="bar cta mono" type="submit">Continue <span class="arrow">&#8599;</span></button></form>{searching_overlay()}""")


def seo_head(title: str, desc: str, url: str, image: str | None = None, jsonld: dict | None = None) -> str:
    tags = [f'<meta name="description" content="{escape(desc)}">', f'<link rel="canonical" href="{escape(url)}">',
            '<meta property="og:type" content="website">', f'<meta property="og:title" content="{escape(title)}">',
            f'<meta property="og:description" content="{escape(desc)}">', f'<meta property="og:url" content="{escape(url)}">',
            f'<meta name="twitter:card" content="{"summary_large_image" if image else "summary"}">']
    if image:
        tags.append(f'<meta property="og:image" content="{escape(image)}">')
    if jsonld:
        clean = {k: v for k, v in jsonld.items() if v}
        tags.append('<script type="application/ld+json">' + json.dumps(clean).replace("</", "<\\/") + "</script>")
    return "".join(tags)


# ---------------------------------------------------------------- the card
def _topics_attr(topics) -> str:
    return escape(" ".join(t for t in topics if t != "other"))


def _tags(topics) -> str:
    return "".join(f'<span class="tagz">{escape(TOPIC_LABELS.get(t, t))}</span>' for t in topics if t != "other")


# The card and the votes list are two views of one page, switched by the URL hash (#votes, #votes-for, #votes-against),
# so the postal code never has to go into a URL and the back button works.
FILTER_JS = """
const cardView=document.getElementById('card-view'),votesView=document.getElementById('votes-view'),
 form=document.getElementById('filter'),q=document.getElementById('q'),items=[...votesView.querySelectorAll('[data-item]')],
 boxes=[...form.querySelectorAll('input[name=topic]:not(:disabled)')],count=document.getElementById('count'),
 tabs=[...document.querySelectorAll('.tabs a')];let mode='all';
function apply(){const want=boxes.filter(b=>b.checked).map(b=>b.value),text=q.value.trim().toLowerCase();
 const pool=items.filter(it=>mode==='all'||it.dataset.ballot===mode);let shown=[];
 items.forEach(it=>{const t=(it.dataset.topics||'').split(' ').filter(Boolean);
  const ok=pool.includes(it)&&(!want.length||want.some(w=>t.includes(w)))&&(!text||it.dataset.text.includes(text));
  it.classList.toggle('hidden',!ok);if(ok)shown.push(it);});
 shown.forEach((it,i)=>it.classList.toggle('l',i%2===0));
 count.textContent=(want.length||text)?('Showing '+shown.length+' of '+pool.length):'';}
function route(){const m=location.hash.match(/^#votes(?:-(for|against))?$/);
 cardView.classList.toggle('hidden',!!m);votesView.classList.toggle('hidden',!m);
 if(m){mode=m[1]||'all';tabs.forEach(t=>t.classList.toggle('on',t.dataset.mode===mode));apply();window.scrollTo(0,0);}}
form.addEventListener('input',apply);form.addEventListener('submit',e=>e.preventDefault());
addEventListener('hashchange',route);route();
const hbs=[...document.querySelectorAll('.hum')];
if(hbs.length){const set=on=>{hbs.forEach(h=>h.setAttribute('aria-pressed',on?'true':'false'));document.body.classList.toggle('human-on',on);
  try{localStorage.setItem('mpcard-human',on?'1':'')}catch(e){}};
 let saved=false;try{saved=localStorage.getItem('mpcard-human')==='1'}catch(e){}
 set(saved);hbs.forEach(h=>h.addEventListener('click',()=>set(h.getAttribute('aria-pressed')!=='true')));}
"""

WORDS_JS = """
const bw=document.querySelector('.bubwrap');
if(bw){const tip=bw.querySelector('.tip'),rows=[...document.querySelectorAll('.wrow[data-i]')],gs=[...bw.querySelectorAll('.bub')];
 function on(i){gs.forEach(g=>g.classList.toggle('on',g.dataset.i===i));rows.forEach(r=>r.classList.toggle('on',r.dataset.i===i));
  bw.classList.toggle('hov',i!=null);const g=gs.find(g=>g.dataset.i===i&&g.getBoundingClientRect().width>0);
  if(i==null||!g){tip.hidden=true;return}const d=g.dataset;
  tip.querySelector('.tt').textContent=d.term;tip.querySelector('.tn').textContent=d.n+'\\u00d7';
  tip.querySelector('.tm').textContent='#'+(+i+1)+' of '+rows.length+' \\u00b7 in '+d.s+' speeches';
  tip.querySelector('.tl').textContent='Last said '+d.last;tip.hidden=false;
  const b=g.getBoundingClientRect(),w=bw.getBoundingClientRect();let x=b.right-w.left+10;
  if(x+tip.offsetWidth>w.width)x=b.left-w.left-tip.offsetWidth-10;if(x<0)x=Math.max(0,Math.min(w.width-tip.offsetWidth,b.left-w.left));
  tip.style.left=x+'px';tip.style.top=Math.max(0,b.top-w.top)+'px';}
 bw.addEventListener('mouseover',e=>{const g=e.target.closest('.bub');on(g?g.dataset.i:null)});
 bw.addEventListener('mouseleave',()=>on(null));
 bw.addEventListener('focusin',e=>{const g=e.target.closest('.bub');if(g)on(g.dataset.i)});bw.addEventListener('focusout',()=>on(null));
 rows.forEach(r=>{r.addEventListener('mouseenter',()=>on(r.dataset.i));r.addEventListener('mouseleave',()=>on(null))});}
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


def _fit(term: str, size: int, r: float) -> list[str]:
    """The term as one or two lines if it fits inside a circle of radius r, else nothing (hover shows it)."""
    room = 1.65 * r
    width = lambda s: len(s) * size * 0.56
    if r < 30:
        return []
    if width(term) <= room:
        return [term]
    ws = term.split()
    if len(ws) < 2 or r < 40:
        return []
    lines = min(([" ".join(ws[:k]), " ".join(ws[k:])] for k in range(1, len(ws))), key=lambda ls: max(map(len, ls)))
    return lines if max(map(width, lines)) <= room * 0.92 else []


def bubbles_svg(terms, w: int, h: int, cls: str) -> str:
    parts = []
    for i, (t, (x, y, r)) in enumerate(zip(terms, words.pack([t.count for t in terms], w, h))):
        size, label = max(11, min(22, round(r / 4.2))), ""
        lines = _fit(t.term, size, r)
        while not lines and size > 10 and r >= 30:  # long words get slightly smaller type before giving up on a label
            size -= 1
            lines = _fit(t.term, size, r)
        if lines:
            small, lh = max(9, round(size * 0.5)), round(size * 1.1)
            top = y - (len(lines) * lh + 4 + small) / 2 + size * 0.85
            spans = "".join(f'<tspan x="{x:.1f}" y="{top + k * lh:.1f}">{escape(s)}</tspan>' for k, s in enumerate(lines))
            label = (f'<text font-size="{size}">{spans}</text>'
                     f'<text class="n" font-size="{small}" x="{x:.1f}" y="{top + (len(lines) - 1) * lh + 6 + small:.1f}">{t.count}</text>')
        parts.append(f'<g class="bub{" top" if i == 0 else ""}" data-i="{i}" data-term="{escape(t.term)}" data-n="{t.count}" data-s="{t.speeches}"'
                     f' data-last="{escape(t.last_said)}" tabindex="0" aria-label="{escape(t.term)}: {t.count} mentions">'
                     f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}"/>{label}</g>')
    return f'<svg class="bubbles {cls}" viewBox="0 0 {w} {h}" role="group" aria-label="Words they use most, sized by how often">{"".join(parts)}</svg>'


def words_section(c) -> str:
    if not c.terms:
        return ""
    top = c.terms[0].count

    def row(i, t) -> str:
        return (f'<div class="wrow" data-i="{i}"><span class="num soft" style="text-align:left">{i + 1:02d}</span><span class="wt">{escape(t.term)}</span>'
                f'<span class="wb"><span class="wbar" style="width:{max(1, round(100 * t.count / top))}%"></span></span>'
                f'<span class="num">{t.count}</span><span class="num soft ws">{t.speeches}</span><span class="num soft wl">{escape(t.last_said)}</span></div>')

    rows = [row(i, t) for i, t in enumerate(c.terms)]
    more = f'<details class="wmore"><summary class="mono">Show all {len(rows)} terms &#8599;</summary>{"".join(rows[10:])}</details>' if len(rows) > 10 else ""
    since = f" since {escape(c.speeches_since)}" if c.speeches_since else ""
    fav = f' openparliament.ca lists their favourite word as &ldquo;{escape(c.favourite_word)}&rdquo;.' if c.favourite_word else ""
    tip = ('<div class="tip" hidden><div class="row"><span class="tt"></span><span class="mono tn" style="margin:0;opacity:1"></span></div>'
           '<span class="mono tm"></span><span class="mono tl"></span></div>')
    return (f'<div class="sec"><div><div class="mono soft">In the House, they talk most about</div><h2>What they keep coming back to</h2></div>'
            f'<span class="mono soft">Mentions in {c.speech_count} speeches</span></div>'
            f'<div class="bubwrap">{bubbles_svg(c.terms, 1220, 540, "wide")}{bubbles_svg(c.terms, 360, 600, "narrow")}{tip}</div>'
            '<div class="wtable"><div class="wrow whead mono soft"><span>Rank</span><span>Term</span><span class="wb">Mentions</span>'
            '<span class="num">Times</span><span class="num ws">Speeches</span><span class="num wl">Last said</span></div>'
            f'{"".join(rows[:10])}{more}</div>'
            f'<div class="grid"><div class="cell s12 fine" style="margin:0">Counted from their {c.speech_count} most recent speeches in the House and committees{since}, '
            f'leaving out common words and House procedure words. Hover a bubble or a row to see it in both.{fav}</div></div>')


def card_page(c, postal, pick, site: dict | None = None) -> bytes:
    """site: set for the published static pages (url, updated); adds SEO tags and the updated date."""
    mp, p = c.mp, c.profile

    # --- hero
    if c.photo_url:
        photo = f'<img src="{escape(c.photo_url)}" alt="" referrerpolicy="no-referrer">'
    else:
        photo = f'<div class="initials">{escape("".join(w[0] for w in mp.name.split()[:2]))}</div>'
    tag = f'<a class="tag mono" href="{escape(mp.ourcommons_url)}" target="_blank" rel="noopener noreferrer">Official page &#8599;</a>' if mp.ourcommons_url else ""
    ident = identity_line(c)
    since = f"MP since {escape(c.mp_since[:4])}" if c.mp_since else ""
    notes = "".join(f'<div class="notice">{escape(n)}</div>' for n in c.notes + p.notes)
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
    hero = f"""<div class="grid"><div class="cell photo s4" style="--party:{party_colour(mp.party)}"><div class="frame">{photo}</div>{tag}</div>
<div class="cell s8" style="padding:0;display:flex;flex-direction:column;justify-content:space-between">
<div style="padding:30px 32px 24px"><div class="mono soft">Your MP &middot; {escape(mp.party)} &middot; {escape(mp.riding)}</div>
<h1 class="name">{escape(mp.name)}</h1>{f'<p class="lead">{escape(ident)}</p>' if ident else ''}{office}{notes}</div>
<div>{"".join(contact)}</div></div></div>"""

    # --- stat boxes: time in office, bills, election, votes
    boxes = []
    if c.mp_since:
        yrs = max(0.0, (date.today() - date.fromisoformat(c.mp_since)).days / 365.25)
        boxes.append(("Time in office", f"{yrs:.0f}<span style='font-size:.4em'> yrs</span>" if yrs >= 1.5 else "&lt;2<span style='font-size:.4em'> yrs</span>", since, ""))
    law = sum(1 for b in c.bills if b.became_law)
    to_bills = '<a class="mono ul" href="#bills">See their bills &darr;</a>' if c.bills else ""
    boxes.append(("Bills sponsored", f"{len(c.bills)}", f"{law} became law" if c.bills else "none on record", to_bills))
    if c.election:
        e = c.election
        boxes.append(("Won their election with" if e.won else "Lost their last election with", f"{e.share}%", f"of the vote, in {e.year}", ""))
    if c.votes_total:
        y, n = c.ballots_cast.get("Yes", 0), c.ballots_cast.get("No", 0)
        boxes.append(("House votes", f"{y}<span style='font-size:.4em'> yes</span> {n}<span style='font-size:.4em'> no</span>", f"of {c.votes_total} this session", ""))
    span = {1: "s12", 2: "s6", 3: "s4"}.get(len(boxes), "s3")
    stat_html = "".join(f'<div class="cell {span}"><div class="mono soft">{escape(lbl)}</div><div class="big">{val}</div><div class="fine">{escape(sub)}</div>{more}</div>'
                        for lbl, val, sub, more in boxes)

    # --- at a glance: what they voted for (Pro) and against (Anti)
    def refs(ids) -> str:
        return "".join(f'<sup><a href="{escape(c.ref_links[i][1])}" target="_blank" rel="noopener noreferrer" title="{escape(c.ref_links[i][0])}">{n}</a></sup>'
                       for n, i in enumerate(ids, 1) if i in c.ref_links)

    def side(kind: str, title: str, votes) -> str:
        said = next((x for x in c.overview if x.get("kind") == kind), None)
        word = "for" if kind == "for" else "against"
        if said:
            text = escape(said["text"]) + refs(said["refs"])
        elif votes:
            text = f"Voted {word} {len(votes)} bill{'s' if len(votes) != 1 else ''} at a deciding vote this session."
        else:
            text = f"No votes {word} a bill on record this session."
        more = f'<a class="mono ul" href="#votes-{word}">See what they vote {word} &#8599;</a>' if votes else ""
        return (f'<div class="cell s6 side"><h3>{title}<span class="dot {"pro" if kind == "for" else "anti"}"></span></h3>'
                f'<p>{text}</p>{more}</div>')

    source = "AI-written from the linked records" if any(x.get("kind") in ("for", "against") for x in c.overview) else "From the voting record"
    glance = (f'<div class="sec"><h2>At a glance</h2><span class="mono soft">{source}</span></div>'
              f'<div class="grid">{side("for", "Pro", c.backed)}{side("against", "Anti", c.opposed)}</div>')

    # --- sponsored bills
    bill_cells = ""
    for b in c.bills:
        topics = c.bill_topics.get(b.url, [])
        txt = c.bill_plain.get(b.url) or b.title
        law_tag = '<span class="tagz fill">Became law</span>' if b.became_law else ""
        human = c.human.get(b.url, "")
        words_ = f'<span class="t-plain">{escape(txt)}</span>' + (f'<span class="t-human">{escape(human)}</span>' if human else "")
        bill_cells += (f'<div class="cell s6{" has-human" if human else ""}" data-bill><p style="margin:0 0 8px;font-size:1.2rem;font-weight:400;line-height:1.35">{words_}</p>'
                       f'<div class="meta"><span class="mono soft">Bill {escape(b.number)} &middot; {escape(b.session)} &middot; {escape(b.status)}</span>{link("https://openparliament.ca" + b.url, "Bill")}</div>'
                       f'<div>{law_tag}{_tags(topics)}</div><div class="fine">Official title: {escape(b.title)}</div></div>')
    if len(c.bills) % 2:  # an empty slot would leave the bottom rule half-width
        bill_cells += '<div class="cell s6 fillcell"></div>'
    bills_toggle = HUMAN_BUTTON if any(b.url in c.human for b in c.bills) else ""
    bills = ('<div class="sec" id="bills"><div><h2>Bills they put forward</h2>' + (f'<div class="sectoggle">{bills_toggle}</div>' if bills_toggle else "") +
             '</div><span class="mono soft">Sponsored by this MP</span></div>'
             f'<div class="grid">{bill_cells}</div>') if bill_cells else ""

    card_view = f'<div id="card-view">{hero}<div class="grid">{stat_html}</div>{glance}{words_section(c)}{bills}</div>'

    # --- votes view: every bill-deciding vote, filterable by Pro / Anti, topic and words
    def vote_item(v) -> str:
        stage = "Final vote" if v.stage == "3rd reading" else "Moved forward (2nd reading)"
        result = "Passed" if v.result == "Passed" else v.result
        ballot = "for" if v.ballot == "Yes" else "against"
        human = c.human.get(v.bill_url, "")
        text = (v.plain + " " + human + " " + v.legal_title + " " + v.number).lower()
        words_ = f'<span class="t-plain">{escape(v.plain)}</span>' + (f'<span class="t-human">{escape(human)}</span>' if human else "")
        return (f'<div class="vitem{" has-human" if human else ""}" data-item data-ballot="{ballot}" data-topics="{_topics_attr(v.topics)}" data-text="{escape(text)}"><p>{words_}</p>'
                f'<div class="meta"><span class="mono soft">Bill {escape(v.number)} &middot; {stage} &middot; {escape(v.date)} &middot; {escape(result)}</span>'
                f'{link("https://openparliament.ca" + v.vote_url, "Vote record")}</div>'
                f'<div><span class="tagz {"pro" if ballot == "for" else "anti"}">Voted {ballot}</span>{_tags(v.topics)}</div>'
                f'<div class="fine">Official title: {escape(v.legal_title)}</div></div>')

    counts: dict[str, int] = {}
    for kv in c.key_votes:
        for t in set(kv.topics) - {"other"}:
            counts[t] = counts.get(t, 0) + 1
    tagged = bool(counts)
    chips = "".join(
        f'<label class="chip{"" if tagged else " off"}"><input type="checkbox" name="topic" value="{escape(k)}"{"" if tagged else " disabled"}>'
        f'<span>{escape(v)}{f" &middot; {counts[k]}" if counts.get(k) else ""}</span></label>' for k, v in TOPIC_LABELS.items())
    notag = "" if tagged else '<div class="fine">Topic filters need ANTHROPIC_API_KEY set when the server starts. Search by words still works.</div>'
    human_toggle = HUMAN_BUTTON if any(kv.bill_url in c.human for kv in c.key_votes) else ""
    vitems = "".join(vote_item(v) for v in c.key_votes) or '<div class="vitem soft">No bill-deciding votes on record this session.</div>'
    votes_view = f"""<div id="votes-view" class="hidden"><div class="grid"><form id="filter" class="cell s12 filter" style="padding-top:26px">
<a class="mono back" href="#card">&lsaquo; Back</a>
<div class="mono soft" style="margin-top:22px">Your MP &middot; {escape(mp.party)} &middot; {escape(mp.riding)}</div>
<h1 class="name">{escape(mp.name)}</h1>
<nav class="tabs" aria-label="Which votes"><a href="#votes" data-mode="all">All</a><a href="#votes-for" data-mode="for">Pro<span class="dot pro"></span></a><a href="#votes-against" data-mode="against">Anti<span class="dot anti"></span></a></nav>
<label for="q" class="mono soft">What do you care about? Filter {escape(mp.name)}'s record</label>
<input type="text" id="q" placeholder="Try: rent, clinics, transit&hellip;" autocomplete="off">
<div class="chips">{chips}</div>{notag}{human_toggle}<div class="mono soft" id="count" style="margin-top:12px;min-height:1em"></div>
<div class="fine">Votes that decided a bill (2nd or 3rd reading); {c.other_votes} other votes on amendments and procedure are not shown. Voting against a bill does not mean opposing everything in it, and MPs usually vote with their party. Plain-language descriptions are written by AI from Parliament's official summary of each bill, and &ldquo;Make it more human&rdquo; rewrites them again in everyday words; the official title is under each one.</div>
</form></div><div class="vgrid">{vitems}</div></div>"""

    footer = (f'{marquee("Know your MP")}<a class="bar mono" href="/">{"Find another MP" if site else "Look up another postal code"} <span class="arrow">&#8599;</span></a>'
              '<div class="grid"><div class="cell s12 fine" style="border-bottom:0">In Canada MPs almost always vote with their party, so a voting record says less than what an MP chooses to speak about and sponsor. '
              'Sources: openparliament.ca, ourcommons.ca, parl.ca. Descriptions are AI-written from those records; follow the links to check.'
              + (f' Updated <time datetime="{site["updated_iso"]}">{site["updated"]}</time>.' if site else "") + '</div></div>')

    body = f'{topbar("MP card")}{card_view}{votes_view}{footer}<script>{FILTER_JS}{WORDS_JS}</script>'
    if not site:
        return page(mp.name, body)
    title = f"{mp.name}, MP for {mp.riding}: votes, bills and speeches | Know Your MP"
    desc = (f"{mp.name} ({mp.party}) is the Member of Parliament for {mp.riding}. See how they voted, the bills they sponsored and what they "
            "speak about, in plain language with links to the sources.")
    return page(title, body, seo_head(title, desc, site["url"], c.photo_url, {
        "@context": "https://schema.org", "@type": "Person", "name": mp.name, "jobTitle": "Member of Parliament",
        "url": site["url"], "memberOf": {"@type": "Organization", "name": mp.party}, "image": c.photo_url,
        "workLocation": {"@type": "Place", "name": mp.riding}}))


HUMAN_BUTTON = ('<button type="button" class="hum mono" aria-pressed="false"><span class="sw" aria-hidden="true"></span>Make it more human'
                '<span class="soft">&middot; AI</span></button>')


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
        postal = one("q") or one("postal")
        by = "name" if one("by") == "name" else "postal"
        pick = int(one("pick")) if one("pick").isdigit() else None
        if self.path != "/mp":
            return self._send(page("Not found", "<h1>Not found</h1>"), 404)
        try:
            return self._send(card_page(service.card(postal, pick, by_name=by == "name"), postal, pick))
        except service.SplitPostcode as e:
            return self._send(choose_riding(e, postal, by))
        except service.UserError as e:
            return self._send(home(str(e), postal, by), 400)
        except Exception:
            return self._send(home("Something went wrong reading the public records. Please try again in a minute.", postal, by), 500)


def serve(port: int = 8000):
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)  # localhost only
    print(f"Open http://127.0.0.1:{port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
