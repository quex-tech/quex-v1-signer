"""Operator tooling; not shipped in the TEE image (it copies quex_backend only)."""

import atexit
import os
import shutil
import tempfile
from pathlib import Path

# quex_backend provisions a signer key at import; point it at a private throwaway one.
_key_dir = tempfile.mkdtemp(prefix="quex-tools-")
os.environ["ETH_SIGNER_KEY_FILE"] = str(Path(_key_dir) / "sk.txt")
# Blank blocks both env and .env sources: a real TD key must never land on this host.
os.environ["TD_SECRET_KEY"] = ""
# DEBUG only stubs /quote (never called by the tools) so pyquex_tdx is not required.
os.environ["DEBUG"] = "1"
atexit.register(shutil.rmtree, _key_dir, ignore_errors=True)
