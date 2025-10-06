/**
 * Simplified onboarding data structure
 * Follows the standard ReDNA onboarding script
 */

export interface BasicSetupQuestion {
  id: string;
  label: string;
  options: string[];
  allowOther?: boolean;
}

export interface WyrOption {
  letter: string;
  text: string;
}

export interface WyrQuestion {
  id: string;
  question: string;
  options: WyrOption[];
}

/**
 * Basic Setup Questions (5 questions)
 */
export const BASIC_SETUP_QUESTIONS: BasicSetupQuestion[] = [
  {
    id: 'age_range',
    label: 'Age Range',
    options: ['18-24', '25-34', '35-44', '45-54', '55+']
  },
  {
    id: 'gender',
    label: 'Gender',
    options: ['Male', 'Female', 'Non-Binary', 'Prefer Not to Say', 'Other'],
    allowOther: true
  },
  {
    id: 'orientation',
    label: 'Orientation',
    options: ['Straight', 'Gay', 'Bisexual', 'Pansexual', 'Asexual', 'Prefer Not to Say', 'Other'],
    allowOther: true
  },
  {
    id: 'preferred_language',
    label: 'Preferred Language',
    options: ['English', 'Spanish', 'French', 'German', 'Other'],
    allowOther: true
  },
  {
    id: 'relationship_status',
    label: 'Relationship Status',
    options: ['Single', 'In a Relationship', 'Married', 'Open/Poly', 'Prefer Not to Say']
  }
];

/**
 * Welcome message shown at the start
 */
export const WELCOME_MESSAGE = `Welcome to ReDNA, your personal guide to positive, consensual relationship discovery! Let's get started with some basics. This is quick and private—answer what feels right for you.`;

/**
 * Message shown after basic setup
 */
export const BASIC_SETUP_COMPLETE_MESSAGE = `Thank you! Your responses help seed your ReDNA with initial insights. Your initial Refinement Rating (RR) is 0%—more refined than 0% of new users. This measures how accurately your profile mirrors your true relationship self, and it grows with more data to supercharge our tips! Now, let's meet your Head Coach to get you on your way.`;

/**
 * Default Head Coach name
 */
export const DEFAULT_HEAD_COACH_NAME = 'Alex Harmony';

/**
 * Head Coach introduction message
 */
export const HEAD_COACH_INTRO = `Hi, I'm Alex Harmony, your Head Coach for ReDNA refinement! I'm here to help you explore your relationship self in a positive, consensual way. To get started, we just need one quick "Would You Rather" question—it's fun and gives a glimpse into your style. Ready?`;

/**
 * Initial "Would You Rather" question
 */
export const INITIAL_WYR_QUESTION: WyrQuestion = {
  id: 'wyr_perfect_evening',
  question: 'If you were planning a perfect evening with someone special, would you rather:',
  options: [
    { letter: 'A', text: 'A cozy home dinner with deep conversation?' },
    { letter: 'B', text: 'An adventurous outdoor walk holding hands?' },
    { letter: 'C', text: 'A surprise gift exchange?' },
    { letter: 'D', text: 'Quality time cuddled up watching a movie?' }
  ]
};
