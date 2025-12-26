# Frontend Public Directory - AI Agent Guide

## Purpose

This directory contains static assets that are served directly at the root URL path without processing by Vite. Files placed here are copied as-is to the build output (`dist/`) and accessible via root-relative URLs (e.g., `/favicon.ico`).

## Current Contents

- **`.gitkeep`** - Empty placeholder file to ensure directory exists in git
- **`AGENTS.md`** - This documentation file

## Usage

### What Goes Here

Place these types of files in `/public/`:

1. **Favicon files**

   - `favicon.ico` - Browser tab icon
   - `favicon.svg` - SVG favicon for modern browsers
   - `apple-touch-icon.png` - iOS home screen icon
   - `favicon-16x16.png`, `favicon-32x32.png` - Sized favicons

2. **Manifest files**

   - `site.webmanifest` - PWA manifest for installable web app
   - `robots.txt` - Search engine crawler instructions
   - `sitemap.xml` - Site structure for SEO

3. **Static images**

   - Brand logos that don't change
   - Default/placeholder images
   - Background images used in CSS

4. **Other static files**
   - `_redirects` or `_headers` for hosting platforms (Netlify, etc.)
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
<!-- Correct: relative to root -->
<link rel="icon" type="image/svg+xml" href="/vite.svg" />
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

When running:

- **`npm run dev`**: Files served from `/public/` at `http://localhost:5173/`
- **`npm run build`**: Files copied to `dist/` at build time

## File Access

All files in this directory are publicly accessible:

- `/public/logo.png` → `http://localhost:5173/logo.png`
- `/public/images/icon.svg` → `http://localhost:5173/images/icon.svg`

## Best Practices

1. **Keep it minimal**: Only place files here that truly need to be at the root
2. **Use descriptive names**: Avoid generic names like `image1.png`
3. **Optimize files**: Compress images before adding (use ImageOptim, TinyPNG, etc.)
4. **Version with filename**: For cache busting, rename files (e.g., `logo-v2.png`)
5. **Document purpose**: Add comments to this file when adding new assets

## Expected Future Files

Based on the project structure, you may want to add:

- **`favicon.ico`** - Replace default Vite favicon
- **`nvidia-logo.svg`** - NVIDIA branding for PWA manifest
- **`logo-192x192.png`** - Icon for Android PWA (192x192)
- **`logo-512x512.png`** - Icon for Android PWA (512x512)
- **`robots.txt`** - SEO crawler configuration
- **`site.webmanifest`** - PWA manifest with app metadata

Example `site.webmanifest`:

```json
{
  "name": "Home Security Intelligence Dashboard",
  "short_name": "Security Dashboard",
  "description": "AI-powered home security monitoring with NVIDIA RTX acceleration",
  "theme_color": "#76B900",
  "background_color": "#0E0E0E",
  "display": "standalone",
  "icons": [
    {
      "src": "/logo-192x192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/logo-512x512.png",
      "sizes": "512x512",
      "type": "image/png"
    }
  ]
}
```

## Notes for AI Agents

- **Do not remove `.gitkeep`** until you add real files
- **Public files bypass Vite processing** - they are not optimized, minified, or bundled
- **Use absolute paths** starting with `/` to reference these files
- **Cache considerations**: Browsers may cache these files aggressively
- **Security**: Do not place sensitive files here (API keys, credentials, etc.)
- **Size matters**: Large files here increase build size and deployment time

## Vite Configuration

The public directory is configured in the Vite build:

- **Dev mode**: Files served from `/public/` at `http://localhost:5173/`
- **Build mode**: Files copied to `dist/` root during `npm run build`
- **No processing**: Unlike `src/assets/`, these files bypass Vite's bundler

The current `index.html` references:

```html
<link rel="icon" type="image/svg+xml" href="/vite.svg" />
```

This should be updated to use a custom favicon once branding is finalized.

## Directory Status

**Current status**: Empty (only placeholder `.gitkeep` and this AGENTS.md)

**Action needed**: Add favicon and PWA icons when branding is finalized. Recommended files:

1. `favicon.ico` - Traditional favicon
2. `favicon.svg` - SVG favicon for modern browsers
3. `apple-touch-icon.png` - iOS home screen icon (180x180)
4. `site.webmanifest` - PWA manifest
