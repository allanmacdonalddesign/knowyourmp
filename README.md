# Civic Leverage Tool

Helps Canadians find where they can still change an outcome, and what to do. See `BRIEF.md` for the full plan and `docs/data-notes.md` for verified data-source details.

## Status
- Phase 0 (explore and verify): done
- Phase 1 (postal code to cited MP profile, CLI): done
- Phase 2 (opportunities and ranking): done for committee studies, bills and petitions; Gazette not yet
- Phase 3 (action helpers): done (cited letter drafts, brief submission guide)
- Phase 4 (web UI): done. Flow: postal code -> MP "baseball card" (votes, party-line record, bills, statements, committees) -> filter by what you care about -> ways to act

## Setup
```
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
export ANTHROPIC_API_KEY=...   # optional; enables topic tagging. Never commit it.
```

## Use
```
python -m civic profile M5V3L9
python -m civic profile <POSTAL> --pick 2    # when a postal code covers more than one riding
python -m civic opportunities M5V3L9 --interests housing,climate   # needs ANTHROPIC_API_KEY
python -m civic web      # simple local page at http://127.0.0.1:8000 (this machine only)
# then, using the item numbers from `opportunities`:
python -m civic brief M5V3L9 --interests health,gender --item 1
python -m civic letter M5V3L9 --interests health,gender --item 1 --why "your own reason"
pytest
```

`letter` prints a draft only and never sends anything; it cites only the MP's real statements (every URL is checked against the real list, with a plain template as fallback). `brief` prints the real deadline, limits and form link; you submit it yourself.

Cache lives at `~/.civic/cache.db` (override with `CIVIC_DB`). Set `CIVIC_CONTACT` to your own email for the User-Agent sent to upstream services.
