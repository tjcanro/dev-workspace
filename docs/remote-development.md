# Remote development

The portable helpers live in `dev-workspace`. Neovim-specific remote buffers,
search, previews, diffs, and plugin adaptations live in
[NvimConfig](https://github.com/tjcanro/NvimConfig).

## Profile

Copy `profiles/example.toml` to the ignored `profiles/local.toml`. Keep private
host aliases, directories, and agent commands in that local file:

```toml
[remote]
enabled = true
host = "dev-host"
project_root = "/home/user/project"
session_name = "remote-dev"
editor_command = "nvim"
agent = "code-reviewer"
guest_command = "make vm-ssh"
nvim_config_dir = "Workspace/NvimConfig"

[ssh]
control_dir = "~/.ssh/workbench"
control_persist = "15m"
```

These are sections to merge into the full example profile. `remote.enabled`
controls tmuxp rendering; an explicit `workbench remote` command uses the profile
whether or not that template is enabled. To select another profile, put
`--profile PATH` immediately after `remote`.

Authentication, ports, jump hosts, and identity files remain in your existing
OpenSSH configuration. The helpers do not edit it. They pass connection-sharing
options to SSH and create a user-owned socket directory with mode 0700. A shared
connection remains available for the configured interval after its clients exit.

## SSH and native remote editing

```sh
workbench remote ssh
workbench remote ssh -- git --version
workbench remote ssh -- sh -lc 'cd /home/user/project && git status --short'
workbench remote edit
workbench remote edit 'src/a file.rs'
```

`ssh` without a command opens an interactive login. Command arguments retain
their boundaries through remote shell quoting; use `sh -lc` explicitly when
you need shell syntax. `edit` changes to `project_root`, adds `~/.local/bin` to
the remote PATH, and runs `editor_command` with an interactive terminal.

Native remote editing requires Neovim, its configuration/plugins, and supporting
tools already installed on the remote host. Editor configuration remains
separate from source code. This command launches the editor; it does not install
software or make the editor process persistent.

When remote installation is unavailable, run Neovim locally and use:

```vim
:RemoteSession dev-host//home/user/project
```

That mode keeps Neovim local and accesses files through SSH. Remote search needs
Git; language-server features require a suitable language server remotely. The
Neovim Lua helper manages its own connection sockets under Neovim's state
directory, independently of workbench's sockets. Its existing remote AI
integration still has host-specific settings; arbitrary-host file editing does
not imply arbitrary-host AI routing.

## Persistent remote terminals

```sh
workbench remote ensure host agent
workbench remote attach host
workbench remote attach agent
workbench remote attach guest
```

Roles become named remote tmux sessions, for example `remote-dev-host` and
`remote-dev-agent`. `ensure` creates only missing sessions. `attach` first
ensures its requested session, then attaches. Existing sessions and their
processes are preserved, including when commands in the profile change. Detach
with the remote tmux prefix followed by `d`.

The host role opens a login shell. The agent role defaults to `claude --agent`
with the configured role. To use a different CLI or resume policy, set
`remote.agent_command`, for example `"claude --continue"`. The guest role runs
`remote.guest_command`; omit that field if guest access is not needed.

Editor and agent commands are trusted shell commands from your local profile.
Each session starts in `project_root`. A guest command should enter an existing
guest; the helper does not inspect VM state, start guests, reset disks, remove
old sessions, or apply migrations. It requires tmux and a POSIX shell remotely;
`flock` and KVM utilities are not needed. Prefixes must differ when projects
share a remote account to avoid reusing another project's sessions.

## Neovim configuration sync

```sh
workbench remote sync-nvim --dry-run
workbench remote sync-nvim
# Preview an exact mirror, including removal of remote-only config files:
workbench remote sync-nvim --dry-run --delete
workbench remote sync-nvim --delete
```

The source is `[workspace].nvim_config_dir`. The destination is
`[remote].nvim_config_dir`, relative to the remote home. Both must already be
Neovim Git checkouts containing `init.lua`. The remote `~/.config/nvim` must be a
symlink resolving to that destination. Validation uses portable shell commands
on macOS and Linux.

The local configuration is authoritative: matching remote files are overwritten.
Remote-only files are kept unless `--delete` is supplied. `.git` metadata and
`.DS_Store` are excluded. `--dry-run` validates the destination and previews file
changes without copying or removing remote files. SSH and rsync are required on
the relevant machines. The command does not install tools, copy authentication,
restore plugins, or synchronize source repositories.

To restore plugins afterward when desired:

```sh
workbench remote ssh -- nvim --headless '+Lazy! restore' +qa
```

`workbench sync-remote HOST` remains a separate operation that copies configured
agent roles and skills. It does not synchronize Neovim configuration or generate
remote Codex agent adapters.
