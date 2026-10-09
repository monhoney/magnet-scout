# Security policy

Please report suspected vulnerabilities privately through GitHub's security advisory feature.
Do not include API keys, full peer addresses, or private index URLs in a public issue.

MagnetScout processes untrusted network metadata. Reports involving unsafe metainfo parsing,
credential exposure, unbounded network activity, SSRF, or unexpected payload retrieval are
especially useful. The project does not consider provider downtime or stale swarm counts a
security vulnerability.

Every external response is subject to a decompressed byte limit before parsing. XML entity
expansion and redirects are disabled, and tracker and web-seed verification rejects non-public
address ranges. MagnetScout does not include a DHT backend. These controls are security boundaries;
changes to them require regression tests and updated architecture documentation.
