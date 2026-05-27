# Project Context

This repo contains small, mostly independent scripts. Keep durable context at the
use-case/script level so future sessions can start with the relevant notes without
mixing unrelated tools.

## Context Files

- `AGENTS.md` - repo-wide instructions for agent behavior.
- `docs/development-pipeline.md` - end-to-end development pipeline.
- `docs/requirement-intake.md` - requirement intake process.
- `docs/prd-process.md` - PRD rules, sections, and approval gates.
- `docs/implementation-process.md` - coding workflow.
- `docs/testing-process.md` - verification expectations.
- `docs/deployment-readiness.md` - release readiness checklist.
- `sync_folders/context.md` - context for the folder sync utility.
- `find_duplicates/context.md` - context for the duplicate finder.

## Convention

- Read `AGENTS.md` before starting work.
- At the start of future work, read the nearest relevant `context.md` first.
- Keep this root file as an index and repo-wide convention only.
- Put implementation notes, UI decisions, test commands, and known tradeoffs in the
  script-level context file.
- Update a script-level context file when source changes affect future work.
- Do not treat context files as authoritative when the source disagrees; source wins.
