"""
Career Coach Service
Professional development, skill optimization, and career planning.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..storage import read_user_state, write_user_state


class CareerCoach:
    """
    Career optimization coach that analyzes SkillDNA, ProfDNA, and provides
    actionable guidance for professional development and career transitions.
    """

    def __init__(self, user_id: str, resolved_state: Optional[Dict[str, Any]] = None):
        self.user_id = user_id
        self._resolved_override = resolved_state

    def _load_state(self) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        """
        Load user state, allowing injected resolved data for capability-gated flows.
        """
        if self._resolved_override is not None:
            # Provide empty evidence/observations when resolved is injected
            return self._resolved_override, {"items": []}, {"items": [], "by_trait": {}}
        return read_user_state(self.user_id)

    def get_skill_curiosity_map(
        self,
        min_curiosity: float = 50.0
    ) -> Dict[str, Any]:
        """
        Generate a map of skills with curiosity/RR distribution.

        Args:
            min_curiosity: Minimum curiosity threshold for highlighting

        Returns:
            Skill curiosity map with categorized skills
        """
        resolved, _, _ = self._load_state()

        skill_traits = []
        for trait_path, trait_data in resolved.items():
            if not isinstance(trait_data, dict):
                continue

            if trait_path.startswith("SkillDNA"):
                skill_traits.append({
                    "path": trait_path,
                    "name": trait_path.split(".")[-1],
                    "value": trait_data.get("resolved_value") or trait_data.get("value"),
                    "rr": trait_data.get("rr", 50.0),
                    "curiosity": trait_data.get("curiosity", 50.0),
                    "ucn": trait_data.get("ucn", 500.0)
                })

        # Categorize skills
        high_curiosity = [s for s in skill_traits if s["curiosity"] >= min_curiosity]
        low_curiosity = [s for s in skill_traits if s["curiosity"] < min_curiosity]

        # Sort high curiosity by curiosity (descending)
        high_curiosity.sort(key=lambda x: x["curiosity"], reverse=True)

        # Sort low curiosity by RR (most resolved first)
        low_curiosity.sort(key=lambda x: x["rr"], reverse=True)

        return {
            "high_curiosity_skills": high_curiosity,
            "well_resolved_skills": low_curiosity,
            "total_skills": len(skill_traits),
            "avg_skill_rr": sum(s["rr"] for s in skill_traits) / len(skill_traits) if skill_traits else 0.0,
            "skills_needing_attention": len(high_curiosity)
        }

    def get_career_dashboard(self) -> Dict[str, Any]:
        """
        Generate comprehensive career dashboard with satisfaction, skills, and recommendations.

        Returns:
            Dashboard data including RR distribution, skills, and professional stats
        """
        resolved, _, _ = self._load_state()

        # Collect SkillDNA and ProfDNA traits
        skills = []
        prof_traits = []

        for trait_path, trait_data in resolved.items():
            if not isinstance(trait_data, dict):
                continue

            if trait_path.startswith("SkillDNA"):
                skills.append({
                    "path": trait_path,
                    "name": trait_path.split(".")[-1],
                    "rr": trait_data.get("rr", 50.0),
                    "curiosity": trait_data.get("curiosity", 50.0)
                })
            elif trait_path.startswith("ProfDNA"):
                prof_traits.append({
                    "path": trait_path,
                    "name": trait_path.split(".")[-1],
                    "value": trait_data.get("resolved_value") or trait_data.get("value"),
                    "rr": trait_data.get("rr", 50.0),
                    "curiosity": trait_data.get("curiosity", 50.0)
                })

        # Calculate satisfaction score (simple heuristic: average RR across ProfDNA)
        satisfaction_score = (
            sum(t["rr"] for t in prof_traits) / len(prof_traits)
            if prof_traits else 50.0
        )

        # Calculate skill distribution
        skill_distribution = {
            "high_rr": len([s for s in skills if s["rr"] >= 70]),
            "medium_rr": len([s for s in skills if 40 <= s["rr"] < 70]),
            "low_rr": len([s for s in skills if s["rr"] < 40])
        }

        return {
            "satisfaction_score": round(satisfaction_score, 1),
            "total_skills": len(skills),
            "skill_distribution": skill_distribution,
            "professional_traits": len(prof_traits),
            "top_strengths": sorted(skills, key=lambda x: x["rr"], reverse=True)[:5],
            "skill_gaps": sorted(skills, key=lambda x: x["curiosity"], reverse=True)[:5]
        }

    def generate_learning_path(
        self,
        target_skill: str,
        current_level: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Generate a learning path for a specific skill.

        Args:
            target_skill: Skill path or name to develop
            current_level: Current RR level (auto-detected if None)

        Returns:
            Learning path with steps, timeline, and milestones
        """
        resolved, _, _ = self._load_state()

        # Find the skill
        skill_data = None
        for trait_path, trait_info in resolved.items():
            if isinstance(trait_info, dict) and (
                trait_path == target_skill or
                trait_path.endswith(f".{target_skill}")
            ):
                skill_data = {
                    "path": trait_path,
                    "rr": trait_info.get("rr", 50.0),
                    "curiosity": trait_info.get("curiosity", 50.0),
                    "current_value": trait_info.get("resolved_value") or trait_info.get("value")
                }
                break

        if not skill_data:
            return {
                "error": "skill_not_found",
                "message": f"Skill '{target_skill}' not found in SkillDNA"
            }

        rr = current_level if current_level is not None else skill_data["rr"]

        # Generate learning steps based on current RR
        steps = []
        if rr < 30:
            steps = [
                "Foundation: Complete introductory course or tutorial",
                "Practice: Build 2-3 simple projects",
                "Consolidation: Join community or find mentor",
                "Application: Use skill in real-world context"
            ]
        elif rr < 60:
            steps = [
                "Intermediate: Advanced course or specialized training",
                "Projects: Build 1-2 complex projects",
                "Mastery: Teach or document your learning",
                "Integration: Combine with complementary skills"
            ]
        else:
            steps = [
                "Advanced: Contribute to open source or lead project",
                "Specialization: Deep dive into niche area",
                "Thought leadership: Write/speak about expertise",
                "Mentorship: Guide others in this skill"
            ]

        return {
            "skill": skill_data["path"],
            "current_rr": rr,
            "current_curiosity": skill_data["curiosity"],
            "target_rr": min(rr + 20, 95),  # Aim for +20 RR improvement
            "steps": steps,
            "estimated_timeline": f"{len(steps) * 2}-{len(steps) * 4} weeks",
            "next_action": steps[0] if steps else "Review current skill level"
        }

    def recommend_career_paths(
        self,
        top_n: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Recommend potential career paths based on SkillDNA, MotivationDNA, and PersonalityDNA.

        Args:
            top_n: Number of recommendations to return

        Returns:
            List of career path recommendations with match scores
        """
        resolved, _, _ = self._load_state()

        # Collect relevant traits
        top_skills = []
        motivations = []
        personality_traits = []

        for trait_path, trait_data in resolved.items():
            if not isinstance(trait_data, dict):
                continue

            rr = trait_data.get("rr", 50.0)
            value = trait_data.get("resolved_value") or trait_data.get("value")

            if trait_path.startswith("SkillDNA") and rr >= 60:
                top_skills.append(trait_path.split(".")[-1])
            elif trait_path.startswith("PsyDNA.MotivationDNA"):
                motivations.append({
                    "trait": trait_path.split(".")[-1],
                    "value": value,
                    "strength": rr
                })
            elif trait_path.startswith("PsyDNA.PersonalityDNA"):
                personality_traits.append({
                    "trait": trait_path.split(".")[-1],
                    "value": value,
                    "rr": rr
                })

        # Simple career matching heuristics
        # In production, this would use a proper career database and matching algorithm
        recommendations = []

        # Tech/Engineering path if technical skills are strong
        tech_skills = [s for s in top_skills if any(
            kw in s.lower() for kw in ["programming", "software", "data", "engineering"]
        )]
        if tech_skills:
            recommendations.append({
                "path": "Technology/Engineering",
                "match_score": min(len(tech_skills) * 15 + 40, 95),
                "matched_skills": tech_skills[:3],
                "reasoning": "Strong technical skill foundation"
            })

        # Creative/Design path if creative skills present
        creative_skills = [s for s in top_skills if any(
            kw in s.lower() for kw in ["design", "creative", "visual", "writing"]
        )]
        if creative_skills:
            recommendations.append({
                "path": "Creative/Design",
                "match_score": min(len(creative_skills) * 15 + 40, 95),
                "matched_skills": creative_skills[:3],
                "reasoning": "Creative skills and aesthetic sensibility"
            })

        # Management/Leadership if high extraversion or leadership skills
        leadership_skills = [s for s in top_skills if any(
            kw in s.lower() for kw in ["leadership", "management", "communication"]
        )]
        if leadership_skills:
            recommendations.append({
                "path": "Management/Leadership",
                "match_score": min(len(leadership_skills) * 15 + 45, 95),
                "matched_skills": leadership_skills[:3],
                "reasoning": "Leadership and people management capabilities"
            })

        # Sort by match score and return top N
        recommendations.sort(key=lambda x: x["match_score"], reverse=True)
        return recommendations[:top_n]

    def create_development_goal(
        self,
        skill_path: str,
        target_rr: float,
        timeline_weeks: int
    ) -> Dict[str, Any]:
        """
        Create a tracked development goal for a skill.

        Args:
            skill_path: Full SkillDNA path
            target_rr: Target RR to achieve
            timeline_weeks: Timeline in weeks

        Returns:
            Goal object with tracking metadata
        """
        resolved, _, _ = read_user_state(self.user_id)

        current_trait = resolved.get(skill_path, {})
        current_rr = current_trait.get("rr", 0.0) if isinstance(current_trait, dict) else 0.0

        goal = {
            "id": f"goal_{skill_path}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            "skill": skill_path,
            "current_rr": current_rr,
            "target_rr": target_rr,
            "timeline_weeks": timeline_weeks,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "active",
            "progress_pct": 0.0,
            "milestones": [
                {
                    "week": i * (timeline_weeks // 4),
                    "target_rr": current_rr + (target_rr - current_rr) * (i / 4),
                    "completed": False
                }
                for i in range(1, 5)
            ]
        }

        return goal


__all__ = ["CareerCoach"]
