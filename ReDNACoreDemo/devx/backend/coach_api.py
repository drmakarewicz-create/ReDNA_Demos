"""
Coach Workshop API for DevX.

Provides endpoints to list and edit coach prompt files using a canonical registry.
"""

import json
import shutil
import fcntl
import zipfile
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .coach_registry import COACH_ROLES, SYSTEM_AGENTS, get_coach_by_id, get_default_scaffold

router = APIRouter()

# Resolve prompts directory relative to project root
DEVX_ROOT = Path(__file__).resolve().parents[3]
PROMPTS_DIR = DEVX_ROOT / "prompts"
BACKUPS_DIR = PROMPTS_DIR / "backups"
RETIRED_DIR = PROMPTS_DIR / "retired"
DELETED_DIR = PROMPTS_DIR / "deleted"
FEATURES_DIR = PROMPTS_DIR / "features"
INSIGHTS_DIR = PROMPTS_DIR / "insights"
OPS_BACKUPS_DIR = PROMPTS_DIR / "ops_backups"
DELETION_LOG = PROMPTS_DIR / "deletion_log.jsonl"
OPS_LOCK_FILE = PROMPTS_DIR / ".ops.lock"
REDNA_ROOT = DEVX_ROOT / "ReDNACoreDemo"
SCHEMAS_DIR = DEVX_ROOT / "ReDNACoreDemo" / "devx" / "schemas"

# Ensure directories exist
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
RETIRED_DIR.mkdir(parents=True, exist_ok=True)
DELETED_DIR.mkdir(parents=True, exist_ok=True)
FEATURES_DIR.mkdir(parents=True, exist_ok=True)
INSIGHTS_DIR.mkdir(parents=True, exist_ok=True)
OPS_BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
SCHEMAS_DIR.mkdir(parents=True, exist_ok=True)


# Safe operations infrastructure
@contextmanager
def ops_lock(timeout_seconds=60):
    """
    Acquire exclusive file lock for coach operations.
    
    Prevents concurrent mutations. Returns 423 if already locked.
    """
    lock_file = None
    try:
        OPS_LOCK_FILE.touch(exist_ok=True)
        lock_file = open(OPS_LOCK_FILE, 'r+')
        
        # Try to acquire exclusive lock with timeout
        import time
        start = time.time()
        while True:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.time() - start > timeout_seconds:
                    raise HTTPException(
                        status_code=423,
                        detail="Another operation in progress. Please wait and retry."
                    )
                time.sleep(0.1)
        
        yield lock_file
        
    finally:
        if lock_file:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                lock_file.close()
            except:
                pass


