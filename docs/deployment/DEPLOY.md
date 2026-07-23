# 🚀 Deploy In Office - Step by Step

## ✅ What's Ready

Your app is now ready to deploy! All configuration files are created:
- ✅ `render.yaml` - for backend deployment on Render
- ✅ `vercel.json` - for frontend deployment on Vercel
- ✅ `backend/Dockerfile.production` - for containerized backend
- ✅ Updated requirements and dependencies

## 📝 Step-by-Step Deployment Instructions

### **Step 1: Push to GitHub**

1. Create a new repository on GitHub:
   - Go to: https://github.com/new
   - Name: `in-office`
   - Description: "Team work location tracking app"
   - Set to **Public**
   - ✅ Check "Initialize with README"
   - Click "Create repository"

2. Push your code to GitHub:

```bash
cd /path/to/in-office

# Add the GitHub remote (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/in-office.git

# Push to GitHub
git branch -M main
git push -u origin main
```

📝 **Note**: Replace `YOUR_USERNAME` with your actual GitHub username!

---

### **Step 2: Deploy Backend to Render**

1. **Go to Render**: https://render.com
2. **Sign up** (use "Sign up with GitHub")
3. **Click "New"** → **"Blueprint"**
4. **Connect repository**: Search for `in-office`
5. **Click the repository** and "Connect"
6. **Render will detect** `render.yaml` automatically
7. **Click "Apply"** and wait for deployment (~10 minutes)
8. **Copy the backend URL** (looks like: `https://work-tracker-api.onrender.com`)

💾 **Save this URL** - you'll need it for the frontend!

---

### **Step 3: Deploy Frontend to Vercel**

1. **Go to Vercel**: https://vercel.com
2. **Sign up** (use "Sign up with GitHub")
3. **Click "Add New Project"**
4. **Import Git Repository**: Search for `in-office`
5. **Click "Import"**
6. **Configure Project**:
   - **Root Directory**: Leave as `/` (root)
   - **Framework Preset**: Should auto-detect as "Vite"
   - **Build Command**: Should be `npm install && npm run build`
   - **Output Directory**: Should be `frontend/dist`
   
7. **Add Environment Variable**:
   - Click "Environment Variables"
   - Add:
     - **Name**: `VITE_API_BASE`
     - **Value**: Your backend URL from Step 2 (e.g., `https://work-tracker-api.onrender.com`)
   - Click "Save"

8. **Click "Deploy"** and wait (~5 minutes)

9. **🎉 Done!** Your app is live at the Vercel URL

---

## 🎊 **Your App is Now Live!**

### **Share with Your Team:**
- Send them the Vercel URL
- They can start tracking work locations immediately
- No accounts, no passwords - completely open

### **Test It:**
1. Visit your Vercel URL
2. Enter your name
3. Fill in your week
4. Click "Save my week"
5. Switch to "Who's where" to see the dashboard

---

## 🛠️ **Troubleshooting**

### Backend not deploying on Render?
- Check the build logs in Render dashboard
- Make sure Python 3.11 is selected
- Verify `render.yaml` is in the repo root

### Frontend can't connect to backend?
- Check the environment variable `VITE_API_BASE` is set correctly
- Make sure the backend URL has no trailing slash
- Verify backend is running (check Render logs)

### Database issues?
- SQLite on Render uses ephemeral storage (data may reset)
- For permanent storage, upgrade to PostgreSQL later

---

## 💰 **Costs**

### **Current Setup: $0/month**
- ✅ Vercel: Free forever for personal use
- ✅ Render: Free tier (backend may sleep after 15 min inactivity)
- ✅ Database: SQLite (included, ephemeral)

### **If Backend Sleeps:**
- First request after sleep takes ~30 seconds (waking up)
- Subsequent requests are instant
- To keep it always on: Upgrade Render plan ($7/month)

---

## 🔄 **Updating Your App**

After making changes:

```bash
# Make your changes
cd /path/to/in-office

# Commit changes
git add .
git commit -m "Your update message"

# Push to GitHub
git push

# Both Vercel and Render will auto-deploy
```

---

## 📱 **Next Steps**

1. ✅ Deploy and test
2. ✅ Share URL with team
3. 💡 Consider custom domain
4. 💡 Set up monitoring
5. 💡 Plan PostgreSQL upgrade for permanent data

Good luck! 🚀
