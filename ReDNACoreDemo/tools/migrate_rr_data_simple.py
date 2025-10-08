#!/usr/bin/env python3
"""
Simplified RR Data Migration Script

Just analyze the current state without full migration complexity.
"""

import sys
sys.path.insert(0, '/Users/davidmakarewicz/Documents/ReDNA_Demos/ReDNACoreDemo')

from core.storage import list_users, read_user_state

# Get all users
all_users = list_users()
print(f"Total users: {len(all_users)}")

total_traits = 0
invalid_rr_count = 0

for user_entry in all_users:
    user_id = user_entry.get("id")
    if not user_id:
        continue
    
    try:
        resolved, _, _ = read_user_state(user_id)
        if not resolved:
            continue
        
        for trait_path, entry in resolved.items():
            total_traits += 1
            rr = entry.get("rr")
            
            if rr is None or (isinstance(rr, (int, float)) and rr > 100):
                invalid_rr_count += 1
                if invalid_rr_count <= 5:  # Show first 5
                    print(f"  Invalid RR: {user_id} - {trait_path}: RR={rr}")
    
    except Exception as e:
        print(f"Error reading {user_id}: {e}")
        continue

print(f"\nTotal traits: {total_traits}")
print(f"Invalid RR values: {invalid_rr_count}")
