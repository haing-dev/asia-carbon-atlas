# Asia Carbon Credit Atlas — Build Spec (v3)

> For Claude, working either from the owner's claude.ai chat with this repo attached or in Claude Code (§12). Read this whole file before writing code. Where this spec says "discover", inspect the live source first and record what you find in `docs/sources.md` before building the adapter. Ask the owner before deviating from any **MUST**. At the end of every work session, update `docs/progress.md`.

## 0. Purpose and ground rules

A public, research-only (non-commercial) website mapping carbon credit projects in Asia (excluding mainland China), across registries and Paris Agreement mechanisms. Data is checked every 10 days.

- **MUST: Verifiable data only.** Every row links to a public registry record or official source page. Every volume figure traces to a source URL, version and content hash. Rows that can't meet this are excluded.
- **MUST: Public sources only for offtakers.** Only registry retirement records, government publications and public announcements count. Never infer.
- **MUST: Respectful collection.**
  - Obey robots.txt.
  - Use at most ~1 request/sec per host, with a descriptive User-Agent carrying a contact email.
  - Never log in, bypass bot protection, or scrape behind auth.
  - If a source blocks or breaks, mark it **stale**, keep its last good records, and flag it on the site. Do not work around the block.
- **MUST: Attribution.** Show a per-source citation and a "data as of" date on the site.
- **MUST: Efficiency rules in §1.**

## 1. Efficiency rules (MUST)

- **E1. Probe before fetch.** Every source has a cheap probe (one or a few requests) that returns a change signal: a release version, ETag/Last-Modified, a record count, the newest issuance date, or a hash of the listing page. If the signal matches `state/manifest.json`, skip the source entirely and reuse its committed records.
- **E2. Fetch only what changed, bulk first.**
  - Order of preference per source: official bulk file or API → the JSON endpoint behind the website → paginated listing pages → detail pages.
  - Fetch detail pages only for new records, or records whose listing row changed. Read listings sorted newest-first only until the first already-seen record.
  - Use conditional HTTP (ETag / If-Modified-Since), compression and keep-alive. Run different hosts in parallel (async), each at ≤1 req/s.
  - A headless browser is the last resort. Install it in CI only in runs where that source actually changed.
- **E3. Route runs by what changed** (§11):
  - Website-only change → build and deploy the site.
  - Rule, config or review change → reprocess from committed records, with no fetching.
  - Changed adapter → re-fetch only that source.
  - Only the schedule (or a manual run) probes all sources.
- **E4. No-op runs are cheap and silent.** If nothing changed upstream: no commit, no build, no deploy. One exception: commit a heartbeat update of `state/manifest.json` at least every 30 days, because GitHub disables schedules in public repos after 60 days without activity.
- **E5. Light, diff-friendly storage** (§4).
- **E6. Claude last, cached, batched, on its own schedule** (§10). Data refreshes use no Claude at all.

**Targets** (checked in §14):

| Situation | Target | Claude usage |
|---|---|---|
| Scheduled refresh, nothing changed upstream | < 5 min; no commit, no deploy | none |
| Scheduled refresh with typical changes | < 20 min | none |
| Website change pushed to `main` | live in < 3 min | none |
| Rule/config/review change pushed | live in < 3 min | none |
| Reprocess all records locally | < 60 s | none |
| Enrichment run | ≤ 60 min, ≤ `MAX_ITEMS` items | capped |

## 2. Geography

Include these countries (UN M49 regions; the list lives in `config/countries.yaml`):

| Region | Countries |
|---|---|
| East Asia | Japan, South Korea, Mongolia, Taiwan, Hong Kong, Macau |
| Southeast Asia | Brunei, Cambodia, Indonesia, Laos, Malaysia, Myanmar, Philippines, Singapore, Thailand, Timor-Leste, Vietnam |
| South Asia | Afghanistan, Bangladesh, Bhutan, India, Maldives, Nepal, Pakistan, Sri Lanka |
| Central Asia | Kazakhstan, Kyrgyzstan, Tajikistan, Turkmenistan, Uzbekistan |