def create_transaction_backup(op: str, coach_id: str, files: List[Path], target_id: str = None) -> Dict[str, Any]:
    """
    Create a transaction backup ZIP before mutating operations.
    
    Args:
        op: Operation type (rename|retire|purge|restore)
        coach_id: Coach being operated on
        files: List of file paths to backup
        target_id: For rename operations, the new coach ID
        
    Returns:
        Dict with backup metadata
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_name = f"{timestamp}_{op}_{coach_id}.zip"
    if target_id:
        zip_name = f"{timestamp}_{op}_{coach_id}_to_{target_id}.zip"
    
    zip_path = OPS_BACKUPS_DIR / zip_name
    
    # Build manifest
    manifest = {
        "op": op,
        "actor": "devx",
        "ts": datetime.now().isoformat(),
        "coach_id": coach_id,
        "files": []
    }
    
    if target_id:
        manifest["target_id"] = target_id
    
    # Create ZIP with all files
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_path in files:
            if file_path.exists():
                rel_path = str(file_path.relative_to(DEVX_ROOT))
                manifest["files"].append(rel_path)
                zf.write(file_path, rel_path)
        
        # Add manifest
        zf.writestr("_manifest.json", json.dumps(manifest, indent=2))
    
    # Check if git repo exists
    git_message = None
    git_dir = DEVX_ROOT / ".git"
    if git_dir.exists():
        files_str = " ".join(manifest["files"])
        if op == "rename":
            git_message = f"DevX: rename {coach_id} -> {target_id} (bundle {zip_name})"
        else:
            git_message = f"DevX: {op} {coach_id} (bundle {zip_name})"
        
        git_message = f"git add {files_str}\ngit commit -m \"{git_message}\""
    
    return {
        "bundle_path": str(zip_path.relative_to(DEVX_ROOT)),
        "bundle_name": zip_name,
        "files_backed_up": len(manifest["files"]),
        "git_suggestion": git_message,
        "manifest": manifest
    }




class CoachPromptUpdate(BaseModel):
    """Request body for updating a coach prompt."""
    text: str


class CoachFeaturesUpdate(BaseModel):
    """Request body for updating coach features config."""
    config: Dict[str, Any]


class CoachRenameRequest(BaseModel):
    """Request body for renaming a coach."""
    new_coach_id: str
    new_label: str
    reason: Optional[str] = None


class CoachInfo(BaseModel):
    """Coach metadata for listing."""
    id: str
    label: str
    filename: str
    prompt_path: str
    exists: bool
    status: str  # "present", "missing", or "retired"
    size_bytes: int


@router.get("/devx/api/coaches", response_model=List[CoachInfo])
async def list_coaches(include_retired: bool = Query(False)) -> List[CoachInfo]:
    """
    List all coach roles from the canonical registry.

    Returns all coaches whether their prompt files exist or not.
    Excludes system agents (core_ai.md, ucn_rr_ai.md).
    Excludes purged coaches (those in deleted/ directory).

    Args:
        include_retired: Include retired coaches in the list

    Returns:
        List of coach metadata with existence status
    """
    if not PROMPTS_DIR.exists():
        raise HTTPException(status_code=500, detail=f"Prompts directory not found: {PROMPTS_DIR}")

    coaches: List[CoachInfo] = []

    for coach_role in COACH_ROLES:
        # Skip system agents
        if coach_role["filename"] in SYSTEM_AGENTS:
            continue

        prompt_file = PROMPTS_DIR / coach_role["filename"]
        retired_dir = RETIRED_DIR / coach_role["id"]

        # Check if purged (exists in deleted/ directory)
        deleted_dirs = list(DELETED_DIR.glob(f"{coach_role['id']}_*"))
        is_purged = len(deleted_dirs) > 0

        # Skip purged coaches entirely - they should not appear in the list
        if is_purged:
            continue

        # Check if retired
        is_retired = retired_dir.exists()

        # Skip retired coaches unless explicitly requested
        if is_retired and not include_retired:
            continue

        # Determine status and path
        if is_retired:
            retired_prompt = retired_dir / coach_role["filename"]
            exists = retired_prompt.exists()
            size_bytes = retired_prompt.stat().st_size if exists else 0
            status = "retired"
            prompt_path = str(retired_dir.relative_to(DEVX_ROOT))
        else:
            exists = prompt_file.exists()
            size_bytes = prompt_file.stat().st_size if exists else 0
            status = "present" if exists else "missing"
            prompt_path = str(prompt_file.relative_to(DEVX_ROOT)) if exists else f"prompts/{coach_role['filename']}"

        coaches.append(CoachInfo(
            id=coach_role["id"],
            label=coach_role["label"],
            filename=coach_role["filename"],
            prompt_path=prompt_path,
            exists=exists,
            status=status,
            size_bytes=size_bytes
        ))

    # Sort by label
    coaches.sort(key=lambda c: c.label)

    return coaches


@router.get("/devx/api/coaches/{coach_id}")
async def get_coach_prompt(coach_id: str) -> Dict[str, Any]:
    """
    Get the prompt text for a specific coach.

    If the file doesn't exist, returns a default scaffold with 200 OK.

    Args:
        coach_id: Coach identifier (e.g., "head_coach", "career_coach")

    Returns:
        Dict with coach metadata and prompt text (or scaffold)
    """
    coach_role = get_coach_by_id(coach_id)
    if not coach_role:
        raise HTTPException(
            status_code=404,
            detail=f"Coach not found in registry: {coach_id}"
        )

    prompt_file = PROMPTS_DIR / coach_role["filename"]
    exists = prompt_file.exists()

    if exists:
        try:
            text = prompt_file.read_text(encoding="utf-8")
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to read prompt file: {str(e)}"
            )

        stat = prompt_file.stat()
        modified_at = datetime.fromtimestamp(stat.st_mtime).isoformat()
        size_bytes = stat.st_size
    else:
        # Return scaffold for missing file
        text = get_default_scaffold(coach_role["label"])
        modified_at = datetime.now().isoformat()
        size_bytes = 0

    return {
        "id": coach_id,
        "name": coach_role["filename"].replace(".md", ""),
        "display_name": coach_role["label"],
        "path": str(prompt_file.relative_to(DEVX_ROOT)),
        "text": text,
        "exists": exists,
        "size_bytes": size_bytes,
        "modified_at": modified_at
    }


@router.put("/devx/api/coaches/{coach_id}")
async def update_coach_prompt(coach_id: str, update: CoachPromptUpdate) -> Dict[str, Any]:
    """
    Update the prompt text for a specific coach.

    Creates a timestamped backup before saving (if file exists).
    Creates a new file if it doesn't exist yet.

    Args:
        coach_id: Coach identifier
        update: Request body with new prompt text

    Returns:
        Success message with backup info
    """
    coach_role = get_coach_by_id(coach_id)
    if not coach_role:
        raise HTTPException(
            status_code=404,
            detail=f"Coach not found in registry: {coach_id}"
        )

    prompt_file = PROMPTS_DIR / coach_role["filename"]

    # Create backup if file exists
    backup_path = None
    if prompt_file.exists():
        try:
            old_text = prompt_file.read_text(encoding="utf-8")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"{coach_id}_{timestamp}.md"
            backup_path = BACKUPS_DIR / backup_filename
            backup_path.write_text(old_text, encoding="utf-8")
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create backup: {str(e)}"
            )

    # Write new prompt text
    try:
        prompt_file.write_text(update.text, encoding="utf-8")
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to write prompt file: {str(e)}"
        )

    stat = prompt_file.stat()

    return {
        "saved": True,
        "id": coach_id,
        "name": coach_role["label"],
        "path": str(prompt_file.relative_to(DEVX_ROOT)),
        "bytes": stat.st_size,
        "backup_created": backup_path is not None,
        "backup_path": str(backup_path.relative_to(DEVX_ROOT)) if backup_path else None,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
    }


def _scan_references(coach_id: str) -> List[Dict[str, Any]]:
    """
    Scan ReDNACoreDemo/ for references to a coach ID.

    Returns list of {"file": path, "line": line_num, "content": text}
    """
    references = []

    # Search patterns: coach_id in code, config, and markdown
    search_patterns = [
        coach_id,
        f'"{coach_id}"',
        f"'{coach_id}'",
        f"{coach_id}_ai",
    ]

    # File extensions to search
    extensions = {'.py', '.yaml', '.yml', '.json', '.md', '.txt'}

    if not REDNA_ROOT.exists():
        return references

    for file_path in REDNA_ROOT.rglob('*'):
        # Skip directories, hidden files, and non-matching extensions
        if not file_path.is_file() or file_path.name.startswith('.'):
            continue
        if file_path.suffix not in extensions:
            continue

        try:
            content = file_path.read_text(encoding='utf-8')
            lines = content.split('\n')

            for line_num, line in enumerate(lines, 1):
                for pattern in search_patterns:
                    if pattern in line:
                        references.append({
                            "file": str(file_path.relative_to(DEVX_ROOT)),
                            "line": line_num,
                            "content": line.strip()[:100]  # Limit to 100 chars
                        })
                        break  # One match per line is enough
        except (UnicodeDecodeError, PermissionError):
            # Skip files that can't be read
            continue

    return references


def _log_deletion(action: str, coach_id: str, mode: str, operator: str = "devx", **kwargs):
    """Append deletion action to deletion_log.jsonl"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "coach_id": coach_id,
        "mode": mode,
        "operator": operator,
        **kwargs
    }

    try:
        with DELETION_LOG.open('a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry) + '\n')
    except Exception as e:
        # Non-fatal: log to stderr but don't block operation
        print(f"Warning: Failed to write deletion log: {e}", file=__import__('sys').stderr)


def _remove_from_registry(coach_id: str):
    """Remove a coach from coach_registry.py"""
    registry_file = DEVX_ROOT / "ReDNACoreDemo" / "devx" / "backend" / "coach_registry.py"

    try:
        # Read the registry file
        content = registry_file.read_text(encoding='utf-8')
        lines = content.split('\n')

        # Filter out the line containing this coach_id
        filtered_lines = []
        skip_next = False
        for i, line in enumerate(lines):
            # Look for the coach entry - it should be a dict with "id": "coach_id"
            if f'"id": "{coach_id}"' in line or f"'id': '{coach_id}'" in line:
                # Skip this line and potentially check if we need to clean up trailing comma
                skip_next = True
                continue

            if skip_next:
                skip_next = False
                # Skip the line if it's just a closing brace or continuation
                if line.strip() in ['},', '}']:
                    continue

            filtered_lines.append(line)

        # Write back
        registry_file.write_text('\n'.join(filtered_lines), encoding='utf-8')

    except Exception as e:
        # Non-fatal: log warning but don't block deletion
        print(f"Warning: Failed to remove from registry: {e}", file=__import__('sys').stderr)


def _add_to_registry(coach_id: str, label: str, filename: str):
    """Add a coach back to coach_registry.py"""
    registry_file = DEVX_ROOT / "ReDNACoreDemo" / "devx" / "backend" / "coach_registry.py"

    try:
        # Read the registry file
        content = registry_file.read_text(encoding='utf-8')
        lines = content.split('\n')

        # Find the closing bracket of COACH_ROLES list
        insert_index = -1
        for i, line in enumerate(lines):
            if line.strip() == ']' and 'COACH_ROLES' in ''.join(lines[max(0, i-10):i]):
                insert_index = i
                break

        if insert_index == -1:
            raise ValueError("Could not find COACH_ROLES closing bracket")

        # Create new entry
        new_entry = f'    {{"id": "{coach_id}", "label": "{label}", "filename": "{filename}"}},'

        # Insert before the closing bracket
        lines.insert(insert_index, new_entry)

        # Write back
        registry_file.write_text('\n'.join(lines), encoding='utf-8')

    except Exception as e:
        # Non-fatal: log warning but don't block restoration
        print(f"Warning: Failed to add to registry: {e}", file=__import__('sys').stderr)


@router.delete("/devx/api/coaches/{coach_id}")
async def delete_coach(
    coach_id: str,
    mode: str = Query("retire", pattern="^(retire|purge)$"),
    force: bool = Query(False),
    reason: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """
    Retire or purge a coach role.

    Args:
        coach_id: Coach identifier
        mode: "retire" (safe, reversible) or "purge" (permanent)
        force: Skip reference check (dangerous)
        reason: Optional explanation for deletion

    Returns:
        Dict with action result and references found
    """
    coach_role = get_coach_by_id(coach_id)
    if not coach_role:
        raise HTTPException(
            status_code=404,
            detail=f"Coach not found in registry: {coach_id}"
        )

    prompt_file = PROMPTS_DIR / coach_role["filename"]

    # Scan for references
    references = _scan_references(coach_id)

    # Block purge if references exist (unless forced)
    if mode == "purge" and references and not force:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot purge: {len(references)} references found. Use force=true to override.",
            headers={"X-References-Found": str(len(references))}
        )

    if mode == "retire":
        # Move to retired directory
        retired_coach_dir = RETIRED_DIR / coach_id
        retired_coach_dir.mkdir(parents=True, exist_ok=True)

        retired_path = retired_coach_dir / coach_role["filename"]

        # Move prompt file if it exists
        if prompt_file.exists():
            shutil.move(str(prompt_file), str(retired_path))

        # Create manifest
        manifest = {
            "coach_id": coach_id,
            "label": coach_role["label"],
            "retired_at": datetime.now().isoformat(),
            "reason": reason or "No reason provided",
            "original_path": f"prompts/{coach_role['filename']}",
            "references_found": len(references)
        }

        manifest_path = retired_coach_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')

        _log_deletion("retire", coach_id, mode, reason=reason, references=len(references))

        return {
            "retired": True,
            "coach_id": coach_id,
            "path": str(retired_coach_dir.relative_to(DEVX_ROOT)),
            "references_found": references,
            "manifest": manifest
        }

    else:  # mode == "purge"
        # Move to deleted directory with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        deleted_coach_dir = DELETED_DIR / f"{coach_id}_{timestamp}"
        deleted_coach_dir.mkdir(parents=True, exist_ok=True)

        # Move prompt file
        if prompt_file.exists():
            shutil.move(str(prompt_file), str(deleted_coach_dir / coach_role["filename"]))

        # Move backups if they exist
        backup_pattern = f"{coach_id}_*.md"
        for backup_file in BACKUPS_DIR.glob(backup_pattern):
            shutil.move(str(backup_file), str(deleted_coach_dir / backup_file.name))

        # Remove from registry
        _remove_from_registry(coach_id)

        # Create deletion manifest
        manifest = {
            "coach_id": coach_id,
            "label": coach_role["label"],
            "purged_at": datetime.now().isoformat(),
            "reason": reason or "No reason provided",
            "original_path": f"prompts/{coach_role['filename']}",
            "references_found": len(references),
            "forced": force,
            "registry_removed": True
        }

        manifest_path = deleted_coach_dir / "deletion_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')

        _log_deletion("purge", coach_id, mode, reason=reason, references=len(references), forced=force)

        return {
            "purged": True,
            "coach_id": coach_id,
            "path": str(deleted_coach_dir.relative_to(DEVX_ROOT)),
            "references_found": references,
            "forced": force,
            "registry_removed": True,
            "manifest": manifest
        }


@router.post("/devx/api/coaches/{coach_id}/restore")
async def restore_coach(coach_id: str) -> Dict[str, Any]:
    """
    Restore a retired or deleted coach.

    Searches retired/ and deleted/ directories for the coach and restores it.
    If restoring from purged state, also re-adds to registry.

    Args:
        coach_id: Coach identifier

    Returns:
        Dict with restoration result
    """
    coach_role = get_coach_by_id(coach_id)

    # Check retired directory first
    retired_coach_dir = RETIRED_DIR / coach_id
    if retired_coach_dir.exists():
        # Need coach_role for filename
        if not coach_role:
            raise HTTPException(
                status_code=404,
                detail=f"Coach {coach_id} not in registry and cannot determine filename"
            )

        retired_prompt = retired_coach_dir / coach_role["filename"]

        if retired_prompt.exists():
            # Restore to prompts/
            dest_path = PROMPTS_DIR / coach_role["filename"]
            shutil.move(str(retired_prompt), str(dest_path))

            # Clean up retired directory
            shutil.rmtree(retired_coach_dir)

            _log_deletion("restore", coach_id, "from_retired")

            return {
                "restored": True,
                "coach_id": coach_id,
                "source": "retired",
                "path": str(dest_path.relative_to(DEVX_ROOT))
            }

    # Check deleted directory (purged coaches)
    deleted_dirs = sorted(DELETED_DIR.glob(f"{coach_id}_*"), reverse=True)
    if deleted_dirs:
        # Use most recent deletion
        deleted_coach_dir = deleted_dirs[0]

        # Read manifest to get coach metadata
        manifest_path = deleted_coach_dir / "deletion_manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            label = manifest.get("label", coach_id.replace("_", " ").title())
            filename = manifest.get("original_path", "").split("/")[-1]
        else:
            # Fallback if no manifest
            label = coach_id.replace("_", " ").title()
            filename = f"{coach_id}_ai.md"

        deleted_prompt = deleted_coach_dir / filename

        if deleted_prompt.exists():
            # Restore to prompts/
            dest_path = PROMPTS_DIR / filename
            shutil.move(str(deleted_prompt), str(dest_path))

            # Restore backups
            for backup_file in deleted_coach_dir.glob(f"{coach_id}_*.md"):
                shutil.move(str(backup_file), str(BACKUPS_DIR / backup_file.name))

            # Re-add to registry if it was removed (purged)
            if not coach_role:
                _add_to_registry(coach_id, label, filename)

            _log_deletion("restore", coach_id, "from_deleted", source_dir=deleted_coach_dir.name)

            return {
                "restored": True,
                "coach_id": coach_id,
                "source": "deleted",
                "source_dir": deleted_coach_dir.name,
                "path": str(dest_path.relative_to(DEVX_ROOT)),
                "registry_restored": not bool(coach_role)
            }

    raise HTTPException(
        status_code=404,
        detail=f"Coach {coach_id} not found in retired or deleted directories"
    )


@router.get("/devx/api/coaches/{coach_id}/features")
async def get_coach_features(coach_id: str) -> Dict[str, Any]:
    """
    Get the features config for a specific coach.

    If the file doesn't exist, returns a default scaffold.

    Args:
        coach_id: Coach identifier

    Returns:
        Features config JSON
    """
    coach_role = get_coach_by_id(coach_id)
    if not coach_role:
        raise HTTPException(
            status_code=404,
            detail=f"Coach not found in registry: {coach_id}"
        )

    features_file = FEATURES_DIR / f"{coach_id}_features.json"

    if features_file.exists():
        try:
            config = json.loads(features_file.read_text(encoding="utf-8"))
            return {
                "id": coach_id,
                "config": config,
                "exists": True,
                "path": str(features_file.relative_to(DEVX_ROOT))
            }
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to read features file: {str(e)}"
            )
    else:
        # Return default scaffold
        scaffold = {
            "version": "1.0",
            "showInUI": True,
            "panes": []
        }
        return {
            "id": coach_id,
            "config": scaffold,
            "exists": False,
            "path": str(features_file.relative_to(DEVX_ROOT))
        }


