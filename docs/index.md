---
layout: default
title: Documentation
---

# Stakeholder descriptions to PASS models

This bachelor's thesis prototype combines two stakeholder perspectives into a
reviewed, subject-oriented process model using PASS (Parallel Activity
Specification Schema). It uses an LLM to extract process knowledge, Neo4j to
store the model and review decisions, and RDF to export the resulting process.

[Setup](#setup) · [Run](#run) · [Workflow](#workflow) ·
[Infrastructure](#infrastructure) · [Ontology and term mapping](#ontology-and-term-mapping) ·
[Tests](#tests) · [Evaluation](#evaluation) · [Limitations](#limitations)

## Setup

Use Python 3.12. Neo4j is required for the demo and export; Docker can run the
included database setup. Live extraction additionally requires an OpenAI API
key with access to `gpt-5.2`, the model configured in the code.

Clone the repository and run these commands from its root:

```bash
git clone https://github.com/lenaherf/bachelorarbeit_v1.git
cd bachelorarbeit_v1
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
```

Edit `.env` before starting the application:

| Setting | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | API key for live extraction; leave empty for the fixed demo. |
| `NEO4J_URI` | Database address; `bolt://localhost:7688` for the included container. |
| `NEO4J_USERNAME` | Database user; `neo4j` for the included container. |
| `NEO4J_PASSWORD` | Your database password. |
| `NEO4J_DATABASE` | Database name; defaults to `neo4j`. |
| `PASS_NEO4J_PASSWORD` | Initial password for the included container; match `NEO4J_PASSWORD`. |

Keep real credentials in `.env`, which is excluded from Git.

Start the local database with Docker running:

```bash
docker compose --env-file .env -f infra/neo4j-pass-spike/compose.yaml up -d
```

Wait for Neo4j to become available at <http://localhost:7475>. Both published
ports are bound to `127.0.0.1`, limiting access through them to your computer.
For an existing Neo4j instance, use its connection settings and skip Docker.

## Run

### Fixed complaint example

```bash
python -m stakeholder_extraction.complaint_demo --reviewer "Your name"
```

This starts with predefined Customer and Customer Service views, so it makes no
LLM calls. It exercises PASS mapping, correspondence review, behaviour selection,
canonical process assembly, database storage and retrieval, and completeness
checks using known inputs.

At review prompts, enter `c` to confirm, `r` to reject, or `q` to quit. Your
reviewer name is stored with the decisions. A completed run prints the saved
process URI, which is needed for export.

### Live descriptions

```bash
python -m stakeholder_extraction.complaint_demo --reviewer "Your name" --live
```

Enter two different stakeholder role names and their process descriptions.
Finish each description with a line containing only `.`. Inspect and confirm
the extracted views, then review correspondences and behaviours.

Live mode sends the descriptions to OpenAI and incurs API usage charges. If
open questions or mapping issues remain, revise the descriptions and restart.
Rejecting a required selection also stops the current run. Previously saved
records remain in Neo4j.

### Export

Replace `PROCESS_URI` with the URI printed by the completed run:

```bash
python -m stakeholder_extraction.export_process \
  --process-uri "PROCESS_URI" \
  --output-directory exports/example-01
```

Select the process start subject when prompted. The output directory must not
already exist. The exporter writes:

| File | Contents |
| --- | --- |
| `model.ttl` | Canonical process as PASS RDF in Turtle format. |
| `model.owl` | RDF/XML adapted for the Visio importer. |
| `validation.json` | Completeness issues, warnings, and prototype SHACL results. |

Errors block export. Warnings require explicit acceptance with the additional
flag `--allow-draft-with-warnings`; the output is then marked as a draft.

## Workflow

1. **Prepare text:** correct language and rewrite descriptions into active
   sentences while preserving process information.
2. **Extract:** create a structured stakeholder view containing candidate
   subjects, messages, activities, states, transitions, evidence, and questions.
3. **Map:** convert candidates into separate PASS fragments and report
   unresolved references or unsupported combinations.
4. **Review correspondences:** propose subjects with matching normalized names,
   paired messages, and messages described by only one perspective. An
   administrator confirms or rejects the proposals.
5. **Select behaviours:** review each stakeholder's source behaviour and
   assemble the confirmed canonical elements into one process selection.
6. **Validate and export:** check structure and completeness, then validate
   exported RDF against the prototype SHACL profile.

Neo4j stores the source views, fragments, review decisions, and canonical
elements. Export vocabulary checks use the development ontology in
`ontology/generated/standard_PASS_ont_dev.ttl`.

## Infrastructure

`infra/neo4j-pass-spike/compose.yaml` provides Neo4j 5.26.0 Community Edition.
Use the start command and connection settings in [Setup](#setup). The Python
pipeline stores its application data directly through the Neo4j driver.

The container stores its data in the local `data/` folder and logs in `logs/`
under `infra/neo4j-pass-spike/`. These folders are excluded from Git. To stop
the container, run from the repository root:

```bash
docker compose --env-file .env -f infra/neo4j-pass-spike/compose.yaml down
```

The locally stored database files remain available for the next start. Changing
the password in `.env` does not reset an existing database's password.

## Ontology and term mapping

The PASS ontology is published by
[I2PM](https://github.com/I2PM/Standard-PASS-Ontology). The repository includes:

| File or folder under `ontology/` | Purpose |
| --- | --- |
| `source/standard_PASS_ont_dev.owl` | Bundled development ontology, with version IRI `http://www.i2pm.net/standard-pass-ont/dev`. |
| `source/standard_PASS_ont_v_1.1.0.owl` | Released version 1.1.0, retained for reference; not loaded by the current exporter. |
| `generated/standard_PASS_ont_dev.ttl` | Turtle representation of the development ontology, used for export vocabulary checks. |
| `shapes/pass-prototype-shapes.ttl` | The prototype's SHACL export profile, rather than a complete translation of the ontology. |
| `examples/complaint-reference.ttl` | Reference PASS model for the complaint scenario. |

The original conversion command for the Turtle representation is not recorded
in this repository. The generated file contains an OWL API generator annotation.
Identify the bundled development source with:

```bash
shasum -a 256 ontology/source/standard_PASS_ont_dev.owl
```

The ontology files are third-party material, excluded from this project's own
MIT license grant. Consult the upstream license and retain its original
copyright and permission notices.

### PASS terms

This table connects process concepts to the formal names used in the PASS
ontology. Each term's full IRI is the namespace
`http://www.i2pm.net/standard-pass-ont#` followed by the term name.

| Concept | PASS term |
| --- | --- |
| Process model | `PASSProcessModel` |
| Subject with a specified behaviour | `FullySpecifiedSubject` |
| External subject represented through its interactions | `InterfaceSubject` |
| Message definition | `MessageSpecification` |
| Message exchange between subjects | `MessageExchange` |
| Subject behaviour | `SubjectBehavior` |
| Base behaviour used in the RDF export | `SubjectBaseBehavior` |

## Tests

Install dependencies as described above, then run:

```bash
OPENAI_API_KEY=not-used-for-tests python -m pytest
```

The default tests exclude integration tests and do not make live LLM calls.
The dummy key allows the current API client to initialize during test collection.

To run integration tests against a separately configured test database:

```bash
OPENAI_API_KEY=not-used-for-tests python -m pytest -m integration
```

Integration tests write records to the Neo4j database selected in `.env`.

## Evaluation

The repository contains five case inputs in `evaluation/input/`, recorded runs
under `evaluation/runs/EC-*/R*/`, and the assessment spreadsheet
`evaluation/results_modelcheck_NLcheck.xlsx`. Successful exports include model
files and validation reports; stopped runs may contain only a terminal log.

To repeat a case, use live mode, enter its two stakeholder descriptions, and
record the extraction, review decisions, and validation outcome. Export the
saved process when possible. LLM responses can differ between repetitions,
including whether clarification is requested or export is possible.

## Limitations

- The interactive runner currently accepts exactly two stakeholder views.
- Correspondence matching uses normalized names; it does not resolve arbitrary
  synonyms automatically.
- Unresolved questions and mapping issues require revising the input and
  starting another run; the runner has no interactive editing step.
- Structural completeness and prototype SHACL conformance do not establish
  full PASS ontology conformance, freedom from communication deadlocks, or
  compatibility with every consuming tool. The export report records full
  ontology and consuming-tool validation as `not_run`.

## License

Original code and documentation are licensed under MIT. Bundled third-party
material, including the PASS ontologies and their converted representations,
is excluded and remains subject to its owners' terms. See the repository's
[LICENSE.md](https://github.com/lenaherf/bachelorarbeit_v1/blob/main/LICENSE.md)
for the full text and scope.

Parts of this documentation were prepared with the assistance of AI; if you
find any issues, please open a pull request.
