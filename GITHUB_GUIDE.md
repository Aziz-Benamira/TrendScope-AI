# 🐙 GitHub Submission Guide

## Quick Commands to Update Your Repository

### 1. Initialize Git (if not already done)

```powershell
cd C:\Users\benam\Downloads\TrendScope-AI

# Check if git is initialized
git status

# If not, initialize
git init
git branch -M main
```

### 2. Add Your Remote Repository

```powershell
# Replace with your actual GitHub repository URL
git remote add origin https://github.com/yourusername/TrendScope-AI.git

# Or if already exists, update it
git remote set-url origin https://github.com/yourusername/TrendScope-AI.git
```

### 3. Stage All Files

```powershell
# Add all files (respects .gitignore)
git add .

# Check what will be committed
git status
```

### 4. Commit Your Changes

```powershell
git commit -m "Complete TrendScope-AI project with RAG, streaming, and dashboard

Features:
- Real-time streaming with Kafka and Spark
- RAG-powered chat with Mistral/Ollama
- ChromaDB vector database with 29K+ reviews
- React dashboard with live charts
- TrendScore algorithm for movie ranking
- TMDB and Reddit data integration
- Docker Compose deployment
- Comprehensive documentation and LaTeX report"
```

### 5. Push to GitHub

```powershell
# First time push
git push -u origin main

# Or if already exists
git push origin main
```

---

## 📁 Files That Will Be Uploaded

✅ **Included (as per .gitignore):**
- All source code (.py, .jsx, .js)
- Configuration files (docker-compose.yml, requirements.txt)
- Documentation (.md files)
- LaTeX report (PROJECT_REPORT.tex)
- Setup scripts (.ps1, .sh)
- Dockerfiles

❌ **Excluded (as per .gitignore):**
- node_modules/ (too large)
- __pycache__/ (generated)
- tmdb_dataset_files/ (large datasets)
- .venv/ (virtual environment)
- *.pyc (bytecode)
- Logs and temp files

---

## 🌟 Create a GitHub Repository

### Option A: Via GitHub Website

1. Go to https://github.com/new
2. Repository name: `TrendScope-AI`
3. Description: "Real-Time Movie Trend Analysis with RAG-Powered Insights - Kafka, Spark, ChromaDB, Ollama/Mistral"
4. Choose Public or Private
5. **Don't** initialize with README (you already have one)
6. Click "Create repository"
7. Copy the repository URL
8. Use the commands above to push

### Option B: Via GitHub CLI

```powershell
# Install GitHub CLI first: https://cli.github.com/

gh repo create TrendScope-AI --public --description "Real-Time Movie Trend Analysis with RAG-Powered Insights" --source=. --remote=origin --push
```

---

## 📝 Update README for GitHub

Your README.md should have these sections (already present):
- ✅ Project title and description
- ✅ Architecture diagram
- ✅ Features list
- ✅ Installation instructions
- ✅ Usage guide
- ✅ Tech stack
- ✅ Screenshots/demos (optional)

---

## 🔒 Important: API Keys

**DO NOT** commit actual API keys! Your documentation should say:

```markdown
## API Keys Required

Create a `.env` file (not tracked in git) with:

```bash
TMDB_API_KEY=your_key_here
REDDIT_CLIENT_ID=your_id_here
REDDIT_CLIENT_SECRET=your_secret_here
```

Instructions to obtain keys:
- TMDB: https://www.themoviedb.org/settings/api
- Reddit: https://www.reddit.com/prefs/apps
```

---

## 📊 Recommended Repository Structure

```
TrendScope-AI/
├── .github/
│   └── workflows/           # CI/CD (optional)
├── backend/                 # FastAPI backend
├── web-dashboard/          # React frontend
├── producers/              # Kafka producers
├── processors/             # Spark streaming
├── monitoring/             # Prometheus + Grafana
├── docs/                   # Documentation
├── tests/                  # Unit tests
├── docker-compose.yml      # Docker orchestration
├── README.md              # Main documentation
├── GETTING_STARTED.md     # Setup guide
├── SUBMISSION_GUIDE.md    # This guide
├── PROJECT_REPORT.tex     # Academic report
├── .gitignore            # Git exclusions
└── LICENSE               # License file
```

---

## 🎓 For Professor Review

Include these in your GitHub repository:

1. **README.md** - Comprehensive overview
2. **GETTING_STARTED.md** - Setup instructions
3. **SUBMISSION_GUIDE.md** - Submission checklist
4. **PROJECT_REPORT.tex** - Academic report (LaTeX)
5. **docs/** folder - Additional documentation
6. **All source code** - Well-commented
7. **docker-compose.yml** - One-command deployment
8. **requirements.txt** - Python dependencies

---

## ✅ Pre-Push Checklist

Before pushing to GitHub:

- [ ] All sensitive data removed (API keys, passwords)
- [ ] .gitignore properly configured
- [ ] README.md is clear and comprehensive
- [ ] Code is well-commented
- [ ] Docker setup tested and working
- [ ] Documentation is accurate
- [ ] License file added (if required)
- [ ] Requirements files are up-to-date

---

## 🚀 Verify Your Repository

After pushing, check:

```powershell
# View your repository
start https://github.com/yourusername/TrendScope-AI
```

Verify on GitHub:
- ✅ All files uploaded correctly
- ✅ README displays properly
- ✅ No sensitive data exposed
- ✅ .gitignore working (node_modules not uploaded)
- ✅ Repository is accessible to professor

---

## 📨 Share with Professor

Provide:
1. **GitHub URL**: `https://github.com/yourusername/TrendScope-AI`
2. **ZIP File**: Created with `.\create_submission_package.ps1`
3. **PDF Report**: Compile PROJECT_REPORT.tex to PDF

---

## 🛠️ Troubleshooting

### Issue: "Repository not found"
```powershell
# Check remote URL
git remote -v

# Update if needed
git remote set-url origin https://github.com/yourusername/TrendScope-AI.git
```

### Issue: "Permission denied"
```powershell
# Use GitHub Personal Access Token
# Settings → Developer settings → Personal access tokens
# Use token as password when pushing
```

### Issue: "File too large"
```powershell
# Check for large files
git ls-files -z | xargs -0 du -h | sort -hr | head -20

# Add to .gitignore and remove from tracking
git rm --cached large-file.tsv
git commit -m "Remove large file"
```

### Issue: "Branch 'main' doesn't exist"
```powershell
# Create main branch
git branch -M main
git push -u origin main
```

---

## 📞 Need Help?

- GitHub Docs: https://docs.github.com/
- Git Basics: https://git-scm.com/book/en/v2
- .gitignore Templates: https://github.com/github/gitignore

**Good luck with your submission! 🎓**
