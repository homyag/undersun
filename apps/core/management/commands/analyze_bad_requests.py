from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
import re

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

LOG_LINE_RE = re.compile(
    r"^(?P<level>\w+)\s+(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<time>\d{2}:\d{2}:\d{2}),(?P<millis>\d{3})\s+(?P<module>\w+)\s+\d+\s+\d+\s+(?P<message>.*)$"
)
PATH_RE = re.compile(r"path=([^ ]+)")
IP_RE = re.compile(r"ip=([^ ]+)")
UA_RE = re.compile(r'ua="([^"]*)"')


class Command(BaseCommand):
    help = "Analyze logs/bad_requests.log and output summary statistics"

    def add_arguments(self, parser):
        parser.add_argument(
            '--log-path',
            default='logs/bad_requests.log',
            help='Path to bad_requests.log (default: logs/bad_requests.log)',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='How many days back to analyze (default: 7)',
        )
        parser.add_argument(
            '--top',
            type=int,
            default=10,
            help='How many top IPs/paths to show (default: 10)',
        )

    def handle(self, *args, **options):
        log_path = Path(options['log_path'])
        days = options['days']
        top = options['top']

        if not log_path.exists():
            raise CommandError(f'Log file not found: {log_path}')

        cutoff_dt = timezone.now() - timedelta(days=days)
        if timezone.is_aware(cutoff_dt):
            cutoff_dt_local = timezone.localtime(cutoff_dt)
        else:
            cutoff_dt_local = cutoff_dt
        cutoff_naive = cutoff_dt_local.replace(tzinfo=None)

        totals = Counter()
        daily_counts = Counter()
        category_ip = defaultdict(Counter)
        category_path = defaultdict(Counter)
        category_ua = defaultdict(Counter)
        googlebot_hits = 0
        total_lines = 0
        parsed_lines = 0
        skipped_old = 0
        parse_errors = 0

        with log_path.open('r', encoding='utf-8', errors='ignore') as fp:
            for line in fp:
                total_lines += 1
                line = line.strip()
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

                if 'forbidden-path' in message:
                    category = 'forbidden-path'
                elif 'bad-inquiry-invalid-method' in message:
                    category = 'bad-inquiry-invalid-method'
                else:
                    category = 'inquiry'

                totals[category] += 1
                daily_counts[match.group('date')] += 1

                ip_match = IP_RE.search(message)
                path_match = PATH_RE.search(message)
                ua_match = UA_RE.search(message)

                ip = ip_match.group(1) if ip_match else 'unknown'
                if ip.startswith('66.249.') or (ua_match and 'googlebot' in ua_match.group(1).lower()):
                    googlebot_hits += 1

                category_ip[category][ip] += 1

                if path_match:
                    category_path[category][path_match.group(1)] += 1

                if ua_match:
                    category_ua[category][ua_match.group(1)] += 1

        if not parsed_lines:
            self.stdout.write(self.style.WARNING('No log entries within the requested period'))
            return

        self.stdout.write(self.style.SUCCESS(f'Analyzed log: {log_path}'))
        self.stdout.write(f'Lines processed: {total_lines}, parsed: {parsed_lines}, older than {days}d: {skipped_old}, parse errors: {parse_errors}')
        self.stdout.write(f'Period start: {cutoff_dt_local.strftime("%Y-%m-%d %H:%M:%S %Z")}')
        google_share = (googlebot_hits / parsed_lines) * 100 if parsed_lines else 0
        self.stdout.write(f'Googlebot hits (IP 66.249.* or UA contains Googlebot): {googlebot_hits} ({google_share:.1f}%)')
        self.stdout.write('Totals by category:')
        for category, count in totals.items():
            self.stdout.write(f'  {category}: {count}')

        self.stdout.write('\nDaily counts:')
        for date_str in sorted(daily_counts.keys()):
            self.stdout.write(f'  {date_str}: {daily_counts[date_str]}')

        self._print_top('IPs', category_ip, top)
        self._print_top('Paths', category_path, top)
        self._print_top('User-Agents', category_ua, min(top, 5))

    def _print_top(self, label, data, top):
        self.stdout.write(f'\nTop {label}:')
        for category, counter in data.items():
            self.stdout.write(f'  [{category}]')
            for value, count in counter.most_common(top):
                self.stdout.write(f'    {value}: {count}')
            if not counter:
                self.stdout.write('    (no data)')
