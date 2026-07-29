import pytest
from unittest.mock import Mock, patch
from libs.commands.assign_command import AssignCommand


@pytest.fixture
def mock_issue():
    issue = Mock()
    issue.key = "TEST-123"
    return issue


@pytest.fixture
def assign_setup(mock_ui, mock_jira_api, mock_issue):
    """Common happy-path wiring: issue 1 selected, one discoverable user"""
    mock_ui.prompt_get_string.return_value = "1"
    mock_ui.get_row.return_value = [0, mock_issue]
    mock_jira_api.get_assignable_users.return_value = [
        {"displayName": "Carol Danvers", "accountId": "acc-123"}
    ]


class TestAssignCommand:
    def test_shortcut_property(self):
        """Test that AssignCommand has correct shortcut"""
        command = AssignCommand()
        assert command.shortcut == "a"

    def test_description_property(self):
        """Test that AssignCommand has correct description"""
        command = AssignCommand()
        assert command.description == "assign"

    def test_execute_assigns_discovered_user(self, mock_ui, mock_view, mock_jira_api, mock_issue, assign_setup):
        """Test assigning to a user discovered from Jira"""
        mock_ui.prompt_fuzzy_find.return_value = "Carol Danvers"

        command = AssignCommand()
        result = command.execute(ui=mock_ui, view=mock_view, jira=mock_jira_api)

        mock_jira_api.assign_to_account_id.assert_called_once_with(mock_issue, "acc-123")
        mock_ui.prompt.assert_called_with("Assigned TEST-123 to Carol Danvers...")
        mock_view.refresh.assert_called_once()
        assert result is None

    def test_execute_unassign(self, mock_ui, mock_view, mock_jira_api, mock_issue, assign_setup):
        """Test that choosing Unassigned assigns to a null accountId"""
        mock_ui.prompt_fuzzy_find.return_value = "Unassigned"

        command = AssignCommand()
        command.execute(ui=mock_ui, view=mock_view, jira=mock_jira_api)

        mock_jira_api.assign_to_account_id.assert_called_once_with(mock_issue, None)
        mock_view.refresh.assert_called_once()

    def test_execute_choices_include_unassigned_first(self, mock_ui, mock_view, mock_jira_api, assign_setup):
        """Test that the fuzzy find choices start with Unassigned"""
        mock_ui.prompt_fuzzy_find.return_value = ""

        command = AssignCommand()
        command.execute(ui=mock_ui, view=mock_view, jira=mock_jira_api)

        choices = mock_ui.prompt_fuzzy_find.call_args[0][1]
        assert choices == ["Unassigned", "Carol Danvers"]

    def test_execute_no_users_found(self, mock_ui, mock_view, mock_jira_api, mock_issue):
        """Test that an empty discovered user list aborts with a message"""
        mock_ui.prompt_get_string.return_value = "1"
        mock_ui.get_row.return_value = [0, mock_issue]
        mock_jira_api.get_assignable_users.return_value = []

        command = AssignCommand()
        command.execute(ui=mock_ui, view=mock_view, jira=mock_jira_api)

        mock_ui.prompt.assert_called_with("No assignable users found for this project...")
        mock_ui.prompt_fuzzy_find.assert_not_called()
        mock_jira_api.assign_to_account_id.assert_not_called()
        mock_view.refresh.assert_not_called()

    def test_execute_escape_cancels(self, mock_ui, mock_view, mock_jira_api, assign_setup):
        """Test that escaping the fuzzy find prompt cancels the assignment"""
        mock_ui.prompt_fuzzy_find.return_value = ""

        command = AssignCommand()
        command.execute(ui=mock_ui, view=mock_view, jira=mock_jira_api)

        mock_jira_api.assign_to_account_id.assert_not_called()
        mock_view.refresh.assert_not_called()

    def test_execute_confirm_no_aborts(self, mock_ui, mock_view, mock_jira_api, assign_setup):
        """Test that answering no to the confirmation aborts the assignment"""
        mock_ui.prompt_fuzzy_find.return_value = "Carol Danvers"
        mock_ui.prompt_get_character.return_value = "n"

        command = AssignCommand()
        command.execute(ui=mock_ui, view=mock_view, jira=mock_jira_api)

        mock_jira_api.assign_to_account_id.assert_not_called()
        mock_view.refresh.assert_not_called()

    def test_execute_non_numeric_selection_ignored(self, mock_ui, mock_view, mock_jira_api):
        """Test that non-numeric selections are ignored"""
        mock_ui.prompt_get_string.return_value = "abc"

        command = AssignCommand()
        command.execute(ui=mock_ui, view=mock_view, jira=mock_jira_api)

        mock_jira_api.get_assignable_users.assert_not_called()
        mock_jira_api.assign_to_account_id.assert_not_called()
        mock_view.refresh.assert_not_called()

    def test_execute_handles_exceptions(self, mock_ui, mock_view, mock_jira_api):
        """Test that exceptions are handled properly"""
        mock_ui.prompt_get_string.side_effect = Exception("Test error")

        command = AssignCommand()
        result = command.execute(ui=mock_ui, view=mock_view, jira=mock_jira_api)

        mock_ui.error.assert_called_once_with("Assign to user", mock_ui.prompt_get_string.side_effect)
        assert result is None

    def test_execute_handles_jira_api_exceptions(self, mock_ui, mock_view, mock_jira_api, assign_setup):
        """Test handling of Jira API exceptions during assignment"""
        mock_ui.prompt_fuzzy_find.return_value = "Carol Danvers"
        mock_jira_api.assign_to_account_id.side_effect = Exception("Jira API error")

        command = AssignCommand()
        result = command.execute(ui=mock_ui, view=mock_view, jira=mock_jira_api)

        mock_ui.error.assert_called_once()
        mock_view.refresh.assert_not_called()
        assert result is None
