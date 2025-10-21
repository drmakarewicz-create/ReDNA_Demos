import { adaptCuriosity, adaptRR } from '../provenanceClient';

describe('adaptRR', () => {
  it('converts rr_meta scale 0_1000 to percentile', () => {
    const result = adaptRR(undefined, { rr_raw: 820, scale: '0_1000' });
    expect(result).toBe(82);
  });

  it('clamps rr to 0-100 when provided directly', () => {
    expect(adaptRR(110, undefined)).toBe(100);
    expect(adaptRR(-5, undefined)).toBe(0);
  });
});

describe('adaptCuriosity', () => {
  it('clamps provided curiosity to 0-100', () => {
    expect(adaptCuriosity(140, undefined)).toBe(100);
    expect(adaptCuriosity(-20, undefined)).toBe(0);
  });

  it('derives curiosity from RR when missing', () => {
    expect(adaptCuriosity(undefined, 82)).toBe(18);
  });
});
