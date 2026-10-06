/**
 * ISS-001: the shared notify-decision badge.
 *
 * The pins that make it more than a chip:
 *  - exactly TWO renderable states (the OD-31 narrow reading): notify=true
 *    "Notifies" and notify=false "Not notifying". A recorded decision not
 *    to page is a REAL answer and must render - "why was I not paged?" is
 *    an audit question, and hiding false would silently fold it into the
 *    no-decision mass;
 *  - absence (undefined/null) renders NOTHING: absence is not False. The
 *    REST field's exclude_if and the WS frame's absent key both mean "no
 *    decision was ever made" (legacy events, replay rows, other emitters) -
 *    inventing a third visual state there would mint a fake decision;
 *  - the colors stay out of the risk palette (VerdictBadge's doctrine):
 *    this is a delivery-status marker, and green/red here would read as
 *    "safe/dangerous";
 *  - the aria-label names the state, like the sibling badges.
 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import NotifyBadge from './NotifyBadge';

describe('NotifyBadge', () => {
  it('renders "Notifies" for a recorded decision to notify', () => {
    render(<NotifyBadge notify={true} />);
    expect(screen.getByText('Notifies')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveAttribute('data-notify', 'yes');
    expect(screen.getByRole('status')).toHaveAccessibleName('Notification decision: Notifies');
  });

  it('renders "Not notifying" for a recorded decision NOT to notify', () => {
    render(<NotifyBadge notify={false} />);
    expect(screen.getByText('Not notifying')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveAttribute('data-notify', 'no');
    expect(screen.getByRole('status')).toHaveAccessibleName('Notification decision: Not notifying');
  });

  it('de-emphasizes "Not notifying" without hiding it', () => {
    render(<NotifyBadge notify={false} />);
    const badge = screen.getByRole('status');
    // Muted is a STYLE, never visibility - the decision must stay readable
    // and in the a11y tree (the VerdictBadge rejected rule, same reason).
    expect(badge.className).toMatch(/gray|opacity/);
    expect(badge).not.toHaveStyle({ display: 'none' });
  });

  it.each([
    ['undefined', undefined],
    ['null', null],
  ])('renders NOTHING for %s - absence is not a decision', (_name, value) => {
    const { container } = render(<NotifyBadge notify={value} />);
    expect(container).toBeEmptyDOMElement();
    // Not "renders nothing visibly" - NOTHING in the tree. A hidden third
    // state would be just as fake as a rendered one.
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('never uses the risk palette (delivery status is not a severity claim)', () => {
    render(<NotifyBadge notify={true} />);
    const yes = screen.getByRole('status');
    expect(yes.className).toMatch(/blue/);
    render(<NotifyBadge notify={false} />);
    const no = screen.getAllByRole('status')[1];
    // No red/green on either tone - those classes mean risk level app-wide.
    for (const badge of [yes, no]) {
      expect(badge.className).not.toMatch(/red|green|emerald|rose/);
    }
  });
});
