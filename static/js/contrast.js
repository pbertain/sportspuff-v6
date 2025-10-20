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
    
    // Return black for light backgrounds, white for dark backgrounds
    return luminance > 0.5 ? '#000000' : '#FFFFFF';
}

function adjustTextContrast() {
    // Adjust contrast for all cards
    const cards = document.querySelectorAll('.card, .stat-card, .league-card');
    
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
            
            // Apply contrast color to text elements
            const textElements = card.querySelectorAll('h1, h2, h3, h4, h5, h6, p, span, div:not(.btn)');
            textElements.forEach(element => {
                // Skip elements that already have specific color styling
                if (!element.style.color || element.style.color === '') {
                    element.style.color = contrastColor;
                }
            });
        }
    });
    
    // Adjust contrast for league cards specifically
    const leagueCards = document.querySelectorAll('.league-card');
    leagueCards.forEach(card => {
        const league = card.dataset.league;
        if (league) {
            // Apply league-specific styling with proper contrast
            const leagueColors = {
                'MLB': { bg: '#0E4C92', text: '#FFFFFF' },
                'NHL': { bg: '#BFC9CA', text: '#000000' },
                'NBA': { bg: '#7028E4', text: '#FFFFFF' },
                'NFL': { bg: '#B3001B', text: '#FFFFFF' },
                'WNBA': { bg: '#FF6F00', text: '#FFFFFF' },
                'MLS': { bg: '#2BAE66', text: '#FFFFFF' }
            };
            
            if (leagueColors[league]) {
                card.style.backgroundColor = leagueColors[league].bg;
                const textElements = card.querySelectorAll('h5, p, .stat-number');
                textElements.forEach(element => {
                    element.style.color = leagueColors[league].text;
                });
            }
        }
    });
}

// Run on page load
document.addEventListener('DOMContentLoaded', adjustTextContrast);

// Run when window is resized (in case of responsive changes)
window.addEventListener('resize', adjustTextContrast);
