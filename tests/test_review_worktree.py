import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
import uuid


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("tmux") and shutil.which("jq"), "requires tmux and jq")
class ReviewWorktreeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="review-launch-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "sample"
        self.repo.mkdir()
        self.tools = self.root / "tools"
        self.tools.mkdir()
        self.server = "review-test-" + uuid.uuid4().hex
        self.real_tmux = shutil.which("tmux")
        self.env = dict(os.environ, CODE_REVIEW_ROOT=str(self.root / "reviews"))
        self.env.pop("TMUX", None)
        self.env.pop("TMUX_PANE", None)
        self.env["PATH"] = str(self.tools) + os.pathsep + self.env["PATH"]
        self.env["REVIEW_TEST_ROOT"] = str(self.root)
        self.env["REVIEW_TEST_TMUX"] = self.real_tmux
        self.env["REVIEW_TEST_SERVER"] = self.server
        self.env["REVIEW_TEST_GIT"] = shutil.which("git")
        self.env["REVIEW_TEST_REPO"] = str(self.repo)
        self.env["REVIEW_TEST_AGENT_EXIT"] = "7"
        self.addCleanup(self.stop_server)
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Review Test")
        self.git("config", "user.email", "review@example.com")
        (self.repo / "file.txt").write_text("base\n")
        self.git("add", "file.txt")
        self.git("commit", "-m", "base")
        self.base = self.git("rev-parse", "HEAD").strip()
        (self.repo / "file.txt").write_text("head\n")
        self.git("commit", "-am", "head")
        self.head = self.git("rev-parse", "HEAD").strip()
        self.git("update-ref", "refs/pull/1/head", self.head)
        self.git("update-ref", "refs/heads/main", self.base)
        self.git("remote", "add", "origin", str(self.repo))
        self.git("remote", "set-url", "origin", "https://github.com/example/sample.git")
        # Use local Git transport; no provider or authentication is involved.
        self.tool("git", '''#!/usr/bin/env python3
import os
import sys
args = sys.argv[1:]
if "fetch" in args:
    args[args.index("origin", args.index("fetch"))] = os.environ["REVIEW_TEST_REPO"]
os.execv(os.environ["REVIEW_TEST_GIT"], [os.environ["REVIEW_TEST_GIT"], *args])
''')
        (self.root / "metadata.json").write_text(json.dumps({
            "number": 1, "title": "Test review", "url": "https://github.com/example/sample/pull/1",
            "baseRefName": "main", "headRefOid": self.head,
        }))
        self.tool("gh", '#!/bin/sh\ncat "$REVIEW_TEST_ROOT/metadata.json"\n')
        self.tool("nvim", '#!/bin/sh\nexec sleep 300\n')
        self.tool("claude", '''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys
root = Path(os.environ["REVIEW_TEST_ROOT"])
(root / "agent-args.json").write_text(json.dumps(sys.argv[1:]))
with (root / "agent-starts").open("a") as log:
    log.write("start\\n")
if os.environ["REVIEW_TEST_AGENT_EXIT"] == "live":
    os.execlp("sleep", "sleep", "300")
print("simulated startup failure", flush=True)
sys.exit(int(os.environ["REVIEW_TEST_AGENT_EXIT"]))
''')
        self.tool("tmux", '''#!/bin/sh
case "$1" in
  attach-session|switch-client)
    printf '%s\n' "$1" >> "$REVIEW_TEST_ROOT/attachments"
    exit 0 ;;
esac
exec "$REVIEW_TEST_TMUX" -L "$REVIEW_TEST_SERVER" -f /dev/null "$@"
''')

    def stop_server(self):
        subprocess.run([self.real_tmux, "-L", self.server, "kill-server"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def tool(self, name, source):
        path = self.tools / name
        path.write_text(source)
        path.chmod(0o755)

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args],
                                       text=True, stderr=subprocess.DEVNULL)

    def tmux(self, *args):
        return subprocess.check_output([str(self.tools / "tmux"), *args],
                                       env=self.env, text=True, stderr=subprocess.DEVNULL).strip()

    def launch(self, *args):
        result = subprocess.run([str(ROOT / "bin" / "review-pr"), "1", "--repo", str(self.repo), *args],
                                env=self.env, text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def panes(self):
        return self.tmux("list-panes", "-t", "review-sample-pr-1:review",
                         "-F", "#{pane_id}|#{pane_dead}|#{pane_dead_status}|#{@review-role}").splitlines()

    def wait_for_agent(self, starts=1, dead=True):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            log = self.root / "agent-starts"
            count = len(log.read_text().splitlines()) if log.exists() else 0
            agents = [p.split("|") for p in self.panes() if p.endswith("|reviewer")]
            if count == starts and len(agents) == 1 and agents[0][1] == str(int(dead)):
                # Exit notification can precede tmux draining the final PTY output.
                if dead and "simulated startup failure" not in self.tmux(
                        "capture-pane", "-p", "-t", agents[0][0], "-S", "-100"):
                    time.sleep(0.05)
                    continue
                return agents[0]
            time.sleep(0.05)
        self.fail("reviewer did not reach expected state")

    def test_failed_agent_stays_visible_and_restarts_without_refreshing_checkout(self):
        self.launch()
        pane = self.wait_for_agent()
        self.assertEqual(pane[2], "7")
        args = json.loads((self.root / "agent-args.json").read_text())
        self.assertEqual(args[args.index("--model") + 1], "opus")
        self.assertEqual(args[args.index("--effort") + 1], "xhigh")
        self.assertIn("before/after behavior", args[-1])
        self.assertIn("Mermaid flow diagram", args[-1])
        self.assertIn("simulated startup failure", self.tmux(
            "capture-pane", "-p", "-t", pane[0], "-S", "-100"))
        worktree = self.root / "reviews" / "sample-pr-1"
        (worktree / "file.txt").write_text("unfinished edit\n")
        self.env["TMUX"] = "test-client"
        result = self.launch()
        self.wait_for_agent(starts=2)
        self.assertNotIn("Fetching", result.stdout)
        self.assertEqual((worktree / "file.txt").read_text(), "unfinished edit\n")
        self.assertEqual((self.root / "attachments").read_text().splitlines(),
                         ["attach-session", "switch-client"])
        self.assertEqual(len(self.panes()), 2)

    def test_missing_agent_is_restored_and_live_legacy_agent_is_reused(self):
        self.env["REVIEW_TEST_AGENT_EXIT"] = "live"
        self.launch()
        pane = self.wait_for_agent(dead=False)
        self.tmux("set-option", "-p", "-t", pane[0], "-u", "@review-role")
        self.launch()
        self.wait_for_agent(dead=False)
        self.assertEqual(len(self.panes()), 2)
        self.tmux("kill-pane", "-t", pane[0])
        self.launch()
        self.wait_for_agent(starts=2, dead=False)
        self.assertEqual(len(self.panes()), 2)

    def test_prepare_only_does_not_start_tmux_or_agent(self):
        self.launch("--prepare-only")
        self.assertTrue((self.root / "reviews" / "sample-pr-1" / ".git").exists())
        self.assertFalse((self.root / "agent-starts").exists())
        self.assertFalse((self.root / "attachments").exists())


if __name__ == "__main__":
    unittest.main()
