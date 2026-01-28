# SLIM-MCP Integration

Leverage SLIM as a transport mechanism for MCP, enabling efficient load balancing
and dynamic discovery across MCP servers.

## Installation

```bash
pip install slim-mcp
```

## Overview

SLIM-MCP provides a seamless integration between SLIM (Secure Low-Latency
Interactive Messaging) and MCP (Model Context Protocol), allowing you to:

- Create MCP servers that can be discovered and accessed through SLIM
- Connect MCP clients to servers using SLIM as the transport layer
- Handle multiple concurrent sessions
- Leverage SLIM's load balancing and service discovery capabilities

## Quick Start

### Server Setup

```python
import asyncio
import slim_bindings
from mcp.server.lowlevel import Server
import mcp.types as types
from slim_mcp import create_local_app, run_mcp_server

# Create an MCP server application
mcp_app = Server("example-server")

# Define your tools
@mcp_app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="example",
            description="An example tool",
            inputSchema={
                "type": "object",
                "required": ["url"],
                "properties": {
                    "url": {"type": "string", "description": "URL parameter"}
                },
            },
        )
    ]

async def main():
    # Create SLIM app
    name = slim_bindings.Name("org", "namespace", "server-name")
    slim_app, _ = await create_local_app(name)

    # Run MCP server
    await run_mcp_server(slim_app, mcp_app)

asyncio.run(main())
```

### Client Setup

```python
import asyncio
import slim_bindings
from mcp import ClientSession
from slim_mcp import create_local_app, create_client_streams

async def main():
    # Create SLIM app
    client_name = slim_bindings.Name("org", "namespace", "client-id")
    client_app, _ = await create_local_app(client_name)

    # Connect to server using standard MCP transport pattern
    destination = slim_bindings.Name("org", "namespace", "server-name")
    async with create_client_streams(client_app, destination) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the session
            await session.initialize()

            # List available tools
            tools = await session.list_tools()
            print(f"Available tools: {tools}")

asyncio.run(main())
```

### Client with Upstream Connection

When connecting through a SLIM gateway or upstream server:

```python
import asyncio
import slim_bindings
from mcp import ClientSession
from slim_mcp import create_local_app, create_client_streams

async def main():
    # Create SLIM app with upstream connection
    client_name = slim_bindings.Name("org", "namespace", "client-id")
    config = slim_bindings.new_insecure_client_config("http://127.0.0.1:46357")
    client_app, connection_id = await create_local_app(client_name, config)

    # Set route to destination through upstream connection
    destination = slim_bindings.Name("org", "namespace", "server-name")
    if connection_id is not None:
        await client_app.set_route_async(destination, connection_id)

    # Connect to server
    async with create_client_streams(client_app, destination) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print(f"Available tools: {tools}")

asyncio.run(main())
```

## API Reference

### Core Functions

#### `create_local_app(name, config=None, enable_opentelemetry=False, shared_secret=...)`

Create a local SLIM app and optionally connect to an upstream server.

**Parameters:**
- `name` (slim_bindings.Name): The name of the local app
- `config` (slim_bindings.ClientConfig | None): Optional upstream server configuration
- `enable_opentelemetry` (bool): Enable OpenTelemetry tracing
- `shared_secret` (str): Shared secret for authentication (min 32 characters)

**Returns:** `tuple[slim_bindings.App, int | None]` - The app and optional connection ID

**Example:**
```python
# Local app without upstream
name = slim_bindings.Name("org", "ns", "my-app")
app, _ = await create_local_app(name)

# App with upstream connection
config = slim_bindings.new_insecure_client_config("http://localhost:46357")
app, conn_id = await create_local_app(name, config)
```

### Server Functions

#### `run_mcp_server(slim_app, mcp_app, session_timeout=None)`

Run an MCP server that listens for SLIM sessions and handles MCP requests.

**Parameters:**
- `slim_app` (slim_bindings.App): The SLIM app instance
- `mcp_app` (mcp.server.lowlevel.Server): The MCP server instance
- `session_timeout` (datetime.timedelta | None): Optional timeout for listening

**Example:**
```python
from mcp.server.lowlevel import Server
import slim_bindings
from slim_mcp import create_local_app, run_mcp_server

mcp_app = Server("my-server")

# Define tools...
@mcp_app.list_tools()
async def list_tools():
    return [...]

# Create and run
name = slim_bindings.Name("org", "ns", "my-server")
slim_app, _ = await create_local_app(name)
await run_mcp_server(slim_app, mcp_app)
```

### Client Functions

#### `create_client_streams(slim_app, destination, max_retries=2, timeout=timedelta(seconds=15))`

Create MCP client streams using SLIM transport. This follows the standard MCP transport pattern.

**Parameters:**
- `slim_app` (slim_bindings.App): The SLIM app instance
- `destination` (slim_bindings.Name): The destination name to connect to
- `max_retries` (int): Maximum number of retries for messages
- `timeout` (datetime.timedelta): Timeout for message delivery

**Yields:** `tuple[ReadStream, WriteStream]` - MCP-compatible read/write streams

**Example:**
```python
from mcp import ClientSession
import slim_bindings
from slim_mcp import create_local_app, create_client_streams

name = slim_bindings.Name("org", "ns", "client")
client_app, _ = await create_local_app(name)

destination = slim_bindings.Name("org", "ns", "server")
async with create_client_streams(client_app, destination) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
```

### Configuration

#### Creating Client Configurations

Use slim_bindings helper functions to create configurations:

```python
import slim_bindings

# Insecure connection (for development)
config = slim_bindings.new_insecure_client_config("http://localhost:46357")

# Custom configuration
from slim_mcp.examples.mcp_server_time.server import ClientConfigType
config_type = ClientConfigType()
config = config_type.convert({
    "endpoint": "http://localhost:46357",
    "tls": {"insecure": True}
}, None, None)
```

## Features

- **Standard MCP Transport Pattern**: Follows the same pattern as stdio, SSE, and WebSocket transports
- **Simple Functional API**: Clean functions instead of complex class hierarchies
- **Automatic Session Management**: Handles session lifecycle and cleanup
- **Concurrent Sessions**: Support for multiple concurrent sessions
- **TLS Support**: Built-in support for secure connections
- **Dynamic Discovery**: Leverage SLIM's service discovery capabilities
- **Load Balancing**: Utilize SLIM's load balancing features
- **Connection Routing**: Set routes to destinations through upstream connections

## Examples

Check out the `slim_mcp/examples` directory for complete examples:

- **MCP Time Server**: A server that provides time and timezone conversion tools
- **LlamaIndex Agent**: A client that uses LlamaIndex to interact with MCP servers

## Error Handling

The library provides comprehensive error handling and logging. All operations
are wrapped with proper cleanup to ensure resources are released.

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("slim_mcp")
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

Apache-2.0

