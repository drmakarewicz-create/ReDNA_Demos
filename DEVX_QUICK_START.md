# DevX Quick Start Guide

**Status**: ✅ Installation Complete
**Validation**: ✅ All checks passed
**Ready**: Yes

---

## Start DevX

```bash
cd /Users/davidmakarewicz/Documents/ReDNA_Demos

# Start backend + frontend
./scripts/start_devx.sh
```

**Expected output**:
```
🚀 Starting DevX...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📡 Starting DevX backend...
   ✅ Backend started (PID: 12345)
   ✅ Backend health check passed
🎨 Starting DevX frontend...
   📦 Installing frontend dependencies... (first time only)
   ✅ Frontend started (PID: 12346)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ DevX is running!

   Backend:  http://127.0.0.1:8100
   Frontend: http://127.0.0.1:3100
   Logs:     ReDNACoreDemo/devx/logs

To stop DevX: ./scripts/stop_devx.sh
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**First-time startup**: Frontend dependencies will be installed (~2-3 minutes).

---

## Access DevX

### Frontend UI
Open in your browser:
```
http://127.0.0.1:3100
```

### Backend API
API documentation:
```
http://127.0.0.1:8100/docs
```

Health check:
```bash
curl http://127.0.0.1:8100/health
```

---

## Using Trait Workshop

### 1. Browse Traits

**Left Panel** - Trait Browser:
- Search by name or path
- Filter by namespace (SkillDNA, BehDNA, etc.)
- Click a trait to view/edit

**Visual Indicators**:
- 🟢 Green dot = Has value model
- Badge shows namespace
- Status badge (production/beta/prototype)

### 2. View Metadata

**Right Panel** - Definition Editor:
- Click "Metadata" tab
- View namespace, version, status, ID
- Read-only (metadata changes require API)

### 3. Edit Value Model

**Steps**:
1. Click "Value Model" tab
2. Select canonical type:
   - **Numeric**: Range [min, max] + unit (e.g., 0-100 skill_level)
   - **Categorical**: List of categories (e.g., ["low", "medium", "high"])
   - **Ordinal**: Ordered categories with rankings
   - **Boolean**: True/false
   - **Text**: Free-form text
   - **Composite**: Complex nested structures

3. Fill in required fields (range, unit, categories, etc.)
4. Click "Save Value Model"
5. See green success message

**Example - Numeric Type**:
```
Canonical Type: numeric
Min: 0
Max: 100
Unit: skill_level
```

**Example - Categorical Type**:
```
Canonical Type: categorical
Categories: ["beginner", "intermediate", "advanced", "expert"]
```

### 4. View Semantics (Read-Only)

**Steps**:
1. Click "Semantics" tab
2. View inclusion/exclusion criteria (if defined)
3. Full editor coming in v1.1

---

## API Examples

### List Traits

```bash
curl http://127.0.0.1:8100/devx/api/traits/list
```

**With filters**:
```bash
# Filter by namespace
curl "http://127.0.0.1:8100/devx/api/traits/list?namespace=SkillDNA"

# Filter by status
curl "http://127.0.0.1:8100/devx/api/traits/list?status=production"

# Filter by value model presence
curl "http://127.0.0.1:8100/devx/api/traits/list?has_value_model=true"
```

### Get Trait Definition

```bash
curl "http://127.0.0.1:8100/devx/api/traits/definition?path=SkillDNA.PresentationDNA"
```

### Save Value Model (Direct)

```bash
curl -X POST http://127.0.0.1:8100/devx/api/traits/assert \
  -H "Content-Type: application/json" \
  -d '{
    "trait_path": "SkillDNA.PresentationDNA",
    "value_model": {
      "canonical_type": "numeric",
      "range": [0, 100],
      "unit": "skill_level"
    }
  }'
```

### Create Change Request

```bash
curl -X POST http://127.0.0.1:8100/devx/api/traits/propose-change \
  -H "Content-Type: application/json" \
  -d '{
    "trait_path": "SkillDNA.PresentationDNA",
    "change_type": "add_value_model",
    "value_model": {
      "canonical_type": "numeric",
      "range": [0, 100],
      "unit": "skill_level"
    },
    "reason": "Adding value model for skill assessment",
    "author": "dev_user"
  }'
