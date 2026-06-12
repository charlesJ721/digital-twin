---
layer: 架构层
date: "2026-06-12"
tags:
  - Hermes
  - 架构
  - 会话
dg-publish: true
---

# Hermes 跨平台会话连续性分析

> 创建：2026-06-09 | 来源：与 Hermes 飞书对话

## 问题

从终端切到飞书时，如何让 Hermes 无缝衔接任务进度？是否存在两个 Agent 并行跑同一任务的风险？

## 现状

Hermes 的每个平台（CLI、飞书、Telegram 等）创建独立会话，彼此不共享 session context。Memory（MEMORY.md）和 session_search 是唯二的跨会话桥梁。

### 并行冲突风险

终端 Agent mid-turn（工具调用中未回复）时，飞书 Agent 被唤醒执行同一任务 → 两个进程共享同一文件系统，存在竞态风险。但「用户的注意力是天然互斥锁」——一次只能在一个平台输入——大部分场景不会触发。

## Hermes 社区反馈

### 相关 Issues（全部 Open，P3 优先级）

| Issue | 标题 | 日期 |
|-------|------|------|
| #17193 | Cross-session management across gateways and mediums | 2026-04-29 |
| #8457 | Persistent Session Memory with Cross-Session Search & Auto-Compression | 2026-04-12 |
| #25544 | WeChat + Feishu seamless context handoff | 2026-05-14 |
| #18457 | Cross-Surface Session Continuity | 2026-05-05 |
| #8366 | CLI ↔ Telegram ↔ iMessage handoff | 2026-05-30 |

### #17193 详细内容

提出问题：
- 无法从 Telegram 看到 Web UI 创建的会话
- 无跨媒介统一会话视图
- Session ID 是 UUID，无法跨平台对应
- 未命名会话离开原平台就找不到

提议方案：`/sessions` 命令、`/switch <id>` 命令、跨平台 session 上下文连续性

### #8457 详细内容

提出完整架构方案：每个会话线程独立 markdown 文件，Gateway 重启/跨平台切换时自动加载。生命周期：活跃(24h)→近期(1-7天)→归档(7-30天)→知识提取(>30天)。

结论：均标 P3，无人认领，无 PR 合并。是已知的架构级能力缺口而非 Bug。

## OpenClaw 的解法

**OpenClaw 没有这个问题——所有 DM 默认共享同一个会话。**

架构差异：
- OpenClaw：单一 Gateway 进程拥有所有 session 状态，所有平台连接同一 Gateway
- Hermes：各平台独立会话，Memory + session_search 事后桥接

关键功能：
- `session.dmScope: "main"` —— 所有平台共享会话
- `session.identityLinks` —— 同用户多平台身份链接
- `sessions_send` —— Agent 可向其他会话发消息
- Channel Docking —— 迁移回复路由到其他渠道

### 背景

OpenClaw 和 Hermes 同源——OpenClaw 是原 Nous Research 项目，后 rebrand 为 Hermes Agent。`hermes claw migrate` 可一键迁移。社区 fork (openclaw/openclaw) 仍在维护。

## 融合可行性

将 OpenClaw 做网关 + Hermes 做核心 Agent 的混合架构理论可行，但不实际：
- 两个框架都想拥有 Agent Loop（不是纯路由层+纯执行层）
- Session 归属冲突（都想管理自己的 session 状态）
- 无现成集成点，没有生产级实践

方向：等待 Hermes 自身 Gateway 演进，而非外挂框架。

## 当前最佳实践

1. 长任务用 cron（不卡任何会话）
2. 切换平台前确认对面 Agent 已完成一轮（不在 mid-turn）
3. `session_search` + Memory 做上下文桥接
4. 重要会话命名（`/title`）+ 设定 `/goal` 持久目标
