#!/usr/bin/env python3
"""
Print wiki index status: path, chunk count, embedding dim, build timestamp.
Robust if manifest missing.
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from jarvis.code_rag.index import DEFAULT_INDEX_DIR, load_index, _load_manifest

def main():
    index_dir = Path(os.getenv("CODE_RAG_INDEX_DIR") or DEFAULT_INDEX_DIR)
    print(f"Index path: {index_dir}")

    loaded = load_index(index_dir=index_dir)
    if not loaded:
        print("Index not found or invalid.")
        return

    idx, chunks = loaded
    print(f"Chunk count: {len(chunks)}")
    print(f"Embedding dim: {idx.d}")

    manifest = _load_manifest(index_dir)
    if manifest and "build_timestamp" in manifest:
        print(f"Build timestamp: {manifest['build_timestamp']}")
    else:
        print("Build timestamp: N/A")

if __name__ == "__main__":
    main()