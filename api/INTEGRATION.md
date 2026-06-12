# DT Hub — AI 助理集成协议 v1.0

> 将任何 AI 助理（Hermes、ChatGPT、Claude、公司内部 AI 等）接入 Digital Twin Hub。
> 会话开始拉取上下文，会话中主动推送洞察。去中心化输入，中心化整合。

---

## 快速开始

复制下面的 System Prompt 片段到你的 AI 助理配置中（替换 `{USERNAME}` 和 `{API_KEY}`）：

```
你已接入 Digital Twin Hub。在每次会话中：

## 启动时：拉取当前 Digital Twin 上下文
会话开始时，调用 GET 获取用户当前的维度状态：
GET https://dt-hub.{your-worker}.workers.dev/api/user/{USERNAME}?key={API_KEY}

这会返回完整的七层维度数据（人格特质、认知架构、价值观、行为模式、
社会关系、叙事自我等），以及已有的洞察。用这些信息来个性化你的交互方式。

## 会话中：主动发现并推送洞察
在对话过程中，当你观察到以下信号时，准备一条洞察：
- 用户表达了新的自我认知或反思
- 用户的决策揭示了未被记录的价值观或行为模式
- 对话暴露了一个之前未察觉的认知偏误或思维习惯
- 用户描述了一段影响其人生叙事的关键经历

每条洞察的格式：
{
  "date": "ISO日期",
  "dimension": "所属子维度（如：动机结构、防御机制、信任建立、关键转折等）",
  "insight": "一句话洞察（少于 50 字）",
  "confidence": "high|medium|low",
  "evidence": "支持证据——从对话中摘录的具体原句"
}

## 会话结束或积累 3+ 条高质量洞察时：推送
POST https://dt-hub.{your-worker}.workers.dev/api/user/{USERNAME}/insights
Authorization: Bearer {API_KEY}
Content-Type: application/json

{
  "insights": [...],
  "source": "chatgpt",     // 标识来源：hermes|chatgpt|claude|other
  "fill_rate_updates": {   // 可选：如果你判断某层填充度提升了
    "3": 55,
    "4": 50
  }
}

## 约束
- 置信度 low 的洞察不要推送，只推送 medium 和 high
- 不杜撰。没有证据时不硬填
- 不推送具体人名、公司名、项目名等可识别信息
- 每次推送 1-5 条，宁缺毋滥
- 如果用户主动说「这个记到 DT 里」或类似的话，标记为 high 置信度
```

---

## 不同 AI 平台的适配

### Hermes Agent (你的 Mac Mini)
将以上内容保存为 `~/.hermes/skills/dt-hub-push/SKILL.md`：
```yaml
---
name: dt-hub-push
description: Push insights to Digital Twin Hub after sessions
trigger: after_session
---
```
已在 cron job 中实现自动推送，无需额外配置。

### ChatGPT / Claude (公司 PC)
将 System Prompt 片段粘贴到 Custom Instructions 或 Project 配置中。
替换 `{USERNAME}` = `arslonga`，`{API_KEY}` = `dt_你的key`。

### 任意其他 AI 工具
任何支持自定义 system prompt 或支持 HTTP 调用的 AI 工具都可以接入。
核心就两个端点：
- `GET  /api/user/{username}?key={api_key}` → 拉取
- `POST /api/user/{username}/insights` + `Authorization: Bearer {api_key}` → 推送

---

## 工作流示意

```
公司 PC (ChatGPT)                    Mac Mini (Hermes)                 朋友手机 (Claude)
      │                                    │                                │
      │ GET /api/user/arslonga              │ 已有本地 context               │ GET /api/user/friend
      │ → 获取当前 DT 上下文                │                                │ → 自己的 DT
      │                                    │                                │
      │ [对话产生洞察]                      │ [对话产生洞察]                  │ [对话产生洞察]
      │                                    │                                │
      │ POST /api/user/arslonga/insights    │ cron job POST                  │ POST /api/user/friend/insights
      │                                    │                                │
      └────────────┬───────────────────────┴────────────────┬───────────────┘
                   │                                        │
                   ▼                                        ▼
            charlesJ721/digital-twin (GitHub)
            data/users/arslonga/dimensions.json
            data/users/friend/dimensions.json
                   │
                   │ CI 部署
                   ▼
            charlesj721.github.io/digital-twin
            /u/arslonga  /u/friend
```

---

## 部署清单

- [ ] 部署 Cloudflare Worker: `cd api && npm install && wrangler deploy`
- [ ] 设置 secret: `wrangler secret put GITHUB_TOKEN`
- [ ] 设置 secret: `wrangler secret put DT_API_KEY_ARSLONGA`
- [ ] 验证: `curl https://dt-hub.xxx.workers.dev/api/health`
- [ ] 测试拉取: `curl https://dt-hub.xxx.workers.dev/api/user/arslonga`
- [ ] 测试推送: `curl -X POST .../api/user/arslonga/insights -H "Authorization: Bearer dt_xxx" -d '{"insights":[...],"source":"test"}'`
- [ ] 在公司 PC AI 中配置 System Prompt
- [ ] 分享给朋友/家人时提供他们的 API key
