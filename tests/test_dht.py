import pytest

from magnet_scout import dht
from magnet_scout.dht import DHTBatchVerifier
from magnet_scout.models import TorrentResult, VerificationStatus

HASH = "0123456789abcdef0123456789abcdef01234567"


async def test_dht_discards_addresses_and_applies_only_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(dht, "_run_isolated", lambda hashes, timeout, limit: {HASH: 7})
    result = TorrentResult("Linux", f"magnet:?xt=urn:btih:{HASH}", HASH)

    await DHTBatchVerifier(timeout=3).verify_many([result])

    assert result.dht_attempted is True
    assert result.dht_peers == 7
    assert result.verified_peers == 7
    assert result.verification_status is VerificationStatus.VERIFIED_PEERS_ONLY
    assert not hasattr(result, "peer_addresses")


def test_dht_worker_has_hard_parent_deadline() -> None:
    with pytest.raises(TimeoutError, match="hard deadline"):
        dht._run_isolated([HASH], timeout=0.01, peer_limit=1)
