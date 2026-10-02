# Data notes (Phase 0, verified 2026-10-01)

All requests sent with `User-Agent: civic-leverage-tool/0.1 (allan@pragmatics.studio)`. Samples live in `samples/`.

## Represent API (Open North) — WORKS
- `GET https://represent.opennorth.ca/postcodes/M5V3L9/` → 200. Sample: `samples/represent_postcode_M5V3L9.json`.
- Top-level keys: `code, city, province, centroid, boundaries_concordance, boundaries_centroid, representatives_centroid`.
- **`representatives_concordance` is absent** for this postcode and `boundaries_concordance` is `[]`. Concordance only appears when a postcode straddles boundaries, so a split postcode is detected by its presence/non-empty. Still need a known split postcode to verify its shape.
- MP = entry in `representatives_centroid` with `elected_office == "MP"` (4 reps returned; 1 MP: Chi Nguyen, Liberal, "Spadina—Harbourfront").
- Useful MP fields: `name, party_name, district_name, url (ourcommons), email, offices[] (legislature / constituency, with tel + postal)`.
- Riding names have changed with the new boundaries (`Spadina—Fort York` appears in `boundaries_centroid`; the MP is for `Spadina—Harbourfront`). Use the MP entry's `district_name`, not the boundary list.

## openparliament.ca — WORKS
- Root `https://api.openparliament.ca/`; `?format=json` works. No `API-Version` header was needed so far (re-check their docs page).
- Pagination: `{"pagination": {"offset","limit","next_url","previous_url"}}`; list items under `objects`.
- `/politicians/{slug}/`: `memberships[]` (start/end dates, party, riding), `other_info.parl_mp_id`, `links`, `email`, `voice`. Note Freeland's last membership ended 2026-01-12, so slugs of former MPs still resolve.
- `/politicians/` list items have only `name, url, current_party, current_riding, image`. Slug is the last path segment of `url`. Mapping Represent's MP to a slug needs a name match (or `parl_mp_id` from the ourcommons URL, e.g. `chi-nguyen(123192)`); to be built and verified.
- `/speeches/?politician={slug}`: items have `time, attribution, content (HTML), url, politician_url, procedural, source_id, document_url`. **Heading fields `h1/h2/h3` exist only on House debate speeches; committee speeches have none.**
- **Members' statements** are identified by `h1 == "Statements by Members"`, with `h2` as the statement's title (e.g. "2026 Canadian Screen Awards"). Confirmed on a real record (debate 2026-06-05). Other `h1` values seen: `Government Orders`, `Oral Questions`.
- `/votes/?session=45-1`: items have `bill_url, number, date, description, result, yea_total, nay_total, paired_total, url`. `/votes/{session}/{n}/` adds `party_votes[]` with a per-party `disagreement` fraction.
- `/votes/ballots/?politician={slug}`: items have `vote_url, politician_url, ballot`.
- Rate limits: not documented in what I've read; I slept 1s between requests. Bulk analysis should use their database dump (not yet checked).

## Party-line dissent (answers a Phase 0 question)
- Sampled the 60 most recent House votes (session 45-1): mean per-party `disagreement` is **0.03%**, and **no vote** had any party split more than 5%. Data: `samples/dissent_sample.json`.
- Caveat: the sample is recent votes only, not all of the session, and I did not separate whipped from free votes. A bigger sample should be run before showing a number to users.

## LEGISinfo — WORKS (bulk JSON)
- `GET https://www.parl.ca/legisinfo/en/bills/json` → 200, ~950 KB, a JSON array of 188 bills for the current session. Sample: `samples/legisinfo_bills.json`.
- Fields: `NumberCode, LongTitleEn, StatusNameEn, LatestCompletedMajorStageNameEn, BillDocumentTypeNameEn (Private Member's Bill / House Government Bill / Senate …), SponsorPersonId, SponsorPersonName, IsHouseBill, PassedHouseFirstReadingDateTime, BillStages`.
- **`OngoingStageNameEn` is null for all 188 bills**, so "current stage" comes from `StatusNameEn` / `LatestCompletedMajorStageNameEn` instead. `BillStages` was empty in the one bill inspected. Not yet verified whether it fills in for bills further along.
- `SponsorPersonName` was a blank `' '` on the bill inspected, so sponsor linking may need `SponsorPersonId`; to verify.
- 91 of 188 are private members' bills, which is useful for the leverage ranking.

