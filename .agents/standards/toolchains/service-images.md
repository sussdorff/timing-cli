# Stateful Service Images

Images of stateful services use the latest release of their current major
line. A major upgrade changes on-disk formats, schemas or behaviour. It is
deliberate and gets its own work order. The check therefore never asks for a
new major. It fails only when a pinned version is older than the latest release
of its own line. `postgres:14.19` passes while 18 exists, as long as 14.19 is
the latest 14.x.

| Tag form | Verdict |
|----------|---------|
| Line tag: `postgres:16`, `postgres:16-alpine`, `quay.io/keycloak/keycloak:26`, `healthsamurai/aidboxone:2608`, `postgis/postgis:16-3` | Floats on the line, ok |
| Pinned release: `postgres:16.2`, `keycloak:26.1`, `keycloak:26.7.5-0`, `aidboxone:2608.2`, `postgis/postgis:16-3.4` | Fails when the line has a newer release with the same variant family, at the tag's precision. A numeric build suffix (`-0`) belongs to the release |
| Channel or no version: `latest`, `edge`, `stable`, `nightly`, a variant only (`alpine`), or no tag | Fails as `major_unpinned`: the tag names no major line and can cross a major on the next pull. Pin the line tag instead |
| Version-bearing tag outside the scheme: `postgres:16rc1`, `postgis/postgis:16-master` | Fails as `unparseable`. Use a line or release tag |
| Line tag with digest: `postgres:18@sha256:…` | The digest has to be one Docker Hub or Quay lists for the tag. Otherwise it fails as `digest_not_latest`, which is the signal to rotate |
| Full release tag with digest: `postgres:17.5-alpine@sha256:…` | The tag is judged first. When the tag is current, the digest has to be one the registry lists for that exact tag; otherwise it fails as `digest_not_latest` |
| Digest without a version tag: `aidboxone@sha256:…`, `postgres:latest@sha256:…` | An `implicit` note: no line is declared, so put a version tag next to the digest |

A variant family is the tag suffix without its OS release number:
`alpine3.22` and `alpine` belong to the same family, `bookworm` is a different
one. Prerelease and nightly tags (`18rc1`, `26.9.0-nightly`, `2608-rc`) are
never counted as the latest release.

The latest release of a line comes from the registry's tag list, read in pages
up to a fixed bound. A listing that is still incomplete at the bound is the
typed `image_lookup_failed` error, never a pass.

## Known Images and Versioning Schemes

| Image | Registry | Line and release |
|-------|----------|------------------|
| `postgres`, `healthsamurai/aidboxdb` | Docker Hub | Line = major, release = `major.minor` |
| `postgis/postgis` | Docker Hub | `<postgres major>-<postgis major>.<minor>[.<patch>]`: line = Postgres major plus PostGIS major (`16-3`), release = the PostGIS version within it. Neither major is ever demanded: `16-3.5` passes while `16-4.0` or `17-3.5` exist |
| `healthsamurai/aidboxone` | Docker Hub | CalVer: line = `YYMM` monthly release, release = `YYMM.N` patch. Aidbox has no semantic major, so moving to a newer `YYMM` line counts as the deliberate upgrade |
| `quay.io/keycloak/keycloak` | Quay | Line = major, release = `major.minor[.patch]` |
| `keycloak/keycloak`, `redis`, `valkey/valkey`, `mariadb`, `mysql`, `mongo` | Docker Hub | Line = major, release = `major.minor[.patch]` |

Other images are not judged. A new stateful image is added to the `STATEFUL`
table in the check, together with a test.