Exclude: mainland China, North Korea, the Middle East (including Iran), Turkey, the Caucasus, Russia, and Oceania/PNG.

Normalize country names to ISO3 (`country_converter`). Hong Kong, Macau and Taiwan are separate keys: HKG, MAC, TWN.

Filter to Asian records at parse time. Non-Asian rows are never stored. Exception: a multi-country record is kept if at least one of its host countries is in the list above.

## 3. Sources (phase 1)

Each source is one adapter in `pipeline/sources/<name>.py`. It exposes `probe()`, which returns the change signal, and `fetch(changed_since)`, which returns normalized `registry_record` rows (§4).

| # | Source | Covers | Probe (change signal) | Fetch when changed |
|---|---|---|---|---|
| S1 | **Berkeley VROD** (CC BY 4.0) | **Verra (VCS)**, Gold Standard, Isometric | Read the VROD page and extract the latest version label (1 request). | Download only the main workbook, only when the version changes (≈ every 2 months). Read it with polars + calamine (fast), keeping only Asian rows and the needed columns. Skip the "raw registry files" workbook unless a needed field is missing. Do not archive the workbook, since Berkeley keeps every version online; store URL + version + sha256. |
| S2 | **CDM (UNFCCC)** | Project activities, PoAs/CPAs, CER issuance | Newest entries on the CDM issuance / recent-activity listing. | Discover bulk options first: a CDM search export, or the CAD Trust public API (CDM is in it). Then a **one-time baseline**: listing-level data for all Asian CDM projects, and detail pages only for projects that (a) have issued, (b) are transitioning to PACM, or (c) are registered with an active crediting period. After that, fetch details only for projects in new issuance or status entries. A full listing re-sync runs quarterly in its own workflow (`cdm-resync.yml`), never inside the regular refresh. |
| S3 | **Global Carbon Council** | Registered projects, ACC issuance/retirement | Count + hash of the registered-project listing; newest issuance date. | Details for new/changed projects only. Try the JSON endpoint first, a browser last. |
| S4 | **Universal Carbon Registry** | Projects (mostly India), CoU issuance/retirement | Count + hash of the project listing; newest issuance date. | Details for new/changed only. |
| S5 | **Puro.earth** | Biochar, ERW and other CDR | Newest issuance and retirement dates (JSON endpoint behind registry.puro.earth first). | Read the issuance and retirement listings newest-first until the first already-seen record. Re-read the project listing only when the project count changes. Aggregate retirements per beneficiary per project; never store individual transactions. |
| S6 | **Isometric** | ERW, biochar | If `ISOMETRIC_API_KEY` exists: the API's newest-update signal, or the record count. | API (`api.isometric.com/registry/v0`); use an "updated since" filter if one exists. Without the key, skip this adapter; Isometric comes from VROD. |
| S7 | **JCM (Japan)** | **Registered projects only**, plus issued credits | Hash of the registered-project list for each Asian partner country (~12 pages), plus the issuance list. | Details for new/changed only. Use the IGES database as a cross-check only (copyright-reserved). |
| S8 | **UNEP-CCC Article 6 Pipeline** | Article 6 tags (6.2 authorization, buyer country, CDM→PACM transition); PACM-registered activities as rows | ETag/Last-Modified or hash of the Excel download. | Parse only when it changes (≈ monthly). |

Gold Standard is included via VROD (confirmed by the owner).

**Verra plan:**

1. **Now:** use VROD. Label rows "Verra data via Berkeley VROD vX". Do not scrape Verra's new registry (a JS app with no public bulk export).
2. **Later:** add `sources/verra_api.py` when Verra's announced data API ships.
3. **Optional:** evaluate the CAD Trust Data Model 2.0 public API (GitHub `Chia-Network/cadt`, `docs/cadt_rpc_api_v2.md`) as a bulk feed for Verra/GS/GCC/CDM. Adopt it only if its records carry registry IDs we can link back to, and if it is cheaper than the adapters it replaces.