## Petitions (ourcommons.ca) — WORKS via the page's own search endpoint, unfiltered only
- The XML/CSV export (`output=xml|csv`) is gated by reCAPTCHA; we do not use it.
- The search page loads results by `POST https://www.ourcommons.ca/petitions/en/Petition/SearchAsync` (form body `reCaptchaAction=SEARCH`), returning JSON `{success, html, ...}` where `html` is a results fragment. Sample: `samples/petitions_searchasync.json`.
- The page's own JS (`isCaptchaRequired`) only requires a reCAPTCHA token when a filter is set (`sponsor, keyword, text, type, status`, a non-default `order`, or xml/csv output). The plain default listing needs none, so we use only the unfiltered request and **never send filters or work around the captcha**. Topic/status filtering is done on our side.
- Default listing: "95 results found", 20 per page (`RPP=20`), `Page=N` for paging (page 2 request tested above returns different petition ids). Re-check that the default view is open petitions only.
- Parseable per row: petition id (`e-7775`), category ("Social affairs and equality"), keyword tags (e.g. "Housing", a province), status text and closing date ("Open for signature until January 27, 2027"), sponsoring MP name, signature count, and a link `Details?Petition=e-7775`. The HTML contains each row twice (desktop `<tr>` and a mobile `<div>`), so parse only the `<tr class="Pub">` rows.
- Petition titles/text are not in the list; they need the Details page (not yet fetched).
- robots.txt (`ourcommons.ca/robots.txt`) does not disallow `/petitions/`. Keep to one request per page with the descriptive User-Agent and cache.
- This is scraping an internal endpoint, so isolate it in `sources/petitions.py` and expect breakage.

## Committees (ourcommons.ca) — PARTIAL
- `https://www.ourcommons.ca/Committees/en/Work?parl=45&session=1` → 200 HTML (`samples/committees_work.html`), links like `/Committees/en/ENVI/StudyActivity?studyActivityId=…`. No structured export found yet; this will need an isolated scraper in `sources/`. Calls for briefs and deadlines not yet located.

## Canada Gazette Part I — PARTIAL
- `https://gazette.gc.ca/rp-pr/p1/2026/index-eng.html` → 200 HTML (`samples/gazette_p1_2026_index.html`). No structured feed found yet; scraping or an RSS feed to look for.

