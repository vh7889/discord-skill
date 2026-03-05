from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def mention(discord_id: int) -> str:
    return f"<@{discord_id}>"


class Action(str, Enum):
    ALLOW = "allow"
    REPLY_ONLY = "reply_only"
    SILENT_DROP = "silent_drop"
    BLOCK_SAFETY = "block_safety"


@dataclass
class Grant:
    requester_id: int
    approved_at: datetime
    expires_at: datetime


@dataclass
class Decision:
    action: Action
    reason: str
    bot_reply: str | None = None
    owner_notify: str | None = None
    required_mention_id: int | None = None


@dataclass
class PolicyConfig:
    owner_discord_id: int
    pending_ask_limit: int = 3
    default_denied_text: str = "请先获得爸爸同意"
    expired_text: str = "你的授权已到期，请等待主人续权。"
    pending_over_limit_text: str = "已超过等待期追问上限，请等待主人授权。"
    deny_safety_text: str = "该请求涉及隐私或安全敏感内容，无法提供。"


class OwnerGatedGuard:
    """
    严格授权守卫（可嵌入 Discord Bot）:
    - owner: 无条件放行
    - 非 owner: 每次回复前检查授权是否有效
    - 授权过期: 立即停聊 + 通知 owner 续权
    - 未续权时连续追问超过阈值: 静默
    """

    def __init__(self, config: PolicyConfig):
        self.config = config
        self.grants: dict[int, Grant] = {}
        self.pending_ask_count: dict[int, int] = {}

    def authorize(
        self,
        requester_id: int,
        duration_minutes: int,
        approved_by: int,
        now: datetime | None = None,
    ) -> Grant:
        if approved_by != self.config.owner_discord_id:
            raise PermissionError("Only OWNER_DISCORD_ID can authorize chat.")
        if duration_minutes <= 0:
            raise ValueError("duration_minutes must be > 0")
        now = now or _utcnow()
        grant = Grant(
            requester_id=requester_id,
            approved_at=now,
            expires_at=now + timedelta(minutes=duration_minutes),
        )
        self.grants[requester_id] = grant
        self.pending_ask_count[requester_id] = 0
        return grant

    def revoke(self, requester_id: int, revoked_by: int) -> None:
        if revoked_by != self.config.owner_discord_id:
            raise PermissionError("Only OWNER_DISCORD_ID can revoke chat.")
        self.grants.pop(requester_id, None)
        self.pending_ask_count[requester_id] = 0

    def evaluate_before_reply(
        self,
        sender_id: int,
        sender_is_bot: bool,
        message_text: str,
        is_sensitive: bool,
        now: datetime | None = None,
    ) -> Decision:
        now = now or _utcnow()

        # 1) 安全一票否决
        if is_sensitive:
            return Decision(
                action=Action.BLOCK_SAFETY,
                reason="safety_sensitive",
                bot_reply=f"{mention(sender_id)} {self.config.deny_safety_text}",
                required_mention_id=sender_id,
            )

        # 2) owner 无条件放行
        if sender_id == self.config.owner_discord_id:
            return Decision(
                action=Action.ALLOW,
                reason="owner",
                required_mention_id=self.config.owner_discord_id,
            )

        # 3) 非 owner 必须按授权时间窗检查（每次回复前）
        grant = self.grants.get(sender_id)
        if grant and now < grant.expires_at:
            self.pending_ask_count[sender_id] = 0
            return Decision(
                action=Action.ALLOW,
                reason="active_grant",
                required_mention_id=sender_id,
            )

        # 4) 无授权或已过期：先累计追问次数
        count = self.pending_ask_count.get(sender_id, 0) + 1
        self.pending_ask_count[sender_id] = count

        # 达到阈值后静默
        if count > self.config.pending_ask_limit:
            return Decision(
                action=Action.SILENT_DROP,
                reason="pending_ask_over_limit",
            )

        # 前 3 次：回复对方 + 通知 owner 申请/续权
        expired = grant is not None and now >= grant.expires_at
        if expired:
            bot_reply = f"{mention(sender_id)} {self.config.expired_text}"
        else:
            bot_reply = f"{mention(sender_id)} {self.config.default_denied_text}"

        requester_kind = "机器人" if sender_is_bot else "用户"
        owner_notify = (
            f"{mention(self.config.owner_discord_id)} "
            f"{requester_kind} {mention(sender_id)} 正在请求与我对话。"
            "是否同意？若同意请给出时长（例如：同意 20 分钟）。"
        )

        return Decision(
            action=Action.REPLY_ONLY,
            reason="need_owner_approval_or_renewal",
            bot_reply=bot_reply,
            owner_notify=owner_notify,
            required_mention_id=sender_id,
        )


def render_answer_with_required_mention(answer: str, required_mention_id: int) -> str:
    """
    保证每条回复都带目标 mention（人/机器人/主人）。
    """
    prefix = mention(required_mention_id)
    text = answer.strip()
    if text.startswith(prefix):
        return text
    return f"{prefix} {text}"
