# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
MCP Client implementation using SLIM transport.

This module provides functions to create MCP client sessions over SLIM transport.
"""

import datetime
import logging
from contextlib import asynccontextmanager

import slim_bindings
import mcp.types as types
from slim_bindings.slim_bindings import SessionConfig, SessionType
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
import anyio
import asyncio

logger = logging.getLogger(__name__)


@asynccontextmanager
async def create_slim_session(
    slim_app: slim_bindings.App,
    destination: slim_bindings.Name,
    max_retries: int = 2,
    timeout: datetime.timedelta = datetime.timedelta(seconds=15),
):
    """
    Create a SLIM session to a destination.

    Args:
        slim_app: The SLIM app instance
        destination: The destination name to connect to
        max_retries: Maximum number of retries for messages
        timeout: Timeout for message delivery

    Yields:
        slim_bindings.Session: The created session
    """
    # Create session
    session_with_completion = await slim_app.create_session_async(
        config=SessionConfig(
            session_type=SessionType.POINT_TO_POINT,
            enable_mls=False,
            max_retries=max_retries,
            interval=timeout,
            metadata={},
        ),
        destination=destination,
    )

    # Wait for session establishment
    await session_with_completion.completion.wait_async()
    session = session_with_completion.session

    try:
        yield session
    finally:
        # Delete session when done
        completion = await slim_app.delete_session_async(session)
        await completion.wait_async()


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
                        extra={"message": received_msg.payload.decode()},
                    )

                    message = types.JSONRPCMessage.model_validate_json(
                        received_msg.payload.decode()
                    )
                    await read_stream_writer.send(message)
                except Exception as exc:
                    if "session channel closed" in str(exc):
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

            tg.create_task(force_termination())
    except* TerminateTaskGroup:
        pass


@asynccontextmanager
async def create_client_streams(
    slim_app: slim_bindings.App,
    destination: slim_bindings.Name,
    max_retries: int = 2,
    timeout: datetime.timedelta = datetime.timedelta(seconds=15),
):
    """
    Create MCP client streams using SLIM transport.

    This follows the standard MCP transport pattern of exposing read/write streams
    that the user wraps with ClientSession.

    Args:
        slim_app: The SLIM app instance
        destination: The destination name to connect to
        max_retries: Maximum number of retries for messages
        timeout: Timeout for message delivery

    Yields:
        tuple: (read_stream, write_stream) for MCP communication

    Example:
        ```python
        import slim_bindings
        from mcp import ClientSession
        from slim_mcp import create_local_app, create_client_streams

        # Create SLIM app
        name = slim_bindings.Name("org", "ns", "my-client")
        config = slim_bindings.new_insecure_client_config("http://localhost:46357")
        slim_app, conn_id = await create_local_app(name, config)

        # Set route to destination
        destination = slim_bindings.Name("org", "ns", "my-server")
        await slim_app.set_route_async(destination, conn_id)

        # Create MCP client session
        async with create_client_streams(slim_app, destination) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
        ```
    """
    async with create_slim_session(
        slim_app, destination, max_retries, timeout
    ) as session:
        logger.info("SLIM session established with destination %s", destination)
        async with create_mcp_streams(session) as (read_stream, write_stream):
            logger.info("MCP streams created over SLIM session")
            yield read_stream, write_stream
