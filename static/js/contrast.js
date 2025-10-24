/**
 * Automatic Contrast Adjustment for Team Cards
 * This script calculates the luminance of background colors and adjusts text colors
 * to ensure proper contrast while maintaining the team's color scheme.
 */

document.addEventListener('DOMContentLoaded', function() {
    // Function to convert hex color to RGB
    function hexToRgb(hex) {
        const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
        return result ? {
            r: parseInt(result[1], 16),
            g: parseInt(result[2], 16),
            b: parseInt(result[3], 16)
        } : null;
    }

    // Function to calculate relative luminance
    function getLuminance(r, g, b) {
        const [rs, gs, bs] = [r, g, b].map(c => {
            c = c / 255;
            return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
        });
        return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
    }

    // Function to calculate contrast ratio between two colors
    function getContrastRatio(color1, color2) {
        const rgb1 = hexToRgb(color1);
        const rgb2 = hexToRgb(color2);
        
        if (!rgb1 || !rgb2) return 1;
        
        const lum1 = getLuminance(rgb1.r, rgb1.g, rgb1.b);
        const lum2 = getLuminance(rgb2.r, rgb2.g, rgb2.b);
        
        const brightest = Math.max(lum1, lum2);
        const darkest = Math.min(lum1, lum2);
        
        return (brightest + 0.05) / (darkest + 0.05);
    }

    // Function to adjust color brightness
    function adjustBrightness(hex, percent) {
        const rgb = hexToRgb(hex);
        if (!rgb) return hex;
        
        const factor = percent / 100;
        const r = Math.round(Math.max(0, Math.min(255, rgb.r + (255 - rgb.r) * factor)));
        const g = Math.round(Math.max(0, Math.min(255, rgb.g + (255 - rgb.g) * factor)));
        const b = Math.round(Math.max(0, Math.min(255, rgb.b + (255 - rgb.b) * factor)));
        
        return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
    }

    // Function to darken color
    function darkenColor(hex, percent) {
        const rgb = hexToRgb(hex);
        if (!rgb) return hex;
        
        const factor = 1 - (percent / 100);
        const r = Math.round(rgb.r * factor);
        const g = Math.round(rgb.g * factor);
        const b = Math.round(rgb.b * factor);
        
        return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
    }

    // Function to get optimal text color for background
    function getOptimalTextColor(backgroundColor, originalTextColor) {
        const whiteContrast = getContrastRatio(backgroundColor, '#FFFFFF');
        const blackContrast = getContrastRatio(backgroundColor, '#000000');
        
        // WCAG AA standard requires contrast ratio of at least 4.5:1 for normal text
        const minContrast = 4.5;
        
        // If original color has good contrast, keep it
        if (originalTextColor) {
            const originalContrast = getContrastRatio(backgroundColor, originalTextColor);
            if (originalContrast >= minContrast) {
                return originalTextColor;
            }
        }
        
        // Choose between white and black based on which has better contrast
        if (whiteContrast >= minContrast && whiteContrast > blackContrast) {
            return '#FFFFFF';
        } else if (blackContrast >= minContrast) {
            return '#000000';
        } else {
            // If neither meets minimum contrast, adjust the original color
            if (originalTextColor) {
                // Try to darken or lighten the original color
                const rgb = hexToRgb(originalTextColor);
                if (rgb) {
                    const luminance = getLuminance(rgb.r, rgb.g, rgb.b);
                    const bgLuminance = getLuminance(...Object.values(hexToRgb(backgroundColor)));
                    
                    if (luminance > bgLuminance) {
                        // Text is lighter than background, darken it
                        return darkenColor(originalTextColor, 50);
                    } else {
                        // Text is darker than background, lighten it
                        return adjustBrightness(originalTextColor, 50);
                    }
                }
            }
            
            // Fallback to white or black
            return whiteContrast > blackContrast ? '#FFFFFF' : '#000000';
        }
    }

    // Function to apply contrast adjustments to team cards
    function applyContrastAdjustments() {
        const teamItems = document.querySelectorAll('.team-item');
        
        teamItems.forEach(function(teamItem) {
            const computedStyle = window.getComputedStyle(teamItem);
            const backgroundColor = computedStyle.backgroundColor;
            
            // Convert RGB to hex if needed
            let bgHex = backgroundColor;
            if (backgroundColor.startsWith('rgb')) {
                const rgb = backgroundColor.match(/\d+/g);
                if (rgb && rgb.length >= 3) {
                    bgHex = `#${rgb.map(x => parseInt(x).toString(16).padStart(2, '0')).join('')}`;
                }
            }
            
            // Find text elements within this team item
            const teamName = teamItem.querySelector('.team-name');
            const stadiumInfo = teamItem.querySelector('.stadium-info');
            const locationInfo = teamItem.querySelector('.location-info');
            
            // Get original colors
            const originalTeamNameColor = teamName ? window.getComputedStyle(teamName).color : null;
            const originalStadiumColor = stadiumInfo ? window.getComputedStyle(stadiumInfo).color : null;
            const originalLocationColor = locationInfo ? window.getComputedStyle(locationInfo).color : null;
            
            // Convert colors to hex
            function rgbToHex(rgb) {
                if (!rgb || rgb === 'rgba(0, 0, 0, 0)') return null;
                const match = rgb.match(/\d+/g);
                if (match && match.length >= 3) {
                    return `#${match.map(x => parseInt(x).toString(16).padStart(2, '0')).join('')}`;
                }
                return null;
            }
            
            const originalTeamNameHex = rgbToHex(originalTeamNameColor);
            const originalStadiumHex = rgbToHex(originalStadiumColor);
            const originalLocationHex = rgbToHex(originalLocationColor);
            
            // Apply optimal colors
            if (teamName) {
                const optimalTeamNameColor = getOptimalTextColor(bgHex, originalTeamNameHex);
                teamName.style.color = optimalTeamNameColor;
            }
            
            if (stadiumInfo) {
                const optimalStadiumColor = getOptimalTextColor(bgHex, originalStadiumHex);
                stadiumInfo.style.color = optimalStadiumColor;
            }
            
            if (locationInfo) {
                const optimalLocationColor = getOptimalTextColor(bgHex, originalLocationHex);
                locationInfo.style.color = optimalLocationColor;
            }
        });
    }

    // Apply contrast adjustments when page loads
    applyContrastAdjustments();
    
    // Re-apply if window is resized (in case of responsive changes)
    window.addEventListener('resize', function() {
        setTimeout(applyContrastAdjustments, 100);
    });
    
    // Re-apply if CSS changes (for dynamic content)
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.type === 'attributes' && 
                (mutation.attributeName === 'style' || mutation.attributeName === 'class')) {
                setTimeout(applyContrastAdjustments, 50);
            }
        });
    });
    
    // Observe changes to team items
    const teamItems = document.querySelectorAll('.team-item');
    teamItems.forEach(function(item) {
        observer.observe(item, { attributes: true });
    });
});