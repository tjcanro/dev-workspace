---
name: workspace-agent-authoring
description: Create or update shared Claude and Codex agent roles inside a dev-workspace repository.
---

# Workspace agent authoring

Use the repository's role as the shared source of instructions for Claude and
Codex. Do not maintain separate copies of the behavioral prompt.

## Workflow

1. Run `bin/workbench agent new <name> --description <description>` when the
   role does not exist. Add `--read-only` when the agent must never edit, and
   `--with-skill` only when it needs a reusable task workflow beyond its role.
2. Refine `agents/roles/<name>.md` with a narrow scope, concrete trigger,
   permission boundary, required source material, and completion criteria.
3. Put conditional or lengthy procedures in a focused skill under `skills/`.
   Keep task state and conversation history outside Git.
4. Run `bin/workbench validate` and inspect `bin/workbench install --dry-run`
   before installation.

Do not publish company hostnames, credentials, active handoffs, incident memory,
private repository details, or machine-specific absolute paths. Put those roles
in a configured private overlay with the same `agents/roles/` and `skills/`
layout.
