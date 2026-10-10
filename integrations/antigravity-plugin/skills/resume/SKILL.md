---
name: resume
description: Resume UME memory capture after it was paused with /ume:pause.
disable-model-invocation: true
---

# Resume memory capture

Resume memory capture for this machine.

Run:

```bash
python3 "${ANTIGRAVITY_PLUGIN_ROOT}/core/memory_cli.py" --harness "antigravity"  resume
```

Confirm to the user that capture is active again. New sessions record evidence and
create memories as normal; nothing that happened while paused is retroactively
captured.
