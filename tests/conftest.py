# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import asyncio
import logging

import slim_bindings
import pytest_asyncio

logger = logging.getLogger(__name__)


@pytest_asyncio.fixture(scope="function")
async def server(request):
    if not slim_bindings.is_initialized():
        tracing_config = slim_bindings.new_tracing_config()
        tracing_config.log_level = "info"
        slim_bindings.initialize_with_configs(
            runtime_config=slim_bindings.new_runtime_config(),
            tracing_config=tracing_config,
            service_config=[slim_bindings.new_service_config()],
        )

    service = slim_bindings.get_global_service()

    server_config = slim_bindings.new_insecure_server_config(request.param)
    await service.run_server_async(server_config)

    await asyncio.sleep(1)

    yield request.param

    service.stop_server(request.param)
