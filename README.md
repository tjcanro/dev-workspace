# dev-workspace

A repeatable Neovim, tmux, tmuxp, and CLI-agent workspace for developers who
move between local repositories and remote environments.

The repository keeps reusable configuration in Git while leaving credentials,
machine-specific values, agent state, and private operational context on the
machine where they belong.

## What is included

- A shared agent-role format that installs into Claude Code and generates Codex
  custom-agent configuration from the same instructions.
- A read-only `code-reviewer` agent.
- `review-pr` and `review-mr`, which create isolated Git worktrees and open a
  Neovim + Claude review workspace in tmux.
- `neo-help`, which opens the README from your Neovim configuration repository.
- Local and remote tmuxp templates.
- A simple tmux theme that works both locally and on remote hosts.
- `workbench install`, `doctor`, `validate`, `agent new`, and `sync-remote`
  commands.
- A private-overlay mechanism for company-specific agents and profiles.

The Neovim configuration itself remains independent. By default this project
expects [tjcanro/NvimConfig](https://github.com/tjcanro/NvimConfig).

## Quick start

```sh
git clone https://github.com/tjcanro/dev-workspace.git ~/Workspace/dev-workspace
cd ~/Workspace/dev-workspace

cp profiles/example.toml profiles/local.toml
$EDITOR profiles/local.toml

./bin/workbench doctor
./bin/workbench install --dry-run
./bin/workbench install
```

Ensure `~/.local/bin` is on `PATH`, then open the generated development session:

```sh
tmuxp load ~/.config/tmuxp/local-dev.yaml
```

## Commands

```text
workbench doctor
workbench validate
workbench install [--dry-run] [--profile PATH]
workbench render [--dry-run] [--profile PATH]
workbench agent new NAME --description TEXT [--read-only] [--with-skill]
workbench sync-remote HOST [--dry-run] [--profile PATH]

review-pr NUMBER_OR_URL [--repo PATH] [--prepare-only]
review-mr NUMBER_OR_URL [--repo PATH] [--prepare-only]
neo-help
```

`review-pr` uses GitHub CLI; `review-mr` uses GitLab CLI. Both fetch the review
head into an isolated worktree under `~/Workspace/reviews` by default, open
Diffview in Neovim, and start Claude's read-only `code-reviewer` agent beside
the editor.

## Agents and private overlays

Roles in `agents/roles/` are Claude-compatible Markdown files. Installation
symlinks them into `~/.claude/agents` and renders equivalent Codex custom-agent
TOML into `~/.codex/agents`.

Company-specific roles, skills, and profiles should live in a separate private
repository with the same directory shape:

```text
private-workspace/
├── agents/roles/
└── skills/
```

Add that checkout to `profiles/local.toml`:

```toml
[overlays]
paths = ["~/Workspace/private-workspace"]
```

The installer discovers roles and skills from the public repository and every
configured overlay. Skills are installed into both Claude's and Codex's user
skill directories. Private overlays are never copied into this repository.

See [Agent architecture](docs/agents.md), [tmux and tmuxp](docs/tmux.md), and
[security and sharing](docs/security.md) for the design boundaries.

## Development

```sh
./bin/workbench validate
python3 -m unittest discover -s tests -v
```

The repository is intentionally dependency-light. The core CLI uses only the
Python standard library; tmuxp and the optional developer tests bring their own
YAML dependencies.
