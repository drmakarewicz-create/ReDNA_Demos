# Contributing to ReDNA

Welcome! This guide will help you get started contributing to the ReDNA project.

---

## 📚 Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Code Structure](#code-structure)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [Git Workflow](#git-workflow)
- [Code Style](#code-style)
- [Pull Request Process](#pull-request-process)
- [Common Tasks](#common-tasks)

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.9+** (for backend/core)
- **Node.js 18+** & npm (for web frontend)
- **Git** with hooks support
- **rsync** (for backups, optional)

### Quick Start

```bash
# Clone the repository
git clone <repository-url>
cd ReDNA_Demos

# Set up git hooks
git config core.hooksPath .githooks

# Install Python dependencies (if you have requirements.txt)
# pip install -r requirements.txt

# Install web dependencies
cd web
npm install
cd ..

# Start all services
bash scripts/start_all_services.sh
```

---

## 🛠️ Development Setup

### 1. Core API (Python)

```bash
# Start Core API (port 8015)
PYTHONPATH=.:ReDNACoreDemo python3 ReDNACoreDemo/core/api.py
```

**Health check**: http://localhost:8015/health

### 2. React Frontend

```bash
cd web
npm run dev
# Runs on http://localhost:3000
```

**TypeScript check**: `npm run typecheck`

### 3. DevX Environment

```bash
# Start DevX backend (8100) + frontend (3100)
bash scripts/start_devx.sh

# Stop DevX
bash scripts/stop_devx.sh
```

---

## 📁 Code Structure

```
ReDNA_Demos/
├── ReDNACoreDemo/
│   ├── core/              # Core Python backend
│   │   ├── api.py         # Main API server
│   │   ├── ontology/      # Ontology V2 system (105K+ containers)
│   │   ├── policy/        # Policy evaluation engine
│   │   └── ...
│   ├── devx/              # Developer experience tools
│   │   ├── backend/       # DevX API (port 8100)
│   │   └── frontend/      # DevX UI (port 3100)
│   ├── tests/             # Python tests
│   └── docs/              # Architecture docs
├── web/                   # React/Next.js frontend
│   ├── src/
│   │   ├── app/           # Next.js app routes
│   │   ├── components/    # React components
│   │   └── lib/           # Utilities & API client
│   └── package.json
├── scripts/
│   ├── autonomous/        # Health check, self-verify
│   ├── backups/           # Backup & retention scripts
│   └── ...
├── docs/ops/              # Operational documentation
└── .githooks/             # Git pre-commit hooks
```

---

## 🔄 Development Workflow

### Typical Development Flow

1. **Check health**: `bash scripts/autonomous/daily_health_check.sh`
2. **Create feature branch**: `git checkout -b feature/my-feature`
3. **Make changes** to code
4. **Run tests**: See [Testing](#testing) section
5. **Type check** (for web): `cd web && npm run typecheck`
6. **Commit** with descriptive message
7. **Push** and create PR

### Running All Services

```bash
# Start everything
bash scripts/start_all_services.sh

# Check status
curl http://localhost:8015/health  # Core API
curl http://localhost:8100/health  # DevX Backend
curl http://localhost:3000         # React
```

---

## 🧪 Testing

### Python Tests

```bash
# Run all tests
PYTHONPATH=.:ReDNACoreDemo python3 -m pytest

# Run specific test file
PYTHONPATH=.:ReDNACoreDemo python3 -m pytest ReDNACoreDemo/tests/test_policy.py

# Run with verbose output
PYTHONPATH=.:ReDNACoreDemo python3 -m pytest -v

# Run with coverage
PYTHONPATH=.:ReDNACoreDemo python3 -m pytest --cov=ReDNACoreDemo
```

### TypeScript Type Checking

```bash
cd web
npm run typecheck
```

### E2E Tests (if configured)

```bash
cd web
npm run test:e2e
```

---

## 🌿 Git Workflow

### Branching Strategy

- `main` - Production-ready code
- `feature/*` - New features
- `fix/*` - Bug fixes
- `docs/*` - Documentation updates

### Commit Message Format

Use conventional commits:

```
feat: Add new ontology API endpoint
fix: Resolve TypeScript path resolution
docs: Update CONTRIBUTING guide
refactor: Simplify backup retention logic
test: Add tests for policy engine
```

### Git Hooks

Pre-commit hook prevents large files (>10MB) from being committed.

**Bypass hook** (use sparingly):
```bash
SKIP_HOOKS=1 git commit -m "message"
```

---

## 🎨 Code Style

### Python

- Follow PEP 8 style guide
- Use type hints where appropriate
- Maximum line length: 100 characters
- Use docstrings for public functions

**Example**:
```python
def compute_insights(user_id: str, time_range: int = 7) -> dict:
    """
    Compute user insights for the specified time range.

    Args:
        user_id: User identifier
        time_range: Number of days to analyze (default: 7)

    Returns:
        Dictionary containing computed insights
    """
    ...
```

### TypeScript/React

- Use TypeScript strict mode
- Prefer functional components with hooks
- Use interfaces for props
- Maximum line length: 100 characters

**Example**:
```typescript
interface ButtonProps {
  label: string;
  onClick: () => void;
  disabled?: boolean;
}

export function Button({ label, onClick, disabled = false }: ButtonProps) {
  return (
    <button onClick={onClick} disabled={disabled}>
      {label}
    </button>
  );
}
```

### File Naming

- Python: `snake_case.py`
- TypeScript: `kebab-case.tsx` or `PascalCase.tsx` for components
- Tests: `test_*.py` or `*.test.ts`

---

## 📝 Pull Request Process

### Before Submitting

1. ✅ All tests pass
2. ✅ Type checking passes (for web)
3. ✅ Code follows style guidelines
4. ✅ Commits are meaningful and well-formatted
5. ✅ Documentation updated (if needed)

### PR Template

```markdown
## Description
Brief description of what this PR does.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
Describe how you tested this change.

## Checklist
- [ ] Tests pass
- [ ] Type checking passes
- [ ] Code reviewed by self
- [ ] Documentation updated
```

### Review Process

1. Create PR with clear title and description
2. Request review from maintainers
3. Address feedback
4. Ensure CI checks pass
5. Squash and merge when approved

---

## 🔧 Common Tasks

### Adding a New API Endpoint

1. Add route in `ReDNACoreDemo/core/api.py`
2. Implement handler function
3. Add tests in `ReDNACoreDemo/tests/`
4. Update API documentation

### Adding a New React Component

1. Create component in `web/src/components/`
2. Add TypeScript types
3. Import and use in parent component
4. Test in browser

### Running Database Migrations

```bash
# (If you have migrations set up)
python3 scripts/run_migrations.py
```

### Creating a Backup

```bash
# Create backup (mirrors to iCloud automatically)
bash scripts/backups/create_backup.sh

# View retention status
bash scripts/backups/retention_cleanup.sh

# Delete old backups
bash scripts/backups/retention_cleanup.sh --apply
```

### Running Health Checks

```bash
# Daily health check
bash scripts/autonomous/daily_health_check.sh

# View report
cat docs/ops/DAILY_HEALTH_REPORT.md

# Self-verification
bash scripts/autonomous/self_verify.sh
```

---

## 🐛 Debugging

### Common Issues

**Issue**: TypeScript errors about missing `@/` imports

**Solution**: Ensure `paths` is configured in `tsconfig.json`:
```json
{
  "compilerOptions": {
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```

**Issue**: Python import errors

**Solution**: Always set `PYTHONPATH`:
```bash
PYTHONPATH=.:ReDNACoreDemo python3 your_script.py
```

**Issue**: Port already in use

**Solution**: Find and kill the process:
```bash
lsof -ti:8015 | xargs kill -9
```

**Issue**: Pre-commit hook fails

**Solution**: Bypass temporarily:
```bash
SKIP_HOOKS=1 git commit -m "message"
```

---

## 📚 Resources

### Documentation

- [Session Complete Report](SESSION_COMPLETE_2025_10_11.md)
- [iCloud Backup Setup](docs/ops/ICLOUD_BACKUP_SETUP.md)
- [Backup Retention Policy](docs/ops/BACKUP_RETENTION_POLICY.md)
- [DevX Quick Start](DEVX_QUICK_START.md)
- [Ontology Overview](ONTOLOGY_V5_COMPLETE_SUMMARY.md)

### Architecture Docs

- [ReDNA Core Docs](ReDNACoreDemo/docs/)
- [Ontology V5 Index](ONTOLOGY_V5_INDEX.md)
- [Phase Documentation](ReDNACoreDemo/docs/)

---

## 💬 Getting Help

- Check existing documentation first
- Search closed issues/PRs for similar problems
- Ask in discussions (if enabled)
- Reach out to maintainers

---

## 🎯 Areas Looking for Contributors

- **Testing**: Expand test coverage
- **Documentation**: Improve guides and examples
- **UI/UX**: Polish frontend components
- **Performance**: Optimize API endpoints
- **DevOps**: Improve deployment automation

---

## 📜 License

[Specify license here]

---

## 🙏 Thank You!

Thank you for contributing to ReDNA! Every contribution, no matter how small, makes a difference.

**Happy coding!** 🚀

---

*Last Updated: 2025-10-11*
*Maintained by: ReDNA Team*
