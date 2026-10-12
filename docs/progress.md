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

## Next
- GCC: owner will upload a GCC export manually (site blocks bots) → add a file-based GCC adapter reading it from the repo.
- M3: fuzzy dedupe (VCS↔CDM rarely cross-reference), CDM issuance by vintage for overlap rule, population shares (UN WPP).
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
