import json
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from libs.Claudeck import Claudeck
from libs.commands.worktree_command import WorktreeCommand


def completed(returncode=0, stdout="", stderr=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def claudeck_with(result, installed=True):
    run = Mock(return_value=result) if not isinstance(result, Exception) else Mock(side_effect=result)
    return Claudeck(run=run, which=lambda _: "/usr/local/bin/claudeck" if installed else None), run


class TestClaudeckStatus:
    def test_not_installed_runs_nothing(self):
        c, run = claudeck_with(completed(), installed=False)
        assert c.status() is None
        assert not c.can_start_sessions()
        run.assert_not_called()

    def test_outside_claudeck_is_none(self):
        c, _ = claudeck_with(completed(1, json.dumps({"claudeck": False, "reason": "not here"})))
        assert c.status() is None

    def test_inside_with_starts_allowed(self):
        c, run = claudeck_with(completed(0, json.dumps({"claudeck": True, "sessionId": "s-3", "mayStartSessions": True})))
        assert c.status()["sessionId"] == "s-3"
        assert c.can_start_sessions()
        assert run.call_args[0][0] == ["claudeck", "status", "--json"]

    def test_inside_with_starts_off(self):
        c, _ = claudeck_with(completed(0, json.dumps({"claudeck": True, "mayStartSessions": False})))
        assert not c.can_start_sessions()

    @pytest.mark.parametrize("result", [completed(0, "not json"), subprocess.TimeoutExpired("claudeck", 10), OSError("gone")])
    def test_garbage_or_failure_is_none(self, result):
        c, _ = claudeck_with(result)
        assert c.status() is None


class TestClaudeckNewSession:
    def test_passes_flags_and_prompt_on_stdin(self):
        c, run = claudeck_with(completed(0, "s-7\n"))
        assert c.new_session("brief", directory="/repo", name="EPM-1", worktree=True, focus=True) == "s-7"
        args, kwargs = run.call_args
        assert args[0] == ["claudeck", "session", "new", "--prompt", "-", "--dir", "/repo",
                           "--name", "EPM-1", "--worktree", "--focus"]
        assert kwargs["input"] == "brief"

    def test_refusal_raises_with_reason(self):
        c, _ = claudeck_with(completed(1, "", "claudeck: Rate limited\n"))
        with pytest.raises(Exception, match="Rate limited"):
            c.new_session("brief")


class TestWorktreeCommand:
    def setup_method(self):
        self.issue = SimpleNamespace(key="EPM-42", fields=SimpleNamespace(summary="Fix the thing"))
        self.ui = Mock()
        self.ui.prompt_get_issue.return_value = ["1", Mock(), self.issue]
        self.ui.prompt_get_string.return_value = ""
        self.mygit = Mock()
        self.mygit.branch_name_for_issue.return_value = "bs/epm-42/fix-the-thing"
        self.mygit.repo_root.return_value = "/repo"
        self.mygit.create_worktree_for_issue.return_value = ("bs/epm-42/fix-the-thing", "/repo-worktrees/x")

    def test_under_claudeck_asks_it_for_a_worktree_session(self):
        claudeck = Mock()
        claudeck.can_start_sessions.return_value = True
        claudeck.new_session.return_value = "s-9"
        WorktreeCommand(claudeck).execute(self.ui, Mock(), Mock(), mygit=self.mygit)

        self.mygit.create_worktree_for_issue.assert_not_called()
        prompt = claudeck.new_session.call_args[0][0]
        assert "EPM-42" in prompt and "git branch -m bs/epm-42/fix-the-thing" in prompt
        assert claudeck.new_session.call_args[1] == {"directory": "/repo", "name": "EPM-42", "worktree": True, "focus": True}
        self.ui.error.assert_not_called()

    def test_outside_claudeck_keeps_the_old_behaviour(self, monkeypatch):
        claudeck = Mock()
        claudeck.can_start_sessions.return_value = False
        run = Mock()
        monkeypatch.setattr("libs.commands.worktree_command.subprocess.run", run)
        WorktreeCommand(claudeck).execute(self.ui, Mock(), Mock(), mygit=self.mygit)

        claudeck.new_session.assert_not_called()
        self.mygit.create_worktree_for_issue.assert_called_once_with("EPM-42", "Fix the thing")
        run.assert_called_once_with(["claude"], cwd="/repo-worktrees/x")

    def test_claudeck_refusal_is_shown_as_an_error(self):
        claudeck = Mock()
        claudeck.can_start_sessions.return_value = True
        claudeck.new_session.side_effect = Exception("Claudeck could not start a session: off")
        WorktreeCommand(claudeck).execute(self.ui, Mock(), Mock(), mygit=self.mygit)
        self.ui.error.assert_called_once()
