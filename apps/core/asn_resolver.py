from __future__ import annotations

import bisect
import ipaddress
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class ASNRecord:
    start: int
    end: int
    asn: str
    organization: str


class ASNResolver:
    """Simple resolver built on top of iptoasn/db-ip TSV file."""

    def __init__(self, db_path: Optional[Path]) -> None:
        self.db_path = db_path
        self.records: List[ASNRecord] = []
        if db_path and db_path.exists():
            self._load()

    def _load(self) -> None:
        records: List[ASNRecord] = []
        if not self.db_path:
            return
        with self.db_path.open('r', encoding='utf-8', errors='ignore') as fh:
            for line in fh:
                if not line or line.startswith('#'):
                    continue
                parts = line.strip().split('\t')
                if len(parts) < 5:
                    continue
                start_ip, end_ip, asn, *_rest = parts
                org = _rest[-1] if _rest else ''
                try:
                    start_int = int(ipaddress.ip_address(start_ip))
                    end_int = int(ipaddress.ip_address(end_ip))
                except ValueError:
                    continue
                asn = asn.strip()
                org = org.strip()
                if not asn or asn == '0':
                    continue
                records.append(ASNRecord(start=start_int, end=end_int, asn=f'AS{asn}', organization=org))
        records.sort(key=lambda r: r.start)
        self.records = records

    def lookup(self, ip: str) -> Optional[ASNRecord]:
        if not self.records:
            return None
        try:
            ip_int = int(ipaddress.ip_address(ip))
        except ValueError:
            return None
        starts = [record.start for record in self.records]
        idx = bisect.bisect_right(starts, ip_int) - 1
        if 0 <= idx < len(self.records):
            record = self.records[idx]
            if record.start <= ip_int <= record.end:
                return record
        return None

_resolver: Optional[ASNResolver] = None
_resolver_mtime: Optional[float] = None


def get_resolver(db_path: Path) -> ASNResolver:
    global _resolver, _resolver_mtime
    target_path = Path(db_path) if db_path else None
    mtime = None
    if target_path and target_path.exists():
        try:
            mtime = target_path.stat().st_mtime
        except OSError:
            mtime = None

    needs_reload = False
    if _resolver is None:
        needs_reload = True
    elif target_path and _resolver.db_path != target_path:
        needs_reload = True
    elif mtime is not None and _resolver_mtime != mtime:
        needs_reload = True
    elif mtime is not None and not _resolver.records:
        needs_reload = True

    if needs_reload:
        _resolver = ASNResolver(target_path)
        _resolver_mtime = mtime

    return _resolver
