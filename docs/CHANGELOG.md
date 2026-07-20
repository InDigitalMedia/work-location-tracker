# 📝 Changes Made

## ✅ Recent Updates

### 1. **Removed Weekends**
- Changed from 7 days (Mon-Sun) to 5 days (Mon-Fri only)
- Backend now calculates week end as Friday instead of Sunday
- Users can now only fill in weekdays

### 2. **Update Logic**
> **Note:** this section originally described a delete-then-insert update strategy. That approach turned out to cause real data loss (see `docs/history/DATA_LOSS_ROOT_CAUSE_REPORT.md`) and was replaced — see the "Fixed - Data Loss Prevention" entry in the root [`CHANGELOG.md`](../CHANGELOG.md) for what's actually in place now.

The backend performs atomic per-day upserts instead of delete-then-insert:
- Each entry is written with `INSERT ... ON CONFLICT (user_key, date, time_period) DO UPDATE`
- Submitting a partial week only touches those days — other days are left untouched
- Same person, same date = updates the existing entry in place; no delete step involved
- User identity is normalized via `user_key` (`lower(trim(user_name))`) so name-casing differences can't create duplicate or orphaned entries

### 3. **Improved Dashboard Display**
- **Previous**: Showed each person as a separate card
- **Now**: Shows location badges with people listed inline
- Example display:
  ```
  Monday, January 15, 2024
    [Office] - John, Alice, Bob
    [WFH] - Charlie, David  
    [Client] - Emma (Client Name)
  ```

---

## 🎯 What This Means for Users

### For People Filling In:
- Only see Monday-Friday
- Weekend is automatically skipped
- Can update their week anytime (just re-submit)

### For Dashboard Viewers:
- See who's where listed by location
- Much easier to scan
- Compact display shows all people in one line per location

---

## 🚀 Deployment Status

Changes are being deployed to:
- **Backend**: Render (automatic)
- **Frontend**: Vercel (automatic)

Both will auto-deploy in ~2-3 minutes from the git push.