```

**Response**:
```json
{
  "cr_id": "cr_abc12345",
  "trait_path": "SkillDNA.PresentationDNA",
  "status": "validated",
  "risk_level": "low",
  "validation_errors": []
}
```

### Apply Change Request

```bash
curl -X POST http://127.0.0.1:8100/devx/api/traits/apply-change \
  -H "Content-Type: application/json" \
  -d '{"cr_id": "cr_abc12345"}'
```

---

## Stop DevX

```bash
./scripts/stop_devx.sh
```

**Expected output**:
```
🛑 Stopping DevX...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Stopping backend (PID: 12345)...
   ✅ Backend stopped
   Stopping frontend (PID: 12346)...
   ✅ Frontend stopped
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ DevX stopped
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Troubleshooting

### Backend won't start

**Check if port is available**:
```bash
lsof -ti:8100
```

**If port is in use**:
- DevX will auto-increment to 8101
- Or manually kill the process: `lsof -ti:8100 | xargs kill`

**Check logs**:
```bash
tail -f ReDNACoreDemo/devx/logs/backend.log
```

### Frontend won't start

**Check if port is available**:
```bash
lsof -ti:3100
```

**If dependencies failed to install**:
```bash
cd ReDNACoreDemo/devx/frontend
rm -rf node_modules
npm install
```

**Check logs**:
```bash
tail -f ReDNACoreDemo/devx/logs/frontend.log
```

### Changes not appearing

**Hard refresh browser**:
- Mac: Cmd + Shift + R
- Windows/Linux: Ctrl + Shift + R

**Or restart DevX**:
```bash
./scripts/stop_devx.sh
./scripts/start_devx.sh
```

### Port conflict with Core/UCNRR

**This should never happen** - DevX has port safety built in.

If it does:
1. Stop DevX: `./scripts/stop_devx.sh`
2. Check DevX logs: `cat ReDNACoreDemo/devx/logs/devx_start.log`
3. Verify Core/UCNRR are healthy:
   ```bash
   curl http://127.0.0.1:8015/health  # Core
   curl http://127.0.0.1:8011/health  # UCNRR
   ```

---

## Validation

Run validation script to check installation:

```bash
./scripts/validate_devx.sh
```

**Expected output**: ✅ All checks pass

---

## Next Steps

### Try These Tasks

1. **Browse Traits**:
   - Filter by "SkillDNA" namespace
   - Click on a trait
   - View its metadata

2. **Edit a Value Model**:
   - Select a trait without a value model
   - Go to "Value Model" tab
   - Set type to "numeric"
   - Set range [0, 100]
   - Set unit "skill_level"
   - Save

3. **Use the API**:
   - List all traits: `curl http://127.0.0.1:8100/devx/api/traits/list`
   - Get a definition: `curl "http://127.0.0.1:8100/devx/api/traits/definition?path=SkillDNA.PresentationDNA"`

4. **Check API Docs**:
   - Open http://127.0.0.1:8100/docs
   - Try the interactive API explorer

### Read Documentation

- [DevX Overview](docs/DEVX_OVERVIEW.md) - Full system documentation
- [Port Safety](docs/DEVX_PORT_SAFETY.md) - How port isolation works
- [Completion Summary](DEVX_COMPLETION_SUMMARY.md) - Implementation details
- [DevX README](ReDNACoreDemo/devx/README.md) - Main README

---

## Support

**Logs**: `ReDNACoreDemo/devx/logs/`
- `backend.log` - Backend errors and info
- `frontend.log` - Frontend build/runtime logs
- `devx_start.log` - Port assignments

**Health Checks**:
```bash
# Backend
curl http://127.0.0.1:8100/health

# Frontend
curl http://127.0.0.1:3100
```

**Validate Installation**:
```bash
./scripts/validate_devx.sh
```

---

**Version**: 1.0.0
**Status**: Production Ready
**Last Updated**: 2025-10-08

🎯 **DevX is ready to use!**
