from concurrent.futures import ThreadPoolExecutor
from protocol.operations import OperationJournal


def test_concurrent_retries_conflicts_and_identity_scope():
    journal = OperationJournal()
    effects = []
    def execute():
        effects.append(1)
        return {"success": True, "value": len(effects)}
    def call():
        return journal.execute(1, 'a', 'op', 'move', {'unit_id': 1}, execute)
    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(lambda _: call(), range(20)))
    assert len(effects) == 1
    assert all(r[0]['value'] == 1 for r in results)
    assert journal.execute(1, 'a', 'op', 'attack', {}, execute)[0]['error'] == 'operation_conflict'
    journal.execute(1, 'b', 'op', 'move', {}, execute)
    journal.execute(2, 'a', 'op', 'move', {}, execute)
    assert len(effects) == 3


def test_unknown_execution_is_not_repeated():
    journal = OperationJournal()
    def fail():
        raise RuntimeError('execution interrupted')
    import pytest
    with pytest.raises(RuntimeError):
        journal.execute(1, 'a', 'op', 'attack', {}, fail)
    assert journal.execute(1, 'a', 'op', 'attack', {}, fail)[0]['error'] == 'operation_outcome_unknown'
