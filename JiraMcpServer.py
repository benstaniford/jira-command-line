#!/usr/bin/env python3
"""
MCP Server for Jira Integration

This server provides tools to interact with Jira using the existing MyJira library.
It exposes various Jira operations as MCP tools that can be used by MCP clients.
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
from libs.MyJira import MyJira
from libs.MyJiraConfig import MyJiraConfig

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-jira-server")

class JiraMCPServer:
    def __init__(self):
        self.server = Server("jira-mcp-server")
        self.jira: Optional[MyJira] = None
        self.config: Optional[Dict[str, Any]] = None
        
        # Register tools
        self._register_tools()
        
    def _register_tools(self):
        """Register all available tools with the MCP server."""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List available Jira tools."""
            return [
                Tool(
                    name="get_issue",
                    description="Get a Jira issue by its key",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "key": {
                                "type": "string",
                                "description": "The Jira issue key (e.g., 'EPM-123')"
                            }
                        },
                        "required": ["key"]
                    }
                ),
                Tool(
                    name="search_issues",
                    description="Search for Jira issues using JQL (Jira Query Language)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "jql": {
                                "type": "string",
                                "description": "JQL query string"
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "Maximum number of results to return",
                                "default": 50
                            }
                        },
                        "required": ["jql"]
                    }
                ),
                Tool(
                    name="get_sprint_issues",
                    description="Get issues from the current active sprint",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "team": {
                                "type": "string",
                                "description": "Team name (optional, uses default if not specified)"
                            }
                        },
                        "required": []
                    }
                ),
                Tool(
                    name="get_backlog_issues",
                    description="Get issues from the team backlog",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "team": {
                                "type": "string",
                                "description": "Team name (optional, uses default if not specified)"
                            }
                        },
                        "required": []
                    }
                ),
                Tool(
                    name="create_issue",
                    description="Create a new Jira issue",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "Issue summary/title"
                            },
                            "description": {
                                "type": "string",
                                "description": "Issue description"
                            },
                            "issue_type": {
                                "type": "string",
                                "description": "Issue type (Story, Task, Bug, etc.)",
                                "default": "Story"
                            },
                            "in_sprint": {
                                "type": "boolean",
                                "description": "Whether to create the issue in the current sprint",
                                "default": False
                            }
                        },
                        "required": ["title", "description"]
                    }
                ),
                Tool(
                    name="update_issue",
                    description="Update a Jira issue (assign, set story points, change status)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "key": {
                                "type": "string",
                                "description": "The Jira issue key"
                            },
                            "assignee": {
                                "type": "string",
                                "description": "User shortname to assign to (optional)"
                            },
                            "story_points": {
                                "type": "number",
                                "description": "Story points to set (optional)"
                            },
                            "status": {
                                "type": "string",
                                "description": "Status to transition to (optional)"
                            }
                        },
                        "required": ["key"]
                    }
                ),
                Tool(
                    name="add_comment",
                    description="Add a comment to a Jira issue",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "key": {
                                "type": "string",
                                "description": "The Jira issue key"
                            },
                            "comment": {
                                "type": "string",
                                "description": "Comment text to add"
                            }
                        },
                        "required": ["key", "comment"]
                    }
                ),
                Tool(
                    name="get_teams",
                    description="Get list of available teams",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                ),
                Tool(
                    name="set_team",
                    description="Switch to a different team context",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "team": {
                                "type": "string",
                                "description": "Team name to switch to"
                            }
                        },
                        "required": ["team"]
                    }
                )
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> Sequence[TextContent]:
            """Handle tool calls."""
            try:
                # Initialize Jira connection if not already done
                await self._ensure_jira_initialized()
                
                if name == "get_issue":
                    return await self._get_issue(arguments)
                elif name == "search_issues":
                    return await self._search_issues(arguments)
                elif name == "get_sprint_issues":
                    return await self._get_sprint_issues(arguments)
                elif name == "get_backlog_issues":
                    return await self._get_backlog_issues(arguments)
                elif name == "create_issue":
                    return await self._create_issue(arguments)
                elif name == "update_issue":
                    return await self._update_issue(arguments)
                elif name == "add_comment":
                    return await self._add_comment(arguments)
                elif name == "get_teams":
                    return await self._get_teams(arguments)
                elif name == "set_team":
                    return await self._set_team(arguments)
                else:
                    raise ValueError(f"Unknown tool: {name}")
                    
            except Exception as e:
                logger.error(f"Error in tool {name}: {e}")
                return [TextContent(type="text", text=f"Error: {str(e)}")]

    async def _ensure_jira_initialized(self):
        """Ensure Jira connection is initialized."""
        if self.jira is None:
            config_manager = MyJiraConfig()
            if not config_manager.exists():
                raise ValueError("Jira config file not found. Please run the main jira application first to generate configuration.")
            
            self.config = config_manager.load()
            jira_config = self.config["jira"]
            self.jira = MyJira(jira_config)
            logger.info(f"Initialized Jira connection for {jira_config['url']}")

    async def _get_issue(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Get a single Jira issue by key."""
        key = arguments["key"]
        issue = self.jira.get_issue_by_key(key)
        
        # Get formatted issue details
        issue_body = self.jira.get_body(issue, include_comments=True, format_as_html=False)
        
        result = {
            "key": issue.key,
            "summary": issue.fields.summary,
            "status": str(issue.fields.status),
            "assignee": self.jira.get_assignee(issue),
            "issue_type": str(issue.fields.issuetype),
            "story_points": self.jira.get_story_points(issue),
            "sprint": self.jira.get_sprint_name(issue),
            "created": str(issue.fields.created),
            "updated": str(issue.fields.updated),
            "details": issue_body
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _search_issues(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Search for issues using JQL."""
        jql = arguments["jql"]
        max_results = arguments.get("max_results", 50)
        
        issues = self.jira.search_issues(jql)
        
        # Limit results
        if len(issues) > max_results:
            issues = issues[:max_results]
        
        results = []
        for issue in issues:
            results.append({
                "key": issue.key,
                "summary": issue.fields.summary,
                "status": str(issue.fields.status),
                "assignee": self.jira.get_assignee(issue),
                "issue_type": str(issue.fields.issuetype),
                "story_points": self.jira.get_story_points(issue),
                "sprint": self.jira.get_sprint_name(issue)
            })
        
        return [TextContent(type="text", text=json.dumps({
            "total_found": len(issues),
            "issues": results
        }, indent=2))]

    async def _get_sprint_issues(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Get issues from current sprint."""
        team = arguments.get("team")
        if team:
            self.jira.set_team(team)
        
        issues = self.jira.get_sprint_issues()
        
        results = []
        for issue in issues:
            results.append({
                "key": issue.key,
                "summary": issue.fields.summary,
                "status": str(issue.fields.status),
                "assignee": self.jira.get_assignee(issue),
                "issue_type": str(issue.fields.issuetype),
                "story_points": self.jira.get_story_points(issue)
            })
        
        return [TextContent(type="text", text=json.dumps({
            "team": self.jira.team_name,
            "sprint_issues": results
        }, indent=2))]

    async def _get_backlog_issues(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Get issues from team backlog."""
        team = arguments.get("team")
        if team:
            self.jira.set_team(team)
        
        issues = self.jira.get_backlog_issues()
        
        results = []
        for issue in issues:
            results.append({
                "key": issue.key,
                "summary": issue.fields.summary,
                "status": str(issue.fields.status),
                "assignee": self.jira.get_assignee(issue),
                "issue_type": str(issue.fields.issuetype),
                "story_points": self.jira.get_story_points(issue)
            })
        
        return [TextContent(type="text", text=json.dumps({
            "team": self.jira.team_name,
            "backlog_issues": results
        }, indent=2))]

    async def _create_issue(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Create a new Jira issue."""
        title = arguments["title"]
        description = arguments["description"]
        issue_type = arguments.get("issue_type", "Story")
        in_sprint = arguments.get("in_sprint", False)
        
        if in_sprint:
            new_issue = self.jira.create_sprint_issue(title, description, issue_type)
        else:
            new_issue = self.jira.create_backlog_issue(title, description, issue_type)
        
        result = {
            "key": new_issue.key,
            "summary": new_issue.fields.summary,
            "issue_type": str(new_issue.fields.issuetype),
            "status": str(new_issue.fields.status),
            "url": new_issue.permalink()
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _update_issue(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Update a Jira issue."""
        key = arguments["key"]
        issue = self.jira.get_issue_by_key(key)
        
        updates = []
        
        # Handle assignment
        if "assignee" in arguments:
            assignee = arguments["assignee"]
            if assignee.lower() == "me":
                self.jira.assign_to_me(issue)
                updates.append(f"Assigned to {self.jira.fullname}")
            else:
                self.jira.assign_to(issue, assignee)
                updates.append(f"Assigned to {assignee}")
        
        # Handle story points
        if "story_points" in arguments:
            points = arguments["story_points"]
            self.jira.set_story_points(issue, points)
            updates.append(f"Set story points to {points}")
        
        # Handle status change
        if "status" in arguments:
            status = arguments["status"]
            self.jira.change_status(issue, status)
            updates.append(f"Changed status to {status}")
        
        result = {
            "key": key,
            "updates": updates,
            "message": f"Successfully updated {key}"
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _add_comment(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Add a comment to a Jira issue."""
        key = arguments["key"]
        comment = arguments["comment"]
        
        issue = self.jira.get_issue_by_key(key)
        self.jira.add_comment(issue, comment)
        
        result = {
            "key": key,
            "comment_added": comment,
            "message": f"Successfully added comment to {key}"
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _get_teams(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Get list of available teams."""
        teams = self.jira.get_teams()
        
        result = {
            "current_team": self.jira.team_name,
            "available_teams": teams
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _set_team(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Set the current team context."""
        team = arguments["team"]
        self.jira.set_team(team)
        
        result = {
            "previous_team": self.jira.team_name if hasattr(self, '_previous_team') else "unknown",
            "current_team": team,
            "message": f"Successfully switched to team {team}"
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

async def main():
    """Main entry point for the MCP server."""
    logger.info("Starting Jira MCP Server...")
    jira_server = JiraMCPServer()
    logger.info("Jira MCP Server initialized with tools")
    
    # Run the server using stdio transport
    async with stdio_server() as (read_stream, write_stream):
        await jira_server.server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="jira-mcp-server",
                server_version="1.0.0",
                capabilities=jira_server.server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())