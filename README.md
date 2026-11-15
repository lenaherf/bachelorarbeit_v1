# Stakeholder descriptions to PASS models

Bachelor's thesis prototype for building a subject-oriented process model from
two stakeholder perspectives. It prepares and extracts process descriptions,
maps them to PASS fragments, records administrator reviews in Neo4j, and exports
a selected canonical process as RDF.

[Detailed documentation](docs/index.md) · [License](LICENSE.md)

## Setup

Use Python 3.12 and a running Neo4j database. Run all commands from the repository
root. Live extraction also requires an OpenAI API key with access to `gpt-5.2`
(the model currently configured in the code).

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
```

Edit `.env` with your database credentials and, for live extraction, your API key.

To start the included local Neo4j setup, install Docker and run:

```bash
docker compose --env-file .env -f infra/neo4j-pass-spike/compose.yaml up -d
```

Set `PASS_NEO4J_PASSWORD` and `NEO4J_PASSWORD` to the same password before starting
the container. The example configuration uses this container's Bolt port `7688`;
its browser is at <http://localhost:7475>. For an existing database, adjust the
connection settings instead. Database files stay in the local infrastructure
folder and are excluded from Git.

## Run

Start with the fixed complaint example. It requires Neo4j but makes no LLM calls:

```bash
python -m stakeholder_extraction.complaint_demo --reviewer "Your name"
```

Review correspondences and behaviours with `c` (confirm), `r` (reject), or `q`
(quit). The runner prints the saved process URI for export.

To extract your own descriptions using the LLM pipeline:

```bash
python -m stakeholder_extraction.complaint_demo --reviewer "Your name" --live
```

Enter two different stakeholder role names and their descriptions. Finish each
description with a line containing only `.`. Live mode sends the descriptions to
the configured OpenAI service and uses paid API calls. Open questions or mapping
issues stop the run; revise the descriptions and restart. Previously saved
records remain in Neo4j.

Export a saved process, replacing `PROCESS_URI` with the printed URI:

```bash
python -m stakeholder_extraction.export_process \
  --process-uri "PROCESS_URI" \
  --output-directory exports/example-01
```

Select the start subject when prompted. The output directory must be new. It
contains `model.ttl`, a Visio-oriented `model.owl`, and `validation.json`. To
explicitly export a draft with unresolved warnings, add
`--allow-draft-with-warnings`. Validation errors block export.

## Tests

```bash
OPENAI_API_KEY=not-used-for-tests python -m pytest
OPENAI_API_KEY=not-used-for-tests python -m pytest -m integration
```

The first command runs the default tests without live API calls. The dummy key
allows the current API client to initialize during test collection. Integration
tests require the configured Neo4j database and write records; use a separate
test database.

## Project structure and scope

- `stakeholder_extraction/`: extraction, PASS mapping, reconciliation, canonical
  models, database access, validation, and export; tests are in `test/`.
- `ontology/`: reference ontologies, generated Turtle, examples, and prototype
  SHACL shapes. Export vocabulary checks use `standard_PASS_ont_dev.ttl`.
- `evaluation/`: case inputs, recorded runs, exported models, and assessment spreadsheet.
- `infra/`: local Neo4j setup.
- `scripts/manual/`: development checks; some make API calls or write to Neo4j.

The interactive runner currently supports two views. Matching uses normalized
names and requires explicit review. LLM outputs can vary between runs. Passing
the implemented structural and SHACL checks does not establish full PASS
ontology conformance, freedom from communication deadlocks, or compatibility
with every consuming tool.

Parts of this documentation were prepared with the assistance of AI; if you find any issues, please open a pull request.
