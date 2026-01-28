# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

# Core helper functions
from slim_mcp.helpers import create_local_app, setup_service

# Server-side functions
from slim_mcp.mcp_server import (
    run_mcp_server,
    create_mcp_streams as server_create_mcp_streams,
)

# Client-side functions
from slim_mcp.mcp_client import (
    create_client_streams,
    create_slim_session,
    create_mcp_streams as client_create_mcp_streams,
)

__all__ = [
    # Core helpers
    "create_local_app",
    "setup_service",
    # Server functions
    "run_mcp_server",
    "server_create_mcp_streams",
    # Client functions
    "create_client_streams",
    "create_slim_session",
    "client_create_mcp_streams",
]
