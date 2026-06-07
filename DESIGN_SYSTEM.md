# Tennis Design System

## Visual Tone

Professional, clean, sports-stat friendly, and slightly cartoonish. The UI should look credible, with humor reserved for hover states, unlocks, mascots, and error pages.

## Asset Rules

- Prefer transparent PNG and SVG outputs.
- Use consistent ball size and camera angle.
- No drop shadow unless specifically needed.
- Tournament balls should work at small sizes.
- Mascots should be readable at card/icon size.
- Easter eggs should not interfere with normal navigation.

## Naming Convention

Use lowercase kebab-case filenames.

Examples:

- tennis-ball-wimbledon-green.png
- tennis-ball-french-open-clay.png
- mascot-us-open-pigeon.png
- badge-career-grand-slam.svg
- theme-australian-open.json

## Suggested CSS Tokens

```css
:root {
  --tennis-atp-navy: #0b214a;
  --tennis-wta-purple: #6f35ff;
  --tennis-wimbledon-green: #1f7a3a;
  --tennis-french-clay: #d96b2b;
  --tennis-us-open-navy: #002f6c;
  --tennis-australian-open-blue: #00a3e0;
  --tennis-career-gold: #d4af37;
}
```
