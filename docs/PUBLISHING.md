# Publishing

`chat-omni-digest` is a normal Python package. The package can be built locally, attached to a GitHub Release, and later uploaded to PyPI.

## Build Locally

```bash
python3 -m pip install -e ".[dev,pdf,office,media]"
python3 -m pytest
python3 -m compileall src
python3 -m build
python3 -m twine check --strict dist/*
```

The build creates:

- `dist/chat_omni_digest-0.1.0-py3-none-any.whl`
- `dist/chat_omni_digest-0.1.0.tar.gz`

## GitHub Release

```bash
git tag v0.1.0
git push origin v0.1.0
gh release create v0.1.0 dist/* --title "v0.1.0" --notes "First packaged release."
```

Users can install from the release tag:

```bash
python3 -m pip install "chat-omni-digest[pdf,office,media] @ git+https://github.com/duevan07/chat-omni-digest.git@v0.1.0"
```

## PyPI

The PyPI package name `chat-omni-digest` should be published from GitHub Actions using Trusted Publishing.

1. Log in to PyPI.
2. Create a pending publisher for:
   - PyPI project name: `chat-omni-digest`
   - Owner: `duevan07`
   - Repository: `chat-omni-digest`
   - Workflow: `publish-pypi.yml`
   - Environment: `pypi`
3. Open GitHub Actions and manually run `Publish to PyPI`.

After PyPI accepts the package, users can install it with:

```bash
python3 -m pip install "chat-omni-digest[pdf,office,media]"
```
