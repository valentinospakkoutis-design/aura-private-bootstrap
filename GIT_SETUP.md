# 🔄 AURA Auto-Commit Setup Guide

## ✅ Τι Έγινε

1. ✅ Git repository initialized
2. ✅ `.gitignore` created
3. ✅ Auto-commit scripts created (PowerShell & Bash)
4. ✅ GitHub Actions workflow created
5. ✅ Initial commit made

---

## 🚀 Πώς να Χρησιμοποιήσετε

### Επιλογή 1: Manual Auto-Commit (PowerShell)

```powershell
# Auto-commit με custom message
npm run commit "Your custom message"

# Auto-commit και push
npm run commit:push
```

Ή απευθείας:
```powershell
.\scripts\auto-commit.ps1
.\scripts\auto-commit.ps1 -Push
```

### Επιλογή 2: GitHub Actions (Αυτόματο)

Το GitHub Actions workflow θα τρέχει:
- Κάθε μέρα στις 2:00 AM UTC
- Όταν κάνετε manual push
- Όταν κάνετε manual trigger

**Σημείωση**: Χρειάζεται να έχετε ήδη συνδέσει το repository με GitHub.

---

## 📋 GitHub Setup (Πρώτη Φορά)

### 1. Δημιουργήστε GitHub Repository

1. Πηγαίνετε στο https://github.com/new
2. Repository name: `aura-private-bootstrap` (ή ό,τι θέλετε)
3. **ΠΡΟΣΟΧΗ**: Επιλέξτε **Private** (γιατί το package.json έχει `"private": true`)
4. **ΜΗΝ** επιλέξτε "Initialize with README"
5. Κάντε click "Create repository"

### 2. Συνδέστε το Local Repository

```powershell
# Προσθέστε το remote (αντικαταστήστε <username> και <repo-name>)
git remote add origin https://github.com/<username>/<repo-name>.git

# Ή με SSH (αν έχετε SSH keys setup)
git remote add origin git@github.com:<username>/<repo-name>.git

# Ελέγξτε
git remote -v
```

### 3. Push για Πρώτη Φορά

```powershell
# Δημιουργήστε main branch
git branch -M main

# Push
git push -u origin main
```

---

## 🔄 Auto-Commit Scripts

### PowerShell Script (`scripts/auto-commit.ps1`)

**Χρήση:**
```powershell
.\scripts\auto-commit.ps1
.\scripts\auto-commit.ps1 -Message "Custom message"
.\scripts\auto-commit.ps1 -Push
```

**Features:**
- ✅ Auto-detect changes
- ✅ Auto-stage all files
- ✅ Timestamp in commit message
- ✅ Optional push to GitHub

### Bash Script (`scripts/auto-commit.sh`)

**Χρήση:**
```bash
chmod +x scripts/auto-commit.sh
./scripts/auto-commit.sh
./scripts/auto-commit.sh "Custom message" true
```

---

## ⚙️ GitHub Actions Workflow

Το workflow (`.github/workflows/auto-commit.yml`) θα:
- ✅ Τρέχει κάθε μέρα στις 2:00 AM UTC
- ✅ Ελέγχει για changes
- ✅ Κάνει auto-commit και push

**Σημείωση**: Χρειάζεται να έχετε push access στο repository.

---

## 📝 .gitignore

Το `.gitignore` περιλαμβάνει:
- `node_modules/`
- `backend/venv/`
- `.env` files
- Build outputs
- IDE files
- OS files

---

## 🎯 Quick Start

```powershell
# 1. Setup GitHub (μόνο πρώτη φορά)
git remote add origin https://github.com/<username>/<repo-name>.git
git push -u origin main

# 2. Auto-commit (κάθε φορά που θέλετε)
npm run commit:push

# 3. Done! ✅
```

---

## 💡 Tips

1. **Κάντε commit συχνά**: Το auto-commit script είναι γρήγορο!
2. **Custom messages**: Χρησιμοποιήστε `npm run commit "Your message"`
3. **GitHub Actions**: Αφήστε το να τρέχει αυτόματα κάθε μέρα
4. **Private repo**: Το repository είναι private (ασφαλές)

---

## ❓ Troubleshooting

### "Remote not found"
```powershell
git remote add origin <your-github-repo-url>
```

### "Permission denied"
- Ελέγξτε GitHub credentials
- Χρησιμοποιήστε Personal Access Token αν χρειάζεται

### "Nothing to commit"
- Αυτό είναι καλό! Δεν υπάρχουν changes.

---

**Made with 💎 in Cyprus**

