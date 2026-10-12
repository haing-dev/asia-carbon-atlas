# Source notes

## vrod — Berkeley Voluntary Registry Offsets Database (Verra, Gold Standard, Isometric)
- Page: https://gspp.berkeley.edu/berkeley-carbon-trading-project/offsets-database (CC BY 4.0, cite per page).
- Probe: version label in the main download link (`Voluntary-Registry-Offsets-Database--vYYYY-MM.xlsx`), ~every 2 months.
- Fetch: main workbook (~17 MB), sheet `PROJECTS`, header on row 4. Keep VCS/GOLD/ISO rows with an Asian country.
- Fields used: Project ID, Name, Voluntary Status, Scope/Type, Methodology, Country, State, Developer, Owner, totals issued/retired,
  issued-by-vintage block (columns after "First Year of Project (Vintage)"), Estimated Annual Emission Reductions, PoA ID,
  listed/registered dates, Registry Documents, Project Website.
- Registry links: VCS `https://registry.verra.org/app/projectDetail/VCS/<id>`, GS `https://registry.goldstandard.org/projects/details/<id>`,
  Isometric `https://to.isometric.com/<prj_id>` (from the workbook). Verra/GS links not verifiable from the chat sandbox — owner to spot-check.

## cdm — UNFCCC CDM via UNEP-CCC CDM Pipeline
- cdm.unfccc.int robots.txt disallows `/Projects/projsearch.html`, `/Projects/registered.html` and sets Crawl-delay 60 → no scraping of UNFCCC.
- Data: https://unepccc.org/cdm-ji-pipeline/ → `cdm-pipeline.xlsx` (sheet `CDM_Projects`, header row 4). Last upstream update 2025-04.
- Probe: link on the UNEP page + HEAD ETag/Last-Modified.
- Units are kilotonnes in the sheet (×1000). Retired = voluntary cancellations. `Credit buyer` kept as `credit_buyer_raw` (public PDD/LoA info).
- Links: `https://cdm.unfccc.int/Projects/Validation/DB/<uid>/view.html` (PA) and `.../ProgrammeOfActivities/Validation/DB/<uid>/view.html` (PoA) — verified to load.
- Not available: per-vintage issuance (sheet `UNFCCC_issuances` has periods; could be used in M3), project developer.

## puro — Puro.earth Registry
- `/projects` embeds all projects as JSON in the Next.js payload (projectId, name, countryCode, supplierName, methodology, crediting period, lat/long).
- Detail page `/projects/<id>` shows "Issued credits" and "Retired credits" totals and the issuance list.
- Probe: hash of the embedded project list + newest row on `/issuances`. Fetch detail pages for Asian projects only (7 as of 2026-10).
- Retirement beneficiaries: shown client-side; to add in M5 (offtakers).
