# Providers

Providers translate a source-specific response into `TorrentResult` objects. They never rank
results, mark provider claims as verified, or download torrent payloads.

## Included providers

| Name | Source | Notes |
| --- | --- | --- |
| `internet-archive` | Internet Archive advanced search and metadata APIs | Public collections; optional subject and explicit-license filters |
| `academic-torrents` | Academic Torrents public index | Research datasets and publications; index is cached locally |
| `fedora` | Fedora torrent metadata | Official Fedora release torrents |
| configurable name | Torznab-compatible API | Optional; trust and legality depend on the configured service |

The first three are enabled by default. Torznab endpoints are opt-in because they vary in quality,
policy, authentication, and content.

## Interface

```python
from typing import Protocol

from magnet_scout.models import TorrentResult


class SearchProvider(Protocol):
    name: str

    async def search(self, query: str, limit: int) -> list[TorrentResult]: ...
```

A provider should:

1. Use a structured, documented endpoint where possible.
2. Apply the supplied result limit and the shared HTTP client's timeout.
3. Produce a valid magnet URI and place the source name in `providers`.
4. Put source pages in `provider_urls`, not arbitrary download destinations.
5. Treat seed and leech counts as reported data only.
6. Leave unavailable values as `None`.
7. Include offline fixtures and tests for success, malformed data, and server failure.

Register a default provider in `providers/registry.py`. A provider exception is deliberately
isolated by `SearchService`; do not catch broad exceptions merely to return an empty list.

## Torznab configuration

Create `${XDG_CONFIG_HOME:-~/.config}/magnet-scout/config.toml`:

```toml
[[torznab]]
name = "my-index"
url = "https://example.invalid/api"
api_key_env = "MY_INDEX_API_KEY"
```

Then export the key and select the configured provider:

```console
export MY_INDEX_API_KEY='...'
magnet-scout search example --provider my-index
```

MagnetScout does not endorse or determine the legality of a configured Torznab source.
