import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { OpenQuestionsPanel } from '../open-questions-panel';
import type { NextQuestionCandidate } from '@/lib/curiosityClient';

const sampleQuestion: NextQuestionCandidate = {
  question_text: 'What time do you usually go to bed?',
  target_trait_id: 'PaDNA.Sleep.Chronotype',
  confidence: 0.72,
  graph_path: ['node_a', 'edge_b', 'node_c'],
  rationale: 'High uncertainty on Chronotype (u=0.72)',
};

describe('OpenQuestionsPanel', () => {
  it('renders a single question with Ask button', () => {
    const handleAsk = jest.fn();
    render(
      <OpenQuestionsPanel
        userId="demo-user"
        questions={[sampleQuestion]}
        loading={false}
        error={null}
        onRetry={jest.fn()}
        onAsk={handleAsk}
      />
    );

    expect(screen.getByText('Open Questions')).toBeInTheDocument();
    expect(screen.getByText(sampleQuestion.question_text)).toBeInTheDocument();
    expect(screen.getByText(sampleQuestion.target_trait_id)).toBeInTheDocument();
    expect(screen.getByText('72%')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Ask'));
    expect(handleAsk).toHaveBeenCalledWith(sampleQuestion);
  });

  it('renders empty state when no questions are available', () => {
    render(
      <OpenQuestionsPanel
        userId="demo-user"
        questions={[]}
        loading={false}
        error={null}
        onRetry={jest.fn()}
        onAsk={jest.fn()}
      />
    );

    expect(
      screen.getByText(/No open questions right now/i)
    ).toBeInTheDocument();
  });

  it('renders error state when API fails', () => {
    render(
      <OpenQuestionsPanel
        userId="demo-user"
        questions={[]}
        loading={false}
        error="API error"
        onRetry={jest.fn()}
        onAsk={jest.fn()}
      />
    );

    expect(screen.getByText('API error')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Retry/i })).toBeInTheDocument();
  });
});

