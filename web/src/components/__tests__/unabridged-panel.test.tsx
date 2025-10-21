import React from 'react';
import { render, screen, within } from '@testing-library/react';
import type { UnabridgedSnapshot } from '@/lib/api';
import { UnabridgedPanel } from '../unabridged-panel';

jest.mock('../../lib/perf-hud', () => ({
  updateVirtualizerMetrics: jest.fn(),
  removeVirtualizerMetrics: jest.fn(),
}));

const mockVirtualItems = [
  { key: 0, index: 0, start: 0, size: 68 },
  { key: 1, index: 1, start: 68, size: 68 },
  { key: 2, index: 2, start: 136, size: 68 },
];

jest.mock('@tanstack/react-virtual', () => ({
  useVirtualizer: jest.fn(() => ({
    getVirtualItems: () => mockVirtualItems,
    getTotalSize: () => mockVirtualItems.length * 68,
    measureElement: jest.fn(),
  })),
}));

jest.mock('../provenance/trait-provenance-drawer', () => () => null);
jest.mock('../why/WhyCardModal', () => ({
  WhyCardModal: () => null,
}));

const baseSnapshot: UnabridgedSnapshot = {
  user_id: 'demo-user',
  count: 3,
  traits: [
    {
      trait_id: 'PaDNA.LowCuriosity',
      value: 'Value A',
      ucn: 0.3,
      rr: null,
      rr_meta: { rr_raw: 820, scale: '0_1000' },
      curiosity: null,
      reasons: [],
      badges: [],
      last_observed: '2025-10-20T12:00:00Z',
    },
    {
      trait_id: 'PaDNA.HighCuriosity',
      value: 'Value B',
      ucn: 0.2,
      rr: 12,
      curiosity: 88,
      reasons: [],
      badges: [],
      last_observed: '2025-10-21T12:00:00Z',
    },
    {
      trait_id: 'PaDNA.MidCuriosity',
      value: 'Value C',
      ucn: 0.55,
      rr: 39,
      curiosity: 61,
      reasons: [],
      badges: [],
      last_observed: '2025-10-19T12:00:00Z',
    },
  ],
};

describe('UnabridgedPanel', () => {
  it('sorts rows by curiosity descending by default', () => {
    render(<UnabridgedPanel snapshot={baseSnapshot} />);

    const rows = screen.getAllByRole('row');
    const firstDataRow = rows[1];
    expect(within(firstDataRow).getByText('PaDNA.HighCuriosity')).toBeInTheDocument();
  });

  it('renders UCN and Curiosity bars with expected widths', () => {
    render(<UnabridgedPanel snapshot={baseSnapshot} />);

    const ucnBar = screen.getByTestId('ucn-bar-PaDNA-HighCuriosity');
    expect(ucnBar).toHaveStyle({ width: '20%' });

    const curiosityBar = screen.getByTestId('curiosity-bar-PaDNA-HighCuriosity');
    expect(curiosityBar).toHaveStyle({ width: '88%' });

    const rrBar = screen.getByTestId('rr-bar-PaDNA-LowCuriosity');
    expect(rrBar).toHaveStyle({ width: '82%' });
  });
});