## 4. Data model and storage

### 4.1 Storage (MUST)

- **No database server, no Parquet, no binary files in git.** The whole dataset (~10–20k records) fits in memory; process it with polars.
- **Git `main` holds only small text files**, written deterministically (records sorted by `record_id`, fixed field order, volumes as integers), so unchanged data produces no diff and git compresses changes well:
  - `data/records/<source>.jsonl`: normalized Asian records, one per line. Expect under ~15 MB in total.
  - `data/enrichment.jsonl`: websites and offtakers, with evidence URLs and `next_check` dates.
  - `state/manifest.json`: per-source probe signals, `last_checked`, `last_changed`, row counts, stale flag, and the hash of the last deployed site.
  - `review/*.csv` and `config/*`.
- **No volatile per-record fields.** Never store `fetched_at` on records; store `first_seen` and `last_changed` only. The per-source `last_checked` lives once, in the manifest. Otherwise every record would change on every run.
- **Generated website data is never committed.** It is built in CI at deploy time.
- **Raw snapshots** (provenance and re-parsing):
  - Store them as assets on one GitHub Release named `snapshots` in this (private) repo. Each run that fetched new content uploads one bundle, `snapshots-<YYYY-MM-DD>.tar.zst`, holding only content hashes not archived before. `state/snapshots_index.jsonl` maps each hash to its bundle.
  - Upload with the workflow's built-in `GITHUB_TOKEN` (`gh release upload`); no extra account or secrets.
  - Keep the bundles behind current records plus one previous version; delete unreferenced bundles monthly. Limits: ≤ 1,000 assets per release, each < 2 GiB.
  - Sources that archive their own versions (VROD) are not copied; store URL + version + hash.
  - If an upload fails, log it and continue; archiving never blocks the pipeline.
- **Do not use the GitHub Actions cache to hold state.** Cache entries unused for 7 days are evicted, and runs are 10 days apart.

### 4.2 `registry_record` (one per project per registry; stored)

| Field | Type | Notes |
|---|---|---|
| `record_id` | str | `{registry}:{native_id}`, e.g. `VCS:1234`, `CDM:5678`, `JCM:ID002` |
| `registry` | enum | VCS, GS, CDM, PACM, GCC, UCR, PURO, ISO, JCM |
| `native_id`, `registry_url` | str | `registry_url` is the deep link to the public record (**required**) |
| `name`, `developer_raw`, `participants_raw` | str | |
| `countries` | list[ISO3] | All host countries |
| `methodology_codes` | list[str] | Raw codes |
| `registry_type_raw`, `registry_status_raw` | str | Verbatim |
| `est_annual_tco2e` | int? | The registry's estimated annual reductions/removals |
| `issued_tco2e`, `retired_tco2e` | int | Cumulative |
| `issuance_by_vintage` | map[year → int] | |
| `crediting_start`, `crediting_end` | date? | |
| `cross_refs` | list[str] | IDs at other registries (§7) |
| `beneficiaries` | list | `{name, qty, last_date}`, aggregated per beneficiary, where public |
| `source_version`, `raw_hash`, `first_seen`, `last_changed` | | Provenance |

### 4.3 `project` (deduplicated cluster; derived in memory each run, never stored)

- `project_id` (stable: derived from the smallest `record_id` in the cluster), `display_name`
- `project_url`, `developer`, `developer_url`
- `countries`, `country_shares` (§8)
- `category_l1`, `category_l2`, `nature_or_tech`, `removal_type`
- `registries`: `record_id` + `registry_url` for each member
- `stage`: `pipeline` | `registered` | `issuing` | `inactive`
- `est_annual_tco2e`, `issued_tco2e`, `retired_tco2e`
- `article6`: `{authorized, buyer_countries, mechanism: "6.2"|"6.4", ca_applied?, source_url}`
- `offtakers`: list of `{name, type, volume?, date, source_url, source_title}`, where `type` ∈ {`announced_offtake`, `retirement_beneficiary`, `sovereign_buyer`}
- `flags`: e.g. `vintage_overlap`, `multi_country`, `stale_source`, `needs_review`

