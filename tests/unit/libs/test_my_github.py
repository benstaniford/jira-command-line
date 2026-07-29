import pytest
from unittest.mock import Mock, patch
from libs.MyGithub import MyGithub


@pytest.fixture
def github_config():
    return {
        "username": "tuser",
        "login": "testuser",
        "token": "test-github-token",
        "repo_owner": "test-org",
        "repo_name": "test-repo"
    }


class TestMyGithub:
    @patch('libs.MyGithub.Github')
    def test_init_uses_config_repo_by_default(self, mock_github_class, github_config):
        """Test that repo owner/name come from config when no override is given"""
        github = MyGithub(github_config)

        assert github.repo_owner == "test-org"
        assert github.repo_name == "test-repo"
        assert github.pull_endpoint == "https://api.github.com/repos/test-org/test-repo/pulls"
        assert github.pull_query == "https://api.github.com/search/issues?q=repo:test-org/test-repo"

    @patch('libs.MyGithub.Github')
    def test_init_repo_override_takes_precedence(self, mock_github_class, github_config):
        """Test that a repo tuple overrides the config repo"""
        github = MyGithub(github_config, repo=("BeyondTrust", "pathfinder-agent"))

        assert github.repo_owner == "BeyondTrust"
        assert github.repo_name == "pathfinder-agent"
        assert github.pull_endpoint == "https://api.github.com/repos/BeyondTrust/pathfinder-agent/pulls"
        assert github.pull_query == "https://api.github.com/search/issues?q=repo:BeyondTrust/pathfinder-agent"

    @patch('libs.MyGithub.Github')
    def test_create_pull_targets_override_repo(self, mock_github_class, github_config):
        """Test that create_pull uses the overridden repo"""
        mock_github = Mock()
        mock_github_class.return_value = mock_github

        github = MyGithub(github_config, repo=("BeyondTrust", "pathfinder-agent"))
        github.create_pull(title="t", body="b", head="h", base="main")

        mock_github.get_repo.assert_called_once_with("BeyondTrust/pathfinder-agent")
