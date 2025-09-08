#!/usr/bin/env python3
"""
MCP Server for Azure DevOps Integration

This server provides tools to interact with Azure DevOps (VSTS) using the REST API.
It exposes various Azure DevOps operations as MCP tools that can be used by MCP clients.
"""

import asyncio
import base64
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence
import urllib.parse
import requests
from requests.auth import HTTPBasicAuth

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

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-azdo-server")

class AzdoMCPServer:
    def __init__(self):
        self.server = Server("azdo-mcp-server")
        self.session: Optional[requests.Session] = None
        self.org_url: Optional[str] = None
        self.project: Optional[str] = None
        self.repo: Optional[str] = None
        self.pat_token: Optional[str] = None
        
        # Register tools
        self._register_tools()
        
    def _register_tools(self):
        """Register all available Azure DevOps tools with the MCP server."""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List available Azure DevOps tools."""
            return [
                # Pipeline tools
                Tool(
                    name="list_pipelines",
                    description="List all build pipelines in the project",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                ),
                Tool(
                    name="get_pipeline_runs",
                    description="Get recent runs for a specific pipeline",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "pipeline_id": {
                                "type": "integer",
                                "description": "The pipeline ID"
                            },
                            "top": {
                                "type": "integer", 
                                "description": "Number of runs to retrieve (default: 10)",
                                "default": 10
                            }
                        },
                        "required": ["pipeline_id"]
                    }
                ),
                Tool(
                    name="get_build_details",
                    description="Get detailed information about a specific build",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "build_id": {
                                "type": "integer",
                                "description": "The build ID"
                            }
                        },
                        "required": ["build_id"]
                    }
                ),
                Tool(
                    name="trigger_pipeline",
                    description="Trigger a pipeline run",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "pipeline_id": {
                                "type": "integer",
                                "description": "The pipeline ID to trigger"
                            },
                            "branch": {
                                "type": "string",
                                "description": "Branch to build (default: main)",
                                "default": "main"
                            }
                        },
                        "required": ["pipeline_id"]
                    }
                ),
                # Build logs
                Tool(
                    name="get_build_logs",
                    description="Get logs for a specific build",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "build_id": {
                                "type": "integer",
                                "description": "The build ID"
                            }
                        },
                        "required": ["build_id"]
                    }
                ),
                Tool(
                    name="download_build_logs",
                    description="Download build logs to a local directory",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "build_id": {
                                "type": "integer",
                                "description": "The build ID"
                            },
                            "download_path": {
                                "type": "string",
                                "description": "Local path to download the logs (default: ./logs)",
                                "default": "./logs"
                            },
                            "include_system_logs": {
                                "type": "boolean",
                                "description": "Include system/internal logs (default: false)",
                                "default": false
                            }
                        },
                        "required": ["build_id"]
                    }
                ),
                Tool(
                    name="get_build_timeline",
                    description="Get the timeline/jobs for a build",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "build_id": {
                                "type": "integer",
                                "description": "The build ID"
                            }
                        },
                        "required": ["build_id"]
                    }
                ),
                # Artifacts
                Tool(
                    name="list_build_artifacts",
                    description="List artifacts for a specific build",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "build_id": {
                                "type": "integer",
                                "description": "The build ID"
                            }
                        },
                        "required": ["build_id"]
                    }
                ),
                Tool(
                    name="download_artifact",
                    description="Download an artifact from a build",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "build_id": {
                                "type": "integer",
                                "description": "The build ID"
                            },
                            "artifact_name": {
                                "type": "string",
                                "description": "Name of the artifact to download"
                            },
                            "download_path": {
                                "type": "string",
                                "description": "Local path to download the artifact",
                                "default": "./artifacts"
                            }
                        },
                        "required": ["build_id", "artifact_name"]
                    }
                ),
                # Test results
                Tool(
                    name="get_test_results",
                    description="Get test results for a build",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "build_id": {
                                "type": "integer",
                                "description": "The build ID"
                            }
                        },
                        "required": ["build_id"]
                    }
                ),
                Tool(
                    name="get_test_runs",
                    description="Get test runs for a build",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "build_id": {
                                "type": "integer",
                                "description": "The build ID"
                            }
                        },
                        "required": ["build_id"]
                    }
                ),
                # Repository tools
                Tool(
                    name="get_pull_requests",
                    description="Get pull requests from the repository",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "status": {
                                "type": "string",
                                "description": "PR status filter (active, completed, abandoned, all)",
                                "default": "active"
                            }
                        },
                        "required": []
                    }
                ),
                Tool(
                    name="get_work_items",
                    description="Search for work items using WIQL query",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "wiql": {
                                "type": "string",
                                "description": "Work Item Query Language (WIQL) query"
                            },
                            "top": {
                                "type": "integer",
                                "description": "Number of work items to retrieve (default: 50)",
                                "default": 50
                            }
                        },
                        "required": ["wiql"]
                    }
                ),
                # Release pipelines
                Tool(
                    name="list_releases",
                    description="List release pipelines and recent releases",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "definition_id": {
                                "type": "integer",
                                "description": "Release definition ID (optional)"
                            },
                            "top": {
                                "type": "integer",
                                "description": "Number of releases to retrieve (default: 10)",
                                "default": 10
                            }
                        },
                        "required": []
                    }
                ),
                Tool(
                    name="get_release_details",
                    description="Get detailed information about a specific release",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "release_id": {
                                "type": "integer",
                                "description": "The release ID"
                            }
                        },
                        "required": ["release_id"]
                    }
                )
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> Sequence[TextContent]:
            """Handle tool calls."""
            try:
                # Initialize Azure DevOps connection if not already done
                await self._ensure_azdo_initialized()
                
                # Route to appropriate handler
                tool_handlers = {
                    "list_pipelines": self._list_pipelines,
                    "get_pipeline_runs": self._get_pipeline_runs,
                    "get_build_details": self._get_build_details,
                    "trigger_pipeline": self._trigger_pipeline,
                    "get_build_logs": self._get_build_logs,
                    "download_build_logs": self._download_build_logs,
                    "get_build_timeline": self._get_build_timeline,
                    "list_build_artifacts": self._list_build_artifacts,
                    "download_artifact": self._download_artifact,
                    "get_test_results": self._get_test_results,
                    "get_test_runs": self._get_test_runs,
                    "get_pull_requests": self._get_pull_requests,
                    "get_work_items": self._get_work_items,
                    "list_releases": self._list_releases,
                    "get_release_details": self._get_release_details
                }
                
                if name in tool_handlers:
                    return await tool_handlers[name](arguments)
                else:
                    raise ValueError(f"Unknown tool: {name}")
                    
            except Exception as e:
                logger.error(f"Error in tool {name}: {e}")
                return [TextContent(type="text", text=f"Error: {str(e)}")]

    async def _ensure_azdo_initialized(self):
        """Ensure Azure DevOps connection is initialized."""
        if self.session is None:
            # Get configuration from environment variables
            self.pat_token = os.getenv("AZURE_DEVOPS_EXT_PAT")
            self.org_url = os.getenv("AZ_ORG")
            self.project = os.getenv("AZ_PROJECT")
            self.repo = os.getenv("AZ_REPO")
            
            if not all([self.pat_token, self.org_url, self.project]):
                raise ValueError("Missing required environment variables: AZURE_DEVOPS_EXT_PAT, AZ_ORG, AZ_PROJECT")
            
            # Create authenticated session
            self.session = requests.Session()
            self.session.auth = HTTPBasicAuth("", self.pat_token)
            self.session.headers.update({
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "mcp-azdo-server/1.0.0",
                "X-TFS-FedAuthRedirect": "Suppress"
            })
            
            logger.info(f"Initialized Azure DevOps connection for {self.org_url}/{self.project}")

    def _make_request(self, url: str, method: str = "GET", data: Optional[Dict] = None, return_raw: bool = False) -> any:
        """Make an authenticated request to Azure DevOps API."""
        try:
            if method.upper() == "GET":
                response = self.session.get(url)
            elif method.upper() == "POST":
                response = self.session.post(url, json=data)
            elif method.upper() == "PUT":
                response = self.session.put(url, json=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
                
            response.raise_for_status()
            
            # Return raw response if requested (for file downloads)
            if return_raw:
                return response
            
            # Handle empty responses
            if not response.content:
                return {}
                
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise

    # Pipeline tools implementation
    async def _list_pipelines(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """List all build pipelines in the project."""
        url = f"{self.org_url}/{self.project}/_apis/build/definitions?api-version=6.0"
        
        data = self._make_request(url)
        pipelines = data.get("value", [])
        
        result = {
            "total": len(pipelines),
            "pipelines": [
                {
                    "id": pipeline["id"],
                    "name": pipeline["name"],
                    "path": pipeline.get("path", "\\"),
                    "revision": pipeline.get("revision", 0),
                    "created_date": pipeline.get("createdDate"),
                    "queue_status": pipeline.get("queueStatus"),
                    "type": pipeline.get("type"),
                    "uri": pipeline.get("uri")
                }
                for pipeline in pipelines
            ]
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _get_pipeline_runs(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Get recent runs for a specific pipeline."""
        pipeline_id = arguments["pipeline_id"]
        top = arguments.get("top", 10)
        
        url = f"{self.org_url}/{self.project}/_apis/build/builds?definitions={pipeline_id}&$top={top}&api-version=6.0"
        
        data = self._make_request(url)
        builds = data.get("value", [])
        
        result = {
            "pipeline_id": pipeline_id,
            "total": len(builds),
            "builds": [
                {
                    "id": build["id"],
                    "build_number": build.get("buildNumber"),
                    "status": build.get("status"),
                    "result": build.get("result"),
                    "start_time": build.get("startTime"),
                    "finish_time": build.get("finishTime"),
                    "source_branch": build.get("sourceBranch"),
                    "requested_by": build.get("requestedBy", {}).get("displayName"),
                    "queue_time": build.get("queueTime")
                }
                for build in builds
            ]
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _get_build_details(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Get detailed information about a specific build."""
        build_id = arguments["build_id"]
        
        url = f"{self.org_url}/{self.project}/_apis/build/builds/{build_id}?api-version=6.0"
        
        build = self._make_request(url)
        
        result = {
            "id": build["id"],
            "build_number": build.get("buildNumber"),
            "status": build.get("status"),
            "result": build.get("result"),
            "start_time": build.get("startTime"),
            "finish_time": build.get("finishTime"),
            "source_branch": build.get("sourceBranch"),
            "source_version": build.get("sourceVersion"),
            "requested_by": build.get("requestedBy", {}).get("displayName"),
            "requested_for": build.get("requestedFor", {}).get("displayName"),
            "queue_time": build.get("queueTime"),
            "definition": {
                "id": build.get("definition", {}).get("id"),
                "name": build.get("definition", {}).get("name")
            },
            "repository": {
                "id": build.get("repository", {}).get("id"),
                "name": build.get("repository", {}).get("name"),
                "url": build.get("repository", {}).get("url")
            },
            "reason": build.get("reason"),
            "priority": build.get("priority"),
            "uri": build.get("uri"),
            "url": build.get("url")
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _trigger_pipeline(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Trigger a pipeline run."""
        pipeline_id = arguments["pipeline_id"]
        branch = arguments.get("branch", "main")
        
        # First get pipeline definition to construct proper request
        definition_url = f"{self.org_url}/{self.project}/_apis/build/definitions/{pipeline_id}?api-version=6.0"
        definition = self._make_request(definition_url)
        
        # Trigger the build
        url = f"{self.org_url}/{self.project}/_apis/build/builds?api-version=6.0"
        
        build_request = {
            "definition": {
                "id": pipeline_id
            },
            "sourceBranch": f"refs/heads/{branch}"
        }
        
        build = self._make_request(url, method="POST", data=build_request)
        
        result = {
            "build_id": build["id"],
            "build_number": build.get("buildNumber"),
            "pipeline_id": pipeline_id,
            "pipeline_name": definition.get("name"),
            "branch": branch,
            "status": build.get("status"),
            "queue_time": build.get("queueTime"),
            "url": build.get("_links", {}).get("web", {}).get("href"),
            "message": f"Successfully triggered build #{build.get('buildNumber')} for pipeline {definition.get('name')}"
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _get_build_logs(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Get logs for a specific build."""
        build_id = arguments["build_id"]
        
        # First get the list of logs
        logs_url = f"{self.org_url}/{self.project}/_apis/build/builds/{build_id}/logs?api-version=6.0"
        logs_data = self._make_request(logs_url)
        
        logs = logs_data.get("value", [])
        
        # Get content for each log
        log_contents = []
        for log in logs[:5]:  # Limit to first 5 logs to avoid too much data
            log_id = log["id"]
            content_url = f"{self.org_url}/{self.project}/_apis/build/builds/{build_id}/logs/{log_id}?api-version=6.0"
            
            try:
                # Use the authenticated _make_request method for consistency
                response = self._make_request(content_url, return_raw=True)
                
                log_contents.append({
                    "id": log_id,
                    "type": log.get("type"),
                    "url": log.get("url"),
                    "line_count": log.get("lineCount", 0),
                    "content": response.text[:2000] + "..." if len(response.text) > 2000 else response.text
                })
            except Exception as e:
                log_contents.append({
                    "id": log_id,
                    "type": log.get("type"),
                    "url": log.get("url"),
                    "line_count": log.get("lineCount", 0),
                    "error": f"Failed to retrieve log content: {str(e)}"
                })
        
        result = {
            "build_id": build_id,
            "total_logs": len(logs),
            "showing_first": min(5, len(logs)),
            "logs": log_contents
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _download_build_logs(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Download build logs to a local directory."""
        build_id = arguments["build_id"]
        download_path = arguments.get("download_path", "./logs")
        include_system_logs = arguments.get("include_system_logs", False)
        
        # Create download directory
        os.makedirs(download_path, exist_ok=True)
        
        # First get the list of logs
        logs_url = f"{self.org_url}/{self.project}/_apis/build/builds/{build_id}/logs?api-version=6.0"
        logs_data = self._make_request(logs_url)
        
        logs = logs_data.get("value", [])
        
        if not logs:
            raise ValueError(f"No logs found for build {build_id}")
        
        downloaded_files = []
        download_errors = []
        
        for log in logs:
            log_id = log["id"]
            log_type = log.get("type", "Unknown")
            line_count = log.get("lineCount", 0)
            
            # Skip system logs unless explicitly requested
            if not include_system_logs and log_type.lower() in ["container", "system"]:
                continue
            
            # Skip empty logs
            if line_count == 0:
                continue
                
            try:
                # Download log content with proper authentication
                content_url = f"{self.org_url}/{self.project}/_apis/build/builds/{build_id}/logs/{log_id}?api-version=6.0"
                
                # Use the authenticated session to get raw content
                response = self._make_request(content_url, return_raw=True)
                
                # Create filename
                safe_type = log_type.replace("/", "_").replace("\\", "_")
                filename = f"build_{build_id}_log_{log_id}_{safe_type}.txt"
                filepath = os.path.join(download_path, filename)
                
                # Write log content to file
                with open(filepath, "w", encoding="utf-8", errors="replace") as f:
                    f.write(response.text)
                
                downloaded_files.append({
                    "log_id": log_id,
                    "type": log_type,
                    "line_count": line_count,
                    "filename": filename,
                    "filepath": filepath,
                    "size_bytes": len(response.content)
                })
                
            except Exception as e:
                error_msg = f"Failed to download log {log_id} ({log_type}): {str(e)}"
                logger.error(error_msg)
                download_errors.append({
                    "log_id": log_id,
                    "type": log_type,
                    "error": error_msg
                })
        
        result = {
            "build_id": build_id,
            "download_path": download_path,
            "total_logs_available": len(logs),
            "downloaded_count": len(downloaded_files),
            "error_count": len(download_errors),
            "include_system_logs": include_system_logs,
            "downloaded_files": downloaded_files,
            "errors": download_errors,
            "message": f"Successfully downloaded {len(downloaded_files)} log files to {download_path}"
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _get_build_timeline(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Get the timeline/jobs for a build."""
        build_id = arguments["build_id"]
        
        url = f"{self.org_url}/{self.project}/_apis/build/builds/{build_id}/timeline?api-version=6.0"
        
        data = self._make_request(url)
        records = data.get("records", [])
        
        result = {
            "build_id": build_id,
            "total_records": len(records),
            "timeline": [
                {
                    "id": record["id"],
                    "name": record.get("name"),
                    "type": record.get("type"),
                    "state": record.get("state"),
                    "result": record.get("result"),
                    "start_time": record.get("startTime"),
                    "finish_time": record.get("finishTime"),
                    "percent_complete": record.get("percentComplete"),
                    "order": record.get("order"),
                    "parent_id": record.get("parentId"),
                    "log": {
                        "id": record.get("log", {}).get("id"),
                        "type": record.get("log", {}).get("type"),
                        "url": record.get("log", {}).get("url")
                    } if record.get("log") else None
                }
                for record in records
            ]
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _list_build_artifacts(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """List artifacts for a specific build."""
        build_id = arguments["build_id"]
        
        url = f"{self.org_url}/{self.project}/_apis/build/builds/{build_id}/artifacts?api-version=6.0"
        
        data = self._make_request(url)
        artifacts = data.get("value", [])
        
        result = {
            "build_id": build_id,
            "total_artifacts": len(artifacts),
            "artifacts": [
                {
                    "id": artifact["id"],
                    "name": artifact["name"],
                    "resource": {
                        "type": artifact.get("resource", {}).get("type"),
                        "data": artifact.get("resource", {}).get("data"),
                        "properties": artifact.get("resource", {}).get("properties"),
                        "url": artifact.get("resource", {}).get("url"),
                        "download_url": artifact.get("resource", {}).get("downloadUrl")
                    }
                }
                for artifact in artifacts
            ]
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _download_artifact(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Download an artifact from a build."""
        build_id = arguments["build_id"]
        artifact_name = arguments["artifact_name"]
        download_path = arguments.get("download_path", "./artifacts")
        
        # First get artifact information
        url = f"{self.org_url}/{self.project}/_apis/build/builds/{build_id}/artifacts?artifactName={artifact_name}&api-version=6.0"
        
        data = self._make_request(url)
        artifacts = data.get("value", [])
        
        if not artifacts:
            raise ValueError(f"Artifact '{artifact_name}' not found for build {build_id}")
        
        artifact = artifacts[0]
        download_url = artifact.get("resource", {}).get("downloadUrl")
        
        if not download_url:
            raise ValueError(f"No download URL available for artifact '{artifact_name}'")
        
        # Create download directory
        os.makedirs(download_path, exist_ok=True)
        
        # Download the artifact
        response = self.session.get(download_url)
        response.raise_for_status()
        
        # Save to file
        filename = f"{artifact_name}_build_{build_id}.zip"
        filepath = os.path.join(download_path, filename)
        
        with open(filepath, "wb") as f:
            f.write(response.content)
        
        result = {
            "build_id": build_id,
            "artifact_name": artifact_name,
            "download_path": filepath,
            "file_size": len(response.content),
            "message": f"Successfully downloaded artifact '{artifact_name}' to {filepath}"
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _get_test_results(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Get test results for a build."""
        build_id = arguments["build_id"]
        
        url = f"{self.org_url}/{self.project}/_apis/test/resultdetailsbybuild?buildId={build_id}&api-version=6.0"
        
        try:
            data = self._make_request(url)
            results_for_group = data.get("resultsForGroup", [])
            
            all_results = []
            summary = {
                "total_tests": 0,
                "passed": 0,
                "failed": 0,
                "not_executed": 0,
                "groups": len(results_for_group)
            }
            
            for group in results_for_group:
                group_data = group.get("groupByValue", {})
                results = group.get("results", [])
                
                for result in results:
                    all_results.append({
                        "test_id": result.get("id"),
                        "test_case_title": result.get("testCaseTitle"),
                        "outcome": result.get("outcome"),
                        "state": result.get("state"),
                        "priority": result.get("priority"),
                        "duration": result.get("durationInMs"),
                        "error_message": result.get("errorMessage"),
                        "stack_trace": result.get("stackTrace")[:500] + "..." if result.get("stackTrace") and len(result.get("stackTrace", "")) > 500 else result.get("stackTrace"),
                        "automated_test_name": result.get("automatedTestName"),
                        "test_run": {
                            "id": result.get("testRun", {}).get("id"),
                            "name": result.get("testRun", {}).get("name")
                        }
                    })
                    
                    # Update summary
                    summary["total_tests"] += 1
                    outcome = result.get("outcome", "").lower()
                    if outcome == "passed":
                        summary["passed"] += 1
                    elif outcome == "failed":
                        summary["failed"] += 1
                    elif outcome == "notexecuted":
                        summary["not_executed"] += 1
            
            result = {
                "build_id": build_id,
                "summary": summary,
                "test_results": all_results
            }
            
        except Exception as e:
            # Fallback to basic test runs API
            logger.warning(f"Detailed test results failed, trying basic API: {e}")
            return await self._get_test_runs(arguments)
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _get_test_runs(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Get test runs for a build."""
        build_id = arguments["build_id"]
        
        url = f"{self.org_url}/{self.project}/_apis/test/runs?buildIds={build_id}&api-version=6.0"
        
        data = self._make_request(url)
        test_runs = data.get("value", [])
        
        result = {
            "build_id": build_id,
            "total_runs": len(test_runs),
            "test_runs": [
                {
                    "id": run["id"],
                    "name": run.get("name"),
                    "state": run.get("state"),
                    "outcome": run.get("outcome"),
                    "total_tests": run.get("totalTests"),
                    "passed_tests": run.get("passedTests"),
                    "failed_tests": run.get("failedTests"),
                    "unanalyzed_tests": run.get("unanalyzedTests"),
                    "incomplete_tests": run.get("incompleteTests"),
                    "not_applicable_tests": run.get("notApplicableTests"),
                    "start_date": run.get("startedDate"),
                    "completed_date": run.get("completedDate"),
                    "build": {
                        "id": run.get("build", {}).get("id"),
                        "name": run.get("build", {}).get("name")
                    },
                    "web_access_url": run.get("webAccessUrl")
                }
                for run in test_runs
            ]
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _get_pull_requests(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Get pull requests from the repository."""
        status = arguments.get("status", "active")
        
        if not self.repo:
            raise ValueError("Repository name not configured. Set AZ_REPO environment variable.")
        
        url = f"{self.org_url}/{self.project}/_apis/git/repositories/{self.repo}/pullrequests?searchCriteria.status={status}&api-version=6.0"
        
        data = self._make_request(url)
        pull_requests = data.get("value", [])
        
        result = {
            "repository": self.repo,
            "status_filter": status,
            "total": len(pull_requests),
            "pull_requests": [
                {
                    "pull_request_id": pr["pullRequestId"],
                    "title": pr.get("title"),
                    "description": pr.get("description")[:200] + "..." if pr.get("description") and len(pr.get("description", "")) > 200 else pr.get("description"),
                    "status": pr.get("status"),
                    "created_by": pr.get("createdBy", {}).get("displayName"),
                    "creation_date": pr.get("creationDate"),
                    "source_branch": pr.get("sourceRefName"),
                    "target_branch": pr.get("targetRefName"),
                    "merge_status": pr.get("mergeStatus"),
                    "url": pr.get("_links", {}).get("web", {}).get("href")
                }
                for pr in pull_requests
            ]
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _get_work_items(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Search for work items using WIQL query."""
        wiql = arguments["wiql"]
        top = arguments.get("top", 50)
        
        # Execute WIQL query
        query_url = f"{self.org_url}/{self.project}/_apis/wit/wiql?api-version=6.0"
        query_data = {
            "query": wiql
        }
        
        query_result = self._make_request(query_url, method="POST", data=query_data)
        work_items = query_result.get("workItems", [])[:top]
        
        if not work_items:
            return [TextContent(type="text", text=json.dumps({
                "wiql": wiql,
                "total": 0,
                "work_items": []
            }, indent=2))]
        
        # Get work item IDs
        work_item_ids = [str(wi["id"]) for wi in work_items]
        ids_string = ",".join(work_item_ids)
        
        # Get work item details
        details_url = f"{self.org_url}/{self.project}/_apis/wit/workitems?ids={ids_string}&api-version=6.0"
        details_result = self._make_request(details_url)
        
        work_item_details = details_result.get("value", [])
        
        result = {
            "wiql": wiql,
            "total": len(work_item_details),
            "work_items": [
                {
                    "id": wi["id"],
                    "rev": wi.get("rev"),
                    "url": wi.get("url"),
                    "fields": {
                        "title": wi.get("fields", {}).get("System.Title"),
                        "work_item_type": wi.get("fields", {}).get("System.WorkItemType"),
                        "state": wi.get("fields", {}).get("System.State"),
                        "assigned_to": wi.get("fields", {}).get("System.AssignedTo", {}).get("displayName") if wi.get("fields", {}).get("System.AssignedTo") else None,
                        "created_by": wi.get("fields", {}).get("System.CreatedBy", {}).get("displayName") if wi.get("fields", {}).get("System.CreatedBy") else None,
                        "created_date": wi.get("fields", {}).get("System.CreatedDate"),
                        "changed_date": wi.get("fields", {}).get("System.ChangedDate"),
                        "area_path": wi.get("fields", {}).get("System.AreaPath"),
                        "iteration_path": wi.get("fields", {}).get("System.IterationPath"),
                        "priority": wi.get("fields", {}).get("Microsoft.VSTS.Common.Priority"),
                        "severity": wi.get("fields", {}).get("Microsoft.VSTS.Common.Severity")
                    }
                }
                for wi in work_item_details
            ]
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _list_releases(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """List release pipelines and recent releases."""
        definition_id = arguments.get("definition_id")
        top = arguments.get("top", 10)
        
        # Build URL based on whether definition_id is specified
        if definition_id:
            url = f"{self.org_url}/{self.project}/_apis/release/releases?definitionId={definition_id}&$top={top}&api-version=6.0"
        else:
            url = f"{self.org_url}/{self.project}/_apis/release/releases?$top={top}&api-version=6.0"
        
        data = self._make_request(url)
        releases = data.get("value", [])
        
        result = {
            "definition_id": definition_id,
            "total": len(releases),
            "releases": [
                {
                    "id": release["id"],
                    "name": release.get("name"),
                    "status": release.get("status"),
                    "created_on": release.get("createdOn"),
                    "created_by": release.get("createdBy", {}).get("displayName"),
                    "modified_on": release.get("modifiedOn"),
                    "modified_by": release.get("modifiedBy", {}).get("displayName"),
                    "release_definition": {
                        "id": release.get("releaseDefinition", {}).get("id"),
                        "name": release.get("releaseDefinition", {}).get("name")
                    },
                    "description": release.get("description"),
                    "reason": release.get("reason"),
                    "web_access_url": release.get("_links", {}).get("web", {}).get("href")
                }
                for release in releases
            ]
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _get_release_details(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Get detailed information about a specific release."""
        release_id = arguments["release_id"]
        
        url = f"{self.org_url}/{self.project}/_apis/release/releases/{release_id}?api-version=6.0"
        
        release = self._make_request(url)
        
        # Extract environment information
        environments = []
        for env in release.get("environments", []):
            environments.append({
                "id": env.get("id"),
                "name": env.get("name"),
                "status": env.get("status"),
                "rank": env.get("rank"),
                "created_on": env.get("createdOn"),
                "modified_on": env.get("modifiedOn"),
                "conditions": env.get("conditions", []),
                "deploy_steps": [
                    {
                        "id": step.get("id"),
                        "deployment_id": step.get("deploymentId"),
                        "attempt": step.get("attempt"),
                        "status": step.get("status"),
                        "operation_status": step.get("operationStatus"),
                        "requested_by": step.get("requestedBy", {}).get("displayName"),
                        "requested_for": step.get("requestedFor", {}).get("displayName"),
                        "queued_on": step.get("queuedOn"),
                        "last_modified_on": step.get("lastModifiedOn")
                    }
                    for step in env.get("deploySteps", [])
                ]
            })
        
        result = {
            "id": release["id"],
            "name": release.get("name"),
            "status": release.get("status"),
            "created_on": release.get("createdOn"),
            "created_by": release.get("createdBy", {}).get("displayName"),
            "modified_on": release.get("modifiedOn"),
            "modified_by": release.get("modifiedBy", {}).get("displayName"),
            "release_definition": {
                "id": release.get("releaseDefinition", {}).get("id"),
                "name": release.get("releaseDefinition", {}).get("name"),
                "url": release.get("releaseDefinition", {}).get("url")
            },
            "description": release.get("description"),
            "reason": release.get("reason"),
            "keep_forever": release.get("keepForever"),
            "logs_container_url": release.get("logsContainerUrl"),
            "web_access_url": release.get("_links", {}).get("web", {}).get("href"),
            "environments": environments,
            "artifacts": [
                {
                    "source_id": artifact.get("sourceId"),
                    "type": artifact.get("type"),
                    "alias": artifact.get("alias"),
                    "definition_reference": artifact.get("definitionReference", {}),
                    "is_primary": artifact.get("isPrimary")
                }
                for artifact in release.get("artifacts", [])
            ]
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

async def main():
    """Main entry point for the MCP server."""
    logger.info("Starting Azure DevOps MCP Server...")
    azdo_server = AzdoMCPServer()
    logger.info("Azure DevOps MCP Server initialized with tools")
    
    # Run the server using stdio transport
    async with stdio_server() as (read_stream, write_stream):
        await azdo_server.server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="azdo-mcp-server",
                server_version="1.0.0",
                capabilities=azdo_server.server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())