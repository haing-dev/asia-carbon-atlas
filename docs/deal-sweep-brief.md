# Offtake deal sweep — brief (read fully)

Goal: find EVERY publicly announced carbon-credit purchase, offtake, pre-purchase or forward agreement made by the
buyers assigned to you, so a public research website (Carbon Credit Atlas) misses none. Exhaustive ("scorched earth"):
missing a big buyer's deal will look very bad. Also capture public disclosures of credits a buyer RETIRED from named
projects (e.g. in its sustainability / ESG / CDP report or a registry page it links).

## Scope
- Project / supplier location: any country EXCEPT mainland China, North Korea, the Middle East (incl. Iran, Gulf, Israel,
  Jordan...), Oceania (Australia, NZ, PNG, Pacific islands). In scope: Asia (incl. Japan, Korea, Taiwan, HK, SE/South/
  Central Asia), North America (US, Canada, Mexico, Central America, Caribbean), South America, Africa, Europe (incl.
  UK, Turkey, Caucasus, Russia, Ukraine). Buyer HQ can be anywhere.
- Any credit type: nature (REDD+, ARR/reforestation, IFM, mangroves/blue carbon, soil, rice methane, agroforestry),
  engineered removals (biochar, enhanced rock weathering, DAC, BECCS, mineralization, bio-oil/biomass burial), and
  avoidance (cookstoves, landfill/biogas, renewables, methane, etc.). Also Article 6 ITMO purchases and
  results-based-payment ERPAs that transfer credits.
- Any date (as old as 2010 is fine).
- Exclude: equity investments, grants, partnerships or MoUs WITHOUT a credit purchase; projects in excluded countries;
  deals where the source does not name the buyer and at least the supplier/developer.
- Supplier-level deals are fine (e.g. "Microsoft buys 100,000 t from Varaha (India)"), with the country if stated.

## Method (do all)
1. For each buyer, run several WebSearch queries: "<buyer> carbon removal agreement", "<buyer> carbon credits offtake",
   "<buyer> purchases carbon credits", "<buyer> forward purchase carbon", "<buyer> biochar|DAC|BECCS|reforestation|
   REDD|cookstove credits", "<buyer> Article 6", and "<buyer> sustainability report carbon credits retired projects".
   Use mode "extended" when standard results are thin.
2. Check aggregators that list deals by buyer: cdr.fyi (deal alerts, buyer pages), carbonherald.com, carboncredits.com,
   esgtoday.com, carbon-pulse (headlines only), Argus, Bloomberg/Reuters headlines, company press-release pages.
3. OPEN each source with WebFetch to confirm: buyer, supplier/project, country, volume (if any), date. If the page
   cannot be opened, try another source for the same deal; if none opens, include it with "verified": false.
4. Volume = the TOTAL committed volume in tCO2e (multi-year totals, not annual). If only an annual rate and a period
   are given, multiply and say so in volume_note. "Up to X" -> X with volume_note "up to". If not stated -> null.
   If one volume covers several buyers or several projects, give the total and explain in volume_note.
5. Skip sources already checked: run `uv run python -m pipeline.ledger check URL ...`
   for candidate URLs; skip any marked "added" or "not_added" (re-try only "unverified" or "new").
6. Before adding, check whether it's already in the site: grep -i the buyer and supplier in
   config/offtakers.yaml (read-only; DO NOT edit any repo file). Still include it, with
   already_listed true/false (true only if the same buyer+supplier+date/volume is there). If listed but our volume or
   date is wrong/missing, set already_listed true and describe the fix in "fix".

## Output
Write ONLY to the JSON file path given in your task (a list of objects), then reply with a 5-line summary
(counts: found, new, already listed, fixes, unverified). One object per buyer x supplier/project x announcement:
{
 "kind": "offtake" | "retirement_disclosure",
 "buyer": "Microsoft",                      // as named in the source; coalitions: name members if the source does
 "supplier": "Varaha",                       // developer / seller / project proponent
 "project": "Kheti biochar programme",       // project name if named, else null
 "registry_id": "VCS 1234" | "GS 12345" | "Puro 123" | "Isometric ..." | null,  // only if the source or registry states it
 "countries": ["IND"],                        // ISO3; [] if not stated
 "credit_type": "biochar",                   // one of: redd arr ifm blue_carbon peat_wetland other_land rice_methane
                                              // soil_carbon agroforestry livestock fertilizer biochar erw dac beccs
                                              // mineralization biomass_storage solar wind hydro biomass_power geothermal
                                              // other_re industrial_ee waste_heat buildings grid cookstoves water
                                              // household_biogas offgrid_solar landfill wastewater biogas_ad composting
                                              // coal_mine_methane oil_gas_methane industrial_gases cement fuel_switch
                                              // e_mobility mass_transit fleet other
 "volume_tco2e": 100000 | null,
 "volume_note": "",                          // e.g. "100k/yr x 6 yrs (2028-2033)", "up to", "shared with X"
 "period": "2028-2033" | null,
 "date": "2026-01-15",                       // announcement date (YYYY-MM-DD; YYYY-MM if day unknown)
 "source_url": "...", "source_title": "...",
 "quote": "exact sentence(s) from the source naming buyer, supplier and volume",
 "verified": true,                            // you opened the page and the quote is on it
 "already_listed": false, "fix": null
}
