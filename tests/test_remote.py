import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import workspace_remote as remote


class RemoteTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="remote-workspace-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.profile = {
            "workspace": {"nvim_config_dir": str(self.root / "source")},
            "remote": {"host": "user@dev-host", "project_root": str(self.root / "project 'quoted'; $data"),
                       "session_name": "test-workspace", "agent_command": "exec sleep 300"},
            "ssh": {"control_dir": str(self.root / "control sockets")},
        }

    def test_connection_sharing_preserves_command_arguments(self):
        args = argparse.Namespace(remote_action="ssh", remote_command=["--", "printf", "%s", "a 'quoted' $(value)"])
        with patch.object(remote.subprocess, "run") as run:
            remote.run(self.profile, args)
        command = run.call_args.args[0]
        self.assertEqual(shlex.split(command[-1]), args.remote_command[1:])
        self.assertEqual(command[-2], "user@dev-host")
        self.assertIn("ControlMaster=auto", command)
        self.assertIn("ControlPersist=15m", command)
        self.assertNotIn("-tt", command)
        self.assertEqual((self.root / "control sockets").stat().st_mode & 0o777, 0o700)

    def test_cli_dispatches_ssh_and_preserves_arguments(self):
        tools = self.root / "cli-tools"
        tools.mkdir()
        capture = self.root / "ssh-arguments.json"
        ssh = tools / "ssh"
        ssh.write_text("#!" + sys.executable + "\nimport json,sys\nfrom pathlib import Path\nPath(" + repr(str(capture)) + ").write_text(json.dumps(sys.argv[1:]))\n")
        ssh.chmod(0o755)
        profile = self.root / "profile.toml"
        profile.write_text('[remote]\nhost = "dev-host"\n[ssh]\ncontrol_dir = ' + json.dumps(str(self.root / "cli-control")) + '\n')
        result = subprocess.run([sys.executable, str(ROOT / "bin/workbench"), "remote", "--profile", str(profile),
                                 "ssh", "--", "printf", "%s", "a 'quoted' value"],
                                env=dict(os.environ, PATH=str(tools) + os.pathsep + os.environ["PATH"]),
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        args = json.loads(capture.read_text())
        self.assertEqual(args[-2], "dev-host")
        self.assertEqual(shlex.split(args[-1]), ["printf", "%s", "a 'quoted' value"])

    def test_invalid_host_and_remote_destination_are_rejected(self):
        for host in ["-oProxyCommand=bad", "host; command", ""]:
            self.profile["remote"]["host"] = host
            with self.assertRaises(remote.RemoteError):
                remote.ssh_command(self.profile)
        for destination in ["", ".", "../other", "/", "/tmp/config", "-option"]:
            self.profile["remote"]["nvim_config_dir"] = destination
            with self.assertRaises(remote.RemoteError):
                remote.remote_target(self.profile)

    def test_login_and_editor_allocate_tty_and_quote_paths(self):
        with patch.object(remote.subprocess, "run") as run:
            remote.run(self.profile, argparse.Namespace(remote_action="ssh", remote_command=[]))
            self.assertIn("-tt", run.call_args.args[0])
            remote.run(self.profile, argparse.Namespace(remote_action="edit", files=["a file;name.rs"]))
            command = run.call_args.args[0]
            self.assertIn("-tt", command)
            self.assertIn(shlex.quote(self.profile["remote"]["project_root"]), command[-1])
            self.assertIn(shlex.quote("a file;name.rs"), command[-1])

    def test_guest_requires_an_explicit_command(self):
        with self.assertRaises(remote.RemoteError):
            remote.ensure_script(self.profile, ["guest"])

    @unittest.skipUnless(shutil.which("tmux"), "requires tmux")
    def test_ensure_preserves_live_sessions_and_recreates_missing_sessions(self):
        project = Path(self.profile["remote"]["project_root"])
        project.mkdir()
        server = "remote-test-" + uuid.uuid4().hex
        tmux = shutil.which("tmux")
        self.addCleanup(lambda: subprocess.run([tmux, "-L", server, "kill-server"], capture_output=True))
        tools = self.root / "tools"
        tools.mkdir()
        wrapper = tools / "tmux"
        wrapper.write_text("#!/bin/sh\nexec " + shlex.join([tmux, "-L", server, "-f", "/dev/null"]) + ' "$@"\n')
        wrapper.chmod(0o755)
        env = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ["PATH"])
        script = remote.ensure_script(self.profile, ["agent", "host"])
        subprocess.run(["sh", "-c", script], env=env, check=True)
        query = [tmux, "-L", server, "display-message", "-p", "-t", "test-workspace-agent:agent.0", "#{pane_id}:#{pane_current_path}"]
        first = subprocess.check_output(query, text=True)
        subprocess.run(["sh", "-c", script], env=env, check=True)
        self.assertEqual(subprocess.check_output(query, text=True), first)
        self.assertEqual(Path(first.strip().split(":", 1)[1]).resolve(), project.resolve())
        subprocess.run([tmux, "-L", server, "kill-session", "-t", "=test-workspace-agent"], check=True)
        subprocess.run(["sh", "-c", script], env=env, check=True)
        self.assertNotEqual(subprocess.check_output(query, text=True), first)

    @unittest.skipUnless(shutil.which("rsync"), "requires rsync")
    def test_sync_validates_destination_and_preserves_git_including_delete_mode(self):
        source = Path(self.profile["workspace"]["nvim_config_dir"])
        source.mkdir()
        (source / ".git").mkdir()
        (source / ".git" / "config").write_text("local metadata")
        (source / "init.lua").write_text("return {}\n")
        (source / "new.lua").write_text("return true\n")
        home = self.root / "remote-home"
        destination = home / "Workspace" / "NvimConfig"
        (destination / ".git").mkdir(parents=True)
        (destination / ".git" / "config").write_text("remote metadata")
        (destination / "init.lua").write_text("old config\n")
        (destination / "remote-only.lua").write_text("keep until --delete\n")
        (home / ".config").mkdir()
        (home / ".config" / "nvim").symlink_to(destination)
        actual_run = subprocess.run
        calls = []

        def local_transport(command, **kwargs):
            calls.append(command)
            if command[0] == "ssh":
                # Exercise the actual remote preflight in a disposable home
                # without connecting to SSH or changing the process HOME.
                script = command[-1].replace('"$HOME"', shlex.quote(str(home)))
                script = script.replace('$HOME/.config/nvim', str(home / ".config/nvim"))
                return actual_run(["sh", "-c", script], **kwargs)
            transport_index = command.index("-e")
            local = command[:transport_index] + command[transport_index + 2:-1] + [str(destination) + "/"]
            return actual_run(local, stdout=subprocess.PIPE, **kwargs)

        with patch.object(remote.subprocess, "run", side_effect=local_transport):
            remote.sync_nvim(self.profile, dry_run=True, delete=True)
            self.assertFalse((destination / "new.lua").exists())
            self.assertTrue((destination / "remote-only.lua").exists())
            remote.sync_nvim(self.profile)
            self.assertTrue((destination / "new.lua").exists())
            self.assertTrue((destination / "remote-only.lua").exists())
            remote.sync_nvim(self.profile, delete=True)
            self.assertFalse((destination / "remote-only.lua").exists())
            self.assertEqual((destination / ".git/config").read_text(), "remote metadata")
            (home / ".config/nvim").unlink()
            with self.assertRaises(subprocess.CalledProcessError):
                remote.sync_nvim(self.profile)
        self.assertEqual(calls[-1][0], "ssh")


if __name__ == "__main__":
    unittest.main()
