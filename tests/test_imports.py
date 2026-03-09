# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import pytest


def test_slim_bindings_import_fails():
    with pytest.raises(ImportError):
        from slim_bindings.slim_bindings import SessionConfig, SessionType  # noqa: F401


def test_slim_bindings_import_succeeds():
    from slim_bindings import SessionConfig, SessionType

    assert SessionConfig is not None
    assert SessionType is not None
