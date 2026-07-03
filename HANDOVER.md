# Ownership Handover — Work Location Tracker

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

Reference: `vercel.json`, `docs/deployment/HOSTING_GUIDE.md`. (Vercel occasionally renames settings pages — if a label below doesn't match exactly, use the dashboard search bar for "transfer".)

### 2a. Cam creates an account

- [ ] Go to `vercel.com/signup` and sign up (or log in) with the email you gave Shaz in Step 0.

### 2b. Shaz starts the transfer

- [ ] Log in to the Vercel dashboard and open the `work-location-tracker` project.
- [ ] Go to the project's **Settings** tab.
- [ ] Scroll to the bottom to the **Transfer Project** section.
- [ ] Click **Transfer**, and enter Cam's Vercel username or email as the destination.
- [ ] Confirm by typing the project name when prompted.
- [ ] Vercel emails Cam a transfer confirmation link.

### 2c. Cam accepts and reconnects

- [ ] Open the transfer email and click **Accept Transfer** while logged into your Vercel account.
- [ ] Go to **Settings → Git** on the project and reconnect it to the repo's new location (`github.com/<cam-username>/work-location-tracker`) — the Git link typically breaks once GitHub ownership moves, since the integration was authorized under Shaz's GitHub account.
- [ ] Go to **Settings → Environment Variables** and confirm the variable pointing at the backend (e.g. `VITE_API_BASE`) still has the correct Render URL.
- [ ] Trigger a redeploy (Deployments tab → ⋯ on the latest deployment → **Redeploy**, or just push a commit) and confirm the site loads.

## Step 3 — Render (backend API + Postgres database)

Reference: `render.yaml`, `docs/deployment/HOSTING_GUIDE.md`, `docs/deployment/DEPLOY_WITH_PERSISTENT_DB.md`. Render's ownership model is per-**workspace**, not per-service — the cleanest path is inviting Cam into Shaz's workspace as Admin, then transferring the whole workspace to him.

### 3a. Cam creates an account

- [ ] Go to `render.com` and sign up (or log in) with the same email from Step 0.

### 3b. Shaz invites Cam to the workspace

- [ ] Log in to the Render dashboard.
- [ ] Open the workspace switcher (top-left) and select the workspace this project is in.
- [ ] Go to **Settings → People** (sometimes labeled "Members" or "Team").
- [ ] Click **Invite Member**, enter Cam's email, and set his role to **Admin**.

### 3c. Cam accepts, Shaz transfers ownership

- [ ] Cam accepts the invite email and joins the workspace.
- [ ] Shaz goes to **Settings → General** (or wherever workspace ownership lives) and looks for a **Transfer Ownership** action to hand the workspace itself to Cam. If Render doesn't expose a direct "transfer workspace" button in your account, keep Cam as Admin and skip straight to Step 6 (Shaz removing himself) instead — an Admin has full control already, and removing Shaz effectively completes the handover.

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
- [ ] Remove Shaz from the Vercel project/team.
- [ ] Remove Shaz from the Render workspace.
- [ ] Confirm the old SendGrid API key (if it was Shaz's) is revoked once the new one is confirmed working.

## Not relevant — safe to ignore

`ecosystem.config.js` and `config/com.worktracker.*.plist` reference a local PM2/launchd setup on Shaz's own Mac. Confirmed dead (nothing running, logs stop Oct 31 2025) — production genuinely runs on Render + Vercel, not anyone's laptop. Delete these files or leave them; they don't affect the transfer.
