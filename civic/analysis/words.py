"""What an MP keeps coming back to: the words and phrases they use most in their speeches, counted, plus a bubble layout.

Counts are plain frequencies over the speeches we fetched (their most recent ones), after dropping common English
and House-procedure words. No AI is involved, so every number can be checked against the speeches.
"""
import html
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass

MAX_TERMS = 30
MIN_PHRASE = 4  # a two- or three-word phrase must recur this often to count as one term

STOP = set("""
a about above after again against all almost along already also although always am among an and another any anyone anything
are aren't around as at back be because been before being below between both but by can can't cannot could couldn't did didn't
do does doesn't doing don't done down during each either else enough even ever every everyone everything far few for from
further get gets getting give given go goes going gone got had hadn't has hasn't have haven't having he he's her here here's hers
herself him himself his how how's however i i'd i'll i'm i've if in into is isn't it it's its itself just know last least less
let let's like made make makes making many may maybe me might more most much must mustn't my myself need needs never new next
no nor not nothing now of off often on once one ones only or other others our ours ourselves out over own part per perhaps put
quite rather really right said same say saying says see seen several shall she she's should shouldn't since so some something
still such sure take taken than that that's the their theirs them themselves then there there's these they they'd they'll
they're they've thing things think this those though through thus to today together too toward towards under until up upon
us use used very want wants was wasn't way we we'd we'll we're we've well were weren't what what's when when's where where's
whether which while who who's whole whom whose why why's will with within without won't would wouldn't yes yet you you'd
you'll you're you've your yours yourself yourselves
also able across actually ago ahead already among another anyway around away became become becomes come comes coming
course day days different does done else end ensure especially example fact first found four go good great happen happened
help here high including indeed instead keep kind large later long look looking lot lots main matter mean means mentioned
moment much number old order particular past place point possible present probably really reason regard regarding said
second sense set show side simply since small sort start step talk talking tell term terms thank thanks three time times
top true try trying two us various week weeks whatever work working year years yesterday
mr mrs ms madam speaker hon honourable member members minister ministers government governments canada canada's canadian
canadians country house parliament people today bill bills motion question questions answer colleagues committee chair
deputy prime party parties opposition side debate debates order members' member's oral statement statements riding
colleague colleagues federal issue issues earlier information important bit ask asked forward speak
""".split())
MID = {"on", "of", "for", "and", "to", "in"}  # allowed inside a three-word phrase ("price on pollution")
TOKEN_RE = re.compile(r"[a-zà-öø-ÿ0-9]+(?:['’-][a-zà-öø-ÿ0-9]+)*")


@dataclass(frozen=True)
class Term:
    term: str
    count: int
    speeches: int  # how many speeches use it
    last_said: str  # yyyy-mm-dd


def _tokens(text: str) -> list[str]:
    plain = html.unescape(re.sub(r"<[^>]+>", " ", text)).lower().replace("’", "'")
    return TOKEN_RE.findall(plain)


def _keep(tok: str) -> bool:
    if tok in STOP:
        return False
    if tok.isdigit():
        return len(tok) == 4 and tok[:2] in ("19", "20")  # years like 2030, not stray numbers
    return len(tok) >= 3 or any(ch.isdigit() for ch in tok)


