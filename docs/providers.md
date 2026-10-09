# Providers

Providers translate a source-specific response into `TorrentResult` objects. They never rank
results, mark provider claims as verified, or download torrent payloads.

## Included providers

| Name | Source | Notes |
| --- | --- | --- |
| `internet-archive` | Internet Archive advanced search and metadata APIs | Public collections; explicit-license filter enabled by default |
| `academic-torrents` | Academic Torrents public index | Research datasets and publications; index is cached locally |
| `fedora` | Fedora torrent metadata | Official Fedora release torrents |
| configurable name | Torznab-compatible API | Optional; trust and legality depend on the configured service |

The first three are enabled by default. Torznab endpoints are opt-in because they vary in quality,
policy, authentication, and content.

MagnetScout identifies automated HTTP traffic with a versioned User-Agent. Internet Archive
requests retry a `429 Too Many Requests` response only within a bounded attempt count, honor a
bounded `Retry-After` delay, and use limited concurrency. Provider failures remain isolated.

Internet Archive items must have a `licenseurl` field by default. Users can explicitly broaden a
search with `--include-unlicensed-ia`, but missing or present metadata is not a legal determination.
The adapter preserves available `license_url` and `rights` evidence for review.

Queries are sent to Internet Archive and configured Torznab endpoints. Academic Torrents publishes
an XML database specifically for local programmatic searching; MagnetScout caches that database.
The Fedora torrent catalog is also filtered locally after retrieval.

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
API keys are accepted only for HTTPS endpoints and are read from environment variables rather than
stored directly in configuration. The key is sent as a Torznab query parameter and can therefore
appear in logs maintained by the configured service or an intermediary. Users must trust and
administer their selected endpoint accordingly and should never include a real key in an issue,
shell transcript, fixture, or committed file.

Provider availability does not grant rights to a service, its metadata, or referenced content.
See [Licensing and external services](licensing.md) for the separation between MagnetScout's MIT
license and third-party terms.

Provider and product names are used only for identification. MagnetScout is not affiliated with or
endorsed by the listed services. Fedora is a trademark of Red Hat, Inc.; no Fedora logos are used.
