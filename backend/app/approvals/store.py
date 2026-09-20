"""Pending-action storage with the compare-and-set that makes approval
exactly-once.

`claim` is the only door to execution and it is a single locked transition out
of PENDING. Two approvals racing on the same action, or a replay of a decision
that already ran, both lose here rather than in the refund path.
"""

from datetime import datetime, timezone
from threading import Lock

from app.approvals.models import TERMINAL, PendingAction, PendingStatus


class ApprovalError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class InMemoryApprovalStore:
    def __init__(self) -> None:
        self._actions: dict[str, PendingAction] = {}
        self._lock = Lock()

    def create(self, action: PendingAction) -> PendingAction:
        with self._lock:
            if action.pending_id in self._actions:
                raise ApprovalError("DUPLICATE_PENDING", "This pending action already exists.")
            self._actions[action.pending_id] = action
            return action

    def get(self, pending_id: str) -> PendingAction:
        with self._lock:
            action = self._actions.get(pending_id)
            if action is None:
                raise ApprovalError("UNKNOWN_PENDING", "No such pending action.")
            return action

    def pending(self) -> tuple[PendingAction, ...]:
        with self._lock:
            return tuple(a for a in self._actions.values() if a.status is PendingStatus.PENDING)

    def claim(self, pending_id: str, expected_version: int, expected_digest: str) -> PendingAction:
        """Move PENDING -> CLAIMED, or refuse. Only the winner may execute."""
        with self._lock:
            action = self._actions.get(pending_id)
            if action is None:
                raise ApprovalError("UNKNOWN_PENDING", "No such pending action.")
            if action.status in TERMINAL:
                raise ApprovalError("ALREADY_DECIDED", f"This action is already {action.status.value}.")
            if action.status is not PendingStatus.PENDING:
                raise ApprovalError("ALREADY_CLAIMED", "This action is already being executed.")
            if action.version != expected_version:
                raise ApprovalError("STALE_VERSION", "This approval was made against an older state.")
            if action.arguments_sha256 != expected_digest:
                raise ApprovalError("DIGEST_MISMATCH", "The approved action does not match the pending action.")
            claimed = action.transition(PendingStatus.CLAIMED, decided_at=datetime.now(timezone.utc))
            self._actions[pending_id] = claimed
            return claimed

    def settle(self, pending_id: str, status: PendingStatus) -> PendingAction:
        """Record the outcome of a claim. Called only by the claim's winner."""
        with self._lock:
            action = self._actions[pending_id]
            stamps = {"executed_at": datetime.now(timezone.utc)} if status is PendingStatus.EXECUTED else {}
            settled = action.transition(status, **stamps)
            self._actions[pending_id] = settled
            return settled

    def deny(self, pending_id: str, expected_version: int) -> PendingAction:
        with self._lock:
            action = self._actions.get(pending_id)
            if action is None:
                raise ApprovalError("UNKNOWN_PENDING", "No such pending action.")
            if action.status in TERMINAL:
                raise ApprovalError("ALREADY_DECIDED", f"This action is already {action.status.value}.")
            if action.status is not PendingStatus.PENDING:
                raise ApprovalError("ALREADY_CLAIMED", "This action is already being executed.")
            if action.version != expected_version:
                raise ApprovalError("STALE_VERSION", "This approval was made against an older state.")
            denied = action.transition(PendingStatus.DENIED, decided_at=datetime.now(timezone.utc))
            self._actions[pending_id] = denied
            return denied

    def reset(self) -> None:
        with self._lock:
            self._actions = {}
