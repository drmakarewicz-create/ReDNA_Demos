import React from 'react';
import { render, screen } from '@testing-library/react';
import { WhyCardPanel } from '../why-card-panel';
import type { WhyCard } from '@/lib/provenanceClient';

const buildCard = (overrides?: Partial<WhyCard>): WhyCard => ({
  id: 'wc_123',
  user_id: 'demo',
  trait_id: 'PaDNA.Chronotype',
  what: 'You consistently wake up at 6am.',
  why: 'High RR score and low uncertainty from repeated observations.',
  next: 'Log your evening energy levels for one week.',
  rr: null,
  rr_meta: { rr_raw: 720, scale: '0_1000' },
  curiosity: null,
  ucn: { u: 0.3, c: 0.6, n: 0.7 },
  created_at: '2025-10-25T12:34:56Z',
  metadata: {},
  ...overrides,
});

describe('WhyCardPanel', () => {
  it('renders the Why-Card content when provided', () => {
    const card = buildCard();

    render(<WhyCardPanel loading={false} error={null} card={card} traitId={card.trait_id} />);

    expect(screen.getByText('Why-Card (Explainability)')).toBeInTheDocument();
    expect(screen.getByText('What')).toBeInTheDocument();
    expect(screen.getByText(card.what)).toBeInTheDocument();
    expect(screen.getByText('Why')).toBeInTheDocument();
    expect(screen.getByText(card.why)).toBeInTheDocument();
    expect(screen.getByText('Next')).toBeInTheDocument();
    expect(screen.getByText(card.next)).toBeInTheDocument();
    expect(screen.getByText('RR')).toBeInTheDocument();
    expect(screen.getByText('72.0%')).toBeInTheDocument();
    expect(screen.getByText('Cur')).toBeInTheDocument();
    expect(screen.getByText('28.0%')).toBeInTheDocument();
    expect(screen.getByLabelText('RR metadata')).toBeInTheDocument();
    expect(screen.getByText('U')).toBeInTheDocument();
    expect(screen.getByText('0.30')).toBeInTheDocument();
    expect(screen.getByText('C')).toBeInTheDocument();
    expect(screen.getByText('0.60')).toBeInTheDocument();
    expect(screen.getByText('N')).toBeInTheDocument();
    expect(screen.getByText('0.70')).toBeInTheDocument();
  });

  it('shows the empty-state hint when no card is available', () => {
    render(<WhyCardPanel loading={false} error={null} card={null} traitId="PaDNA.Chronotype" />);

    expect(
      screen.getByText(/No Why-Card yet\. Promote this trait or provide more evidence/i)
    ).toBeInTheDocument();
  });
});
