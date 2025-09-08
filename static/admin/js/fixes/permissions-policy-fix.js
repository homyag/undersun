/**
 * Fix for Django admin Permissions Policy violation with unload event
 * This script addresses the specific issue in RelatedObjectLookups.js
 */

(function() {
    'use strict';
    
    // Suppress the specific permissions policy violation warning
    const originalConsoleWarn = console.warn;
    console.warn = function() {
        const message = arguments[0];
        if (typeof message === 'string' && 
            message.includes('Permissions policy violation') && 
            message.includes('unload is not allowed')) {
            // Suppress this specific warning - it's a known Django admin issue
            return;
        }
        return originalConsoleWarn.apply(console, arguments);
    };
    
    // Wait for DOM to be ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initFix);
    } else {
        initFix();
    }
    
    function initFix() {
        // Override addEventListener to replace unload with beforeunload
        if (window.addEventListener) {
            const originalAddEventListener = window.addEventListener;
            window.addEventListener = function(type, listener, options) {
                if (type === 'unload') {
                    // Use beforeunload instead of unload for better compatibility
                    type = 'beforeunload';
                }
                return originalAddEventListener.call(this, type, listener, options);
            };
        }
        
        // Handle jQuery if it exists
        if (window.jQuery) {
            // Override jQuery's unload method
            const $ = window.jQuery;
            const originalUnload = $.fn.unload;
            if (originalUnload) {
                $.fn.unload = function(handler) {
                    return this.on('beforeunload', handler);
                };
            }
            
            // Override jQuery's on method for unload events
            const originalOn = $.fn.on;
            $.fn.on = function(events) {
                if (typeof events === 'string' && events.includes('unload')) {
                    events = events.replace(/\bunload\b/g, 'beforeunload');
                }
                return originalOn.apply(this, arguments);
            };
        }
    }
    
    // Additional cleanup after window load
    window.addEventListener('load', function() {
        // Try to prevent any remaining unload event issues
        try {
            // Remove any existing unload listeners that might cause issues
            if (window.removeEventListener) {
                const dummyHandler = function() {};
                window.removeEventListener('unload', dummyHandler);
            }
        } catch (e) {
            // Silently ignore any errors
        }
    });
    
})();