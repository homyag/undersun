"""Download iptoasn TSV and store locally for ASN lookups."""
from __future__ import annotations

import argparse
import gzip
import sys
from pathlib import Path

import requests

DEFAULT_URL = "https://iptoasn.com/data/ip2asn-combined.tsv.gz"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "tmp" / "ip2asn.tsv"


def download(url: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, timeout=120)
    response.raise_for_status()

    data = response.content
    if url.endswith('.gz'):
        data = gzip.decompress(data)

    output.write_bytes(data)
    print(f"Saved {len(data)} bytes to {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download iptoasn TSV database")
    parser.add_argument('--url', default=DEFAULT_URL, help='Source URL (default: %(default)s)')
    parser.add_argument('--output', default=str(DEFAULT_OUTPUT), help='Destination file path')
    args = parser.parse_args()

    output_path = Path(args.output)
    try:
        download(args.url, output_path)
    except Exception as exc:  # pragma: no cover
        print(f"Failed to download ASN database: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