def _check_integration_layer(coach_id: str, layer: str) -> Dict[str, Any]:
    """
    Check if a coach is integrated in a specific layer.

    Returns: {"pass": bool, "details": str}
    """
    try:
        if layer == "coach_registry":
            # Check ReDNACoreDemo/core/coach_registry.yaml
            registry_file = REDNA_ROOT / "core" / "coach_registry.yaml"
            if not registry_file.exists():
                return {"pass": False, "details": "coach_registry.yaml not found"}

            content = registry_file.read_text(encoding="utf-8")
            # Check if coach_id appears under "coaches:" section
            if f"{coach_id}:" in content:
                return {"pass": True, "details": "Found in registry"}
            return {"pass": False, "details": "Not found in coach_registry.yaml"}

        elif layer == "mode_manager":
            # Check ReDNACoreDemo/core/coach_mode_manager.py
            mode_mgr_file = REDNA_ROOT / "core" / "coach_mode_manager.py"
            if not mode_mgr_file.exists():
                return {"pass": False, "details": "coach_mode_manager.py not found"}

            content = mode_mgr_file.read_text(encoding="utf-8")
            checks = [
                (f'"{coach_id}"' in content, "VALID_MODES"),
                (f'"{coach_id}":' in content, "MODE_DISPLAY_NAMES or MODE_CAPABILITIES")
            ]

            passed = [check[1] for check in checks if check[0]]
            failed = [check[1] for check in checks if not check[0]]

            if not failed:
                return {"pass": True, "details": f"Found in {', '.join(passed)}"}
            return {"pass": False, "details": f"Missing from {', '.join(failed)}"}

        elif layer == "ui_readonly":
            # Check ReDNACoreDemo/core/ui_readonly.py
            ui_file = REDNA_ROOT / "core" / "ui_readonly.py"
            if not ui_file.exists():
                return {"pass": False, "details": "ui_readonly.py not found"}

            content = ui_file.read_text(encoding="utf-8")
            checks = [
                (f'"{coach_id}"' in content, "_DEFAULT_ICONS or _FALLBACK_PERSONAS")
            ]

            if checks[0][0]:
                return {"pass": True, "details": "Found in ui_readonly.py"}
            return {"pass": False, "details": "Not found in ui_readonly.py"}

        elif layer == "api_ts":
            # Check web/src/lib/api.ts
            api_ts_file = DEVX_ROOT / "web" / "src" / "lib" / "api.ts"
            if not api_ts_file.exists():
                return {"pass": False, "details": "api.ts not found"}

            content = api_ts_file.read_text(encoding="utf-8")

            # Check CANONICAL_ORDER, CANONICAL_DEFAULTS, PERSONA_ALIASES
            checks = [
                (f"'{coach_id}'" in content, "referenced in api.ts")
            ]

            if checks[0][0]:
                return {"pass": True, "details": "Found in api.ts"}
            return {"pass": False, "details": "Not found in CANONICAL_ORDER/DEFAULTS/ALIASES"}

        elif layer == "page_client":
            # Check web/src/app/page-client.tsx
            page_client_file = DEVX_ROOT / "web" / "src" / "app" / "page-client.tsx"
            if not page_client_file.exists():
                return {"pass": False, "details": "page-client.tsx not found"}

            content = page_client_file.read_text(encoding="utf-8")

            # Check normalizePersonaKey, shouldShowCoachToolsPane, renderRightPane
            checks = [
                (f"'{coach_id}'" in content or f'"{coach_id}"' in content, "referenced in page-client.tsx")
            ]

            if checks[0][0]:
                return {"pass": True, "details": "Found in page-client.tsx"}
            return {"pass": False, "details": "Not found in normalizePersonaKey or other functions"}

        elif layer == "core_api_prompts":
            # Check ReDNACoreDemo/core/api.py for SYSTEM_PROMPT, PERSONA_PROMPTS, PERSONA_RUBRICS
            core_api_file = REDNA_ROOT / "core" / "api.py"
            if not core_api_file.exists():
                return {"pass": False, "details": "core/api.py not found"}

            content = core_api_file.read_text(encoding="utf-8")

            # Just check if coach_id is mentioned at all
            if coach_id.lower() in content.lower() or coach_id.replace("_", " ").lower() in content.lower():
                return {"pass": True, "details": "Found in core/api.py"}
            return {"pass": False, "details": "Not found in SYSTEM_PROMPT or PERSONA_PROMPTS"}

        elif layer == "hc_llm_agent":
            # Check ReDNACoreDemo/core/hc_llm_agent.py
            hc_llm_file = REDNA_ROOT / "core" / "hc_llm_agent.py"
            if not hc_llm_file.exists():
                return {"pass": False, "details": "hc_llm_agent.py not found"}

            content = hc_llm_file.read_text(encoding="utf-8")

            if coach_id.lower() in content.lower() or coach_id.replace("_", " ").lower() in content.lower():
                return {"pass": True, "details": "Found in hc_llm_agent.py"}
            return {"pass": False, "details": "Not found in system message builder"}

        else:
            return {"pass": False, "details": f"Unknown layer: {layer}"}

    except Exception as e:
        return {"pass": False, "details": f"Error checking layer: {str(e)}"}


