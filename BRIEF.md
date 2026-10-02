# Civic Leverage Tool — Project Brief

## Mission

Help Canadians take effective civic action. Most civic tools show what already happened. This one answers a different question: "Where can I, specifically, still change an outcome, and what exactly should I do?"

Every design decision follows from this framing: favour actions that are tractable and neglected over actions that are visible but low-leverage.

## Key context about the Canadian system

Read this before designing features. It shapes almost everything.

- Party discipline is very strong. MPs rarely vote against their party on whipped votes, so "pressure your MP before the vote" is usually low-leverage. Verify this ourselves from the ballot data early on, and show users the real dissent rate.
- The real leverage points are less visible:
  - Committee stage, where bills get amended and anyone can submit a written brief.
  - Private members' bills, which often get free votes.
  - E-petitions, which get a mandatory government response at 500 signatures.
  - Regulatory consultations in Canada Gazette Part I.
  - Influence on caucus and ministers through a sympathetic MP.
- Personalized contact beats volume. Identical form letters get filtered out by staff, so the tool helps people write their own specific letters. It must never mass-send.

## User journey (the product)

1. **Find my MP.** User enters a postal code and gets their riding and MP.
2. **Understand my MP.** Show what the MP is responsible for (their roles) separately from what they personally champion (their choices).
3. **What's coming up that I can affect?** List open opportunities, ranked by the overlap between the user's interests, the MP's interests, and what's open now.
4. **Take action.** Each opportunity comes with one concrete, stage-appropriate action and help doing it.
5. *(Later)* **Follow up.** Ask whether the user got a response and whether the outcome changed, so we learn which actions actually work.

## Data sources

Verify every endpoint and field name by making real requests before writing code that depends on it. The notes below are starting points, not guarantees.

### Represent API (Open North): postal code to MP

- `https://represent.opennorth.ca/postcodes/{POSTALCODE}/` (postal code uppercase, no space)
- Check both `representatives_centroid` and `representatives_concordance`, and filter for `elected_office == "MP"`.
- Some postal codes straddle ridings. If more than one MP comes back, ask the user to choose or to enter a full address. Never silently guess.
- Respect their rate limits.

### openparliament.ca: the historical record (House of Commons only)

- API root: `https://api.openparliament.ca/`. Request JSON with `?format=json` or an `Accept: application/json` header.
- Send a descriptive User-Agent with contact info, and an `API-Version` header if their docs ask for it. Check their API docs page for current requirements.
- Useful resources to explore:
  - `/politicians/` and `/politicians/{slug}/`
  - `/speeches/?politician=...`
  - `/bills/`
  - `/votes/` and `/votes/ballots/?politician=...`
  - `/committees/`
- For anything heavy (bulk speech analysis), use their full database download rather than hammering the API. It's a one-person project, so be a good citizen.
- Limitation: there is no Senate coverage, and it is mostly backward-looking.

### Forward-looking sources (needed for step 3)

openparliament doesn't track what's scheduled, so step 3 needs these:

| Source | Use |
|---|---|
| LEGISinfo (parl.ca/legisinfo) | Current stage of every bill; look for its JSON/XML exports |
| ourcommons.ca committee pages | Meeting schedules, current studies, calls for briefs and deadlines |
| Notice Paper / Order Paper (ourcommons.ca) | Motions and bills about to come up |
| petitions.ourcommons.ca | Open e-petitions, signature counts, sponsoring MPs |
| Canada Gazette Part I (gazette.gc.ca) | Proposed regulations open for comment |

Prefer official structured exports over HTML scraping wherever they exist. Where scraping is unavoidable, isolate it in its own module so breakage is contained.

## The core insight for Step 2: chosen signals vs. assigned signals

Most House speech is assigned by party role. Ministers speak about their portfolio, critics attack the matching ministry, and backbenchers deliver party lines. Naively counting speech topics measures the party and the job title, not the person.

**Chosen signals, weighted heavily:**

- Members' statements (Standing Order 31, the 60-second statements before Question Period). These are often riding-focused. Identify them by the debate section heading; inspect real data to find how they're labelled.
- Private members' bills and motions they sponsor. Each MP gets very few, so what they spend them on is revealing.
- Petitions they present on constituents' behalf.
- Long-held committee memberships.

