import { render, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import BoundingBoxOverlay, { BoundingBox, arePropsEqual } from './BoundingBoxOverlay';

describe('BoundingBoxOverlay', () => {
  const mockBoxes: BoundingBox[] = [
    {
      x: 100,
      y: 100,
      width: 200,
      height: 300,
      label: 'person',
      confidence: 0.95,
    },
    {
      x: 400,
      y: 200,
      width: 150,
      height: 100,
      label: 'car',
      confidence: 0.87,
    },
    {
      x: 50,
      y: 50,
      width: 80,
      height: 80,
      label: 'dog',
      confidence: 0.72,
    },
  ];

  it('renders without crashing', () => {
    const { container } = render(
      <BoundingBoxOverlay boxes={mockBoxes} imageWidth={800} imageHeight={600} />
    );
    expect(container.querySelector('svg')).toBeInTheDocument();
  });

  it('renders correct number of bounding boxes', () => {
    const { container } = render(
      <BoundingBoxOverlay boxes={mockBoxes} imageWidth={800} imageHeight={600} />
    );
    const rects = container.querySelectorAll('rect[fill="none"]');
    expect(rects.length).toBe(3);
  });

  it('applies correct dimensions to SVG viewBox', () => {
    const { container } = render(
      <BoundingBoxOverlay boxes={mockBoxes} imageWidth={1920} imageHeight={1080} />
    );
    const svg = container.querySelector('svg');
    expect(svg?.getAttribute('viewBox')).toBe('0 0 1920 1080');
  });

  it('renders bounding boxes with correct positions and dimensions', () => {
    const { container } = render(
      <BoundingBoxOverlay boxes={[mockBoxes[0]]} imageWidth={800} imageHeight={600} />
    );
    const rect = container.querySelector('rect[fill="none"]');
    expect(rect?.getAttribute('x')).toBe('100');
    expect(rect?.getAttribute('y')).toBe('100');
    expect(rect?.getAttribute('width')).toBe('200');
    expect(rect?.getAttribute('height')).toBe('300');
  });

  it('applies default colors based on object label', () => {
    const { container } = render(
      <BoundingBoxOverlay boxes={mockBoxes} imageWidth={800} imageHeight={600} />
    );
    const rects = container.querySelectorAll('rect[fill="none"]');

    // person = red (#ef4444)
    expect(rects[0].getAttribute('stroke')).toBe('#ef4444');

    // car = blue (#3b82f6)
    expect(rects[1].getAttribute('stroke')).toBe('#3b82f6');

    // dog = amber (#f59e0b)
    expect(rects[2].getAttribute('stroke')).toBe('#f59e0b');
  });

  it('uses custom color when provided', () => {
    const customBoxes: BoundingBox[] = [
      {
        x: 100,
        y: 100,
        width: 200,
        height: 200,
        label: 'custom',
        confidence: 0.9,
        color: '#ff00ff',
      },
    ];

    const { container } = render(
      <BoundingBoxOverlay boxes={customBoxes} imageWidth={800} imageHeight={600} />
    );
    const rect = container.querySelector('rect[fill="none"]');
    expect(rect?.getAttribute('stroke')).toBe('#ff00ff');
  });

  it('displays labels by default', () => {
    const { container } = render(
      <BoundingBoxOverlay boxes={[mockBoxes[0]]} imageWidth={800} imageHeight={600} />
    );
    const text = container.querySelector('text');
    expect(text?.textContent).toContain('person');
  });

  it('hides labels when showLabels is false', () => {
    const { container } = render(
      <BoundingBoxOverlay
        boxes={[mockBoxes[0]]}
        imageWidth={800}
        imageHeight={600}
        showLabels={false}
      />
    );
    const text = container.querySelector('text');
    expect(text).not.toBeInTheDocument();
  });

  it('displays confidence percentage by default', () => {
    const { container } = render(
      <BoundingBoxOverlay boxes={[mockBoxes[0]]} imageWidth={800} imageHeight={600} />
    );
    const text = container.querySelector('text');
    expect(text?.textContent).toContain('95%');
  });

  it('hides confidence when showConfidence is false', () => {
    const { container } = render(
      <BoundingBoxOverlay
        boxes={[mockBoxes[0]]}
        imageWidth={800}
        imageHeight={600}
        showConfidence={false}
      />
    );
    const text = container.querySelector('text');
    expect(text?.textContent).toBe('person');
    expect(text?.textContent).not.toContain('95%');
  });

  it('formats confidence correctly', () => {
    const testBoxes: BoundingBox[] = [
      { ...mockBoxes[0], confidence: 0.123 },
      { ...mockBoxes[1], confidence: 0.999 },
      { ...mockBoxes[2], confidence: 0.5 },
    ];

    const { container } = render(
      <BoundingBoxOverlay boxes={testBoxes} imageWidth={800} imageHeight={600} />
    );
    const texts = container.querySelectorAll('text');

    expect(texts[0].textContent).toContain('12%');
    expect(texts[1].textContent).toContain('100%');
    expect(texts[2].textContent).toContain('50%');
  });

  it('filters boxes by minimum confidence threshold', () => {
    const { container } = render(
      <BoundingBoxOverlay
        boxes={mockBoxes}
        imageWidth={800}
        imageHeight={600}
        minConfidence={0.8}
      />
    );
    const rects = container.querySelectorAll('rect[fill="none"]');
    // Only person (0.95) and car (0.87) should be shown, dog (0.72) filtered out
    expect(rects.length).toBe(2);
  });

  it('shows all boxes when minConfidence is 0', () => {
    const { container } = render(
      <BoundingBoxOverlay boxes={mockBoxes} imageWidth={800} imageHeight={600} minConfidence={0} />
    );
    const rects = container.querySelectorAll('rect[fill="none"]');
    expect(rects.length).toBe(3);
  });

  it('shows no boxes when minConfidence is too high', () => {
    const { container } = render(
      <BoundingBoxOverlay
        boxes={mockBoxes}
        imageWidth={800}
        imageHeight={600}
        minConfidence={0.99}
      />
    );
    const svg = container.querySelector('svg');
    expect(svg).not.toBeInTheDocument();
  });

  it('calls onClick handler when box is clicked', () => {
    const handleClick = vi.fn();
    const { container } = render(
      <BoundingBoxOverlay
        boxes={[mockBoxes[0]]}
        imageWidth={800}
        imageHeight={600}
        onClick={handleClick}
      />
    );

    const rect = container.querySelector('rect[fill="none"]');
    fireEvent.click(rect!);

    expect(handleClick).toHaveBeenCalledTimes(1);
    expect(handleClick).toHaveBeenCalledWith(mockBoxes[0]);
  });

  it('calls onClick with correct box when multiple boxes are present', () => {
    const handleClick = vi.fn();
    const { container } = render(
      <BoundingBoxOverlay
        boxes={mockBoxes}
        imageWidth={800}
        imageHeight={600}
        onClick={handleClick}
      />
    );

    const rects = container.querySelectorAll('rect[fill="none"]');

    fireEvent.click(rects[1]);
    expect(handleClick).toHaveBeenCalledWith(mockBoxes[1]);

    fireEvent.click(rects[2]);
    expect(handleClick).toHaveBeenCalledWith(mockBoxes[2]);
  });

  it('adds cursor pointer class when onClick is provided', () => {
    const { container } = render(
      <BoundingBoxOverlay
        boxes={[mockBoxes[0]]}
        imageWidth={800}
        imageHeight={600}
        onClick={() => {}}
      />
    );

    const rect = container.querySelector('rect[fill="none"]');
    expect(rect?.classList.contains('cursor-pointer')).toBe(true);
  });

  it('does not add cursor pointer class when onClick is not provided', () => {
    const { container } = render(
      <BoundingBoxOverlay boxes={[mockBoxes[0]]} imageWidth={800} imageHeight={600} />
    );

    const rect = container.querySelector('rect[fill="none"]');
    expect(rect?.classList.contains('cursor-pointer')).toBe(false);
  });

  it('returns null when imageWidth is 0', () => {
    const { container } = render(
      <BoundingBoxOverlay boxes={mockBoxes} imageWidth={0} imageHeight={600} />
    );
    expect(container.querySelector('svg')).not.toBeInTheDocument();
  });

  it('returns null when imageHeight is 0', () => {
    const { container } = render(
      <BoundingBoxOverlay boxes={mockBoxes} imageWidth={800} imageHeight={0} />
    );
    expect(container.querySelector('svg')).not.toBeInTheDocument();
  });

  it('returns null when imageWidth is negative', () => {
    const { container } = render(
      <BoundingBoxOverlay boxes={mockBoxes} imageWidth={-800} imageHeight={600} />
    );
    expect(container.querySelector('svg')).not.toBeInTheDocument();
  });

  it('returns null when boxes array is empty', () => {
    const { container } = render(
      <BoundingBoxOverlay boxes={[]} imageWidth={800} imageHeight={600} />
    );
    expect(container.querySelector('svg')).not.toBeInTheDocument();
  });

  it('handles unknown object labels with default color', () => {
    const unknownBox: BoundingBox = {
      x: 100,
      y: 100,
      width: 200,
      height: 200,
      label: 'unknown_object',
      confidence: 0.85,
    };

    const { container } = render(
      <BoundingBoxOverlay boxes={[unknownBox]} imageWidth={800} imageHeight={600} />
    );

    const rect = container.querySelector('rect[fill="none"]');
    // Should use default gray color (#6b7280)
    expect(rect?.getAttribute('stroke')).toBe('#6b7280');
  });

  it('renders label background with correct color', () => {
    const { container } = render(
      <BoundingBoxOverlay boxes={[mockBoxes[0]]} imageWidth={800} imageHeight={600} />
    );

    const labelBackground = container.querySelectorAll('rect[opacity="0.9"]')[0];
    expect(labelBackground?.getAttribute('fill')).toBe('#ef4444');
  });

  it('positions label above bounding box', () => {
    const box: BoundingBox = {
      x: 100,
      y: 200,
      width: 150,
      height: 150,
      label: 'test',
      confidence: 0.9,
    };

    const { container } = render(
      <BoundingBoxOverlay boxes={[box]} imageWidth={800} imageHeight={600} />
    );

    const labelBackground = container.querySelector('rect[opacity="0.9"]');
    // Label should be 28 pixels above the box
    expect(labelBackground?.getAttribute('y')).toBe(String(box.y - 28));
  });

  it('renders with responsive scaling', () => {
    const { container } = render(
      <BoundingBoxOverlay boxes={mockBoxes} imageWidth={800} imageHeight={600} />
    );

    const svg = container.querySelector('svg');
    expect(svg?.classList.contains('w-full')).toBe(true);
    expect(svg?.classList.contains('h-full')).toBe(true);
    expect(svg?.getAttribute('preserveAspectRatio')).toBe('none');
  });

  it('applies correct z-index for overlay positioning', () => {
    const { container } = render(
      <BoundingBoxOverlay boxes={mockBoxes} imageWidth={800} imageHeight={600} />
    );

    const svg = container.querySelector('svg');
    expect(svg?.style.zIndex).toBe('10');
  });

  it('renders multiple boxes with different labels and confidence levels', () => {
    const diverseBoxes: BoundingBox[] = [
      { x: 10, y: 10, width: 50, height: 50, label: 'person', confidence: 0.99 },
      { x: 100, y: 100, width: 100, height: 100, label: 'car', confidence: 0.85 },
      { x: 300, y: 300, width: 75, height: 75, label: 'cat', confidence: 0.72 },
      { x: 500, y: 200, width: 120, height: 80, label: 'package', confidence: 0.91 },
    ];

    const { container } = render(
      <BoundingBoxOverlay boxes={diverseBoxes} imageWidth={1920} imageHeight={1080} />
    );

    const rects = container.querySelectorAll('rect[fill="none"]');
    const texts = container.querySelectorAll('text');

    expect(rects.length).toBe(4);
    expect(texts.length).toBe(4);

    expect(texts[0].textContent).toContain('person');
    expect(texts[1].textContent).toContain('car');
    expect(texts[2].textContent).toContain('cat');
    expect(texts[3].textContent).toContain('package');
  });

  it('handles hover state changes when onClick is provided', () => {
    const { container } = render(
      <BoundingBoxOverlay
        boxes={[mockBoxes[0]]}
        imageWidth={800}
        imageHeight={600}
        onClick={() => {}}
      />
    );

    const rect = container.querySelector('rect[fill="none"]') as SVGRectElement;

    // Initial stroke width
    expect(rect.getAttribute('stroke-width')).toBe('3');

    // Simulate hover
    fireEvent.mouseEnter(rect);
    expect(rect.getAttribute('stroke-width')).toBe('5');

    // Simulate mouse leave
    fireEvent.mouseLeave(rect);
    expect(rect.getAttribute('stroke-width')).toBe('3');
  });

  it('has absolute positioning for overlay', () => {
    const { container } = render(
      <BoundingBoxOverlay boxes={mockBoxes} imageWidth={800} imageHeight={600} />
    );

    const svg = container.querySelector('svg');
    expect(svg?.classList.contains('absolute')).toBe(true);
    expect(svg?.classList.contains('inset-0')).toBe(true);
  });
});

// =============================================================================
// React.memo Optimization Tests (NEM-1120)
// =============================================================================

describe('arePropsEqual - React.memo custom comparator', () => {
  const baseBox: BoundingBox = {
    x: 100,
    y: 100,
    width: 200,
    height: 300,
    label: 'person',
    confidence: 0.95,
  };

  const baseProps = {
    boxes: [baseBox],
    imageWidth: 800,
    imageHeight: 600,
    showLabels: true,
    showConfidence: true,
    minConfidence: 0,
    onClick: undefined,
  };

  it('returns true when props are identical', () => {
    expect(arePropsEqual(baseProps, baseProps)).toBe(true);
  });

  it('returns true when boxes array has same content', () => {
    const prevProps = { ...baseProps, boxes: [{ ...baseBox }] };
    const nextProps = { ...baseProps, boxes: [{ ...baseBox }] };
    expect(arePropsEqual(prevProps, nextProps)).toBe(true);
  });

  it('returns false when boxes array length changes', () => {
    const prevProps = { ...baseProps, boxes: [baseBox] };
    const nextProps = { ...baseProps, boxes: [baseBox, baseBox] };
    expect(arePropsEqual(prevProps, nextProps)).toBe(false);
  });

  it('returns false when box x coordinate changes', () => {
    const prevProps = { ...baseProps, boxes: [{ ...baseBox }] };
    const nextProps = { ...baseProps, boxes: [{ ...baseBox, x: 150 }] };
    expect(arePropsEqual(prevProps, nextProps)).toBe(false);
  });

  it('returns false when box y coordinate changes', () => {
    const prevProps = { ...baseProps, boxes: [{ ...baseBox }] };
    const nextProps = { ...baseProps, boxes: [{ ...baseBox, y: 150 }] };
    expect(arePropsEqual(prevProps, nextProps)).toBe(false);
  });

  it('returns false when box width changes', () => {
    const prevProps = { ...baseProps, boxes: [{ ...baseBox }] };
    const nextProps = { ...baseProps, boxes: [{ ...baseBox, width: 250 }] };
    expect(arePropsEqual(prevProps, nextProps)).toBe(false);
  });

  it('returns false when box height changes', () => {
    const prevProps = { ...baseProps, boxes: [{ ...baseBox }] };
    const nextProps = { ...baseProps, boxes: [{ ...baseBox, height: 350 }] };
    expect(arePropsEqual(prevProps, nextProps)).toBe(false);
  });

  it('returns false when box label changes', () => {
    const prevProps = { ...baseProps, boxes: [{ ...baseBox }] };
    const nextProps = { ...baseProps, boxes: [{ ...baseBox, label: 'car' }] };
    expect(arePropsEqual(prevProps, nextProps)).toBe(false);
  });

  it('returns false when box confidence changes', () => {
    const prevProps = { ...baseProps, boxes: [{ ...baseBox }] };
    const nextProps = { ...baseProps, boxes: [{ ...baseBox, confidence: 0.8 }] };
    expect(arePropsEqual(prevProps, nextProps)).toBe(false);
  });

  it('returns false when box color changes', () => {
    const prevProps = { ...baseProps, boxes: [{ ...baseBox }] };
    const nextProps = { ...baseProps, boxes: [{ ...baseBox, color: '#ff0000' }] };
    expect(arePropsEqual(prevProps, nextProps)).toBe(false);
  });

  it('returns false when imageWidth changes', () => {
    const prevProps = { ...baseProps };
    const nextProps = { ...baseProps, imageWidth: 1024 };
    expect(arePropsEqual(prevProps, nextProps)).toBe(false);
  });

  it('returns false when imageHeight changes', () => {
    const prevProps = { ...baseProps };
    const nextProps = { ...baseProps, imageHeight: 768 };
    expect(arePropsEqual(prevProps, nextProps)).toBe(false);
  });

  it('returns false when showLabels changes', () => {
    const prevProps = { ...baseProps };
    const nextProps = { ...baseProps, showLabels: false };
    expect(arePropsEqual(prevProps, nextProps)).toBe(false);
  });

  it('returns false when showConfidence changes', () => {
    const prevProps = { ...baseProps };
    const nextProps = { ...baseProps, showConfidence: false };
    expect(arePropsEqual(prevProps, nextProps)).toBe(false);
  });

  it('returns false when minConfidence changes', () => {
    const prevProps = { ...baseProps };
    const nextProps = { ...baseProps, minConfidence: 0.5 };
    expect(arePropsEqual(prevProps, nextProps)).toBe(false);
  });

  it('returns true when onClick is the same function reference', () => {
    const handler = vi.fn();
    const prevProps = { ...baseProps, onClick: handler };
    const nextProps = { ...baseProps, onClick: handler };
    expect(arePropsEqual(prevProps, nextProps)).toBe(true);
  });

  it('returns false when onClick function reference changes', () => {
    const prevProps = { ...baseProps, onClick: vi.fn() };
    const nextProps = { ...baseProps, onClick: vi.fn() };
    expect(arePropsEqual(prevProps, nextProps)).toBe(false);
  });

  it('returns true when both onClick are undefined', () => {
    const prevProps = { ...baseProps, onClick: undefined };
    const nextProps = { ...baseProps, onClick: undefined };
    expect(arePropsEqual(prevProps, nextProps)).toBe(true);
  });

  it('handles multiple boxes correctly', () => {
    const box1: BoundingBox = {
      x: 10,
      y: 10,
      width: 50,
      height: 50,
      label: 'person',
      confidence: 0.9,
    };
    const box2: BoundingBox = {
      x: 100,
      y: 100,
      width: 80,
      height: 80,
      label: 'car',
      confidence: 0.85,
    };

    const prevProps = { ...baseProps, boxes: [box1, box2] };
    const nextProps = { ...baseProps, boxes: [{ ...box1 }, { ...box2 }] };
    expect(arePropsEqual(prevProps, nextProps)).toBe(true);
  });

  it('detects change in second box of multiple boxes', () => {
    const box1: BoundingBox = {
      x: 10,
      y: 10,
      width: 50,
      height: 50,
      label: 'person',
      confidence: 0.9,
    };
    const box2: BoundingBox = {
      x: 100,
      y: 100,
      width: 80,
      height: 80,
      label: 'car',
      confidence: 0.85,
    };

    const prevProps = { ...baseProps, boxes: [box1, box2] };
    const nextProps = { ...baseProps, boxes: [{ ...box1 }, { ...box2, x: 150 }] };
    expect(arePropsEqual(prevProps, nextProps)).toBe(false);
  });

  it('handles empty boxes arrays', () => {
    const prevProps = { ...baseProps, boxes: [] };
    const nextProps = { ...baseProps, boxes: [] };
    expect(arePropsEqual(prevProps, nextProps)).toBe(true);
  });
});

describe('BoundingBoxOverlay memoization', () => {
  it('is wrapped with React.memo', () => {
    // React.memo components have a $$typeof of REACT_MEMO_TYPE
    // We can verify by checking the component's type property
    expect(BoundingBoxOverlay).toHaveProperty('$$typeof');
    // Memo components also have a compare property if a custom comparator is provided
    expect(BoundingBoxOverlay).toHaveProperty('compare', arePropsEqual);
  });
});

// =============================================================================
// Snapshot Tests (NEM-1428)
// =============================================================================

describe('BoundingBoxOverlay snapshots', () => {
  const mockBoxes: BoundingBox[] = [
    {
      x: 100,
      y: 100,
      width: 200,
      height: 300,
      label: 'person',
      confidence: 0.95,
    },
    {
      x: 400,
      y: 200,
      width: 150,
      height: 100,
      label: 'car',
      confidence: 0.87,
    },
  ];

  it('renders with single bounding box', () => {
    const { container } = render(
      <BoundingBoxOverlay boxes={[mockBoxes[0]]} imageWidth={800} imageHeight={600} />
    );
    expect(container.firstChild).toMatchSnapshot();
  });

  it('renders with multiple bounding boxes', () => {
    const { container } = render(
      <BoundingBoxOverlay boxes={mockBoxes} imageWidth={800} imageHeight={600} />
    );
    expect(container.firstChild).toMatchSnapshot();
  });

  it('renders with labels hidden', () => {
    const { container } = render(
      <BoundingBoxOverlay boxes={mockBoxes} imageWidth={800} imageHeight={600} showLabels={false} />
    );
    expect(container.firstChild).toMatchSnapshot();
  });

  it('renders with confidence hidden', () => {
    const { container } = render(
      <BoundingBoxOverlay
        boxes={mockBoxes}
        imageWidth={800}
        imageHeight={600}
        showConfidence={false}
      />
    );
    expect(container.firstChild).toMatchSnapshot();
  });

  it('renders with custom colors', () => {
    const customBoxes: BoundingBox[] = [
      {
        x: 100,
        y: 100,
        width: 200,
        height: 200,
        label: 'custom',
        confidence: 0.9,
        color: '#ff00ff',
      },
      {
        x: 400,
        y: 400,
        width: 150,
        height: 150,
        label: 'another',
        confidence: 0.85,
        color: '#00ffff',
      },
    ];

    const { container } = render(
      <BoundingBoxOverlay boxes={customBoxes} imageWidth={800} imageHeight={600} />
    );
    expect(container.firstChild).toMatchSnapshot();
  });

  it('renders with different image dimensions', () => {
    const { container } = render(
      <BoundingBoxOverlay boxes={mockBoxes} imageWidth={1920} imageHeight={1080} />
    );
    expect(container.firstChild).toMatchSnapshot();
  });

  it('renders with minConfidence filter', () => {
    const { container } = render(
      <BoundingBoxOverlay
        boxes={mockBoxes}
        imageWidth={800}
        imageHeight={600}
        minConfidence={0.9}
      />
    );
    expect(container.firstChild).toMatchSnapshot();
  });

  it('renders with various object types', () => {
    const diverseBoxes: BoundingBox[] = [
      { x: 10, y: 10, width: 50, height: 50, label: 'person', confidence: 0.99 },
      { x: 100, y: 100, width: 100, height: 100, label: 'car', confidence: 0.85 },
      { x: 300, y: 300, width: 75, height: 75, label: 'cat', confidence: 0.72 },
      { x: 500, y: 200, width: 120, height: 80, label: 'package', confidence: 0.91 },
    ];

    const { container } = render(
      <BoundingBoxOverlay boxes={diverseBoxes} imageWidth={1920} imageHeight={1080} />
    );
    expect(container.firstChild).toMatchSnapshot();
  });

  it('renders with unknown object type (default color)', () => {
    const unknownBox: BoundingBox = {
      x: 100,
      y: 100,
      width: 200,
      height: 200,
      label: 'unknown_object',
      confidence: 0.85,
    };

    const { container } = render(
      <BoundingBoxOverlay boxes={[unknownBox]} imageWidth={800} imageHeight={600} />
    );
    expect(container.firstChild).toMatchSnapshot();
  });
});
