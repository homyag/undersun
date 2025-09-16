// Our Team Section - Show/Hide functionality
document.addEventListener('DOMContentLoaded', function() {
    const showMoreBtn = document.getElementById('show-more-team');
    const additionalTeam = document.getElementById('additional-team');
    const chevronIcon = document.getElementById('chevron-icon');
    
    if (!showMoreBtn || !additionalTeam || !chevronIcon) {
        return;
    }

    // Инициализируем стили для плавной анимации
    additionalTeam.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
    additionalTeam.style.opacity = '0';
    additionalTeam.style.transform = 'translateY(-20px)';

    let isExpanded = false;

    showMoreBtn.addEventListener('click', function() {
        isExpanded = !isExpanded;
        
        if (isExpanded) {
            // Show additional team members
            additionalTeam.classList.remove('hidden');
            // Добавляем небольшую задержку для плавного появления
            setTimeout(() => {
                additionalTeam.style.opacity = '1';
                additionalTeam.style.transform = 'translateY(0)';
            }, 50);
            chevronIcon.classList.add('rotate-180');
        } else {
            // Hide additional team members with animation
            additionalTeam.style.opacity = '0';
            additionalTeam.style.transform = 'translateY(-20px)';
            setTimeout(() => {
                additionalTeam.classList.add('hidden');
            }, 300);
            chevronIcon.classList.remove('rotate-180');
        }
    });
});