import json
from time import perf_counter

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.models import Count
from django.test import Client
from django.test.utils import CaptureQueriesContext

from apps.properties.models import Property


MAP_BOUNDS_CASES = {
    "island": "bounds_north=8.25&bounds_south=7.60&bounds_east=98.70&bounds_west=98.05",
    "west_coast": "bounds_north=8.15&bounds_south=7.75&bounds_east=98.45&bounds_west=98.20",
    "south": "bounds_north=7.90&bounds_south=7.60&bounds_east=98.50&bounds_west=98.20",
    "north": "bounds_north=8.25&bounds_south=7.95&bounds_east=98.60&bounds_west=98.20",
}


class Command(BaseCommand):
    help = "Measure the map JSON endpoint against repeatable Phuket map bounds."

    def add_arguments(self, parser):
        parser.add_argument(
            "--requests",
            type=int,
            default=30,
            help="Number of in-process requests per bounds case (default: 30).",
        )

    def handle(self, *args, **options):
        requests_per_case = options["requests"]
        if requests_per_case < 2:
            raise CommandError("--requests must be at least 2")

        properties = Property.objects.filter(
            is_active=True,
            status="available",
            latitude__isnull=False,
            longitude__isnull=False,
        )
        duplicate_groups = list(
            properties.values("latitude", "longitude")
            .annotate(count=Count("id"))
            .filter(count__gt=1)
        )

        client = Client()
        cases = {}
        for case_name, query_string in MAP_BOUNDS_CASES.items():
            timings_ms = []
            payload_sizes = []
            property_counts = []
            query_counts = []

            for _ in range(requests_per_case):
                started_at = perf_counter()
                with CaptureQueriesContext(connection) as queries:
                    response = client.get(
                        f"/ru/property/ajax/map/?{query_string}",
                        HTTP_HOST="localhost",
                    )
                timings_ms.append((perf_counter() - started_at) * 1000)

                payload = response.json()
                if response.status_code != 200 or not payload.get("success"):
                    raise CommandError(
                        f"{case_name} failed: HTTP {response.status_code}, payload={payload}"
                    )

                payload_sizes.append(len(response.content))
                property_counts.append(len(payload["properties"]))
                query_counts.append(len(queries))

            sorted_timings = sorted(timings_ms)
            p95_index = round((len(sorted_timings) - 1) * 0.95)
            cases[case_name] = {
                "requests": requests_per_case,
                "properties": property_counts[0],
                "payload_bytes": payload_sizes[0],
                "query_count": query_counts[0],
                "p50_ms": round(sorted_timings[len(sorted_timings) // 2], 2),
                "p95_ms": round(sorted_timings[p95_index], 2),
                "min_ms": round(min(sorted_timings), 2),
                "max_ms": round(max(sorted_timings), 2),
            }

        result = {
            "active_properties_with_coordinates": properties.count(),
            "duplicate_coordinate_groups": len(duplicate_groups),
            "properties_in_duplicate_coordinate_groups": sum(
                group["count"] for group in duplicate_groups
            ),
            "largest_duplicate_coordinate_group": max(
                (group["count"] for group in duplicate_groups), default=0
            ),
            "cases": cases,
        }
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
