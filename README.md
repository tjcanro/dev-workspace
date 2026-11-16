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
- Shared SSH connections, remote editor launch, persistent named remote
  terminals, and validated Neovim configuration sync.
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
workbench remote [--profile PATH] ssh [-- COMMAND ARG...]
workbench remote [--profile PATH] edit [FILE...]
workbench remote [--profile PATH] ensure ROLE...
workbench remote [--profile PATH] attach ROLE
workbench remote [--profile PATH] sync-nvim [--dry-run] [--delete]

review-pr NUMBER_OR_URL [--repo PATH] [--prepare-only]
review-mr NUMBER_OR_URL [--repo PATH] [--prepare-only]
neo-help
```

`review-pr` uses GitHub CLI; `review-mr` uses GitLab CLI. Both fetch the review
head into an isolated worktree under `~/Workspace/reviews` by default, open
Diffview in Neovim, and start Claude's read-only `code-reviewer` agent beside
the editor. New reviewer sessions use Claude's `opus` model alias
with extra-high (`xhigh`) effort. Reports include findings and evidence gaps,
then a change summary and a Mermaid diagram of the implementation with verified
code references.

Rerunning either command preserves an active review checkout and restores a
missing or exited reviewer pane. Agent startup failures stay visible in the
pane; resolve the displayed error and rerun the command to restart the agent.

## Remote workspaces

Set `[remote].host` and `project_root` in your local profile. Then:

```sh
workbench remote ssh
workbench remote ssh -- git --version
workbench remote edit
workbench remote ensure host agent
workbench remote attach host
workbench remote sync-nvim --dry-run
```

SSH connections are reused for 15 minutes by default. Named remote tmux
sessions survive a local disconnect; rerunning `ensure` or `attach` preserves
live sessions and creates missing ones. Guest access uses your configured
command. These helpers use existing remote tools and never start or reset a VM.

See [Remote development](docs/remote-development.md) for both editor modes,
configuration, sync behavior, and prerequisites. Python 3.11 or newer is required
for `workbench`.

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

A skill that already lives in its own canonical repository can be registered
without copying it into an overlay:

```toml
[skills]
paths = ["~/Workspace/example-skill"]
```

Each path must contain a top-level `SKILL.md`. The installer uses the skill name
from that file and links the same source into both agent harnesses.

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
