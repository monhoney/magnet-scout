# Changelog

## 0.2.2 - 2026-10-09

- Identify automated requests with a versioned MagnetScout User-Agent.
- Honor bounded Internet Archive `429` retries and reduce provider concurrency.
- Require explicit Internet Archive license metadata by default, with an opt-out flag.
- Document query and IP disclosure, provider terms, API-key handling, and trademarks.
- Remove an obsolete DHT statement from the security policy.

## 0.2.1 - 2026-10-09

- Include the project license and third-party notice inventory in published distributions.
- Verify that every installed runtime distribution retains at least one license or notice file.
- Document redistribution requirements for separately installed dependencies and MPL-2.0 files.

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
