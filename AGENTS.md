# Repository instructions

## Agent skills

### Issue tracker

Track issues and specs in GitHub Issues for `fabricesemti80/home-dc`. Before reading or publishing tickets, read `docs/agents/issue-tracker.md`.

### Triage labels

Use the five default triage labels. Before triaging issues, read `docs/agents/triage-labels.md`.

### Secrets inventories

This repository holds no secrets. Secret and env-var inventories live in each owner repository's `docs/secrets-and-env-vars.md`, linked from the README's "Secrets and state" section. If a summary line in that section changes (a Doppler project/config, or which repository owns a credential), keep it consistent with those inventories. If a new `home-dc-*` repository with secrets is added, add its inventory link to the table.

### Domain docs

Use a single-context layout: root `GLOSSARY.md` and `docs/adr/`. Before exploring the repository, read `docs/agents/domain.md`.
