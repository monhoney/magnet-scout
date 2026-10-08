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

Until the first PyPI release, install from a checkout:

```console
python -m pip install -e .
```

Optional DHT peer discovery is installed separately:

```console
python -m pip install 'magnet-scout[dht]'
```

## CLI

```console
magnet-scout search ubuntu
magnet-scout search ubuntu --top 10
magnet-scout search ubuntu --verify --top 10
magnet-scout search ubuntu --verify --min-verified-seeders 3
magnet-scout search ubuntu --json
magnet-scout search dataset --provider academic-torrents
```

The default providers are Internet Archive, Academic Torrents, and Fedora. Provider failures are
reported independently, so one unavailable source does not discard results from the others.

`--verify` performs bounded tracker and web-seed observations without requesting payload pieces.
`--dht` adds optional, process-isolated peer discovery. A provider's reported seeder count remains
separate from independently observed values.

## Python API

```python
from magnet_scout import parse_magnet

magnet = parse_magnet("magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&dn=Example")
print(magnet.info_hash)
print(magnet.canonical_uri)
```

Provider integration uses the asynchronous `SearchProvider` protocol. See
[docs/providers.md](docs/providers.md) for a complete example.

## Evidence, not guarantees

- `reported_seeders` is untrusted metadata supplied by a provider.
- `verified_seeders` is a recent tracker observation when the tracker supports scraping.
- `dht_peers` counts peer endpoints discovered during a bounded lookup; addresses are discarded.
- `UNKNOWN` means there was not enough independent evidence. It does not mean dead.
- No check proves that a complete payload will remain available.

The exact score and ranking rules are documented in
[docs/health-scoring.md](docs/health-scoring.md).

## Documentation

- [Architecture](docs/architecture.md)
- [Providers](docs/providers.md)
- [Health scoring](docs/health-scoring.md)
- [Development](docs/development.md)
- [Release process](docs/releasing.md)

## License

MagnetScout is released under the MIT License.
