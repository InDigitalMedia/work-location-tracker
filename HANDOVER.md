# Ownership Handover — Work Location Tracker

> An interactive, checkable version of this doc is at [`HANDOVER.html`](HANDOVER.html) — open it in a browser (double-click it locally, or view it via GitHub's raw link) to tick items off as you go. This Markdown file is the source of truth; the HTML mirrors its content.

**For: Cam**
**From: Shaz (`shaz.ahmed@indigital.marketing`) — last day is July 17, 2026**
**Deadline: complete everything below before July 17, 2026**

This app currently depends entirely on Shaz's personal accounts (GitHub, Vercel, Render, and probably SendGrid). Nothing here transfers automatically when Shaz leaves — if this doc isn't completed first, the site and the weekly report email will silently break the day his accounts are deactivated. Cam is taking ownership on his own personal accounts (no company org exists for this yet).

If Cam is using Claude Code, this doc is written so it can be handed the whole task — it can run the repo-side git commands and verification steps, but the actual account transfers on GitHub/Vercel/Render must be done by a human in each dashboard (Claude Code has no access to those accounts).

## Step 0 — Cam: send Shaz these three things first

Shaz needs these to send the transfer/invite requests:

- [ ] Your GitHub username
- [ ] The email you want tied to Vercel and Render
- [ ] Confirmation you can accept invites/transfers promptly (they usually expire after a few days)

## Step 1 — GitHub repo transfer

- [ ] Shaz: go to `github.com/shaz1409/work-location-tracker` → Settings → General → "Danger Zone" → **Transfer ownership** → enter Cam's GitHub username.
- [ ] Cam: accept the transfer email from GitHub.
- [ ] Cam: once transferred, the repo URL becomes `github.com/<cam-username>/work-location-tracker`. Update your local clone's remote:

  ```bash
  git remote set-url origin https://github.com/<cam-username>/work-location-tracker.git
  git remote -v   # confirm it points to the new URL
  ```

## Step 2 — Vercel (frontend hosting)

Reference: `vercel.json`. The frontend is a fully stateless static build (no database, no persisted state), so rather than transferring Shaz's existing Vercel project — which now requires picking a destination **team** even for a one-person handover — Cam just sets up a brand-new Vercel project on his own account. Nothing is lost by doing it this way, and it avoids the team/transfer flow entirely.

### 2a. Cam creates an account

- [ ] Go to `vercel.com/signup` and sign up (ideally via "Continue with GitHub," using the same GitHub account that now owns the repo after Step 1 — this makes importing the repo a one-click action).

### 2b. Cam imports the project fresh

- [ ] Dashboard → **Add New...** → **Project**.
- [ ] Import `work-location-tracker` (Vercel will list it once it has access to Cam's GitHub account/repos).
- [ ] Leave **Root Directory** as the repo root — do **not** set it to `frontend`. The root `package.json`'s build script already `cd`s into `frontend`, builds it, and copies the output to the repo root, and `vercel.json` (at the repo root) expects that. Overriding Root Directory to `frontend` will break the build.
- [ ] Framework preset, build command (`npm run build`), and output directory (`dist`) should all auto-fill from `vercel.json` — leave as detected.
- [ ] Add environment variable `VITE_API_BASE` = the Render backend URL (e.g. `https://work-tracker-api.onrender.com` — same service from Step 3 below, unchanged since Render isn't being recreated).
- [ ] Click **Deploy** and wait ~2-3 minutes.
- [ ] Confirm the deployed URL loads the app and can submit/view entries.

### 2c. Custom domain (only if one is currently in use)

- [ ] Shaz: check the old Vercel project's **Settings → Domains** for any custom domain attached.
- [ ] If one exists: Cam adds the same domain under his new project's **Settings → Domains**, then DNS gets repointed to Cam's project/nameservers. Expect a few minutes of downtime while it propagates — plan this for a low-traffic moment.

## Step 3 — Render (backend API + Postgres database)

Reference: `render.yaml`, `docs/deployment/HOSTING_GUIDE.md`, `docs/deployment/DEPLOY_WITH_PERSISTENT_DB.md`. Render's ownership model is per-**workspace**, not per-service.

**Important — do not have Cam create an independent Render setup from scratch.** Unlike Vercel, the backend isn't stateless: `worktracker-db` (a Postgres database) holds every historical attendance entry. A fresh Render account deploying `render.yaml` from scratch would provision a brand-new, empty database — silently wiping the history. So instead, Cam is invited directly into Shaz's existing workspace as Admin, keeping the exact same database. This is the whole handover mechanism here — there's no separate "transfer ownership" button to look for; an Admin already has full functional control, and Shaz removing his own account access in Step 6 is what finalizes it.

### 3a. Cam creates an account

- [ ] Go to `render.com` and sign up (or log in) with the same email from Step 0.

### 3b. Shaz invites Cam to the workspace

- [ ] Log in to the Render dashboard.
- [ ] Open the workspace switcher (top-left) and select the workspace this project is in.
- [ ] Go to **Settings → People** (sometimes labeled "Members" or "Team").
- [ ] Click **Invite Member**, enter Cam's email, and set his role to **Admin**.

### 3c. Cam accepts

- [ ] Cam accepts the invite email and joins the workspace. No further action needed here — Admin access is sufficient, and Step 6 (Shaz removing himself) is what completes the handover.

### 3d. Cam verifies the service

- [ ] Open the `api` service → **Settings → Build & Deploy** and confirm the connected GitHub repo points to `github.com/<cam-username>/work-location-tracker` — reconnect if it still points to the old location.
- [ ] Open the `api` service → **Environment** tab and confirm `DATABASE_URL` is still auto-populated from the `worktracker-db` database (via the `fromDatabase` link in `render.yaml`).
- [ ] **Do not delete or recreate the `worktracker-db` database at any point in this process** — it holds all historical entries. Ownership/workspace changes keep the data; recreating the database from scratch would wipe it.

## Step 4 — Email sending (SendGrid) and Render environment variables

Reference: `docs/WEEKLY_REPORT_SETUP.md`, `backend/report.py`.

The weekly attendance report email is sent via SendGrid, configured through Render env vars. As of this handover, there are **no hardcoded fallback values** — `backend/report.py` raises an error if these are missing, rather than silently defaulting to Shaz's email:

```bash
SMTP_SERVER=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=<SendGrid API key>
FROM_EMAIL=<sender address, e.g. cam@indigital.marketing>
REPORT_EMAILS=<comma-separated recipient list>
```

- [ ] Confirm whether the current SendGrid account belongs to Shaz personally. If so:
  - [ ] Cam creates his own SendGrid account (free tier: 100 emails/day) per `docs/WEEKLY_REPORT_SETUP.md`.
  - [ ] Generate a new "Mail Send" API key.
  - [ ] Verify a sender email/domain in SendGrid.
- [ ] Update `SMTP_PASSWORD` and `FROM_EMAIL` on Render with the new values.
- [ ] Update `REPORT_EMAILS` to the correct recipient list going forward.
- [ ] Manually trigger `/admin/send-weekly-report` (see `docs/WEEKLY_REPORT_SETUP.md`) once to confirm email sends successfully end-to-end.

⚠️ Note: that endpoint is currently **unprotected** — anyone who finds the URL can trigger a send. Worth adding a shared-secret header check at some point; not blocking for handover.

## Step 5 — Verify everything works end-to-end

- [ ] Load the live frontend URL and submit a week's entries.
- [ ] Confirm the dashboard view shows the submission.
- [ ] Confirm the weekly report email arrives (Step 4's manual trigger).
- [ ] Confirm Cam can push a commit and see it auto-deploy on both Vercel and Render.

## Step 6 — Shaz removes himself (do this last, only after Cam confirms everything above)

- [ ] Remove Shaz from the GitHub repo's collaborators (should already be moot after transfer, but check).
- [ ] Shaz deletes his own old Vercel project (Dashboard → project → **Settings** → scroll to **Delete Project**) — Cam's new project is fully independent, so this doesn't affect him.
- [ ] Remove Shaz from the Render workspace (**Settings → People** → remove) — this is the step that actually finalizes Render ownership, since Cam was made Admin rather than a formal transfer happening.
- [ ] Confirm the old SendGrid API key (if it was Shaz's) is revoked once the new one is confirmed working.

## Not relevant — safe to ignore

`ecosystem.config.js` and `config/com.worktracker.*.plist` reference a local PM2/launchd setup on Shaz's own Mac. Confirmed dead (nothing running, logs stop Oct 31 2025) — production genuinely runs on Render + Vercel, not anyone's laptop. Delete these files or leave them; they don't affect the transfer.
