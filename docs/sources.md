# Source notes

## vrod — Berkeley Voluntary Registry Offsets Database (Verra, Gold Standard, Isometric)
- Page: https://gspp.berkeley.edu/berkeley-carbon-trading-project/offsets-database (CC BY 4.0, cite per page).
- Probe: version label in the main download link (`Voluntary-Registry-Offsets-Database--vYYYY-MM.xlsx`), ~every 2 months.
- Fetch: main workbook (~17 MB), sheet `PROJECTS`, header on row 4. Keep VCS/GOLD/ISO/ACR/CAR/ART rows with an in-scope country. Year blocks: issued by vintage (used), retired by year, remaining by vintage, issued by issuance year (used for first issuance) — each block is read only up to where the years restart.
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
- Probe: hash of the embedded project list + newest row on `/issuances`. Fetch detail pages for in-scope projects only (7 as of 2026-10).
- Retirement beneficiaries: shown client-side; to add in M5 (offtakers).

## jcm — Joint Crediting Mechanism (Japan)
- List: https://www.jcm.go.jp/jc/projects (static HTML on S3, table `#pro_list`, ~150 rows, all partner countries). Only status "Project registered" kept.
- Issuances: https://www.jcm.go.jp/jc/projects-issues (table `#refno_desc`: per monitoring period, one row per country — host and Japan shares). Issued = sum of country rows; first issuance = earliest date.
- Estimated annual: median of non-zero "Estimated emission reductions in each year" on the project page (fetched once per project, then reused).
- Probe: HEAD ETag of the two list pages. Developer = first Japanese participant (both sides kept in participants).

## ucr — Universal Carbon Registry
- Grid: `/CouRegistry/Grid?...&PageSize=1000` lists all projects (~314) with title "(UCR ID Number: N)", status, start/end year, state, type. No robots.txt (404).
- Detail `/Registry/Details?id=...`: location, type, authorized contact, serial blocks (available / retired / tokenized). Issued = sum of distinct serial ranges; country from the serial's ISO2 code (`...-UCR-CoU-IN-...`), else location.
- Probe: grid hash + month → details re-read when the list changes, and at most monthly (~5 min). No issuance dates or ex-ante estimates on UCR pages.

## a6pipeline — UNEP-CCC Article 6 Pipeline
- JSON API behind the activity tables: `POST https://a6pipeline.unepccc.org/api/graphs/4003` with `{"show_as":"table","source":"pacm","pacm_stage":"all_all_registered"}` and `{"show_as":"table","source":"a6p2"}`. No robots.txt (404).
- PACM: registered activities (all CDM transitions in 2026-10); CPAs summed per programme; cross-referenced to `CDM:<id>` so they merge.
- 6.2: rows matched to JCM/Verra/Gold Standard by their document link become annotation records (tag + buyer country, never volume).
  Authorised activities (Registered / MO issued) with no other registry record become their own rows (registry `A62`), e.g. Bangkok E-Bus (Thailand → Switzerland).
- Buyer country = middle code of the A6 ID (e.g. `TH-CH-5002`); `ND` = not disclosed.

## gcc — Global Carbon Council
- gcc2.globalcarboncouncil.com (and the old domain) answer bots with a Cloudflare challenge (HTTP 403, `cf-mitigated: challenge`). No bypass.
- Source: the owner's "Approved Projects → Export" from https://gcc2.globalcarboncouncil.com/search/registration, committed to
  `data/manual/gcc/`. Adapter reads the newest .xlsx; probe = file hash. Fields: submission no., title, validated ER/yr, methodology,
  activity type, country, market eligibility (CORSIA / Article 6.2 CA+ label), validator, crediting period, registration date.
- Not in the export: developer, issued/retired, project page URL (rows link to the GCC search page).

## Offtakers
- CDM: "Credit buyer" column of the UNEP-CCC CDM Pipeline, parsed as `Country (Entity)`; shown as "CDM credit buyer".
- Announcements: `config/offtakers.yaml`, researched by web search; each source must name buyer, project/supplier and date.
