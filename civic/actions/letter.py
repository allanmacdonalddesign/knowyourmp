"""Letter drafting: a short, personal starting point citing the MP's real statements. Never sends anything."""
import re
from dataclasses import dataclass, field

from ..analysis.classify import reply_text
from ..analysis.profile import Claim
from ..config import LETTER_MODEL

FOOTER = (
    "\n---\nThis is a starting point, not a finished letter. Staff filter out identical form letters, "
    "so please rewrite it in your own words and add why this matters to you personally. "
    "Fill in the [brackets]. This tool does not send anything."
)
URL_RE = re.compile(r"https?://[^\s)\]>\"']+")


@dataclass
class LetterInput:
    mp_name: str
    riding: str
    opportunity_title: str
    opportunity_url: str
    kind: str  # committee_study | bill | petition
    why: str = ""
    ask: str = ""
    position: str = "support"
    mp_on_committee: str | None = None  # committee code if the MP sits on it
    topics: list[str] = field(default_factory=list)


def pick_statements(claims: list[Claim], topics: list[str], n: int = 2) -> list[Claim]:
    """Only the MP's own statements, preferring topic overlap. Never invent or force a citation."""
    with_quote = [c for c in claims if c.quote]
    relevant = [c for c in with_quote if set(c.topics) & set(topics) - {"other"}]
    return relevant[:n]


def default_ask(i: LetterInput) -> str:
    if i.ask:
        return i.ask
    if i.kind == "committee_study":
        if i.mp_on_committee:
            return "As a member of this committee, please raise these concerns with your colleagues during the study."
        return "Please bring these concerns to the attention of your colleagues on the committee."
    if i.kind == "bill":
        verb = "vote in favour of" if i.position == "support" else "vote against"
        return f"Please {verb} this bill, and let me know your position."
    return "Please support this petition and let me know your position."


def skeleton(i: LetterInput, cited: list[Claim]) -> str:
    parts = [f"Dear {i.mp_name},", "",
             f"I am a constituent in {i.riding} writing about {i.opportunity_title} ({i.opportunity_url})."]
    parts.append(i.why or "[Add one or two sentences, in your own words, about why this matters to you.]")
    for c in cited:
        parts.append(f'You spoke about a related issue: "{c.quote[:220].rstrip()}..." ({c.url})')
    parts += [default_ask(i), "", "Sincerely,", "[YOUR NAME]"]
    return "\n".join(parts)


def _prompt(i: LetterInput, cited: list[Claim]) -> str:
    quotes = "\n".join(f"- ({c.url}) {c.quote}" for c in cited) or "(none: do not cite any statement)"
    return f"""Draft a short letter from a constituent to their Member of Parliament.

MP: {i.mp_name}, riding of {i.riding}
Subject: {i.opportunity_title} ({i.opportunity_url})
What the constituent says matters to them: {i.why or "(not provided: leave a [bracketed] placeholder for them to fill in)"}
The one ask: {default_ask(i)}

The MP's own past statements you may cite (use only these, with the URL in parentheses right after):
{quotes}

Rules:
- At most 180 words. Plain, polite, specific. First person.
- Exactly one clear ask. No pressure, flattery or gotcha framing; neutral and nonpartisan.
- Only cite statements from the list above, accurately; never invent quotes, facts or personal details. Use [brackets] for anything the writer must fill in.
- Address the MP as "Dear {i.mp_name}" with no honorific or gendered title, and refer to them by full name or "you".
- Do not claim the writer has done anything not stated above (for example submitting a brief, attaching documents, or having met the MP). Do not add an address or date block.
- Prefer quoting the part of a statement most relevant to the subject, accurately and briefly.
- Sign off with [YOUR NAME].
- Output only the letter."""


def valid_citations(text: str, allowed: set[str]) -> bool:
    return all(u.rstrip(".,;") in allowed for u in URL_RE.findall(text))


def draft(i: LetterInput, claims: list[Claim], client=None) -> str:
    cited = pick_statements(claims, topics=i.topics)
    allowed = {c.url for c in cited} | {i.opportunity_url}
    if client is not None:
        for _ in range(2):
            resp = client.messages.create(
                model=LETTER_MODEL, max_tokens=3000, messages=[{"role": "user", "content": _prompt(i, cited)}]
            )
            text = reply_text(resp)
            if valid_citations(text, allowed):
                return text + FOOTER
    return skeleton(i, cited) + FOOTER