**Assigned signals, shown separately and weighted lightly when inferring personal interest:**

- Ministerial or critic roles, and speeches clearly within that portfolio
- Government or opposition speeches during bill debate

**Output:** a short, plain-language profile with two clearly separated sections, "Responsible for" and "Personally champions", where every claim links to its source (a speech, bill, or vote). No claim without a citation.

**Topic classification:** use the Anthropic API (Claude) to tag speeches and bills against a fixed topic taxonomy. Define the taxonomy in one config file so it stays consistent (for example: housing, health, climate/environment, immigration, justice, Indigenous affairs, economy/cost of living, defence, transportation, etc.). Cache classifications; never re-classify the same speech twice.

## Step 3: ranking opportunities

For each open opportunity, compute a leverage score from these factors:

- **Overlap:** user interests ∩ MP interests ∩ topic of the opportunity. Overlap with a sympathetic MP is highest leverage, because we're arming an ally, not converting an opponent.
- **Stage:** committee stage, open consultations, and private members' bills rank above final votes on whipped government bills.
- **Time remaining:** deadlines soon but not past.
- **Neglectedness** (if measurable): few briefs or witnesses so far, or a petition close to 500 signatures.

Keep the scoring simple, transparent, and explainable to the user ("Ranked high because..."). No black boxes.

## Step 4: action types

| Situation | Action |
|---|---|
| Bill in committee | Submit a written brief; email committee members (not only your own MP) |
| Topic your MP champions | Request a constituency office meeting; MPs are usually in-riding on Fridays and during non-sitting weeks |
| Open petition | Sign; if near 500, help gather signatures |
| Upcoming vote / general | Personalized letter citing the MP's own past statements |
| Gazette consultation | Submit a comment before the deadline |

**Letter drafting rules:** draft a starting point that cites the MP's real statements with links, make one clear ask, and keep it short. Prompt the user to rewrite it in their own words. Never send anything automatically.

## Principles and guardrails

- **Nonpartisan.** Same treatment for every party. No "gotcha" framing. Present records factually with sources.
- **Cite everything.** Every claim about an MP links to the primary source.
- **No mass messaging, ever.** The tool helps individuals write; it doesn't send.
- **Privacy.** Store postal codes and interests minimally. Don't build user profiles beyond what the feature needs.
- **Be kind to upstream services.** Cache aggressively, prefer bulk downloads, use a descriptive User-Agent.
- **Measure actions, not page views.** Track briefs submitted, letters written, meetings requested, and responses received.

## Build plan

Build in phases. Get each one working end-to-end before starting the next.

### Phase 0: Explore and verify (do this first)

- Hit each data source and save sample responses to `samples/`.
- Write `docs/data-notes.md` recording actual endpoints, fields, quirks, and rate limits.
- Answer from real data: how are Members' statements identified? How often do MPs break party lines?

### Phase 1: Postal code to MP profile (CLI)

- `python -m civic profile M5V3L9`, which prints the MP, riding, roles, and a "Personally champions" profile with citations.
- Handle split postal codes.
- Local cache: SQLite.

### Phase 2: Opportunities

- Ingest LEGISinfo, committee schedules, and open petitions.
- `python -m civic opportunities M5V3L9 --interests housing,climate`, which prints ranked opportunities, each with a score explanation and a suggested action.

### Phase 3: Action helpers

- Letter draft generator with citations.
- Brief submission guide that pulls the committee's actual requirements and deadline.

### Phase 4: Web UI

- Only after the CLI proves the logic. Keep it simple.

### Phase 5: Follow-up loop

- Opt-in check-ins: did you get a response? Did the bill change?

## Tech preferences

- Python 3.11+, httpx, SQLite (via sqlite3 or SQLModel), typer for the CLI
- Anthropic Python SDK for classification and drafting; API key from the environment, never committed
- pytest, with recorded sample responses as fixtures so tests don't hit live APIs
- Small modules: `sources/` (one file per data source), `analysis/`, `ranking/`, `actions/`, `cli.py`

## How to work in this repo

- Verify against real data before assuming any API shape.
- When an upstream source is ambiguous or broken, note it in `docs/data-notes.md` and ask rather than guess.
- Keep commits small and focused on one phase or feature.
