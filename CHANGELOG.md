# Changelog

## 0.2.0 - 2026-10-09

- Replace `torf` and `bencode.py` with a bounded, read-only MIT-licensed parser.
- Remove the GPL-licensed optional DHT backend and its CLI options.
- Hash the exact original torrent `info` bytes and reject non-canonical bencode input.
- Document dependency and provider-service license boundaries.

## 0.1.1 - 2026-10-09

- Fix documentation links rendered on PyPI.
- Clarify the boundaries between the project license, dependencies, external services, and
  result-content rights.

## 0.1.0 - 2026-10-09

- Initial CLI and Python API for searching public BitTorrent metadata providers.
- Magnet parsing, info-hash normalization, metadata merging, verification, and health ranking.
- Internet Archive, Academic Torrents, Fedora, and configurable Torznab adapters.
