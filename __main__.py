"""python -m lib.packs [--check] [pack ...]: list packs, or check a combination for alias conflicts."""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from lib.packs import Knowledge, _import, available  # noqa: E402

ap = argparse.ArgumentParser(description="List knowledge packs, or check a combination for alias conflicts.")
ap.add_argument("packs", nargs="*")
ap.add_argument("--check", action="store_true")
a = ap.parse_args()
if not a.packs:
    for n in available():
        mod = _import(n)
        ents = sum(len(v) for v in getattr(mod, "ENTITIES", {}).values())
        print(f"{n:12s} {ents:4d} entities {len(getattr(mod, 'IDEAS', [])):3d} themes  {getattr(mod, 'DESCRIPTION', '')}")
    sys.exit(0)
k = Knowledge(a.packs)
print(f"packs: {' -> '.join(k.packs)}; {len(k.entities)} entities, {len(k.ideas)} themes, "
      f"{len(k.origin_rules)} origin rules, {len(k.metadata)} metadata parsers")
if a.check:
    conflicts = k.alias_conflicts()
    for alias, a1, a2 in conflicts:
        print(f"  alias {alias!r}: {a1}  vs  {a2}")
    print(f"{len(conflicts)} alias conflicts")
