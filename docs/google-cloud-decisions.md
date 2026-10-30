# Google Cloud migration decisions

Status: decisions recorded only. Implementation not started.

Implementation plan: `docs/google-cloud-setup.md`.

Date: 2026-10-29

## Target stack

- Frontend: Firebase App Hosting (Next.js).
- Backend: FastAPI on Cloud Run.
- Database: Cloud Firestore, Native mode, same project.
- Auth: Firebase Authentication with the Google provider only.
- Secrets: Secret Manager.
- Build: Cloud Build and Artifact Registry.

## Decisions

1. **Source of truth: Option A.**
   Keep Python memory as the runtime source of truth. Firestore stays the durable
   backup and restore source. Cloud Run runs with `--max-instances=1`. Repository
   interfaces stay stable so a later move to Firestore can be contained.

2. **Frontend host: App Hosting.**
   Use Firebase App Hosting for the Next.js frontend. The existing
   `firebase.json` `apphosting` block is the starting point.

3. **Authentication: Google only.**
   Remove the password-based admin path (`ADMIN_PASSWORD = "1234"`,
   `/admin/session` password flow, `Admin-Session-Token` admin login). Admin and
   GOD identity come from the verified Google email.

4. **Region: closest available.**
   Use `me-west1` (Tel Aviv) if Firestore supports it; otherwise use
   `europe-west1` (Belgium). Firestore location is permanent, so verify before
   creating the project. Keep Firestore, Cloud Run, and App Hosting in the same
   area.

5. **Domain: Google defaults first.**
   Use the default `*.hosted.app` and `*.run.app` hostnames. Add a custom domain
   later.

## Open question

- Players: keep display-name-only join, or require Google sign-in for players
  too? Not decided.

## Decided 2026-10-30

- Login uses Google sign-in for everyone (players, admin, GOD). No password, no
  GOD access key.
- After Google sign-in, ask for a nickname. The nickname is the display name
  shown in rooms and on the scoreboard.
- Roles: `tal.vazanas@gmail.com` = god, `shachar383838@gmail.com` = admin.
  Everyone else is a player.
- Local development uses the Firebase Auth emulator so sign-in works without a
  real project. Production verifies real Google ID tokens.

## Constraints to remember

- Firestore location cannot be changed after project creation.
- Firestore, App Hosting, and Cloud Run regions should match to avoid latency.
- The backend Firestore publisher currently uses the emulator-only
  `Authorization: Bearer owner` header. Production needs Application Default
  Credentials.
- The frontend always connects to the Firestore emulator today. Production needs
  an env-gated switch.
- The special users live in `backend/app/special_users.py`:
  `tal.vazanas@gmail.com` is `god`, `shachar383838@gmail.com` is `admin`.
