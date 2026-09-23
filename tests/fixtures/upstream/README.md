# Upstream contract fixtures

Golden copies of the wire-agent ADR-0003 contract payloads this plugin
emits. `housing.envelope.json` is byte-identical to
`wire-agent/tests/fixtures/upstream/housing.envelope.json`; the wire
importer models (`src/wire/imports.py` there) are the schema source of
truth. When the schema changes, update both copies.
