"""Shared fixtures.

`RemoteContext` is `ContextVar`-backed process state, so tests that touch it
reset it rather than inheriting whatever the previous test left behind.
"""

import pytest

from rotk_agent.core.bridge import RemoteContext
from rotk_agent.core.config import LLMConfig
from rotk_agent.core.stats import ErrorStatsCollector


@pytest.fixture
def stats():
    return ErrorStatsCollector()


@pytest.fixture
def config():
    return LLMConfig(
        provider="fake",
        model_id="fake-model",
        api_key="EMPTY",
        base_url="fake://local",
        max_tokens=512,
        enable_thinking=False,
    )


@pytest.fixture
def clean_remote_context():
    """Give the test an empty status and id_map."""
    RemoteContext.set_status({})
    RemoteContext.set_id_map({})
    yield RemoteContext
    RemoteContext.set_status({})
    RemoteContext.set_id_map({})
