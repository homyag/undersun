import subprocess
import re
from collections import Counter
from datetime import datetime, timedelta, timezone as dt_timezone
from ipaddress import ip_address
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

LOG_LINE_RE = re.compile(
    r"^(?P<level>\w+)\s+(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<time>\d{2}:\d{2}:\d{2}),(?P<millis>\d{3})\s+(?P<module>\w+)\s+\d+\s+\d+\s+(?P<message>.*)$"
)
IP_RE = re.compile(r"ip=([^ ]+)")
CATEGORY_MARKERS = {
    'bad-inquiry-invalid-method': 'bad-inquiry-invalid-method',
    'forbidden-path': 'forbidden-path',
}


class Command(BaseCommand):
    help = "Ban suspicious IPs from bad_requests.log using fail2ban"

    def add_arguments(self, parser):
        parser.add_argument('--log-path', default='logs/bad_requests.log', help='Path to bad_requests.log')
        parser.add_argument('--days', type=int, default=30, help='How many days back to analyze (default: 30)')
        parser.add_argument('--min-count', type=int, default=3, help='Minimum events per IP to consider suspicious (default: 3)')
        parser.add_argument('--ban', action='store_true', help='Ban the suspicious IPs via fail2ban')
        parser.add_argument('--jail', default='undersun-badrequests', help='Fail2ban jail name (default: undersun-badrequests)')
        parser.add_argument('--email', default='', help='Comma-separated list of recipients for summary email (optional)')
        parser.add_argument('--subject', default='Undersun bad requests ban report', help='Subject for summary email')

    def handle(self, *args, **options):
        log_path = Path(options['log_path'])
        if not log_path.exists():
            raise CommandError(f'Log file not found: {log_path}')

        days = options['days']
        min_count = options['min_count']
        cutoff_dt = timezone.now() - timedelta(days=days)
        if timezone.is_aware(cutoff_dt):
            cutoff_naive = cutoff_dt.astimezone(dt_timezone.utc).replace(tzinfo=None)
        else:
            cutoff_naive = cutoff_dt

        counter = Counter()
        total_lines = 0
        parsed_lines = 0
        skipped_old = 0
        parse_errors = 0
        with log_path.open('r', encoding='utf-8', errors='ignore') as fp:
            for raw_line in fp:
                total_lines += 1
                line = raw_line.strip()
                if not line:
                    continue
                match = LOG_LINE_RE.match(line)
                if not match:
                    parse_errors += 1
                    continue
                timestamp_str = f"{match.group('date')} {match.group('time')}"
                try:
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    parse_errors += 1
                    continue
                if timestamp < cutoff_naive:
                    skipped_old += 1
                    continue
                parsed_lines += 1
                message = match.group('message')
                if not any(marker in message for marker in CATEGORY_MARKERS):
                    continue
                ip_match = IP_RE.search(message)
                if not ip_match:
                    continue
                raw_ip = ip_match.group(1)
                try:
                    parsed_ip = ip_address(raw_ip)
                except ValueError:
                    continue

                if parsed_ip.is_private or parsed_ip.is_loopback or parsed_ip.is_reserved:
                    continue

                counter[str(parsed_ip)] += 1

        suspects = {ip: count for ip, count in counter.items() if count >= min_count}
        if not suspects:
            self.stdout.write(self.style.SUCCESS('No IPs exceeded the threshold.'))
            return

        sorted_suspects = sorted(suspects.items(), key=lambda item: item[1], reverse=True)
        self.stdout.write(self.style.WARNING(f'Found {len(sorted_suspects)} IP(s) with >= {min_count} events in the last {days} day(s):'))
        for ip, count in sorted_suspects:
            self.stdout.write(f'  {ip}: {count}')

        banned_ips = []
        if options['ban']:
            for ip, count in sorted_suspects:
                result = subprocess.run(
                    ['fail2ban-client', 'set', options['jail'], 'banip', ip],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    self.stdout.write(self.style.SUCCESS(f'Banned {ip} ({count} hits)'))
                    banned_ips.append((ip, count))
                else:
                    self.stdout.write(self.style.ERROR(f'Failed to ban {ip}: {result.stderr.strip()}'))

        email_recipients = [addr.strip() for addr in options['email'].split(',') if addr.strip()]
        if email_recipients:
            subject = options['subject']
            body_lines = [
                f'Period: last {days} day(s), threshold: {min_count}',
                f'Total log lines processed: {total_lines}, parsed: {parsed_lines}, older than range: {skipped_old}, parse errors: {parse_errors}',
                '\nSuspicious IPs:',
            ]
            for ip, count in sorted_suspects:
                status = 'BANNED' if any(ip == banned_ip for banned_ip, _ in banned_ips) else 'PENDING'
                body_lines.append(f'- {ip}: {count} ({status})')
            body = '\n'.join(body_lines)
            try:
                subprocess.run(
                    ['mail', '-s', subject, *email_recipients],
                    input=body,
                    text=True,
                    check=True,
                )
                self.stdout.write(self.style.SUCCESS(f'Summary email sent to: {", ".join(email_recipients)}'))
            except FileNotFoundError:
                self.stdout.write(self.style.ERROR('mail command not found; unable to send email.'))
            except subprocess.CalledProcessError as exc:
                self.stdout.write(self.style.ERROR(f'Failed to send email: {exc}'))