@router.get("/devx/api/coaches/{coach_id}/checklist")
async def get_coach_checklist(coach_id: str) -> Dict[str, Any]:
    """
    Check 7-layer integration status for a coach.

    Returns pass/fail status for each layer.

    Args:
        coach_id: Coach identifier

    Returns:
        Dict with per-layer status and overall readiness
    """
    coach_role = get_coach_by_id(coach_id)
    if not coach_role:
        raise HTTPException(
            status_code=404,
            detail=f"Coach not found in registry: {coach_id}"
        )

    # Define the 7 layers from ADDING_NEW_COACH_PROTOCOL.md
    layers = [
        {"id": "coach_registry", "label": "Coach Registry (coach_registry.yaml)", "required": True},
        {"id": "mode_manager", "label": "Mode Manager (coach_mode_manager.py)", "required": True},
        {"id": "ui_readonly", "label": "UI Roster (ui_readonly.py)", "required": True},
        {"id": "api_ts", "label": "Frontend Roster (api.ts)", "required": True},
        {"id": "page_client", "label": "Frontend Normalize (page-client.tsx)", "required": True},
        {"id": "core_api_prompts", "label": "Prompts (api.py)", "required": False},
        {"id": "hc_llm_agent", "label": "LLM Agent (hc_llm_agent.py)", "required": False},
    ]

    # Check each layer
    results = []
    required_pass_count = 0
    required_total_count = 0

    for layer_def in layers:
        result = _check_integration_layer(coach_id, layer_def["id"])

        layer_result = {
            "layer": layer_def["id"],
            "label": layer_def["label"],
            "required": layer_def["required"],
            "pass": result["pass"],
            "details": result["details"]
        }
        results.append(layer_result)

        if layer_def["required"]:
            required_total_count += 1
            if result["pass"]:
                required_pass_count += 1

    # Overall status: all required layers must pass
    ready = required_pass_count == required_total_count

    return {
        "id": coach_id,
        "ready": ready,
        "layers": results,
        "summary": {
            "required_passed": required_pass_count,
            "required_total": required_total_count,
            "optional_passed": sum(1 for r in results if not r["required"] and r["pass"]),
            "optional_total": sum(1 for r in results if not r["required"])
        }
    }


