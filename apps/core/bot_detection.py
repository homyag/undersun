from __future__ import annotations

import ipaddress
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from django.conf import settings
from django.core.cache import cache

from apps.core.asn_resolver import get_resolver

logger = logging.getLogger(__name__)


@dataclass
class RuleMatch:
    key: str
    weight: int
    detail: Optional[str] = None


@dataclass
class DetectionResult:
    score: int
    action: str
    matched_rules: List[RuleMatch] = field(default_factory=list)
    notify_fail2ban: bool = False
    headers: Dict[str, str] = field(default_factory=dict)
    asn: Optional[str] = None
    asn_organization: Optional[str] = None


class BotDetectionService:
    """Calculate bot score for incoming requests based on heuristics."""

    def __init__(self) -> None:
        self._load_config()

    def _load_config(self) -> None:
        config = getattr(settings, 'BOT_PROTECTION', {})
        self.enabled = config.get('ENABLED', True)
        self.whitelist_ips = self._compile_networks(config.get('WHITELIST_IPS', []))
        self.whitelist_user_agents = self._compile_regex(config.get('WHITELIST_USER_AGENTS', []))
        self.blacklist_ips = self._compile_networks(config.get('BLACKLIST_IPS', []))
        self.suspicious_user_agents = self._compile_regex(config.get('SUSPICIOUS_USER_AGENTS', []))
        self.high_risk_user_agents = self._compile_regex(config.get('HIGH_RISK_USER_AGENT_PATTERNS', []))
        self.forbidden_paths = self._compile_regex(config.get('FORBIDDEN_PATH_PATTERNS', []))
        self.header_keys = config.get('HEADER_KEYS', [])
        rate_limit = config.get('RATE_LIMIT', {})
        self.rate_limit_window = rate_limit.get('WINDOW_SECONDS', 10)
        self.rate_limit_max = rate_limit.get('MAX_REQUESTS', 5)
        self.skip_path_prefixes = tuple(config.get('SKIP_PATH_PREFIXES', []))
        self.skip_methods = set(config.get('SKIP_METHODS', []))
        self.challenge_cookie = config.get('CHALLENGE_COOKIE', 'bot_challenge')
        self.thresholds = config.get('ACTION_THRESHOLDS', {})
        self.weights = config.get('RULE_WEIGHTS', {})
        asn_db = config.get('ASN_DB_PATH')
        self.asn_db_path = Path(asn_db) if asn_db else None
        self.asn_weights = config.get('ASN_WEIGHTS', {})
        self.asn_org_patterns = {k.lower(): v for k, v in config.get('ASN_ORG_PATTERNS', {}).items()}

    @staticmethod
    def _compile_networks(values: List[str]) -> List[ipaddress._BaseNetwork]:
        compiled = []
        for value in values:
            try:
                if '/' in value:
                    compiled.append(ipaddress.ip_network(value, strict=False))
                else:
                    compiled.append(ipaddress.ip_network(f'{value}/32', strict=False))
            except ValueError:
                logger.warning('Invalid IP/network in BOT_PROTECTION config: %s', value)
        return compiled

    @staticmethod
    def _compile_regex(patterns: List[str]) -> List[re.Pattern]:
        compiled = []
        for pattern in patterns:
            try:
                compiled.append(re.compile(pattern, re.IGNORECASE))
            except re.error:
                logger.warning('Invalid regex pattern in BOT_PROTECTION config: %s', pattern)
        return compiled

    def is_ip_whitelisted(self, client_ip: str) -> bool:
        return self._ip_matches(client_ip, self.whitelist_ips)

    def is_ip_blacklisted(self, client_ip: str) -> bool:
        return self._ip_matches(client_ip, self.blacklist_ips)

    @staticmethod
    def _ip_matches(ip_str: str, networks: List[ipaddress._BaseNetwork]) -> bool:
        if not ip_str:
            return False
        try:
            address = ipaddress.ip_address(ip_str)
        except ValueError:
            return False
        return any(address in network for network in networks)

    def is_user_agent_whitelisted(self, user_agent: str) -> bool:
        return any(pattern.search(user_agent or '') for pattern in self.whitelist_user_agents)

    def evaluate(self, request, client_ip: str, proxy_ip: Optional[str]) -> DetectionResult:
        if not self.enabled:
            return DetectionResult(score=0, action='allow')

        matches: List[RuleMatch] = []
        score = 0
        user_agent = (request.META.get('HTTP_USER_AGENT') or '')[:512]
        if request.method in self.skip_methods:
            return DetectionResult(score=0, action='allow')

        path = request.path or '/'
        referer = (request.META.get('HTTP_REFERER') or '')[:2048]

        if path.startswith(self.skip_path_prefixes):
            return DetectionResult(score=0, action='allow')

        # Rule: blacklist IP
        asn_value = None
        asn_org_value = None

        if self.is_ip_blacklisted(client_ip):
            score += self._add_match(matches, 'blacklist_ip')

        # Rule: forbidden paths
        if any(pattern.search(path) for pattern in self.forbidden_paths):
            score += self._add_match(matches, 'forbidden_path', path)

        # Rule: suspicious UA
        if user_agent == '-' or any(pattern.search(user_agent) for pattern in self.suspicious_user_agents):
            score += self._add_match(matches, 'suspicious_user_agent', user_agent or '-')
        elif any(pattern.search(user_agent) for pattern in self.high_risk_user_agents):
            score += self._add_match(matches, 'high_risk_user_agent', user_agent[:120])

        # Rule: missing headers typical for browsers
        headers = self._collect_headers(request)
        missing_accept_lang = not headers.get('HTTP_ACCEPT_LANGUAGE')
        missing_accept_encoding = not headers.get('HTTP_ACCEPT_ENCODING')
        missing_sec = not headers.get('HTTP_SEC_CH_UA') and not headers.get('HTTP_SEC_FETCH_SITE')

        if missing_accept_lang and missing_accept_encoding:
            rule_key = 'missing_headers_critical'
            if self.is_ip_whitelisted(client_ip):
                rule_key = 'missing_headers'
            score += self._add_match(matches, rule_key, 'accept')
        elif missing_accept_lang or missing_accept_encoding:
            score += self._add_match(matches, 'missing_headers', 'accept')
        elif missing_sec:
            score += self._add_match(matches, 'missing_headers', 'sec')

        # Rule: JS challenge presence
        cookie_token = request.COOKIES.get(self.challenge_cookie)
        field_token = request.POST.get('bot_challenge_token') or request.GET.get('bot_challenge_token')
        if not cookie_token:
            score += self._add_match(matches, 'js_challenge_missing', 'cookie')
        elif request.method in {'POST', 'PUT', 'PATCH'} and not field_token:
            if self._is_metrika_ping(path) and self._is_internal_referer(referer, request):
                pass
            else:
                score += self._add_match(matches, 'js_challenge_missing', 'field')
        elif field_token and field_token != cookie_token:
            score += self._add_match(matches, 'js_challenge_failed', 'mismatch')

        # Rule: no referer and requesting HTML (approx by missing file extension)
        no_referer_hit = False
        if not referer and not path.startswith(self.skip_path_prefixes) and '.' not in path.split('/')[-1]:
            no_referer_hit = True
            score += self._add_match(matches, 'no_referer')

        # Rule: suspicious methods HEAD/OPTIONS on HTML
        if request.method in {'HEAD', 'OPTIONS'} and not path.startswith(self.skip_path_prefixes):
            score += self._add_match(matches, 'head_on_html', request.method)

        # Rule: single HTML hit without static follow-up
        if request.method == 'GET' and self._is_single_html_hit(client_ip, path):
            score += self._add_match(matches, 'single_html_hit')

        # Rule: ASN reputation
        asn_record = self._lookup_asn(client_ip)
        if asn_record:
            asn_value = asn_record.asn
            asn_org_value = asn_record.organization
            asn_weight = self._asn_weight(asn_record)
            if asn_weight:
                detail = f"{asn_record.asn} {asn_record.organization}".strip()
                score += self._add_match(
                    matches,
                    'asn_datacenter',
                    detail=detail,
                    weight_override=asn_weight,
                )

        # Rule: rate limiting
        if self._is_rate_limited(client_ip):
            score += self._add_match(matches, 'rate_limit')

        if no_referer_hit and len(matches) > 1:
            score += self._add_match(matches, 'no_referer_combo')

        action = self._resolve_action(score)
        matched_keys = {match.key for match in matches}
        basic_rules = {'js_challenge_missing', 'single_html_hit', 'no_referer', 'no_referer_combo'}
        if matched_keys and matched_keys.issubset(basic_rules) and action in {'block', 'challenge'}:
            action = 'monitor'
        notify_fail2ban = score >= self.thresholds.get('fail2ban', 100)
        return DetectionResult(
            score=score,
            action=action,
            matched_rules=matches,
            notify_fail2ban=notify_fail2ban,
            headers=headers,
            asn=asn_value,
            asn_organization=asn_org_value,
        )

    def _collect_headers(self, request) -> Dict[str, str]:
        collected = {}
        for header in self.header_keys:
            value = request.META.get(header)
            if value:
                collected[header] = value[:256]
        return collected

    def _is_rate_limited(self, client_ip: str) -> bool:
        if not client_ip or not self.rate_limit_max:
            return False
        cache_key = f'botrate:{client_ip}'
        try:
            if cache.add(cache_key, 1, timeout=self.rate_limit_window):
                return False
            count = cache.incr(cache_key)
        except ValueError:
            count = 1
        except Exception:  # pragma: no cover
            logger.exception('Rate limit cache failure')
            return False
        return count >= self.rate_limit_max

    def _is_single_html_hit(self, client_ip: str, path: str) -> bool:
        """Считать одиночные HTML-запросы без последующих статических обращений."""
        if not client_ip:
            return False
        # анализируем только HTML пути (без расширения), избегая статики
        leaf = path.split('/')[-1]
        if '.' in leaf:
            return False
        cache_key = f'bouncehit:{client_ip}'
        if cache.get(cache_key):
            return False
        cache.set(cache_key, True, timeout=getattr(settings, 'BOT_PROTECTION', {}).get('BOUNCE_WINDOW_SECONDS', 5))
        return True

    def _add_match(
        self,
        matches: List[RuleMatch],
        key: str,
        detail: Optional[str] = None,
        weight_override: Optional[int] = None,
    ) -> int:
        weight = weight_override if weight_override is not None else self.weights.get(key, 0)
        if weight:
            matches.append(RuleMatch(key=key, weight=weight, detail=detail))
        return weight

    @staticmethod
    def _is_metrika_ping(path: str) -> bool:
        if not path:
            return False
        normalized = path.rstrip('/') or '/'
        return normalized.endswith('/bot/metrika-loaded')

    @staticmethod
    def _is_internal_referer(referer: str, request) -> bool:
        if not referer:
            return False
        try:
            parsed = urlparse(referer)
        except ValueError:
            return False
        if not parsed.netloc:
            return False
        host = request.get_host()
        return parsed.netloc.endswith(host)

    def _lookup_asn(self, client_ip: str):
        if not client_ip or not self.asn_db_path:
            return None
        try:
            resolver = get_resolver(self.asn_db_path)
            return resolver.lookup(client_ip)
        except Exception:  # pragma: no cover
            return None

    def _asn_weight(self, record) -> int:
        if not record:
            return 0
        if record.asn in self.asn_weights:
            return self.asn_weights[record.asn]
        org_lower = record.organization.lower()
        for pattern, weight in self.asn_org_patterns.items():
            if pattern in org_lower:
                return weight
        return 0

    def _resolve_action(self, score: int) -> str:
        if score >= self.thresholds.get('block', 90):
            return 'block'
        if score >= self.thresholds.get('challenge', 60):
            return 'challenge'
        if score >= self.thresholds.get('monitor', 30):
            return 'monitor'
        return 'allow'


bot_detection_service = BotDetectionService()
