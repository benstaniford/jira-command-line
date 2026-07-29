import pytest
from libs.JiraXrayIssue import MyTestDefinitions


class TestIsExistingTestPlan:
    @pytest.mark.parametrize("test_plan", ["EPM-123", "AIDR-9", "HELP-45678"])
    def test_issue_keys_are_existing_plans(self, test_plan):
        definitions = MyTestDefinitions("/Some/Folder", test_plan)
        assert definitions.is_existing_test_plan() is True

    @pytest.mark.parametrize("test_plan", ["My plan name", "epm-123", "EPM123", "-123", None])
    def test_non_keys_are_new_plans(self, test_plan):
        definitions = MyTestDefinitions("/Some/Folder", test_plan)
        assert definitions.is_existing_test_plan() is False
