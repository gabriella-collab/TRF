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

A shared password gives all signed-in friends access to edit every page. Names are not individual identities. Concurrent editing uses the last saved submission. Selecting photos does not save unsaved text answers; save answers first.

Each image upload is limited to 10 MB, five recent photos, and one childhood photo per friend. Images are decoded and re-encoded as JPEG with no location metadata. HEIC is not supported: export it as JPG first. Captions apply to all photos in an upload batch. Remove and upload again to replace a photo or caption.

The homepage does not use the deck's cover photo as a real group portrait. It uses a typographic collage until an approved photo is provided.

## Validate

```sh
cd /workspace/TRF
/workspace/trf-venv/bin/python -m unittest -v
```

Tests cover private routes, CSRF, incorrect passwords and throttling, all eleven pages, response persistence across app restarts, group updates, derived gratitude/Halloween content, output escaping, uploads, photo access, count limits, invalid files, deletion, and logout.

No hosting deployment or public URL is created by running this repository.
