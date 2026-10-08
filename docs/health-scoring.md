# Health and confidence scoring

Scores are evidence summaries, never availability guarantees.

## Current formula

Health starts at 0 and is capped at 100:

- independently observed peers: `min(60, 15 * log2(peers + 1))`
- responsive tracker with observed peers: 15
- metadata observed from the swarm: 10
- each additional reporting provider: 5, capped at 10
- reported seeders: `min(5, log2(seeders + 1))`; deliberately low weight
- freshness: 5 when checked within 15 minutes, fading linearly to 0 at 24 hours

Classification: `EXCELLENT >= 80`, `GOOD >= 60`, `FAIR >= 40`, `POOR > 0`,
`DEAD = 0` only when at least one tracker returned a valid zero-peer scrape.
Timeouts, tracker errors, unsupported trackers, and absent trackers remain
`UNKNOWN` rather than being treated as evidence of death.

Confidence is separate. It starts at 10 for valid normalized metadata, adds 15
per provider (cap 45), 25 for a completed independent check, 10 for a responsive
tracker, 10 for a responsive web-seed endpoint, 5 for swarm metadata, and up to
10 for freshness. It is capped at 100. Web-seed responsiveness never adds
health points and never changes the swarm health classification.

Provider-reported counts never set `verified`. Tracker scrape values populate
`verified_seeders`, `verified_leechers`, and `verified_peers`. Counts from
different trackers are not summed because their peer sets may overlap; the
maximum observation is retained. A positive peer count sets `verified`, but
does not guarantee that a complete, reachable copy can be downloaded.

`verification_status` makes the evidence explicit:

- `NOT_CHECKED`: no verification was requested or no supported tracker exists
- `VERIFIED_SEEDED`: at least one tracker reported a complete peer
- `VERIFIED_PEERS_ONLY`: peers were reported but no complete peer was observed
- `TRACKER_RESPONSIVE`: a valid scrape reported zero peers
- `UNREACHABLE`: supported trackers were tried but none returned a valid scrape

With `--dht`, `dht_peers` is an independently discovered peer count. A positive
count can produce `VERIFIED_PEERS_ONLY`, but cannot prove that a complete seeder
exists; only a tracker complete count can produce `VERIFIED_SEEDED`. A zero DHT
count alone remains `UNKNOWN` because DHT observation is incomplete by nature.

## Ranking

Sort keys, in order, are: verified status, health score, verified peers,
provider count, responsive web seed, confidence, freshness, reported seeders,
then title. Missing numbers sort below known numbers. With `--verify`, `--min-seeders` uses
`verified_seeders`; otherwise it uses the provider-reported field. Unknown
values are excluded. Prefer the unambiguous `--min-reported-seeders` and
`--min-verified-seeders` options; `--min-seeders` exists for compatibility.
