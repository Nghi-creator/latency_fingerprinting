"""Opt-in deterministic partitioning; parameter cases stay with their test function."""

import hashlib

import pytest


def shard_for(nodeid, count):
    if count < 1:
        raise ValueError("shard count must be positive")
    # Parameter IDs can contain set reprs whose order varies between processes.
    # Hash the stable file/class/function prefix so those cases cannot disappear
    # or run twice when different runners collect the same parametrized test.
    owner = nodeid.split("[", 1)[0]
    return int.from_bytes(hashlib.sha256(owner.encode("utf-8")).digest(), "big") % count


def pytest_addoption(parser):
    group = parser.getgroup("ci sharding")
    group.addoption("--shard-index", type=int, default=None)
    group.addoption("--shard-count", type=int, default=None)


def pytest_configure(config):
    index, count = config.getoption("shard_index"), config.getoption("shard_count")
    if (index is None) != (count is None) or (
        index is not None and (count < 1 or not 0 <= index < count)
    ):
        raise pytest.UsageError("supply both shard options with 0 <= index < count")


def pytest_collection_modifyitems(config, items):
    index, count = config.getoption("shard_index"), config.getoption("shard_count")
    if index is None:
        return
    selected, deselected = [], []
    for item in items:
        (selected if shard_for(item.nodeid, count) == index else deselected).append(item)
    config.hook.pytest_deselected(items=deselected)
    items[:] = selected
