# Licensing and external services

MagnetScout's own source code is distributed under the MIT License. That license does not grant
rights to third-party software, provider services, trademarks, torrent metadata, or content
referenced by a search result.

## Python dependencies

Runtime dependencies are installed as separate distributions and remain under their respective
licenses. MagnetScout 0.2.0 removed `torf`, `bencode.py`, and the optional
`pythontorrentdht` backend, eliminating its declared GPL and BitTorrent Open Source License runtime
dependencies. No installed runtime distribution currently declares GPL or AGPL. Direct
dependencies use MIT, BSD, or PSF-family licenses; the transitive certificate bundle `certifi`
declares MPL-2.0, a file-level weak-copyleft license. All packages retain their own notices and
conditions. Anyone redistributing an environment, container, executable bundle, or modified
dependency must review and satisfy the licenses of everything they distribute; MagnetScout's MIT
license does not replace those terms.

MagnetScout does not vendor dependency source code. Dependency names and version constraints are
listed in `pyproject.toml`; installed license metadata can be audited as part of a downstream
distribution process. The built-in bencode and torrent metainfo parsers are original MagnetScout
code under the repository's MIT License and implement only the bounded read-only subset needed by
tracker scrape responses and provider metadata.

CI walks the installed runtime dependency closure and rejects metadata declaring GPL, AGPL, LGPL,
or the BitTorrent Open Source License. This is a policy guard, not a substitute for reviewing
license texts: package metadata can be incomplete, dependency versions can change within allowed
ranges, and redistribution may impose notice obligations even for permissive dependencies.

The runtime tree reviewed for 0.2.0 contained MIT, BSD, ISC, PSF, and MPL-2.0 components. In
particular, `certifi` uses MPL-2.0. Ordinary unmodified use does not relicense MagnetScout, but a
redistributor should preserve the license and notices shipped by every included distribution and
review any modifications to MPL-covered files.

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
