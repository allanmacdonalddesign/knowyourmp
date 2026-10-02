"""A short, cited, plain-language overview of an MP. Every sentence must reference real items; invalid output is dropped."""
import json
import re

from ..config import LETTER_MODEL
from .classify import reply_text

MAX_SENTENCES = 4


def _prompt(name: str, party: str, items: dict[str, str], stats: str) -> str:
    listing = "\n".join(f"[{k}] {v}" for k, v in items.items())
    return f"""Write a short plain-English overview of what {name} ({party}) stands for, using ONLY the items below.

Facts: {stats}

Items (each has an id in brackets):
{listing}

Rules:
- 2 to 4 sentences, each under 30 words, in everyday language a teenager would understand.
- Every sentence must cite one to three item ids it is based on.
- Only say what the items show. "Voted for" / "voted against" describe a vote on that bill, not their beliefs or motives; never guess why.
- Neutral and nonpartisan: no praise, no criticism, no loaded words, no "gotcha" framing.
- You may point out that MPs usually vote with their party, but do not claim anything about party positions beyond the items.
- Cover three things where the items allow: what they voted for, what they voted against, and what they choose to speak or sponsor about.

Reply with only JSON: [{{"text": "sentence", "refs": ["v1", "s2"]}}, ...]"""


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
        if refs:  # a claim with no valid source is dropped, never shown
            out.append({"text": s["text"].strip(), "refs": refs})
    return out


def generate(client, name: str, party: str, items: dict[str, str], stats: str) -> list[dict]:
    if client is None or not items:
        return []
    resp = client.messages.create(
        model=LETTER_MODEL, max_tokens=3000, messages=[{"role": "user", "content": _prompt(name, party, items, stats)}]
    )
    return validate(reply_text(resp), set(items))
