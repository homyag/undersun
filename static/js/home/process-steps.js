// Process Steps Interactive Functionality
function toggleStep(stepNumber) {
    // Hide all step details
    const allStepDetails = document.querySelectorAll('.step-details');
    allStepDetails.forEach(function (detail) {
        detail.classList.add('hidden');
    });

    // Reset all cloud button styles
    const allClouds = document.querySelectorAll('.process-step-cloud');
    allClouds.forEach(function (cloud) {
        cloud.classList.remove('ring-4', 'scale-110');
    });

    // Show the selected step details with animation
    const targetDetail = document.getElementById('step-details-' + stepNumber);
    const targetCloud = document.getElementById('step-cloud-' + stepNumber);

    if (targetDetail && targetCloud) {
        // Add active state to clicked cloud
        targetCloud.classList.add('ring-4', 'scale-110');

        // Show details with fade-in effect
        targetDetail.classList.remove('hidden');

        // Smooth scroll to the details
        targetDetail.scrollIntoView({
            behavior: 'smooth',
            block: 'nearest'
        });

        // Add a subtle bounce animation
        targetDetail.style.animation = 'fadeInUp 0.5s ease-out';
    }
}

// Add CSS animation keyframes
const style = document.createElement('style');
style.textContent = `
@keyframes fadeInUp {
    from {
        opacity: 0;
        transform: translateY(20px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.step-details {
    animation: fadeInUp 0.5s ease-out;
}

/* Consultation form tabs */
.consultation-tab {
    background-color: transparent;
    color: rgba(255, 255, 255, 0.7);
}

.consultation-tab.active {
    background-color: rgba(255, 193, 7, 0.2);
    color: #ffc107;
    backdrop-filter: blur(4px);
    font-weight: 600;
}

.consultation-tab:hover {
    background-color: rgba(255, 193, 7, 0.1);
    color: #ffc107;
}

.consultation-content {
    display: block;
}

.consultation-content.hidden {
    display: none;
}

.consultation-content.active {
    display: block;
}

/* Consultation form enhancements */
.consultation-icon-circle {
    transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.consultation-card:hover .consultation-icon-circle {
    transform: scale(1.1);
    box-shadow: 0 0 20px rgba(255, 193, 7, 0.4);
}

.consultation-expert-icon {
    transition: color 0.3s ease;
}

.consultation-card:hover .consultation-expert-icon {
    color: #1f2937 !important;
}

/* Enhanced styling for form inputs */
.consultation-form-input:focus {
    ring-color: #ffc107 !important;
    border-color: #ffc107 !important;
    box-shadow: 0 0 0 3px rgba(255, 193, 7, 0.1) !important;
}

/* Tab icons animation */
.consultation-tab.active i {
    animation: tabIconPulse 2s infinite;
}

@keyframes tabIconPulse {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.1); }
}

/* Additional branding emphasis */
.text-accent {
    color: #ffc107 !important;
    font-weight: 700;
    text-shadow: 0 0 10px rgba(255, 193, 7, 0.3);
}
`;
document.head.appendChild(style);