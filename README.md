# scripts

Daily-use local automation scripts and a sample development pipeline for
agent-assisted work.

## Projects

- `sync_folders/` - sync missing or changed files from one folder to another.
- `find_duplicates/` - find duplicate files and optionally delete duplicates
  using an explicit keep policy.

## Development Pipeline

Start with:

- `AGENTS.md` - repo-wide agent instructions.
- `context.md` - durable repo context and document index.
- `docs/development-pipeline.md` - intake-to-release workflow.

Subprojects may also include their own `AGENTS.md` and `context.md` files.
Read the nearest ones before changing code in that area.
