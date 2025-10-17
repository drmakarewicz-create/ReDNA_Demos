export const metadata = {
  title: 'LLM Benchmarks - ReDNA DevX',
  description: 'Inspect backlog, run batches, and review reports for the LLM benchmarking suite.',
};

import LLMBenchmarksPageClient from './page.client';

export default function LLMBenchmarksPage() {
  return <LLMBenchmarksPageClient />;
}
