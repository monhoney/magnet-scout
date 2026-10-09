"""Public API for MagnetScout."""

from magnet_scout._version import __version__
from magnet_scout.magnets import InvalidMagnet, ParsedMagnet, parse_magnet
from magnet_scout.models import Health, SearchReport, TorrentResult, VerificationStatus
from magnet_scout.service import SearchService, merge_results

__all__ = [
    "Health",
    "InvalidMagnet",
    "ParsedMagnet",
    "SearchReport",
    "SearchService",
    "TorrentResult",
    "VerificationStatus",
    "__version__",
    "merge_results",
    "parse_magnet",
]
