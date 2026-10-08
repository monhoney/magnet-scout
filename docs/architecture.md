# Architecture

## Scope

MagnetScout returns normalized torrent metadata and magnet URIs. It does not download pieces,
store payload content, launch torrent clients, or manage media libraries.

## Search pipeline

```text
query
  -> concurrent providers
  -> normalized TorrentResult values
  -> magnet validation and canonical info hashes
  -> merge by info hash
  -> optional bounded verification
  -> health and confidence scoring
  -> ranking and filters
  -> CLI or Python result objects
```

`SearchService` owns orchestration. Each provider implements `SearchProvider`, and exceptions are
converted to `ProviderFailure` entries. The successful providers continue to contribute results.

## Models and normalization

`TorrentResult` keeps claims and observations distinct. Provider counts use `reported_*` fields;
tracker and DHT observations use `verified_*` and `dht_peers`. Missing data stays `None` rather
than becoming a misleading zero.

`parse_magnet` accepts hexadecimal and base32 BEP 9 `btih` values and produces a lowercase,
40-character hexadecimal info hash. `merge_results` uses that hash as its key, retains all source
providers and URLs, and merges the richest available metadata.

## Verification boundaries

The tracker verifier sends HTTP(S) or UDP scrape requests where supported. It does not announce as
a peer. Web-seed checks make bounded HTTP `HEAD` requests for responsiveness and do not count as
swarm health. Optional DHT verification runs in a separate process under a hard deadline, requests
peer discovery only, counts returned endpoints, and discards their addresses.

All network work uses explicit timeouts, concurrency limits, and decompressed response-size caps.
Redirects are disabled so credentials and bounded-request rules cannot be bypassed through a
redirect chain. Environment proxy variables are ignored by the CLI. Verification observations are
cached briefly to avoid repeatedly contacting infrastructure.

## Trust boundaries

Provider titles, descriptions, counts, links, and torrent files are untrusted input. Control
characters are removed in human output, XML entities are disabled, magnet complexity is bounded,
torrent metainfo is parsed without materializing payloads, and provider errors cannot terminate
aggregate search. API keys for optional Torznab providers are read from environment variables,
never stored directly in the configuration file, and sent only to HTTPS endpoints.
