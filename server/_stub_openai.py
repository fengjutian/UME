"""Minimal OpenAI-compatible embeddings stub for local end-to-end verification.

The F-08 fix moved the UME memory path past the SDK's entity-id guard, but the
run after the fix still returned 500 — this time from `openai.AuthenticationError`,
because the only key available here is a placeholder. That is an environment
limitation, not a code one, and it also means "the guard is passed" is the
strongest claim a log trace can support.

This stub closes that gap: it answers `POST /v1/embeddings` with a deterministic
1536-dim vector so the real `ume.Memory.add` / `search` can complete against the
real pgvector store, with no network and no credential.

Deterministic on purpose: the same text always maps to the same vector, so a
search for text that was just written can actually find it. A random vector
would make the end-to-end check look flaky for no reason.

Run:  python server/_stub_openai.py
Then: OPENAI_BASE_URL=http://127.0.0.1:8891/v1 OPENAI_API_KEY=stub
"""

import hashlib
import json
import math
from http.server import BaseHTTPRequestHandler, HTTPServer

DIMS = 1536


def _vector_for(text: str) -> list[float]:
    """Hash the text into a stable unit vector of the model's dimension."""
    seed = hashlib.sha256(text.encode("utf-8")).digest()
    raw = [seed[i % len(seed)] / 255.0 + 1e-3 for i in range(DIMS)]
    norm = math.sqrt(sum(value * value for value in raw)) or 1.0
    return [value / norm for value in raw]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):  # keep the server's output readable
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")

        if not self.path.endswith("/embeddings"):
            self.send_error(404, "stub only implements /embeddings")
            return

        payload = body.get("input")
        if isinstance(payload, str):
            inputs = [payload]
        elif isinstance(payload, list):
            inputs = [item if isinstance(item, str) else json.dumps(item, sort_keys=True) for item in payload]
        else:
            inputs = [""]

        data = {
            "object": "list",
            "model": body.get("model", "text-embedding-3-small"),
            "data": [
                {"object": "embedding", "index": index, "embedding": _vector_for(text)}
                for index, text in enumerate(inputs)
            ],
            "usage": {"prompt_tokens": 0, "total_tokens": 0},
        }

        encoded = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 8891), Handler).serve_forever()