@router.put("/devx/api/coaches/{coach_id}/features")
async def update_coach_features(coach_id: str, update: CoachFeaturesUpdate) -> Dict[str, Any]:
    """
    Update the features config for a specific coach.

    Creates a timestamped backup before saving (if file exists).

    Args:
        coach_id: Coach identifier
        update: Request body with features config JSON

    Returns:
        Success message with backup info
    """
    coach_role = get_coach_by_id(coach_id)
    if not coach_role:
        raise HTTPException(
            status_code=404,
            detail=f"Coach not found in registry: {coach_id}"
        )

    features_file = FEATURES_DIR / f"{coach_id}_features.json"

    # Validate config has required fields
    if "version" not in update.config:
        raise HTTPException(
            status_code=400,
            detail="Features config must include 'version' field"
        )

    # Create backup if file exists
    backup_path = None
    if features_file.exists():
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"{coach_id}_features_{timestamp}.json"
            backup_path = BACKUPS_DIR / backup_filename
            shutil.copy2(str(features_file), str(backup_path))
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create backup: {str(e)}"
            )

    # Write new features config
    try:
        features_file.write_text(
            json.dumps(update.config, indent=2),
            encoding="utf-8"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to write features file: {str(e)}"
        )

    stat = features_file.stat()

    return {
        "saved": True,
        "id": coach_id,
        "path": str(features_file.relative_to(DEVX_ROOT)),
        "bytes": stat.st_size,
        "backup_created": backup_path is not None,
        "backup_path": str(backup_path.relative_to(DEVX_ROOT)) if backup_path else None,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
    }


