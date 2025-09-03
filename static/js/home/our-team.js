// Our Team Section - Show/Hide functionality
document.addEventListener('DOMContentLoaded', function() {
    const showMoreBtn = document.getElementById('show-more-team');
    const additionalTeam = document.getElementById('additional-team');
    const chevronIcon = document.getElementById('chevron-icon');
    
    if (!showMoreBtn || !additionalTeam || !chevronIcon) {
        return;
    }

    let isExpanded = false;

    showMoreBtn.addEventListener('click', function() {
        isExpanded = !isExpanded;
        
        if (isExpanded) {
            // Show additional team members
            additionalTeam.classList.remove('hidden');
            additionalTeam.classList.add('animate-fadeIn');
            chevronIcon.classList.add('rotate-180');
        } else {
            // Hide additional team members
            additionalTeam.classList.add('hidden');
            additionalTeam.classList.remove('animate-fadeIn');
            chevronIcon.classList.remove('rotate-180');
        }
    });
});