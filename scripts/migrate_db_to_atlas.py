#!/usr/bin/env python3
"""One-shot migration: local Mongo (preview cluster) -> MongoDB Atlas.

Usage:
    SRC_MONGO_URL="mongodb://localhost:27017" \
    DST_MONGO_URL="mongodb+srv://USER:PASS@cluster0.xxxx.mongodb.net" \
    DB_NAME="hashcloud_db" \
    python3 /app/scripts/migrate_db_to_atlas.py

What it does:
  • Connects to source + destination clusters.
  • Walks every collection in DB_NAME on the source.
  • Skips system collections (system.*).
  • For each collection: copies in batches of 500 docs, upserting on `_id`.
  • Idempotent — re-running picks up new documents but never duplicates.
  • Prints a per-collection diff at the end so we can verify nothing was lost.

Why upsert (not insert_many): if the script is interrupted, the next run
resumes cleanly without primary-key conflicts.
"""
from __future__ import annotations
import os
import sys
import time
from pymongo import MongoClient, UpdateOne
from pymongo.errors import BulkWriteError

BATCH = 500


def main() -> int:
    src_url = os.environ.get("SRC_MONGO_URL")
    dst_url = os.environ.get("DST_MONGO_URL")
    db_name = os.environ.get("DB_NAME", "hashcloud_db")
    if not src_url or not dst_url:
        print("❌ SRC_MONGO_URL and DST_MONGO_URL must be set.", file=sys.stderr)
        return 2

    print(f"=== Migrating database '{db_name}' ===")
    print(f"  source:  {src_url.split('@')[-1].split('/')[0]}")
    print(f"  dest:    {dst_url.split('@')[-1].split('/')[0]}")
    print()

    src = MongoClient(src_url)[db_name]
    dst = MongoClient(dst_url)[db_name]

    src_cols = [c for c in src.list_collection_names() if not c.startswith("system.")]
    if not src_cols:
        print("⚠ no collections on source.")
        return 0
    print(f"  collections to migrate: {len(src_cols)}")

    totals = []
    for col in src_cols:
        s_col = src[col]
        d_col = dst[col]
        total = s_col.estimated_document_count()
        if total == 0:
            print(f"  • {col:<32} 0 docs (skip)")
            totals.append((col, 0, 0))
            continue

        copied = 0
        t0 = time.time()
        batch_ops: list[UpdateOne] = []
        for doc in s_col.find({}, batch_size=BATCH):
            batch_ops.append(UpdateOne({"_id": doc["_id"]}, {"$set": doc}, upsert=True))
            if len(batch_ops) >= BATCH:
                try:
                    d_col.bulk_write(batch_ops, ordered=False)
                except BulkWriteError as exc:
                    # Duplicate key on upsert can happen if another process is
                    # writing concurrently; we don't care.
                    print(f"    ⚠ {col} partial: {exc.details.get('writeErrors', [])[:2]}")
                copied += len(batch_ops)
                batch_ops.clear()
        if batch_ops:
            try:
                d_col.bulk_write(batch_ops, ordered=False)
            except BulkWriteError as exc:
                print(f"    ⚠ {col} partial: {exc.details.get('writeErrors', [])[:2]}")
            copied += len(batch_ops)

        dst_total = d_col.estimated_document_count()
        elapsed = time.time() - t0
        print(f"  • {col:<32} src={total:>6}  dst={dst_total:>6}  copied={copied:>6}  ({elapsed:.1f}s)")
        totals.append((col, total, dst_total))

    print()
    print("=== summary ===")
    missing = 0
    for col, src_n, dst_n in totals:
        delta = src_n - dst_n
        status = "✅" if delta <= 0 else f"❌ ({delta} missing)"
        print(f"  {col:<32} src={src_n:>6}  dst={dst_n:>6}  {status}")
        if delta > 0:
            missing += delta
    if missing:
        print(f"\n❌ {missing} documents missing total. Re-run to retry.")
        return 1
    print("\n✅ all collections copied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
