from __future__ import annotations

import contextvars
import functools
import time
from dataclasses import dataclass, field
from typing import Any, Callable


_CURRENT_RUN: contextvars.ContextVar["RunContext | None"] = contextvars.ContextVar(
    "open_agentops_current_run", default=None
)


@dataclass
class RunContext:
    environment: str = "ci"
    tool_policies: dict[str, dict[str, Any]] = field(default_factory=dict)
    simulators: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)

    def event(self, event_type: str, **payload: Any) -> dict[str, Any]:
        item = {
            "ts": time.time(),
            "type": event_type,
            **payload,
        }
        self.events.append(item)
        return item


def current_run() -> RunContext | None:
    return _CURRENT_RUN.get()


def set_current_run(ctx: RunContext | None):
    return _CURRENT_RUN.set(ctx)


def reset_current_run(token: contextvars.Token) -> None:
    _CURRENT_RUN.reset(token)


def emit_event(event_type: str, **payload: Any) -> None:
    ctx = current_run()
    if ctx is not None:
        ctx.event(event_type, **payload)


def emit_metric(name: str, value: int | float, *, unit: str | None = None, **tags: Any) -> None:
    emit_event("metric", name=name, value=value, unit=unit, tags=tags)


def _mode_for(policy: dict[str, Any], environment: str) -> str:
    key = f"{environment}_mode"
    return str(policy.get(key) or policy.get("mode") or "live")


def _result_for_blocked(name: str, reason: str) -> dict[str, Any]:
    return {
        "ok": False,
        "blocked": True,
        "tool": name,
        "reason": reason,
    }


def _result_for_approval(name: str, args: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": False,
        "approval_required": True,
        "tool": name,
        "requested_args": args,
    }


def tool(
    _fn: Callable[..., Any] | None = None,
    *,
    name: str | None = None,
    effect: str = "read",
    ci_mode: str = "live",
    staging_mode: str | None = None,
    production_mode: str | None = None,
    simulator: str | None = None,
    category: str | None = None,
) -> Callable[..., Any]:
    """Decorate an agent tool so test runs can trace and enforce mutation policy."""

    def decorate(fn: Callable[..., Any]) -> Callable[..., Any]:
        tool_name = name or fn.__name__
        default_policy = {
            "effect": effect,
            "ci_mode": ci_mode,
            "staging_mode": staging_mode,
            "production_mode": production_mode,
            "simulator": simulator,
            "category": category,
        }

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            ctx = current_run()
            call_args = {
                "args": list(args),
                "kwargs": kwargs,
            }
            if ctx is None:
                return fn(*args, **kwargs)

            policy = {**default_policy, **ctx.tool_policies.get(tool_name, {})}
            mode = _mode_for(policy, ctx.environment)
            ctx.event(
                "tool_call",
                tool=tool_name,
                effect=policy.get("effect", effect),
                mode=mode,
                args=call_args,
            )

            if mode == "block":
                result = _result_for_blocked(tool_name, f"{tool_name} is blocked in {ctx.environment}")
                ctx.event("tool_result", tool=tool_name, status="blocked", result=result)
                ctx.event("policy_violation", tool=tool_name, reason="blocked_tool_called")
                return result

            if mode == "approval_required":
                result = _result_for_approval(tool_name, call_args)
                ctx.event("approval_request", tool=tool_name, args=call_args, status="pending")
                ctx.event("tool_result", tool=tool_name, status="approval_required", result=result)
                return result

            if mode == "simulate":
                sim_name = str(policy.get("simulator") or simulator or tool_name.split(".")[0])
                sim = ctx.simulators.get(sim_name)
                if sim is not None and hasattr(sim, "call"):
                    result = sim.call(tool_name, *args, **kwargs)
                else:
                    result = {"ok": True, "simulated": True, "tool": tool_name, "args": call_args}
                ctx.event("tool_result", tool=tool_name, status="simulated", result=result)
                return result

            result = fn(*args, **kwargs)
            ctx.event("tool_result", tool=tool_name, status="live", result=result)
            return result

        wrapper.__agentops_tool__ = {
            "name": tool_name,
            "effect": effect,
            "ci_mode": ci_mode,
            "staging_mode": staging_mode,
            "production_mode": production_mode,
            "simulator": simulator,
            "category": category,
        }
        return wrapper

    if _fn is not None:
        return decorate(_fn)
    return decorate
