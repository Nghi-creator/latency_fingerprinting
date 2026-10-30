"""Shards must preserve the entire inventory and reject partial configuration."""

from types import SimpleNamespace

import pytest

from . import sharding


def config(index=None, count=None, *, deselected=None):
    options = dict(shard_index=index, shard_count=count)
    return SimpleNamespace(
        getoption=options.__getitem__,
        hook=SimpleNamespace(pytest_deselected=lambda *, items: deselected.extend(items)),
    )


@pytest.mark.parametrize("index,count", [(None, 4), (0, None), (-1, 4), (4, 4), (0, 0), (0, -1)])
def test_invalid_shard_configuration_fails_instead_of_skipping_tests(index, count):
    with pytest.raises(pytest.UsageError):
        sharding.pytest_configure(config(index, count))


def test_opt_in_plugin_keeps_default_collection_unchanged():
    items = [SimpleNamespace(nodeid=f"test_example.py::test_case[{i}]") for i in range(200)]
    original = list(items)
    sharding.pytest_configure(config())
    sharding.pytest_collection_modifyitems(config(), items)
    assert items == original


@pytest.mark.parametrize("count", [1, 4, 7])
def test_shards_cover_each_node_once_and_preserve_order(count):
    original = [
        SimpleNamespace(nodeid=f"tests/test_example.py::test_case_{i // 2}[{i % 2}]")
        for i in range(2000)
    ]
    groups = []
    for index in range(count):
        items, removed = list(original), []
        selected_config = config(index, count, deselected=removed)
        sharding.pytest_configure(selected_config)
        sharding.pytest_collection_modifyitems(selected_config, items)
        assert len(items) + len(removed) == len(original)
        assert {item.nodeid for item in items}.isdisjoint(item.nodeid for item in removed)
        assert items == [item for item in original if item in items]
        groups.append([item.nodeid for item in items])
    flattened = [nodeid for group in groups for nodeid in group]
    assert len(flattened) == len(set(flattened)) == len(original)
    assert set(flattened) == {item.nodeid for item in original}
    assert all(groups)  # These representative inventories populate every shard.
    assert [sharding.shard_for(item.nodeid, count) for item in reversed(original)] == list(
        reversed([sharding.shard_for(item.nodeid, count) for item in original])
    )


def test_invalid_count_is_rejected():
    with pytest.raises(ValueError, match="positive"):
        sharding.shard_for("test.py::test", 0)


def test_parameter_id_order_does_not_change_ownership():
    names = (
        "tests/test.py::test_case[{'alpha', 'beta'}]",
        "tests/test.py::test_case[{'beta', 'alpha'}]",
        "tests/test.py::test_case[another generated ID]",
    )
    for count in (1, 4, 7):
        assert len({sharding.shard_for(name, count) for name in names}) == 1
