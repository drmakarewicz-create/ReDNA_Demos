import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { OnboardingChat } from '../onboarding/onboarding-chat';

const DEFAULT_USER_ID = 'tester';

function createJsonResponse(
  payload: any,
  init?: { status?: number; headers?: Record<string, string> }
): any {
  const status = init?.status ?? 200;
  const headersInit = {
    'content-type': 'application/json',
    ...(init?.headers ?? {}),
  };
  const headerEntries = Object.entries(headersInit).map(([key, value]) => [
    key.toLowerCase(),
    value,
  ]);
  const headersMap = new Map<string, string>(headerEntries);
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: {
      get: (key: string) => headersMap.get(key.toLowerCase()) ?? null,
    },
    json: jest.fn().mockResolvedValue(payload),
  };
}

function makeIngestResponse() {
  return {
    snapshot: {
      traits: [
        {
          trait_id: 'PaDNA.Sleep.Chronotype',
          value: 'Evening Owl',
        },
      ],
    },
    rescore: {
      rr_by_trait: {
        'PaDNA.Sleep.Chronotype': 82.3,
      },
      curiosity_by_trait: {
        'PaDNA.Sleep.Chronotype': 61.5,
      },
    },
  };
}

describe('OnboardingChat', () => {
  const originalFetch = global.fetch;
  let fetchMock: jest.Mock;
  let randomSpy: jest.SpyInstance<number, []>;

  beforeEach(() => {
    fetchMock = jest.fn();
    global.fetch = fetchMock as unknown as typeof global.fetch;
    window.localStorage.clear();
    randomSpy = jest.spyOn(Math, 'random').mockReturnValue(0.1);
  });

  afterEach(() => {
    global.fetch = originalFetch;
    randomSpy.mockRestore();
    jest.clearAllMocks();
  });

  it('renders trait cards with RR and Curiosity values', async () => {
    fetchMock.mockResolvedValue(createJsonResponse(makeIngestResponse()));

    render(<OnboardingChat userId={DEFAULT_USER_ID} />);

    const textarea = screen.getByPlaceholderText(/Describe something about yourself/i);
    const form = textarea.closest('form');
    expect(form).not.toBeNull();

    fireEvent.change(textarea, { target: { value: 'I stay up late reading.' } });
    fireEvent.submit(form!);

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/core/api/ingest_text'),
        expect.objectContaining({ method: 'POST' })
      )
    );

    const explainButton = await screen.findByText('Explain Why');
    const cardContainer = explainButton.closest('div');
    expect(cardContainer).toBeTruthy();
    expect(cardContainer?.textContent).toContain('Chronotype');
    expect(cardContainer?.textContent).toContain('Evening Owl');
    expect(cardContainer?.textContent).toContain('RR 82.3%');
    expect(cardContainer?.textContent).toContain('Curiosity 61.5%');
  });

  it('opens the Why-Card modal when Explain Why is clicked', async () => {
    const whyResponse = {
      trait_id: 'PaDNA.Sleep.Chronotype',
      why: 'We noticed consistent night activity in your notes.',
    };

    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('/core/api/ingest_text')) {
        return Promise.resolve(createJsonResponse(makeIngestResponse()));
      }

      if (url.includes('/core/api/traits/PaDNA.Sleep.Chronotype/why')) {
        return Promise.resolve(createJsonResponse(whyResponse));
      }

      return Promise.reject(new Error(`Unexpected fetch: ${url}`));
    });

    render(<OnboardingChat userId={DEFAULT_USER_ID} />);

    const textarea = screen.getByPlaceholderText(/Describe something about yourself/i);
    const form = textarea.closest('form');
    expect(form).not.toBeNull();

    fireEvent.change(textarea, { target: { value: 'I stay up late reading.' } });
    fireEvent.submit(form!);

    const explainButton = await screen.findByText('Explain Why');

    fireEvent.click(explainButton);

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([input]) =>
          String(input).includes('/core/api/traits/PaDNA.Sleep.Chronotype/why')
        )
      ).toBe(true)
    );

    const modal = await screen.findByRole('dialog');
    const modalQueries = within(modal);
    expect(modalQueries.getByText('Why-Card')).toBeInTheDocument();
    expect(modalQueries.getByText(/Chronotype/)).toBeInTheDocument();
    expect(
      modalQueries.getByText('We noticed consistent night activity in your notes.')
    ).toBeInTheDocument();
  });

  it('requests an auto curiosity question after three exchanges', async () => {
    const questionText = 'What sparks your curiosity right now?';

    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('/core/api/ingest_text')) {
        return Promise.resolve(createJsonResponse(makeIngestResponse()));
      }

      if (url.includes(`/core/graph/user/${DEFAULT_USER_ID}/next_question`)) {
        return Promise.resolve(createJsonResponse({ question_text: questionText }));
      }

      return Promise.reject(new Error(`Unexpected fetch: ${url} ${JSON.stringify(init)}`));
    });

    render(<OnboardingChat userId={DEFAULT_USER_ID} />);

    const textarea = screen.getByPlaceholderText(/Describe something about yourself/i);
    const form = textarea.closest('form');
    expect(form).not.toBeNull();

    for (let i = 0; i < 3; i += 1) {
      fireEvent.change(textarea, { target: { value: `message ${i}` } });
      fireEvent.submit(form!);

      await waitFor(() => {
        const ingestionCalls = fetchMock.mock.calls.filter(([input]) =>
          String(input).includes('/core/api/ingest_text')
        );
        expect(ingestionCalls.length).toBeGreaterThanOrEqual(i + 1);
      });
    }

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([input]) =>
          String(input).includes(`/core/graph/user/${DEFAULT_USER_ID}/next_question`)
        )
      ).toBe(true)
    );

    await screen.findByText(questionText);
  });
});