## 5. Stage mapping

Map each registry's raw status to four stages. The mapping lives in `config/stages.yaml`; an unmapped status fails validation loudly.

| Stage | Rule |
|---|---|
| `pipeline` | Listed / under development / under validation / registration requested. **JCM: never** (registered only). PACM: transition approved but not yet registered counts here; a prior-consideration notice alone is excluded. |
| `registered` | Registered, with no issuance to date |
| `issuing` | At least one issuance (issued > 0) |
| `inactive` | Withdrawn, rejected, deregistered, or crediting period ended with no renewal. Hidden by default; filterable. |

A project's stage is the most advanced stage across its member records.

## 6. Credit-type taxonomy

Two levels, written "L1 – L2" in the UI, defined in `config/taxonomy.yaml`. Classify in this order:

1. **Methodology dictionary** in `config/methodology_map.csv`. Seed it from:
   - VROD Scope/Type (CC BY);
   - CarbonPlan `offsets-db-data` protocol mapping (MIT; attribute it);
   - CDM methodologies (ACM/AM/AMS/AR-ACM/AR-AMS);
   - JCM methodology IDs;
   - Puro, Isometric and GCC methodologies.
2. **Keyword rules** on the name for codes that span types (e.g. ACM0002 → solar / wind / hydro / geothermal).
3. **Claude**, only for leftovers. Classify **per methodology code or unmatched name pattern, never per project**, in batches of up to 50 per call. Results go to `review/taxonomy_pending.csv`; once approved they are added to the dictionary, so each code is classified once ever.

| L1 | L2 |
|---|---|
| Forestry & land use | REDD+ (avoided deforestation) · ARR (afforestation/reforestation) · Improved forest management · Blue carbon (mangrove/seagrass) · Peatland & wetland · Other land use |
| Agriculture | Rice methane (AWD/DSR) · Soil carbon & regenerative ag · Agroforestry · Livestock & manure · Fertilizer / N₂O |
| Engineered & hybrid removal | Biochar · Enhanced rock weathering · DAC/DACCS · BECCS · Mineralization / carbonated materials · Biomass storage / wood products |
| Renewable energy | Solar · Wind · Hydro · Biomass power · Geothermal · Other RE |
| Energy efficiency | Industrial EE · Waste heat recovery · Buildings & lighting · Grid / T&D |
| Household & community | Cookstoves · Water purification · Household biogas · Solar home / off-grid lighting |
| Waste & methane | Landfill gas · Wastewater · Biogas / anaerobic digestion · Composting · Coal mine methane · Oil & gas methane |
| Industrial & fuel switch | Industrial gases (HFC-23, N₂O, SF₆) · Cement / clinker · Fuel switching |
| Transport | E-mobility · Mass transit · Fleet efficiency |
| Other | Other |

Extra tags: `nature_or_tech` (nature-based / technology), `removal_type` (removal / reduction / mixed).

## 7. Deduplication across registries

One row per real-world project, even when it appears in CDM, VCS, GS, GCC, UCR and PACM.

1. **Explicit cross-references** (deterministic, free):
   - Regex-extract IDs: `CDM (Ref|ref\.?|project)? ?\d{3,5}`, `VCS ?\d{2,5}`, `GS ?\d{2,5}`, `GCC ?\d+`, `UCR ?\d+`, PoA/CPA refs.
   - Link PACM transitions to their CDM reference via the A6 Pipeline.
   - Union-find on shared IDs.
