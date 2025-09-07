#!/usr/bin/env python3
"""
MCP Server for GitHub Integration

This server provides tools to interact with GitHub using the existing MyGithub library.
It exposes various GitHub operations as MCP tools that can be used by MCP clients.
"""

import asyncio
import json
import logging
import sys
from typing import Any, Dict, List, Optional, Sequence

# MCP imports
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    LoggingLevel
)

# Local imports
from libs.MyGithub import MyGithub
from libs.MyJiraConfig import MyJiraConfig

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-github-server")

class GithubMCPServer:
    def __init__(self):
        self.server = Server("github-mcp-server")
        self.github: Optional[MyGithub] = None
        self.config: Optional[Dict[str, Any]] = None
        
        # Register tools
        self._register_tools()
        
    def _register_tools(self):
        """Register all available GitHub tools with the MCP server."""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List available GitHub tools."""
            return [
                Tool(
                    name="get_prs",
                    description="Get all pull requests for the repository",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                ),
                Tool(
                    name="get_prs_query",
                    description="Search for pull requests using a query",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query for PRs (e.g., 'assignee:username', 'is:open')"
                            }
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="get_pr_description",
                    description="Get the description/body of a pull request by PR number",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "pr_number": {
                                "type": "integer",
                                "description": "The pull request number"
                            }
                        },
                        "required": ["pr_number"]
                    }
                ),
                Tool(
                    name="update_pr_description",
                    description="Update the description/body of a pull request",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "pr_number": {
                                "type": "integer",
                                "description": "The pull request number"
                            },
                            "new_description": {
                                "type": "string",
                                "description": "The new description/body for the PR"
                            }
                        },
                        "required": ["pr_number", "new_description"]
                    }
                ),
                Tool(
                    name="get_pr_by_number",
                    description="Get full details of a pull request by number",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "pr_number": {
                                "type": "integer",
                                "description": "The pull request number"
                            }
                        },
                        "required": ["pr_number"]
                    }
                ),
                Tool(
                    name="create_pull",
                    description="Create a new pull request",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "Pull request title"
                            },
                            "body": {
                                "type": "string",
                                "description": "Pull request description/body"
                            },
                            "head": {
                                "type": "string",
                                "description": "Head branch (source branch for the PR)"
                            },
                            "base": {
                                "type": "string",
                                "description": "Base branch (target branch for the PR)",
                                "default": "main"
                            }
                        },
                        "required": ["title", "body", "head"]
                    }
                ),
                Tool(
                    name="get_requested_reviewers",
                    description="Get the requested reviewers for a pull request",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "pr": {
                                "type": "object",
                                "description": "Pull request object from get_prs or similar"
                            }
                        },
                        "required": ["pr"]
                    }
                ),
                Tool(
                    name="am_i_reviewer",
                    description="Check if the current user is a requested reviewer for a PR",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "pr": {
                                "type": "object",
                                "description": "Pull request object from get_prs or similar"
                            }
                        },
                        "required": ["pr"]
                    }
                ),
                Tool(
                    name="get_pr_age",
                    description="Get the age of a pull request in days",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "pr": {
                                "type": "object",
                                "description": "Pull request object from get_prs or similar"
                            }
                        },
                        "required": ["pr"]
                    }
                )
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> Sequence[TextContent]:
            """Handle tool calls."""
            try:
                # Initialize GitHub connection if not already done
                await self._ensure_github_initialized()
                
                if name == "get_prs":
                    return await self._get_prs(arguments)
                elif name == "get_prs_query":
                    return await self._get_prs_query(arguments)
                elif name == "get_pr_description":
                    return await self._get_pr_description(arguments)
                elif name == "update_pr_description":
                    return await self._update_pr_description(arguments)
                elif name == "get_pr_by_number":
                    return await self._get_pr_by_number(arguments)
                elif name == "create_pull":
                    return await self._create_pull(arguments)
                elif name == "get_requested_reviewers":
                    return await self._get_requested_reviewers(arguments)
                elif name == "am_i_reviewer":
                    return await self._am_i_reviewer(arguments)
                elif name == "get_pr_age":
                    return await self._get_pr_age(arguments)
                else:
                    raise ValueError(f"Unknown tool: {name}")
                    
            except Exception as e:
                logger.error(f"Error in tool {name}: {e}")
                return [TextContent(type="text", text=f"Error: {str(e)}")]

    async def _ensure_github_initialized(self):
        """Ensure GitHub connection is initialized."""
        if self.github is None:
            config_manager = MyJiraConfig()
            if not config_manager.exists():
                raise ValueError("Config file not found. Please run the main jira application first to generate configuration.")
            
            self.config = config_manager.load()
            
            # Look for GitHub config in the main config
            github_config = self.config.get("github")
            if not github_config:
                raise ValueError("GitHub configuration not found in config file. Please add 'github' section with token, repo_owner, repo_name, username, and login.")
            
            self.github = MyGithub(github_config)
            logger.info(f"Initialized GitHub connection for {github_config.get('repo_owner')}/{github_config.get('repo_name')}")

    async def _get_prs(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Get all pull requests for the repository."""
        prs = self.github.get_prs()
        
        results = []
        for pr in prs:
            results.append({
                "number": pr["number"],
                "title": pr["title"],
                "state": pr["state"],
                "user": pr["user"]["login"],
                "created_at": pr["created_at"],
                "updated_at": pr["updated_at"],
                "html_url": pr["html_url"],
                "head": pr["head"]["ref"],
                "base": pr["base"]["ref"],
                "draft": pr.get("draft", False),
                "assignee": pr["assignee"]["login"] if pr["assignee"] else None
            })
        
        return [TextContent(type="text", text=json.dumps({
            "total": len(results),
            "pull_requests": results
        }, indent=2))]

    async def _get_prs_query(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Search for pull requests using a query."""
        query = arguments["query"]
        prs = self.github.get_prs_query(query)
        
        results = []
        for pr in prs:
            results.append({
                "number": pr["number"],
                "title": pr["title"],
                "state": pr["state"],
                "user": pr["user"]["login"],
                "created_at": pr["created_at"],
                "updated_at": pr["updated_at"],
                "html_url": pr["html_url"],
                "head": pr["head"]["ref"],
                "base": pr["base"]["ref"],
                "draft": pr.get("draft", False),
                "assignee": pr["assignee"]["login"] if pr["assignee"] else None
            })
        
        return [TextContent(type="text", text=json.dumps({
            "query": query,
            "total": len(results),
            "pull_requests": results
        }, indent=2))]

    async def _get_pr_description(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Get the description/body of a pull request."""
        pr_number = arguments["pr_number"]
        description = self.github.get_pr_description(pr_number)
        
        result = {
            "pr_number": pr_number,
            "description": description or ""
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _update_pr_description(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Update the description/body of a pull request."""
        pr_number = arguments["pr_number"]
        new_description = arguments["new_description"]
        
        success = self.github.update_pr_description(pr_number, new_description)
        
        result = {
            "pr_number": pr_number,
            "updated": success,
            "message": f"Successfully updated PR #{pr_number} description"
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _get_pr_by_number(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Get full details of a pull request by number."""
        pr_number = arguments["pr_number"]
        pr = self.github.get_pr_by_number(pr_number)
        
        result = {
            "number": pr.number,
            "title": pr.title,
            "body": pr.body,
            "state": pr.state,
            "user": pr.user.login,
            "created_at": str(pr.created_at),
            "updated_at": str(pr.updated_at),
            "merged": pr.merged,
            "mergeable": pr.mergeable,
            "html_url": pr.html_url,
            "head": {
                "ref": pr.head.ref,
                "sha": pr.head.sha,
                "repo": pr.head.repo.full_name if pr.head.repo else None
            },
            "base": {
                "ref": pr.base.ref,
                "sha": pr.base.sha,
                "repo": pr.base.repo.full_name
            },
            "draft": pr.draft,
            "assignee": pr.assignee.login if pr.assignee else None,
            "assignees": [assignee.login for assignee in pr.assignees],
            "requested_reviewers": [reviewer.login for reviewer in pr.requested_reviewers],
            "labels": [label.name for label in pr.labels],
            "milestone": pr.milestone.title if pr.milestone else None,
            "additions": pr.additions,
            "deletions": pr.deletions,
            "changed_files": pr.changed_files,
            "comments": pr.comments,
            "review_comments": pr.review_comments,
            "commits": pr.commits
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _create_pull(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Create a new pull request."""
        title = arguments["title"]
        body = arguments["body"]
        head = arguments["head"]
        base = arguments.get("base", "main")
        
        pr = self.github.create_pull(title, body, head, base)
        
        result = {
            "number": pr.number,
            "title": pr.title,
            "html_url": pr.html_url,
            "state": pr.state,
            "head": pr.head.ref,
            "base": pr.base.ref,
            "message": f"Successfully created PR #{pr.number}: {pr.title}"
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _get_requested_reviewers(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Get the requested reviewers for a pull request."""
        pr = arguments["pr"]
        reviewers = self.github.get_requested_reviewers(pr)
        
        result = {
            "pr_number": pr.get("number"),
            "requested_reviewers": reviewers
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _am_i_reviewer(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Check if the current user is a requested reviewer for a PR."""
        pr = arguments["pr"]
        is_reviewer = self.github.am_i_reviewer(pr)
        
        result = {
            "pr_number": pr.get("number"),
            "am_i_reviewer": is_reviewer,
            "current_user": self.github.login
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _get_pr_age(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Get the age of a pull request in days."""
        pr = arguments["pr"]
        age_days = self.github.get_pr_agedays(pr)
        
        result = {
            "pr_number": pr.get("number"),
            "age_days": int(age_days),
            "created_at": pr.get("created_at")
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

async def main():
    """Main entry point for the MCP server."""
    logger.info("Starting GitHub MCP Server...")
    github_server = GithubMCPServer()
    logger.info("GitHub MCP Server initialized with tools")
    
    # Run the server using stdio transport
    async with stdio_server() as (read_stream, write_stream):
        await github_server.server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="github-mcp-server",
                server_version="1.0.0",
                capabilities=github_server.server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())