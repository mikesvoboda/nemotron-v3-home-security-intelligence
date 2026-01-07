# Frontend Public Images

## Purpose

The `frontend/public/images/` directory contains static image assets used in the React frontend. These images are publicly accessible and served directly by the web server without processing.

## Directory Structure

```
frontend/public/images/
├── AGENTS.md                  # This file
├── nvidia-eye.svg             # 749 bytes - NVIDIA eye logo
└── nvidia-logo-white.svg      # 1,265 bytes - NVIDIA wordmark logo (white)
```

## Image Inventory

### `nvidia-eye.svg` (749 bytes)

**Description:** NVIDIA's iconic eye logo in SVG format.

**Usage:**
- Currently not actively used in the application
- Available for future use in branding elements
- May be used as a favicon or loading indicator

**Format:**
- Vector graphic (SVG)
- Scalable to any size without quality loss
- Small file size for fast loading

**Color:** Green (#76B900) - NVIDIA brand color

### `nvidia-logo-white.svg` (1,265 bytes)

**Description:** NVIDIA wordmark logo in white color for use on dark backgrounds.

**Usage:**
- **Header branding:** Displayed in the top-left corner of the application header
- **Component:** `frontend/src/components/layout/Header.tsx`
- **Purpose:** Primary branding element throughout the application

**Location in Code:**
```tsx
// frontend/src/components/layout/Header.tsx (line 243)
<img src="/images/nvidia-logo-white.svg" alt="NVIDIA" className="h-6 w-auto md:h-8" />
```

**Display:**
- Height: 24px (mobile), 32px (desktop)
- Color: White (#FFFFFF)
- Background: Dark theme (#1A1A1A)

**Format:**
- Vector graphic (SVG)
- Optimized for web delivery
- Renders crisp at any resolution

## Public Directory Behavior

Files in `frontend/public/` are served directly at the root URL path:

```
/images/nvidia-logo-white.svg → http://localhost:3000/images/nvidia-logo-white.svg
```

**Key characteristics:**
- No build-time processing or optimization
- Directly accessible via absolute paths
- Cached by browsers based on HTTP headers
- Not included in JavaScript bundle

## Usage in Components

To reference images from the public directory:

```tsx
// Absolute path from public root (recommended)
<img src="/images/nvidia-logo-white.svg" alt="NVIDIA" />

// Do NOT use relative paths from public directory
// ❌ Wrong: <img src="./nvidia-logo.svg" />
// ❌ Wrong: <img src="../public/images/nvidia-logo.svg" />
```

## Image Specifications

### SVG Best Practices

All SVG files in this directory should:
- Be optimized with SVGO or similar tools
- Remove unnecessary metadata and comments
- Use viewBox for responsive sizing
- Avoid embedded raster images
- Use semantic markup where possible

### Current Images

| File                      | Format | Size   | Optimized | Usage Status |
| ------------------------- | ------ | ------ | --------- | ------------ |
| `nvidia-eye.svg`          | SVG    | 749 B  | Yes       | Not used     |
| `nvidia-logo-white.svg`   | SVG    | 1,265 B| Yes       | Active       |

## Adding New Images

When adding images to this directory:

1. **Choose the right location:**
   - Use `public/` for static assets that don't need processing
   - Use `src/assets/` for images imported in components (processed by Vite)

2. **Optimize before adding:**
   ```bash
   # Optimize SVGs
   npx svgo nvidia-logo.svg

   # Optimize PNGs/JPGs
   npx imagemin image.png --out-dir=. --plugin=pngquant
   ```

3. **Follow naming conventions:**
   - Use lowercase with hyphens: `nvidia-logo-white.svg`
   - Be descriptive: Include color/variant if applicable
   - Avoid spaces and special characters

4. **Update this documentation:**
   - Add entry to the image inventory table
   - Document usage and purpose
   - Note if image is actively used in components

## Security Considerations

Public images are:
- **Accessible to anyone:** No authentication required
- **Cacheable:** Browsers may cache for extended periods
- **Version-controlled:** Changes are tracked in git

**Do NOT place in public/**:
- User-uploaded content
- Sensitive or proprietary images
- Images requiring authentication
- Dynamically generated images

## Performance

SVG images in this directory are optimized for performance:

- **File sizes:** < 2KB each (very small)
- **Format:** Vector graphics scale without quality loss
- **Caching:** Browser caches these assets indefinitely
- **HTTP/2:** Multiple images can be fetched in parallel

**Metrics:**
- Total directory size: ~2KB
- Load time: < 10ms on fast connections
- Impact on First Contentful Paint: Minimal

## Related Documentation

- `/frontend/AGENTS.md` - Frontend architecture overview
- `/frontend/src/components/layout/AGENTS.md` - Layout components
- `/frontend/src/components/layout/Header.tsx` - Header component (uses logo)

## Testing

These public images are tested indirectly through:

- **Component tests:** `Header.test.tsx` verifies logo rendering
- **E2E tests:** Visual regression tests ensure branding displays correctly
- **Accessibility tests:** Alt text and semantic markup verified

**Example test:**
```tsx
// frontend/src/components/layout/Header.test.tsx
it('renders NVIDIA logo', () => {
  render(<Header />);
  const logo = screen.getByAlt('NVIDIA');
  expect(logo).toBeInTheDocument();
  expect(logo).toHaveAttribute('src', '/images/nvidia-logo-white.svg');
});
```

## Maintenance

- **Review periodically:** Remove unused images (e.g., `nvidia-eye.svg` if confirmed unused)
- **Update branding:** If NVIDIA brand guidelines change, update logos accordingly
- **Optimize regularly:** Run SVGO on SVGs to ensure minimal file size
- **Monitor usage:** Track which images are actively used vs. deprecated

## License and Attribution

NVIDIA logos are trademarks of NVIDIA Corporation:
- Use only in accordance with NVIDIA branding guidelines
- Do not modify or distort logos
- Maintain proper aspect ratios and clear space

For NVIDIA brand guidelines, see: [NVIDIA Brand Portal](https://www.nvidia.com/en-us/about-nvidia/legal-info/logo-brand-usage/)