2. **Fuzzy matching** for the rest:
   - Block on country + `category_l2`.
   - Score pairs with `rapidfuzz` on: normalized name, capacity (MW), developer overlap, state/province, methodology compatibility, crediting-period adjacency, and coordinates within ~5 km.
   - Score ≥ 0.90: auto-merge.
   - 0.70–0.90: deterministic tie-breaks first (same capacity + same developer → merge). Claude only for the remainder, in batches of up to 20 pairs per call (Haiku). Results go to `review/dedupe_pending.csv`.
   - Below 0.70: keep separate.
   - Never merge records whose country sets don't intersect.
   - Decisions persist in `review/dedupe_decisions.csv`, keyed by the record pair plus a fingerprint of their key fields. A pair is adjudicated once and revisited only if those fields change.
3. **Volume roll-up:**
   - `issued` = sum across registries, but a vintage year issued in two registries counts once (the max), and the project gets the `vintage_overlap` flag. Raw per-registry numbers are shown in the row detail.
   - `retired` follows the same rule.
   - `est_annual` = the most recent registry's estimate, not a sum.

## 8. Multi-country projects

Show a multi-country project as **one row** listing all its countries.

For map tallies only, split its volumes pro rata by population:

- Population: UN World Population Prospects 2024, fixed reference year 2025 (it includes TWN, HKG, MAC).
- Only Asian shares count on the map.
- State the method on the Methods page and in the row tooltip.

## 9. Website

### 9.1 UI/UX

Learn from CarbonPlan's OffsetsDB, but do **not** copy its code, fonts, colors, logos or text. Principles to borrow:

- Data-first minimalism.
- Tabular numerals with units (tCO₂e, tCO₂e/yr).
- Compact pill filters with one-click clear.
- Expandable rows instead of modals.
- Filter state in the URL.
- "Download CSV of current view".
- Updates and Methods pages.

Make it our own: one colorblind-safe hue per L1, our own font pairing, light theme by default with a dark toggle, and a map-first layout.

**Layout:**

1. **Header**: title, "data as of" date per source, links to Methods and Sources.
2. **Map**:
   - Asia-centred d3-geo projection, one circle per country.
   - Metric dropdown: **Issued (cumulative tCO₂e)** | **Estimated annual (tCO₂e/yr)**.
   - The type, stage and registry filters also apply to the circles.
   - Hover shows a tooltip; click selects the country and scrolls to the table.
3. **Filters**:
   - Credit type: tick-box multi-select by L1, expandable to L2.
   - Stage: Pipeline / Registered / Issuing, plus an Inactive toggle.
   - Registry: multi-select.
   - Article 6 only: toggle.
   - Search box.
4. **Table** (sortable; the selected country, or all):
   1. Project name: links to `project_url` when it exists, with a small icon per `registry_url`.
   2. Developer: links to `developer_url` when it exists.
   3. Country, with a multi-country badge.
   4. Credit type (L1 – L2).
   5. Registry badges linking to each record, plus a 6.2/6.4 badge.
   6. Stage.
   7. Estimated annual.
   8. Issued.
   9. Retired.
   10. Announced offtaker(s): each linked to its source, with a type icon.
5. **Expanded row**: per-registry breakdown, issuance-by-vintage chart, methodology codes, crediting period, flags and sources.

**Circle scaling:**

- Area ∝ value: `r = R_MAX · sqrt(v / v_max)`.
  - `R_MAX` ≈ 6% of map width, clamped 28–56 px.
  - Minimum radius 3 px for nonzero values.
  - Never use a log scale.
- Draw large circles first, with semi-transparent fill and stroke.
- Use leader lines for HKG/MAC/SGP/BRN.
- Legend: three reference circles.
- Rescale whenever the metric or filters change.

### 9.2 Data delivery (MUST, for speed and lightness)

