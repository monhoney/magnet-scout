# Release process

Releases use PyPI Trusted Publishing. No long-lived PyPI token belongs in GitHub secrets or local
configuration. A manual workflow run publishes the current version to TestPyPI; publishing a
GitHub Release publishes the matching version to production PyPI.

The Hatchling build backend is temporarily capped below 1.30 because newer releases emit Core
Metadata 2.5, which Twine 6.2 does not yet accept. Remove the cap only after the complete build and
upload toolchain supports that metadata version.

## One-time setup

1. Create separate PyPI and TestPyPI accounts, verify their email addresses, and enable 2FA.
2. Create the `testpypi` and `pypi` GitHub environments. Require approval on `pypi` deployments.
3. Register pending Trusted Publishers on both package indexes with these values:

   | Field | Value |
   | --- | --- |
   | Project | `magnet-scout` |
   | Owner | `monhoney` |
   | Repository | `magnet-scout` |
   | Workflow | `release.yml` |
   | Environment | `testpypi` or `pypi` |

4. Never add a `PYPI_API_TOKEN` or `TEST_PYPI_API_TOKEN` secret.

## TestPyPI

Run the `Release` workflow manually from the `main` branch. It builds the wheel and source archive
once, checks their metadata, and uploads the exact artifacts to TestPyPI through the `testpypi`
environment. A version can be uploaded only once on each index.

Install the result into a fresh environment while obtaining ordinary dependencies from PyPI:

```console
python -m venv /tmp/magnet-scout-test
/tmp/magnet-scout-test/bin/pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  magnet-scout==0.1.0
/tmp/magnet-scout-test/bin/magnet-scout --help
```

## Production PyPI

Create an annotated `vX.Y.Z` tag on the reviewed commit and publish a GitHub Release for that tag.
The workflow refuses a release tag that does not exactly match the versions in `pyproject.toml`
and `magnet_scout.__version__`. The `pypi` environment approval is the final publication gate.

## Checklist

1. Review dependency licenses and security advisories.
2. Update the version in `pyproject.toml` and `src/magnet_scout/__init__.py`.
3. Move relevant `CHANGELOG.md` entries into a dated release section.
4. Run `ruff format --check .`, `ruff check .`, `mypy`, and `pytest`.
5. Run `python -m build` and `python -m twine check dist/*`.
6. Install the wheel in a fresh virtual environment and run CLI smoke tests.
7. Run `python scripts/check_release.py --tag vX.Y.Z`.
8. Test the exact version through TestPyPI.
9. Tag the reviewed commit with an annotated `vX.Y.Z` tag and publish its GitHub Release.
10. Approve the `pypi` environment deployment after reviewing the built artifact.

Deleting a PyPI file or release is irreversible, and an uploaded filename cannot be reused. Fixes
must use a new version. Creating or pushing a tag alone does not publish; the GitHub Release must be
published and the protected `pypi` environment must be approved.
