# Progress log

## Status
- **M0 (scaffold): done** (2026-10-12). Live at https://asia-carbon-atlas.pages.dev (empty until sources connect).
  - Pipeline skeleton: polite HTTP client, probe/fetch refresh, process, validate, build; stub adapters for 8 sources.
  - Site: Asia map (area-scaled circles, metric dropdown), filters, sortable/expandable table, CSV export, Methods/Sources.
  - Workflows: `refresh` (no-op run ≈ 6 s, no commit), `publish` (≈ 30 s), `deploy` (skips upload when build unchanged).

## Next
- M1: adapters with probes for Berkeley VROD (Verra/GS/Isometric), CDM baseline, Puro.

## Decisions
- Private repo `haing-dev/asia-carbon-atlas`; Cloudflare Pages project `asia-carbon-atlas`; target cost $0.
- 30 countries (`config/countries.yaml`); North Korea and Iran excluded.
- Data checks every 10 days; Claude lookups monthly via a scheduled Claude task (set up at M5).

## Notes for Claude working from chat
- The chat workspace cannot reach registry sites or GitHub Actions logs; job step results and `::notice::` annotations are readable with `gh run view`.
- Test scrapers by pushing the adapter (triggers `refresh` for that source only) or `gh workflow run refresh.yml -f sources=<id> -f force=true`.

## Open issues
- (none)
