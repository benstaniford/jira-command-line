#!/usr/bin/env python3
"""
MCP Server for Confluence Integration

This server provides tools to interact with Confluence using the atlassian-python-api library.
It exposes various Confluence operations as MCP tools for document manipulation, search,
import/export, and attachment management.
"""

import asyncio
import json
import logging
import os
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

# Confluence imports
from atlassian import Confluence

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-confluence-server")

class ConfluenceMCPServer:
    def __init__(self):
        self.server = Server("confluence-mcp-server")
        self.confluence: Optional[Confluence] = None

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
                    description="Get a Confluence page by ID or title/space combination",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "page_id": {
                                "type": "string",
                                "description": "The page ID (optional if title and space provided)"
                            },
                            "title": {
                                "type": "string",
                                "description": "Page title (required if page_id not provided)"
                            },
                            "space": {
                                "type": "string",
                                "description": "Space key (required if page_id not provided)"
                            },
                            "expand": {
                                "type": "string",
                                "description": "Additional fields to expand (e.g., 'body.storage,version')",
                                "default": "body.storage,version"
                            }
                        }
                    }
                ),
                Tool(
                    name="create_page",
                    description="Create a new Confluence page",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "space": {
                                "type": "string",
                                "description": "Space key where the page will be created"
                            },
                            "title": {
                                "type": "string",
                                "description": "Page title"
                            },
                            "body": {
                                "type": "string",
                                "description": "Page content in Confluence storage format (HTML)"
                            },
                            "parent_id": {
                                "type": "string",
                                "description": "Parent page ID (optional)"
                            }
                        },
                        "required": ["space", "title", "body"]
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
                                "description": "The page ID to update"
                            },
                            "title": {
                                "type": "string",
                                "description": "New page title (optional)"
                            },
                            "body": {
                                "type": "string",
                                "description": "New page content in Confluence storage format (HTML)"
                            },
                            "minor_edit": {
                                "type": "boolean",
                                "description": "Whether this is a minor edit",
                                "default": False
                            }
                        },
                        "required": ["page_id", "body"]
                    }
                ),
                Tool(
                    name="delete_page",
                    description="Delete a Confluence page",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "page_id": {
                                "type": "string",
                                "description": "The page ID to delete"
                            }
                        },
                        "required": ["page_id"]
                    }
                ),
                Tool(
                    name="search",
                    description="Search for Confluence content using CQL (Confluence Query Language)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "cql": {
                                "type": "string",
                                "description": "CQL query string (e.g., 'type=page and space=DEV')"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results",
                                "default": 25
                            }
                        },
                        "required": ["cql"]
                    }
                ),
                Tool(
                    name="get_all_pages_from_space",
                    description="Get all pages from a specific Confluence space",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "space": {
                                "type": "string",
                                "description": "Space key"
                            },
                            "start": {
                                "type": "integer",
                                "description": "Start index for pagination",
                                "default": 0
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results",
                                "default": 100
                            }
                        },
                        "required": ["space"]
                    }
                ),
                Tool(
                    name="get_page_child_pages",
                    description="Get child pages of a specific page",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "page_id": {
                                "type": "string",
                                "description": "Parent page ID"
                            },
                            "start": {
                                "type": "integer",
                                "description": "Start index for pagination",
                                "default": 0
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results",
                                "default": 25
                            }
                        },
                        "required": ["page_id"]
                    }
                ),
                Tool(
                    name="export_page",
                    description="Export a Confluence page to PDF format",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "page_id": {
                                "type": "string",
                                "description": "The page ID to export"
                            },
                            "output_path": {
                                "type": "string",
                                "description": "Path where the PDF will be saved"
                            }
                        },
                        "required": ["page_id", "output_path"]
                    }
                ),
                Tool(
                    name="attach_file",
                    description="Attach a file to a Confluence page",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "page_id": {
                                "type": "string",
                                "description": "The page ID to attach to"
                            },
                            "file_path": {
                                "type": "string",
                                "description": "Path to the file to attach"
                            },
                            "comment": {
                                "type": "string",
                                "description": "Comment for the attachment (optional)"
                            }
                        },
                        "required": ["page_id", "file_path"]
                    }
                ),
                Tool(
                    name="get_attachments",
                    description="Get all attachments from a Confluence page",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "page_id": {
                                "type": "string",
                                "description": "The page ID"
                            }
                        },
                        "required": ["page_id"]
                    }
                ),
                Tool(
                    name="download_attachment",
                    description="Download an attachment from a Confluence page",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "page_id": {
                                "type": "string",
                                "description": "The page ID"
                            },
                            "filename": {
                                "type": "string",
                                "description": "Attachment filename"
                            },
                            "output_path": {
                                "type": "string",
                                "description": "Path where the file will be saved"
                            }
                        },
                        "required": ["page_id", "filename", "output_path"]
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
                                "description": "The space key"
                            }
                        },
                        "required": ["space_key"]
                    }
                ),
                Tool(
                    name="get_all_spaces",
                    description="Get all Confluence spaces",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "start": {
                                "type": "integer",
                                "description": "Start index for pagination",
                                "default": 0
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results",
                                "default": 25
                            }
                        }
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
                elif name == "delete_page":
                    return await self._delete_page(arguments)
                elif name == "search":
                    return await self._search(arguments)
                elif name == "get_all_pages_from_space":
                    return await self._get_all_pages_from_space(arguments)
                elif name == "get_page_child_pages":
                    return await self._get_page_child_pages(arguments)
                elif name == "export_page":
                    return await self._export_page(arguments)
                elif name == "attach_file":
                    return await self._attach_file(arguments)
                elif name == "get_attachments":
                    return await self._get_attachments(arguments)
                elif name == "download_attachment":
                    return await self._download_attachment(arguments)
                elif name == "get_space":
                    return await self._get_space(arguments)
                elif name == "get_all_spaces":
                    return await self._get_all_spaces(arguments)
                else:
                    raise ValueError(f"Unknown tool: {name}")

            except Exception as e:
                logger.error(f"Error in tool {name}: {e}")
                return [TextContent(type="text", text=f"Error: {str(e)}")]

    async def _ensure_confluence_initialized(self):
        """Ensure Confluence connection is initialized."""
        if self.confluence is None:
            # Get credentials from environment variables
            email = os.getenv("CONFLUENCE_EMAIL")
            api_key = os.getenv("CONFLUENCE_API_KEY")
            url = os.getenv("CONFLUENCE_URL")

            if not email or not api_key:
                raise ValueError(
                    "CONFLUENCE_EMAIL and CONFLUENCE_API_KEY environment variables must be set"
                )

            if not url:
                raise ValueError("CONFLUENCE_URL environment variable must be set")

            self.confluence = Confluence(
                url=url,
                username=email,
                password=api_key,
                cloud=True
            )
            logger.info(f"Initialized Confluence connection for {url}")

    async def _get_page(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Get a Confluence page by ID or title/space."""
        page_id = arguments.get("page_id")
        title = arguments.get("title")
        space = arguments.get("space")
        expand = arguments.get("expand", "body.storage,version")

        if page_id:
            page = self.confluence.get_page_by_id(page_id, expand=expand)
        elif title and space:
            page = self.confluence.get_page_by_title(space=space, title=title, expand=expand)
        else:
            raise ValueError("Either page_id or both title and space must be provided")

        result = {
            "id": page["id"],
            "type": page["type"],
            "status": page["status"],
            "title": page["title"],
            "space": page["space"]["key"],
            "version": page["version"]["number"],
            "body": page.get("body", {}).get("storage", {}).get("value", ""),
            "url": page["_links"]["webui"]
        }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _create_page(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Create a new Confluence page."""
        space = arguments["space"]
        title = arguments["title"]
        body = arguments["body"]
        parent_id = arguments.get("parent_id")

        result = self.confluence.create_page(
            space=space,
            title=title,
            body=body,
            parent_id=parent_id
        )

        response = {
            "id": result["id"],
            "title": result["title"],
            "space": result["space"]["key"],
            "version": result["version"]["number"],
            "url": result["_links"]["webui"],
            "message": f"Successfully created page '{title}'"
        }

        return [TextContent(type="text", text=json.dumps(response, indent=2))]

    async def _update_page(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Update an existing Confluence page."""
        page_id = arguments["page_id"]
        body = arguments["body"]
        title = arguments.get("title")
        minor_edit = arguments.get("minor_edit", False)

        # Get current page to get version and title
        current_page = self.confluence.get_page_by_id(page_id, expand="version")
        current_title = title if title else current_page["title"]
        current_version = current_page["version"]["number"]

        result = self.confluence.update_page(
            page_id=page_id,
            title=current_title,
            body=body,
            minor_edit=minor_edit
        )

        response = {
            "id": result["id"],
            "title": result["title"],
            "version": result["version"]["number"],
            "previous_version": current_version,
            "url": result["_links"]["webui"],
            "message": f"Successfully updated page '{current_title}'"
        }

        return [TextContent(type="text", text=json.dumps(response, indent=2))]

    async def _delete_page(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Delete a Confluence page."""
        page_id = arguments["page_id"]

        # Get page info before deletion
        page = self.confluence.get_page_by_id(page_id)
        title = page["title"]

        self.confluence.remove_page(page_id)

        result = {
            "page_id": page_id,
            "title": title,
            "message": f"Successfully deleted page '{title}'"
        }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _search(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Search for Confluence content using CQL."""
        cql = arguments["cql"]
        limit = arguments.get("limit", 25)

        results = self.confluence.cql(cql, limit=limit)

        items = []
        for item in results.get("results", []):
            items.append({
                "id": item.get("content", {}).get("id"),
                "type": item.get("content", {}).get("type"),
                "title": item.get("title"),
                "space": item.get("content", {}).get("space", {}).get("key"),
                "url": item.get("url"),
                "excerpt": item.get("excerpt", "")
            })

        response = {
            "total_results": results.get("totalSize", 0),
            "results": items
        }

        return [TextContent(type="text", text=json.dumps(response, indent=2))]

    async def _get_all_pages_from_space(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Get all pages from a specific space."""
        space = arguments["space"]
        start = arguments.get("start", 0)
        limit = arguments.get("limit", 100)

        pages = self.confluence.get_all_pages_from_space(
            space=space,
            start=start,
            limit=limit,
            expand="version"
        )

        results = []
        for page in pages:
            results.append({
                "id": page["id"],
                "title": page["title"],
                "type": page["type"],
                "status": page["status"],
                "version": page["version"]["number"]
            })

        response = {
            "space": space,
            "count": len(results),
            "pages": results
        }

        return [TextContent(type="text", text=json.dumps(response, indent=2))]

    async def _get_page_child_pages(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Get child pages of a specific page."""
        page_id = arguments["page_id"]
        start = arguments.get("start", 0)
        limit = arguments.get("limit", 25)

        children = self.confluence.get_page_child_by_type(
            page_id=page_id,
            type="page",
            start=start,
            limit=limit
        )

        results = []
        for child in children:
            results.append({
                "id": child["id"],
                "title": child["title"],
                "type": child["type"],
                "status": child["status"]
            })

        response = {
            "parent_id": page_id,
            "count": len(results),
            "children": results
        }

        return [TextContent(type="text", text=json.dumps(response, indent=2))]

    async def _export_page(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Export a Confluence page to PDF."""
        page_id = arguments["page_id"]
        output_path = arguments["output_path"]

        # Get page info
        page = self.confluence.get_page_by_id(page_id)
        title = page["title"]

        # Export as PDF
        pdf_content = self.confluence.get_page_as_pdf(page_id)

        # Write to file
        with open(output_path, "wb") as f:
            f.write(pdf_content)

        result = {
            "page_id": page_id,
            "title": title,
            "output_path": output_path,
            "message": f"Successfully exported page '{title}' to {output_path}"
        }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _attach_file(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Attach a file to a Confluence page."""
        page_id = arguments["page_id"]
        file_path = arguments["file_path"]
        comment = arguments.get("comment", "")

        if not os.path.exists(file_path):
            raise ValueError(f"File not found: {file_path}")

        result = self.confluence.attach_file(
            filename=file_path,
            page_id=page_id,
            comment=comment
        )

        response = {
            "page_id": page_id,
            "filename": os.path.basename(file_path),
            "comment": comment,
            "message": f"Successfully attached {os.path.basename(file_path)} to page"
        }

        return [TextContent(type="text", text=json.dumps(response, indent=2))]

    async def _get_attachments(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Get all attachments from a Confluence page."""
        page_id = arguments["page_id"]

        attachments = self.confluence.get_attachments_from_content(page_id)

        results = []
        for attachment in attachments.get("results", []):
            results.append({
                "id": attachment["id"],
                "title": attachment["title"],
                "type": attachment["type"],
                "mediaType": attachment.get("metadata", {}).get("mediaType"),
                "fileSize": attachment.get("extensions", {}).get("fileSize"),
                "download_url": attachment["_links"]["download"]
            })

        response = {
            "page_id": page_id,
            "count": len(results),
            "attachments": results
        }

        return [TextContent(type="text", text=json.dumps(response, indent=2))]

    async def _download_attachment(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Download an attachment from a Confluence page."""
        page_id = arguments["page_id"]
        filename = arguments["filename"]
        output_path = arguments["output_path"]

        # Download the attachment
        content = self.confluence.download_attachments_from_page(
            page_id=page_id,
            filename=filename
        )

        # Write to file
        with open(output_path, "wb") as f:
            f.write(content)

        result = {
            "page_id": page_id,
            "filename": filename,
            "output_path": output_path,
            "message": f"Successfully downloaded {filename} to {output_path}"
        }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _get_space(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Get information about a Confluence space."""
        space_key = arguments["space_key"]

        space = self.confluence.get_space(space_key, expand="description.plain,homepage")

        result = {
            "id": space["id"],
            "key": space["key"],
            "name": space["name"],
            "type": space["type"],
            "description": space.get("description", {}).get("plain", {}).get("value", ""),
            "homepage_id": space.get("homepage", {}).get("id"),
            "url": space["_links"]["webui"]
        }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _get_all_spaces(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """Get all Confluence spaces."""
        start = arguments.get("start", 0)
        limit = arguments.get("limit", 25)

        spaces = self.confluence.get_all_spaces(start=start, limit=limit)

        results = []
        for space in spaces.get("results", []):
            results.append({
                "id": space["id"],
                "key": space["key"],
                "name": space["name"],
                "type": space["type"]
            })

        response = {
            "count": len(results),
            "spaces": results
        }

        return [TextContent(type="text", text=json.dumps(response, indent=2))]

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
