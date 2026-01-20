import os
import json
from pathlib import Path

from jarvis import memory


def rebuild_for_user(user_id: str) -> None:
    store = memory._get_store(user_id)
    if not os.path.exists(store.data_file):
        print(f"No memory JSON for {user_id}")
        return
    with open(store.data_file, "r", encoding="utf-8") as f:
        entries = json.load(f)
    # Force new index by clearing and rebuilding
    store.index = memory.faiss.IndexFlatL2(memory.DIM)
    store.memories = []
    for entry in entries:
        try:
            vec = memory._encode(entry)
            memory._ensure_index_dim(store, vec.size)
            store.index.add(vec.reshape(1, -1))
            store.memories.append(entry)
        except Exception as exc:
            print(f"Skip entry: {exc!r}")
    store.save()
    print(f"Rebuilt memory for {user_id}: {store.index.ntotal} entries")


def main():
    data_dir = Path(__file__).resolve().parents[1] / "data" / "memory"
    if not data_dir.exists():
        print("No memory directory")
        return
    for json_file in data_dir.glob("*.json"):
        user_id = json_file.stem
        rebuild_for_user(user_id)


if __name__ == "__main__":
    main()
