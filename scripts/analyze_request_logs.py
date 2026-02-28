"""Анализ RequestLog за текущие сутки.

Скрипт предназначен для запуска на продакшене через `python manage.py shell` или
как отдельный Django-скрипт (`python scripts/analyze_request_logs.py`). Он выводит
топ IP за сегодняшний день, ассоциации ASN, наиболее частые пути и user-agent’ы.

Пример запуска:

    python scripts/analyze_request_logs.py

"""

from __future__ import annotations

import os
import sys
from datetime import date

from django.utils import timezone
from django.db.models import Count


def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

    import django  # noqa: WPS433 (import inside function to avoid configuring before sys.path)

    django.setup()

    from apps.core.models import RequestLog  # pylint: disable=import-error

    tz_now = timezone.now()
    today_start = tz_now.replace(hour=0, minute=0, second=0, microsecond=0)

    top_ips = (
        RequestLog.objects
        .filter(created_at__gte=today_start)
        .values('client_ip', 'asn', 'asn_organization')
        .annotate(hit_count=Count('id'))
        .order_by('-hit_count')[:20]
    )

    detailed = []
    for entry in top_ips:
        ip = entry['client_ip']
        details = {
            'client_ip': ip,
            'asn': entry.get('asn') or '-',
            'asn_org': entry.get('asn_organization') or '-',
            'hit_count': entry['hit_count'],
            'top_paths': list(
                RequestLog.objects
                .filter(client_ip=ip, created_at__gte=today_start)
                .values('path')
                .annotate(cnt=Count('id'))
                .order_by('-cnt')[:3]
            ),
            'top_uas': list(
                RequestLog.objects
                .filter(client_ip=ip, created_at__gte=today_start)
                .values('user_agent')
                .annotate(cnt=Count('id'))
                .order_by('-cnt')[:2]
            ),
            'actions': list(
                RequestLog.objects
                .filter(client_ip=ip, created_at__gte=today_start)
                .values('action')
                .annotate(cnt=Count('id'))
                .order_by('-cnt')
            ),
        }
        detailed.append(details)

    print(f"=== RequestLog summary for {date.today()} ===")
    if not detailed:
        print('Нет записей за сегодня.')
        return

    for entry in detailed:
        print('-' * 80)
        print(
            f"IP: {entry['client_ip']}  hits={entry['hit_count']}  "
            f"ASN={entry['asn']}  Org={entry['asn_org']}"
        )
        print('  Actions:', ', '.join(f"{a['action']}={a['cnt']}" for a in entry['actions']))
        print('  User-Agents:')
        for ua in entry['top_uas']:
            agent = ua['user_agent'] or '-'
            print(f"    {ua['cnt']:>4} × {agent[:120]}")
        print('  Paths:')
        for path in entry['top_paths']:
            print(f"    {path['cnt']:>4} × {path['path']}")


if __name__ == '__main__':
    main()
