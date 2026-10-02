# Civic Leverage Tool

Helps Canadians find where they can still change an outcome, and what to do. See `BRIEF.md` for the full plan and `docs/data-notes.md` for verified data-source details.

## Status
- Phase 0 (explore and verify): done
- Phase 1 (postal code to cited MP profile, CLI): done
- Phase 2 (opportunities and ranking): not started

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
pytest
```

Cache lives at `~/.civic/cache.db` (override with `CIVIC_DB`). Set `CIVIC_CONTACT` to your own email for the User-Agent sent to upstream services.
