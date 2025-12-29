# Frontend Public Directory - AI Agent Guide

## Purpose

This directory contains static assets that are served directly at the root URL path without processing by Vite. Files placed here are copied as-is to the build output (`dist/`) and accessible via root-relative URLs (e.g., `/favicon.svg`).

## Current Contents

| File          | Purpose                                                   |
| ------------- | --------------------------------------------------------- |
| `.gitkeep`    | Empty placeholder to ensure directory exists in git       |
| `favicon.svg` | Application favicon (security shield icon with checkmark) |
| `AGENTS.md`   | This documentation file                                   |

## favicon.svg

The current favicon is an SVG security shield icon:

- Green shield shape with gradient
- White checkmark overlay
- Uses emerald/teal colors (`#10B981`, `#059669`)

This is a custom security-themed icon appropriate for the application.

## Usage

### What Goes Here

Place these types of files in `/public/`:

1. **Favicon files**

   - `favicon.ico` - Traditional favicon for older browsers
   - `favicon.svg` - SVG favicon for modern browsers (current)
   - `apple-touch-icon.png` - iOS home screen icon (180x180)
   - `favicon-16x16.png`, `favicon-32x32.png` - Sized PNG favicons

2. **Manifest files**

   - `site.webmanifest` - PWA manifest for installable web app
   - `robots.txt` - Search engine crawler instructions
   - `sitemap.xml` - Site structure for SEO

3. **Static images**

   - Brand logos that don't change
   - Default/placeholder images
   - Background images used in CSS

4. **Other static files**
   - `_redirects` or `_headers` for hosting platforms
   - Static JSON data files
   - PDF documents, downloadable files

### What Does NOT Go Here

Do NOT place these in `/public/`:

- **Component images** - Import into components instead
- **Assets that need processing** - Use `src/assets/` for images/fonts that should be optimized
- **Source code** - All `.ts`, `.tsx`, `.css` files belong in `src/`
- **Dynamic content** - Use API endpoints for runtime data

## How to Reference Public Files

### In HTML (`index.html`)

```html
<link rel="icon" type="image/svg+xml" href="/favicon.svg" />
```

### In Components

```typescript
// Correct: absolute path from root
<img src="/logo.png" alt="Logo" />

// Incorrect: do not import from public
// import logo from '../public/logo.png'  // WRONG
```

### In CSS

```css
/* Correct: absolute path from root */
background-image: url(/background.jpg);
```

## Build Behavior

- **`npm run dev`**: Files served directly from `/public/`
- **`npm run build`**: Files copied to `dist/` at build time

## File Access

All files in this directory are publicly accessible:

- `/public/favicon.svg` -> `http://localhost:5173/favicon.svg`
- `/public/images/icon.png` -> `http://localhost:5173/images/icon.png`

## Best Practices

1. **Keep it minimal**: Only place files here that truly need to be at the root
2. **Use descriptive names**: Avoid generic names like `image1.png`
3. **Optimize files**: Compress images before adding
4. **Version with filename**: For cache busting, rename files (e.g., `logo-v2.png`)
5. **Document purpose**: Add comments when adding new assets

## Potential Future Additions

Based on project needs, consider adding:

- **`apple-touch-icon.png`** - iOS home screen icon (180x180)
- **`site.webmanifest`** - PWA manifest with app metadata
- **`robots.txt`** - SEO crawler configuration

Example `site.webmanifest`:

```json
{
  "name": "Home Security Intelligence Dashboard",
  "short_name": "Security Dashboard",
  "description": "AI-powered home security monitoring",
  "theme_color": "#76B900",
  "background_color": "#0E0E0E",
  "display": "standalone",
  "icons": [
    {
      "src": "/favicon.svg",
      "sizes": "any",
      "type": "image/svg+xml"
    }
  ]
}
```

## Notes for AI Agents

- **Public files bypass Vite processing** - they are not optimized or bundled
- **Use absolute paths** starting with `/` to reference these files
- **Cache considerations**: Browsers may cache these files aggressively
- **Security**: Do not place sensitive files here (API keys, credentials)
- **Size matters**: Large files increase build size and deployment time
- The current `index.html` references `/favicon.svg` which exists in this directory
