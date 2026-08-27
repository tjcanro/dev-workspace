# tmux and tmuxp

The repository includes two tmuxp templates:

- `local-dev`: Neovim, Neo-tree, and the reusable bottom terminal.
- `remote-dev`: local Neovim editing remote files plus separate remote agent,
  host shell, and guest-entry panes.

`workbench render` substitutes values from `profiles/local.toml` and writes
ordinary tmuxp YAML into `~/.config/tmuxp`. The remote template is rendered only
when `remote.enabled = true`.

The status theme uses blue for local sessions and green for nested remote tmux
sessions. A Nerd Font is required for the session badge and separators.

After installation:

```sh
tmux source-file ~/.config/tmux/dev-workspace-common.conf
tmuxp load ~/.config/tmuxp/local-dev.yaml
```
