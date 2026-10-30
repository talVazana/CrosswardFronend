# Google Cloud setup and configuration

Status: plan. Nothing is deployed yet. The app runs locally only.

This document lists what must be created and configured to run the app on
Firebase and Google Cloud. It also lists the code changes that must land before
each step works.

## Target architecture

- Frontend: Next.js on Firebase App Hosting.
- Backend: FastAPI on Cloud Run, `--max-instances=1`.
- Database: Cloud Firestore, Native mode, one project with App Hosting.
- Auth: Firebase Authentication, Google provider only.
- Secrets: Secret Manager.
- Images: Artifact Registry, built by Cloud Build.

The backend keeps game state in memory and uses Firestore as durable backup and
restore source. `--max-instances=1` is mandatory for this model.

## 1. Prerequisites

1. Install the Google Cloud CLI (`gcloud`). It is not installed on this machine.
2. Run `gcloud auth login` and `gcloud config set project <PROJECT_ID>`.
3. Confirm billing is enabled on the project.
4. Install or update the Firebase CLI. Version 15.23.0 is installed.
5. Run `firebase login`.

Decide the project ID before creating anything. Firestore location cannot be
changed later.

## 2. Create the project

Create one Google Cloud project for all services, or a Firebase project that
creates the same underlying project.

Set these values:

| Setting | Value |
|---|---|
| Project ID | To be decided |
| Display name | Crossword Arena |
| Billing account | Must be active |
| Firestore location | `me-west1` if supported, otherwise `europe-west1` |
| Default region for Cloud Run | Same area as Firestore |

Then update `.firebaserc` from `demo-crossword-arena` to the real project ID.

### Enable APIs

- Cloud Firestore API
- Firebase Authentication
- Identity Toolkit API
- Cloud Run API
- Cloud Build API
- Artifact Registry API
- Secret Manager API
- Firebase App Hosting API

## 3. Firestore

### Create the database

Create a Firestore database in Native mode in the chosen location.

Collections written by the backend:

- `rooms`
- `room_images`
- `puzzle_answers`
- `sessions`
- `admin_sessions`
- `submissions`
- `player_states`
- `player_identities`
- `player_totals`
- `admin_solves`
- `settings` (document `god`, runtime limit overrides)
- `special_users` (document `users`, roles by email)

### Deploy rules and indexes

Deploy `firestore.rules` and `firestore.indexes.json` with:

```powershell
firebase deploy --only firestore
```

The rules must allow:

- Public read of `rooms`. The frontend uses `onSnapshot` before sign-in.
- No client writes. All writes come from the backend service account, which
  bypasses rules.
- Deny everything else for clients.

### Backend connection changes

`backend/app/services/firestore_publisher.py` currently targets the emulator:

- URL is built from `FIRESTORE_EMULATOR_HOST`.
- Requests use `Authorization: Bearer owner`.

Production needs:

1. Detect production mode from an environment variable such as
   `FIRESTORE_MODE=production`.
2. Use the Firestore REST API with Application Default Credentials, or switch to
   `google-cloud-firestore`. The second option is simpler and adds one
   dependency.
3. Use `FIRESTORE_PROJECT_ID` from the environment.
4. Keep the emulator path for local development and tests.

The module must fail closed: if production mode is requested and credentials are
missing, startup must log an error and refuse to accept game traffic rather than
pretend to persist.

### Frontend connection changes

`frontend/src/lib/firebase.ts` always calls `connectFirestoreEmulator`. Production
needs:

1. `NEXT_PUBLIC_FIREBASE_PROJECT_ID` set to the real project.
2. Emulator connection only when `NEXT_PUBLIC_FIRESTORE_EMULATOR_HOST` is set.
3. Firebase web app config values: API key, auth domain, app ID. The current
   client initializes with project ID only, which is not valid for production.

## 4. Authentication

Enable the Google provider in Firebase Authentication. Add the App Hosting
domain and `localhost` to authorized domains.

### Roles

Roles come from the verified email address:

| Email | Role |
|---|---|
| `tal.vazanas@gmail.com` | God |
| `shachar383838@gmail.com` | Admin |

The role list must remain server-side. Firestore storage for `special_users`
already exists; keep it as the runtime source and seed it from these defaults.

### Code changes required

1. Remove `ADMIN_PASSWORD = "1234"` and the password branch of
   `/admin/session`.
2. Verify Firebase ID tokens on the backend. Either add `firebase-admin` or
   verify Google ID tokens with the public keys.
3. Resolve admin identity from the verified email, not from a password cookie.
4. Replace the GOD access key with a verified GOD email. Keep the key path only
   for local development, controlled by an environment flag.
5. Add frontend sign-in, token refresh, and sign-out.
6. Decide whether players must sign in. Today players join by display name only.
   If players stay anonymous, room read rules must remain public.

Admin and GOD must never be able to escalate each other:

- GOD manages limits and special users, not game actions.
- Admin runs game actions, not user management.

## 5. Secret Manager

Create one secret per value:

| Secret | Used by | Notes |
|---|---|---|
| `GEMINI_API_KEY` | Backend | Gemini clue extraction |
| `TELEGRAM_BOT_TOKEN` | Backend | Telegram announcements |
| `TELEGRAM_CHAT_ID` | Backend | Target group |
| `GOD_ACCESS_KEY` | Backend | Local fallback only, remove after auth |

Grant the Cloud Run service account `roles/secretmanager.secretAccessor` on each
secret. Do not put secret values in the image, in `apphosting.yaml`, or in git.

`PUBLIC_APP_URL` is not a secret. Set it to the App Hosting URL so Telegram join
links are correct.

## 6. Backend on Cloud Run

### Build inputs