- **Stack:** Svelte + Vite (small bundle), d3-geo, virtualized table rows for the "All" view. No backend. Must work at 375 px width.
- **Files built at deploy time:**
  - `meta.json` (tiny, not cached): data-as-of per source, source health, and the hashed filenames below.
  - `index.<hash>.json`: every project's filter and aggregation fields in compact columnar form (integer codes plus dictionaries): id, country shares, L2 category, stage, registry bitmask, Article 6 flag, est annual, issued, retired. **Target < 150 KB compressed.** The map circles and filters run entirely on this file in the browser, so filtering is instant.
  - `rows/<ISO3>.<hash>.json`: display fields (names, developers, URLs, offtakers, vintages) for one country, loaded when that country is selected. The "All" view loads shards progressively.
- **Caching:** hashed files get long-lived immutable cache headers. Unchanged shards keep their hash, so visitors and the CDN download only what changed.
- **Basemap:** an Asia-only TopoJSON, simplified and quantized with mapshaper (< 100 KB), plus a precomputed centroids file that includes HKG/MAC/SGP points.
- **CSV export** is generated in the browser from loaded data; there is no separate CSV file.
- **Fonts:** one self-hosted, subsetted woff2 family plus a mono for numbers, or system fonts.
- **Deploy:** GitHub Actions builds and runs `wrangler pages deploy` (direct upload, which sends only files with new hashes). Skip the deploy when the built output hash equals the last deployed hash. On the first deploy, create the Pages project `asia-carbon-atlas` if it doesn't exist (`wrangler pages project create asia-carbon-atlas --production-branch main`). Secrets: `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`.

## 10. Enrichment (Claude, on the owner's Max subscription)

**MUST: No paid API calls.** Do not call the Messages API from code, and do not use `ANTHROPIC_API_KEY`.

### 10.1 Schedule and gate

- **Primary: a monthly scheduled Claude task** on the owner's claude.ai account, created from the owner's chat. It runs on the Max plan, with no install and no token. It fires on the 3rd of each month (after the refresh on the 1st); the initial backfill is a few manually started runs of the same task.
- Each run starts a fresh cloud session with this repo attached. **Its first action is the gate**, `make enrich-gate`: if the queue holds fewer than 25 items and the oldest is under 30 days old, the session ends immediately.
- **Fallback**, only if a scheduled task can't push to the repo: `enrich.yml` in GitHub Actions running the Claude Code CLI with `CLAUDE_CODE_OAUTH_TOKEN`. The owner creates the token once with `claude setup-token`; it is valid for one year. Never pass `--bare`, which ignores the token.

### 10.2 How Claude is run

- `make enrich-queue` writes `work/enrich_queue.jsonl`: new or changed items only, largest volume first, capped at `MAX_ITEMS` (default 150 per run).
- The session works through the queue in chunks of ~10 items, **each chunk in a fresh subagent** (small context), using WebSearch/WebFetch only. Taxonomy and dedupe chunks use a small, fast model; web research uses a mid-size model.
- Inputs are compact JSON per item (name, developer, country, registry IDs and URLs), never whole pages. Each chunk returns a strict JSON array, appended to `work/enrich_results.jsonl`.
- `make enrich-merge` validates results against §10.4. Invalid items are re-queued once, then sent to `review/`.
- The session commits accepted results (`data/enrichment.jsonl`) to `main` and pending items to the rolling review branch, rebasing on the latest `main` before pushing. `publish.yml` then deploys.
- On a usage-limit error: stop, keep finished chunks, leave the rest queued. Enrichment never blocks the data refresh or the live site.

### 10.3 What to look up, and when to re-check (`config/enrich.yaml`)

| Item | Unit | Scope | Re-check rule |
|---|---|---|---|
| Developer website | Per developer **entity**; projects inherit it | All developers | Found: never re-searched. Its link is checked monthly by a plain HTTP request (no Claude) and re-searched only after 2 consecutive dead checks. Not found: retry after 180 days, then 365. |
| Project website | Per project | Top 500 by volume, plus all Article 6 projects | Same as above |
| Announced offtakers (news/press) | **Per developer first** (one search covers all its projects), then per project | Per-project search only for the top 300 by issued volume, plus all Article 6 projects | Re-search only on events: first issuance, issued +25% since last search, new Article 6 authorization, or new registry listing. Otherwise every 180 days for top projects. Nothing found: back off 180 → 365 days. |
| Retirement beneficiaries, sovereign buyers | From registry / A6 data | All | Every refresh, no Claude |
| Taxonomy fallback | Per new code or pattern, batches ≤ 50 | Leftovers only | Once |
| Dedupe adjudication | Per candidate pair, batches ≤ 20 | 0.70–0.90 band only | Once, unless key fields change |

