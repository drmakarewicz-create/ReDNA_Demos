#!/usr/bin/env python3
"""
Quick verification script for debug endpoint auth implementation.
"""
import os
import sys

# Test 1: Check imports work
print("✓ Test 1: Checking imports...")
try:
    from ReDNACoreDemo.core.graph.debug_api import DEBUG_ROUTES_ENABLED, DEBUG_TOKEN, router
    print(f"  DEBUG_ROUTES_ENABLED={DEBUG_ROUTES_ENABLED}")
    print(f"  DEBUG_TOKEN={'(set)' if DEBUG_TOKEN else '(empty)'}")
    print("  ✓ Imports successful\n")
except ImportError as e:
    print(f"  ✗ Import failed: {e}\n")
    sys.exit(1)

# Test 2: Check router has routes
print("✓ Test 2: Checking router routes...")
route_count = len(router.routes)
print(f"  Found {route_count} routes in router")

if DEBUG_ROUTES_ENABLED:
    # Should have 3 specific endpoints
    expected = 3
    if route_count == expected:
        print(f"  ✓ Correct number of routes (expected {expected})\n")
    else:
        print(f"  ⚠ Route count mismatch (expected {expected}, got {route_count})\n")
else:
    # Should have 1 catch-all shim
    expected = 1
    if route_count == expected:
        print(f"  ✓ Shim route mounted (expected {expected})\n")
    else:
        print(f"  ⚠ Route count mismatch (expected {expected}, got {route_count})\n")

# Test 3: List routes
print("✓ Test 3: Route details...")
for route in router.routes:
    path = getattr(route, 'path', 'unknown')
    methods = getattr(route, 'methods', set())
    print(f"  - {path} [{', '.join(methods)}]")
print()

# Test 4: Check auth function
print("✓ Test 4: Auth function check...")
try:
    from ReDNACoreDemo.core.graph.debug_api import verify_debug_auth
    print("  ✓ verify_debug_auth function exists\n")
except ImportError:
    print("  ✗ verify_debug_auth function not found\n")

# Summary
print("=" * 60)
print("SUMMARY")
print("=" * 60)
if DEBUG_ROUTES_ENABLED and not DEBUG_TOKEN:
    print("⚠ WARNING: Debug routes enabled with NO auth token")
    print("   This is OK for development but NOT safe for production")
    print("   Set X_REDNA_DEBUG_TOKEN in .env for production")
elif DEBUG_ROUTES_ENABLED and DEBUG_TOKEN:
    print("✓ Debug routes enabled WITH auth token (production-safe)")
elif not DEBUG_ROUTES_ENABLED:
    print("✓ Debug routes DISABLED (production lockdown mode)")
print("=" * 60)
