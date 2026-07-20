# 🔧 Fix: Database Persistence on Render

## Problem
When you redeploy your app, the database gets wiped because SQLite data is stored in ephemeral container storage.

## Solution: Use PostgreSQL on Render

### ✅ What I Just Fixed
- Updated `render.yaml` to use PostgreSQL instead of SQLite
- Configured automatic database connection via environment variables
- Your data will now persist across redeployments!

---

## 🚀 How to Deploy (Updated Steps)

### 1️⃣ Push Updated Code to GitHub
```bash
cd /path/to/work-location-tracker
git add render.yaml
git commit -m "Add PostgreSQL database for persistent storage"
git push origin main
```

### 2️⃣ Deploy on Render (with PostgreSQL)

1. Go to https://render.com
2. Sign in to your dashboard
3. **If you already have a service running:**
   - Delete the old service (it was using SQLite)
   - Settings → Scroll down → "Delete Service"
   
4. **Create New Web Service:**
   - Click "New" → "Web Service"
   - Connect your GitHub repo
   - Select `InDigitalMedia/work-location-tracker`
   - **Root Directory**: `backend`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app:app --host 0.0.0.0 --port $PORT`
   
5. **Add Environment Variables:**
   - Click "Add Environment Variable"
   - Key: `PYTHONPATH`
   - Value: `/opt/render/project/src`
   - Click "Save"
   
6. **Click "Create Web Service"**
7. **Render will automatically:**
   - Create a PostgreSQL database (`worktracker-db`)
   - Set up the connection string
   - Configure your app to use it

8. **Wait 10-15 minutes** for the first deployment

---

### 3️⃣ Your Data Now Persists! 🎉

Every time you redeploy:
- ✅ Database stays intact
- ✅ All your work entries are preserved
- ✅ No more losing data on redeploy

---

## 🗄️ Database Details

**Free Tier Limits:**
- 1GB storage (plenty for thousands of entries)
- 90 days retention
- Automatic backups

**Connection Info (handled automatically):**
- Database: `worktracker`
- Host: Auto-configured by Render
- Credentials: Stored securely by Render

---

## 🔄 How to Verify It's Working

### Check Render Dashboard:
1. Go to your Render dashboard
2. You should see two services:
   - `work-tracker-api` (your backend)
   - `worktracker-db` (your PostgreSQL database)

### Test Your App:
1. Add some entries via the frontend
2. Redeploy your backend
3. Check that entries are still there ✅

---

## 💰 Cost

**Still FREE on Render's free tier!**
- Web service: Free
- PostgreSQL database: Free (90 days retention)
- Total: $0/month

---

## 🆘 Troubleshooting

### "Can't connect to database" error:
- Check Render dashboard → Your service → Logs
- Look for connection string errors
- Make sure the database service exists in your dashboard

### "Table doesn't exist" error:
- This is normal on first deployment
- Your app will auto-create tables on startup
- Check logs to confirm tables were created

### Database seems empty after migration:
- Your old SQLite data is gone (expected)
- Start fresh with new entries
- Future redeploys will keep your data

---

## 📝 What Changed

### Files Modified:
- ✅ `render.yaml` - Added PostgreSQL database configuration
- ✅ Your app code already supports PostgreSQL (no changes needed)

### What Your Code Does:
1. Reads `DATABASE_URL` from environment
2. Converts `postgres://` to `postgresql://` (for compatibility)
3. Connects to PostgreSQL automatically
4. Creates tables on first run

---

## ✅ You're All Set!

Your database will now persist across redeployments. No more losing data! 🎉

To deploy:
1. Commit and push the changes
2. Create a new Render service (or update existing)
3. Render will handle the PostgreSQL setup automatically

---

## 🎯 Next Steps

1. **Backend**: Deploy with PostgreSQL (above)
2. **Frontend**: Deploy to Vercel (unchanged, follow previous guide)
3. **Test**: Add entries, redeploy, verify data persists
4. **Share**: Give your team the frontend URL

Enjoy your persistent database! 🚀

