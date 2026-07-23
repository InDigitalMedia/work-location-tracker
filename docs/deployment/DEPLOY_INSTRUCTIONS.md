# 🚀 Quick Deployment Guide for In Office

## Your Repository
- GitHub: https://github.com/InDigitalMedia/in-office
- You're ready to deploy!

---

## 📍 **Step 1: Deploy Backend to Render**

1. **Go to**: https://render.com
2. **Sign up** (use GitHub)
3. **Click "New" → "Web Service"**
4. **Connect your GitHub account** and select `InDigitalMedia/in-office`
5. **Configure**:
   - Name: `work-tracker-api`
   - Region: Choose closest to you
   - Branch: `main`
   - Root Directory: `backend`
   - Runtime: `Python 3`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
6. **Click "Create Web Service"**
7. **Wait** 10-15 minutes for first deployment
8. **Copy your backend URL** (e.g., `https://work-tracker-api-xxxx.onrender.com`)

---

## 🎨 **Step 2: Deploy Frontend to Vercel**

1. **Go to**: https://vercel.com
2. **Sign up** (use GitHub)
3. **Click "Add New Project"**
4. **Import** your repository `InDigitalMedia/in-office`
5. **Configure**:
   - Root Directory: `frontend`
   - Framework Preset: Auto-detect (Vite)
   - Build Command: `npm run build`
   - Output Directory: `dist`
6. **IMPORTANT - Add Environment Variable**:
   - Name: `VITE_API_BASE`
   - Value: Your Render backend URL from Step 1 (e.g., `https://work-tracker-api-xxxx.onrender.com`)
   - Click "Save"
7. **Click "Deploy"**
8. **Wait** 2-3 minutes
9. **Done!** 🎉

---

## ✅ **Your App is Live!**

- Your app will be at: `https://your-project-name.vercel.app`
- Share this URL with your team of 40-50 people
- They can access it from anywhere!

---

## 💰 **Cost**

- **$0/month** - 100% free!
- Render free tier: May sleep after 15 minutes of inactivity (wakes up on first request)
- Vercel: Free forever for personal projects

---

## 🐛 **Troubleshooting**

### Backend sleeps?
- First request after sleep takes ~30 seconds to wake
- Consider upgrading Render to Always On ($7/month) if needed

### Frontend can't connect?
- Check `VITE_API_BASE` environment variable in Vercel
- Make sure backend URL has no trailing slash

### Data resets?
- ✅ **FIXED!** Now using PostgreSQL with persistent storage
- See `DEPLOY_WITH_PERSISTENT_DB.md` for details

---

## 📊 **What Your Team Will See**

When they open your link, they'll be able to:
- Enter their name
- Select their work location for the week
- See who's working where on the dashboard
- No login required - completely open!

---

## 🎯 **Next Steps**

1. Deploy to Render and Vercel
2. Test the app
3. Share the Vercel URL with your team
4. Monitor usage in both dashboards

Good luck! 🚀

