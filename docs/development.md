# Development

```console
python -m pip install -e '.[dev,dht]'
ruff check .
mypy
pytest
bandit -r src -ll
pip-audit . --progress-spinner off
python -m build
```

Tests use injected HTTPX transports and fixtures and must pass offline. To make
a live smoke test, run `magnet-scout search ubuntu --provider internet-archive
--top 3`; live API failures should produce a provider warning and a nonzero exit
only when no provider produced results.

Structured diagnostics use Python logging and go to stderr so JSON stdout stays
machine-readable. Do not include peer addresses in logs or fixtures.

Tracker verification tests use HTTPX's in-process mock transport and binary UDP
response fixtures. They must never contact public trackers during the test
suite. Live verification reveals the caller's IP address to each queried
tracker even though scrape does not register the caller as a swarm peer.

The SQLite verification cache defaults to
`$XDG_CACHE_HOME/magnet-scout/verification.sqlite3` (or `~/.cache/...`). Tests
must use `tmp_path`; never write tests into a developer's real cache.

CI runs formatting, lint, strict typing, tests, and wheel/sdist builds on Python
3.11–3.13. DHT tests use a stubbed count path plus a real parent-deadline test;
they do not query the public DHT.

Torznab tests use XML fixtures and HTTPX mock transports. Never put real API
keys in fixtures, command examples, exception messages, or snapshots.

See `docs/releasing.md` for the release checklist. Do not create a version tag
before a release commit exists, and do not publish externally without explicit
authorization.
