import subprocess
from unittest.mock import patch

from libs.BranchNamer import BranchNamer


LONG_SUMMARY = ("DefendpointService crashes intermittently when a policy "
                "containing a large number of application rules is applied")


def _completed(stdout, returncode=0):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


class TestConfiguration:
    def test_defaults_when_config_empty(self):
        namer = BranchNamer({})

        assert namer.model == "haiku"
        assert namer.max_length == 40
        assert namer.enabled()

    def test_config_overrides_defaults(self):
        namer = BranchNamer({"branch_name_model": "sonnet", "max_branch_summary_length": 10})

        assert namer.model == "sonnet"
        assert namer.max_length == 10

    def test_blank_model_disables_shortening(self):
        namer = BranchNamer({"branch_name_model": ""})

        assert not namer.enabled()

    @patch('libs.BranchNamer.subprocess.run')
    def test_disabled_namer_never_calls_claude(self, mock_run):
        namer = BranchNamer({"branch_name_model": ""})

        assert namer.shorten(LONG_SUMMARY) == LONG_SUMMARY
        mock_run.assert_not_called()


class TestShorten:
    @patch('libs.BranchNamer.subprocess.run')
    def test_short_summary_is_returned_untouched(self, mock_run):
        namer = BranchNamer({})

        assert namer.shorten("Fix the crash") == "Fix the crash"
        mock_run.assert_not_called()

    @patch('libs.BranchNamer.shutil.which', return_value="/usr/bin/claude")
    @patch('libs.BranchNamer.subprocess.run')
    def test_long_summary_is_shortened_by_claude(self, mock_run, mock_which):
        mock_run.return_value = _completed("defendpoint-crash-large-policy\n")
        namer = BranchNamer({})

        assert namer.shorten(LONG_SUMMARY) == "defendpoint crash large policy"

        command = mock_run.call_args[0][0]
        assert command[:5] == ["claude", "-p", "--model", "haiku", "--strict-mcp-config"]
        assert LONG_SUMMARY in command[5]

    @patch('libs.BranchNamer.shutil.which', return_value="/usr/bin/claude")
    @patch('libs.BranchNamer.subprocess.run')
    def test_configured_model_is_passed_to_claude(self, mock_run, mock_which):
        mock_run.return_value = _completed("short-name\n")
        namer = BranchNamer({"branch_name_model": "sonnet"})

        namer.shorten(LONG_SUMMARY)

        assert mock_run.call_args[0][0][3] == "sonnet"


class TestFallbacks:
    @patch('libs.BranchNamer.shutil.which', return_value=None)
    @patch('libs.BranchNamer.subprocess.run')
    def test_missing_claude_falls_back_to_full_summary(self, mock_run, mock_which):
        namer = BranchNamer({})

        assert namer.shorten(LONG_SUMMARY) == LONG_SUMMARY
        mock_run.assert_not_called()

    @patch('libs.BranchNamer.shutil.which', return_value="/usr/bin/claude")
    @patch('libs.BranchNamer.subprocess.run', side_effect=subprocess.TimeoutExpired("claude", 60))
    def test_timeout_falls_back_to_full_summary(self, mock_run, mock_which):
        assert BranchNamer({}).shorten(LONG_SUMMARY) == LONG_SUMMARY

    @patch('libs.BranchNamer.shutil.which', return_value="/usr/bin/claude")
    @patch('libs.BranchNamer.subprocess.run', side_effect=OSError("boom"))
    def test_oserror_falls_back_to_full_summary(self, mock_run, mock_which):
        assert BranchNamer({}).shorten(LONG_SUMMARY) == LONG_SUMMARY

    @patch('libs.BranchNamer.shutil.which', return_value="/usr/bin/claude")
    @patch('libs.BranchNamer.subprocess.run')
    def test_non_zero_exit_falls_back_to_full_summary(self, mock_run, mock_which):
        mock_run.return_value = _completed("whatever", returncode=1)

        assert BranchNamer({}).shorten(LONG_SUMMARY) == LONG_SUMMARY

    @patch('libs.BranchNamer.shutil.which', return_value="/usr/bin/claude")
    @patch('libs.BranchNamer.subprocess.run')
    def test_chatty_reply_falls_back_to_full_summary(self, mock_run, mock_which):
        mock_run.return_value = _completed(
            "Sure! Here is a branch name:\n\ndefendpoint-crash\n")

        assert BranchNamer({}).shorten(LONG_SUMMARY) == LONG_SUMMARY

    @patch('libs.BranchNamer.shutil.which', return_value="/usr/bin/claude")
    @patch('libs.BranchNamer.subprocess.run')
    def test_reply_with_illegal_characters_falls_back(self, mock_run, mock_which):
        mock_run.return_value = _completed("feature/defendpoint crash!\n")

        assert BranchNamer({}).shorten(LONG_SUMMARY) == LONG_SUMMARY

    @patch('libs.BranchNamer.shutil.which', return_value="/usr/bin/claude")
    @patch('libs.BranchNamer.subprocess.run')
    def test_reply_that_is_still_too_long_falls_back(self, mock_run, mock_which):
        mock_run.return_value = _completed("a" * 41 + "\n")

        assert BranchNamer({}).shorten(LONG_SUMMARY) == LONG_SUMMARY

    @patch('libs.BranchNamer.shutil.which', return_value="/usr/bin/claude")
    @patch('libs.BranchNamer.subprocess.run')
    def test_empty_reply_falls_back(self, mock_run, mock_which):
        mock_run.return_value = _completed("\n")

        assert BranchNamer({}).shorten(LONG_SUMMARY) == LONG_SUMMARY

    @patch('libs.BranchNamer.shutil.which', return_value="/usr/bin/claude")
    @patch('libs.BranchNamer.subprocess.run')
    def test_quoted_and_uppercased_reply_is_cleaned_up(self, mock_run, mock_which):
        mock_run.return_value = _completed('"Defendpoint-Crash-Large-Policy"\n')

        assert BranchNamer({}).shorten(LONG_SUMMARY) == "defendpoint crash large policy"
