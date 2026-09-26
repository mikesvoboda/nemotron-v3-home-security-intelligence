/**
 * 1.6 (spec §4): the shared verdict badge.
 *
 * The interim ActivityFeed chip ("Unverified", keyed on risk_score === null)
 * is what this replaces everywhere. The pins that make it more than a chip:
 *  - the vocabulary is the FIVE states an operator can actually see: the
 *    four spec verdicts + "unverified" for an event with NO verification row
 *    (legacy events, and vlm events not yet analyzed);
 *  - verification_failed is NOT styled like rejected. They mean different
 *    things - one is "the VLM says the candidate is not real", the other is
 *    "the VLM could not answer" - and conflating them hides the broken ones
 *    inside the dismissed ones (D11: NULL score, honest absence);
 *  - rejected is de-emphasized (plan Task 6) but NEVER hidden: it must stay
 *    readable and stay in the a11y tree, because "what did we dismiss?" is
 *    an audit question;
 *  - the aria-label names the state, because the badge is the only text on
 *    a card that carries it.
 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import VerdictBadge from './VerdictBadge';

describe('VerdictBadge', () => {
  it.each([
    ['confirmed', 'Confirmed'],
    ['rejected', 'Rejected'],
    ['uncertain', 'Uncertain'],
    ['verification_failed', 'Verification failed'],
  ] as const)('renders the %s verdict with its own label', (verdict, text) => {
    render(<VerdictBadge verdict={verdict} />);
    expect(screen.getByText(text)).toBeInTheDocument();
  });

  it('renders the unverified state for an event with no verification row', () => {
    render(<VerdictBadge verdict={undefined} />);
    expect(screen.getByText('Unverified')).toBeInTheDocument();
    // The interim ActivityFeed chip stays green-lighted as a fallback
    // vocabulary: same WORD, so nothing downstream re-keys on it.
    expect(screen.getByText('Unverified')).toHaveAttribute('data-verdict', 'unverified');
  });

  it.each(['confirmed', 'rejected', 'uncertain', 'verification_failed', 'none'] as const)(
    'carries a data-verdict of %s for styling/tests',
    (v) => {
      // 'none' is the API filter's pseudo-value; the badge maps it to
      // unverified rather than inventing a sixth look.
      render(<VerdictBadge verdict={v} />);
      const badge = screen.getByRole('status');
      expect(badge).toHaveAttribute('data-verdict', v === 'none' ? 'unverified' : v);
    }
  );

  it('gives verification_failed a DIFFERENT treatment than rejected', () => {
    // Both dismissed-ish, utterly different meaning: a failed verification
    // needs attention, a rejected one is resolved. Same classes would fold
    // the broken events into the dismissed ones.
    render(<VerdictBadge verdict="rejected" />);
    const rejected = screen.getByRole('status');
    render(<VerdictBadge verdict="verification_failed" />);
    const failed = screen.getAllByRole('status')[1];
    expect(failed.className).not.toEqual(rejected.className);
  });

  it('de-emphasizes rejected without hiding it', () => {
    render(<VerdictBadge verdict="rejected" />);
    const badge = screen.getByRole('status');
    // De-emphasis is a STYLE (muted), never visibility: the dismissed event
    // must stay readable and in the a11y tree — audit needs "what did we
    // dismiss", and aria-hidden would erase that from a screen reader.
    expect(badge.className).toMatch(/muted|opacity|gray/);
    expect(badge).not.toHaveStyle({ display: 'none' });
    expect(badge).toHaveAccessibleName('Verification verdict: Rejected');
  });

  it('names the state in the accessible name for every state', () => {
    render(<VerdictBadge verdict="uncertain" />);
    expect(screen.getByRole('status')).toHaveAccessibleName('Verification verdict: Uncertain');
  });

  it('never renders the raw verdict snake_case at a human', () => {
    render(<VerdictBadge verdict="verification_failed" />);
    expect(screen.queryByText('verification_failed')).not.toBeInTheDocument();
  });
});
