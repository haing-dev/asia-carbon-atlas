# Progress log

## Status
- **M0 (scaffold): done** (2026-10-12). Live at https://asia-carbon-atlas.pages.dev (empty until sources connect).
  - Pipeline skeleton: polite HTTP client, probe/fetch refresh, process, validate, build; stub adapters for 8 sources.
  - Site: Asia map (area-scaled circles, metric dropdown), filters, sortable/expandable table, CSV export, Methods/Sources.
  - Workflows: `refresh` (no-op run ≈ 6 s, no commit), `publish` (≈ 30 s), `deploy` (skips upload when build unchanged).

- **M1 (first sources): done** (2026-10-12). VROD 3,125 Asian records (VCS 1,734 / GS 1,371 / ISO 20), CDM 3,024 (via UNEP-CCC pipeline;
  UNFCCC robots.txt forbids scraping), Puro 7. 5,848 projects after cross-reference dedupe (78 merged clusters).
  - Credit types: `config/type_rules.yaml` (exact registry types first, then keywords); 2 projects left as "Other".
  - Stages: `config/stages.yaml` for CDM/VCS/GS/ISO/PURO.
  - Site: dropdown filters (credit type with sub-types, project stage, registry), numbered footnotes at the end.

- **M2 (more sources): done** (2026-10-12). UCR 301 records (300 India, 1 Nepal), JCM 83 registered, A6 Pipeline 153
  (19 PACM, 133 6.2 tags, 1 standalone 6.2 row: Bangkok E-Bus). 6,233 projects; 107 carry an Article 6 tag. Adapters for JCM (registered only), UCR, and the UNEP-CCC Article 6 Pipeline
  (PACM rows merged with CDM; 6.2 status/buyer tags on matching JCM/Verra projects; unmatched authorised 6.2 activities as rows).
  GCC blocked (403) → disabled. Site: shaded map + ranked bars with flags, "Listed"/"Validated", separate Listed/Validated/1st issued year columns, grouped registry filter.

- **M3 (dedupe, population): done** (2026-10-12). Fuzzy cross-registry matching (`pipeline/dedupe.py`: rapidfuzz on
  normalised names, blocked by country + L1; hard guards on capacity, place, phase number, technology; mutual-best rule;
  ≥0.90 merge, 0.70–0.90 → `review/dedupe_pending.csv`; owner decisions in `review/dedupe_decisions.csv`). 395 projects merged by
  name. CDM issuance by vintage (UNFCCC_issuances, spread over monitoring periods); a vintage issued in two registries counts once
  (219 projects flagged `vintage_overlap`). Population split from UN WPP 2024 (`config/population.csv`, `tools` workflow);
  lead record's hosts, or the single country named in the title.
- **GCC: done** via the owner's approved-projects export (`data/manual/gcc/*.xlsx`; site is behind a Cloudflare challenge).
  138 Asian projects. No issuance, developer or per-project links in the export. GCC issuances live on S&P's registry
  (registry.spglobal.com/gccregistry, undocumented JSON API) — not used.
- **Offtakers (M5 part 1): done.** CDM credit buyers (UNEP-CCC column, ~1,360 projects) + 14 verified public deals on registry
  projects and 11 "Announced deal" rows (supplier-level deals, World Bank FCPF ERPAs) in `config/offtakers.yaml`.

- **Session 2026-10-12 (UI + weekly):** offtaker search + column after Developer; bullet-point notes; source-date column;
  "Weekly headlines" (data/headlines.json → meta.json); map hover lift; dedupe review page = private artifact
  https://claude.ai/artifact/HMJAiyx5ZAXieaE3j72qFi (db collection `decisions`; apply with `python -m pipeline.review_page --apply`).
  Refresh is now weekly (Sun); weekly Claude scheduled task (Mon) per `docs/weekly-task.md`.

- Light theme (style guide, 2026-10-29); was night mode only. Footnotes live in `content/notes.md` (owner edits on GitHub; "Edit notes" link shows after visiting the site once with `?owner=1`).

