# Python and uv

The Python minimum stays 3.14. It is set in the `python` standard: its style
page and section 14 of its Python 3.14 patterns page. The minimum applies to
CPython only; PyPy and GraalPy versions in CI stay non-failing notes.
Within the minor line in use, Python is always on the latest patch release. A
repository moves to a new minor once its dependencies support it. uv is always
the latest release.

| Place | Rule |
|-------|------|
| `pyproject.toml` `requires-python` | Its lower bound is 3.14 or newer (`>=3.14`). It is a minimum, not a patch pin. A lower bound below 3.14, or no lower bound at all (`<4`), fails as `below_minimum`. A pin, exclusion or upper bound is judged against the newest released minor line it admits: it has to admit every patch of that line or at least its latest patch, otherwise it fails as `range_excludes_latest` (`==3.14.0`, `>=3.14,<3.14.3`, and `>=3.14,<3.15.2` once 3.15.2 is out). A partly admitted line without a release yet is skipped for the next lower admitted line. An upper bound is never required. Prerelease bounds such as `>=3.14.0rc1` count as their release. |
| `.python-version`, `.tool-versions`, mise configs | A minor line (`3.14`) floats to its latest patch and is fine. A full version (`3.14.0`, also `3.14.0rc1`) fails once a newer 3.14 patch is out. A line below 3.14 (`3.12`, also free-threaded `3.12t`) fails as `below_minimum`. `3.x` is fine. Every version an entry lists is judged. |
| CI `setup-python` | Set `python-version: '3.14'` (or `3.x`) together with `check-latest: true`, so the runner's cached older patch is not used. The same precision rules apply to `python-version-file`. A semver range follows the same rule as `requires-python`: `'>=3.14 <3.15'` is fine because it admits every 3.14 patch, `'>=3.14 <3.15.2'` fails once 3.15.2 is out, and a partly admitted unreleased line (`'>=3.14 <3.16.1'` before 3.16.0) is skipped for the next lower admitted line. A step that names a minor, a range or a version file without `check-latest: true` is reported as an `implicit` note, and so is a step without any version; the rollout fixes both. PyPy and GraalPy versions are not CPython and are an `implicit` note. |
| `python:` images | The same precision rules apply to the tag: `python:3.14-slim` is fine, `python:3.14.0-slim` fails once a newer patch is out, `python:3.12-slim` and `python:3.12t-slim` are below the minimum. |
| CI `setup-uv` | Set `version: latest`. An explicit older version fails, and so does a PEP 440 range that excludes the latest uv (`'>=0.5,<0.9'`); `'>=0.5'` is fine. `resolution-strategy: lowest` fails as `lowest_resolution`, because it installs the oldest uv the version admits. A `python-version` input follows the Python rules. A `version-file` is read relative to the step's `working-directory`: `required-version`, then a `uv` requirement in the project dependencies or dependency groups of a `pyproject.toml`, `uv.toml`, a requirements file or `.tool-versions`. A step without `version` or `version-file` is reported as an `implicit` note: setup-uv then falls back to `required-version` or to the latest release. |
| `[tool.uv] required-version`, `uv.toml` `required-version` | Admits the latest uv. `==0.9.0` fails once a newer uv is out. `>=0.9` is fine. |
| `ghcr.io/astral-sh/uv` images | A version tag (`0.12.23`, `0.12`, `0.12.23-python3.14-bookworm`) is judged at its precision against the latest uv. Tags without a version (`latest`, `python3.14-bookworm-slim`) float for uv. A Python version in the tag (`python3.14`) follows the Python rules, so `python3.12-bookworm-slim` fails as `below_minimum`. |
| Developer and fleet hosts | `uv self update` (or the fleet installer) keeps uv current. `uv python install 3.14` together with `uv python upgrade` keeps the patch current. |

The latest patch comes from endoflife.date for the minor line in question.
`uv.lock` and other lockfiles stay pinned. This standard does not judge them.
