(function() {
    const overlay = document.getElementById('cookie-consent-overlay');
    if (!overlay) {
        return;
    }

    const lang = overlay.dataset.cookieLang || 'ru';
    const acceptBtn = document.getElementById('cookie-consent-accept');
    const declineBtn = document.getElementById('cookie-consent-decline');
    const STORAGE_KEY = 'undersun_cookie_consent_v1';

    function readState() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            return raw ? JSON.parse(raw) : {};
        } catch (err) {
            console.warn('Cookie consent: unable to read state', err);
            return {};
        }
    }

    function writeState(state) {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
        } catch (err) {
            console.warn('Cookie consent: unable to persist state', err);
        }
    }

    function hideOverlay() {
        overlay.classList.add('hidden');
        overlay.classList.add('pointer-events-none');
        overlay.classList.remove('cookie-consent-mobile-top');
    }

    function rectsOverlap(first, second) {
        return Boolean(
            first &&
            second &&
            first.right > second.left &&
            first.left < second.right &&
            first.bottom > second.top &&
            first.top < second.bottom
        );
    }

    function adjustMobilePlacement() {
        overlay.classList.remove('cookie-consent-mobile-top');

        if (!window.matchMedia('(max-width: 768px)').matches) {
            return;
        }

        const overlayRect = overlay.getBoundingClientRect();
        if (document.getElementById('main-price')) {
            overlay.classList.add('cookie-consent-mobile-top');
            return;
        }

        const criticalElements = Array.from(document.querySelectorAll('main h1, h1, #main-price, [onclick="openCallbackModal()"]'))
            .filter(element => {
                const rect = element.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0 && rect.bottom > 0 && rect.top < window.innerHeight;
            });

        if (criticalElements.some(element => rectsOverlap(overlayRect, element.getBoundingClientRect()))) {
            overlay.classList.add('cookie-consent-mobile-top');
        }
    }

    function showOverlay() {
        overlay.classList.remove('hidden');
        overlay.classList.remove('pointer-events-none');
        window.requestAnimationFrame(adjustMobilePlacement);
    }

    function dispatchUpdate(status) {
        const event = new CustomEvent('cookieConsentUpdated', {
            detail: { language: lang, status }
        });
        window.dispatchEvent(event);
    }

    document.addEventListener('DOMContentLoaded', function() {
        const state = readState();
        const consent = state[lang];

        if (!consent || !consent.status) {
            showOverlay();
        }

        window.addEventListener('resize', adjustMobilePlacement);

        acceptBtn?.addEventListener('click', function() {
            const nextState = readState();
            nextState[lang] = {
                status: 'accepted',
                timestamp: new Date().toISOString()
            };
            writeState(nextState);
            hideOverlay();
            dispatchUpdate('accepted');
        });

        declineBtn?.addEventListener('click', function() {
            const nextState = readState();
            nextState[lang] = {
                status: 'declined',
                timestamp: new Date().toISOString()
            };
            writeState(nextState);
            hideOverlay();
            dispatchUpdate('declined');
        });
    });
})();
