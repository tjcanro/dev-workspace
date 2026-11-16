"""Portable SSH workspace operations; no third-party Python dependencies."""

import argparse
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import subprocess


class RemoteError(ValueError):
    pass


def host_name(profile):
    host = profile.get("remote", {}).get("host", "")
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.@-]*", host):
        raise RemoteError("remote.host must be an SSH alias or user@host")
    return host


def ssh_command(profile, command=None, *, tty=False):
    host = host_name(profile)
    settings = profile.get("ssh", {})
    directory = Path(os.path.expandvars(os.path.expanduser(
        settings.get("control_dir", "~/.ssh/workbench"))))
    if directory.is_symlink():
        raise RemoteError("SSH control directory must not be a symlink")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if directory.stat().st_uid != os.getuid():
        raise RemoteError("SSH control directory must belong to the current user")
    directory.chmod(0o700)
    result = ["ssh", "-o", "ControlMaster=auto", "-o",
              "ControlPersist=" + str(settings.get("control_persist", "15m")),
              "-o", "ControlPath=" + str(directory / "%C")]
    if tty:
        result.append("-tt")
    result.append(host)
    if command is not None:
        result.append(command)
    return result


def project_root(profile):
    root = profile.get("remote", {}).get("project_root", "")
    if not root.startswith("/") or "\n" in root:
        raise RemoteError("remote.project_root must be an absolute remote directory")
    return root


def shell_prefix(profile):
    return 'export PATH="$HOME/.local/bin:$PATH"; cd ' + shlex.quote(project_root(profile)) + " && "


def session_spec(profile, role):
    remote = profile.get("remote", {})
    prefix = remote.get("session_name", "remote-dev")
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_-]*", prefix):
        raise RemoteError("remote.session_name must use letters, digits, underscores, or hyphens")
    if role == "host":
        command = 'exec "${SHELL:-/bin/sh}" -l'
    elif role == "agent":
        command = remote.get("agent_command")
        if command is None:
            agent = remote.get("agent", "code-reviewer")
            command = shlex.join(["claude", "--agent", agent])
    elif role == "guest":
        command = remote.get("guest_command", "")
    else:
        raise RemoteError("unknown remote session role")
    if not isinstance(command, str) or not command.strip():
        raise RemoteError(f"configure a non-empty remote.{role}_command")
    return prefix + "-" + role, command


def ensure_script(profile, roles):
    root = project_root(profile)
    lines = ['set -eu', 'export PATH="$HOME/.local/bin:$PATH"', "cd " + shlex.quote(root)]
    for role in roles:
        name, command = session_spec(profile, role)
        # Quote the complete script: the remote login shell may be different
        # from the shell tmux uses to start a new pane.
        pane = shlex.join(["sh", "-lc", command])
        exact = shlex.quote("=" + name)
        lines.extend([
            f"if ! tmux has-session -t {exact} 2>/dev/null; then",
            "  if " + shlex.join(["tmux", "new-session", "-d", "-s", name,
                                   "-n", role, "-c", root, pane]) + "; then :",
            # A concurrent ensure can win the creation race. Only accept that
            # failure when the exact desired session now exists.
            f"  else tmux has-session -t {exact}; fi",
            "fi",
        ])
    return "\n".join(lines)


def remote_target(profile):
    relative = profile.get("remote", {}).get("nvim_config_dir", "Workspace/NvimConfig")
    path = PurePosixPath(relative)
    if (not relative or path.is_absolute() or ".." in path.parts or
            path == PurePosixPath(".") or "\n" in relative or relative.startswith("-")):
        raise RemoteError("remote.nvim_config_dir must be a non-empty directory relative to remote home")
    return str(path)


def sync_nvim(profile, *, dry_run=False, delete=False):
    source = Path(os.path.expandvars(os.path.expanduser(profile["workspace"]["nvim_config_dir"]))).resolve()
    if not (source / ".git").exists() or not (source / "init.lua").is_file():
        raise RemoteError("Neovim source must contain .git and init.lua")
    relative = remote_target(profile)
    # pwd -P works on macOS and Linux, unlike GNU-specific readlink -f.
    check = '\n'.join([
        "set -eu", 'target="$HOME"/' + shlex.quote(relative),
        'test -e "$target/.git"', 'test -f "$target/init.lua"',
        'test -L "$HOME/.config/nvim"',
        'test "$(cd "$target" && pwd -P)" = "$(cd "$HOME/.config/nvim" && pwd -P)"',
    ])
    transport = ssh_command(profile)
    subprocess.run([*transport, check], check=True)
    command = ["rsync", "-ai", "--exclude", "/.git", "--exclude", ".DS_Store"]
    if dry_run:
        command.append("--dry-run")
    if delete:
        command.append("--delete")
    # rsync starts the remote receiver in the remote user's home directory.
    # Quoting the relative path preserves spaces and shell metacharacters.
    command.extend(["-e", shlex.join(transport[:-1]), str(source) + "/",
                    host_name(profile) + ":" + shlex.quote(relative) + "/"])
    subprocess.run(command, check=True)


def run(profile, args):
    action = args.remote_action
    if action == "ssh":
        words = list(args.remote_command)
        if words[:1] == ["--"]:
            words.pop(0)
        subprocess.run(ssh_command(profile, shlex.join(words) if words else None,
                                   tty=not words), check=True)
    elif action == "edit":
        editor = profile.get("remote", {}).get("editor_command", "nvim")
        command = shell_prefix(profile) + editor
        if args.files:
            command += " " + shlex.join(args.files)
        subprocess.run(ssh_command(profile, command, tty=True), check=True)
    elif action in {"ensure", "attach"}:
        roles = [args.role] if action == "attach" else args.roles
        subprocess.run(ssh_command(profile, ensure_script(profile, roles)), check=True)
        if action == "attach":
            name, _ = session_spec(profile, args.role)
            subprocess.run(ssh_command(profile, shlex.join(
                ["exec", "tmux", "attach-session", "-t", "=" + name]), tty=True), check=True)
    elif action == "sync-nvim":
        sync_nvim(profile, dry_run=args.dry_run, delete=args.delete)


def add_parser(subparsers):
    parser = subparsers.add_parser("remote", help="SSH, remote editing, and persistent terminals")
    parser.add_argument("--profile", help="local profile (place before the remote subcommand)")
    actions = parser.add_subparsers(dest="remote_action", required=True)
    ssh = actions.add_parser("ssh", help="login or run a command using a shared SSH connection")
    ssh.add_argument("remote_command", nargs=argparse.REMAINDER, help="remote command and arguments, after --")
    edit = actions.add_parser("edit", help="run an existing remote Neovim installation")
    edit.add_argument("files", nargs="*")
    ensure = actions.add_parser("ensure", help="create missing named remote tmux sessions")
    ensure.add_argument("roles", choices=["host", "agent", "guest"], nargs="+")
    attach = actions.add_parser("attach", help="ensure and attach to a named remote session")
    attach.add_argument("role", choices=["host", "agent", "guest"])
    sync = actions.add_parser("sync-nvim", help="sync config to a validated existing remote checkout")
    sync.add_argument("--dry-run", action="store_true")
    sync.add_argument("--delete", action="store_true", help="also remove remote-only config files; preserves .git")
