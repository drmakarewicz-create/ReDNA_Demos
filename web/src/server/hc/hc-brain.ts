/**
 * HC Brain v1
 *
 * Persona and dialogue generation for Head Coach.
 *
 * Responsibilities:
 * - Generate friendly, respectful replies with HC persona
 * - Compose nudges based on curiosity spikes
 * - Maintain warm, concise, precise tone
 * - Always explain "why" when appropriate
 */

export interface HCContext {
  userId: string;
  hcName: string;
  userPreferredName?: string;
  tone: 'warm' | 'professional' | 'casual';
  explainSuggestions: boolean;
  goals?: string[];
  curiosityHotspots?: Array<{
    trait: string;
    curiosity: number;
    reason: string;
  }>;
  recentDecisions?: Array<{
    ts: string;
    summary: string;
    why?: string;
  }>;
}

export interface HCReply {
  message: string;
  why?: string;
  actions?: Array<{
    label: string;
    action: string;
    etaMins?: number;
  }>;
}

/**
 * Compose a reply to user message.
 *
 * HC persona guidelines:
 * - Warm, succinct, precise
 * - Shows empathy, avoids fluff
 * - Ask one tight clarifying question when necessary
 * - Offer 2-3 options with time/effort estimates
 * - Always give a small "why"
 * - Prefer progress over perfection
 */
export function composeReply(ctx: HCContext, userMsg: string): HCReply {
  const userMsgLower = userMsg.toLowerCase().trim();

  // Handle common queries

  // "What should I do next?"
  if (
    userMsgLower.includes('what') &&
    (userMsgLower.includes('next') || userMsgLower.includes('do'))
  ) {
    const hotspots = ctx.curiosityHotspots || [];

    if (hotspots.length === 0) {
      return {
        message: "You're in great shape! All traits are well-established. Want to explore something new?",
        actions: [
          {
            label: 'Import more photos',
            action: 'import_photos',
            etaMins: 5
          },
          {
            label: 'Review recent changes',
            action: 'review_changes',
            etaMins: 3
          }
        ]
      };
    }

    const top = hotspots[0];
    const traitName = top.trait.split('.').pop() || top.trait;

    return {
      message: `Your quickest win is reducing uncertainty for **${traitName}**.`,
      why: `It has high curiosity (${Math.round(top.curiosity)}) — ${top.reason}. Adding one piece of evidence will help.`,
      actions: [
        {
          label: `Add evidence for ${traitName}`,
          action: 'add_evidence',
          etaMins: 2
        },
        {
          label: 'Review top 3 hotspots',
          action: 'review_hotspots',
          etaMins: 5
        },
        {
          label: 'See full plan',
          action: 'show_plan',
          etaMins: 1
        }
      ]
    };
  }

  // "Why are you suggesting...?"
  if (userMsgLower.includes('why') && userMsgLower.includes('suggest')) {
    const hotspots = ctx.curiosityHotspots || [];
    if (hotspots.length > 0) {
      const top = hotspots[0];
      const traitName = top.trait.split('.').pop() || top.trait;

      return {
        message: `I'm suggesting you focus on **${traitName}** because:`,
        why: (
          `1. It has high curiosity (${Math.round(top.curiosity)}/1000)\n` +
          `2. Reason: ${top.reason}\n` +
          `3. Adding evidence here gives you the biggest uncertainty reduction\n\n` +
          `*Source: ReDNA Core UCN/RR scoring system*`
        )
      };
    }

    return {
      message: "I don't have an active suggestion right now. Want me to plan your next hour?",
      actions: [
        {
          label: 'Plan my next hour',
          action: 'plan_next_hour',
          etaMins: 1
        }
      ]
    };
  }

  // "Explain..."
  if (userMsgLower.includes('explain')) {
    return {
      message: "I'd be happy to explain. Which topic would you like me to break down?",
      why: "Ask about any trait, decision, or suggestion and I'll give you the details with sources.",
      actions: [
        {
          label: 'Explain curiosity scoring',
          action: 'explain_curiosity'
        },
        {
          label: 'Explain my recent decisions',
          action: 'explain_decisions'
        }
      ]
    };
  }

  // "Help" or "What can you do?"
  if (
    userMsgLower.includes('help') ||
    userMsgLower.includes('what can you') ||
    userMsgLower.includes('capabilities')
  ) {
    return {
      message: `Hi! I'm **${ctx.hcName}**, your Head Coach. Here's what I can help with:`,
      why: (
        `• **Plan next actions** — Focus on high-impact tasks\n` +
        `• **Reduce uncertainty** — Guide you through curiosity hotspots\n` +
        `• **Explain decisions** — Break down why I suggest things\n` +
        `• **Track progress** — Show what's changed and why\n\n` +
        `Just ask "what should I do next?" or click any action button.`
      )
    };
  }

  // Default: friendly acknowledgment with action options
  const hotspots = ctx.curiosityHotspots || [];
  const hasHotspots = hotspots.length > 0;

  if (hasHotspots) {
    return {
      message: `Got it! ${hasOptimisticWords(userMsg) ? "Let's keep that momentum going." : "Here are a few options:"}`,
      actions: [
        {
          label: 'Show me quick wins',
          action: 'quick_wins',
          etaMins: 2
        },
        {
          label: 'Plan next hour',
          action: 'plan_next_hour',
          etaMins: 15
        },
        {
          label: 'Explain my curiosity hotspots',
          action: 'explain_hotspots',
          etaMins: 3
        }
      ]
    };
  }

  return {
    message: "I'm here to help! Ask me anything or try one of these:",
    actions: [
      {
        label: 'What should I do next?',
        action: 'plan_next'
      },
      {
        label: 'Review my progress',
        action: 'review_progress'
      },
      {
        label: 'Import more data',
        action: 'import_data'
      }
    ]
  };
}

/**
 * Compose a micro-nudge based on curiosity spikes or undone plans.
 *
 * Nudges are gentle, actionable, and time-bound.
 */
export function composeNudge(ctx: HCContext): HCReply | null {
  const hotspots = ctx.curiosityHotspots || [];

  if (hotspots.length === 0) {
    return null;
  }

  const top = hotspots[0];

  // Only nudge if curiosity is very high (>900)
  if (top.curiosity < 900) {
    return null;
  }

  const traitName = top.trait.split('.').pop() || top.trait;

  return {
    message: `**2-minute opportunity:** Add evidence for **${traitName}**`,
    why: `High curiosity detected (${Math.round(top.curiosity)}). Quick action = big impact.`,
    actions: [
      {
        label: 'Do it now',
        action: 'add_evidence',
        etaMins: 2
      },
      {
        label: 'Queue for later',
        action: 'queue_task'
      },
      {
        label: 'Skip',
        action: 'dismiss_nudge'
      }
    ]
  };
}

/**
 * Generate a "morning snapshot" — micro-ritual summary.
 */
export function composeMorningSnapshot(ctx: HCContext): HCReply {
  const hotspots = ctx.curiosityHotspots || [];
  const recentDecisions = ctx.recentDecisions || [];

  let message = `**Good morning!** Here's your snapshot:\n\n`;

  if (recentDecisions.length > 0) {
    const latest = recentDecisions[0];
    message += `• **Latest:** ${latest.summary}\n`;
  }

  if (hotspots.length > 0) {
    message += `• **Top focus:** ${hotspots.length} curiosity hotspot(s)\n`;
  } else {
    message += `• **Status:** All traits well-established ✓\n`;
  }

  if (ctx.goals && ctx.goals.length > 0) {
    message += `• **Goals:** ${ctx.goals.slice(0, 2).join(', ')}\n`;
  }

  return {
    message,
    actions: hotspots.length > 0
      ? [
          {
            label: 'Show quick wins',
            action: 'quick_wins',
            etaMins: 5
          },
          {
            label: 'Plan my day',
            action: 'plan_day',
            etaMins: 10
          }
        ]
      : [
          {
            label: 'Import new data',
            action: 'import_data'
          },
          {
            label: 'Review progress',
            action: 'review_progress'
          }
        ]
  };
}

/**
 * Generate an "end-of-day recap" — micro-ritual summary.
 */
export function composeEndOfDayRecap(ctx: HCContext): HCReply {
  const recentDecisions = ctx.recentDecisions || [];

  let message = `**End-of-day recap:**\n\n`;

  if (recentDecisions.length > 0) {
    message += `Today you:\n`;
    recentDecisions.slice(0, 3).forEach((dec, i) => {
      message += `${i + 1}. ${dec.summary}\n`;
    });
  } else {
    message += `No major updates today — steady as she goes!\n`;
  }

  message += `\n**Tomorrow's focus?**`;

  return {
    message,
    actions: [
      {
        label: 'Plan tomorrow',
        action: 'plan_next_day'
      },
      {
        label: 'Review what changed',
        action: 'review_changes'
      }
    ]
  };
}

// Helper functions

function hasOptimisticWords(msg: string): boolean {
  const optimisticWords = ['great', 'thanks', 'awesome', 'perfect', 'good', 'yes', 'ok'];
  const msgLower = msg.toLowerCase();
  return optimisticWords.some((word) => msgLower.includes(word));
}
