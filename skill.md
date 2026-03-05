---
name: openclaw-bot-interchat
description: Coordinate owner-approved bot-to-bot tutoring conversations between OpenClaw bots in Discord groups. Use when a user asks to let one bot consult another bot, cross-bot Q&A, bot collaboration, delegation to another bot owner, or controlled inter-bot chat. Enforce explicit owner consent before any bot replies, require known bot/owner identities, cap total rounds, stop on understanding confirmation, and prevent infinite loops or autonomous bot networks.
---

# OpenClaw Bot Interchat

## Objective

Run a controlled tutoring session between two bots in a Discord group:
- Requester bot: asks for help because it lacks a capability.
- Expert bot: can answer after its human owner explicitly approves.
- Session ends when requester bot confirms understanding and tags both humans/bot.

## Required Inputs Before Start

Collect and validate these fields before creating a session:
- `self_owner`: who owns the current bot (Discord user mention or user ID).
- `target_bot`: which bot to ask (bot mention or bot ID, plus display name).
- `target_owner`: owner of the target bot (if unknown, ask and wait).
- `topic` and `goal`.

If any required field is missing:
- Ask a direct follow-up question.
- Keep state at `IDLE` and do not send inter-bot learning messages.

## Required Safety Rules

Apply all rules every time:
- Require explicit owner consent before expert bot sends any knowledge response.
- Deny by default: no consent means no chat.
- Scope consent to one session only. Never treat old consent as reusable.
- Cap conversation length (`MAX_TURNS`, recommended `8`).
- Cap idle wait (`MAX_IDLE_MINUTES`, recommended `10`).
- Cap retries for unclear answers (`MAX_RETRY_PER_QUESTION`, recommended `2`).
- Require a hard stop message when limits are reached.
- Never allow bot-to-bot self-propagation (no inviting third bot without owner approvals).

## Session State Machine

Use this exact state flow:
1. `IDLE`
2. `REQUESTED` (requester bot asks expert bot for help)
3. `PENDING_OWNER_APPROVAL` (expert bot asks its owner)
4. `APPROVED` or `REJECTED`
5. `ACTIVE_CHAT` (structured Q&A rounds)
6. `UNDERSTOOD` or `LIMIT_REACHED` or `TIMEOUT` or `CANCELLED`
7. `CLOSED`

Transition guards:
- `PENDING_OWNER_APPROVAL -> ACTIVE_CHAT` only if owner approval is explicit and recent.
- Any state -> `CLOSED` if owner revokes permission.
- `ACTIVE_CHAT -> CLOSED` when requester bot emits final understanding confirmation.

## Handshake Protocol

### Step 1: Requester bot initiates

Requester bot sends:
- Its owner identity (`self_owner`).
- Target bot identity (`target_bot`).
- What it cannot do.
- What it wants to learn.
- Desired output format (short answer, steps, example).
- Proposed max rounds.

### Step 2: Expert bot asks owner

Expert bot must contact owner with:
- Requester identity (human + bot).
- Topic summary.
- Risk note (data leakage / policy risk).
- Session bounds (max turns, timeout).
- Approve/Reject choices.

### Step 3: Approval result

- If rejected: send polite reject reason and close.
- If approved: publish session constraints and start Q&A.

## Active Chat Rules

Per round in `ACTIVE_CHAT`:
- Keep one question per turn.
- Expert bot answers in bounded format: `Answer`, `Reasoning`, `Mini-check`.
- Requester bot must respond with either:
  - `UNDERSTOOD` + concise restatement, or
  - `NOT_YET` + specific confusion point.
- Increment turn count each round.
- If confusion repeats beyond retry cap, close with escalation to humans.

## Completion Criteria

Requester bot may close as understood only if all are true:
- Can restate the key concept accurately.
- Can provide one concrete example.
- Can state one failure case or boundary.

Then requester bot posts final close message tagging:
- requester owner (e.g. `@小张`)
- expert bot (or expert owner as required by group convention)

## Required End Conditions

Always terminate on first matched condition:
- Understanding achieved.
- `MAX_TURNS` reached.
- `MAX_IDLE_MINUTES` reached.
- Owner revokes permission.
- Human explicitly sends cancel.

No silent termination. Always send a close reason.

## Message Templates

Use or adapt these templates.

### A) Requester -> Expert (initial)

`[Interchat Request] 我是 <requester_bot>（主人：<requester_owner>），想请教 <target_bot>。我在 <topic> 上能力不足，目标是学会 <goal>。期望输出：<format>。建议最多 <N> 轮。`

### B) Expert -> Owner (approval ask)

`[Approval Needed] <requester_bot> 请求就 <topic> 与我互聊。范围：<scope>；上限：<N> 轮；超时：<M> 分钟。是否同意本次会话？回复：同意/拒绝。`

### C) Expert -> Requester (approved)

`[Approved] 已获主人同意。会话开始：最多 <N> 轮，空闲超时 <M> 分钟。请发送第一个具体问题。`

### D) Expert -> Requester (rejected)

`[Rejected] 主人未批准本次互聊（原因：<optional>）。本次会话关闭。`

### E) Round answer format

`Answer: ...`  
`Reasoning: ...`  
`Mini-check: 请你用一句话复述，并给一个例子。`

### F) Final close by requester

`[Session Closed - Understood] @<requester_owner> @<expert_bot_or_owner> 我已理解 <topic>，可独立完成 <task>。感谢本次互聊。`

### G) Limit/timeout close

`[Session Closed - Limit] 已达到 <turn/timeout> 限制，避免无限互聊。建议由 @<requester_owner> 与 @<expert_owner> 人工接管。`

## Implementation Notes

When implementing in code:
- Store per-session fields: `session_id`, `requester_bot`, `requester_bot_id`, `expert_bot`, `expert_bot_id`, `requester_owner`, `requester_owner_id`, `expert_owner`, `expert_owner_id`, `topic`, `goal`, `state`, `turn_count`, `retry_count`, `approved_at`, `expires_at`.
- Attach all bot messages to `session_id` to avoid cross-session mixing.
- Ignore messages not matching current session or channel.
- Use deterministic parsers for control tokens: `同意`, `拒绝`, `UNDERSTOOD`, `NOT_YET`, `CANCEL`.
- Log every state transition with timestamp and actor.
