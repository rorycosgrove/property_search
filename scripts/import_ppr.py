"""Standalone PPR import script backed by worker task implementation."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from apps.worker.tasks import import_ppr


def main():
    years = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    print(f"Importing PPR data ({years} year(s))...")
    result = import_ppr(years=years)
    print(
        "Done. "
        f"new={result['new_records']} "
        f"duplicates={result['duplicates']} "
        f"skipped={result['skipped_invalid']} "
        f"failed={result['failed']}"
    )


if __name__ == "__main__":
    main()
