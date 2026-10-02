# MP Card

Your MP as a baseball card: enter a postal code, see who represents you and what they actually do. Votes, bills and speeches are described in plain language, and every claim links to its source.

## Run
```
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
export ANTHROPIC_API_KEY=...   # optional; enables plain-language bill descriptions, topics and the overview. Never commit it.
python -m civic web            # http://127.0.0.1:8000 (this machine only)
python -m civic profile M5V3L9 # plain text version in the terminal
pytest
```

The first card for a new MP takes a minute or two (it reads public records and describes each bill once). After that it is cached in `~/.civic/cache.db` (override with `CIVIC_DB`). Set `CIVIC_CONTACT` to your own email for the User-Agent sent to upstream services.

## What is on the card
Time in office, votes this session, how often they voted with their party, bills sponsored; an AI-written overview; how they voted on bills; bills they sponsored; what they choose to speak about; roles and committees. A search box and topic chips filter the whole card.

## Principles
Nonpartisan and cited: same card for every MP, every claim links to a primary source (openparliament.ca, ourcommons.ca, parl.ca). Postal codes are never stored or logged. Be kind to upstream services: cache aggressively, throttle, descriptive User-Agent.

## History
The earlier version also ranked opportunities to act on (committee briefs, bills, petitions) and drafted letters. That work is preserved in git: `git checkout pre-card-only`. See `BRIEF.md` for the original plan and `docs/data-notes.md` for verified data-source notes.
