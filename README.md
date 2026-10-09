# MagnetScout

MagnetScout is a lightweight Python CLI and library for discovering BitTorrent metadata from
pluggable providers, normalizing magnet links, checking current swarm signals, and ranking useful
results. It never downloads torrent payloads or sends results to a BitTorrent client.

MagnetScout is intended for public, freely licensed, and otherwise lawfully distributed content.
Metadata is informative rather than a legal determination; users remain responsible for deciding
whether they may access a result.

## Status

The project is alpha software. Provider availability and swarm observations can change at any
time, and a healthy score does not guarantee a successful download.

## Install

MagnetScout requires Python 3.11 or newer.

```console
python -m pip install magnet-scout
```

To install the development version from a checkout:

```console
python -m pip install -e .
```

## CLI

```console
magnet-scout search ubuntu
magnet-scout search ubuntu --top 10
magnet-scout search ubuntu --verify --top 10
magnet-scout search ubuntu --verify --min-verified-seeders 3
magnet-scout search ubuntu --json
magnet-scout search dataset --provider academic-torrents
magnet-scout search archive-query --include-unlicensed-ia
```

The default providers are Internet Archive, Academic Torrents, and Fedora. Provider failures are
reported independently, so one unavailable source does not discard results from the others.
Internet Archive results require explicit provider-supplied license metadata by default. The
`--include-unlicensed-ia` option broadens discovery but does not establish that an item may legally
be accessed or redistributed.

`--verify` performs bounded tracker and web-seed observations without requesting payload pieces.
A provider's reported seeder count remains separate from independently observed tracker values.

## Network privacy

Searches sent to Internet Archive disclose the query to Internet Archive. A configured Torznab
service receives the query and any API key required by that service. Academic Torrents and Fedora
catalogs are searched locally after their public indexes are fetched.

`--verify` contacts tracker and web-seed endpoints supplied by torrent metadata. Those third-party
operators can observe the user's public IP address, request time, and requested info hash or URL.
MagnetScout does not log full peer addresses, but it cannot prevent remote services from keeping
their own logs. Verification is therefore disabled unless explicitly requested.

## Python API

```python
from magnet_scout import parse_magnet

magnet = parse_magnet("magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&dn=Example")
print(magnet.info_hash)
print(magnet.canonical_uri)
```

Provider integration uses the asynchronous `SearchProvider` protocol. See
[the provider documentation](https://github.com/monhoney/magnet-scout/blob/main/docs/providers.md)
for a complete example.

## Evidence, not guarantees

- `reported_seeders` is untrusted metadata supplied by a provider.
- `verified_seeders` is a recent tracker observation when the tracker supports scraping.
- `UNKNOWN` means there was not enough independent evidence. It does not mean dead.
- No check proves that a complete payload will remain available.

The exact score and ranking rules are documented in
[the health-scoring documentation](https://github.com/monhoney/magnet-scout/blob/main/docs/health-scoring.md).

## Documentation

- [Architecture](https://github.com/monhoney/magnet-scout/blob/main/docs/architecture.md)
- [Providers](https://github.com/monhoney/magnet-scout/blob/main/docs/providers.md)
- [Health scoring](https://github.com/monhoney/magnet-scout/blob/main/docs/health-scoring.md)
- [Development](https://github.com/monhoney/magnet-scout/blob/main/docs/development.md)
- [Release process](https://github.com/monhoney/magnet-scout/blob/main/docs/releasing.md)
- [Licensing and external services](https://github.com/monhoney/magnet-scout/blob/main/docs/licensing.md)

## License

MagnetScout is released under the MIT License.

That license covers MagnetScout's own source code. Dependencies, provider services, trademarks,
and content referenced by search results retain their own licenses and terms. See the
[licensing notes](https://github.com/monhoney/magnet-scout/blob/main/docs/licensing.md) and
[third-party notices](https://github.com/monhoney/magnet-scout/blob/main/THIRD_PARTY_NOTICES.md).

All product and service names are used only to identify their respective providers. MagnetScout is
not affiliated with or endorsed by Internet Archive, Academic Torrents, Fedora Project, Red Hat,
or any configured Torznab service. Fedora is a trademark of Red Hat, Inc.
