"""LEGISinfo bulk JSON: current stage of every bill."""
from dataclasses import dataclass

from ..http import Fetcher

URL = "https://www.parl.ca/legisinfo/en/bills/json"

COMMITTEE = "At consideration in committee in the House of Commons"
SECOND = "At second reading in the House of Commons"
REPORT = "At report stage in the House of Commons"
THIRD = "At third reading in the House of Commons"
ACTIVE_HOUSE_STATUSES = {COMMITTEE, SECOND, REPORT, THIRD}


@dataclass(frozen=True)
class LegisBill:
    number: str
    title: str
    status: str
    is_private_member: bool
    sponsor: str
    url: str


def parse(data: list[dict]) -> list[LegisBill]:
    out = []
    for b in data:
        if not b.get("IsHouseBill"):
            continue
        number = b["NumberCode"]
        out.append(
            LegisBill(
                number=number,
                title=b.get("ShortTitleEn") or b.get("LongTitleEn") or "",
                status=b.get("StatusNameEn") or "",
                is_private_member=b.get("BillDocumentTypeNameEn", "").startswith("Private Member"),
                sponsor=(b.get("SponsorPersonName") or "").strip(),
                url=f"https://www.parl.ca/legisinfo/en/bill/{b['ParliamentNumber']}-{b['SessionNumber']}/{number}",
            )
        )
    return out


def fetch_active(fetcher: Fetcher) -> list[LegisBill]:
    return [b for b in parse(fetcher.get_json(URL)) if b.status in ACTIVE_HOUSE_STATUSES]
