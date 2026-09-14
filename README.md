# Loqed Touch Smart Lock — Python client

This repository provides a small async-first Python client for the Loqed Touch smart lock. It wraps [the HTTP API used by Loqed devices](https://support.loqed.com/en/articles/6127856-loqed-local-bridge-api-integration) and exposes convenient helpers to read lock state, send lock/unlock commands, and manage webhooks.

## Quick start

1. Install the package (recommended: in a virtualenv):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

2. Install dev/test dependencies (optional):

```bash
pip install -e .[dev]
```

3. Use the client (async):

```python
import asyncio
from loqedAPI.loqed import APIClient, LoqedAPI

async def main():
	client = APIClient(base_url="https://api.loqed.com", token="your-api-token")
	api = LoqedAPI(client)

	# fetch a lock by id
	lock = await api.async_get_lock("lock-id")
	print("state:", lock.bolt_state)

	# send an unlock command
	await lock.unlock()

asyncio.run(main())
```

Notes:

- The library is async-first and uses `aiohttp` for HTTP calls.
- `APIClient` accepts `base_url` and an optional `token` (for authorization) or you can provide your own `aiohttp.ClientSession`.

## Testing

Run the test suite with pytest (the project uses `pytest-asyncio` and `aioresponses`):

```bash
source .venv/bin/activate
pytest --cov=src/loqedAPI --cov-report=term-missing
```

## Development

- The package follows standard Python packaging with `pyproject.toml`/`setup.py`.
- Dev/test dependencies are available under the `dev` extra: `pip install -e .[dev]`.
- When editing code, run the tests frequently. The tests are fast and designed to mock network calls.

## Contributing

If you want to contribute:

1. Fork the repo, create a branch, and make your changes.
2. Add or update tests for new behavior.
3. Run the test suite and ensure all tests pass.
4. Open a pull request with a short description of the change.

## Releasing

Releases are built and published to PyPI automatically by a public GitHub Actions
workflow (`.github/workflows/release.yml`) — there is no manual/local publish step.

To cut a release:

1. Draft a [GitHub Release](https://github.com/cpolhout/loqedAPI/releases) with a
   tag in the form `vX.Y.Z` (e.g. `v2.1.12`).
2. Publish the release. The package version is derived from the tag via
   `setuptools-scm`, so the version on PyPI always matches a tagged commit in
   this repository.
3. CI runs the test suite, builds the sdist/wheel, and publishes to PyPI using
   [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (no
   stored API tokens).

## Where to find docs

- Source code is under `src/loqedAPI`.
- Sphinx documentation lives in `docs/`.

## License

See the `LICENSE` file in the project root.
