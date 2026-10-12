# Asia Carbon Credit Atlas

Research-only public website mapping carbon credit projects in Asia (ex-China).

- Full spec: `docs/SPEC.md`. Current status and next steps: `docs/progress.md` (read this first).
- Source notes: `docs/sources.md`. Methods shown on the site: `docs/methods.md`.

MUSTs (details in the spec):
- Verifiable data only: every row links to a public registry/official record; every number traces to source URL + version + hash.
- Offtakers only from public records/announcements; never inferred.
- Polite collection: robots.txt, ≤1 req/s per host, no logins, no bot-protection bypass; broken source → mark stale, keep last good data.
- Efficiency: probe before fetch; fetch only what changed; no-op runs make no commit and no deploy; Claude never runs in data refreshes.
- No paid API calls. Never commit, log or paste secrets.

Commands: `make process` (rebuild projects from committed records, no network), `make site` (build website data + site), `make test`.
Work loop from chat: edit → `make test site` → commit → push `main` → `gh run watch` → report. Update `docs/progress.md` after each session.
