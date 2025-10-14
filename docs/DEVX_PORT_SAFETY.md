# DevX Port Safety Protocol

**System**: DevX Port Detection & Auto-Increment
**Version**: 1.0.0
**Critical**: Service Independence Guarantee

---

## Overview

DevX implements strict port safety protocols to ensure zero interference with existing ReDNA services. This document details the port detection mechanism and fallback strategies.

---

## Port Reservations

### Primary Ports

| Service | Primary Port | Type | Owner |
|---------|--------------|------|-------|
| Core API | 8015 | **PROTECTED** | ReDNA Core |
| UCNRR | 8011 | **PROTECTED** | UCNRR Service |
| React Head Coach | 3001 | **PROTECTED** | React HC |
| Control Panel++ | 8501 | **PROTECTED** | CP++ |
| **DevX Backend** | **8100** | **ISOLATED** | DevX |
| **DevX Frontend** | **3100** | **ISOLATED** | DevX |

### Fallback Ranges

**DevX Backend**: 8100-8109 (10 attempts)
**DevX Frontend**: 3100-3109 (10 attempts)

---

## Port Detection Algorithm

### Backend Implementation

Location: `ReDNACoreDemo/devx/backend/config.py`

```python
import socket

def find_available_port(start_port: int, max_attempts: int = 10) -> int:
    """
    Find an available port starting from start_port.

    Algorithm:
    1. Try to bind to start_port
    2. If successful, return port
    3. If OSError (port in use), try start_port + 1
    4. Repeat up to max_attempts
    5. Raise RuntimeError if all attempts fail

    Args:
        start_port: Starting port number
        max_attempts: Maximum number of ports to try

    Returns:
        Available port number

    Raises:
        RuntimeError: If no available port found in range
    """
    for offset in range(max_attempts):
        port = start_port + offset
        try:
            # Try to bind to the port
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", port))
            sock.close()
            return port
        except OSError:
            # Port in use, try next
            continue

    # All attempts failed
    raise RuntimeError(
        f"Could not find available port in range {start_port}-{start_port + max_attempts - 1}"
    )
```

### Startup Script Implementation

Location: `scripts/start_devx.sh`

```bash
# Check if port is available
if lsof -ti:8100 > /dev/null 2>&1; then
    echo "⚠️  Port 8100 in use, backend will auto-increment"
fi

# Start backend (will auto-detect available port)
python3 ReDNACoreDemo/devx/backend/run_devx.py
```

---

## Port Logging

### Startup Log

Location: `ReDNACoreDemo/devx/logs/devx_start.log`

**Format**:
```
backend_port=8100
backend_host=127.0.0.1
frontend_port=3100
```

**Usage**:
- Read by CP++ to determine DevX URL
- Used for health checks
- Debugging port conflicts

**Example**:
```bash
# Read backend port
BACKEND_PORT=$(grep backend_port devx/logs/devx_start.log | cut -d'=' -f2)

# Test health
curl http://127.0.0.1:$BACKEND_PORT/health
```

---

## Safety Guarantees

### What DevX Will Do

✅ **Detect port availability** before binding
✅ **Auto-increment** to next available port (8100→8101→8102...)
✅ **Log final ports** to `devx_start.log`
✅ **Fail gracefully** if no ports available (error message, no process kill)

### What DevX Will NOT Do

❌ **Terminate processes** on ports 8015, 8011, 3001, 8501
❌ **Modify configs** of Core, UCNRR, React HC, or CP++
❌ **Share state** with other services
❌ **Interfere with** existing network connections

---

## Port Conflict Scenarios

### Scenario 1: Clean Start

**State**: No services running on 8100 or 3100

**Result**:
```
Backend: 8100 ✅
Frontend: 3100 ✅
```

**Logs**:
```
devx_start.log:
backend_port=8100
frontend_port=3100
```

---

### Scenario 2: Backend Port Conflict

**State**: Another process on 8100

**Example**:
```bash
# Simulate conflict
nc -l 8100 &
```

**Result**:
```
Backend: 8101 ✅ (auto-incremented)
Frontend: 3100 ✅
```

**Logs**:
```
backend.log:
2025-10-08 10:30:15 - INFO - Port 8100 unavailable, trying 8101
2025-10-08 10:30:15 - INFO - Starting DevX backend on 127.0.0.1:8101

devx_start.log:
backend_port=8101
frontend_port=3100
```

---

### Scenario 3: Multiple DevX Instances

**State**: DevX already running, user starts second instance

**Result**:
```
Instance 1:
  Backend: 8100 ✅
  Frontend: 3100 ✅

Instance 2:
  Backend: 8101 ✅ (auto-incremented)
  Frontend: 3101 ✅ (auto-incremented)
```

**Use Case**: Running multiple development branches simultaneously

---

### Scenario 4: All Ports Exhausted

**State**: Ports 8100-8109 all in use

**Example**:
```bash
# Occupy all ports
for port in {8100..8109}; do
    nc -l $port &
done
```

**Result**:
```
Backend: FAILED ❌
Error: RuntimeError: Could not find available port in range 8100-8109
```

