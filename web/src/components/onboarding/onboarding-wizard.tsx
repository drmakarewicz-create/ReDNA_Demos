'use client';

import { useState, useCallback, useEffect } from 'react';
import {
  BASIC_SETUP_QUESTIONS,
  WELCOME_MESSAGE,
  BASIC_SETUP_COMPLETE_MESSAGE,
  DEFAULT_HEAD_COACH_NAME,
  HEAD_COACH_INTRO,
  INITIAL_WYR_QUESTION,
  type BasicSetupQuestion,
  type WyrQuestion
} from './wyr-questions';
import { createUser } from '../../lib/api';

interface OnboardingWizardProps {
  userId?: string; // Optional - if not provided, user creation step will be shown
  onComplete: (data: OnboardingData & { userId: string; displayName?: string }) => void;
  onClose: () => void;
}

interface BasicSetupData {
  [key: string]: string;
}

export interface OnboardingData {
  userId?: string;
  displayName?: string;
  basic_setup: BasicSetupData;
  head_coach_name: string;
  wyr_answer?: {
    question_id: string;
    selected_letter: string;
    selected_text: string;
  };
}

type Phase = 'user_creation' | 'welcome' | 'basic_setup' | 'transition' | 'coach_intro' | 'wyr' | 'complete';

export function OnboardingWizard({ userId: initialUserId, onComplete, onClose }: OnboardingWizardProps) {
  const [phase, setPhase] = useState<Phase>(initialUserId ? 'welcome' : 'user_creation');
  const [userId, setUserId] = useState(initialUserId || '');
  const [displayName, setDisplayName] = useState('');
  const [basicSetupData, setBasicSetupData] = useState<BasicSetupData>({});
  const [headCoachName, setHeadCoachName] = useState(DEFAULT_HEAD_COACH_NAME);
  const [otherValues, setOtherValues] = useState<{[key: string]: string}>({});
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);

  const currentQuestion = BASIC_SETUP_QUESTIONS[currentQuestionIndex];
  const isLastQuestion = currentQuestionIndex === BASIC_SETUP_QUESTIONS.length - 1;

  // Handle basic setup selection
  const handleBasicSetupSelection = useCallback((questionId: string, value: string) => {
    setBasicSetupData(prev => ({ ...prev, [questionId]: value }));
  }, []);

  const handleOtherValueChange = useCallback((questionId: string, value: string) => {
    setOtherValues(prev => ({ ...prev, [questionId]: value }));
  }, []);

  const handleContinueFromBasicSetup = useCallback(() => {
    const currentValue = basicSetupData[currentQuestion.id];

    if (!currentValue) {
      return; // Don't allow continue if no selection
    }

    // If "Other" was selected and question allows it, use the other value
    if (currentValue === 'Other' && currentQuestion.allowOther && otherValues[currentQuestion.id]) {
      setBasicSetupData(prev => ({
        ...prev,
        [currentQuestion.id]: otherValues[currentQuestion.id]
      }));
    }

    if (isLastQuestion) {
      setPhase('transition');
    } else {
      setCurrentQuestionIndex(prev => prev + 1);
    }
  }, [basicSetupData, currentQuestion, isLastQuestion, otherValues]);

  const handleBack = useCallback(() => {
    if (phase === 'basic_setup' && currentQuestionIndex > 0) {
      setCurrentQuestionIndex(prev => prev - 1);
    } else if (phase === 'transition') {
      setPhase('basic_setup');
      setCurrentQuestionIndex(BASIC_SETUP_QUESTIONS.length - 1);
    } else if (phase === 'coach_intro') {
      setPhase('transition');
    } else if (phase === 'wyr') {
      setPhase('coach_intro');
    }
  }, [phase, currentQuestionIndex]);

  const handleWyrSelection = useCallback((letter: string, text: string) => {
    console.log('[WYR] Selection clicked:', { letter, text, userId, displayName });

    if (!userId || !userId.trim()) {
      console.error('[WYR] No userId - cannot complete onboarding');
      alert('Error: User ID is missing. Please start over.');
      return;
    }

    const data = {
      userId,
      displayName: displayName || userId,
      basic_setup: basicSetupData,
      head_coach_name: headCoachName,
      wyr_answer: {
        question_id: INITIAL_WYR_QUESTION.id,
        selected_letter: letter,
        selected_text: text
      }
    };
    console.log('[WYR] Calling onComplete with data:', data);
    onComplete(data);
  }, [userId, displayName, basicSetupData, headCoachName, onComplete]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const coerceSlug = (value: string): string => {
    return value
      .toLowerCase()
      .replace(/[^a-z0-9_-]/g, '_')
      .replace(/_{2,}/g, '_')
      .slice(0, 40);
  };

  const validateUserId = (value: string): string | null => {
    const trimmed = value.trim();
    if (!trimmed) return 'User ID required';
    if (trimmed.length < 3) return 'Use at least 3 characters';
    if (!/^[-_a-z0-9]+$/.test(trimmed)) return 'Only lowercase letters, numbers, - and _ allowed';
    return null;
  };

  const handleUserIdChange = (value: string) => {
    setUserId(coerceSlug(value));
  };

  const handleUserCreationContinue = useCallback(async () => {
    const error = validateUserId(userId);
    if (error) return;

    try {
      // Create the user and folders immediately
      console.log('[Onboarding] Creating user:', userId);
      const response = await createUser({
        userId: userId.trim(),
        label: displayName || userId
      });

      console.log('[Onboarding] User created successfully:', response.user);

      // Proceed to welcome phase
      setPhase('welcome');
    } catch (err) {
      console.error('[Onboarding] Failed to create user:', err);
      alert(`Failed to create user: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  }, [userId, displayName]);

  const renderUserCreation = () => {
    const error = validateUserId(userId);
    const canContinue = !error && userId.trim().length >= 3;

    return (
      <div className="space-y-6">
        <div className="text-center mb-8">
          <h2 className="text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-2">
            Create Your Account
          </h2>
          <p className="text-gray-600 dark:text-gray-400">
            Let's start by creating your unique user ID
          </p>
        </div>

        <div className="space-y-4">
          <div>
            <label htmlFor="user-id" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              User ID <span className="text-red-500">*</span>
            </label>
            <input
              id="user-id"
              type="text"
              value={userId}
              onChange={(e) => handleUserIdChange(e.target.value)}
              placeholder="my_username"
              className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-pink-500 focus:border-transparent"
              autoFocus
            />
            {error ? (
              <p className="mt-2 text-sm text-red-600 dark:text-red-400">{error}</p>
            ) : (
              <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
                Use lowercase letters, numbers, hyphens, or underscores
              </p>
            )}
          </div>

          <div>
            <label htmlFor="display-name" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Display Name (optional)
            </label>
            <input
              id="display-name"
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="My Display Name"
              className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-pink-500 focus:border-transparent"
            />
            <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
              How you'd like to be addressed (defaults to user ID)
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={handleUserCreationContinue}
          disabled={!canContinue}
          className="w-full px-6 py-3 bg-gradient-to-r from-pink-500 to-purple-600 hover:from-pink-600 hover:to-purple-700 text-white rounded-lg font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Continue
        </button>
      </div>
    );
  };

  const renderWelcome = () => (
    <div className="space-y-6 text-center">
      <div className="mb-8">
        <div className="w-16 h-16 bg-gradient-to-br from-pink-500 to-purple-600 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
          </svg>
        </div>
        <h2 className="text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-4">
          Welcome to ReDNA
        </h2>
      </div>

      <div className="max-w-lg mx-auto text-left bg-gray-50 dark:bg-gray-800 rounded-lg p-6">
        <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
          {WELCOME_MESSAGE}
        </p>
      </div>

      <button
        type="button"
        onClick={() => setPhase('basic_setup')}
        className="px-6 py-3 bg-gradient-to-r from-pink-500 to-purple-600 hover:from-pink-600 hover:to-purple-700 text-white rounded-lg font-medium transition-all"
      >
        Let's Get Started
      </button>
    </div>
  );

  const renderBasicSetup = () => {
    if (!currentQuestion) return null;

    const selectedValue = basicSetupData[currentQuestion.id];
    const showOtherInput = selectedValue === 'Other' && currentQuestion.allowOther;

    return (
      <div className="space-y-6">
        <div className="text-center mb-6">
          <div className="text-sm text-gray-500 dark:text-gray-400 mb-2">
            Question {currentQuestionIndex + 1} of {BASIC_SETUP_QUESTIONS.length}
          </div>
          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2 mb-4">
            <div
              className="bg-gradient-to-r from-pink-500 to-purple-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${((currentQuestionIndex + 1) / BASIC_SETUP_QUESTIONS.length) * 100}%` }}
            />
          </div>
          <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
            {currentQuestion.label}
          </h3>
        </div>

        <div className="grid grid-cols-2 gap-3">
          {currentQuestion.options.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => handleBasicSetupSelection(currentQuestion.id, option)}
              className={`px-4 py-3 text-left border-2 rounded-lg transition-all font-medium ${
                selectedValue === option
                  ? 'border-purple-500 bg-purple-50 dark:bg-purple-900/20 text-purple-700 dark:text-purple-300'
                  : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600'
              }`}
            >
              {option}
            </button>
          ))}
        </div>

        {showOtherInput && (
          <div className="mt-4">
            <input
              type="text"
              value={otherValues[currentQuestion.id] || ''}
              onChange={(e) => handleOtherValueChange(currentQuestion.id, e.target.value)}
              placeholder="Please specify..."
              className="w-full px-4 py-2 border-2 border-purple-300 dark:border-purple-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:border-purple-500"
              autoFocus
            />
          </div>
        )}

        <div className="flex justify-between pt-4">
          {currentQuestionIndex > 0 ? (
            <button
              type="button"
              onClick={handleBack}
              className="px-4 py-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 font-medium flex items-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              Back
            </button>
          ) : <div />}
          <button
            type="button"
            onClick={handleContinueFromBasicSetup}
            disabled={!selectedValue || (showOtherInput && !otherValues[currentQuestion.id]?.trim())}
            className="px-6 py-2.5 bg-gradient-to-r from-pink-500 to-purple-600 hover:from-pink-600 hover:to-purple-700 disabled:from-gray-300 disabled:to-gray-400 disabled:cursor-not-allowed text-white rounded-lg font-medium transition-all flex items-center gap-2"
          >
            {isLastQuestion ? 'Continue' : 'Next'}
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      </div>
    );
  };

  const renderTransition = () => (
    <div className="space-y-6 text-center">
      <div className="max-w-lg mx-auto bg-gradient-to-br from-purple-50 to-pink-50 dark:from-purple-900/20 dark:to-pink-900/20 rounded-lg p-6">
        <p className="text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-line">
          {BASIC_SETUP_COMPLETE_MESSAGE}
        </p>
      </div>

      <div className="flex flex-col items-center gap-4 pt-4">
        <button
          type="button"
          onClick={() => setPhase('coach_intro')}
          className="px-6 py-3 bg-gradient-to-r from-pink-500 to-purple-600 hover:from-pink-600 hover:to-purple-700 text-white rounded-lg font-medium transition-all"
        >
          Meet Your Head Coach
        </button>
        <button
          type="button"
          onClick={handleBack}
          className="text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
        >
          Go Back
        </button>
      </div>
    </div>
  );

  const renderCoachIntro = () => (
    <div className="space-y-6">
      <div className="text-center mb-6">
        <div className="w-20 h-20 bg-gradient-to-br from-cyan-400 to-blue-600 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg className="w-10 h-10 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.828 14.828a4 4 0 01-5.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <h2 className="text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-2">
          Head Coach Assigned
        </h2>
      </div>

      <div className="max-w-lg mx-auto bg-gradient-to-br from-cyan-50 to-blue-50 dark:from-cyan-900/20 dark:to-blue-900/20 rounded-lg p-6">
        <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
          {HEAD_COACH_INTRO}
        </p>

        <div className="mt-4">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            You can rename me anytime—what would you like to call me?
          </label>
          <input
            type="text"
            value={headCoachName}
            onChange={(e) => setHeadCoachName(e.target.value)}
            placeholder="Enter new name or keep default"
            className="w-full px-4 py-2 border-2 border-cyan-300 dark:border-cyan-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:border-cyan-500"
          />
        </div>
      </div>

      <div className="flex justify-between pt-4">
        <button
          type="button"
          onClick={handleBack}
          className="px-4 py-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 font-medium flex items-center gap-2"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back
        </button>
        <button
          type="button"
          onClick={() => setPhase('wyr')}
          className="px-6 py-3 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700 text-white rounded-lg font-medium transition-all"
        >
          Ready! Let's Go
        </button>
      </div>
    </div>
  );

  const renderWyr = () => (
    <div className="space-y-6">
      <div className="text-center mb-6">
        <h2 className="text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-4">
          Would You Rather
        </h2>
        <p className="text-gray-600 dark:text-gray-400">
          {INITIAL_WYR_QUESTION.question}
        </p>
      </div>

      <div className="space-y-3">
        {INITIAL_WYR_QUESTION.options.map(({ letter, text }) => (
          <button
            key={letter}
            type="button"
            onClick={() => handleWyrSelection(letter, text)}
            className="w-full px-6 py-4 text-left border-2 border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 hover:border-purple-500 hover:bg-purple-50 dark:hover:bg-purple-900/20 rounded-lg transition-all font-medium text-gray-700 dark:text-gray-300 group"
          >
            <span className="inline-block w-8 h-8 rounded-full bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300 font-bold mr-3 text-center leading-8 group-hover:bg-purple-500 group-hover:text-white transition-colors">
              {letter}
            </span>
            {text}
          </button>
        ))}
      </div>

      <div className="flex justify-start pt-4">
        <button
          type="button"
          onClick={handleBack}
          className="px-4 py-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 font-medium flex items-center gap-2"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back
        </button>
      </div>
    </div>
  );

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-gray-500 dark:text-gray-400">
              ReDNA Onboarding
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors"
            aria-label="Close onboarding"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-8">
          {phase === 'user_creation' && renderUserCreation()}
          {phase === 'welcome' && renderWelcome()}
          {phase === 'basic_setup' && renderBasicSetup()}
          {phase === 'transition' && renderTransition()}
          {phase === 'coach_intro' && renderCoachIntro()}
          {phase === 'wyr' && renderWyr()}
        </div>
      </div>
    </div>
  );
}