- Add `backend/Dockerfile`. Base image `python:3.12-slim`. Install
  `backend/requirements.txt`. Run `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- Add `backend/.gcloudignore` or a root `.gcloudignore` that excludes tests,
  fixtures, caches, and the frontend.
- Build and push to Artifact Registry in the same region.

### Service configuration

| Setting | Value |
|---|---|
| Region | Same as Firestore |
| Min instances | `1` recommended, `0` allowed but adds cold starts |
| Max instances | `1` (required by in-memory source of truth) |
| Concurrency | `80` default is fine |
| Request timeout | `300` seconds, above the 120 second image job cap |
| Memory | `1 GiB` minimum |
| CPU | `1` |
| Service account | Dedicated runtime account |

Runtime service account roles:

- `roles/datastore.user`
- `roles/secretmanager.secretAccessor`
- `roles/logging.logWriter`

### Environment variables

| Variable | Value |
|---|---|
| `ALLOWED_ORIGINS` | App Hosting URL |
| `FIRESTORE_PROJECT_ID` | Project ID |
| `FIRESTORE_MODE` | `production` |
| `PUBLIC_APP_URL` | App Hosting URL |
| `GEMINI_API_KEY` | From Secret Manager |
| `TELEGRAM_BOT_TOKEN` | From Secret Manager |
| `TELEGRAM_CHAT_ID` | From Secret Manager |

Limit overrides and kill switches keep their existing names:
`IMAGE_PARSER_TIMEOUT_SECONDS`, `IMAGE_PROCESSING_TIMEOUT_SECONDS`,
`GEMINI_TIMEOUT_SECONDS`, `GEMINI_MAX_ATTEMPTS`, `MAX_GRID_SIZE`, `MAX_CLUES`,
`MAX_CLUE_LENGTH`, `MAX_TOTAL_CLUE_CHARS`, `MAX_UPLOAD_BYTES`,
`MAX_IMAGE_DIMENSION`, `GEMINI_MAX_PER_HOUR`, `GEMINI_MAX_PER_DAY`,
`IMAGE_PARSER_ENABLED`, `GEMINI_EXTRACTION_ENABLED`,
`TELEGRAM_NOTIFICATIONS_ENABLED`.

### Health and access

- Keep `/health` unauthenticated.
- Allow unauthenticated invocations, or add an identity-aware proxy if players
  must sign in. The frontend calls the backend directly, so Cloud Run must accept
  requests from the browser.
- Confirm CORS allows the App Hosting origin only.

### Known production gaps in current code

- `google_clues.py` reads `GEMINI_API_KEY` from the environment. That is fine on
  Cloud Run when the value is injected from Secret Manager.
- Runtime limits and the Gemini quota are process-local. A restart resets the
  counters and restores saved limits from Firestore. This is acceptable with one
  instance but must be documented.
- In-memory Telegram and quota logs are not persisted.

## 7. Frontend on App Hosting

Add `frontend/apphosting.yaml` with:

- Run time and memory.
- Environment variables: `NEXT_PUBLIC_BACKEND_URL`, `NEXT_PUBLIC_FIREBASE_PROJECT_ID`,
  `NEXT_PUBLIC_FIREBASE_API_KEY`, `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN`,
  `NEXT_PUBLIC_FIREBASE_APP_ID`.
- Secret references if any are needed at runtime. Public Firebase values are not
  secrets.

Deploy with:

```powershell
firebase init apphosting
firebase deploy --only apphosting
```

Then:

1. Set `ALLOWED_ORIGINS` on Cloud Run to the final `*.hosted.app` URL.
2. Set `PUBLIC_APP_URL` for Telegram join links.
3. Add the hosting domain to Firebase Auth authorized domains.
4. Smoke-test cross-origin requests from the deployed frontend.

## 8. Cost and abuse controls

Configure all of these before opening the site:

- Billing budget alert in Google Cloud Billing.
- Cloud Run `--max-instances=1`.
- Firestore rules deny client writes.
- Gemini kill switch `GEMINI_EXTRACTION_ENABLED`.
- Upload size, image dimension, grid size, clue count, and clue length limits.
- Gemini hourly and daily quotas. Defaults: 5 per hour, 10 per day.
- Telegram kill switch `TELEGRAM_NOTIFICATIONS_ENABLED`.
- App Check for the frontend, optional but recommended before public launch.

## 9. Verification checklist

After deployment, verify in this order:

1. `GET /health` returns `{"status": "ok"}` from the Cloud Run URL.
2. Cloud Run logs show Firestore restore succeeded, not emulator fallback.
3. Frontend loads the room list from Firestore, not from the emulator.
4. Creating a room with `docs/a.jpg` succeeds and the room appears in Firestore.
5. A second player joins from another browser and sees live updates.
6. Submissions score correctly and survive a backend restart.
7. GOD page works for the GOD email and rejects everyone else.
8. Limits changed in GOD survive a restart.
9. Telegram start and finish messages arrive in the group.
10. Upload over the limit, oversized grid, and oversized clue all fail with a
    clear message.
11. Hourly Gemini quota blocks the next job.
12. `firebase deploy --only firestore` leaves rules unchanged after a redeploy.

## 10. Rollback

- Cloud Run keeps revisions. Route traffic to the previous revision if a deploy
  fails.
- App Hosting keeps previous rollouts. Roll back from the console.
- Firestore rules have no automatic rollback. Keep the last known good copy in
  git and redeploy it.
- Do not delete the Firestore database to roll back. Restore from export instead.

## 11. Open decisions

1. Project ID and Firestore region.
2. Whether players must sign in with Google, or keep display-name join.
3. Whether runtime limits and quotas move to Firestore as shared state later.
4. Whether to keep a local GOD key fallback after Google auth is live.
