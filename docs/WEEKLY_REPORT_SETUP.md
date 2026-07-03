# 📧 Weekly Report Setup Guide

## Overview

The system can automatically generate and email a weekly report showing:
- **Days each person was NOT working from home** (excluding holidays)
- Sent every **Monday morning** for the **previous week** (Mon-Fri)

## What the Report Shows

- **Team Member Name**
- **Days in Office/Client Site** (count of Neal Street + Client Office days)
- **Excludes**: WFH days and Holidays

## Setup Instructions

### Step 1: Configure Email Settings

**Recommended: SendGrid (Free Tier: 100 emails/day)**

SendGrid is the recommended option because:
- ✅ Works reliably from cloud platforms (no firewall issues)
- ✅ Free tier: 100 emails/day (perfect for weekly reports)
- ✅ Easy setup

**Setup SendGrid:**

1. **Create a SendGrid account:**
   - Go to https://sendgrid.com (free account)
   - Sign up and verify your email

2. **Create an API Key:**
   - SendGrid Dashboard → Settings → API Keys
   - Create API Key → "Restricted Access" → Give it "Mail Send" permission
   - Copy the API key (you'll only see it once!)

3. **Verify your sender email:**
   - Settings → Sender Authentication
   - Verify Single Sender (for testing) OR set up Domain Authentication (for production)
   - Use the email you want to send from (e.g., `you@indigital.marketing`)

4. **Add to Render Environment Variables:**
   ```
   SMTP_SERVER=smtp.sendgrid.net
   SMTP_PORT=587
   SMTP_USER=apikey
   SMTP_PASSWORD=your-sendgrid-api-key-here
   FROM_EMAIL=you@indigital.marketing
   REPORT_EMAILS=recipient1@indigital.marketing,recipient2@indigital.marketing
   ```

   `FROM_EMAIL` and `REPORT_EMAILS` are required — the app raises an error on startup of the report job if either is unset, rather than falling back to any hardcoded address.

**Alternative: Gmail or Office 365**

If you prefer to use your existing email:

```
SMTP_SERVER=smtp.gmail.com  # or smtp.office365.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
FROM_EMAIL=your-email@gmail.com
REPORT_EMAILS=recipient1@company.com,recipient2@company.com
```

**For Gmail:** Enable 2FA → Generate App Password: https://myaccount.google.com/apppasswords

**For Office 365:** May require App Password if MFA enabled. Note: Some cloud platforms have connectivity issues with Office 365 SMTP.

### Step 2: Set Up Cron Job

**Option A: Using Render Cron Job (Recommended)**

1. Go to **Render Dashboard** → **New** → **Cron Job**
2. Configure:
   - **Name**: `weekly-report`
   - **Repository**: Your GitHub repo (same as API)
   - **Root Directory**: `backend`
   - **Schedule**: `0 8 * * 1` (Every Monday at 8 AM UTC)
   - **Command**: `python cron_job.py`
   - **Environment Variables**: 
     - Copy all SMTP settings from your API service
     - Copy DATABASE_URL from your API service
     - Set `REPORT_EMAILS` (same as in API service)
   - **Plan**: Free

**Option B: Using HTTP Endpoint + External Cron Service**

Call the API endpoint via external service:

1. Use **cron-job.org** (free) or similar:
   - URL: `https://your-api-url.onrender.com/admin/send-weekly-report`
   - Method: `POST`
   - Schedule: Every Monday at 8 AM UTC
   - No authentication needed (or add API key header if you secure the endpoint)

Other options:
- **EasyCron** (free tier)
- **Zapier** (paid)
- Any service that can make HTTP POST requests on a schedule

### Step 3: Test the Report

**Manual Test (without waiting for Monday):**

```bash
curl -X POST "https://your-api-url.onrender.com/admin/send-weekly-report?recipients=test@example.com"
```

Or visit in browser (GET will work too for testing):
```
https://your-api-url.onrender.com/admin/send-weekly-report?recipients=test@example.com
```

## Schedule Format

The cron schedule `0 8 * * 1` means:
- `0` = minute 0
- `8` = hour 8 (8 AM)
- `*` = every day of month
- `*` = every month
- `1` = Monday

**Adjust timezone:**
- Render cron jobs use UTC
- To send at 8 AM your local time, adjust:
  - **9 AM UK** (BST) = `0 7 * * 1` (7 AM UTC)
  - **8 AM EST** = `0 13 * * 1` (1 PM UTC)
  - **8 AM PST** = `0 16 * * 1` (4 PM UTC)

## Report Format

The email includes:
- **HTML table** with team members and their office/client days
- **Professional styling** (black/white theme matching your app)
- **Date range** for the reported week
- **Generated timestamp**

## Troubleshooting

**Report not sending:**
1. Check Render logs for errors
2. Verify SMTP credentials are correct
3. Test manually with curl command above
4. Check spam folder

**Report shows wrong data:**
- Report uses **previous week** (last Monday-Friday)
- Make sure people are entering data correctly
- Check database directly if needed

**Cron job not running:**
- Verify cron job is active in Render dashboard
- Check cron job logs
- Ensure API URL is correct in cron command
- Consider using external cron service if Render cron isn't working

## Security Notes

- The endpoint is currently **unprotected** (anyone can call it)
- For production, add authentication:
  - API key header check
  - Render cron jobs can set a secret header
  - Or use Render's built-in auth features

## Example Environment Variables Summary

**SendGrid (Recommended):**
```bash
SMTP_SERVER=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
FROM_EMAIL=you@indigital.marketing
REPORT_EMAILS=recipient1@indigital.marketing,recipient2@indigital.marketing

# Database (auto-set by Render)
DATABASE_URL=postgresql://...
```

**Gmail/Office 365 (Alternative):**
```bash
SMTP_SERVER=smtp.gmail.com  # or smtp.office365.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
FROM_EMAIL=your-email@gmail.com
REPORT_EMAILS=recipient1@company.com,recipient2@company.com

# Database (auto-set by Render)
DATABASE_URL=postgresql://...
```

---

**That's it!** Once configured, reports will automatically send every Monday morning. 🎉

