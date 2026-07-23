# 🚀 Free Hosting Guide for In Office

## 🎯 **Recommended Setup: Vercel (Frontend) + Render (Backend)**

### **Cost: $0/month** ✅

---

## 📋 **Quick Setup Steps**

### **Step 1: Push to GitHub**

1. Create a new repository on GitHub:
   - Go to https://github.com/new
   - Name it: `in-office`
   - Set it to **Public**
   - **Don't** initialize with README

2. Push your code:
```bash
cd /path/to/in-office

# Add your GitHub repo as remote
git remote add origin https://github.com/YOUR_USERNAME/in-office.git

# Push to GitHub
git branch -M main
git push -u origin main
```

---

### **Step 2: Deploy Backend to Render**

1. **Go to Render**: https://render.com
2. **Sign up** (use GitHub account)
3. **Click "New" → "Web Service"**
4. **Connect your GitHub repo**
5. **Configure**:
   - **Name**: `work-tracker-api`
   - **Root Directory**: `backend`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app:app --host 0.0.0.0 --port $PORT`
   
6. **Add Environment Variable**:
   - Key: `PYTHONPATH`
   - Value: `/opt/render/project/src`

7. **Click "Create Web Service"**
8. **Wait** for deployment (takes 5-10 minutes)
9. **Copy your API URL** (will look like: `https://work-tracker-api.onrender.com`)

---

### **Step 3: Deploy Frontend to Vercel**

1. **Go to Vercel**: https://vercel.com
2. **Sign up** (use GitHub account)
3. **Click "Add New Project"**
4. **Import** your GitHub repo
5. **Configure**:
   - **Root Directory**: `frontend`
   - **Framework Preset**: `Vite`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`

6. **Add Environment Variable**:
   - Key: `VITE_API_BASE`
   - Value: `https://work-tracker-api.onrender.com` (your backend URL from Step 2)

7. **Click "Deploy"**
8. **Wait** for deployment (takes 2-3 minutes)
9. **You're done!** 🎉 Your app is live!

---

## 🎉 **You're Done!**

Your app will be live at: `https://work-tracker-api.vercel.app`

Share this URL with your team and they can start using it!

---

## 📊 **Alternative Hosting Options**

### **Option 2: Both on Railway** (Also Free)
- Frontend + Backend on same service
- Sign up at: https://railway.app
- Push repo, auto-deploys both services
- Slightly more setup but very powerful

### **Option 3: Vercel + Heroku** (Free + Paid)
- Frontend on Vercel
- Backend on Heroku ($7/month after free tier)
- Full featured but costs money

---

## 🔧 **After Deployment**

### **Update Database (Important!)**
The database will be created automatically, but you can add sample data:

```bash
# SSH into your Render service (if needed)
# Or just use the app - the database will auto-create
```

### **Domain Setup (Optional)**
- **Frontend**: Add custom domain in Vercel settings
- **Backend**: Add custom domain in Render settings

---

## 🆘 **Troubleshooting**

### **Frontend can't connect to backend:**
- Check `VITE_API_BASE` is set correctly
- Make sure backend URL doesn't have trailing slash
- Check Render logs if backend is down

### **Backend not starting:**
- Check Render logs for errors
- Make sure `requirements.txt` has all dependencies
- Verify environment variables are set

### **Database issues:**
- ✅ **FIXED!** Now using PostgreSQL with persistent storage
- See `DEPLOY_WITH_PERSISTENT_DB.md` for setup instructions

---

## 💰 **Cost Summary**

### **Current Setup: $0/month**
- ✅ Frontend: Vercel (free forever)
- ✅ Backend: Render (free tier, sleeps after inactivity)
- ✅ Database: SQLite (included, but ephemeral)

### **For Production Use:**
- Consider PostgreSQL database: **$0-20/month**
- Keeps data permanently
- Better for multiple users

---

## 🎯 **Next Steps**

1. ✅ Deploy both services
2. ✅ Test the app
3. ✅ Share URL with team
4. ✅ Monitor usage
5. 💡 Consider upgrading to PostgreSQL later

---

## 📞 **Need Help?**

If you run into issues during deployment, the logs will show what went wrong. Most common issues:
- Environment variables not set
- Wrong build commands
- Database connection issues

Just check the deployment logs in Vercel/Render dashboards!

Good luck! 🚀
