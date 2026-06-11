(function () {
    'use strict';

    const ACTIVE_STATUSES = new Set(['pending', 'running']);
    const STATUS_COLORS = {
        pending: '#6b7280',
        running: '#2563eb',
        succeeded: '#15803d',
        failed: '#b91c1c',
        cancelled: '#92400e',
    };
    const POLL_INTERVAL_MS = 3000;
    const STATUS_ENDPOINT = '/admin/blog/blogtranslationjob/status-json/';

    function collectJobIds() {
        const ids = new Set();
        document.querySelectorAll('[data-blog-translation-job-status]').forEach((node) => {
            const id = node.getAttribute('data-blog-translation-job-status');
            if (id) {
                ids.add(id);
            }
        });
        return Array.from(ids);
    }

    function updateText(selector, value) {
        document.querySelectorAll(selector).forEach((node) => {
            node.textContent = value;
        });
    }

    function updateJob(job) {
        document
            .querySelectorAll(`[data-blog-translation-job-status="${job.id}"]`)
            .forEach((node) => {
                node.textContent = job.status_label;
                node.style.backgroundColor = STATUS_COLORS[job.status] || STATUS_COLORS.pending;
            });

        updateText(
            `[data-blog-translation-job-progress="${job.id}"]`,
            `${job.progress_percent}% (${job.completed_fields}/${job.total_fields}, ошибок: ${job.failed_fields})`
        );
        updateText(
            `[data-blog-translation-job-current-field="${job.id}"]`,
            job.current_field || '—'
        );
        updateText(
            `[data-blog-translation-job-error="${job.id}"]`,
            job.error_message || ''
        );
    }

    async function pollStatuses() {
        const ids = collectJobIds();
        if (!ids.length) {
            return false;
        }

        const url = `${STATUS_ENDPOINT}?ids=${encodeURIComponent(ids.join(','))}`;
        const response = await fetch(url, {
            credentials: 'same-origin',
            headers: {
                Accept: 'application/json',
            },
        });

        if (!response.ok) {
            return true;
        }

        const payload = await response.json();
        let hasActiveJobs = false;

        (payload.jobs || []).forEach((job) => {
            updateJob(job);
            if (ACTIVE_STATUSES.has(job.status)) {
                hasActiveJobs = true;
            }
        });

        return hasActiveJobs;
    }

    function startPolling() {
        let timerId = null;

        const run = async () => {
            try {
                const shouldContinue = await pollStatuses();
                if (!shouldContinue && timerId) {
                    window.clearInterval(timerId);
                    timerId = null;
                }
            } catch (error) {
                // Keep admin pages usable if a transient polling request fails.
            }
        };

        window.setTimeout(run, 500);
        timerId = window.setInterval(run, POLL_INTERVAL_MS);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', startPolling);
    } else {
        startPolling();
    }
})();