def top_terms(speeches, limit: int = MAX_TERMS) -> list[Term]:
    """First pass: rough counts to choose the terms. `_recount` then counts them exactly."""
    uni, bi, tri = Counter(), Counter(), Counter()
    for s in speeches:
        toks = _tokens(s.text)
        for j, t in enumerate(toks):
            if _keep(t):
                uni[t] += 1
            if j + 1 < len(toks) and _keep(t) and _keep(toks[j + 1]):
                bi[f"{t} {toks[j + 1]}"] += 1
            if j + 2 < len(toks) and _keep(t) and _keep(toks[j + 2]) and (_keep(toks[j + 1]) or toks[j + 1] in MID):
                tri[f"{t} {toks[j + 1]} {toks[j + 2]}"] += 1

    # Prefer the longest phrase that recurs, and take its uses out of its parts so nothing is counted twice.
    chosen: Counter = Counter()
    for p, n in tri.most_common():
        if n < MIN_PHRASE:
            break
        chosen[p] = n
        a, b, c = p.split(" ")
        for part in (f"{a} {b}", f"{b} {c}"):
            bi[part] -= n
        for w in (a, b, c):
            uni[w] -= n
    for p, n in sorted(bi.items(), key=lambda kv: -kv[1]):
        if n < MIN_PHRASE:
            break
        chosen[p] = n
        for w in p.split(" "):
            uni[w] -= n
    for w, n in uni.items():
        if n > 0:
            chosen[w] = n
    return _recount(speeches, [t for t, _ in chosen.most_common(limit * 3)], limit)


def _recount(speeches, candidates: list[str], limit: int) -> list[Term]:
    """Exact counts: in each speech, match the longest chosen phrase first, so a word inside a phrase is not counted again."""
    phrases = {tuple(t.split(" ")) for t in candidates}
    count, last = Counter(), {}
    seen: dict[str, set] = defaultdict(set)
    for i, s in enumerate(speeches):
        toks, when, j = _tokens(s.text), (s.time or "")[:10], 0
        while j < len(toks):
            for n in (3, 2, 1):
                key = tuple(toks[j:j + n])
                if len(key) == n and key in phrases:
                    t = " ".join(key)
                    count[t] += 1
                    seen[t].add(i)
                    last[t] = max(last.get(t, ""), when)
                    j += n
                    break
            else:
                j += 1
    return [Term(t, n, len(seen[t]), last[t]) for t, n in count.most_common(limit)]


def pack(counts: list[int], width: float, height: float, gap: float = 5, fill: float = 0.5) -> list[tuple[float, float, float]]:
    """Place one circle per count (area proportional to count) without overlaps, biggest nearest the centre.

    Greedy: each circle goes at the free spot touching one or two placed circles that is closest to the centre.
    Returns (x, y, r) in the same order as `counts`.
    """
    if not counts:
        return []
    cx, cy = width / 2, height / 2
    k = math.sqrt(fill * width * height / (math.pi * sum(counts)))
    while True:
        placed = _try_pack([k * math.sqrt(c) for c in counts], width, height, gap, cx, cy)
        if placed:
            return placed
        k *= 0.93


def _try_pack(radii, width, height, gap, cx, cy):
    placed: list[tuple[float, float, float]] = []
    squash = width / height

    def free(x, y, r):
        if x - r < 0 or x + r > width or y - r < 0 or y + r > height:
            return False
        return all(math.hypot(x - px, y - py) >= r + pr + gap - 0.01 for px, py, pr in placed)

    for r in radii:
        if not placed:
            cands = [(cx, cy)]
        else:
            cands = []
            for i, (ax, ay, ar) in enumerate(placed):
                d = ar + r + gap
                cands += [(ax + d * math.cos(a * math.pi / 36), ay + d * math.sin(a * math.pi / 36)) for a in range(72)]
                for bx, by, br in placed[i + 1:]:
                    d1, d2, dist = ar + r + gap, br + r + gap, math.hypot(bx - ax, by - ay)
                    if dist == 0 or dist > d1 + d2 or dist < abs(d1 - d2):
                        continue
                    a = (d1 * d1 - d2 * d2 + dist * dist) / (2 * dist)
                    h = math.sqrt(max(0.0, d1 * d1 - a * a))
                    mx, my = ax + a * (bx - ax) / dist, ay + a * (by - ay) / dist
                    for sgn in (1, -1):
                        cands.append((mx + sgn * h * (by - ay) / dist, my - sgn * h * (bx - ax) / dist))
        ok = [p for p in cands if free(p[0], p[1], r)]
        if not ok:
            return None
        x, y = min(ok, key=lambda p: ((p[0] - cx) / squash) ** 2 + (p[1] - cy) ** 2)
        placed.append((x, y, r))
    return placed