- **Americas (2026-10-12):** areas in `config/countries.yaml` (`area:`), per-area basemaps (`web/scripts/make-basemap.mjs`),
  per-area index files, region switcher. ACR/CAR/ART TREES via VROD (ACR/ART link to GreenTrace project lists; CAR to APX).
  Headlines and offtakers per area. ~10.7k projects (Asia 5.96k, North America 3.14k, South America 1.63k).
  Gaps: Cercarbono / BioCarbon Registry (Colombia, EcoRegistry platform), Brazil/Colombia national registries.

- **Review 2026-10-12 (efficiency + accuracy):**
  - Fixed: VROD vintage parsing read all three year blocks (issued-by-vintage, retired-by-year, remaining-by-vintage) into one
    dict, so "issued by vintage" and the cross-registry overlap rule used mixed numbers. Now vintage sums equal issued totals.
  - Fixed: projects with issuance but an inactive registry status were "Inactive" and dropped from default totals (~30M t);
    now Issuing (matches the notes).
  - Fixed: programmes (GS PoA + VPAs) took one VPA's estimate and could under-count issuance; activities now add up
    within a registry, the overlap rule applies only across registries.
  - Unknown volumes (GCC issued, JCM retired, UCR/Puro estimates) now show "—" instead of 0.
  - Est. annual map totals skip projects whose crediting period ended.
  - Efficiency: dedupe 30 s → 1.6 s (candidate pairs via shared tokens; identical results); browser rows 4.2 MB → 1.8 MB
    raw (Asia); refresh gate keeps previous data if a source's row count drops >20%; publish skips non-site files.
  - External spot-checks: Onsan/Paulínia CDM, Guyana ART match public figures; Katingan (50.9M) and CAR totals lag the
    latest registry issuances (VROD v2026-08 snapshot timing).
  - Offtaker backfill (2026-10-13): GSK–Varaha plus ~30 older verified deals (41 mapped offtakes, 36 announced rows).
    Weekly task now also sweeps 5 listed suppliers per week for deals older than 7 days.
  - Weekly 2026-10-19: headlines for 5 areas (week to Oct 19); +3 Charm Industrial deals (Boeing, TD Bank, Klimate.co).
    Sweep (wk 43: BTG TIG, C-Quest, Charm, Climeworks, CO280): C-Quest–bp Angola 15M skipped (source page has no date);
    Climeworks–Swiss Re skipped (no primary source opened). Review artifact had 0 decisions.
  - Weekly 2026-10-26: headlines for 5 areas (week to Oct 26; Asia thin, 6 items); +6 deals: Google & McKinsey–Working
    Trees Brazil (VCS:5184, 320k), Terraton EcoFix Kenya (Climeworks Solutions 2k, Climate Impact Partners), Terraton
    supplier row (Terraset 14k, CUR8 240), Meta–EFM Olympic Rainforest 676k (2025, sweep). Sweep (wk 44: Cumberland,
    Deep Sky, DelAgua, Duke, EFM): Deep Sky–TD June 2026 article = existing deal. Oman 44.01 out of scope. 0 decisions.
  - Tags (`config/tags.yaml`): ~100 searchable tags from record evidence (name/methodology/registry type) + broad
    per-type tags; exact tag/alias search filters to that tag (AWD ≠ DSR). "Tag" column (last) + footnote; CSV includes tags.
    Tags also read GS registry descriptions (gsreg lookup) and CDM/name capacity (small hydro ≤25 MW); every specific
    tag is gated by credit type; manual additions with source in `config/tag_overrides.yaml`.
  - Tag review (2026-10-13): strict `re` (any credit type) vs `ctx` (inside credit types) + `near`; classifier
    keywords made whole-word (LED/REDD/rail/metro/hydro bugs); `python -m pipeline.tag_audit` lists misses/loose hits.
    Verra links moved to the new registry URL; Verra descriptions backfilled daily by `verradesc` (refresh now daily).
    Independent review (300 random projects, 2 rounds): tag precision 91% -> ~98%, recall 97% -> ~99%.
    Verra's endpoint rate-limits GitHub runners hard (often 429 on the first request): `verradesc` tries once a day and
    stops; rice projects' Verra descriptions were fetched page by page via `discover` (browse) and stored in the lookup.
  - Gold Standard links fixed: registry pages use an internal id, not the GS number (new `gsreg` lookup source).

  - 2026-10-16: Africa and Europe areas (countries.yaml, basemaps); "All Regions" tab (default): world map of regional
    totals (click -> region tab) + top-10 offtakers by stated volume, bars split by credit type (summary.<hash>.json).

  - 2026-10-19: **Buyers & market views.** All Regions: one "Top buyers" table with Retired / Issued / Announced
    lenses (top 15, bars by credit type, click -> projects with announced / project issued / retired-by-buyer; name ->
    buyer profile page `?b=<name>`), plus "Retired share and time to first issuance, by credit type". Retirements by
    beneficiary from CarbonPlan OffsetsDB (new `offsetsdb` source, `data/lookups/retirements.jsonl`, snapshot
    2026-06-01; OffsetsDB updates are paused). Buyer entities/aliases + retirement name patterns: `config/buyers.yaml`.
    Region tables: % issued (vs registry estimate to date; pink < 50%) and % retired columns; "Retired by" in details.
    Eligibility dropdown filter (`config/eligibility.yaml`; Article 6.2, 6.4/PACM, registry hold so far) replaces the
    Article 6 checkbox (`?el=`; old `?a6=1` still works). Coverage bar above each region map (`config/coverage.yaml`
    + Cercarbono from OffsetsDB; % hidden until large uncovered programmes have published totals).
    Background hygiene checks `pipeline/checks.py` (in validate + tests; review/hygiene.csv, not on the site).
    Buyer deal sweep (10 parallel web sweeps): +~230 verified deals so far; incomplete because the web-search quota
    (200 per turn) ran out — backlog in `docs/buyer-sweep.md`.

  - 2026-10-20: All Regions headings as questions; region switch on the buyer and credit-type tables (per-region
    buyer totals use each project's regional share); credit-type table: L1 tag pills, renamed sortable columns,
    credit-type filter, small samples (<5) marked ** instead of hidden; subtitles removed. Verified-source ledger
    `data/verified/ledger.jsonl` (`pipeline/ledger.py`; sync/check/import) so sweeps skip news already checked;
    sweep brief `docs/deal-sweep-brief.md`, merge tool `scripts/deal_merge.py`.

  - 2026-10-27: coverage bar removed from the region tabs (owner); `config/coverage.yaml` and build code removed
    (in git history if needed again).

  - 2026-10-29: redesign to the owner's consulting visual style guide (white canvas, Georgia Bold titles and key
    numbers, Arial text, Deep Blue / Cyan / Electric Blue palette in fixed order, linear blue map scale, black keylines
    instead of boxed cards, square outlined controls, no shadows/rounded pills/caps). Design only; no data or logic change.

