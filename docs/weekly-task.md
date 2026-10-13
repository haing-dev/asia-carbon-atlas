# Weekly Claude task (scheduled, Mondays)

Registry numbers, stages and new registry projects are refreshed by the free `refresh` GitHub workflow (Sundays,
probe-before-fetch: only sources that changed are re-read). This task does only what needs judgement, in one short pass.
Budget: ~25 web searches, no page fetches beyond verifying items. Never touch `data/records/` or `state/`.

## Steps
1. `git pull` on `main`. Read `config/offtakers.yaml` and `data/headlines.json` (to skip anything already listed).
2. **Headlines** — for each area (asia = Asia excl. mainland China; north_america = incl. Central America & Caribbean;
   south_america), search news from the last 7 days on carbon credits: issuances, offtake/purchase deals, Article 6 deals
   and authorisations, jurisdictional REDD+, registrations, national carbon-market rules on credits/offsets, partnerships
   that include credit purchases. Pick up to 10 per area, one per story, each opened to confirm date and relevance.
   Write `data/headlines.json`: `{"week_ending": today, "updated": today, "areas": {"asia": [...], "north_america": [...],
   "south_america": [...]}}`, items `{"title" (neutral, ≤90 chars), "url", "source", "date", "countries": [ISO3],
   "type": issuance|offtake|article6|policy|registration|partnership|other}`.
3. **New offtake deals** — from the same searches (plus at most 3 targeted ones), add only NEW deals whose source names
   the buyer, the project or supplier, and the date (SPEC §10.4: no inference; partnerships/investments without a credit
   purchase don't count). If one registry project is unambiguous (`grep -i` the name/developer in `data/records/*.jsonl`),
   add to `offtakes:` with its `record`; otherwise add or extend an `announced_rows:` entry (id `ANN:<supplier>-<type>-<iso>`).
   **Supplier sweep (rotating):** also search "<supplier> carbon credit offtake" for 5 suppliers already in
   `config/offtakers.yaml` (rotate alphabetically by week number), any date, to catch deals older than 7 days.
4. **Duplicate review** — if the `ArtifactData` tool is available, `list` collection `decisions` of
   https://claude.ai/artifact/HMJAiyx5ZAXieaE3j72qFi (all pages), save the rows as JSON and run
   `uv run python -m pipeline.review_page --apply <file>`. Skip silently if the tool is unavailable.
5. `uv run pytest -q` and `uv run python -m pipeline.process` must pass. If nothing changed, stop (no commit).
   Otherwise commit `weekly: headlines + N new deals` and push to `main`; the `publish` workflow deploys.
6. Reply with 3 lines: headlines updated, deals added (names), decisions applied.
