"""Utility for copying suspicious nginx access-log entries into bad_requests.log."""

from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path
from typing import Iterable, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parents[1]

NGINX_LOG_PATTERN = re.compile(
    r'(?P<ip>\S+)\s+\S+\s+\S+\s+\[(?P<time>[^\]]+)]\s+"(?P<request>[^"]*)"\s+'
    r'(?P<status>\d{3})\s+(?P<size>\S+)\s+"(?P<referer>[^"]*)"\s+"(?P<ua>[^"]*)"'
)

SUSPICIOUS_PATTERNS: Tuple[Tuple[re.Pattern[str], str], ...] = (
    (re.compile(r'/administrator'), 'administrator-probe'),
    (re.compile(r'/wp-(?:admin|login\.php|content|includes)'), 'wordpress-probe'),
    (re.compile(r'/wp-login\.php'), 'wordpress-login'),
    (re.compile(r'/phpmyadmin'), 'phpmyadmin-probe'),
    (re.compile(r'/adminer'), 'adminer-probe'),
    (re.compile(r'/manager/html'), 'manager-html-probe'),
    (re.compile(r'/vendor/phpunit'), 'phpunit-probe'),
    (re.compile(r'/\.(?:git|env)'), 'secrets-probe'),
    (re.compile(r'/cgi-bin'), 'cgi-bin-probe'),
    (re.compile(r'/hnap1', re.IGNORECASE), 'hnap1-probe'),
    (re.compile(r'/rdweb', re.IGNORECASE), 'rdweb-probe'),
    (re.compile(r'/\+csc?oe\+', re.IGNORECASE), 'cisco-vpn-probe'),
    (re.compile(r'/remote/login'), 'remote-login-probe'),
    (re.compile(r'/actuator'), 'spring-actuator-probe'),
    (re.compile(r'/nodeinfo'), 'nodeinfo-probe'),
    (re.compile(r'/geoserver'), 'geoserver-probe'),
    (re.compile(r'/aws'), 'aws-config-probe'),
)

SUSPICIOUS_METHODS = {
    'trace', 'delete', 'propfind', 'options', 'connect', 'pri', 'ssh-2.0', 'mglndd', 'profind'
}

SUSPICIOUS_STATUSES = {'444', '400', '401', '405'}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Ingest suspicious nginx access logs.')
    parser.add_argument(
        '--access-log',
        default='/var/log/nginx/access.log',
        help='Path to nginx access.log (default: /var/log/nginx/access.log)',
    )
    parser.add_argument(
        '--state-file',
        default=str(BASE_DIR / 'logs' / '.nginx_bad_requests.offset'),
        help='File to store processed byte offset (default: logs/.nginx_bad_requests.offset)',
    )
    parser.add_argument(
        '--output-log',
        default=str(BASE_DIR / 'logs' / 'bad_requests.log'),
        help='Destination log (default: logs/bad_requests.log)',
    )
    return parser.parse_args()


def configure_logger(output_path: Path) -> logging.Logger:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(output_path)
    formatter = logging.Formatter(
        '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
        style='{'
    )
    handler.setFormatter(formatter)
    logger = logging.getLogger('bad_requests_ingest')
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def load_offset(state_path: Path) -> int:
    try:
        return int(state_path.read_text().strip())
    except Exception:
        return 0


def save_offset(state_path: Path, offset: int) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(str(offset))


def read_new_lines(access_path: Path, offset: int) -> Tuple[Iterable[str], int]:
    file_size = access_path.stat().st_size
    if offset > file_size:
        offset = 0

    with access_path.open('r', encoding='utf-8', errors='ignore') as fh:
        fh.seek(offset)
        lines = fh.readlines()
        new_offset = fh.tell()

    return lines, new_offset


def parse_line(line: str) -> Optional[dict]:
    match = NGINX_LOG_PATTERN.match(line)
    if not match:
        return None
    data = match.groupdict()
    request = data.get('request', '')
    parts = request.split()
    if len(parts) >= 2:
        data['method'] = parts[0]
        data['path'] = parts[1]
    else:
        data['method'] = request or '-'
        data['path'] = '-'
    return data


def is_suspicious(entry: dict) -> Tuple[bool, str]:
    method = entry.get('method', '').lower()
    path = (entry.get('path') or '').lower()
    status = entry.get('status', '')

    for pattern, reason in SUSPICIOUS_PATTERNS:
        if pattern.search(path):
            return True, reason

    if method in SUSPICIOUS_METHODS:
        return True, f'method-{method}'

    if status in SUSPICIOUS_STATUSES and not path.startswith(('/ru/property', '/en/property', '/th/property')):
        return True, f'status-{status}'

    return False, ''


def sanitize(value: str) -> str:
    return (value or '-').replace('"', '')


def ingest(access_path: Path, state_path: Path, logger: logging.Logger) -> int:
    offset = load_offset(state_path)
    lines, new_offset = read_new_lines(access_path, offset)
    ingested = 0

    for line in lines:
        entry = parse_line(line)
        if not entry:
            continue
        suspicious, reason = is_suspicious(entry)
        if not suspicious:
            continue

        logger.warning(
            'source=nginx reason=%s method=%s path=%s status=%s ip=%s ua="%s" referer="%s" time="%s"',
            reason or 'unknown',
            sanitize(entry.get('method', '-')),
            sanitize(entry.get('path', '-')),
            entry.get('status', '-'),
            entry.get('ip', '-'),
            sanitize(entry.get('ua', '-')),
            sanitize(entry.get('referer', '-')),
            entry.get('time', '-'),
        )
        ingested += 1

    save_offset(state_path, new_offset)
    return ingested


def main() -> None:
    args = parse_args()
    logger = configure_logger(Path(args.output_log))
    access_path = Path(args.access_log)
    state_path = Path(args.state_file)

    if not access_path.exists():
        raise SystemExit(f'access log not found: {access_path}')

    ingested = ingest(access_path, state_path, logger)
    print(f'Ingested {ingested} suspicious entries from {access_path}')


if __name__ == '__main__':
    main()
