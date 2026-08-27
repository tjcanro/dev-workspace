# Security and sharing

This repository is public. Do not add:

- Credentials, kubeconfigs, SSH keys, tokens, passwords, or secret-bearing
  environment files
- Company hostnames, site identifiers, private repository URLs, or internal
  network topology
- VM overlays, logs, generated runtime data, or source mirrors
- Agent conversation history, active handoffs, or incident-specific memory
- Personal absolute paths

Use `profiles/local.toml` for machine values and a separate private overlay for
company agents, skills, knowledge, and tmuxp profiles. `workbench validate`
checks committed workspace content for known private markers, but it is a guard
rail rather than a substitute for review.
