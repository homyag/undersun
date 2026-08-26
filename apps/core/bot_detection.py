from __future__ import annotations

import hashlib
import ipaddress
import logging
import re
import time
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
        self.js_challenge_grace_seconds = int(config.get('JS_CHALLENGE_GRACE_SECONDS', 10))
        self.js_challenge_max_misses = int(config.get('JS_CHALLENGE_MAX_MISSES', 3))
        self.js_challenge_exempt_path_prefixes = tuple(
            config.get('JS_CHALLENGE_EXEMPT_PATH_PREFIXES', [])
        )
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

        if path.startswith(self.skip_path_prefixes):
            return DetectionResult(score=0, action='allow')

        headers = self._collect_headers(request)
        missing_accept_lang = not headers.get('HTTP_ACCEPT_LANGUAGE')
        missing_accept_encoding = not headers.get('HTTP_ACCEPT_ENCODING')

        # Known automation clients must not receive the page shell or analytics.
        # Search and audit tools that legitimately use a headless runtime are
        # exempted by WHITELIST_USER_AGENTS in BotDetectionMiddleware first.
        if any(pattern.search(user_agent) for pattern in self.suspicious_user_agents):
            score += self._add_match(matches, 'suspicious_user_agent', 'user_agent')

        # Block truly headerless browser-like traffic and clients that keep
        # requesting HTML without running JS.
        # Meta's company URL validator can probe the public site root without
        # a User-Agent. Permit that one harmless read while retaining the
        # headerless-client block for every other HTML endpoint.
        is_public_site_root = path in ('/', '/ru/', '/en/', '/th/')
        if not is_public_site_root and (
            not user_agent or user_agent == '-' or (missing_accept_lang and missing_accept_encoding)
        ):
            score += self._add_match(matches, 'missing_headers_critical', 'noheader')

        cookie_token = request.COOKIES.get(self.challenge_cookie)
        js_challenge_exempt = self._is_js_challenge_exempt_path(path)

        if score == 0 and not js_challenge_exempt and self._should_enforce_js_challenge(request):
            if cookie_token:
                self._clear_js_challenge_pending(client_ip, user_agent)
            elif self._record_js_challenge_miss(client_ip, user_agent):
                score += self._add_match(matches, 'js_challenge_missing', 'cookie')

        if score == 0 and not js_challenge_exempt and request.method in {'POST', 'PUT', 'PATCH'}:
            if not cookie_token:
                score += self._add_match(matches, 'js_challenge_missing', 'cookie')

        return DetectionResult(
            score=score,
            action='block' if score else 'allow',
            matched_rules=matches,
            notify_fail2ban=False,
            headers=headers,
        )

    def _collect_headers(self, request) -> Dict[str, str]:
        collected = {}
        for header in self.header_keys:
            value = request.META.get(header)
            if value:
                collected[header] = value[:256]
        return collected

    def _should_enforce_js_challenge(self, request) -> bool:
        if request.method not in {'GET', 'HEAD'}:
            return False

        path = request.path or '/'
        if self._is_metrika_ping(path):
            return False

        leaf = path.split('/')[-1]
        return '.' not in leaf

    def _is_js_challenge_exempt_path(self, path: str) -> bool:
        normalized_path = path or '/'
        for prefix in self.js_challenge_exempt_path_prefixes:
            normalized_prefix = (prefix or '').rstrip('/') or '/'
            if normalized_path == normalized_prefix or normalized_path.startswith(f'{normalized_prefix}/'):
                return True
        return False

    def _record_js_challenge_miss(self, client_ip: str, user_agent: str) -> bool:
        cache_key = self._js_challenge_cache_key(client_ip, user_agent)
        if not cache_key:
            return False

        now = time.time()
        timeout = max(self.js_challenge_grace_seconds * 3, 30)
        try:
            started_at, misses = self._parse_js_challenge_state(cache.get(cache_key))
            if started_at is None:
                cache.set(cache_key, f'{now}:1', timeout=timeout)
                return False

            misses += 1
            cache.set(cache_key, f'{started_at}:{misses}', timeout=timeout)
        except Exception:  # pragma: no cover
            logger.exception('JS challenge cache update failure')
            return False

        return (
            misses >= self.js_challenge_max_misses
            and now - started_at >= self.js_challenge_grace_seconds
        )

    @staticmethod
    def _parse_js_challenge_state(raw_value) -> Tuple[Optional[float], int]:
        if raw_value is None:
            return None, 0
        try:
            if isinstance(raw_value, bytes):
                raw_value = raw_value.decode('utf-8')
            raw_text = str(raw_value)
            if ':' in raw_text:
                started_at, misses = raw_text.split(':', 1)
                return float(started_at), int(misses)
            return float(raw_text), 1
        except (TypeError, ValueError):
            return None, 0

    def _clear_js_challenge_pending(self, client_ip: str, user_agent: str) -> None:
        cache_key = self._js_challenge_cache_key(client_ip, user_agent)
        if not cache_key:
            return

        try:
            cache.delete(cache_key)
        except Exception:  # pragma: no cover
            logger.exception('JS challenge cache delete failure')

    @staticmethod
    def _js_challenge_cache_key(client_ip: str, user_agent: str) -> Optional[str]:
        if not client_ip or not user_agent:
            return None
        fingerprint = f'{client_ip}|{user_agent[:512]}'.encode('utf-8', errors='ignore')
        digest = hashlib.sha256(fingerprint).hexdigest()[:24]
        return f'botjs:{digest}'

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

    @staticmethod
    def _is_search_referer(referer: str) -> bool:
        if not referer:
            return False
        try:
            parsed = urlparse(referer)
        except ValueError:
            return False
        if not parsed.netloc:
            return False
        trusted_domains = (
            'google.com',
            'google.ru',
            'google.co.th',
            'bing.com',
            'yandex.ru',
            'yandex.com',
            'duckduckgo.com',
            'search.brave.com',
        )
        return any(parsed.netloc.endswith(domain) for domain in trusted_domains)

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
