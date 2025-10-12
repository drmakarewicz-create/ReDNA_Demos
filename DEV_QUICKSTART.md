# ReDNA Developer Quick Start

**Get up and running in 5 minutes!** ⚡

---

## ⚙️ Prerequisites

```bash
# Check your versions
python3 --version  # Need 3.9+
node --version     # Need 18+
npm --version
git --version
```

---

## 🚀 One-Command Setup

```bash
# 1. Set up git hooks
git config core.hooksPath .githooks

# 2. Install web dependencies
cd web && npm install && cd ..

# 3. Done! Start developing
```

---

## 💻 Development Commands

### Start All Services

```bash
# Start everything at once
bash scripts/start_all_services.sh

# Or start individually:

# Core API (port 8015)
PYTHONPATH=.:ReDNACoreDemo python3 ReDNACoreDemo/core/api.py

# React Frontend (port 3000)
cd web && npm run dev

# DevX Tools (ports 8100, 3100)
bash scripts/start_devx.sh
```

### Health Checks

```bash
# Quick verification
bash scripts/autonomous/self_verify.sh

# Full health report
bash scripts/autonomous/daily_health_check.sh
cat docs/ops/DAILY_HEALTH_REPORT.md
```

### Testing

```bash
# Python tests
PYTHONPATH=.:ReDNACoreDemo python3 -m pytest

# TypeScript check
cd web && npm run typecheck
```

---

## 📍 Service URLs

Once running, access services at:

- **Core API**: http://localhost:8015
  - Health: http://localhost:8015/health
- **React Frontend**: http://localhost:3000
- **DevX Backend**: http://localhost:8100
- **DevX Frontend**: http://localhost:3100

---

## 🔧 Common Tasks

### Create a Backup

```bash
bash scripts/backups/create_backup.sh
# Auto-mirrors to iCloud!
```

### Run Type Checking

```bash
cd web
npm run typecheck  # Should show 0 errors!
```

### Check Git Status

```bash
git status
bash scripts/git_sanity/scan_status.py  # Detailed analysis
```

### Kill Stuck Process

```bash
# Find process on port
lsof -ti:8015

# Kill it
lsof -ti:8015 | xargs kill -9
```

---

## 🐛 Troubleshooting

### TypeScript Import Errors

**Problem**: Can't resolve `@/components/...`

**Fix**: Check `web/tsconfig.json` has paths config:
```json
{
  "compilerOptions": {
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```

### Python Import Errors

**Problem**: `ModuleNotFoundError`

**Fix**: Always set PYTHONPATH:
```bash
PYTHONPATH=.:ReDNACoreDemo python3 your_script.py
```

### Port Already in Use

**Problem**: `EADDRINUSE` error

**Fix**: Kill the process:
```bash
lsof -ti:3000 | xargs kill -9  # For React
lsof -ti:8015 | xargs kill -9  # For Core API
```

### Git Hook Failures

**Problem**: Pre-commit hook blocking

**Fix**: Bypass temporarily:
```bash
SKIP_HOOKS=1 git commit -m "message"
```

---

## 📁 Key Directories

```
ReDNA_Demos/
├── ReDNACoreDemo/core/     # Python backend
├── web/                    # React frontend
├── scripts/
│   ├── autonomous/         # Health checks
│   └── backups/            # Backup scripts
├── docs/ops/               # Operational docs
└── .githooks/              # Git hooks
```

---

## 📚 Next Steps

1. Read [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines
2. Check [SESSION_COMPLETE_2025_10_11.md](SESSION_COMPLETE_2025_10_11.md) for system overview
3. Explore [docs/ops/](docs/ops/) for operational guides
4. Review [ReDNACoreDemo/docs/](ReDNACoreDemo/docs/) for architecture

---

## 🎯 Your First Contribution

### Option 1: Fix a Bug

```bash
git checkout -b fix/my-bugfix
# Make changes
PYTHONPATH=.:ReDNACoreDemo python3 -m pytest
git add .
git commit -m "fix: Description of fix"
git push
```

### Option 2: Add a Feature

```bash
git checkout -b feature/my-feature
# Make changes
cd web && npm run typecheck
git add .
git commit -m "feat: Description of feature"
git push
```

### Option 3: Improve Docs

```bash
git checkout -b docs/improve-readme
# Edit markdown files
git add .
git commit -m "docs: Improve documentation"
git push
```

---

## ⚡ Pro Tips

- **Use health checks** before starting work: `bash scripts/autonomous/daily_health_check.sh`
- **Type check often** when working on frontend: `cd web && npm run typecheck`
- **Commit frequently** with clear messages
- **Test before pushing**: Run tests locally first
- **Read the docs**: Most answers are in existing documentation

---

## 🆘 Need Help?

- Check [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guides
- Review closed issues/PRs for similar problems
- Ask maintainers in discussions

---

**Happy hacking!** 🚀

*Last Updated: 2025-10-11*
