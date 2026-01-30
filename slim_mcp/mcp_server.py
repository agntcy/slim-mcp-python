# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
MCP Server implementation using SLIM transport.

This module provides a simple function to run an MCP server over SLIM transport.
"""

import asyncio
import datetime
import logging
from contextlib import asynccontextmanager

import slim_bindings
import mcp.types as types
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from mcp.server.lowlevel import Server
import anyio

logger = logging.getLogger(__name__)


@asynccontextmanager
async def create_mcp_streams(session: slim_bindings.Session):
    """
    Create MCP-compatible read/write streams from a SLIM session.

    Args:
        session: SLIM session to wrap with streams

    Yields:
        tuple: (read_stream, write_stream) for MCP communication
    """
    # Initialize streams
    read_stream: MemoryObjectReceiveStream[types.JSONRPCMessage | Exception]
    read_stream_writer: MemoryObjectSendStream[types.JSONRPCMessage | Exception]

    write_stream: MemoryObjectSendStream[types.JSONRPCMessage]
    write_stream_reader: MemoryObjectReceiveStream[types.JSONRPCMessage]

    read_stream_writer, read_stream = anyio.create_memory_object_stream(0)
    write_stream, write_stream_reader = anyio.create_memory_object_stream(0)

    class TerminateTaskGroup(Exception):
        pass

    async def slim_reader(session: slim_bindings.Session):
        try:
            while True:
                try:
                    received_msg = await session.get_message_async(timeout=None)
                    logger.debug(
                        "Received message",
                        extra={"payload": received_msg.payload.decode()},
                    )

                    message = types.JSONRPCMessage.model_validate_json(
                        received_msg.payload.decode()
                    )
                    await read_stream_writer.send(message)
                except Exception as exc:
                    # The client closes the session when it wants to
                    # terminate the session, raise TerminateTaskGroup to
                    # cancel the task group and all the streams.
                    if "session closed" in str(exc):
                        raise TerminateTaskGroup()

                    logger.error("Error receiving message", exc_info=True)
                    await read_stream_writer.send(exc)
                    break
        finally:
            await read_stream_writer.aclose()

    async def slim_writer(session: slim_bindings.Session):
        try:
            async for message in write_stream_reader:
                try:
                    json_str = message.model_dump_json(by_alias=True, exclude_none=True)
                    logger.debug("Sending message", extra={"mcp_message": json_str})
                    completion = await session.publish_async(
                        json_str.encode(), payload_type=None, metadata=None
                    )
                    await completion.wait_async()
                except Exception:
                    logger.error("Error sending message", exc_info=True)
                    raise
        finally:
            await write_stream_reader.aclose()

    async def force_termination():
        raise TerminateTaskGroup()

    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(slim_reader(session))
            tg.create_task(slim_writer(session))

            yield read_stream, write_stream

            # Cancel the task group when the context manager hands back
            # control indicating the consumer is done.
            tg.create_task(force_termination())
    except* TerminateTaskGroup:
        pass


async def run_mcp_server(
    slim_app: slim_bindings.App,
    mcp_app: Server,
    session_timeout: datetime.timedelta | None = None,
):
    """
    Run an MCP server using SLIM transport.

    This function listens for incoming SLIM sessions and handles each one by:
    1. Creating MCP-compatible streams from the session
    2. Running the MCP app with those streams

    Args:
        slim_app: The SLIM app instance to listen for sessions
        mcp_app: The MCP server app to handle requests
        session_timeout: Optional timeout for listening for sessions

    Example:
        ```python
        from mcp.server.lowlevel import Server
        import slim_bindings
        from slim_mcp import create_local_app, run_mcp_server

        # Create MCP server
        mcp_app = Server("my-server")

        @mcp_app.list_tools()
        async def list_tools():
            return [...]

        # Create SLIM app
        name = slim_bindings.Name("org", "ns", "my-server")
        slim_app, _ = await create_local_app(name)

        # Run the server
        await run_mcp_server(slim_app, mcp_app)
        ```
    """
    logger.info(
        f"MCP server {slim_app.name()}:{slim_app.id()} listening for sessions..."
    )

    while True:
        try:
            # Listen for incoming session
            session = await slim_app.listen_for_session_async(timeout=session_timeout)
            logger.info(f"New session: {session.session_id}")

            # Handle session in background task
            async def handle_session():
                try:
                    async with create_mcp_streams(session) as (
                        read_stream,
                        write_stream,
                    ):
                        await mcp_app.run(
                            read_stream,
                            write_stream,
                            mcp_app.create_initialization_options(),
                        )
                except Exception as e:
                    logger.error(
                        f"Error handling session {session.session_id}: {e}",
                        exc_info=True,
                    )

            # Start session handler as background task
            asyncio.create_task(handle_session())

        except Exception as e:
            logger.error(f"Error accepting session: {e}", exc_info=True)
            # Continue listening for more sessions
