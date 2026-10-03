"""The 'At a glance' summaries: one cited sentence on what an MP voted for, one on what they voted against.

Each side is written from only that side's votes, so a "for" sentence can only cite bills they voted for.
Every sentence must reference real items; invalid output is dropped and the card shows a plain count instead.
"""
import json
import re

from ..config import LETTER_MODEL
from .classify import reply_text

MAX_SENTENCES = 4
KINDS = ("for", "against", "other")


def _prompt(name: str, party: str, kind: str, items: dict[str, str], stats: str) -> str:
    listing = "\n".join(f"[{k}] {v}" for k, v in items.items())
    return f"""Write ONE plain-English sentence summing up the bills {name} ({party}) voted {kind.upper()}, using ONLY the items below.

Facts: {stats}

Items (each is a bill they voted {kind}; each has an id in brackets):
{listing}

Rules:
- One sentence, under 35 words, in everyday language a teenager would understand. Start with "{name} voted {kind}".
- Group the bills by what they are about (for example housing, taxes, sentencing) and name the most notable two to four.
- Cite one to four item ids the sentence is based on.
- Only say what the items show. Voting {kind} a bill describes a vote, not their beliefs or motives; never guess why.
- Neutral and nonpartisan: no praise, no criticism, no loaded words, no "gotcha" framing.

Reply with only JSON: [{{"text": "sentence", "refs": ["v1", "v2"]}}]"""


def validate(reply: str, valid_ids: set[str]) -> list[dict]:
    m = re.search(r"\[.*\]", reply, flags=re.S)
    if not m:
        return []
    try:
        raw = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    out = []
    for s in raw[:MAX_SENTENCES]:
        if not isinstance(s, dict) or not isinstance(s.get("text"), str):
            continue
        refs = [r for r in s.get("refs", []) if r in valid_ids]
        kind = s.get("kind") if s.get("kind") in KINDS else "other"
        if refs:  # a claim with no valid source is dropped, never shown
            out.append({"text": s["text"].strip(), "kind": kind, "refs": refs})
    return out


def side(client, name: str, party: str, kind: str, items: dict[str, str], stats: str) -> dict | None:
    """One sentence about the bills they voted `kind` ("for" / "against"), citing only `items`, or None."""
    if client is None or not items:
        return None
    resp = client.messages.create(
        model=LETTER_MODEL, max_tokens=2000, messages=[{"role": "user", "content": _prompt(name, party, kind, items, stats)}]
    )
    got = validate(reply_text(resp), set(items))
    return {**got[0], "kind": kind} if got else None
