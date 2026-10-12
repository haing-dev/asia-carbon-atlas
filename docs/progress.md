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

- **M2 (more sources): in progress** (2026-10-12). Adapters for JCM (registered only), UCR, and the UNEP-CCC Article 6 Pipeline
  (PACM rows merged with CDM; 6.2 status/buyer tags on matching JCM/Verra projects; unmatched authorised 6.2 activities as rows).
  GCC blocked (403) → disabled. Site: shaded map + ranked bars with flags, "Listed"/"Validated", Year column, grouped registry filter.

## Next
- Check first JCM/UCR/A6 refresh results (counts, unmapped statuses, type classification of JCM/UCR projects).
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
- VROD "Project Listed" dates were empty; date parser now accepts years/Excel serials — re-check after the next VROD fetch.