## Next
- Finish the buyer deal sweep (`docs/buyer-sweep.md`), add ICVCM CCP and
  CORSIA labels to `config/eligibility.yaml` once their public lists are sourced.
- Owner: send a fresh GCC export when wanted (replace the file in `data/manual/gcc/`); spot-check `review/dedupe_pending.csv` pairs.
- M5 rest: monthly scheduled Claude task for offtaker/website enrichment (queue + review flow per SPEC §10); Puro retirement beneficiaries.
- Owner to spot-check that Verra and Gold Standard registry links open the right project.

## Decisions
- Private repo `haing-dev/asia-carbon-atlas`; Cloudflare Pages project `asia-carbon-atlas`; target cost $0.
- 30 countries (`config/countries.yaml`); North Korea and Iran excluded.
- Data checks every 10 days; Claude lookups monthly via a scheduled Claude task (set up at M5).

## Notes for Claude working from chat
- The chat workspace cannot reach registry sites or GitHub Actions logs; job step results and `::notice::` annotations are readable with `gh run view`.
- Test scrapers by pushing the adapter (triggers `refresh` for that source only) or `gh workflow run refresh.yml -f sources=<id> -f force=true`.

## Open issues
- Gold Standard registry pages sometimes fail to load ("Some error occurred while loading") — the GS site itself; links are correct.
- VROD's "Project Listed" column is blank in the 2026-08 release (checked), so Listed-stage Verra/GS projects show no Year.
- UCR: issued = serial ranges shown on each project page; UCR pages have no issuance dates or ex-ante estimates.
