# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Core helper functions for creating SLIM apps and services.
"""

import logging

import slim_bindings

logger = logging.getLogger(__name__)


def setup_service(enable_opentelemetry: bool = False) -> slim_bindings.Service:
    """
    Initialize and configure the SLIM service.

    Args:
        enable_opentelemetry: Whether to enable OpenTelemetry tracing

    Returns:
        slim_bindings.Service: The configured global service instance

    Note:
        This function initializes the global SLIM service with default configurations.
        For full OpenTelemetry support, set OTEL environment variables.
    """
    # Initialize tracing and global state
    tracing_config = slim_bindings.new_tracing_config()
    runtime_config = slim_bindings.new_runtime_config()
    service_config = slim_bindings.new_service_config()

    tracing_config.log_level = "info"

    if enable_opentelemetry:
        # Note: OpenTelemetry configuration through config objects is complex
        # For now, we'll just initialize with default tracing
        # Users can set OTEL environment variables for full OTEL support
        pass

    slim_bindings.initialize_with_configs(
        tracing_config=tracing_config,
        runtime_config=runtime_config,
        service_config=[service_config],
    )

    # Get the global service instance
    service = slim_bindings.get_global_service()

    return service


async def create_local_app(
    local_name: slim_bindings.Name,
    slim_client_config: slim_bindings.ClientConfig | None = None,
    enable_opentelemetry: bool = False,
    shared_secret: str = "secretsecretsecretsecretsecretsecret",
) -> tuple[slim_bindings.App, int | None]:
    """
    Create a local SLIM app and optionally connect to an upstream server.

    Args:
        local_name: The name of the local app
        slim_client_config: Optional client configuration for connecting to upstream server
        enable_opentelemetry: Whether to enable OpenTelemetry
        shared_secret: Shared secret for authentication (must be at least 32 characters)

    Returns:
        tuple: (App instance, connection ID or None if no connection was made)

    Example:
        ```python
        import slim_bindings
        from slim_mcp import create_local_app

        # Create local app without upstream connection
        name = slim_bindings.Name("org", "ns", "my-app")
        app, conn_id = await create_local_app(name)

        # Create app with upstream connection
        config = slim_bindings.new_insecure_client_config("http://localhost:46357")
        app, conn_id = await create_local_app(name, config)

        # Use connection ID to set routes
        if conn_id is not None:
            destination = slim_bindings.Name("org", "ns", "target")
            await app.set_route_async(destination, conn_id)
        ```
    """
    service = setup_service(enable_opentelemetry=enable_opentelemetry)

    connection_id = None
    # Connect service to upstream server if config provided
    if slim_client_config is not None:
        logger.info(f"config: {slim_client_config}")
        try:
            connection_id = await service.connect_async(slim_client_config)
        except Exception as e:
            # Ignore "client already connected" errors
            if "client already connected" not in str(e):
                raise

        logger.info(
            f"Connected to {slim_client_config.endpoint} with connection_id: {connection_id}"
        )

    # Create local app with shared secret
    local_app = service.create_app_with_secret(local_name, shared_secret)
    logger.info(f"{local_app.id()} Created app")

    # Subscribe app to upstream server if connected
    if connection_id is not None:
        await local_app.subscribe_async(local_name, connection_id)

    return local_app, connection_id