## Order Paper / Notice Paper (ourcommons.ca) — PARTIAL (HTML only)
- `https://www.ourcommons.ca/en/notice-paper` is a 404. `https://www.ourcommons.ca/DocumentViewer/en/house/latest-sitting` redirects to `/documentviewer/en/45-1/house/sitting-145/order-notice` (Order Paper and Notice Paper No. 145, 2026-10-05). Sample: `samples/order_notice_paper.html` (~150 KB HTML).
- HTML only; no structured export found. Section parsing (Private Members' Business, Government Orders, etc.) not yet done. Low priority for v1: LEGISinfo plus the petitions list already cover bills and PMBs.

## openparliament operational rules (from https://openparliament.ca/api/)
- Rate limit exists: heavy concurrency gets HTTP 429. Keep requests sequential (I used 1s sleeps).
- Send `API-Version: v1` (or `?version=v1`) to pin the response shape; the API warns of breaking changes.
- Put an email in the User-Agent (not enforced).
- Bulk data: monthly Postgres dump at https://openparliament.ca/data-download/ (`openparliament.public.sql.bz2`, ~1.2 GB compressed / ~6 GB uncompressed as of mid 2023). Use this for bulk speech analysis; not downloaded yet.

## Split postal codes — NOT YET OBSERVED
- Tried ~25 postal codes. None returned more than one federal MP. `G0A1A0` has a non-empty `boundaries_concordance` and `representatives_concordance` array but it was not federal: the single MP came from `representatives_centroid` and the concordance list had no federal-district entry. Sample: `samples/represent_postcode_G0A1A0_split.json`.
- Until a real straddling federal postcode is found, code must treat "more than one MP across centroid + concordance (deduped by name)" as a split, ask the user to choose or give a full address, and never pick silently. Tests will use a hand-built fixture for this case, clearly labelled synthetic.

## Facts used by Phase 1 (verified)
- openparliament `/politicians/?name=Full+Name` returns the matching MP (use exact-name match; ambiguous names return None rather than guess).
- openparliament `/bills/?sponsor_politician={slug}` lists a member's sponsored bills (slug, not path). Bill detail gives `private_member_bill`, `sponsor_politician_url`, `status`.
- Roles and current committees are not in openparliament. They come from the ourcommons member page ("Current Roles" block); parsed in `civic/sources/ourcommons_member.py`.
- Committee tenure is unavailable, so committees are shown under "Responsible for", not as a chosen signal.
- Petitions an MP has presented: no source found yet.
- Topic tagging: Claude Haiku 4.5, taxonomy in `civic/topics.json`, cached per source URL in SQLite.

## Facts used by Phase 2 (verified)
- Calls for briefs: `https://www.ourcommons.ca/Committees/en/Participate` lists the studies "currently seeking input" (links `.../StudyActivity?studyActivityId=N`). Each study page has "Submit a brief before 11:59 p.m. (EDT) on <date>", a brief-size limit, and live counts "Briefs (N)" and "Witnesses (N)", which we use as the neglectedness signal. Some studies show no deadline (e.g. bill studies), so deadline can be None.
- The study page path is case-insensitive (`/committees/` and `/Committees/` both work).
- LEGISinfo stages used: "At consideration in committee / at second reading / at report stage / at third reading in the House of Commons". House bills only; "Outside the Order of Precedence" PMBs are skipped.
- Petition detail page contains the full request text from "We, the undersigned" to "History"; used for topic tagging and a short title.
- Bills that already appear as an open committee study (title "Bill C-xxx") are deduped.
- Not done: Canada Gazette Part I consultations (HTML only), Order Paper.
- Cost note: first run tags about 130 items with Claude (cached afterwards) and fetches about 95 petition pages at 1 request per second.

## Facts used by Phase 3 (verified)
- Brief form: each study page links to `/committee-participation/en/submit-brief/{code}/{studyId}`: an online form (name, email, phone, country, upload). Its "Conditions for submission" text is parsed for the guide; it links the House's "Guide for Submitting Briefs" (`/Procedure/Guides/brief-e.html`) and the clerk contact page.
- Committee members: `https://www.ourcommons.ca/Committees/en/{CODE}/Members` lists Chair, Vice-Chairs, Members (name, party, riding). No email addresses are listed there, so the guide links to the page rather than guessing addresses.
- Claude replies can begin with a thinking block, so code must join only the text blocks (`reply_text`), not read `content[0].text`.

## Facts used for plain-language cards (verified)
- `/votes/?session=45-1&limit=1000` returns every House vote with description, result and `bill_url` in ONE request (174 votes), so no per-vote fetch is needed to find bill-deciding votes. Descriptions starting "2nd reading" / "3rd reading" with a `bill_url` are bill-passage votes; amendments, "Government Business" motions and supply votes are procedural and are only counted.
- `/votes/ballots/?politician=slug&limit=1000` lists an MP's Yes/No/Paired ballots (absences are not listed).
- Each bill's text on parl.ca (`text_url` in the bill detail) has a "SUMMARY" written by Parliament. Bills at first reading can show only a table of contents under that heading, so a summary must look like prose.
- Plain-language sentences are generated from the official title plus that summary, cached per bill in SQLite (`plain_bills`), and refusals or rambling answers are rejected (the official title is shown instead).
- The card's "At a glance" overview must cite item ids; sentences with no valid source are dropped.

## Questions
None open.
