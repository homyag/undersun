
(function() {
    'use strict';

    function enableStickyActions(formContainer) {
        if (!formContainer) {
            return null;
        }

        const actionBlocks = formContainer.querySelectorAll('.actions');
        if (!actionBlocks.length) {
            return null;
        }

        const topActions = actionBlocks[0];
        if (topActions.dataset.stickyActionsAttached) {
            return null;
        }

        topActions.dataset.stickyActionsAttached = 'true';
        const placeholder = document.createElement('div');
        placeholder.className = 'changelist-actions-placeholder';
        placeholder.style.height = topActions.offsetHeight + 'px';
        topActions.parentNode.insertBefore(placeholder, topActions);

        topActions.classList.add('changelist-actions--sticky');

        function updatePlaceholderHeight() {
            placeholder.style.height = topActions.offsetHeight + 'px';
        }

        function updateLayout(rect) {
            if (rect) {
                topActions.style.left = rect.left + 'px';
                topActions.style.width = rect.width + 'px';
            } else {
                topActions.style.left = '0';
                topActions.style.width = '100%';
            }
        }

        return {
            element: topActions,
            updatePlaceholder: updatePlaceholderHeight,
            updateLayout: updateLayout
        };
    }

    function initStickyScrollbar() {
        if (!document.body.classList.contains('change-list')) {
            return;
        }

        const formContainer = document.querySelector('.changelist-form-container') || document.querySelector('#changelist-form');
        const resultsContainer = (formContainer && formContainer.querySelector('.results')) || document.querySelector('#changelist-form .results') || document.querySelector('.results');

        if (!resultsContainer) {
            return;
        }

        if (resultsContainer.dataset.stickyScrollbarAttached) {
            return;
        }
        resultsContainer.dataset.stickyScrollbarAttached = 'true';

        const stickyScrollbar = document.createElement('div');
        stickyScrollbar.className = 'sticky-horizontal-scrollbar is-hidden';
        stickyScrollbar.setAttribute('aria-hidden', 'true');

        const inner = document.createElement('div');
        inner.className = 'sticky-horizontal-scrollbar__inner';
        stickyScrollbar.appendChild(inner);

        document.body.appendChild(stickyScrollbar);

        const anchorElement = formContainer || document.querySelector('#content-main') || document.querySelector('#content') || document.body;
        const stickyActionsControls = enableStickyActions(formContainer);

        function updateActionsBottomSpacing(hasScrollbar) {
            if (!stickyActionsControls) {
                document.documentElement.style.setProperty('--admin-sticky-actions-bottom', (hasScrollbar ? stickyScrollbar.offsetHeight + 12 : 16) + 'px');
                return;
            }

            const spacing = hasScrollbar ? stickyScrollbar.offsetHeight + 12 : 16;
            document.documentElement.style.setProperty('--admin-sticky-actions-bottom', spacing + 'px');
        }

        function toggleVisibility(visible) {
            if (visible) {
                stickyScrollbar.classList.remove('is-hidden');
                document.body.classList.add('has-sticky-horizontal-scrollbar');
            } else {
                stickyScrollbar.classList.add('is-hidden');
                document.body.classList.remove('has-sticky-horizontal-scrollbar');
            }
            updateActionsBottomSpacing(visible);
        }

        function updateGeometry() {
            window.requestAnimationFrame(function() {
                let rect = null;
                if (!anchorElement) {
                    stickyScrollbar.style.left = '0';
                    stickyScrollbar.style.width = '100%';
                } else {
                    rect = anchorElement.getBoundingClientRect();
                    stickyScrollbar.style.left = rect.left + 'px';
                    stickyScrollbar.style.width = rect.width + 'px';
                }

                if (stickyActionsControls && stickyActionsControls.updateLayout) {
                    stickyActionsControls.updateLayout(rect);
                }
            });
        }

        function refreshScrollbar() {
            window.requestAnimationFrame(function() {
                const scrollWidth = resultsContainer.scrollWidth;
                inner.style.width = scrollWidth + 'px';

                const hasOverflow = scrollWidth > resultsContainer.clientWidth + 1;
                toggleVisibility(hasOverflow);
                if (hasOverflow) {
                    updateGeometry();
                }
            });
        }

        let syncingFromResults = false;
        let syncingFromBar = false;

        function syncFromResults() {
            if (syncingFromBar) {
                syncingFromBar = false;
                return;
            }
            syncingFromResults = true;
            stickyScrollbar.scrollLeft = resultsContainer.scrollLeft;
        }

        function syncFromBar() {
            if (syncingFromResults) {
                syncingFromResults = false;
                return;
            }
            syncingFromBar = true;
            resultsContainer.scrollLeft = stickyScrollbar.scrollLeft;
        }

        resultsContainer.addEventListener('scroll', syncFromResults);
        stickyScrollbar.addEventListener('scroll', syncFromBar);

        function handleResize() {
            refreshScrollbar();
            if (stickyActionsControls && stickyActionsControls.updatePlaceholder) {
                stickyActionsControls.updatePlaceholder();
            }
        }

        refreshScrollbar();
        window.addEventListener('resize', handleResize);
        window.addEventListener('scroll', updateGeometry, { passive: true });

        if (window.ResizeObserver) {
            const resizeObserver = new ResizeObserver(function() {
                refreshScrollbar();
                if (stickyActionsControls && stickyActionsControls.updatePlaceholder) {
                    stickyActionsControls.updatePlaceholder();
                }
            });
            resizeObserver.observe(resultsContainer);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initStickyScrollbar);
    } else {
        initStickyScrollbar();
    }
})();