**Resolution**:
```bash
# Kill unused processes
lsof -ti:8100,8101,8102 | xargs kill

# Or increase max_attempts in config.py
find_available_port(8100, max_attempts=20)  # Try 8100-8119
```

---

## Health Check Protocol

### Backend Health Endpoint

**URL**: `http://127.0.0.1:<port>/health`

**Response**:
```json
{
  "status": "healthy",
  "service": "devx-backend",
  "version": "1.0.0"
}
```

**Usage**:
```bash
# Check if backend is running
curl -f http://127.0.0.1:8100/health && echo "✅ Backend healthy" || echo "❌ Backend down"
```

### Frontend Health Check

**URL**: `http://127.0.0.1:<port>/`

**Response**: HTML page (200 OK)

**Usage**:
```bash
# Check if frontend is running
curl -f http://127.0.0.1:3100/ > /dev/null 2>&1 && echo "✅ Frontend healthy" || echo "❌ Frontend down"
```

---

## Monitoring Script

### Check Service Independence

**Script**: `scripts/check_devx_independence.sh`

```bash
#!/bin/bash
# Verify DevX does not affect other services

set -e

echo "🔍 Checking service independence..."

# Check Core API
if ! curl -sf http://127.0.0.1:8015/health > /dev/null; then
    echo "❌ Core API affected!"
    exit 1
fi

# Check UCNRR
if ! curl -sf http://127.0.0.1:8011/health > /dev/null; then
    echo "❌ UCNRR affected!"
    exit 1
fi

# Check DevX
if ! curl -sf http://127.0.0.1:8100/health > /dev/null; then
    echo "❌ DevX not running!"
    exit 1
fi

echo "✅ All services independent and healthy"
```

**Usage**:
```bash
# Run after starting DevX
./scripts/check_devx_independence.sh
```

---

## Port Release Protocol

### Clean Shutdown

**Script**: `scripts/stop_devx.sh`

```bash
#!/bin/bash
# Stop DevX cleanly

# Read PID files
BACKEND_PID=$(cat devx/logs/backend.pid 2>/dev/null || echo "")
FRONTEND_PID=$(cat devx/logs/frontend.pid 2>/dev/null || echo "")

# Stop backend
if [ -n "$BACKEND_PID" ]; then
    kill $BACKEND_PID
    rm devx/logs/backend.pid
fi

# Stop frontend
if [ -n "$FRONTEND_PID" ]; then
    kill $FRONTEND_PID
    rm devx/logs/frontend.pid
fi

# Fallback: kill by port
lsof -ti:8100,8101,8102 | xargs kill 2>/dev/null || true
lsof -ti:3100,3101,3102 | xargs kill 2>/dev/null || true

echo "✅ DevX stopped"
```

### Forceful Shutdown

```bash
# Kill all DevX processes by port range
for port in {8100..8109}; do
    lsof -ti:$port | xargs kill -9 2>/dev/null || true
done

for port in {3100..3109}; do
    lsof -ti:$port | xargs kill -9 2>/dev/null || true
done
```

---

## Testing

### Port Safety Test Suite

**Test 1: Clean Start**
```bash
./scripts/start_devx.sh
assert_port 8100
assert_port 3100
./scripts/stop_devx.sh
```

**Test 2: Port Conflict Handling**
```bash
# Occupy port 8100
nc -l 8100 &
NC_PID=$!

# Start DevX (should use 8101)
./scripts/start_devx.sh
assert_port 8101

# Cleanup
kill $NC_PID
./scripts/stop_devx.sh
```

**Test 3: Service Independence**
```bash
# Start all services
./scripts/start_all_services.sh

# Start DevX
./scripts/start_devx.sh

# Verify all services still healthy
./scripts/check_services.sh

# Stop DevX
./scripts/stop_devx.sh

# Verify other services unaffected
./scripts/check_services.sh
```

---

## Troubleshooting

### Problem: Port exhaustion

**Symptom**:
```
RuntimeError: Could not find available port in range 8100-8109
```

**Solution**:
```bash
# Check what's using ports
for port in {8100..8109}; do
    echo -n "Port $port: "
    lsof -ti:$port || echo "available"
done

# Kill unused processes
lsof -ti:8100 | xargs kill
```

### Problem: Stale PID files

**Symptom**:
```
Backend PID 12345 not found (process already dead)
```

**Solution**:
```bash
# Remove stale PID files
rm -f devx/logs/backend.pid devx/logs/frontend.pid

# Restart DevX
./scripts/start_devx.sh
```

### Problem: Port already in use after stop

**Symptom**:
```
OSError: [Errno 48] Address already in use
```

**Solution**:
```bash
# Wait for OS to release port (TIME_WAIT state)
sleep 5

# Or kill process forcefully
lsof -ti:8100 | xargs kill -9
```

---

## Best Practices

1. **Always use start/stop scripts** - Don't manually run processes
2. **Check logs after startup** - Verify correct ports in `devx_start.log`
3. **Monitor service health** - Run independence checks periodically
4. **Clean shutdown before restart** - Avoid orphaned processes
5. **Report port conflicts** - Document any unexpected behavior

---

**Last Updated**: 2025-10-08
**Version**: 1.0.0
**Critical**: Service Independence Guarantee
