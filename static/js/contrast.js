/**
 * Automatic Text Contrast Adjustment
 * Determines the best text color (black or white) based on background color
 */

function getContrastColor(backgroundColor) {
    // Convert hex to RGB
    const hex = backgroundColor.replace('#', '');
    const r = parseInt(hex.substr(0, 2), 16);
    const g = parseInt(hex.substr(2, 2), 16);
    const b = parseInt(hex.substr(4, 2), 16);
    
    // Calculate luminance using relative luminance formula
    const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
    
    // Return black for light backgrounds, white for dark backgrounds
    return luminance > 0.5 ? '#000000' : '#FFFFFF';
}

function getContrastColorFromRGB(r, g, b) {
    // Calculate luminance using relative luminance formula
    const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
    
    // Use a lower threshold for better contrast - anything above 0.3 gets black text
    return luminance > 0.3 ? '#000000' : '#FFFFFF';
}

function adjustTextContrast() {
    // Adjust contrast for all cards - be more aggressive
    const cards = document.querySelectorAll('.card, .stat-card, .league-card, .division-card');
    
    cards.forEach(card => {
        const computedStyle = window.getComputedStyle(card);
        const backgroundColor = computedStyle.backgroundColor;
        
        // Extract RGB values from rgba() or rgb() string
        const rgbMatch = backgroundColor.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
        if (rgbMatch) {
            const r = parseInt(rgbMatch[1]);
            const g = parseInt(rgbMatch[2]);
            const b = parseInt(rgbMatch[3]);
            
            const contrastColor = getContrastColorFromRGB(r, g, b);
            
            // Apply contrast color to ALL text elements - be aggressive
            const textElements = card.querySelectorAll('h1, h2, h3, h4, h5, h6, p, span, div, a, td, th');
            textElements.forEach(element => {
                // Skip buttons and links that have their own styling
                if (!element.classList.contains('btn') && !element.tagName.toLowerCase() === 'a') {
                    element.style.color = contrastColor;
                    element.style.textShadow = contrastColor === '#FFFFFF' ? '1px 1px 2px rgba(0,0,0,0.8)' : '1px 1px 2px rgba(255,255,255,0.8)';
                }
            });
        }
    });
    
    // Force dark text on light backgrounds
    const lightElements = document.querySelectorAll('.card, .stat-card, .league-card, .division-card');
    lightElements.forEach(element => {
        const computedStyle = window.getComputedStyle(element);
        const bgColor = computedStyle.backgroundColor;
        const rgbMatch = bgColor.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
        
        if (rgbMatch) {
            const r = parseInt(rgbMatch[1]);
            const g = parseInt(rgbMatch[2]);
            const b = parseInt(rgbMatch[3]);
            
            // If background is light (high RGB values), force dark text
            if (r > 150 && g > 150 && b > 150) {
                const textElements = element.querySelectorAll('h1, h2, h3, h4, h5, h6, p, span, div');
                textElements.forEach(textEl => {
                    textEl.style.color = '#000000';
                    textEl.style.textShadow = '1px 1px 2px rgba(255,255,255,0.8)';
                });
            }
        }
    });
}

// Run on page load
document.addEventListener('DOMContentLoaded', adjustTextContrast);

// Run when window is resized (in case of responsive changes)
window.addEventListener('resize', adjustTextContrast);
