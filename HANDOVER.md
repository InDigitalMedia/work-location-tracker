# Ownership Handover — Work Location Tracker

> An interactive, checkable version of this doc is at [`HANDOVER.html`](HANDOVER.html) — open it in a browser (double-click it locally, or view it via GitHub's raw link) to tick items off as you go. This Markdown file is the source of truth; the HTML mirrors its content.

**For: Cam**
**From: Shaz (`shaz.ahmed@indigital.marketing`) — last day is July 17, 2026**
**Deadline: complete everything below before July 17, 2026**

This app currently depends entirely on Shaz's personal accounts (GitHub, Vercel, and Render). Nothing here transfers automatically when Shaz leaves — if this doc isn't completed first, the site will silently break the day his accounts are deactivated. Cam is taking ownership on his own personal accounts (no company org exists for this yet).

> **Status update (2026-07-20):** All three legs are confirmed done, via different mechanisms than originally planned below (kept for historical context — see the corrected notes under each step). GitHub: repo is at `github.com/InDigitalMedia/work-location-tracker` (an org). Vercel: live production frontend is now `https://in-office.vercel.app`. Render: backend migrated to a new account under `media@indigital.marketing`, live at `https://api-a8uz.onrender.com`, and `/summary/all-users` confirms historical entries (including Shaz's) survived the migration — not a fresh empty database.
>
> The *old* pairing — `work-location-tracker.vercel.app` calling the now-suspended `work-location-tracker.onrender.com` — is dead and orphaned from Shaz's original manual setup. That's expected now that the app has moved to the URLs above; it initially looked like a live outage until this was clarified. Cleanup of the old Vercel project / Render service is still open (see Step 5).

If Cam is using Claude Code, this doc is written so it can be handed the whole task — it can run the repo-side git commands and verification steps, but the actual account transfers on GitHub/Vercel/Render must be done by a human in each dashboard (Claude Code has no access to those accounts).

## Step 0 — Cam: send Shaz these three things first

Shaz needs these to send the transfer/invite requests:

- [ ] Your GitHub username
- [ ] The email you want tied to Vercel and Render
- [ ] Confirmation you can accept invites/transfers promptly (they usually expire after a few days)

## Step 1 — GitHub repo transfer

- [x] Shaz: transferred the repo (destination ended up being the `InDigitalMedia` GitHub org rather than Cam's personal account).
- [x] Cam: accepted the transfer.
- [x] Cam: repo URL is now `github.com/InDigitalMedia/work-location-tracker`; local remote confirmed pointing there via `git remote -v`.

## Step 2 — Vercel (frontend hosting)

> **Done (confirmed 2026-07-20):** live production frontend is `https://in-office.vercel.app` (HTTP 200), and its built JS bundle calls `https://api-a8uz.onrender.com` — matching the migrated Render backend below. The steps under 2a/2b were the original plan; check the actual Vercel dashboard if you need the specifics of how this project is configured (e.g. which account owns it), since that couldn't be verified from the repo alone.

Reference: `vercel.json`. The frontend is a fully stateless static build (no database, no persisted state), so rather than transferring Shaz's existing Vercel project — which now requires picking a destination **team** even for a one-person handover — Cam just sets up a brand-new Vercel project on his own account. Nothing is lost by doing it this way, and it avoids the team/transfer flow entirely.

### 2a. Cam creates an account

- [x] Done — see status note above.

### 2b. Cam imports the project fresh

- [x] Done — see status note above.
- [ ] Confirm **Root Directory** is the repo root (not `frontend`) and `VITE_API_BASE` is set to `https://api-a8uz.onrender.com` — worth a quick dashboard check since these matter for future redeploys even though the current deploy is working.

### 2c. Custom domain (only if one is currently in use)

- [ ] Shaz: check the old Vercel project's **Settings → Domains** for any custom domain attached.
- [ ] If one exists: Cam adds the same domain under his new project's **Settings → Domains**, then DNS gets repointed to Cam's project/nameservers. Expect a few minutes of downtime while it propagates — plan this for a low-traffic moment.

## Step 3 — Render (backend API + Postgres database)

> **Done (confirmed 2026-07-20), via a different mechanism than planned below:** rather than inviting Cam as Admin into Shaz's existing workspace, the backend was migrated to a new Render account under `media@indigital.marketing`. Live at `https://api-a8uz.onrender.com` (HTTP 200) — `/summary/all-users` returns both `Cam Doherty` and `Shaz Ahmed`, confirming `worktracker-db`'s historical entries survived the migration rather than a fresh empty database being provisioned. The steps below were the original plan and are kept for reference; the actual how-it-was-migrated detail (dashboard transfer vs. dump/restore) isn't verifiable from the repo — worth double-checking `media@indigital.marketing`'s access/billing setup directly in the Render dashboard if that matters going forward.

Reference: `render.yaml`, `docs/deployment/HOSTING_GUIDE.md`, `docs/deployment/DEPLOY_WITH_PERSISTENT_DB.md`. Render's ownership model is per-**workspace**, not per-service.

**Original plan (superseded — see status note above; kept for historical context only).** Unlike Vercel, the backend isn't stateless: `worktracker-db` (a Postgres database) holds every historical attendance entry. A fresh Render account deploying `render.yaml` from scratch would provision a brand-new, empty database — silently wiping the history. The original plan was for Cam to be invited directly into Shaz's existing workspace as Admin, keeping the exact same database, rather than creating an independent Render setup from scratch. In practice, the backend was migrated to a new account (`media@indigital.marketing`) instead — and the database came along intact, so the risk this plan was designed to avoid didn't materialize.

### 3a-3d (original plan, superseded — see status note above)

- [x] Render backend is live under the new account with data intact — verified via API, not via the dashboard steps originally planned here.
- [ ] Worth a manual dashboard check: confirm `DATABASE_URL` on the `api-a8uz` service is still linked via `fromDatabase` to `worktracker-db` (per `render.yaml`) rather than a hardcoded string, so future redeploys don't drift.

## Step 4 — Verify everything works end-to-end

- [x] Live frontend (`https://in-office.vercel.app`) loads and its backend (`https://api-a8uz.onrender.com`) responds with real data — verified via API on 2026-07-20.
- [ ] Still worth doing by hand: actually submit a week's entries through the UI and confirm the dashboard reflects it (only API-level checks have been done so far, not a full click-through).
- [ ] Confirm Cam can push a commit and see it auto-deploy on both Vercel and Render.

## Step 5 — Old accounts/services cleanup (do this last, only after everything above is confirmed)

- [ ] Remove Shaz from the GitHub repo's collaborators (should already be moot after transfer, but check).
- [ ] **Old, now-orphaned pairing found 2026-07-20:** `work-location-tracker.vercel.app` (Shaz's original Vercel project) still calls `work-location-tracker.onrender.com` (Shaz's original Render service, currently suspended). Neither is the live app anymore — delete both once confirmed nothing still points at them (e.g. no bookmarked links, no custom domain — see Step 2's original 2c).
- [ ] Remove Shaz from the Render workspace/account (**Settings → People**) if he still has any access to the `media@indigital.marketing` Render account or workspace.

> The weekly report email feature (SendGrid, `backend/report.py`, `/admin/send-weekly-report`) has been removed entirely — the site no longer sends any email, so there's nothing to transfer or re-key here.

## Not relevant — safe to ignore

`ecosystem.config.js` and `config/com.worktracker.*.plist` reference a local PM2/launchd setup — originally hardcoded to Shaz's own Mac, since updated (2026-07-20) to Cam's machine path / made host-agnostic. Confirmed dead either way (nothing running, logs stop Oct 31 2025) — production genuinely runs on Render + Vercel, not anyone's laptop. Delete these files or leave them; they don't affect the transfer.
