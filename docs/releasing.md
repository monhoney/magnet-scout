# Release process

PyPI publication is intentionally deferred until the repository and project metadata have been
reviewed in their final public form.

## Checklist

1. Review dependency licenses and security advisories.
2. Update the version in `pyproject.toml` and `src/magnet_scout/__init__.py`.
3. Move relevant `CHANGELOG.md` entries into a dated release section.
4. Run `ruff format --check .`, `ruff check .`, `mypy`, and `pytest`.
5. Run `python -m build` and `python -m twine check dist/*`.
6. Install the wheel in a fresh virtual environment and run CLI smoke tests.
7. Tag the reviewed commit with an annotated `vX.Y.Z` tag.
8. Publish through a PyPI trusted publisher after explicit maintainer approval.

Do not store PyPI API tokens in the repository or add a publishing workflow before the trusted
publisher is configured. Creating a tag must not publish by itself.
