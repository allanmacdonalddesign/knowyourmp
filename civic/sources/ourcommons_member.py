"""ourcommons.ca member page: current roles and committee memberships.

Scraping isolated here. The page has a "Current Roles" block with
"Committees | Member | <CODE> | <Name>" style runs; if the layout changes, only this file breaks.
"""
import re
from dataclasses import dataclass, field

from ..http import Fetcher


@dataclass
class MemberRoles:
    roles: list[str] = field(default_factory=list)  # e.g. "Parliamentary Secretary to ..."
    committees: list[tuple[str, str]] = field(default_factory=list)  # (code, name)


def _text_runs(html: str) -> list[str]:
    html = re.sub(r"<(script|style).*?</\1>", "", html, flags=re.S | re.I)
    runs = re.sub(r"<[^>]+>", "\n", html).split("\n")
    return [re.sub(r"\s+", " ", r).strip() for r in runs if r.strip()]


def parse_roles(html: str) -> MemberRoles:
    runs = _text_runs(html)
    out = MemberRoles()
    try:
        start = runs.index("Current Roles")
    except ValueError:
        return out
    section = None
    i = start + 1
    while i < len(runs):
        r = runs[i]
        if r in ("Parliamentary Associations and Interparliamentary Groups", "All Roles", "Past Roles", "Contact", "Recent Work"):
            break
        if r in ("Offices and Roles as a Parliamentarian", "Executive Committees"):
            i += 1
            continue
        if r == "Committees":
            section = "committees"
        elif section == "committees":
            if r in ("Member", "Chair", "Vice-Chair"):
                pass
            elif re.fullmatch(r"[A-Z]{3,6}", r) and i + 1 < len(runs):
                out.committees.append((r, runs[i + 1]))
                i += 1
        else:
            out.roles.append(r.replace("&#x2014;", "—"))
        i += 1
    return out


def fetch_roles(fetcher: Fetcher, ourcommons_url: str) -> MemberRoles:
    return parse_roles(fetcher.get_text(ourcommons_url))
