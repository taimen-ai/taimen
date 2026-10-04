
# Object storage (MinIO)

How S3-compatible storage works in a Taimen installation: why the core needs
it, which buckets and accounts are created, how to connect an external S3
instead of the bundled MinIO, what to back up, and how to troubleshoot common
failures. This article is for the operations engineer.

## Who uses the storage

| Consumer | Bucket (variable, default) | Account | What is stored |
|---|---|---|---|
| Control Plane (API and worker) | `CP_S3_BUCKET`, `artifacts` | a dedicated user `CP_S3_ACCESS_KEY_ID` with a policy limited to its own bucket | Task artifact content (see [Artifacts](../control-plane/artifacts.md#content)) |

The core keeps only records in PostgreSQL: the object reference, size, media
type, and SHA-256. The bytes live only in the storage. A content object is
addressed by its checksum within the tenant: `tenants/<tenant-id>/sha256/<hex>`.
Identical files of one tenant are stored as one object; files of different
tenants never overlap.

## MinIO in compose

| Service | Profiles | Purpose |
|---|---|---|
| `minio` | `core` | S3 server, data in the `platform_minio` volume, memory limit `MINIO_MEM_LIMIT` (256m), healthcheck `mc ready local` |
| `minio-bootstrap` | `core` | one-shot: bucket, policy, and the core user; exits after startup |

MinIO is part of the `core` profile and stores only the core's artifact
content. The volume name (historical) is `${COMPOSE_PROJECT_NAME}_platform_minio`,
overridden by `VOLUME_PLATFORM_MINIO`.

**MinIO is not exposed.** No ports are published to the host, and there is
no route in Caddy (the `edge` profile). Clients never receive object
addresses: artifact bytes come in through `PUT /api/v1/artifact-contents`
and go out through `GET /api/v1/artifacts/{id}/content`, where the core
checks permissions and records a download event.

### What `minio-bootstrap` does

The service runs a set of `mc` commands as the MinIO root account:

1. creates the `CP_S3_BUCKET` bucket (`mc mb --ignore-existing`);
2. creates the `cp-artifacts` policy (see below);
3. creates the user `CP_S3_ACCESS_KEY_ID` with the secret
   `CP_S3_SECRET_ACCESS_KEY`;
4. attaches the policy to that user if it is not attached yet.

All steps are idempotent: the service can be restarted on every `up`.
`control-plane-api` waits for it to complete successfully
(`service_completed_successfully`); the dependency is marked optional so
that an installation with an external S3, where the service does not exist,
also starts.

### The core user's policy

The `cp-artifacts` policy for the default bucket `artifacts`:

```json
{"Version": "2012-10-17", "Statement": [
  {"Effect": "Allow", "Action": ["s3:GetBucketLocation", "s3:ListBucket"],
   "Resource": ["arn:aws:s3:::artifacts"]},
  {"Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
   "Resource": ["arn:aws:s3:::artifacts/*"]}
]}
```

- **Objects in its own bucket**: read, write, and delete, for content
  upload, download, deletion by an administrator, and cleanup by the worker.
- **`s3:ListBucket` on the bucket** is needed because at startup the API
  checks the bucket with a `HeadBucket` request; without this permission the
  storage returns `403` and the core treats the storage as unavailable.
- **The core does not need to create buckets** and is not allowed to:
  `minio-bootstrap` creates the bucket. The core user sees no other buckets,
  and root keys are never given to the core.

## Keys

`make secrets` (`tools/fill_secrets.py`) generates all four keys if they are
empty in `.env`:

| Variable | Who uses it |
|---|---|
| `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | the `minio` root account; only `minio-bootstrap` uses it |
| `CP_S3_ACCESS_KEY_ID`, `CP_S3_SECRET_ACCESS_KEY` | the core user: `minio-bootstrap` creates it, Control Plane processes run under it |
| `CP_S3_BUCKET` | the artifact content bucket, `artifacts` by default |

`CP_S3_ACCESS_KEY_ID` and `CP_S3_SECRET_ACCESS_KEY` are required in
`deploy/local/compose.yml` (`${VAR:?…}`): without them neither MinIO-bootstrap nor the
core processes start. The other core settings (`CP_S3_ENDPOINT_URL`,
`CP_S3_REGION`, timeouts, limits) are in the [Control Plane configuration](../control-plane/configuration.md#content-store).

!!! warning "Keys are secrets"
    Keep `.env` together with the rest of the installation configuration:
    without it, a restored MinIO volume opens neither with the root account
    nor with the core user. See [Secrets and rotation](secrets.md).

## External S3 instead of MinIO

You can keep artifact content with any S3-compatible provider. The
`deploy/local/compose.s3.example.yml` file in the superproject root takes `minio` and
`minio-bootstrap` out of the `core` profile (it assigns them a profile that
the installation does not start); include it as the second file:

```bash
tools/compose -f deploy/local/compose.s3.example.yml --profile core --profile edge up -d
```

In `.env`:

```dotenv
CP_S3_ENDPOINT_URL=https://s3.example.com
CP_S3_REGION=<provider region>
CP_S3_BUCKET=<bucket>
CP_S3_ACCESS_KEY_ID=<user key>
CP_S3_SECRET_ACCESS_KEY=<user secret>
```

- Create the bucket in advance with the provider's tools.
- The user needs the same permissions as the policy above: `ListBucket` on
  the bucket and `GetObject`, `PutObject`, `DeleteObject` on its objects.
- The bundled MinIO is not needed in this case.

!!! note "Storage disabled entirely"
    If `CP_S3_ENDPOINT_URL` is empty, Control Plane runs without storage:
    link artifacts and JSON artifacts are created as usual, and the content
    routes return `503 content_store_unavailable`. In the shipped
    `deploy/local/compose.yml` the default address is `http://minio:9000`.

## Backup { #backup }

The `platform_minio` volume holds the core's artifact content. Back it up
together with the Control Plane database:

- **`control-plane-db` ↔ MinIO.** Artifact records live in the Control Plane
  database, the bytes in MinIO. Take them in the same window. If the MinIO
  volume is older than the database, some records with `contentState = stored`
  will have no object, and downloading such artifacts returns
  `503 content_store_unavailable`.

The daily backup script and the restore procedure are in
[Backup](backup.md). Copy the volume **after** the Control Plane database
dump: objects are immutable and addressed by checksum, so the objects of the
records in the dump are already in the volume by then. The exception is
content that an administrator deleted between the dump and the volume copy.

## Cleanup and growth

- **Incomplete uploads.** An upload that no artifact references within
  `CP_ARTIFACT_UPLOAD_TTL_SECONDS` (24 hours by default) is deleted by the
  worker together with its object, if nobody else needs the object. If the
  storage is unavailable, the rows remain until the next pass.
- **Artifact content is kept indefinitely.** Closing a task does not delete
  it. A tenant administrator can delete the bytes of a specific artifact:
  `POST /api/v1/artifacts/{id}:purge-content` (see
  [Deleting content](../control-plane/artifacts.md#purge-content)).
- **The ceiling for one file** is `CP_ARTIFACT_MAX_BYTES` (100 MiB by default);
  an artifact type can narrow it with its own `maxBytes`.

Account for volume growth in [Resources and scaling](capacity.md).

## Common problems

| Symptom | Cause | What to do |
|---|---|---|
| `503 content_store_unavailable` on `PUT /artifact-contents` while MinIO is running | `CP_S3_ENDPOINT_URL` is empty, so storage is disabled in the core | Set the address and recreate the Control Plane processes |
| `503 content_store_unavailable`, with the warning `content store unavailable at start-up` in the API log | MinIO is not up, the keys are wrong, or the user lacks `ListBucket` | `tools/compose ps minio minio-bootstrap`, `minio-bootstrap` logs; check the keys in `.env` and the policy |
| `503 content_store_unavailable` only when reading individual artifacts | The object is missing from storage while the record says `stored`: the volume was restored from an older copy than the database | Restore the MinIO volume from a copy consistent with the database |
| `tools/compose up` fails on `set CP_S3_ACCESS_KEY_ID` | The core keys are missing from `.env` | `make secrets` adds the missing keys |
| `413 request_too_large` on upload | The file is larger than `CP_ARTIFACT_MAX_BYTES` | Reduce the file or raise the installation limit |
| `422 artifact_too_large` when creating an artifact | The file is larger than the registered artifact type's `maxBytes` | Publish a version of the type with a larger `maxBytes` (not above `CP_ARTIFACT_MAX_BYTES`) |

## See also

- [Artifacts and comments](../control-plane/artifacts.md)
- [Control Plane configuration](../control-plane/configuration.md#content-store)
- [Backup](backup.md)
- [Secrets and rotation](secrets.md)
- [Production deployment](deployment.md)
