#!/usr/bin/env python3
"""
MCP Server for Xray Integration

This server provides tools to interact with Xray (Jira test management) using the existing
JiraXrayIssue and XrayApi libraries. It exposes various Xray operations as MCP tools
that can be used by MCP clients.
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
from libs.JiraXrayIssue import JiraXrayIssue
from libs.XrayApi import XrayApi

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-xray-server")

class XrayMCPServer:
    def __init__(self):
        self.server = Server("xray-mcp-server")
        self.jira: Optional[MyJira] = None
        self.xray_api: Optional[XrayApi] = None
        self.config: Optional[Dict[str, Any]] = None
        
        # Register tools
        self._register_tools()
        
    def _register_tools(self):
        """Register all available tools with the MCP server."""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List available Xray tools."""
            return [
                Tool(
                    name="get_test_info",
                    description="Get test information for a Jira issue (definitions and linked tests)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "issue_key": {
                                "type": "string",
                                "description": "The Jira issue key (e.g., 'EPM-123')"
                            }
                        },
                        "required": ["issue_key"]
                    }
                ),
                Tool(
                    name="parse_test_definitions",
                    description="Parse test definitions from a Jira issue",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "issue_key": {
                                "type": "string",
                                "description": "The Jira issue key (e.g., 'EPM-123')"
                            }
                        },
                        "required": ["issue_key"]
                    }
                ),
                Tool(
                    name="create_test_template",
                    description="Create a test template in a Jira issue",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "issue_key": {
                                "type": "string",
                                "description": "The Jira issue key (e.g., 'EPM-123')"
                            }
                        },
                        "required": ["issue_key"]
                    }
                ),
                Tool(
                    name="create_test_cases",
                    description="Create Xray test cases from test definitions in a Jira issue",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "issue_key": {
                                "type": "string",
                                "description": "The Jira issue key containing test definitions"
                            }
                        },
                        "required": ["issue_key"]
                    }
                ),
                Tool(
                    name="get_linked_tests",
                    description="Get all test cases linked to a Jira issue",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "issue_key": {
                                "type": "string",
                                "description": "The Jira issue key (e.g., 'EPM-123')"
                            }
                        },
                        "required": ["issue_key"]
                    }
                ),
                Tool(
                    name="create_test_plan",
                    description="Create or update a test plan with specified tests",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "issue_key": {
                                "type": "string",
                                "description": "The Jira issue key containing test plan information"
                            }
                        },
                        "required": ["issue_key"]
                    }
                ),
                Tool(
                    name="create_test_direct",
                    description="Create a test case directly via Xray API",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "summary": {
                                "type": "string",
                                "description": "Test case summary/title"
                            },
                            "description": {
                                "type": "string",
                                "description": "Test case description"
                            },
                            "test_type": {
                                "type": "string",
                                "description": "Test type: 'Manual', 'Manual (Gherkin)', or 'Cucumber'",
                                "default": "Manual (Gherkin)"
                            },
                            "folder": {
                                "type": "string",
                                "description": "Folder path in test repository (e.g., '/Windows/MyFeature')"
                            },
                            "steps": {
                                "type": "string",
                                "description": "Test steps (Gherkin format for Manual (Gherkin) tests)"
                            }
                        },
                        "required": ["summary", "description", "folder", "steps"]
                    }
                ),
                Tool(
                    name="create_folder",
                    description="Create a folder in the Xray test repository",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Folder path (e.g., '/Windows/MyFeature')"
                            },
                            "test_plan_id": {
                                "type": "string",
                                "description": "Optional test plan ID to create folder within",
                                "default": None
                            }
                        },
                        "required": ["path"]
                    }
                ),
                Tool(
                    name="create_test_plan_direct",
                    description="Create a test plan directly via Xray API",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "summary": {
                                "type": "string",
                                "description": "Test plan summary/title"
                            },
                            "description": {
                                "type": "string",
                                "description": "Test plan description"
                            },
                            "fix_versions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of fix version names",
                                "default": []
                            },
                            "test_issue_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of test issue IDs to include",
                                "default": []
                            }
                        },
                        "required": ["summary", "description"]
                    }
                ),
                Tool(
                    name="delete_tests",
                    description="Delete all test cases linked to a Jira issue",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "issue_key": {
                                "type": "string",
                                "description": "The Jira issue key (e.g., 'EPM-123')"
                            }
                        },
                        "required": ["issue_key"]
                    }
                ),
                Tool(
                    name="unlink_tests",
                    description="Unlink all test cases from a Jira issue (without deleting)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "issue_key": {
                                "type": "string",
                                "description": "The Jira issue key (e.g., 'EPM-123')"
                            }
                        },
                        "required": ["issue_key"]
                    }
                ),
                Tool(
                    name="create_test_set",
                    description="Create a test set with specified tests",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "summary": {
                                "type": "string",
                                "description": "Test set summary/title"
                            },
                            "description": {
                                "type": "string",
                                "description": "Test set description"
                            },
                            "test_issue_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of test issue IDs to include in the test set"
                            }
                        },
                        "required": ["summary", "description", "test_issue_ids"]
                    }
                ),
                Tool(
                    name="create_precondition",
                    description="Create a precondition and link it to specified tests",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "summary": {
                                "type": "string",
                                "description": "Precondition summary/title"
                            },
                            "description": {
                                "type": "string",
                                "description": "Precondition description"
                            },
                            "precondition_type": {
                                "type": "string",
                                "description": "Precondition type (e.g., 'Manual')",
                                "default": "Manual"
                            },
                            "steps": {
                                "type": "string",
                                "description": "Precondition steps/definition"
                            },
                            "test_issue_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of test issue IDs to link to this precondition"
                            }
                        },
                        "required": ["summary", "description", "steps", "test_issue_ids"]
                    }
                ),
                Tool(
                    name="add_tests_to_folder",
                    description="Add existing tests to a folder in the test repository",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Folder path (e.g., '/Windows/MyFeature')"
                            },
                            "test_issue_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of test issue IDs to add to the folder"
                            },
                            "test_plan_id": {
                                "type": "string",
                                "description": "Optional test plan ID if adding to folder within test plan",
                                "default": None
                            }
                        },
                        "required": ["path", "test_issue_ids"]
                    }
                ),
                Tool(
                    name="import_test_results",
                    description="Import test execution results (supports multiple formats)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "format": {
                                "type": "string",
                                "description": "Result format: 'xray-json', 'cucumber', 'junit', 'testng', 'nunit', 'robot'",
                                "enum": ["xray-json", "cucumber", "junit", "testng", "nunit", "robot"]
                            },
                            "results": {
                                "type": "string",
                                "description": "Test results content (JSON string or file content)"
                            },
                            "info": {
                                "type": "string",
                                "description": "Additional info (required for some formats like cucumber)",
                                "default": None
                            }
                        },
                        "required": ["format", "results"]
                    }
                )
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> Sequence[TextContent]:
            """Handle tool calls."""
            try:
                # Initialize connections if not already done
                await self._ensure_initialized()
                
                if name == "get_test_info":
                    return await self._get_test_info(arguments)
                elif name == "parse_test_definitions":
                    return await self._parse_test_definitions(arguments)
                elif name == "create_test_template":
                    return await self._create_test_template(arguments)
                elif name == "create_test_cases":
                    return await self._create_test_cases(arguments)
                elif name == "get_linked_tests":
                    return await self._get_linked_tests(arguments)
                elif name == "create_test_plan":
                    return await self._create_test_plan(arguments)
                elif name == "create_test_direct":
                    return await self._create_test_direct(arguments)
                elif name == "create_folder":
                    return await self._create_folder(arguments)
                elif name == "create_test_plan_direct":
                    return await self._create_test_plan_direct(arguments)
                elif name == "delete_tests":
                    return await self._delete_tests(arguments)
                elif name == "unlink_tests":
                    return await self._unlink_tests(arguments)
                elif name == "create_test_set":
                    return await self._create_test_set(arguments)
                elif name == "create_precondition":
                    return await self._create_precondition(arguments)
                elif name == "add_tests_to_folder":
                    return await self._add_tests_to_folder(arguments)
                elif name == "import_test_results":
                    return await self._import_test_results(arguments)
                else:
                    raise ValueError(f"Unknown tool: {name}")
                    
            except Exception as e:
                logger.error(f"Error in tool {name}: {e}")
                return [TextContent(type="text", text=f"Error: {str(e)}")]

    async def _ensure_initialized(self):
        """Ensure Jira and Xray connections are initialized."""
        if self.jira is None:
            config_manager = MyJiraConfig()
            if not config_manager.exists():
                raise ValueError("Jira config file not found. Please run the main jira application first to generate configuration.")
            
            self.config = config_manager.load()
            jira_config = self.config["jira"]
            self.jira = MyJira(jira_config)
            logger.info(f"Initialized Jira connection for {jira_config['url']}")
            
        if self.xray_api is None:
            xray_config = self.config.get("xray")
            if not xray_config or not xray_config.get("client_id") or not xray_config.get("client_secret"):
                raise ValueError("Xray configuration not found or incomplete. Please configure Xray client_id and client_secret.")
            
            self.xray_api = XrayApi(xray_config)
            self.xray_api.authenticate()
            logger.info("Initialized Xray API connection")

    async def _get_test_info(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Get test information for a Jira issue."""
        issue_key = arguments["issue_key"]
        xray_issue = JiraXrayIssue(issue_key, self.jira)
        
        test_info = xray_issue.get_test_info()
        
        return [TextContent(type="text", text=test_info)]

    async def _parse_test_definitions(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Parse test definitions from a Jira issue."""
        issue_key = arguments["issue_key"]
        xray_issue = JiraXrayIssue(issue_key, self.jira)
        
        definitions = xray_issue.parse_test_definitions()
        
        result = {
            "folder": definitions.get_folder(),
            "test_plan": definitions.get_test_plan(),
            "fix_versions": definitions.get_fix_versions(),
            "test_count": len(definitions),
            "definitions": []
        }
        
        for definition in definitions:
            result["definitions"].append({
                "name": definition._name,
                "description": definition._description,
                "steps": definition._steps
            })
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _create_test_template(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Create a test template in a Jira issue."""
        issue_key = arguments["issue_key"]
        xray_issue = JiraXrayIssue(issue_key, self.jira)
        
        xray_issue.create_test_template()
        
        result = {
            "message": f"Test template created in {issue_key}",
            "issue_key": issue_key
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _create_test_cases(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Create Xray test cases from test definitions in a Jira issue."""
        issue_key = arguments["issue_key"]
        xray_issue = JiraXrayIssue(issue_key, self.jira)
        
        if not xray_issue.sprint_item_has_valid_tests():
            raise ValueError(f"Issue {issue_key} does not have valid test definitions. Use create_test_template first.")
        
        definitions = xray_issue.parse_test_definitions()
        tests = xray_issue.create_test_cases(definitions)
        
        result = {
            "message": f"Created {len(tests)} test cases for {issue_key}",
            "issue_key": issue_key,
            "folder": definitions.get_folder(),
            "test_count": len(tests),
            "created_tests": [test.key for test in tests]
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _get_linked_tests(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Get all test cases linked to a Jira issue."""
        issue_key = arguments["issue_key"]
        xray_issue = JiraXrayIssue(issue_key, self.jira)
        
        tests = xray_issue.get_tests()
        
        result = {
            "issue_key": issue_key,
            "test_count": len(tests),
            "linked_tests": []
        }
        
        for test in tests:
            result["linked_tests"].append({
                "key": test.key,
                "summary": test.fields.summary,
                "status": str(test.fields.status),
                "issue_type": str(test.fields.issuetype)
            })
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _create_test_plan(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Create or update a test plan with specified tests."""
        issue_key = arguments["issue_key"]
        xray_issue = JiraXrayIssue(issue_key, self.jira)
        
        definitions = xray_issue.parse_test_definitions()
        tests = xray_issue.get_tests()
        
        if not tests:
            raise ValueError(f"No test cases found for {issue_key}. Create test cases first.")
        
        test_ids = [test.id for test in tests]
        created_new = xray_issue.create_update_test_plan(definitions, test_ids)
        
        result = {
            "message": f"{'Created new' if created_new else 'Updated existing'} test plan for {issue_key}",
            "issue_key": issue_key,
            "test_plan": definitions.get_test_plan(),
            "test_count": len(test_ids),
            "created_new_plan": created_new
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _create_test_direct(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Create a test case directly via Xray API."""
        summary = arguments["summary"]
        description = arguments["description"]
        test_type = arguments.get("test_type", "Manual (Gherkin)")
        folder = arguments["folder"]
        steps = arguments["steps"]
        
        # Create folder if it doesn't exist
        self.xray_api.create_folder(folder)
        
        # Create the test
        test_key = self.xray_api.create_test(summary, description, test_type, folder, steps)
        
        result = {
            "message": f"Created test case {test_key}",
            "test_key": test_key,
            "summary": summary,
            "test_type": test_type,
            "folder": folder
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _create_folder(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Create a folder in the Xray test repository."""
        path = arguments["path"]
        test_plan_id = arguments.get("test_plan_id")
        
        response = self.xray_api.create_folder(path, test_plan_id)
        
        result = {
            "message": f"Created folder {path}",
            "path": path,
            "test_plan_id": test_plan_id,
            "response": response
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _create_test_plan_direct(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Create a test plan directly via Xray API."""
        summary = arguments["summary"]
        description = arguments["description"]
        fix_versions = arguments.get("fix_versions", [])
        test_issue_ids = arguments.get("test_issue_ids", [])
        
        response = self.xray_api.create_test_plan(summary, description, fix_versions, test_issue_ids)
        
        result = {
            "message": f"Created test plan {summary}",
            "summary": summary,
            "fix_versions": fix_versions,
            "test_count": len(test_issue_ids),
            "response": response
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _delete_tests(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Delete all test cases linked to a Jira issue."""
        issue_key = arguments["issue_key"]
        xray_issue = JiraXrayIssue(issue_key, self.jira)
        
        tests = xray_issue.get_tests()
        test_keys = [test.key for test in tests]
        
        xray_issue.delete_tests()
        
        result = {
            "message": f"Deleted {len(test_keys)} test cases from {issue_key}",
            "issue_key": issue_key,
            "deleted_tests": test_keys
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _unlink_tests(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Unlink all test cases from a Jira issue."""
        issue_key = arguments["issue_key"]
        xray_issue = JiraXrayIssue(issue_key, self.jira)
        
        tests = xray_issue.get_tests()
        test_keys = [test.key for test in tests]
        
        xray_issue.unlink_tests()
        
        result = {
            "message": f"Unlinked {len(test_keys)} test cases from {issue_key}",
            "issue_key": issue_key,
            "unlinked_tests": test_keys
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _create_test_set(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Create a test set with specified tests."""
        summary = arguments["summary"]
        description = arguments["description"]
        test_issue_ids = arguments["test_issue_ids"]
        
        response = self.xray_api.create_test_set(summary, description, test_issue_ids)
        
        result = {
            "message": f"Created test set {summary}",
            "summary": summary,
            "test_count": len(test_issue_ids),
            "response": response
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _create_precondition(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Create a precondition and link it to specified tests."""
        summary = arguments["summary"]
        description = arguments["description"]
        precondition_type = arguments.get("precondition_type", "Manual")
        steps = arguments["steps"]
        test_issue_ids = arguments["test_issue_ids"]
        
        response = self.xray_api.create_precondition(summary, description, precondition_type, steps, test_issue_ids)
        
        result = {
            "message": f"Created precondition {summary}",
            "summary": summary,
            "precondition_type": precondition_type,
            "linked_test_count": len(test_issue_ids),
            "response": response
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _add_tests_to_folder(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Add existing tests to a folder in the test repository."""
        path = arguments["path"]
        test_issue_ids = arguments["test_issue_ids"]
        test_plan_id = arguments.get("test_plan_id")
        
        response = self.xray_api.add_tests_to_folder(path, test_issue_ids, test_plan_id)
        
        result = {
            "message": f"Added {len(test_issue_ids)} tests to folder {path}",
            "path": path,
            "test_count": len(test_issue_ids),
            "test_plan_id": test_plan_id,
            "response": response
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _import_test_results(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Import test execution results."""
        format_type = arguments["format"]
        results = arguments["results"]
        info = arguments.get("info")
        
        try:
            if format_type == "xray-json":
                # For Xray JSON, parse results as JSON
                results_data = json.loads(results) if isinstance(results, str) else results
                response = self.xray_api.import_xray_json_results(results_data)
            elif format_type == "cucumber":
                if not info:
                    raise ValueError("Info parameter required for cucumber format")
                response = self.xray_api.import_cucumber_results(results, info)
            elif format_type == "junit":
                info_data = info if info else ""
                response = self.xray_api.import_junit_results(results, info_data)
            elif format_type == "testng":
                info_data = info if info else ""
                response = self.xray_api.import_testng_results(results, info_data)
            elif format_type == "nunit":
                info_data = info if info else ""
                response = self.xray_api.import_nunit_results(results, info_data)
            elif format_type == "robot":
                info_data = info if info else ""
                response = self.xray_api.import_robot_results(results, info_data)
            else:
                raise ValueError(f"Unsupported format: {format_type}")
            
            result = {
                "message": f"Successfully imported {format_type} test results",
                "format": format_type,
                "response": response
            }
            
        except json.JSONDecodeError as e:
            result = {
                "message": f"Failed to parse {format_type} results as JSON",
                "error": str(e)
            }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

async def main():
    """Main entry point for the MCP server."""
    logger.info("Starting Xray MCP Server...")
    xray_server = XrayMCPServer()
    logger.info("Xray MCP Server initialized with tools")
    
    # Run the server using stdio transport
    async with stdio_server() as (read_stream, write_stream):
        await xray_server.server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="xray-mcp-server",
                server_version="1.0.0",
                capabilities=xray_server.server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())