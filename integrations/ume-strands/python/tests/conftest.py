"""Keep the test suite from sending usage telemetry to the live PostHog project.

Set before ``ume`` is imported: the SDK reads ``UME_TELEMETRY`` once, at import.
"""

from __future__ import annotations

import os

os.environ["UME_TELEMETRY"] = "false"
