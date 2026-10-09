# Third-party notices

MagnetScout does not copy or vendor the source code of its runtime dependencies. Package
installers install those projects as separate distributions, and each distribution remains under
its own license. Their original license files must remain in the corresponding `.dist-info`
directory when an installed environment is copied, bundled, or redistributed.

The following runtime dependency families are expected by MagnetScout 0.2.2. Transitive versions
can vary within the constraints selected by the installer, so redistributors must use the license
files from the exact artifacts they ship as the authoritative terms.

| Distribution | Role | Declared license family |
| --- | --- | --- |
| `click` | CLI framework dependency | BSD-3-Clause |
| `defusedxml` | Defensive XML parsing | Python Software Foundation License |
| `httpx` | HTTP client | BSD-3-Clause |
| `typer` | CLI framework | MIT |
| `anyio` | HTTP concurrency support | MIT |
| `certifi` | CA certificate bundle | MPL-2.0 |
| `h11` | HTTP/1.1 protocol support | MIT |
| `httpcore` | HTTP transport | BSD-3-Clause |
| `idna` | Internationalized domain names | BSD-3-Clause |
| `markdown-it-py` | Rich text rendering dependency | MIT |
| `mdurl` | URL parsing for Markdown | MIT |
| `pygments` | Terminal syntax highlighting | BSD-2-Clause |
| `rich` | Terminal rendering | MIT |
| `shellingham` | Shell detection | ISC |
| `typing-extensions` | Typing compatibility helpers | PSF-2.0 |

This file is an attribution aid, not a replacement for any dependency's license text. In
particular, a distributor that bundles an environment, container, executable, or application must
preserve the license files delivered with every included distribution. Modified MPL-2.0-covered
files must also be handled under the MPL-2.0 requirements. MagnetScout itself does not modify or
redistribute `certifi` files in its wheel or source distribution.

Provider services, torrent metadata, search results, trademarks, and referenced content are not
licensed by MagnetScout. Their operators' terms and the applicable rights for each item remain
separate.
