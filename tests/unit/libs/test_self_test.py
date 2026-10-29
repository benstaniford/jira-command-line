import io
from unittest.mock import Mock

import pytest

from libs.SelfTest import SelfTest, HeadlessTableView, CheckSkipped, CheckWarning, UNTESTED_COMMANDS
from libs.commands.assign_command import AssignCommand
from libs.commands.status_command import StatusCommand


def make_issue(key="TEST-1", summary="A summary", status="To Do", subtasks=()):
    issue = Mock()
    issue.key = key
    issue.fields.summary = summary
    issue.fields.status.name = status
    issue.fields.subtasks = list(subtasks)
    return issue


@pytest.fixture
def self_test():
    jira = Mock()
    jira.team_name = "TestTeam"
    jira.get_optional_fields.return_value = {}
    return SelfTest(jira, Mock(), None, {}, ("owner", "repo"), out=io.StringIO())


class TestHeadlessTableView:
    def test_confirmations_are_always_refused(self):
        ui = HeadlessTableView()
        assert ui.prompt_get_character("Are you sure? (y/n)") == "n"

    def test_subrows_hidden_until_toggled(self):
        ui = HeadlessTableView()
        ui.add_row(["TEST-1"], "parent", [(["TEST-2"], "child")])
        assert [data for _, data, _ in ui.active_rows()] == ["parent"]
        ui.toggle_subrows()
        assert [data for _, data, _ in ui.active_rows()] == ["parent", "child"]

    def test_choice_list_answers_from_script(self):
        ui = HeadlessTableView()
        ui.answers = ["Board B"]
        assert ui.prompt_with_choice_list("Select board", ["Board A", "Board B"]) == (1, "Board B")
        assert ui.prompt_with_choice_list("Select board", ["Board A"]) == (None, "")

    def test_issue_prompt_uses_cursor_only(self):
        ui = HeadlessTableView()
        ui.add_row(["TEST-1"], "issue")
        assert ui.prompt_get_issue() == ["", None, None]
        ui.cursor = 0
        assert ui.prompt_get_issue()[2] == "issue"

    @pytest.mark.parametrize("command", [AssignCommand(), StatusCommand()])
    def test_writing_commands_stop_at_confirmation(self, command):
        ui = HeadlessTableView()
        ui.add_row(["TEST-1"], make_issue())
        ui.cursor = 0
        ui.answers = ["Alice"]
        jira = Mock()
        jira.get_assignable_users.return_value = [{"displayName": "Alice", "accountId": "a1"}]
        jira.get_statuses.return_value = ["Alice"]
        command.execute(ui=ui, view=Mock(), jira=jira)
        jira.assign_to_account_id.assert_not_called()
        jira.change_status.assert_not_called()


class TestSelfTestChecks:
    @pytest.mark.parametrize("raised, status", [
        (None, "PASS"),
        (CheckSkipped("no sprint"), "SKIP"),
        (CheckWarning("odd"), "WARN"),
        (AssertionError("broken"), "FAIL"),
        (RuntimeError("broken"), "FAIL"),
    ])
    def test_check_status(self, self_test, raised, status):
        def fn():
            if raised:
                raise raised
            return "detail"
        self_test.check("thing", fn)
        assert self_test.counts[status] == 1
        assert f"{status}  thing" in self_test.out.getvalue()

    def test_command_errors_fail_the_check(self, self_test):
        self_test.jira.get_backlog_issues.side_effect = Exception("Jira is down")
        with pytest.raises(RuntimeError, match="Jira is down"):
            self_test.run_command("l")

    def test_check_table_records_issues_and_rejects_non_text_cells(self, self_test):
        self_test.view.mode = 2
        self_test.ui.add_header(["Key", "Summary", "Status"])
        self_test.ui.add_row(["TEST-1", "A summary", "To Do"], make_issue(), [(["TEST-2", "Sub", "Done"], make_issue("TEST-2"))])
        assert self_test.check_table(2) == "1 issues, 1 sub-tasks"
        assert list(self_test.seen) == ["TEST-1"]

        self_test.ui.add_row(["TEST-3", None, "To Do"], make_issue("TEST-3"))
        with pytest.raises(AssertionError, match="non-text"):
            self_test.check_table(2)

    def test_uncovered_commands_warn(self, self_test):
        self_test.covered = set(self_test.registry.commands) - {"l"}
        with pytest.raises(CheckWarning, match="l"):
            self_test.check_coverage()
        self_test.covered.add("l")
        assert "commands" in self_test.check_coverage()

    def test_untested_commands_exist(self, self_test):
        assert set(UNTESTED_COMMANDS) <= set(self_test.registry.commands)
