"""
Head Coach UCN/RR API Endpoint
================================

This module contains the FastAPI endpoint for Head Coach action planning
based on UCN/RR curiosity signals.

Add this to core/api.py in the "Head Coach v1 Endpoints" section.
"""

# Insert this code into core/api.py after the @app.get("/hc/explain") endpoint

"""
    @app.get("/hc/action_plan")
    async def hc_action_plan(
        user_id: str = Query(...),
        max_actions: int = Query(5, ge=1, le=20)
    ):
        \"\"\"
        Get Head Coach action plan based on UCN/RR curiosity signals.

        This implements the "Core proposes, Head Coach disposes" architecture:
        1. UCN/RR engine identifies curiosity hotspots
        2. Core converts to recommendations
        3. Head Coach deliberates using 6-check framework
        4. Returns accepted actions in user's best interest

        Args:
            user_id: User identifier
            max_actions: Maximum number of actions to return (default 5)

        Returns:
            {
                "user_id": str,
                "timestamp": str,
                "greeting": str,
                "priority_message": str | null,
                "accepted_actions": [
                    {
                        "action_type": str,
                        "action_description": str,
                        "estimated_time_mins": int,
                        "mode": str,  # mentor, servant, guardian, strategist, confidant
                        "message_to_user": str,
                        "trait_path": str | null,
                        "user_benefit": str
                    }
                ],
                "stats": {
                    "total_signals": int,
                    "acceptance_rate": float,
                    "dominant_mode": str
                }
            }
        \"\"\"
        from .head_coach_ucn_bridge import create_ucn_bridge
        from .storage import read_user_state

        try:
            # Load user traits
            obs_dict, resolved_dict, evidence_dict = read_user_state(user_id)

            # Extract UCN values
            user_traits = {}
            for trait_path, trait_data in resolved_dict.items():
                if isinstance(trait_data, dict) and 'ucn' in trait_data:
                    user_traits[trait_path] = int(trait_data['ucn'])

            if not user_traits:
                return JSONResponse(content={
                    "user_id": user_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "greeting": "No traits found yet. Upload some photos or add observations to get started!",
                    "priority_message": None,
                    "accepted_actions": [],
                    "stats": {
                        "total_signals": 0,
                        "acceptance_rate": 0.0,
                        "dominant_mode": "servant"
                    }
                }, status_code=200)

            # Get action plan from Head Coach
            bridge = create_ucn_bridge()
            plan = bridge.process_curiosity_signals(
                user_id=user_id,
                user_traits=user_traits,
                max_actions=max_actions
            )

            # Format accepted actions for response
            formatted_actions = []
            for decision in plan.accepted_actions:
                formatted_actions.append({
                    "action_type": decision.action_type,
                    "action_description": decision.action_description,
                    "estimated_time_mins": decision.estimated_time_mins,
                    "mode": decision.mode.value,
                    "intervention_style": decision.intervention_style.value,
                    "message_to_user": decision.message_to_user,
                    "trait_path": None,  # Can extract from CoreRecommendation if needed
                    "user_benefit": decision.user_benefit,
                    "when": decision.when_to_present
                })

            return JSONResponse(content={
                "user_id": plan.user_id,
                "timestamp": plan.timestamp,
                "greeting": plan.greeting,
                "priority_message": plan.priority_message,
                "celebration_message": plan.celebration_message,
                "accepted_actions": formatted_actions,
                "stats": {
                    "total_signals": plan.curiosity_signals_count,
                    "total_recommendations": plan.core_recommendations_count,
                    "acceptance_rate": plan.acceptance_rate,
                    "dominant_mode": plan.dominant_mode.value,
                    "deferred_count": len(plan.deferred_actions)
                }
            }, status_code=200)

        except Exception as e:
            logger.error(f"HC action_plan error for {user_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
"""
