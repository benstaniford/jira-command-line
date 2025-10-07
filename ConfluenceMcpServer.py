#!/usr/bin/env python3
"""
MCP Server for Confluence Integration

This server provides tools to interact with Confluence.
It exposes various Confluence operations as MCP tools that can be used by MCP clients.
"""

import asyncio
import json
import logging
import re
import sys
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import urlparse, unquote

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

# Confluence API
from atlassian import Confluence

# Local imports
from libs.MyJiraConfig import MyJiraConfig

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-confluence-server")

class ConfluenceMCPServer:
    def __init__(self):
        self.server = Server("confluence-mcp-server")
        self.confluence: Optional[Confluence] = None
        self.config: Optional[Dict[str, Any]] = None

        # Register tools
        self._register_tools()

    def _register_tools(self):
        """Register all available tools with the MCP server."""

        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List available Confluence tools."""
            return [
                Tool(
                    name="get_page",
                    description="Get a Confluence page by URL, page ID, or space+title",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "Full Confluence page URL (e.g., https://domain.atlassian.net/wiki/spaces/SPACE/pages/123456/Page+Title)"
                            },
                            "page_id": {
                                "type": "string",
                                "description": "Confluence page ID (alternative to URL)"
                            },
                            "space_key": {
                                "type": "string",
                                "description": "Space key (required if using title instead of URL/page_id)"
                            },
                            "title": {
                                "type": "string",
                                "description": "Page title (alternative to URL/page_id, requires space_key)"
                            },
                            "expand": {
                                "type": "string",
                                "description": "Comma-separated list of properties to expand (e.g., 'body.storage,version')",
                                "default": "body.storage,version,space"
                            }
                        },
                        "required": []
                    }
                ),
                Tool(
                    name="create_page",
                    description="Create a new Confluence page",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "space_key": {
                                "type": "string",
                                "description": "Space key where the page will be created"
                            },
                            "title": {
                                "type": "string",
                                "description": "Page title"
                            },
                            "content": {
                                "type": "string",
                                "description": "Page content in Confluence storage format (HTML-like)"
                            },
                            "parent_id": {
                                "type": "string",
                                "description": "Parent page ID (optional, for creating child pages)"
                            }
                        },
                        "required": ["space_key", "title", "content"]
                    }
                ),
                Tool(
                    name="update_page",
                    description="Update an existing Confluence page",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "page_id": {
                                "type": "string",
                                "description": "Confluence page ID to update"
                            },
                            "url": {
                                "type": "string",
                                "description": "Full Confluence page URL (alternative to page_id)"
                            },
                            "title": {
                                "type": "string",
                                "description": "New page title (optional, keeps existing if not provided)"
                            },
                            "content": {
                                "type": "string",
                                "description": "New page content in Confluence storage format"
                            },
                            "append": {
                                "type": "boolean",
                                "description": "If true, append content to existing page instead of replacing",
                                "default": False
                            }
                        },
                        "required": ["content"]
                    }
                ),
                Tool(
                    name="search_pages",
                    description="Search for Confluence pages using CQL (Confluence Query Language)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "cql": {
                                "type": "string",
                                "description": "CQL query string (e.g., 'space=PMFW and title~\"HLK\"')"
                            },
                            "text": {
                                "type": "string",
                                "description": "Simple text search (alternative to CQL, searches titles and content)"
                            },
                            "space_key": {
                                "type": "string",
                                "description": "Limit search to specific space (optional)"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results to return",
                                "default": 25
                            }
                        },
                        "required": []
                    }
                ),
                Tool(
                    name="get_space",
                    description="Get information about a Confluence space",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "space_key": {
                                "type": "string",
                                "description": "Space key"
                            }
                        },
                        "required": ["space_key"]
                    }
                ),
                Tool(
                    name="list_spaces",
                    description="List all Confluence spaces the user has access to",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of spaces to return",
                                "default": 50
                            }
                        },
                        "required": []
                    }
                ),
                Tool(
                    name="get_page_children",
                    description="Get child pages of a Confluence page",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "page_id": {
                                "type": "string",
                                "description": "Parent page ID"
                            },
                            "url": {
                                "type": "string",
                                "description": "Full Confluence page URL (alternative to page_id)"
                            }
                        },
                        "required": []
                    }
                )
            ]

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> Sequence[TextContent]:
            """Handle tool calls."""
            try:
                # Initialize Confluence connection if not already done
                await self._ensure_confluence_initialized()

                if name == "get_page":
                    return await self._get_page(arguments)
                elif name == "create_page":
                    return await self._create_page(arguments)
                elif name == "update_page":
                    return await self._update_page(arguments)
                elif name == "search_pages":
                    return await self._search_pages(arguments)
                elif name == "get_space":
                    return await self._get_space(arguments)
                elif name == "list_spaces":
                    return await self._list_spaces(arguments)
                elif name == "get_page_children":
                    return await self._get_page_children(arguments)
                else:
                    raise ValueError(f"Unknown tool: {name}")

            except Exception as e:
                logger.error(f"Error in tool {name}: {e}", exc_info=True)
                return [TextContent(type="text", text=f"Error: {str(e)}")]

    async def _ensure_confluence_initialized(self):
        """Ensure Confluence connection is initialized."""
        if self.confluence is None:
            config_manager = MyJiraConfig()
            if not config_manager.exists():
                raise ValueError("Config file not found. Please run the main jira application first to generate configuration.")

            self.config = config_manager.load()
            jira_config = self.config["jira"]

            # Use the Jira credentials for Confluence (same Atlassian instance)
            self.confluence = Confluence(
                url=jira_config["url"],
                username=jira_config["username"],
                password=jira_config["password"],
                cloud=True
            )
            logger.info(f"Initialized Confluence connection for {jira_config['url']}")

    def _parse_confluence_url(self, url: str) -> Optional[str]:
        """
        Parse a Confluence URL and extract the page ID.

        Example URL: https://beyondtrust.atlassian.net/wiki/spaces/PMFW/pages/1031831562/How+to+run+the+Microsoft+HLK+driver+tests+against+EPM-W

        Returns: page_id (e.g., '1031831562')
        """
        # Pattern: /pages/{page_id}/...
        match = re.search(r'/pages/(\d+)', url)
        if match:
            return match.group(1)
        return None

    async def _get_page(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Get a Confluence page."""
        page_id = arguments.get("page_id")
        url = arguments.get("url")
        space_key = arguments.get("space_key")
        title = arguments.get("title")
        expand = arguments.get("expand", "body.storage,version,space")

        # Determine how to fetch the page
        if url:
            page_id = self._parse_confluence_url(url)
            if not page_id:
                return [TextContent(type="text", text="Error: Could not extract page ID from URL")]

        if page_id:
            # Fetch by page ID
            page = self.confluence.get_page_by_id(
                page_id=page_id,
                expand=expand
            )
        elif space_key and title:
            # Fetch by space and title
            page = self.confluence.get_page_by_title(
                space=space_key,
                title=title,
                expand=expand
            )
        else:
            return [TextContent(type="text", text="Error: Must provide either 'url', 'page_id', or both 'space_key' and 'title'")]

        if not page:
            return [TextContent(type="text", text="Error: Page not found")]

        # Extract relevant information
        result = {
            "id": page.get("id"),
            "title": page.get("title"),
            "type": page.get("type"),
            "space": page.get("space", {}).get("key") if "space" in page else None,
            "version": page.get("version", {}).get("number") if "version" in page else None,
            "url": f"{self.confluence.url}/wiki/spaces/{page.get('space', {}).get('key')}/pages/{page.get('id')}/{page.get('title', '').replace(' ', '+')}",
            "content": page.get("body", {}).get("storage", {}).get("value") if "body" in page else None,
            "last_modified": page.get("version", {}).get("when") if "version" in page else None,
            "last_modified_by": page.get("version", {}).get("by", {}).get("displayName") if "version" in page else None
        }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _create_page(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Create a new Confluence page."""
        space_key = arguments["space_key"]
        title = arguments["title"]
        content = arguments["content"]
        parent_id = arguments.get("parent_id")

        # Create the page
        page = self.confluence.create_page(
            space=space_key,
            title=title,
            body=content,
            parent_id=parent_id,
            type="page",
            representation="storage"
        )

        result = {
            "id": page.get("id"),
            "title": page.get("title"),
            "space": page.get("space", {}).get("key"),
            "version": page.get("version", {}).get("number"),
            "url": f"{self.confluence.url}/wiki/spaces/{space_key}/pages/{page.get('id')}/{title.replace(' ', '+')}",
            "message": f"Successfully created page '{title}' in space {space_key}"
        }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _update_page(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Update an existing Confluence page."""
        page_id = arguments.get("page_id")
        url = arguments.get("url")
        new_title = arguments.get("title")
        content = arguments["content"]
        append = arguments.get("append", False)

        # Determine page ID
        if url and not page_id:
            page_id = self._parse_confluence_url(url)
            if not page_id:
                return [TextContent(type="text", text="Error: Could not extract page ID from URL")]

        if not page_id:
            return [TextContent(type="text", text="Error: Must provide either 'page_id' or 'url'")]

        # Get current page to get version number and title
        current_page = self.confluence.get_page_by_id(
            page_id=page_id,
            expand="body.storage,version"
        )

        if not current_page:
            return [TextContent(type="text", text=f"Error: Page {page_id} not found")]

        current_version = current_page.get("version", {}).get("number", 1)
        current_title = current_page.get("title")
        current_content = current_page.get("body", {}).get("storage", {}).get("value", "")

        # Determine final content
        if append:
            final_content = current_content + "\n" + content
        else:
            final_content = content

        # Determine final title
        final_title = new_title if new_title else current_title

        # Update the page
        updated_page = self.confluence.update_page(
            page_id=page_id,
            title=final_title,
            body=final_content,
            version_comment="Updated via MCP",
            minor_edit=False
        )

        result = {
            "id": updated_page.get("id"),
            "title": updated_page.get("title"),
            "version": updated_page.get("version", {}).get("number"),
            "previous_version": current_version,
            "url": f"{self.confluence.url}/wiki/pages/viewpage.action?pageId={page_id}",
            "message": f"Successfully updated page '{final_title}'"
        }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _search_pages(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Search for Confluence pages."""
        cql = arguments.get("cql")
        text = arguments.get("text")
        space_key = arguments.get("space_key")
        limit = arguments.get("limit", 25)

        # Build CQL query
        if not cql:
            if text:
                # Simple text search
                cql = f'type=page and text~"{text}"'
                if space_key:
                    cql += f' and space={space_key}'
            elif space_key:
                # Just search by space
                cql = f'type=page and space={space_key}'
            else:
                return [TextContent(type="text", text="Error: Must provide either 'cql', 'text', or 'space_key'")]

        # Execute search
        results = self.confluence.cql(cql, limit=limit)

        pages = []
        for result in results.get("results", []):
            content = result.get("content", {})
            pages.append({
                "id": content.get("id"),
                "title": content.get("title"),
                "type": content.get("type"),
                "space": content.get("space", {}).get("key"),
                "url": f"{self.confluence.url}{content.get('_links', {}).get('webui', '')}",
                "excerpt": result.get("excerpt", "")
            })

        result_data = {
            "total": results.get("totalSize", 0),
            "limit": limit,
            "query": cql,
            "pages": pages
        }

        return [TextContent(type="text", text=json.dumps(result_data, indent=2))]

    async def _get_space(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Get information about a Confluence space."""
        space_key = arguments["space_key"]

        space = self.confluence.get_space(
            space_key=space_key,
            expand="description.plain,homepage"
        )

        result = {
            "key": space.get("key"),
            "name": space.get("name"),
            "type": space.get("type"),
            "description": space.get("description", {}).get("plain", {}).get("value"),
            "homepage_id": space.get("homepage", {}).get("id"),
            "url": f"{self.confluence.url}/wiki/spaces/{space_key}"
        }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _list_spaces(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """List all Confluence spaces."""
        limit = arguments.get("limit", 50)

        spaces = self.confluence.get_all_spaces(
            start=0,
            limit=limit,
            expand="description.plain"
        )

        space_list = []
        for space in spaces.get("results", []):
            space_list.append({
                "key": space.get("key"),
                "name": space.get("name"),
                "type": space.get("type"),
                "url": f"{self.confluence.url}/wiki/spaces/{space.get('key')}"
            })

        result = {
            "total": len(space_list),
            "spaces": space_list
        }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _get_page_children(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Get child pages of a Confluence page."""
        page_id = arguments.get("page_id")
        url = arguments.get("url")

        # Determine page ID
        if url and not page_id:
            page_id = self._parse_confluence_url(url)
            if not page_id:
                return [TextContent(type="text", text="Error: Could not extract page ID from URL")]

        if not page_id:
            return [TextContent(type="text", text="Error: Must provide either 'page_id' or 'url'")]

        # Get child pages
        children = self.confluence.get_page_child_by_type(
            page_id=page_id,
            type="page",
            start=0,
            limit=50
        )

        child_list = []
        for child in children:
            child_list.append({
                "id": child.get("id"),
                "title": child.get("title"),
                "url": f"{self.confluence.url}/wiki/pages/viewpage.action?pageId={child.get('id')}"
            })

        result = {
            "parent_page_id": page_id,
            "total_children": len(child_list),
            "children": child_list
        }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

async def main():
    """Main entry point for the MCP server."""
    logger.info("Starting Confluence MCP Server...")
    confluence_server = ConfluenceMCPServer()
    logger.info("Confluence MCP Server initialized with tools")

    # Run the server using stdio transport
    async with stdio_server() as (read_stream, write_stream):
        await confluence_server.server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="confluence-mcp-server",
                server_version="1.0.0",
                capabilities=confluence_server.server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())
