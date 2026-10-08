# Contributing

Thank you for helping improve MagnetScout. Keep changes within the metadata-only boundary: no
payload downloads, client launching, content storage, or media-library automation.

Create a focused branch, add offline tests for behavior changes, and update the relevant document
when provider behavior or scoring changes. Before opening a pull request, run:

```console
ruff format --check .
ruff check .
mypy
pytest
```

Commit messages should be concise, natural English summaries of the change.
