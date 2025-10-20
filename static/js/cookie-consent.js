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
    }

    function showOverlay() {
        overlay.classList.remove('hidden');
        overlay.classList.remove('pointer-events-none');
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
