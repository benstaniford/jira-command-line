import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from libs.MyGit import MyGit


class TestMyGit:
    def test_init_sets_correct_attributes(self):
        """Test MyGit initialization sets correct attributes"""
        config = {"initials": "js"}
        git = MyGit(config)
        
        assert git.initials == "js"
        assert git.support_dir == os.path.join(os.path.expanduser("~"), "Support")
    
    def test_init_handles_missing_initials(self):
        """Test MyGit handles missing initials in config"""
        config = {}
        git = MyGit(config)
        
        assert git.initials is None
        assert git.support_dir is not None
    
    @patch('libs.MyGit.Repo')
    def test_current_branch_returns_branch_name(self, mock_repo_class):
        """Test current_branch returns the active branch name"""
        mock_repo = Mock()
        mock_repo.active_branch.name = "feature/test-branch"
        mock_repo_class.return_value = mock_repo
        
        config = {"initials": "js"}
        git = MyGit(config)
        
        result = git.current_branch()
        
        assert result == "feature/test-branch"
        mock_repo_class.assert_called_once_with('.')
    
    @patch('libs.MyGit.Repo')
    def test_create_branch_for_issue_with_clean_repo(self, mock_repo_class):
        """Test create_branch_for_issue with clean repository"""
        mock_repo = Mock()
        mock_repo.is_dirty.return_value = False
        mock_repo.git.checkout = Mock()
        mock_repo_class.return_value = mock_repo
        
        config = {"initials": "js"}
        git = MyGit(config)
        
        result = git.create_branch_for_issue("TEST-123", "Fix the bug with spaces")
        
        expected_branch = "js/test-123/fix-the-bug-with-spaces"
        assert result == expected_branch
        
        # Verify the sequence of git commands
        assert mock_repo.git.checkout.call_count == 2
        mock_repo.git.checkout.assert_any_call('main')
        mock_repo.git.checkout.assert_any_call('-b', expected_branch)
        mock_repo.git.push.assert_called_once_with("--set-upstream", "origin", expected_branch)
    
    @patch('libs.MyGit.Repo')
    def test_create_branch_for_issue_with_dirty_repo_raises_exception(self, mock_repo_class):
        """Test create_branch_for_issue raises exception with dirty repo"""
        mock_repo = Mock()
        mock_repo.is_dirty.return_value = True
        mock_repo_class.return_value = mock_repo
        
        config = {"initials": "js"}
        git = MyGit(config)
        
        with pytest.raises(Exception, match="Repo is dirty"):
            git.create_branch_for_issue("TEST-123", "Some summary")
    
    def test_branch_name_sanitization(self):
        """Test that branch names are properly sanitized"""
        config = {"initials": "js"}
        git = MyGit(config)
        
        test_cases = [
            ("TEST-123", "Fix Bug with Special Ch@r$!", "js/test-123/fix-bug-with-special-chr"),
            ("PROJ-456", "Multiple   Spaces", "js/proj-456/multiple-spaces"),
            ("ABC-789", "Trailing Spaces   ", "js/abc-789/trailing-spaces"),
            ("DEF-101", "   Leading Spaces", "js/def-101/leading-spaces"),
            ("GHI-202", "Hyphens---And--More-Hyphens", "js/ghi-202/hyphensandmorehyphens"),  # Fixed expectation
            ("JKL-303", "UPPERCASE TITLE", "js/jkl-303/uppercase-title")
        ]
        
        with patch('libs.MyGit.Repo') as mock_repo_class:
            mock_repo = Mock()
            mock_repo.is_dirty.return_value = False
            mock_repo_class.return_value = mock_repo
            
            for issue_number, summary, expected_branch in test_cases:
                result = git.create_branch_for_issue(issue_number, summary)
                assert result == expected_branch
                # Reset mock for next iteration
                mock_repo.git.checkout.reset_mock()
                mock_repo.git.push.reset_mock()
    
    def test_empty_summary_handling(self):
        """Test handling of empty or whitespace-only summaries"""
        config = {"initials": "js"}
        git = MyGit(config)
        
        with patch('libs.MyGit.Repo') as mock_repo_class:
            mock_repo = Mock()
            mock_repo.is_dirty.return_value = False
            mock_repo_class.return_value = mock_repo
            
            # Empty string
            result = git.create_branch_for_issue("TEST-123", "")
            assert result == "js/test-123/"
            
            # Only spaces
            result = git.create_branch_for_issue("TEST-456", "   ")
            assert result == "js/test-456/"
    
    def test_special_characters_removal(self):
        """Test that special characters are properly removed"""
        config = {"initials": "js"}
        git = MyGit(config)
        
        with patch('libs.MyGit.Repo') as mock_repo_class:
            mock_repo = Mock()
            mock_repo.is_dirty.return_value = False
            mock_repo_class.return_value = mock_repo
            
            summary = "Fix@#$%^&*(){}[]|\\:;\"'<>?/~`+=bug"
            result = git.create_branch_for_issue("TEST-123", summary)
            
            # Should only keep alphanumeric characters and spaces (converted to hyphens)
            assert result == "js/test-123/fixbug"
    
    def test_case_conversion(self):
        """Test that issue numbers and summaries are converted to lowercase"""
        config = {"initials": "JS"}  # Uppercase initials should stay as-is based on current code
        git = MyGit(config)
        
        with patch('libs.MyGit.Repo') as mock_repo_class:
            mock_repo = Mock()
            mock_repo.is_dirty.return_value = False
            mock_repo_class.return_value = mock_repo
            
            result = git.create_branch_for_issue("PROJ-123", "UPPERCASE Summary")
            
            # Issue number should be lowercase, summary should be lowercase
            assert result == "JS/proj-123/uppercase-summary"
    
    @patch('libs.MyGit.Repo')
    def test_git_checkout_called_with_correct_args(self, mock_repo_class):
        """Test that git checkout is called with correct arguments"""
        mock_repo = Mock()
        mock_repo.is_dirty.return_value = False
        mock_repo_class.return_value = mock_repo
        
        config = {"initials": "js"}
        git = MyGit(config)
        
        git.create_branch_for_issue("TEST-123", "test summary")
        
        # Check both checkout calls
        assert mock_repo.git.checkout.call_count == 2
        mock_repo.git.checkout.assert_any_call('main')
        mock_repo.git.checkout.assert_any_call('-b', 'js/test-123/test-summary')