### 10.4 Acceptance rules

| Task | Rule |
|---|---|
| Developer / project website | The domain must clearly belong to the entity (name on the page, matching country or address). Store the evidence URL. Otherwise leave it blank. A registry page is never the "project website". |
| Offtakers | The named buyer, the project (or an unambiguous project reference) and the date must all appear in the source. No inference. JCM participants and traders are not offtakers unless a source says so. All `announced_offtake` items go to review and are published only once approved. |

Review flow: **one rolling pull request** (branch `review/pending`), updated by each run rather than opening a new PR each time. The owner sets `approved=yes` on accepted rows and merges.

Entity aliases live in `config/entities.yaml`. Manual overrides in `config/overrides.yaml` always win.

## 11. Workflows and schedule

| Workflow | Trigger | Does | Never does |
|---|---|---|---|
| `refresh.yml` | Cron `0 2 1,11,21 * *`; manual (inputs: `sources`, `force`); push to `pipeline/sources/<name>.py` (that source only) | Probe → fetch changed sources only → process → validate → commit records + manifest → build + deploy, only if something changed. The run on the 1st also link-checks websites (HTTP only). | Use Claude; re-fetch unchanged sources |
| `publish.yml` | Push to `web/**`, `config/**`, `review/**`, or `pipeline/**` excluding `pipeline/sources/**` | Process from committed records → validate → build → deploy (skipped if the output is unchanged) | Fetch; use Claude |
| Scheduled Claude task (not a workflow) | Monthly on the 3rd; manual runs for the backfill | Gate → queue → Claude chunks → validate → commit enrichment + update the rolling review PR (§10) | Fetch registries |
| `enrich.yml` (fallback only) | Manual | The same, via the Claude Code CLI in Actions | Run while the scheduled task works |
| `cdm-resync.yml` | Cron `0 4 5 1,4,7,10 *` (quarterly); manual | Full CDM listing re-sync | Run inside the normal refresh |

- **Concurrency:** refresh, enrich and cdm-resync share one queue group (no overlap, no cancel). `publish` cancels older in-progress publish runs.
- **Setup speed:** `uv` with a lockfile and `npm ci`. No browser install unless E2 requires it for a changed source.
- **Validation gates:** if any of the following holds, there is no commit and no deploy, the source is marked stale, and the live site stays on the last good version:
  - schema errors;
  - `retired > issued`;
  - negative volumes;
  - a source's row count drops > 20% vs the last run;
  - a total moves > 30% without new records;
  - an unmapped status or methodology.
- **Changelog:** `updates.json` is generated from each run's record diff.

## 12. Working from chat (the owner's default)

- Repo: `haing-dev/asia-carbon-atlas` (private). The owner works with Claude in a claude.ai chat with this repo attached; Claude Code is optional, and both follow this spec.
- If a chat gets long, the owner starts a new chat in the same claude.ai project and says "continue the carbon atlas". Claude reads `docs/progress.md` first.
- For each change request, Claude:
  1. edits in its workspace;
  2. runs the tests and `make process site` locally against the committed records (no network needed);
  3. commits and pushes to `main`;
  4. watches `publish.yml` with `gh run watch` and reports the result.