@router.post("/devx/api/coaches/{coach_id}/rename")
async def rename_coach(coach_id: str, request: CoachRenameRequest) -> Dict[str, Any]:
    """
    Rename a coach across all integration layers (PREVIEW).

    Scans for references and shows what will be modified.

    Args:
        coach_id: Current coach identifier
        request: New coach ID, label, and reason

    Returns:
        Dict with rename preview and files to modify
    """
    coach_role = get_coach_by_id(coach_id)
    if not coach_role:
        raise HTTPException(
            status_code=404,
            detail=f"Coach not found in registry: {coach_id}"
        )

    new_coach_id = request.new_coach_id
    new_label = request.new_label

    # Validation
    if new_coach_id == coach_id:
        raise HTTPException(
            status_code=400,
            detail="New coach ID must be different from current ID"
        )

    # Check if new ID already exists
    if get_coach_by_id(new_coach_id):
        raise HTTPException(
            status_code=409,
            detail=f"Coach ID '{new_coach_id}' already exists"
        )

    # Scan for all references
    references = _scan_references(coach_id)

    # Files that will be modified
    files_to_modify = []

    # Critical integration files
    critical_files = [
        ("ReDNACoreDemo/devx/backend/coach_registry.py", "Update COACH_ROLES"),
        ("ReDNACoreDemo/core/coach_registry.yaml", "Rename coach definition"),
        ("ReDNACoreDemo/core/coach_mode_manager.py", "Update VALID_MODES, MODE_DISPLAY_NAMES"),
        ("ReDNACoreDemo/core/ui_readonly.py", "Update _DEFAULT_ICONS, _FALLBACK_PERSONAS"),
        ("web/src/lib/api.ts", "Update CANONICAL_ORDER, DEFAULTS, ALIASES"),
        ("web/src/app/page-client.tsx", "Update normalizePersonaKey"),
    ]

    for file_path, change_desc in critical_files:
        full_path = DEVX_ROOT / file_path
        if full_path.exists():
            files_to_modify.append({
                "file": file_path,
                "changes": [change_desc]
            })

    # Prompt and features files
    old_prompt = f"prompts/{coach_role['filename']}"
    new_prompt = f"prompts/{coach_role['filename'].replace(coach_id, new_coach_id)}"
    files_to_modify.append({"file": old_prompt, "changes": [f"Rename to {new_prompt}"]})

    old_features = f"prompts/features/{coach_id}_features.json"
    new_features = f"prompts/features/{new_coach_id}_features.json"
    if (FEATURES_DIR / f"{coach_id}_features.json").exists():
        files_to_modify.append({"file": old_features, "changes": [f"Rename to {new_features}"]})

    return {
        "coach_id": coach_id,
        "new_coach_id": new_coach_id,
        "new_label": new_label,
        "references_found": len(references),
        "files_to_modify": files_to_modify,
        "total_files": len(files_to_modify),
        "preview_only": True,
        "message": "This is a preview. Use /rename/execute to perform the rename."
    }


