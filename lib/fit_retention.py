"""
fit_retention.py — еженедельный проход. FIT старше retention.json:fit_ttl_days → удалить.

Использование:
  python -m lib.fit_retention
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _now() -> datetime:
    return datetime.now(timezone.utc)


def run(fit_store_root: str | Path = "state/fit_store",
        config_path: str | Path = "state/fit_store/retention.json",
        decisions_root: str | Path = "state/../decisions") -> dict:
    fit_store_root = Path(fit_store_root)
    index_path = fit_store_root / "index.json"
    if not index_path.exists():
        return {"deleted": [], "kept": 0, "reason": "no index.json"}

    # TTL
    ttl_days = 14
    cfg = fit_store_root / "retention.json"
    if cfg.exists():
        ttl_days = json.loads(cfg.read_text(encoding="utf-8")).get("fit_ttl_days", 14)

    idx = json.loads(index_path.read_text(encoding="utf-8"))
    now = _now()
    keep, deleted = [], []
    for f in idx.get("fits", []):
        exp = datetime.fromisoformat(f["expires_at"])
        if exp <= now:
            p = fit_store_root.parent / f["path"]
            if p.exists():
                p.unlink()
            deleted.append({"id": f["id"], "path": str(p)})
        else:
            keep.append(f)

    idx["fits"] = keep
    index_path.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")

    # Audit
    decisions_path = Path(decisions_root) if decisions_root else Path("decisions")
    decisions_path.mkdir(parents=True, exist_ok=True)
    log = {
        "kind": "retention",
        "run_at": now.isoformat(timespec="seconds"),
        "ttl_days": ttl_days,
        "deleted_count": len(deleted),
        "kept_count": len(keep),
        "deleted": deleted,
        "bytes_freed_estimate": 0,  # Phase 1: skip real size
    }
    log_file = decisions_path / f"{now.date().isoformat()}-retention-XX-days.json"
    # Простой файл с датой
    log_file = decisions_path / f"{now.date().isoformat()}_02-00-00-retention.json"
    log_file.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"deleted": deleted, "kept": len(keep)}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))