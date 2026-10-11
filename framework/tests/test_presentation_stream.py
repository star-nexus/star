from concurrent.futures import ThreadPoolExecutor

from framework.presentation import SnapshotMailbox


def test_slow_viewer_gets_owned_baseline_instead_of_dependent_delta():
    mailbox = SnapshotMailbox()
    first = {'kind': 'delta', 'sequence': 1, 'units': [{'id': '1'}]}
    latest = {'kind': 'snapshot', 'sequence': 2, 'units': [{'id': '2'}]}
    assert mailbox.offer(first, latest)
    first['units'].clear()
    assert mailbox.offer({'kind': 'delta', 'sequence': 2}, latest)
    latest['units'].clear()
    assert mailbox.take() == {'kind': 'snapshot', 'sequence': 2, 'units': [{'id': '2'}]}
    assert mailbox.resyncs == 1 and mailbox.take() is None
    mailbox.close()
    assert not mailbox.offer({}, {}) and mailbox.take() is None


def test_mailbox_concurrent_publish_and_read_remain_bounded():
    mailbox = SnapshotMailbox()
    def producer():
        for n in range(1000):
            mailbox.offer({'kind': 'delta', 'sequence': n}, {'kind': 'snapshot', 'sequence': n})
    with ThreadPoolExecutor(max_workers=2) as pool:
        future = pool.submit(producer)
        while not future.done():
            packet = mailbox.take()
            assert packet is None or 0 <= packet['sequence'] < 1000
        future.result()
    assert mailbox.take() in (None, {'kind': 'delta', 'sequence': 999}, {'kind': 'snapshot', 'sequence': 999})
