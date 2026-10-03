# MP Card

Your MP and their stats: enter a postal code, see who represents you and what they actually do. Votes, bills and speeches are described in plain language, and every claim links to its source.

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

## Publishing as a static site
`python -m civic site` builds a page for every sitting MP (`dist/mp/<name>/`), a directory home page, `sitemap.xml` and `robots.txt`; each page has its own title, description, canonical address, social tags and an "Updated" date.
```
python -m civic site --limit 3          # try it on three MPs
python -m civic site --budget-minutes 300   # full build; exits 3 if it ran out of time (run again, it resumes from the cache)
```
The first full build is slow (hours: it reads public records politely, one request per second). After that it is mostly cache hits. `.github/workflows/publish.yml` rebuilds weekly and publishes to Cloudflare Pages. It needs three repository secrets: `ANTHROPIC_API_KEY`, `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`. Set `SITE_URL` (and the workflow's copy of it) to the address the site is served from.

`functions/api/postal.js` is a small Cloudflare Pages Function that looks up a postal code and redirects to that riding's page. The code is never logged, stored or put in the address.
