# MagnetScout agent instructions

- Preserve the product boundary: return torrent metadata and magnet URIs only. Never add
  payload or piece downloading, content storage, client launching, or media-library integration.
- Prefer structured provider APIs and explicitly legal or public collections over generic web
  search and brittle scraping.
- Keep providers behind `SearchProvider`; one provider failing must not fail an aggregate search.
- Treat provider seed counts as untrusted reports. Only verifier observations may populate
  `verified`, `verified_peers`, or tracker evidence.
- Canonicalize and deduplicate by info hash before verification and ranking.
- Add fixtures and tests for every provider. Tests must not depend on the live network.
- Keep timeouts and concurrency bounded. Never log full peer IP addresses.
- Do not add copyleft runtime dependencies. MagnetScout intentionally does not bundle a DHT
  backend; any future design requires a separate architecture and license review.
- Record architectural discoveries and scoring changes in `docs/`.
- Commit messages must be in English and should read like natural, human-written summaries.
- Run `ruff format --check .`, `ruff check .`, `mypy`, and `pytest` before handing off changes.
