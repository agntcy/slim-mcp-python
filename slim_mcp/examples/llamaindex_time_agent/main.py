# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import asyncio
import json
import logging

import click
import slim_bindings
from dotenv import load_dotenv
from llama_index.core.agent.workflow import ReActAgent
from llama_index.llms.azure_openai import AzureOpenAI
from llama_index.llms.ollama import Ollama
from llama_index.tools.mcp import McpToolSpec
from mcp import ClientSession

from slim_mcp import create_local_app, create_client_streams

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# load .env file
load_dotenv()


async def amain(
    llm_type, llm_endpoint, llm_key, organization, namespace, mcp_server, city, config
):
    if llm_type == "azure":
        kwargs = {
            "engine": "gpt-4o-mini",
            "model": "gpt-4o-mini",
            "is_chat_model": True,
            "azure_endpoint": llm_endpoint,
            "api_key": llm_key,
            "api_version": "2024-08-01-preview",
        }
        llm = AzureOpenAI(**kwargs)
    elif llm_type == "ollama":
        kwargs = {
            "model": "llama3.2",
        }
        llm = Ollama(**kwargs)
    else:
        raise Exception("LLM type must be azure or ollama")

    logger.info("Starting SLIM client")

    # Create SLIM app
    client_name = slim_bindings.Name("org", "ns", "time-agent")
    client_app, connection_id = await create_local_app(client_name, config)

    logger.info("SLIM App created")

    # Set route to destination if we have a connection
    destination = slim_bindings.Name(organization, namespace, mcp_server)
    if connection_id is not None:
        await client_app.set_route_async(destination, connection_id)

    logger.info("SLIM route set")

    # Create MCP client session using standard transport pattern
    async with create_client_streams(client_app, destination) as (read, write):
        logger.info("Creating MCP client session")
        async with ClientSession(read, write) as mcp_session:
            logger.info("Creating MCP tool spec")

            await mcp_session.initialize()

            mcp_tool_spec = McpToolSpec(
                client=mcp_session,
            )

            tools = await mcp_tool_spec.to_tool_list_async()
            print(tools)

            agent = ReActAgent(llm=llm, tools=tools)

            response = await agent.run(
                user_msg=f"What is the current time in {city}?",
            )

            print(response)


class ClientConfigType(click.ParamType):
    """Custom click parameter type for parsing JSON and converting to ClientConfig."""

    name = "clientconfig"

    def convert(self, value, param, ctx):
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


@click.command(context_settings={"auto_envvar_prefix": "TIME_AGENT"})
@click.option("--llm-type", default="azure")
@click.option("--llm-endpoint", default=None)
@click.option("--llm-key", default=None)
@click.option("--mcp-server-organization", default="org")
@click.option("--mcp-server-namespace", default="ns")
@click.option("--mcp-server-name", default="time-server")
@click.option("--city", default="New York")
@click.option(
    "--config",
    default={
        "endpoint": "http://127.0.0.1:46357",
        "tls": {
            "insecure": True,
        },
    },
    type=ClientConfigType(),
    help="slim server configuration",
)
def main(
    llm_type,
    llm_endpoint,
    llm_key,
    mcp_server_organization,
    mcp_server_namespace,
    mcp_server_name,
    city,
    config,
):
    try:
        asyncio.run(
            amain(
                llm_type,
                llm_endpoint,
                llm_key,
                mcp_server_organization,
                mcp_server_namespace,
                mcp_server_name,
                city,
                config,
            )
        )
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt")
    except Exception as e:
        logger.error(f"Error: {e}")
        raise e
