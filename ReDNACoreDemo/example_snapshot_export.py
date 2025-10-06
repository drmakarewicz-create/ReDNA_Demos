"""Example usage of Persona Snapshot Export."""

from core import snapshot_exporter
import json

def example_full_export():
    """Export complete PaDNA snapshot."""
    print("\n=== Full Snapshot Export Example ===\n")

    user_id = "test_user"

    # Export full snapshot
    print("Exporting full PaDNA snapshot...")
    snapshot = snapshot_exporter.export_snapshot(user_id)

    print(f"\n📸 Snapshot ID: {snapshot.id}")
    print(f"👤 User: {snapshot.user_id}")
    print(f"📅 Created: {snapshot.created_at}")
    print(f"🎯 Scope: {snapshot.scope}")
    print(f"📊 Families: {', '.join(snapshot.families)}")
    print(f"📈 Traits: {snapshot.metadata.get('trait_count', 0)}")
    print(f"💾 Size: {snapshot.metadata.get('size_bytes', 0):,} bytes")
    print(f"📦 Version: {snapshot.version}\n")

    # Show data summary
    print("Data Summary:")
    print(f"  - Observations: {len(snapshot.data.get('observations', {}))}")
    print(f"  - Resolved: {len(snapshot.data.get('resolved', {}))}")
    print(f"  - Evidence: {len(snapshot.data.get('evidence', {}))}")

    ucn_summary = snapshot.data.get("ucn_rr_summary", {})
    if ucn_summary:
        print(f"\nUCN/RR Summary:")
        print(f"  - Avg UCN: {ucn_summary.get('avg_ucn', 0):.2f}")
        print(f"  - Avg RR: {ucn_summary.get('avg_rr', 0):.4f}")
        print(f"  - Curiosity: {ucn_summary.get('curiosity_score', 0):.4f}")

    print(f"\n✅ Snapshot saved to: data/users/{user_id}/snapshots/{snapshot.id}.json\n")

    return snapshot


def example_partial_export():
    """Export specific trait families only."""
    print("\n=== Partial Snapshot Export Example ===\n")

    user_id = "test_user"
    families = ["LooksDNA", "StyleDNA"]
    label = "Fashion app export"

    print(f"Exporting {', '.join(families)} with label '{label}'...")
    snapshot = snapshot_exporter.export_snapshot(
        user_id=user_id,
        families=families,
        label=label,
    )

    print(f"\n📸 Snapshot ID: {snapshot.id}")
    print(f"🎯 Scope: {snapshot.scope}")
    print(f"📊 Families: {', '.join(snapshot.families)}")
    print(f"📈 Traits: {snapshot.metadata.get('trait_count', 0)}")
    print(f"💾 Size: {snapshot.metadata.get('size_bytes', 0):,} bytes")
    print(f"🏷️  Label: {snapshot.metadata.get('label')}\n")

    return snapshot


def example_list_snapshots():
    """List snapshot history."""
    print("\n=== Snapshot History Example ===\n")

    user_id = "test_user"

    snapshots = snapshot_exporter.list_snapshots(user_id, limit=10)

    if not snapshots:
        print(f"No snapshots found for user '{user_id}'")
        return

    print(f"Found {len(snapshots)} snapshot(s) for user '{user_id}':\n")

    for i, meta in enumerate(snapshots, 1):
        print(f"{i}. {meta.id}")
        print(f"   Created: {meta.created_at}")
        print(f"   Scope: {meta.scope}")
        print(f"   Families: {', '.join(meta.families) if meta.families else 'None'}")
        print(f"   Traits: {meta.trait_count}")
        print(f"   Size: {meta.size_bytes:,} bytes")
        if meta.label:
            print(f"   Label: {meta.label}")
        print()


def example_load_snapshot():
    """Load and inspect a snapshot."""
    print("\n=== Load Snapshot Example ===\n")

    user_id = "test_user"

    # Get most recent snapshot
    snapshots = snapshot_exporter.list_snapshots(user_id, limit=1)
    if not snapshots:
        print("No snapshots found. Export one first.")
        return

    snapshot_id = snapshots[0].id
    print(f"Loading snapshot: {snapshot_id}\n")

    snapshot = snapshot_exporter.load_snapshot(user_id, snapshot_id)

    if snapshot:
        print(f"✅ Loaded: {snapshot.id}")
        print(f"   Scope: {snapshot.scope}")
        print(f"   Families: {', '.join(snapshot.families)}")
        print(f"   Traits: {snapshot.metadata.get('trait_count', 0)}")

        # Show sample trait
        obs = snapshot.data.get("observations", {})
        if obs:
            sample_trait = list(obs.keys())[0]
            print(f"\n   Sample trait: {sample_trait}")
            print(f"   Value: {json.dumps(obs[sample_trait], indent=4)}")
    else:
        print("❌ Failed to load snapshot")


def example_delete_snapshot():
    """Delete an old snapshot."""
    print("\n=== Delete Snapshot Example ===\n")

    user_id = "test_user"

    # Get oldest snapshot
    snapshots = snapshot_exporter.list_snapshots(user_id, limit=100)
    if len(snapshots) < 2:
        print("Need at least 2 snapshots to demonstrate deletion. Skipping.")
        return

    # Delete the oldest one
    oldest = snapshots[-1]
    print(f"Deleting oldest snapshot: {oldest.id}")
    print(f"  Created: {oldest.created_at}")

    success = snapshot_exporter.delete_snapshot(user_id, oldest.id)

    if success:
        print(f"✅ Deleted: {oldest.id}")

        # Show remaining count
        remaining = snapshot_exporter.list_snapshots(user_id, limit=100)
        print(f"   Remaining snapshots: {len(remaining)}")
    else:
        print(f"❌ Failed to delete snapshot")


def example_json_download():
    """Simulate downloading snapshot as JSON."""
    print("\n=== JSON Download Example ===\n")

    user_id = "test_user"

    # Get most recent
    snapshots = snapshot_exporter.list_snapshots(user_id, limit=1)
    if not snapshots:
        print("No snapshots found. Export one first.")
        return

    snapshot_id = snapshots[0].id
    snapshot = snapshot_exporter.load_snapshot(user_id, snapshot_id)

    if snapshot:
        # Convert to JSON (as would be downloaded)
        json_str = json.dumps(snapshot.as_dict(), indent=2)

        print(f"Snapshot as JSON (first 500 chars):")
        print("=" * 60)
        print(json_str[:500])
        print("...")
        print("=" * 60)
        print(f"\nFull size: {len(json_str):,} characters")
        print(f"File would be: {snapshot_id}.json")


if __name__ == "__main__":
    # Run examples
    print("\n" + "="*60)
    print("  PERSONA SNAPSHOT EXPORT EXAMPLES")
    print("="*60)

    # 1. Full export
    snapshot = example_full_export()

    # 2. Partial export
    partial_snapshot = example_partial_export()

    # 3. List history
    example_list_snapshots()

    # 4. Load snapshot
    example_load_snapshot()

    # 5. JSON download simulation
    example_json_download()

    # 6. Delete snapshot (optional - uncomment to test)
    # example_delete_snapshot()

    print("\n" + "="*60)
    print("✨ Done! Check data/users/test_user/snapshots/")
    print("="*60 + "\n")
