from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .universal import GenericStatefulSimulator


@dataclass
class MessagingSimulator:
    channels: dict[str, dict[str, Any]] = field(default_factory=dict)
    next_message: int = 1

    def _channel(self, name: str) -> dict[str, Any]:
        return self.channels.setdefault(name, {"messages": []})

    def call(self, tool_name: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        if tool_name.endswith("postMessage") or tool_name.endswith("post_message"):
            return self.post_message(**kwargs)
        if tool_name.endswith("replyInThread") or tool_name.endswith("reply_in_thread"):
            return self.reply_in_thread(**kwargs)
        return {"ok": True, "simulated": True, "tool": tool_name, "args": {"args": args, "kwargs": kwargs}}

    def post_message(self, channel: str, text: str, **_: Any) -> dict[str, Any]:
        message_id = f"sim_msg_{self.next_message:03d}"
        self.next_message += 1
        message = {"id": message_id, "channel": channel, "text": text, "replies": []}
        self._channel(channel)["messages"].append(message)
        return {"ok": True, "simulated": True, "message_id": message_id, "channel": channel}

    def reply_in_thread(self, message_id: str, text: str, **_: Any) -> dict[str, Any]:
        for channel in self.channels.values():
            for message in channel["messages"]:
                if message["id"] == message_id:
                    reply_id = f"sim_reply_{self.next_message:03d}"
                    self.next_message += 1
                    message["replies"].append({"id": reply_id, "text": text})
                    return {"ok": True, "simulated": True, "reply_id": reply_id, "message_id": message_id}
        return {"ok": False, "simulated": True, "error": "message_not_found", "message_id": message_id}

    def state(self) -> dict[str, Any]:
        return {"channels": self.channels}


@dataclass
class PaymentsSimulator:
    refunds: list[dict[str, Any]] = field(default_factory=list)
    next_refund: int = 1

    def call(self, tool_name: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        refund_id = f"sim_refund_{self.next_refund:03d}"
        self.next_refund += 1
        item = {"id": refund_id, "tool": tool_name, "args": {"args": args, "kwargs": kwargs}}
        self.refunds.append(item)
        return {"ok": True, "simulated": True, "refund_id": refund_id}

    def state(self) -> dict[str, Any]:
        return {"refunds": self.refunds}


@dataclass
class RepoIssueSimulator:
    issues: list[dict[str, Any]] = field(default_factory=list)
    next_issue: int = 1

    def call(self, tool_name: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        issue_id = self.next_issue
        self.next_issue += 1
        issue = {"id": issue_id, "tool": tool_name, "args": {"args": args, "kwargs": kwargs}}
        self.issues.append(issue)
        return {"ok": True, "simulated": True, "issue_id": issue_id}

    def state(self) -> dict[str, Any]:
        return {"issues": self.issues}


@dataclass
class EmailSimulator:
    messages: list[dict[str, Any]] = field(default_factory=list)
    next_message: int = 1

    def call(self, tool_name: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        message_id = f"sim_email_{self.next_message:03d}"
        self.next_message += 1
        message = {"id": message_id, "tool": tool_name, "args": {"args": args, "kwargs": kwargs}}
        self.messages.append(message)
        return {"ok": True, "simulated": True, "message_id": message_id}

    def state(self) -> dict[str, Any]:
        return {"messages": self.messages}


@dataclass
class CalendarSimulator:
    events: list[dict[str, Any]] = field(default_factory=list)
    next_event: int = 1

    def call(self, tool_name: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        event_id = f"sim_event_{self.next_event:03d}"
        self.next_event += 1
        event = {"id": event_id, "tool": tool_name, "args": {"args": args, "kwargs": kwargs}}
        self.events.append(event)
        return {"ok": True, "simulated": True, "event_id": event_id}

    def state(self) -> dict[str, Any]:
        return {"events": self.events}


@dataclass
class CRMSimulator:
    records: list[dict[str, Any]] = field(default_factory=list)
    next_record: int = 1

    def call(self, tool_name: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        record_id = f"sim_crm_{self.next_record:03d}"
        self.next_record += 1
        record = {"id": record_id, "tool": tool_name, "args": {"args": args, "kwargs": kwargs}}
        self.records.append(record)
        return {"ok": True, "simulated": True, "record_id": record_id}

    def state(self) -> dict[str, Any]:
        return {"records": self.records}


def default_simulators(config: dict[str, Any] | None = None) -> dict[str, Any]:
    simulators: dict[str, Any] = {
        "messaging": MessagingSimulator(),
        "payments": PaymentsSimulator(),
        "repo": RepoIssueSimulator(),
        "email": EmailSimulator(),
        "email": EmailSimulator(),
        "calendar": CalendarSimulator(),
        "crm": CRMSimulator(),
        "crm": CRMSimulator(),
        "crm_alt": CRMSimulator(),
    }
    for name, spec in ((config or {}).get("simulators") or {}).items():
        if name not in simulators:
            simulators[str(name)] = GenericStatefulSimulator(str(name), dict(spec or {}))
    return simulators
