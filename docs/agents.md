# Agent architecture

`agents/roles/<name>.md` is the behavioral source of truth. It uses Claude Code
frontmatter because Claude can load it directly. `workbench install` extracts
the same Markdown body into a Codex custom-agent TOML file, avoiding two prompts
that drift independently.

Use four distinct kinds of information:

| Kind | Location | Git policy |
| --- | --- | --- |
| Role and safety boundary | `agents/roles/` | Versioned |
| Reusable procedure | `skills/` | Versioned |
| Stable domain knowledge | Private overlay | Versioned privately |
| Current handoff and conversation state | User state directory | Never versioned |

Create a role with:

```sh
bin/workbench agent new log-investigator \
  --description "Diagnose application logs without changing the environment" \
  --read-only \
  --with-skill
```

Then replace the generated general workflow with the genuinely non-obvious
rules, sources, and completion criteria for that specialist. Run
`bin/workbench validate` before installing it.

Private overlays use the same layout and are listed in the local profile. This
keeps public tooling and private operational context separate without creating
a second installer.
