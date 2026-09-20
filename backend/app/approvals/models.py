"""The pending-action record and its argument digest.

A human approves one exact action, not a tool name and not a category. The
digest is what makes that precise: it binds the decision to the arguments, the
proposal identity and the reset epoch, so an approval cannot be carried across
a restart, a different order, or a changed amount.
"""

import hashlib
import json
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Mapping

DIGEST_VERSION = 1


class PendingStatus(str, Enum):
    PENDING = "PENDING"
    CLAIMED = "CLAIMED"
    EXECUTED = "EXECUTED"
    DENIED = "DENIED"
    FAILED = "FAILED"


TERMINAL = (PendingStatus.EXECUTED, PendingStatus.DENIED, PendingStatus.FAILED)


def digest_for(
    *,
    epoch: int,
    run_id: str,
    proposal_id: str,
    tool_name: str,
    arguments: Mapping[str, object],
) -> str:
    """Hash a versioned envelope, not the arguments alone.

    Hashing arguments by themselves would let an approval for ₹8,499 on one
    run authorize the identical call on another.
    """
    envelope = {
        "v": DIGEST_VERSION,
        "epoch": epoch,
        "run_id": run_id,
        "proposal_id": proposal_id,
        "tool_name": tool_name,
        "arguments": dict(arguments),
    }
    canonical = json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class PendingAction:
    pending_id: str
    run_id: str
    proposal_id: str
    epoch: int
    tool_name: str
    arguments: Mapping[str, object]
    arguments_sha256: str
    policy_reason_code: str
    status: PendingStatus = PendingStatus.PENDING
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    decided_at: datetime | None = None
    executed_at: datetime | None = None

    def __post_init__(self) -> None:
        expected = digest_for(
            epoch=self.epoch,
            run_id=self.run_id,
            proposal_id=self.proposal_id,
            tool_name=self.tool_name,
            arguments=self.arguments,
        )
        if self.arguments_sha256 != expected:
            raise ValueError("Pending action digest does not match its own arguments.")

    def transition(self, status: PendingStatus, **stamps: datetime) -> "PendingAction":
        return replace(self, status=status, version=self.version + 1, **stamps)
