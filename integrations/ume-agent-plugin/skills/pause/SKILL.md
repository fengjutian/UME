---
name: pause
description: Pause UME memory capture on this machine. Use when the user wants to stop memories being recorded, for example for private work or experiments.
---

# Pause memory capture

To pause (hooks stop capturing and sending session content; a minimal
telemetry ping still fires at session start, under your UME account email,
unless `UME_TELEMETRY=false`):

```bash
python3 "${PLUGIN_ROOT}/core/memory_cli.py" --harness "coding-agent"  pause
```

Confirm the new state back to the user, and remind them that already-created
memories still exist and remain searchable. Pending unsent packets are held
while paused, not expired, and are delivered after resuming. To turn capture
back on, use `/ume:resume`.
