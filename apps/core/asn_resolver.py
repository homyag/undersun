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

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.records: List[ASNRecord] = []
        if db_path and db_path.exists():
            self._load()

    def _load(self) -> None:
        records: List[ASNRecord] = []
        with self.db_path.open('r', encoding='utf-8', errors='ignore') as fh:
            for line in fh:
                if not line or line.startswith('#'):
                    continue
                parts = line.strip().split('\t')
                if len(parts) < 7:
                    continue
                start_ip, end_ip, asn, _cc, _registry, _allocated, org = parts[:7]
                try:
                    start_int = int(start_ip)
                    end_int = int(end_ip)
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


def get_resolver(db_path: Path) -> ASNResolver:
    global _resolver
    if _resolver is None or (_resolver and _resolver.db_path != db_path):
        _resolver = ASNResolver(db_path)
    return _resolver
