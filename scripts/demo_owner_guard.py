from datetime import datetime, timedelta, timezone

from discord_owner_guard import OwnerGatedGuard, PolicyConfig, render_answer_with_required_mention


def main() -> None:
    owner_id = 972435072030474311
    user_id = 123456789

    guard = OwnerGatedGuard(PolicyConfig(owner_discord_id=owner_id, pending_ask_limit=3))
    now = datetime.now(timezone.utc)

    # 未授权：前 3 次会提示并通知主人
    for i in range(1, 4):
        d = guard.evaluate_before_reply(
            sender_id=user_id,
            sender_is_bot=False,
            message_text=f"第{i}次问",
            is_sensitive=False,
            now=now + timedelta(seconds=i),
        )
        print(i, d.action, d.bot_reply, d.owner_notify)

    # 第 4 次：静默
    d = guard.evaluate_before_reply(
        sender_id=user_id,
        sender_is_bot=False,
        message_text="第4次问",
        is_sensitive=False,
        now=now + timedelta(seconds=4),
    )
    print(4, d.action, d.bot_reply, d.owner_notify)

    # 主人授权 1 分钟
    guard.authorize(requester_id=user_id, duration_minutes=1, approved_by=owner_id, now=now)

    # 授权内可回复（并强制 mention）
    d = guard.evaluate_before_reply(
        sender_id=user_id,
        sender_is_bot=False,
        message_text="现在可以聊吗",
        is_sensitive=False,
        now=now + timedelta(seconds=30),
    )
    if d.action.value == "allow":
        print(render_answer_with_required_mention("可以，我们继续。", d.required_mention_id or user_id))

    # 授权过期后再次拦截
    d = guard.evaluate_before_reply(
        sender_id=user_id,
        sender_is_bot=False,
        message_text="过期后再问",
        is_sensitive=False,
        now=now + timedelta(minutes=2),
    )
    print("expired:", d.action, d.bot_reply, d.owner_notify)


if __name__ == "__main__":
    main()
