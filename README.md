# TRF

A private Fall 2026 newsletter for eleven friends. Includes the TRF logo, personal seasonal forms, group notes, gratitude, childhood Halloween archive, and photo uploads. The edition shelf includes Fall 2026 and the original 25-page Summer 2026 PDF, served through authenticated routes. CAMP TRF 2027 has a landing page for July 9–11, 2027. Automatic seasonal rollover and historical snapshots are not implemented.

## Run

Python 3.12 or newer:

```sh
cd /workspace/TRF
python -m venv /workspace/trf-venv
/workspace/trf-venv/bin/pip install -r requirements.txt
/workspace/trf-venv/bin/gunicorn --workers 1 --bind 0.0.0.0:3000 'app:create_app()'
```

Use one worker: login throttling is held in process memory. If scaling beyond one instance, use a shared rate-limit service and database/storage suitable for multiple hosts.

On first startup, a random group password is generated in `instance/password.txt` with owner-only permissions. Retrieve it privately on the server; do not commit or publish this file. For deployment, set `TRF_PASSWORD_HASH` to a Werkzeug password hash through your hosting provider's secure configuration. You can generate a hash without including the password in shell history:

```sh
/workspace/trf-venv/bin/python -c 'from getpass import getpass; from werkzeug.security import generate_password_hash; print(generate_password_hash(getpass("New group password: ")))'
```

Changing the password does not revoke existing sessions. To revoke all sessions, stop the server, remove `instance/session.key`, and restart. Sessions expire after 12 hours.

## Privacy and deployment

Deploy behind HTTPS and set `TRF_SECURE_COOKIES=1`. Set `TRF_DATA_DIR` to a persistent private volume. This directory contains the SQLite database, normalized JPEG photos, signing key, and local password. Back it up securely using SQLite's backup API for the database. Never expose it as a static directory. The application protects page routes and photo routes; public static assets contain only styling and the logo.

A shared password gives all signed-in friends access to edit every page. Names are not individual identities. Concurrent editing uses the last saved submission. The mobile flow is Save my answers → Choose photos → Upload photos → Uploaded ✓ thumbnails. Uploads update the gallery in place without clearing unsaved answers. Recent photos automatically appear with their owner’s update on the homepage; childhood photos and captions appear in Halloween Archives. Selecting photos does not save unsaved text answers; save answers first.

Each image upload is limited to 10 MB, five recent photos, and one childhood photo per friend. Images are decoded and re-encoded as JPEG with no location metadata. HEIC is not supported: export it as JPG first. Captions apply to all photos in an upload batch. Use Replace photo to choose a new photo or caption; the original remains saved until the replacement succeeds.

The homepage does not use the deck's cover photo as a real group portrait. It uses a typographic collage until an approved photo is provided.

## Validate

```sh
cd /workspace/TRF
/workspace/trf-venv/bin/python -m unittest -v
```

Tests cover private routes, CSRF, incorrect passwords and throttling, all eleven pages, response persistence across app restarts, group updates, derived gratitude/Halloween content, output escaping, uploads, photo access, count limits, invalid files, deletion, and logout.

No hosting deployment or public URL is created by running this repository.

## Existing uploads and Render storage checks

This update keeps the same SQLite schema and storage paths; it does not migrate, reset, or delete existing uploads. Render's Blueprint provisions a persistent disk mounted at `/var/data` and sets `TRF_DATA_DIR=/var/data/trf`. Confirm that disk and variable exist on the deployed service under Disks and Environment. A configured Blueprint is not proof the live service has that disk. Do not change the data directory or remove the disk to troubleshoot: it can make existing files appear missing. If the live service used ephemeral storage previously, recover available files before changing its setup.

To diagnose missing photos privately in Render Shell, use this read-only check. It prints counts and storage location, not photo content, captions, credentials, or names:

```sh
python - <<'PY'
import os, sqlite3
from pathlib import Path
p=Path(os.environ.get('TRF_DATA_DIR','instance'))
print('Storage directory:', p)
if not (p/'trf.sqlite3').exists():
    print('No database at the configured location; do not reset or overwrite it.')
else:
    with sqlite3.connect(f'file:{p / "trf.sqlite3"}?mode=ro',uri=True) as c:
        for kind in ('recent','childhood'):
            ids=[r[0] for r in c.execute('SELECT id FROM photos WHERE kind=?',(kind,))]
            print(kind, 'records:', len(ids), 'missing image files:', sum(not (p/'photos'/f'{i}.jpg').exists() for i in ids))
PY
```

Homepage avatars use each person’s separately uploaded Homepage Portrait. Colorful initials appear until a portrait is supplied. Portraits use the same protected persistent storage as other images, with a one-portrait limit per friend; they do not consume recent-photo slots or appear in Halloween Archives.
