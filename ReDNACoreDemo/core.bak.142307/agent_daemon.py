from __future__ import annotations

"""
Agentic Head Coach daemon.

Runs background jobs for registered Head Coach agents. The daemon can be
invoked once (for cron/scheduler) or run continuously inside a service. It
coordinates inbox processing, curiosity nudges, refinement jobs, and
self-improvement tasks according to per-user autonomy and quota policies.
"""

import argparse
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple
from uuid import uuid4

from ReDNACoreDemo.core.agent_trigger_config import TriggerConfig

from ReDNACoreDemo import agents
from ReDNACoreDemo.core.agent_capabilities import (
    CapabilityError,
    ConsentDeniedError,
    ensure_consent,
    ensure_capability_available,
    audit_event,
)
from ReDNACoreDemo.core.storage import CORE_DATA_ROOT
from ReDNACoreDemo.core.agent_triggers import TriggerEngine


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


AUTONOMY_ORDER = {"manual": -1, "propose": 0, "semi": 1, "auto": 2}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso(ts: datetime) -> str:
    return ts.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def _today_key() -> str:
    return _utc_now().strftime("day_%Y%m%d")


class TelemetryEmitter:
    """Simple JSONL telemetry writer - unified agent activity log."""

    def __init__(self) -> None:
        self.dir = CORE_DATA_ROOT / "telemetry" / "agents"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.activity_log = self.dir / "agent_activity.jsonl"

    def emit(self, event_type: str, payload: Dict[str, Any]) -> None:
        data = dict(payload)
        data.setdefault("event", event_type)
        data.setdefault("timestamp", _utc_iso(_utc_now()))
        with self.activity_log.open("a", encoding="utf-8") as handle:
            handle.write(json_dumps(data) + "\n")


def json_dumps(payload: Dict[str, Any]) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False, sort_keys=False)


@dataclass
class AgentJob:
    job_id: str
    kind: str
    payload: Dict[str, Any]
    source: str
    required_autonomy: str = "semi"
    metadata: Dict[str, Any] = field(default_factory=dict)


JobProvider = Callable[[str, agents.AgentPolicy, agents.AgentState], Sequence[Dict[str, Any]]]
JobExecutor = Callable[[AgentJob, agents.AgentPolicy], Dict[str, Any]]


def default_provider(_: str, __: agents.AgentPolicy, ___: agents.AgentState) -> Sequence[Dict[str, Any]]:
    return []


def default_executor(job: AgentJob, policy: agents.AgentPolicy) -> Dict[str, Any]:
    response = {
        "status": "ok",
        "message": f"{job.kind} executed",
        "source": job.source,
        "scope": policy.permissions.get("namespaces", []),
    }
    response.update(job.payload or {})
    return response


