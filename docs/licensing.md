# Licensing and external services

MagnetScout's own source code is distributed under the MIT License. That license does not grant
rights to third-party software, provider services, trademarks, torrent metadata, or content
referenced by a search result.

## Python dependencies

Runtime dependencies are installed as separate distributions and remain under their respective
licenses. In particular, `torf` declares GPL-3.0-or-later and `bencode.py` declares the BitTorrent
Open Source License. Other direct and transitive dependencies also retain their own notices and
conditions. Anyone redistributing an environment, container, executable bundle, or modified
dependency must review and satisfy the licenses of everything they distribute; MagnetScout's MIT
license does not replace those terms.

MagnetScout does not vendor dependency source code. Dependency names and version constraints are
listed in `pyproject.toml`; installed license metadata can be audited as part of a downstream
distribution process.

## Provider services

The built-in adapters access public metadata endpoints operated by Internet Archive, Academic
Torrents, and Fedora. Availability does not imply unrestricted permission. Users and downstream
applications must follow each operator's current terms, access policies, rate limits, and
trademark rules. Configured Torznab services are selected and administered by the user, who is
responsible for the endpoint and any required account or API key.

Provider responses are factual inputs, not bundled project assets. MagnetScout neither republishes
provider databases nor grants permission to use a provider's name, branding, or service beyond
the operator's terms.

## Search results and content

A magnet URI, `.torrent` metadata file, license URL, or provider description is not proof that the
referenced payload is lawful to obtain or redistribute. Rights can differ item by item, and
provider-supplied license metadata may be missing or inaccurate. MagnetScout preserves available
evidence for the user; it does not make a legal determination.

This document describes project boundaries and is not legal advice.
