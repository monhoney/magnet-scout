# MagnetScout agent instructions

- Preserve the product boundary: return torrent metadata and magnet URIs only. Never add
  payload or piece downloading, content storage, client launching, or media-library integration.
- Prefer structured provider APIs and explicitly legal or public collections over generic web
  search and brittle scraping.
- Keep providers behind `SearchProvider`; one provider failing must not fail an aggregate search.
- Treat provider seed counts as untrusted reports. Only verifier observations may populate
  `verified`, `verified_peers`, or tracker and DHT evidence.
- Canonicalize and deduplicate by info hash before verification and ranking.
- Add fixtures and tests for every provider. Tests must not depend on the live network.
- Keep timeouts and concurrency bounded. Never log full peer IP addresses.
- DHT backends must use a hard deadline, perform peer discovery only, discard addresses after
  counting, and never fetch metadata or announce. Prefer process isolation for blocking clients.
- Record architectural discoveries and scoring changes in `docs/`.
- Commit messages must be in English and should read like natural, human-written summaries.
- Run `ruff format --check .`, `ruff check .`, `mypy`, and `pytest` before handing off changes.