class AgentDaemon:
    """
    Coordinates scheduled processing for a Head Coach agent.

    Providers may be overridden (e.g., in tests) to simulate curiosity and
    refinement pipelines.
    """

    def __init__(
        self,
        *,
        interval_minutes: int = 5,
        curiosity_provider: JobProvider = default_provider,
        refinement_provider: JobProvider = default_provider,
        improvement_provider: JobProvider = default_provider,
        executor: JobExecutor = default_executor,
        telemetry: Optional[TelemetryEmitter] = None,
    ) -> None:
        self.interval_minutes = interval_minutes
        self.curiosity_provider = curiosity_provider
        self.refinement_provider = refinement_provider
        self.improvement_provider = improvement_provider
        self.executor = executor
        self.telemetry = telemetry or TelemetryEmitter()
        self.trigger_engine = TriggerEngine()

    # --------------------------------------------------------------------- #
    # Public entry points
    # --------------------------------------------------------------------- #
    def run_once(self, user_id: str) -> Dict[str, Any]:
        """
        Run processing loop once for a given user.
        """
        record = agents.ensure_agent_record(user_id)
        policy = agents.get_agent_policy(user_id)
        state_store = agents.AgentStateStore(user_id)
        state = state_store.load()
        mailbox = agents.AgentMailbox(user_id)
        trigger_config = self.trigger_engine.load_config(user_id)

        self.telemetry.emit(
            "agent_run",
            {
                "agent_id": record.agent_id,
                "user_id": record.user_id,
                "autonomy": policy.autonomy,
                "status": state.status,
                "pending": len(state.pending_jobs),
            },
        )

        inbox_entries, inbox_index = mailbox.read_inbox(start_index=state.inbox_cursor)
        trigger_entries: List[Dict[str, Any]] = []
        new_jobs: List[AgentJob] = []
        for entry in inbox_entries:
            if isinstance(entry, dict) and str(entry.get("type", "")).startswith("trigger."):
                trigger_entries.append(entry)
                continue
            job = self._normalize_job(entry, source="inbox")
            new_jobs.append(job)
            state.register_job(job.__dict__)
            self.telemetry.emit(
                "job_enqueued",
                {
                    "agent_id": record.agent_id,
                    "user_id": record.user_id,
                    "job_id": job.job_id,
                    "kind": job.kind,
                    "source": job.source,
                    "reason": "inbox",
                },
            )

        # Step 2: Curiosity jobs
        for payload in self.curiosity_provider(record.user_id, policy, state) or []:
            job = self._normalize_job(payload, source="curiosity", default_kind="nudge")
            new_jobs.append(job)
            state.register_job(job.__dict__)
            self.telemetry.emit(
                "job_enqueued",
                {
                    "agent_id": record.agent_id,
                    "user_id": record.user_id,
                    "job_id": job.job_id,
                    "kind": job.kind,
                    "source": job.source,
                    "reason": "curiosity_threshold",
                },
            )

        # Step 3: Refinement jobs
        for payload in self.refinement_provider(record.user_id, policy, state) or []:
            job = self._normalize_job(payload, source="refinement", default_kind="refine")
            new_jobs.append(job)
            state.register_job(job.__dict__)
            self.telemetry.emit(
                "job_enqueued",
                {
                    "agent_id": record.agent_id,
                    "user_id": record.user_id,
                    "job_id": job.job_id,
                    "kind": job.kind,
                    "source": job.source,
                    "reason": "refinement_pending",
                },
            )

        # Step 4: Self-improvement jobs
        for payload in self.improvement_provider(record.user_id, policy, state) or []:
            job = self._normalize_job(payload, source="self_improvement", default_kind="analyze")
            new_jobs.append(job)
            state.register_job(job.__dict__)
            self.telemetry.emit(
                "job_enqueued",
                {
                    "agent_id": record.agent_id,
                    "user_id": record.user_id,
                    "job_id": job.job_id,
                    "kind": job.kind,
                    "source": job.source,
                    "reason": "telemetry_available",
                },
            )

        # Step 4b: Weekly learning update (Phase 3b)
        learning_job = self._check_learning_update(record.user_id, state)
        if learning_job:
            new_jobs.append(learning_job)
            state.register_job(learning_job.__dict__)
            self.telemetry.emit(
                "job_enqueued",
                {
                    "agent_id": record.agent_id,
                    "user_id": record.user_id,
                    "job_id": learning_job.job_id,
                    "kind": learning_job.kind,
                    "source": learning_job.source,
                    "reason": "weekly_learning_cycle",
                },
            )

        # Step 4c: Autonomy scheduler (Phase 5.A)
        autonomy_result = self._run_autonomy_scheduler(record.user_id, policy)
        if autonomy_result and autonomy_result.get("tasks_executed", 0) > 0:
            self.telemetry.emit(
                "autonomy_cycle_completed",
                {
                    "agent_id": record.agent_id,
                    "user_id": record.user_id,
                    "tasks_executed": autonomy_result["tasks_executed"],
                    "results": autonomy_result.get("results", []),
                },
            )

        # Step 5: Trigger events
        trigger_jobs = self._process_triggers(record, policy, state, trigger_entries, trigger_config)
        new_jobs.extend(trigger_jobs)

        # Step 5: RSC collaboration messages
        rsc_jobs = self._process_rsc_messages(record.user_id, policy, state, mailbox)
        new_jobs.extend(rsc_jobs)

        executed, proposed, failures = self._dispatch_jobs(record, policy, state, mailbox, new_jobs)

        state.inbox_cursor = inbox_index
        _, outbox_index = mailbox.read_outbox(start_index=0)
        state.outbox_cursor = outbox_index
        state.last_run = _utc_iso(_utc_now())
        state.status = "idle"
        state.run_count += 1
        state.next_run = _utc_iso(_utc_now() + timedelta(minutes=self.interval_minutes))
        state.pending_jobs = self._prune_jobs(state.pending_jobs)

        state_store.save(state)

        summary = {
            "user_id": record.user_id,
            "agent_id": record.agent_id,
            "executed": executed,
            "proposed": proposed,
            "failures": failures,
            "pending_after": len(state.pending_jobs),
        }
        logger.info("Agent %s run summary %s", record.agent_id, summary)
        return summary

    def loop(self, user_id: str) -> None:
        """
        Run continuously with the configured interval.
        """
        while True:
            try:
                self.run_once(user_id)
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("Agent daemon loop failed: %s", exc)
            time.sleep(self.interval_minutes * 60)

    # ------------------------------------------------------------------ #
    # Job helpers
    # ------------------------------------------------------------------ #
    def _normalize_job(
        self,
        payload: Dict[str, Any],
        *,
        source: str,
        default_kind: str = "nudge",
    ) -> AgentJob:
        """
        Ensure payload has required fields for execution pipeline.
        """
        data = dict(payload or {})
        job_id = str(data.get("job_id") or f"{source}-{_utc_now().timestamp()}").replace(" ", "-")
        kind = str(data.get("kind") or data.get("type") or default_kind).lower()
        autonomy = str(data.get("required_autonomy") or data.get("autonomy") or self._default_autonomy(kind)).lower()
        if autonomy not in AUTONOMY_ORDER:
            autonomy = self._default_autonomy(kind)
        metadata = dict(data.get("metadata") or {})
        job_payload = dict(data.get("payload") or {})
        # Coerce top-level fields into payload for convenience
        for key in ("trait_id", "agenda_item", "reason"):
            if key in data and key not in job_payload:
                job_payload[key] = data[key]
        return AgentJob(job_id=job_id, kind=kind, payload=job_payload, source=source, required_autonomy=autonomy, metadata=metadata)

    @staticmethod
    def _default_autonomy(kind: str) -> str:
        mapping = {
            "nudge": "semi",
            "refine": "semi",
            "resolve": "auto",
            "analyze": "auto",
        }
        return mapping.get(kind, "propose")

    def _dispatch_jobs(
        self,
        record: agents.AgentRecord,
        policy: agents.AgentPolicy,
        state: agents.AgentState,
        mailbox: agents.AgentMailbox,
        jobs: Iterable[AgentJob],
    ) -> Tuple[int, int, int]:
        executed = 0
        proposed = 0
        failures = 0

        quota = policy.quotas.get("jobs_per_day", 50)
        today_key = _today_key()
        executed_today = int(state.job_counts.get(today_key, 0))

        for job in jobs:
            if not job.job_id:
                continue

            if executed_today >= quota:
                state.mark_job(job.job_id, status="quota_exceeded", result={"quota": quota})
                mailbox.append_outbox(
                    {
                        "job_id": job.job_id,
                        "status": "quota_exceeded",
                        "message": f"Daily quota reached ({quota})",
                        "kind": job.kind,
                        "source": job.source,
                    }
                )
                self.telemetry.emit(
                    "job_failed",
                    {
                        "agent_id": record.agent_id,
                        "user_id": record.user_id,
                        "job_id": job.job_id,
                        "kind": job.kind,
                        "reason": "quota_exceeded",
                    },
                )
                failures += 1
                continue

            if AUTONOMY_ORDER[policy.autonomy] < AUTONOMY_ORDER[job.required_autonomy]:
                state.mark_job(job.job_id, status="awaiting_manual", result={"required": job.required_autonomy})
                mailbox.append_outbox(
                    {
                        "job_id": job.job_id,
                        "status": "awaiting_manual",
                        "required_autonomy": job.required_autonomy,
                        "agent_autonomy": policy.autonomy,
                        "kind": job.kind,
                    }
                )
                self.telemetry.emit(
                    "job_enqueued",
                    {
                        "agent_id": record.agent_id,
                        "user_id": record.user_id,
                        "job_id": job.job_id,
                        "kind": job.kind,
                        "source": job.source,
                        "reason": "insufficient_autonomy",
                    },
                )
                proposed += 1
                continue

            try:
                required_capability = None
                if isinstance(job.metadata, dict):
                    required_capability = job.metadata.get("required_capability")
                if required_capability:
                    ensure_capability_available(record.user_id, required_capability)

                sensitive_namespaces = None
                if isinstance(job.metadata, dict):
                    sensitive_namespaces = job.metadata.get("sensitive_namespaces")
                if not sensitive_namespaces and isinstance(job.payload, dict):
                    sensitive_namespaces = job.payload.get("sensitive_namespaces")
                if sensitive_namespaces:
                    ensure_consent(record.user_id, sensitive_namespaces)

                # Phase 3b: Route learning_update jobs to dedicated executor
                if job.kind == "learning_update":
                    from ReDNACoreDemo.core.agent_providers import learning_executor
                    result = learning_executor(record.user_id, job.payload)
                    # Update state metadata with last_learning_update timestamp
                    state.metadata["last_learning_update"] = _utc_iso(_utc_now())
                else:
                    result = self.executor(job, policy)

                mailbox.append_outbox(
                    {
                        "job_id": job.job_id,
                        "status": "completed",
                        "kind": job.kind,
                        "result": result,
                        "source": job.source,
                    }
                )
                state.mark_job(job.job_id, status="completed", result=result)
                executed_today += 1
                executed += 1
                state.increment_job_count(today_key)
                state.increment_job_count(job.kind)
                self.telemetry.emit(
                    "job_completed",
                    {
                        "agent_id": record.agent_id,
                        "user_id": record.user_id,
                        "job_id": job.job_id,
                        "kind": job.kind,
                        "source": job.source,
                    },
                )
            except ConsentDeniedError as exc:
                state.mark_job(job.job_id, status="blocked", result={"error": str(exc)})
                mailbox.append_outbox(
                    {
                        "job_id": job.job_id,
                        "status": "blocked",
                        "kind": job.kind,
                        "error": str(exc),
                        "source": job.source,
                    }
                )
                self.telemetry.emit(
                    "job_failed",
                    {
                        "agent_id": record.agent_id,
                        "user_id": record.user_id,
                        "job_id": job.job_id,
                        "kind": job.kind,
                        "reason": "consent_denied",
                    },
                )
                state.record_error({"job_id": job.job_id, "kind": job.kind, "error": str(exc)})
                audit_event(
                    "job_blocked",
                    {
                        "user_id": record.user_id,
                        "agent_id": record.agent_id,
                        "job_id": job.job_id,
                        "reason": "consent_denied",
                    },
                )
                failures += 1
            except CapabilityError as exc:
                state.mark_job(job.job_id, status="blocked", result={"error": str(exc)})
                mailbox.append_outbox(
                    {
                        "job_id": job.job_id,
                        "status": "blocked",
                        "kind": job.kind,
                        "error": str(exc),
                        "source": job.source,
                    }
                )
                self.telemetry.emit(
                    "job_failed",
                    {
                        "agent_id": record.agent_id,
                        "user_id": record.user_id,
                        "job_id": job.job_id,
                        "kind": job.kind,
                        "reason": "capability_missing",
                    },
                )
                state.record_error({"job_id": job.job_id, "kind": job.kind, "error": str(exc)})
                audit_event(
                    "job_blocked",
                    {
                        "user_id": record.user_id,
                        "agent_id": record.agent_id,
                        "job_id": job.job_id,
                        "reason": "capability_missing",
                    },
                )
                failures += 1
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("Job %s failed: %s", job.job_id, exc)
                state.mark_job(job.job_id, status="failed", result={"error": str(exc)})
                mailbox.append_outbox(
                    {
                        "job_id": job.job_id,
                        "status": "failed",
                        "kind": job.kind,
                        "error": str(exc),
                        "source": job.source,
                    }
                )
                self.telemetry.emit(
                    "job_failed",
                    {
                        "agent_id": record.agent_id,
                        "user_id": record.user_id,
                        "job_id": job.job_id,
                        "kind": job.kind,
                        "reason": "exception",
                    },
                )
                state.record_error({"job_id": job.job_id, "kind": job.kind, "error": str(exc)})
                failures += 1

        return executed, proposed, failures

    def _process_triggers(
        self,
        record: agents.AgentRecord,
        policy: agents.AgentPolicy,
        state: agents.AgentState,
        trigger_entries: List[Dict[str, Any]],
        trigger_config: TriggerConfig,
    ) -> List[AgentJob]:
        jobs: List[AgentJob] = []
        if not trigger_entries:
            return jobs

        for entry in trigger_entries:
            event_type = str(entry.get("type") or "")
            payload = entry.get("payload") or {}
            job: Optional[AgentJob] = None
            job_payload = dict(payload)
            job_metadata: Dict[str, Any] = {"trigger_source": entry.get("source"), "trigger_type": event_type}

            if event_type == "trigger.file_added":
                job_id = f"trigger-analyze-{uuid4().hex[:8]}"
                job_payload.setdefault("watched_paths", trigger_config.file_watcher.paths)
                job_metadata["required_capability"] = "core.agent.run"
                job = AgentJob(
                    job_id=job_id,
                    kind="analyze",
                    payload=job_payload,
                    source="trigger:file",
                    required_autonomy="auto",
                    metadata=job_metadata,
                )
            elif event_type == "trigger.conflict_backlog":
                job_id = f"trigger-resolve-{uuid4().hex[:8]}"
                job_metadata["required_capability"] = "core.refinement.resolve"
                job = AgentJob(
                    job_id=job_id,
                    kind="resolve",
                    payload=job_payload,
                    source="trigger:conflict",
                    required_autonomy="auto",
                    metadata=job_metadata,
                )
            elif event_type == "trigger.telemetry_threshold":
                job_id = f"trigger-analyze-{uuid4().hex[:8]}"
                job_metadata["required_capability"] = "core.agent.run"
                job = AgentJob(
                    job_id=job_id,
                    kind="analyze",
                    payload=job_payload,
                    source="trigger:telemetry",
                    required_autonomy="auto",
                    metadata=job_metadata,
                )
            elif event_type == "trigger.calendar_upcoming":
                job_id = f"trigger-nudge-{uuid4().hex[:8]}"
                job_payload.setdefault("lead_minutes", trigger_config.calendar.lead_minutes)
                job = AgentJob(
                    job_id=job_id,
                    kind="nudge",
                    payload=job_payload,
                    source="trigger:calendar",
                    required_autonomy="semi",
                    metadata=job_metadata,
                )

            if job is None:
                audit_event(
                    "trigger_ignored",
                    {
                        "user_id": record.user_id,
                        "agent_id": record.agent_id,
                        "type": event_type,
                        "reason": "unsupported",
                    },
                )
                continue

            sensitive_namespaces = job_payload.get("sensitive_namespaces")
            if sensitive_namespaces:
                job_metadata["sensitive_namespaces"] = list(sensitive_namespaces)

            jobs.append(job)
            state.register_job(job.__dict__)
            audit_event(
                "trigger_consumed",
                {
                    "user_id": record.user_id,
                    "agent_id": record.agent_id,
                    "type": event_type,
                    "job_id": job.job_id,
                    "action": "enqueued",
                    "sensitive_namespaces": job_metadata.get("sensitive_namespaces"),
                },
            )
        return jobs

    def _process_rsc_messages(
        self,
        user_id: str,
        policy: agents.AgentPolicy,
        state: agents.AgentState,
        mailbox: agents.AgentMailbox,
    ) -> List[AgentJob]:
        """
        Process inbound RSC messages and convert to local jobs.

        - invite → validate policy/consent → enqueue rsc_draft job + send accept/decline
        - brief → store to outbox + audit
        - close → finalize thread + audit
        - Expire old invites (send decline with reason expired)
        """
        from ReDNACoreDemo.agents.messages import RSCMessageStore, send_message
        from ReDNACoreDemo.agents.policy import can_receive_rsc_message

        # Only process if RSC is enabled
        if not policy.rsc_enabled:
            return []

        store = RSCMessageStore(user_id)
        inbox = store.read_inbox(include_expired=False, limit=50)
        jobs: List[AgentJob] = []

        for msg in inbox:
            # Check if we've already processed this message
            existing = next((j for j in state.pending_jobs if j.get("rsc_message_id") == msg.id), None)
            if existing:
                continue

            from_agent = msg.from_agent
            can_receive, reason = can_receive_rsc_message(policy, from_agent)

            if msg.type == "rsc_invite":
                # Validate recipient can receive from this sender
                if not can_receive:
                    # Send decline with reason
                    try:
                        partner_user_id = from_agent.replace("hc_", "")
                        send_message(
                            from_user_id=user_id,
                            to_user_id=partner_user_id,
                            message_type="rsc_decline",
                            topic=msg.topic,
                            thread_id=msg.thread_id,
                            in_reply_to=msg.id,
                            payload={"reason": reason},
                            ttl_seconds=msg.ttl_seconds,
                        )
                        self.telemetry.emit(
                            "rsc_invite_declined",
                            {
                                "user_id": user_id,
                                "message_id": msg.id,
                                "from_agent": from_agent,
                                "reason": reason,
                            },
                        )
                    except Exception:
                        pass
                    continue

                # TODO: Check consent for sensitive namespaces in constraints

                # Create local job for this invite
                job_payload = {
                    "rsc_message_id": msg.id,
                    "rsc_thread_id": msg.thread_id,
                    "topic": msg.topic,
                    "constraints": msg.constraints,
                    "from_agent": from_agent,
                }

                job = AgentJob(
                    job_id=f"rsc_draft_{msg.id[:12]}",
                    kind="rsc_draft",
                    payload=job_payload,
                    source="rsc",
                    required_autonomy=policy.autonomy,
                    metadata={"rsc_invite_id": msg.id},
                )
                jobs.append(job)
                state.register_job(job.__dict__)

                # Send accept
                try:
                    partner_user_id = from_agent.replace("hc_", "")
                    send_message(
                        from_user_id=user_id,
                        to_user_id=partner_user_id,
                        message_type="rsc_accept",
                        topic=msg.topic,
                        thread_id=msg.thread_id,
                        in_reply_to=msg.id,
                        ttl_seconds=msg.ttl_seconds,
                    )
                    self.telemetry.emit(
                        "rsc_invite_accepted",
                        {
                            "user_id": user_id,
                            "message_id": msg.id,
                            "from_agent": from_agent,
                            "job_id": job.job_id,
                        },
                    )
                except Exception:
                    pass

            elif msg.type == "rsc_brief":
                # Store brief and audit
                mailbox.append_outbox(
                    {
                        "type": "rsc_brief_received",
                        "message_id": msg.id,
                        "thread_id": msg.thread_id,
                        "from_agent": from_agent,
                        "payload": msg.payload,
                    }
                )
                self.telemetry.emit(
                    "rsc_brief_received",
                    {
                        "user_id": user_id,
                        "message_id": msg.id,
                        "thread_id": msg.thread_id,
                        "from_agent": from_agent,
                    },
                )

            elif msg.type == "rsc_accept":
                # Log acceptance
                self.telemetry.emit(
                    "rsc_invite_accepted_by_partner",
                    {
                        "user_id": user_id,
                        "message_id": msg.id,
                        "thread_id": msg.thread_id,
                        "from_agent": from_agent,
                    },
                )

            elif msg.type == "rsc_decline":
                # Log decline
                self.telemetry.emit(
                    "rsc_invite_declined_by_partner",
                    {
                        "user_id": user_id,
                        "message_id": msg.id,
                        "thread_id": msg.thread_id,
                        "from_agent": from_agent,
                        "reason": msg.payload.get("reason", "unknown"),
                    },
                )

            elif msg.type == "rsc_close":
                # Finalize thread
                self.telemetry.emit(
                    "rsc_thread_closed",
                    {
                        "user_id": user_id,
                        "message_id": msg.id,
                        "thread_id": msg.thread_id,
                        "from_agent": from_agent,
                    },
                )

        # Process expired invites in inbox
        expired = store.read_inbox(include_expired=True, limit=100)
        for msg in expired:
            if not msg.is_expired():
                continue
            if msg.type != "rsc_invite":
                continue

            # Check if we already declined this
            existing_decline = next(
                (m for m in store.read_sent(thread_id=msg.thread_id) if m.type == "rsc_decline" and m.in_reply_to == msg.id),
                None,
            )
            if existing_decline:
                continue

            # Send decline with expired reason
            try:
                partner_user_id = msg.from_agent.replace("hc_", "")
                send_message(
                    from_user_id=user_id,
                    to_user_id=partner_user_id,
                    message_type="rsc_decline",
                    topic=msg.topic,
                    thread_id=msg.thread_id,
                    in_reply_to=msg.id,
                    payload={"reason": "expired"},
                    ttl_seconds=86400,
                )
                self.telemetry.emit(
                    "rsc_invite_expired",
                    {
                        "user_id": user_id,
                        "message_id": msg.id,
                        "thread_id": msg.thread_id,
                        "from_agent": msg.from_agent,
                    },
                )
            except Exception:
                pass

        return jobs

    def _check_learning_update(self, user_id: str, state: agents.AgentState) -> Optional[AgentJob]:
        """
        Check if weekly learning update is due and return job if needed.

        Phase 3b: Weekly learning cycle runs every Monday at 00:00 UTC or when
        manually triggered via POST /ui/hc/learning/{user}/recompute.

        Returns:
            AgentJob for learning update, or None if not due
        """
        # Check last learning update from state metadata
        last_update_str = state.metadata.get("last_learning_update")

        now = _utc_now()
        should_update = False

        if not last_update_str:
            # Never run learning update → run now
            should_update = True
        else:
            try:
                # Parse last update timestamp
                last_update = datetime.fromisoformat(last_update_str.replace('Z', '+00:00'))

                # Check if it's been 7+ days
                days_since = (now - last_update).days

                if days_since >= 7:
                    # Check if today is Monday (weekday() == 0) or if we're overdue
                    if now.weekday() == 0 or days_since >= 8:
                        should_update = True
            except (ValueError, AttributeError):
                # Invalid timestamp → run update
                should_update = True

        if not should_update:
            return None

        # Create learning update job
        job = AgentJob(
            job_id=f"learning_update_{now.timestamp()}",
            kind="learning_update",
            payload={"days": 14, "user_id": user_id},
            source="learning_cycle",
            required_autonomy="auto",
            metadata={"scheduled": True}
        )

        return job

    def _run_autonomy_scheduler(self, user_id: str, policy: agents.AgentPolicy) -> Optional[Dict[str, Any]]:
        """
        Run autonomy scheduler cycle for user.

        Phase 5.A: Checks autonomy policy and runs eligible self-scheduled tasks
        (weekly reflection, narrator summary, learning update, voice summary).

        Returns:
            Result dict with tasks_executed and results, or None if scheduler not enabled
        """
        try:
            from .hc_autonomy import load_autonomy_policy
            from .hc_scheduler import run_scheduler_cycle

            # Load autonomy policy
            autonomy_policy = load_autonomy_policy(user_id)

            # Only run if self-scheduling is enabled
            if not autonomy_policy.self_schedule:
                return None

            # Run scheduler cycle
            result = run_scheduler_cycle(user_id)

            logger.info(
                f"Autonomy scheduler completed for {user_id}: "
                f"{result['tasks_executed']} tasks executed"
            )

            return result

        except Exception as exc:
            logger.exception(f"Autonomy scheduler failed for {user_id}: {exc}")
            return None

    @staticmethod
    def _prune_jobs(jobs: List[Dict[str, Any]], limit: int = 50) -> List[Dict[str, Any]]:
        sanitized: List[Dict[str, Any]] = []
        for job in jobs:
            if not isinstance(job, dict):
                continue
            sanitized.append(job)
        if len(sanitized) > limit:
            return sanitized[-limit:]
        return sanitized


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Agentic Head Coach background daemon")
    parser.add_argument("--user", required=True, help="User ID (e.g., USER1)")
    parser.add_argument("--interval", type=int, default=5, help="Run interval in minutes (loop mode)")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--run-once", action="store_true", dest="once", help="Alias for --once")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)

    # Wire up real providers if available
    from ReDNACoreDemo.core import agent_providers

    daemon = AgentDaemon(
        interval_minutes=args.interval,
        curiosity_provider=agent_providers.curiosity_provider,
        refinement_provider=agent_providers.refinement_provider,
        improvement_provider=agent_providers.improvement_provider,
    )

    if args.once:
        daemon.run_once(args.user)
    else:
        daemon.loop(args.user)


if __name__ == "__main__":  # pragma: no cover
    main()
