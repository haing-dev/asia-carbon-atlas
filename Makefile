# Common tasks. All targets except `refresh` work offline from committed records.
PY := uv run python

.PHONY: refresh process validate data site test
refresh:            ## probe sources, fetch only what changed (network)
	$(PY) -m pipeline.refresh $(ARGS)
process:            ## rebuild projects from committed records
	$(PY) -m pipeline.process
validate:
	$(PY) -m pipeline.validate
data:               ## build website data files into web/public/data
	$(PY) -m pipeline.build
site: data          ## build the static website into web/dist
	cd web && npm ci --no-audit --no-fund && npm run build
test:
	uv run pytest -q
