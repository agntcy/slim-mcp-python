# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import asyncio
import datetime
import logging

import slim_bindings
import mcp.types as types
import pytest
from mcp import ClientSession
from mcp.server.lowlevel import Server

from slim_mcp import create_local_app, run_mcp_server, create_client_streams

# Configure logging
logger = logging.getLogger(__name__)

# Test configuration
TEST_ORG = "org"
TEST_NS = "default"
TEST_MCP_SERVER = "mcp1"
TEST_CLIENT_ID = "client1"


@pytest.fixture
def example_tool() -> types.Tool:
    """Create an example tool for testing."""
    return types.Tool(
        name="example",
        description="The most exemplar tool of the tools",
        inputSchema={
            "type": "object",
            "required": ["url"],
            "properties": {
                "url": {
                    "type": "string",
                    "description": "example URL input parameter",
                }
            },
        },
    )


@pytest.fixture
def mcp_app(example_tool: types.Tool) -> Server:
    """Create and configure an MCP server application."""
    app: Server = Server("example-server")

    @app.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [example_tool]

    return app


@pytest.mark.asyncio
async def test_mcp_client_server_connection(mcp_app):
    """Test basic MCP client-server connection and initialization."""
    # Create server app
    server_name = slim_bindings.Name(TEST_ORG, TEST_NS, TEST_MCP_SERVER)
    server_app, _ = await create_local_app(server_name)

    # Create client app
    client_name = slim_bindings.Name(TEST_ORG, TEST_NS, TEST_CLIENT_ID)
    client_app, _ = await create_local_app(client_name)

    # Start MCP server in background
    server_task = asyncio.create_task(run_mcp_server(server_app, mcp_app))

    try:
        # Give server time to start
        await asyncio.sleep(0.1)

        # Create client session using standard transport pattern
        destination = slim_bindings.Name(TEST_ORG, TEST_NS, TEST_MCP_SERVER)
        async with create_client_streams(client_app, destination) as (read, write):
            async with ClientSession(read, write) as session:
                # Test session initialization
                await session.initialize()
                logger.info(
                    f"Client session initialized at {datetime.datetime.now().isoformat()}"
                )

                # Test tool listing
                tools = await session.list_tools()
                assert tools is not None, "Failed to list tools"

                logger.info(f"Successfully retrieved tools: {tools}")
    finally:
        # Cleanup
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_mcp_client_server_reconnection(mcp_app):
    """Test client reconnection to server."""
    logger.info("Testing client reconnection...")

    # Create server app
    server_name = slim_bindings.Name(TEST_ORG, TEST_NS, TEST_MCP_SERVER)
    server_app, _ = await create_local_app(server_name)

    # Start MCP server in background
    server_task = asyncio.create_task(run_mcp_server(server_app, mcp_app))

    try:
        # Give server time to start
        await asyncio.sleep(0.1)

        destination = slim_bindings.Name(TEST_ORG, TEST_NS, TEST_MCP_SERVER)

        # First connection
        client_name1 = slim_bindings.Name(TEST_ORG, TEST_NS, TEST_CLIENT_ID)
        client_app1, _ = await create_local_app(client_name1)

        async with create_client_streams(client_app1, destination) as (read, write):
            async with ClientSession(read, write) as session:
                logger.info("First session initialized")
                await session.initialize()
                logger.info("First session completed successfully")

                tools = await session.list_tools()
                assert tools is not None, "Failed to list tools"
                logger.info(f"Successfully retrieved tools: {tools}")

        logger.info("Second connection")

        # Second connection with same client ID
        client_name2 = slim_bindings.Name(TEST_ORG, TEST_NS, TEST_CLIENT_ID)
        client_app2, _ = await create_local_app(client_name2)

        async with create_client_streams(client_app2, destination) as (read, write):
            async with ClientSession(read, write) as session:
                logger.info("Second session initialized")
                await session.initialize()
                logger.info("Second session completed successfully")

                tools = await session.list_tools()
                assert tools is not None, "Failed to list tools"
                logger.info(f"Successfully retrieved tools: {tools}")

        # Concurrent connections
        client_name3 = slim_bindings.Name(TEST_ORG, TEST_NS, f"{TEST_CLIENT_ID}_3")
        client_name4 = slim_bindings.Name(TEST_ORG, TEST_NS, f"{TEST_CLIENT_ID}_4")
        client_name5 = slim_bindings.Name(TEST_ORG, TEST_NS, f"{TEST_CLIENT_ID}_5")

        client_app3, _ = await create_local_app(client_name3)
        client_app4, _ = await create_local_app(client_name4)
        client_app5, _ = await create_local_app(client_name5)

        async with (
            create_client_streams(client_app3, destination) as (read1, write1),
            create_client_streams(client_app4, destination) as (read2, write2),
            create_client_streams(client_app5, destination) as (read3, write3),
        ):
            async with (
                ClientSession(read1, write1) as session1,
                ClientSession(read2, write2) as session2,
                ClientSession(read3, write3) as session3,
            ):
                logger.info("Concurrent sessions initialized")
                await session1.initialize()
                await session2.initialize()
                await session3.initialize()
                logger.info("Concurrent sessions completed successfully")

                tools1 = await session1.list_tools()
                assert tools1 is not None, "Failed to list tools"
                logger.info(f"Successfully retrieved tools: {tools1}")

                tools2 = await session2.list_tools()
                assert tools2 is not None, "Failed to list tools"
                logger.info(f"Successfully retrieved tools: {tools2}")

                tools3 = await session3.list_tools()
                assert tools3 is not None, "Failed to list tools"
                logger.info(f"Successfully retrieved tools: {tools3}")

    finally:
        # Cleanup
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass
