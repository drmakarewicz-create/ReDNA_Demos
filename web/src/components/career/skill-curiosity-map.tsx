'use client';

import { useEffect, useState } from 'react';

interface SkillData {
  skill_name: string;
  rr_score: number;
  curiosity_score: number;
  trait_id: string;
}

interface SkillCuriosityMapProps {
  userId: string;
  minCuriosity?: number;
}

/**
 * SkillCuriosityMap Widget
 *
 * Visualizes skills with high curiosity scores to identify learning opportunities.
 * Skills are quadrant-based:
 * - Top-right: High RR + High Curiosity (Mastered but evolving)
 * - Top-left: Low RR + High Curiosity (Learning opportunities)
 * - Bottom-right: High RR + Low Curiosity (Established strengths)
 * - Bottom-left: Low RR + Low Curiosity (Background skills)
 *
 * Data source: /api/coach/career_coach/panel
 */
export function SkillCuriosityMap({ userId, minCuriosity = 50.0 }: SkillCuriosityMapProps) {
  const [skills, setSkills] = useState<SkillData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchSkills() {
      try {
        const baseUrl = process.env.NEXT_PUBLIC_CORE_API_BASE || 'http://127.0.0.1:8000';
        const response = await fetch(
          `${baseUrl}/api/coach/career_coach/panel?user_id=${encodeURIComponent(userId)}`
        );

        if (!response.ok) {
          throw new Error(`API error: ${response.status}`);
        }

        const data = await response.json();
        setSkills(data.skills || []);
        setLoading(false);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load skills');
        setLoading(false);
      }
    }

    fetchSkills();
  }, [userId]);

  if (loading) {
    return (
      <div className="rounded-2xl border border-blue-500/30 bg-gradient-to-br from-blue-950/40 to-slate-950/60 p-6">
        <div className="flex items-center gap-2 mb-4">
          <span className="text-2xl">🎯</span>
          <h3 className="text-lg font-semibold text-blue-200">Skill Curiosity Map</h3>
        </div>
        <p className="text-sm text-slate-400">Loading skills...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-red-500/30 bg-gradient-to-br from-red-950/40 to-slate-950/60 p-6">
        <div className="flex items-center gap-2 mb-4">
          <span className="text-2xl">⚠️</span>
          <h3 className="text-lg font-semibold text-red-200">Error Loading Skills</h3>
        </div>
        <p className="text-sm text-red-300">{error}</p>
      </div>
    );
  }

  // Filter skills by minimum curiosity threshold
  const filteredSkills = skills.filter(s => s.curiosity_score >= minCuriosity);

  // Categorize skills into quadrants
  const learningOpportunities = filteredSkills.filter(s => s.rr_score < 60 && s.curiosity_score >= 70);
  const evolvingMastery = filteredSkills.filter(s => s.rr_score >= 60 && s.curiosity_score >= 70);
  const highCuriositySkills = filteredSkills.filter(s => s.curiosity_score >= 50);

  return (
    <div className="rounded-2xl border border-blue-500/30 bg-gradient-to-br from-blue-950/40 to-slate-950/60 p-6">
      <div className="flex items-center gap-2 mb-4">
        <span className="text-2xl">🎯</span>
        <h3 className="text-lg font-semibold text-blue-200">Skill Curiosity Map</h3>
      </div>

      {filteredSkills.length === 0 ? (
        <div className="text-sm text-slate-400 bg-slate-900/40 rounded-lg p-4 border border-slate-700/30">
          No skills with curiosity ≥ {minCuriosity} detected yet. Continue conversations to build your skill profile.
        </div>
      ) : (
        <div className="space-y-4">
          {/* Learning Opportunities Section */}
          {learningOpportunities.length > 0 && (
            <div className="bg-amber-950/20 border border-amber-500/30 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-lg">🌱</span>
                <h4 className="text-sm font-semibold text-amber-200">
                  Learning Opportunities ({learningOpportunities.length})
                </h4>
              </div>
              <p className="text-xs text-amber-300/80 mb-3">
                High curiosity + Low mastery = Prime for growth
              </p>
              <div className="flex flex-wrap gap-2">
                {learningOpportunities.map((skill) => (
                  <div
                    key={skill.trait_id}
                    className="flex items-center gap-2 bg-amber-900/30 border border-amber-600/40 rounded-lg px-3 py-2"
                  >
                    <div className="flex flex-col">
                      <span className="text-sm font-medium text-amber-100">
                        {skill.skill_name}
                      </span>
                      <div className="flex gap-2 text-xs">
                        <span className="text-amber-300/70">
                          RR: {skill.rr_score.toFixed(0)}
                        </span>
                        <span className="text-amber-300">
                          Curiosity: {skill.curiosity_score.toFixed(0)}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Evolving Mastery Section */}
          {evolvingMastery.length > 0 && (
            <div className="bg-green-950/20 border border-green-500/30 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-lg">🚀</span>
                <h4 className="text-sm font-semibold text-green-200">
                  Evolving Mastery ({evolvingMastery.length})
                </h4>
              </div>
              <p className="text-xs text-green-300/80 mb-3">
                High mastery + High curiosity = Continuous innovation
              </p>
              <div className="flex flex-wrap gap-2">
                {evolvingMastery.map((skill) => (
                  <div
                    key={skill.trait_id}
                    className="flex items-center gap-2 bg-green-900/30 border border-green-600/40 rounded-lg px-3 py-2"
                  >
                    <div className="flex flex-col">
                      <span className="text-sm font-medium text-green-100">
                        {skill.skill_name}
                      </span>
                      <div className="flex gap-2 text-xs">
                        <span className="text-green-300">
                          RR: {skill.rr_score.toFixed(0)}
                        </span>
                        <span className="text-green-300">
                          Curiosity: {skill.curiosity_score.toFixed(0)}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* All High Curiosity Skills Summary */}
          <div className="bg-blue-950/20 border border-blue-500/30 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-lg">💡</span>
              <h4 className="text-sm font-semibold text-blue-200">
                All High Curiosity Skills ({highCuriositySkills.length})
              </h4>
            </div>
            <div className="flex flex-wrap gap-2">
              {highCuriositySkills.map((skill) => {
                const isLowRR = skill.rr_score < 60;
                return (
                  <span
                    key={skill.trait_id}
                    className={`text-xs px-2 py-1 rounded ${
                      isLowRR
                        ? 'bg-amber-900/40 text-amber-200 border border-amber-600/30'
                        : 'bg-blue-900/40 text-blue-200 border border-blue-600/30'
                    }`}
                    title={`RR: ${skill.rr_score.toFixed(0)} | Curiosity: ${skill.curiosity_score.toFixed(0)}`}
                  >
                    {skill.skill_name}
                  </span>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
