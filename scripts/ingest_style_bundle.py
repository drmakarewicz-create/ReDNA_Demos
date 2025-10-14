#!/usr/bin/env python3
"""
ChatDNA Style Bundle Ingestion Script

Validates and ingests persona style bundles into Core user state.
Creates resolved.json with LanguageStyleDNA, PsyDNA, and SocDNA traits.

Usage:
    python scripts/ingest_style_bundle.py fixtures/chatdna/personas/hemingway.bundle.json
    python scripts/ingest_style_bundle.py fixtures/chatdna/personas/obama.bundle.json --dry-run
"""

import json
import sys
from pathlib import Path
from datetime import datetime
import argparse

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def validate_bundle(bundle_data, schema_path):
    """Validate bundle against JSON schema."""
    try:
        import jsonschema
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)
        jsonschema.validate(bundle_data, schema)
        return True, None
    except jsonschema.ValidationError as e:
        return False, str(e)
    except ImportError:
        print("⚠️  jsonschema not installed, skipping schema validation")
        return True, "Schema validation skipped (jsonschema not available)"


def compute_rr_from_ucn(ucn):
    """Compute RR score from UCN (0-1000 → 0-100)."""
    # Simple linear mapping: UCN 1000 → RR 100, UCN 0 → RR 0
    return min(100, max(0, ucn / 10))


def ingest_bundle(bundle_path, dry_run=False, data_dir=None):
    """
    Ingest a style bundle into Core user state.

    Args:
        bundle_path: Path to .bundle.json file
        dry_run: If True, validate but don't write
        data_dir: Override default data directory

    Returns:
        dict: Ingestion summary
    """
    bundle_path = Path(bundle_path)
    if not bundle_path.exists():
        raise FileNotFoundError(f"Bundle not found: {bundle_path}")

    # Load bundle
    with open(bundle_path, 'r', encoding='utf-8') as f:
        bundle = json.load(f)

    user_id = bundle['user_id']
    profile = bundle['profile']
    paths = bundle['paths']

    print(f"📦 Loading bundle: {profile['label']}")
    print(f"   User ID: {user_id}")
    print(f"   Source: {profile['source']}")
    print(f"   Containers: {len(paths)}")

    # Validate against schema
    schema_path = Path(__file__).parent.parent / "fixtures" / "chatdna" / "schema" / "chatdna_style_bundle.schema.json"
    if schema_path.exists():
        valid, error = validate_bundle(bundle, schema_path)
        if not valid:
            print(f"❌ Schema validation failed: {error}")
            return {"success": False, "error": error}
        print("✅ Schema validation passed")

    # Build resolved.json structure
    resolved = {}
    ucn_sum = 0
    high_ucn_traits = []

    for path, trait_data in paths.items():
        # Compute RR if not present
        if 'rr' not in trait_data:
            trait_data['rr'] = compute_rr_from_ucn(trait_data['ucn'])

        # Extract domain (e.g., LanguageStyleDNA from LanguageStyleDNA.CadenceDNA)
        parts = path.split('.')
        domain = parts[0]

        if domain not in resolved:
            resolved[domain] = {}

        # Store trait with Core-compatible structure
        resolved[domain][path] = {
            "resolved_value": trait_data.get("resolved_value"),
            "ucn": trait_data.get("ucn"),
            "rr": trait_data.get("rr"),
            "curiosity": trait_data.get("curiosity", 100 - trait_data.get("rr", 0)),
            "reasons": trait_data.get("reasons", []),
            "provenance": trait_data.get("provenance", {}),
            "version": trait_data.get("version", ".v1"),
            "status": trait_data.get("status", "prototype"),
            "last_updated": datetime.now().isoformat()
        }

        ucn_sum += trait_data['ucn']
        if trait_data['ucn'] >= 800:
            high_ucn_traits.append((path, trait_data['ucn'], trait_data.get('resolved_value')))

    # Calculate summary stats
    mean_ucn = ucn_sum / len(paths) if paths else 0
    mean_rr = compute_rr_from_ucn(mean_ucn)
    high_ucn_traits.sort(key=lambda x: x[1], reverse=True)
    top_5_traits = high_ucn_traits[:5]

    print(f"\n📊 Summary:")
    print(f"   Total containers: {len(paths)}")
    print(f"   Mean UCN: {mean_ucn:.1f}")
    print(f"   Mean RR: {mean_rr:.1f}")
    print(f"\n   Top 5 high-confidence traits:")
    for path, ucn, value in top_5_traits:
        trait_name = path.split('.')[-1].replace('DNA', '')
        print(f"     • {trait_name}: {value} (UCN: {ucn}, RR: {compute_rr_from_ucn(ucn):.1f})")

    if dry_run:
        print("\n🏃 Dry run - no files written")
        return {
            "success": True,
            "dry_run": True,
            "user_id": user_id,
            "container_count": len(paths),
            "mean_ucn": mean_ucn,
            "mean_rr": mean_rr
        }

    # Determine data directory
    if data_dir is None:
        data_dir = Path(__file__).parent.parent / "data" / "users" / user_id
    else:
        data_dir = Path(data_dir) / user_id

    data_dir.mkdir(parents=True, exist_ok=True)

    # Write resolved.json
    resolved_path = data_dir / "resolved.json"
    with open(resolved_path, 'w', encoding='utf-8') as f:
        json.dump(resolved, f, indent=2)

    print(f"\n✅ Ingested to: {resolved_path}")

    # Write user.json metadata
    user_meta = {
        "user_id": user_id,
        "profile": profile,
        "created_at": datetime.now().isoformat(),
        "source": "style_bundle_ingestion",
        "bundle_path": str(bundle_path.absolute())
    }
    user_path = data_dir / "user.json"
    with open(user_path, 'w', encoding='utf-8') as f:
        json.dump(user_meta, f, indent=2)

    # Create empty evidence and observations files
    evidence_path = data_dir / "evidence.json"
    if not evidence_path.exists():
        with open(evidence_path, 'w', encoding='utf-8') as f:
            json.dump({}, f)

    obs_path = data_dir / "observations.json"
    if not obs_path.exists():
        with open(obs_path, 'w', encoding='utf-8') as f:
            json.dump([], f)

    return {
        "success": True,
        "user_id": user_id,
        "resolved_path": str(resolved_path),
        "container_count": len(paths),
        "mean_ucn": mean_ucn,
        "mean_rr": mean_rr,
        "top_traits": top_5_traits
    }


def main():
    parser = argparse.ArgumentParser(description="Ingest ChatDNA style bundle")
    parser.add_argument("bundle_path", help="Path to .bundle.json file")
    parser.add_argument("--dry-run", action="store_true", help="Validate but don't write")
    parser.add_argument("--data-dir", help="Override data directory")
    args = parser.parse_args()

    try:
        result = ingest_bundle(args.bundle_path, dry_run=args.dry_run, data_dir=args.data_dir)
        if result["success"]:
            print("\n🎉 Ingestion complete!")
            sys.exit(0)
        else:
            print(f"\n❌ Ingestion failed: {result.get('error')}")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
