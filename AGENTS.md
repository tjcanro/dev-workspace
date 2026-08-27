# Repository instructions

This is a public configuration and tooling repository.

- Never add credentials, private hostnames, internal repository details,
  company topology, active handoffs, agent conversation history, or personal
  absolute paths. Use a private overlay and `profiles/local.toml` instead.
- Treat `agents/roles/*.md` as the behavioral source of truth. Do not check in
  separately maintained Claude and Codex copies; `workbench install` renders
  the Codex adapter.
- Keep reusable task procedures in focused skills beneath `skills/` and keep
  live state outside the repository.
- Preserve portability across macOS and common Linux shells. The core
  `workbench` CLI must remain Python-standard-library only.
- After changes, run `./bin/workbench validate` and
  `python3 -m unittest discover -s tests -v`.