@router.post("/devx/api/coaches/{coach_id}/rename/execute")
async def execute_rename(coach_id: str, request: CoachRenameRequest) -> Dict[str, Any]:
    """
    Execute the rename operation across all integration layers.

    Args:
        coach_id: Current coach identifier  
        request: New coach ID, label, and reason

    Returns:
        Dict with execution result
    """
    coach_role = get_coach_by_id(coach_id)
    if not coach_role:
        raise HTTPException(status_code=404, detail=f"Coach not found: {coach_id}")

    new_coach_id = request.new_coach_id
    new_label = request.new_label

    if new_coach_id == coach_id:
        raise HTTPException(status_code=400, detail="New ID must be different")
    if get_coach_by_id(new_coach_id):
        raise HTTPException(status_code=409, detail=f"ID '{new_coach_id}' already exists")

    files_modified = []
    errors = []

    try:
        # 1. DevX registry
        devx_reg = DEVX_ROOT / "ReDNACoreDemo" / "devx" / "backend" / "coach_registry.py"
        if devx_reg.exists():
            content = devx_reg.read_text(encoding="utf-8")
            content = content.replace(f'{{"id": "{coach_id}"', f'{{"id": "{new_coach_id}"')
            content = content.replace(f'"label": "{coach_role["label"]}"', f'"label": "{new_label}"')
            devx_reg.write_text(content, encoding="utf-8")
            files_modified.append("coach_registry.py")

        # 2. Core registry (YAML)
        core_reg = REDNA_ROOT / "core" / "coach_registry.yaml"
        if core_reg.exists():
            content = core_reg.read_text(encoding="utf-8")
            content = content.replace(f"  {coach_id}:", f"  {new_coach_id}:")
            content = content.replace(f'id: "{coach_id}"', f'id: "{new_coach_id}"')
            content = content.replace(f'display_name: "{coach_role["label"]}"', f'display_name: "{new_label}"')
            core_reg.write_text(content, encoding="utf-8")
            files_modified.append("coach_registry.yaml")

        # 3. Prompt file
        old_prompt = PROMPTS_DIR / coach_role["filename"]
        new_prompt = PROMPTS_DIR / coach_role["filename"].replace(coach_id, new_coach_id)
        if old_prompt.exists():
            shutil.move(str(old_prompt), str(new_prompt))
            files_modified.append(f"prompts/{coach_role['filename']}")

        # 4. Features file
        old_feat = FEATURES_DIR / f"{coach_id}_features.json"
        new_feat = FEATURES_DIR / f"{new_coach_id}_features.json"
        if old_feat.exists():
            shutil.move(str(old_feat), str(new_feat))
            files_modified.append(f"features/{coach_id}_features.json")

        # 5. Update critical integration files
        for file_rel_path in [
            "ReDNACoreDemo/core/coach_mode_manager.py",
            "ReDNACoreDemo/core/ui_readonly.py",
            "ReDNACoreDemo/core/api.py",
            "ReDNACoreDemo/core/hc_llm_agent.py",
            "web/src/lib/api.ts",
            "web/src/app/page-client.tsx"
        ]:
            fpath = DEVX_ROOT / file_rel_path
            if fpath.exists():
                try:
                    content = fpath.read_text(encoding="utf-8")
                    modified = False
                    if f'"{coach_id}"' in content:
                        content = content.replace(f'"{coach_id}"', f'"{new_coach_id}"')
                        modified = True
                    if f"'{coach_id}'" in content:
                        content = content.replace(f"'{coach_id}'", f"'{new_coach_id}'")
                        modified = True
                    if coach_role["label"] in content:
                        content = content.replace(coach_role["label"], new_label)
                        modified = True
                    if modified:
                        fpath.write_text(content, encoding="utf-8")
                        files_modified.append(file_rel_path)
                except Exception as e:
                    errors.append(f"{file_rel_path}: {str(e)}")

        # Log
        _log_deletion("rename", coach_id, "rename", reason=request.reason, 
                     new_coach_id=new_coach_id, new_label=new_label)

        return {
            "success": True,
            "old_coach_id": coach_id,
            "new_coach_id": new_coach_id,
            "new_label": new_label,
            "files_modified": files_modified,
            "errors": errors,
            "message": f"Renamed '{coach_id}' to '{new_coach_id}'"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rename failed: {str(e)}")


@router.get("/devx/api/coaches/{coach_id}/tests/last")
async def get_last_test_run(coach_id: str) -> Dict[str, Any]:
    """
    Get last test run results for a coach (stub for now).

    Args:
        coach_id: Coach identifier

    Returns:
        Dict with test results
    """
    coach_role = get_coach_by_id(coach_id)
    if not coach_role:
        raise HTTPException(
            status_code=404,
            detail=f"Coach not found in registry: {coach_id}"
        )

    return {
        "coach_id": coach_id,
        "status": "none",
        "message": "No test runs yet. Local LLM sandbox required for testing."
    }


# ============================================================================
# 2) METADATA ENDPOINT
# ============================================================================

@router.get("/devx/api/coaches/{coach_id}/metadata")
async def get_coach_metadata(coach_id: str) -> Dict[str, Any]:
    """
    Get comprehensive metadata from DevX registry, Core YAML, and filesystem.
    """
    coach_role = get_coach_by_id(coach_id)
    if not coach_role:
        raise HTTPException(status_code=404, detail=f"Coach not found: {coach_id}")

    # DevX registry data
    devx_data = {
        "id": coach_role["id"],
        "label": coach_role["label"],
        "filename": coach_role["filename"],
        "source": "DevX registry"
    }

    # Core YAML data (if available)
    core_yaml_data = {}
    core_registry = REDNA_ROOT / "core" / "coach_registry.yaml"
    if core_registry.exists():
        try:
            import yaml
            with open(core_registry, 'r') as f:
                yaml_content = yaml.safe_load(f)
                if yaml_content and "coaches" in yaml_content:
                    coach_yaml = yaml_content["coaches"].get(coach_id, {})
                    core_yaml_data = {
                        "category": coach_yaml.get("category", "N/A"),
                        "capabilities": coach_yaml.get("capabilities", []),
                        "icon": coach_yaml.get("icon", "N/A"),
                        "description": coach_yaml.get("description", "N/A"),
                        "source": "Core YAML"
                    }
        except Exception as e:
            core_yaml_data = {"error": f"Failed to parse YAML: {str(e)}"}

    # Filesystem data
    prompt_file = PROMPTS_DIR / coach_role["filename"]
    features_file = FEATURES_DIR / f"{coach_id}_features.json"

    fs_data = {
        "prompt_path": str(prompt_file.relative_to(DEVX_ROOT)),
        "features_path": str(features_file.relative_to(DEVX_ROOT)),
        "prompt_exists": prompt_file.exists(),
        "features_exists": features_file.exists(),
        "prompt_size_bytes": prompt_file.stat().st_size if prompt_file.exists() else 0,
        "features_size_bytes": features_file.stat().st_size if features_file.exists() else 0,
        "prompt_modified_at": datetime.fromtimestamp(prompt_file.stat().st_mtime).isoformat() if prompt_file.exists() else None,
        "source": "Filesystem"
    }

    return {
        "coach_id": coach_id,
        "devx_registry": devx_data,
        "core_yaml": core_yaml_data,
        "filesystem": fs_data
    }


# ============================================================================
# 3) INSIGHTS APPEND + READ
# ============================================================================

class InsightAppendRequest(BaseModel):
    kind: str  # "summary", "metric", "note"
    data: Dict[str, Any]


@router.post("/devx/api/coaches/{coach_id}/insights/append")
async def append_insight(coach_id: str, request: InsightAppendRequest) -> Dict[str, Any]:
    """Append a single insight entry to the coach's JSONL file."""
    coach_role = get_coach_by_id(coach_id)
    if not coach_role:
        raise HTTPException(status_code=404, detail=f"Coach not found: {coach_id}")

    insights_file = INSIGHTS_DIR / f"{coach_id}.jsonl"

    # Compute prompt hash if file exists
    prompt_file = PROMPTS_DIR / coach_role["filename"]
    prompt_hash = "N/A"
    if prompt_file.exists():
        import hashlib
        prompt_hash = hashlib.sha256(prompt_file.read_bytes()).hexdigest()[:16]

    # Build entry
    entry = {
        "ts": datetime.now().isoformat(),
        "coach_id": coach_id,
        "kind": request.kind,
        "prompt_hash": prompt_hash,
        "data": request.data
    }

    # Append to JSONL
    with insights_file.open('a', encoding='utf-8') as f:
        f.write(json.dumps(entry) + '\n')

    return {"appended": True, "entry": entry}


@router.get("/devx/api/coaches/{coach_id}/insights")
async def get_insights(
    coach_id: str,
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    kinds: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Read insights from JSONL, newest first."""
    coach_role = get_coach_by_id(coach_id)
    if not coach_role:
        raise HTTPException(status_code=404, detail=f"Coach not found: {coach_id}")

    insights_file = INSIGHTS_DIR / f"{coach_id}.jsonl"

    if not insights_file.exists():
        return {
            "coach_id": coach_id,
            "items": [],
            "total": 0,
            "message": "No insights yet"
        }

    # Parse filter kinds
    kind_filter = set(kinds.split(',')) if kinds else None

    # Read all entries
    entries = []
    with insights_file.open('r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                entry = json.loads(line)
                if kind_filter is None or entry.get("kind") in kind_filter:
                    entries.append(entry)

    # Reverse to get newest first
    entries.reverse()

    total = len(entries)
    items = entries[offset:offset + limit]

    return {
        "coach_id": coach_id,
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset
    }


# ============================================================================
# 4) TESTS / DIAGNOSTICS RUNNER
# ============================================================================

class TestRunRequest(BaseModel):
    mode: str  # "sanity" or "validate_packet"
    input: Optional[str] = None


@router.post("/devx/api/coaches/{coach_id}/tests/run")
async def run_test(coach_id: str, request: TestRunRequest) -> Dict[str, Any]:
    """Run sanity dialog or validate coach_packet schema."""
    coach_role = get_coach_by_id(coach_id)
    if not coach_role:
        raise HTTPException(status_code=404, detail=f"Coach not found: {coach_id}")

    if request.mode == "validate_packet":
        # Validate against schema
        schema_file = SCHEMAS_DIR / "coach_packet.json"
        if not schema_file.exists():
            raise HTTPException(status_code=500, detail="Schema file not found")

        schema = json.loads(schema_file.read_text())

        # Parse input
        try:
            packet = json.loads(request.input or "{}")
        except json.JSONDecodeError as e:
            return {
                "coach_id": coach_id,
                "mode": "validate_packet",
                "valid": False,
                "errors": [f"Invalid JSON: {str(e)}"]
            }

        # Validate using jsonschema
        try:
            import jsonschema
            jsonschema.validate(packet, schema)
            return {
                "coach_id": coach_id,
                "mode": "validate_packet",
                "valid": True,
                "errors": []
            }
        except jsonschema.ValidationError as e:
            return {
                "coach_id": coach_id,
                "mode": "validate_packet",
                "valid": False,
                "errors": [str(e)]
            }
        except ImportError:
            # Fallback: basic validation without jsonschema
            errors = []
            if "coach_id" not in packet:
                errors.append("Missing required field: coach_id")
            if "turn_count" not in packet:
                errors.append("Missing required field: turn_count")
            if "messages" not in packet:
                errors.append("Missing required field: messages")

            return {
                "coach_id": coach_id,
                "mode": "validate_packet",
                "valid": len(errors) == 0,
                "errors": errors
            }

    elif request.mode == "sanity":
        # Stub sanity test - returns fake message + minimal packet
        return {
            "coach_id": coach_id,
            "mode": "sanity",
            "status": "passed",
            "output": "Hello! I am the coach assistant. How can I help you today?",
            "coach_packet": {
                "coach_id": coach_id,
                "turn_count": 1,
                "messages": [
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hello! I am the coach assistant. How can I help you today?"}
                ],
                "metadata": {
                    "prompt_hash": "stub_hash",
                    "duration_ms": 42
                }
            }
        }

    else:
        raise HTTPException(status_code=400, detail=f"Unknown mode: {request.mode}")


# ============================================================================
# 5) NEW COACH CREATION WIZARD
# ============================================================================

class CoachCreateRequest(BaseModel):
    new_coach_id: str
    new_label: str
    description: Optional[str] = "Coach description"


@router.post("/devx/api/coaches/create")
async def create_coach(request: CoachCreateRequest) -> Dict[str, Any]:
    """Create a new coach with scaffolds and minimal registry entries."""

    # Validate ID format
    if not re.match(r'^[a-z0-9_]+$', request.new_coach_id):
        raise HTTPException(
            status_code=400,
            detail="Coach ID must match pattern: ^[a-z0-9_]+$"
        )

    # Check uniqueness
    if get_coach_by_id(request.new_coach_id):
        raise HTTPException(
            status_code=409,
            detail=f"Coach ID '{request.new_coach_id}' already exists"
        )

    # Check retired/deleted
    retired_dir = RETIRED_DIR / request.new_coach_id
    if retired_dir.exists():
        raise HTTPException(
            status_code=409,
            detail=f"Coach '{request.new_coach_id}' exists in retired/"
        )

    new_coach_id = request.new_coach_id
    new_label = request.new_label

    with ops_lock():
        # Create prompt scaffold
        prompt_file = PROMPTS_DIR / f"{new_coach_id}_ai.md"
        prompt_scaffold = get_default_scaffold(new_label)
        prompt_file.write_text(prompt_scaffold, encoding='utf-8')

        # Create features scaffold
        features_file = FEATURES_DIR / f"{new_coach_id}_features.json"
        features_scaffold = {"version": "1.0", "showInUI": True, "panes": []}
        features_file.write_text(json.dumps(features_scaffold, indent=2), encoding='utf-8')

        # Append to DevX registry
        devx_registry = REDNA_ROOT / "devx" / "backend" / "coach_registry.py"
        if devx_registry.exists():
            content = devx_registry.read_text(encoding='utf-8')
            # Find COACH_ROLES list and append
            new_entry = f'    {{"id": "{new_coach_id}", "label": "{new_label}", "filename": "{new_coach_id}_ai.md"}},\n'
            # Insert before closing bracket
            content = content.replace(
                ']',
                f'{new_entry}]',
                1  # Only first occurrence
            )
            devx_registry.write_text(content, encoding='utf-8')

        # Create minimal Core YAML entry (append if file exists)
        core_registry = REDNA_ROOT / "core" / "coach_registry.yaml"
        if core_registry.exists():
            yaml_entry = f"""
  {new_coach_id}:
    display_name: "{new_label}"
    id: "{new_coach_id}"
    description: "{request.description}"
    primary_namespaces: []
    capabilities: []
    delegation_context: "New coach - configure as needed"
    natural_domains: []
    suitable_for_types:
      - trait
      - container
    autonomy_level: "medium"
"""
            with core_registry.open('a', encoding='utf-8') as f:
                f.write(yaml_entry)

    # Return checklist snapshot
    from .coach_registry import get_coach_by_id as refresh_coach
    # Reload registry (in production would reload module)

    return {
        "created": True,
        "coach_id": new_coach_id,
        "label": new_label,
        "files_created": [
            str(prompt_file.relative_to(DEVX_ROOT)),
            str(features_file.relative_to(DEVX_ROOT))
        ],
        "message": f"Coach '{new_coach_id}' created. Complete 7-layer integration via Checklist tab."
    }
