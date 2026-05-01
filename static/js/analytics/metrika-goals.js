(function() {
    const GOAL_SELECTOR = '[data-ym-goal]';
    const DEFAULT_EVENT = 'click';
    const SUPPORTED_EVENTS = ['click', 'submit', 'change'];

    function parseParams(element) {
        if (!element || !element.dataset) {
            return undefined;
        }

        const { ymParams } = element.dataset;
        if (ymParams) {
            try {
                const parsed = JSON.parse(ymParams);
                if (parsed && typeof parsed === 'object') {
                    return parsed;
                }
            } catch (error) {
                if (window.console && typeof window.console.warn === 'function') {
                    console.warn('Некорректный JSON в data-ym-params', ymParams, error);
                }
            }
        }

        const params = {};
        Object.keys(element.dataset).forEach(key => {
            if (!key.startsWith('ymParam')) {
                return;
            }
            const paramKey = key.substring('ymParam'.length);
            if (!paramKey) {
                return;
            }
            const normalizedKey = paramKey.charAt(0).toLowerCase() + paramKey.slice(1);
            params[normalizedKey] = element.dataset[key];
        });

        return Object.keys(params).length ? params : undefined;
    }

    function dispatchGoal(element) {
        const goalName = element?.dataset?.ymGoal;
        if (!goalName) {
            return;
        }
        const params = parseParams(element);
        if (typeof window.trackMetrikaGoal === 'function') {
            window.trackMetrikaGoal(goalName, params);
        } else if (typeof window.ym === 'function' && window.METRIKA_COUNTER_ID) {
            window.ym(window.METRIKA_COUNTER_ID, 'reachGoal', goalName, params || {});
        }
    }

    function handleEvent(event) {
        const target = event.target instanceof Element ? event.target : null;
        if (!target) {
            return;
        }

        const goalElement = target.closest(GOAL_SELECTOR);
        if (!goalElement || goalElement.dataset.ymGoalDisabled === 'true') {
            return;
        }

        const expectedEvent = (goalElement.dataset.ymEvent || DEFAULT_EVENT).toLowerCase();
        if (expectedEvent !== event.type) {
            return;
        }

        dispatchGoal(goalElement);

        if (goalElement.dataset.ymOnce === 'true') {
            goalElement.dataset.ymGoalDisabled = 'true';
        }
    }

    SUPPORTED_EVENTS.forEach(eventName => {
        document.addEventListener(eventName, handleEvent, true);
    });

    window.dispatchMetrikaGoal = function(goalName, params) {
        if (!goalName) {
            return;
        }
        window.trackMetrikaGoal?.(goalName, params);
    };
})();
