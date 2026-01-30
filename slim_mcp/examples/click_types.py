# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Common utilities for SLIM-MCP examples.

This module provides shared utilities used across examples, including
click parameter types for configuration parsing.
"""

import json

import click
import slim_bindings


class ClientConfigType(click.ParamType):
    """
    Custom click parameter type for parsing JSON and converting to ClientConfig.

    This allows click options to accept either:
    - A dict (when used as default value)
    - A JSON string (when provided via CLI or environment variable)

    And converts them to slim_bindings.ClientConfig objects.

    Example:
        ```python
        @click.option(
            "--config",
            default={
                "endpoint": "http://127.0.0.1:46357",
                "tls": {"insecure": True},
            },
            type=ClientConfigType(),
        )
        def main(config):
            # config is a slim_bindings.ClientConfig object
            pass
        ```
    """

    name = "clientconfig"

    def convert(self, value, param, ctx):
        """
        Convert a dict or JSON string to a ClientConfig object.

        Args:
            value: Either a dict or JSON string
            param: The click parameter (unused)
            ctx: The click context (unused)

        Returns:
            slim_bindings.ClientConfig: The parsed configuration

        Raises:
            click.BadParameter: If the value is not valid JSON
        """
        # Handle default dict value
        if isinstance(value, dict):
            json_data = value
        else:
            try:
                json_data = json.loads(value)
            except json.JSONDecodeError:
                self.fail(f"{value} is not valid JSON", param, ctx)

        # If only endpoint is provided and tls.insecure is True, use the helper
        if (
            "endpoint" in json_data
            and "tls" in json_data
            and json_data["tls"].get("insecure", False)
            and len(json_data) == 2
            and len(json_data["tls"]) == 1
        ):
            return slim_bindings.new_insecure_client_config(json_data["endpoint"])

        # Otherwise, build the config manually
        # Start with insecure config as base
        config = slim_bindings.new_insecure_client_config(json_data["endpoint"])

        # Override TLS settings if provided
        if "tls" in json_data:
            tls_data = json_data["tls"]
            config.tls = slim_bindings.TlsClientConfig(
                insecure=tls_data.get("insecure", False),
                insecure_skip_verify=tls_data.get("insecure_skip_verify", False),
                source=slim_bindings.TlsSource.NONE(),
                ca_source=slim_bindings.CaSource.NONE(),
                include_system_ca_certs_pool=True,
                tls_version="tls1.3",
            )

        # Set optional fields
        if "origin" in json_data:
            config.origin = json_data["origin"]
        if "server_name" in json_data:
            config.server_name = json_data["server_name"]
        if "compression" in json_data:
            config.compression = slim_bindings.CompressionType[json_data["compression"]]
        if "rate_limit" in json_data:
            config.rate_limit = json_data["rate_limit"]

        return config