- **The chat workspace cannot reach registry websites** (its network allowlist blocks them). Scraper work is therefore tested through a one-source refresh: `gh workflow run refresh.yml -f sources=<name>`. Claude reads the logs and uploaded debug artifacts via `gh` and iterates. WebFetch may be used to inspect page structure.
- **Keep sessions cheap:**
  - Root `CLAUDE.md` stays under 30 lines: a pointer to `docs/SPEC.md` and `docs/progress.md`, plus the MUST list. It is loaded into every session.
  - Read only the files a task needs.
  - Never paste data files into chat.
- After every session, update `docs/progress.md` (done / next / open issues) so a new chat can continue without re-reading everything.

## 13. Repo layout

```
CLAUDE.md                  short pointer (≤ 30 lines)
Makefile                   probe fetch process site enrich test
docs/        SPEC.md progress.md sources.md methods.md
config/      countries.yaml sources.yaml stages.yaml taxonomy.yaml methodology_map.csv entities.yaml overrides.yaml enrich.yaml
pipeline/    http.py probe.py sources/*.py process.py (normalize, classify, dedupe, allocate) validate.py build.py enrich.py
data/        records/<source>.jsonl  enrichment.jsonl
state/       manifest.json
review/      *_pending.csv  *_decisions.csv
web/         Svelte site
work/        (gitignored) queues and temp outputs
.github/workflows/  refresh.yml publish.yml enrich.yml cdm-resync.yml
```

## 14. Milestones and acceptance

| # | Deliverable | Done when |
|---|---|---|
| M0 | Scaffold, config, schemas, Makefile; all four workflows wired with stub adapters | A no-op refresh finishes < 5 min with no commit and no deploy. A `web/` push deploys without running the pipeline. |
| M1 | Adapters with probes: VROD (Verra/GS/Isometric), CDM baseline, Puro | 20 rows spot-checked against source pages. A second run with no upstream change fetches nothing beyond probes. |
| M2 | Adapters: GCC, UCR, JCM (registered only), A6 Pipeline/PACM | Same checks; JCM counts match the official registered list |
| M3 | Taxonomy, stages, dedupe, pro-rata | 100% classified or in review. Dedupe precision checked on a 50-pair sample. Tallies reconcile. Full reprocess < 60 s. |
| M4 | Website | Mobile Lighthouse accessibility ≥ 90 and performance ≥ 90. Works at 375 px. Index file < 150 KB compressed. Scaling per §9. |
| M5 | Enrichment + rolling review PR | Every published website/offtaker has an evidence URL. The queue gate skips small queues. A usage-limit stop keeps partial results. |
| M6 | Scheduled operation | Two consecutive scheduled runs succeed. A forced source failure keeps the live site and flags the source stale. A config change goes live in < 3 min. |

## 15. Attribution (Sources page)

- Berkeley Carbon Trading Project, *Voluntary Registry Offsets Database* vYYYY-MM, UC Berkeley, CC BY 4.0, using their exact citation.
- UNFCCC CDM and Article 6.4 mechanism public records.
- UNEP Copenhagen Climate Centre, *Article 6 Pipeline*.
- Global Carbon Council, Universal Carbon Registry, Puro.earth, Isometric and the JCM public registries (links per row).
- CarbonPlan `offsets-db-data` (MIT), for the protocol mapping seed.
- UN DESA, World Population Prospects 2024.
- Disclaimer: research use only; not investment advice; offtakers are limited to public records and announcements and are not exhaustive.

## 16. Decisions and open items

- **Target cost: $0.**
  - Private GitHub repo (Actions use stays within the free 2,000 min/month).
  - Cloudflare Pages free plan.
  - Archive in GitHub Releases.
  - Claude on the owner's Max plan.
- Freshness: data checked every 10 days, Claude lookups monthly. Staying cheap matters more than being up to date.
- Countries: Afghanistan in; North Korea and Iran out (owner confirmed).
- Secrets, added by the owner in GitHub and never pasted in chat:
  - `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` now;
  - `ISOMETRIC_API_KEY` if Isometric grants access.
- Tune `MAX_ITEMS` and the top-N thresholds after the first enrichment runs.
