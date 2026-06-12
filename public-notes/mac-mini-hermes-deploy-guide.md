---
layer: 手段层
date: "2026-06-12"
tags:
  - Hermes
  - Mac Mini
  - 部署
  - 教程
dg-publish: true
---

> 目标：将 Mac Mini 打造成个人 AI 生产力中枢——持久记忆、自我进化、飞书可达、多模型驱动
>
> 本指南基于 2026 年 6 月实际部署全程记录，所有步骤均经过验证。关键踩坑点标注了 ⚠️ 标记。

## 一、前置准备

### 1.1 Mac Mini 基础确认

```bash
sudo pmset -a sleep 0
sudo pmset -a disksleep 0
sudo pmset -a displaysleep 0
sudo pmset -a womp 1
sudo pmset -a autorestart 1
pmset -g | grep -E "sleep|disksleep|displaysleep|womp|autorestart"
```

预期输出：sleep 0, disksleep 0, displaysleep 0, womp 1, autorestart 1

### 1.2 检查依赖

```bash
git --version
```

Hermes 安装器会自动处理 uv、Python 3.11、Node.js 等所有依赖。

### 1.3 准备凭证

| 凭证 | 来源 |
|---|---|
| DeepSeek API Key | [platform.deepseek.com/api_keys](https://platform.deepseek.com/api_keys) |
| micuapi Claude 令牌 | [www.micuapi.ai](https://www.micuapi.ai) → 控制台 → 创建令牌 → 分组选 `vip_1_ext` |
| micuapi GPT 令牌 | 同上 → 创建令牌 → 分组选 `vip_2`，model 填 `gpt-5.4` |
| 飞书账号 | 你已有的 |

---

## 二、理解架构

```
Hermes（Mac Mini 上运行，你的 agent 大脑）
  │
  ├─ DeepSeek：内置 provider，DEEPSEEK_API_KEY 从 ~/.hermes/.env 读取
  │
  ├─ Claude：custom_provider → https://www.micuapi.ai（不带 /v1，Anthropic 协议）
  │
  ├─ GPT：custom_provider → https://www.micuapi.ai/v1（带 /v1，OpenAI 兼容）
  │
  └─ 飞书 Gateway：WebSocket 直连 open.feishu.cn，无需代理
```

关键原则：
- **DeepSeek 用 Hermes 内置原生 provider**——不经过 custom_providers，避免命名冲突
- **Claude 和 GPT 通过 micuapi 中转**，各自用对应分组的 token
- **CC Switch 不接管 Hermes 配置**——直接手写 config.yaml 是最可靠的方式
- **飞书是国内部署的最优解**——零代理依赖，扫码创建

---

## 三、Step 1：安装 Hermes Agent

```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
source ~/.zshrc
hermes --version
```

> uv 管理的 Python 3.11 与 brew 安装的 Python 互不冲突。

---

## 四、Step 2：配置 config.yaml

⚠️ **不要用 CC Switch 管理 Hermes 配置。** 实测 CC Switch v3.16 写入的 config.yaml 有三个问题：顶层 model 字段缺失导致 Hermes 找不到当前 provider；GPT 供应商的 models 列表被 Claude 模型名污染；base_url 格式与 micuapi 要求不一致。直接手写 config.yaml 是最可靠的。

打开编辑器：

```bash
nano ~/.hermes/config.yaml
```

写入以下完整配置：

```yaml
model:
  provider: deepseek
  model: deepseek-v4-pro

custom_providers:
  - name: micu-claude
    base_url: https://www.micuapi.ai
    api_key: sk-xxxx...xxxx
    api_mode: anthropic_messages
    model: claude-sonnet-4-6

  - name: micu-gpt
    base_url: https://www.micuapi.ai/v1
    api_key: sk-xxxx...xxxx
    api_mode: chat_completions
    model: gpt-5.4
```

⚠️ 三个关键点：
- **顶层 `provider: deepseek` 而不是 `custom`**——用 Hermes 内置的 DeepSeek provider
- **Claude 的 base_url 不带 `/v1`**，GPT 的**带 `/v1`**——micuapi 文档明确要求
- **不要写 `models:` 块**——只留 `model:` 一行指定默认模型。写了 models 列表会导致 `/model` 切换时候选模型错乱

## 五、Step 3：设置环境变量

⚠️ **不要写到 `~/.zshrc`。** Hermes gateway 通过 launchd 启动为系统服务，不读 shell 配置文件。所有环境变量必须写在 `~/.hermes/.env` 里。

```bash
echo 'DEEPSEEK_API_KEY=sk-xxxx...xxxx' >> ~/.hermes/.env
```

> 如果你有多个 DeepSeek API Key 或需要轮换，Hermes 还支持 `hermes auth add deepseek --api-key` 命令管理多 key 池，但单 key 场景 .env 就够用。

## 六、Step 4：验证 CLI 对话

```bash
hermes
```

看到欢迎界面后：

```
你现在用的是什么模型
```

返回 DeepSeek 身份 → 链路通。然后验证 Claude：

```
/model
# 选 micu-claude
```

> ⚠️ 如果报 `Provider resolver returned an empty API key`，说明 config.yaml 的顶层 model 配置有问题。最常见的两个原因：`provider: custom` 但 custom_providers 里没有匹配的 name；或者用了 `provider: deepseek` 但内置 provider 和 custom_providers 里的 deepseek 条目冲突。解法：config.yaml 顶层用 `provider: deepseek`，custom_providers 里不要有 name 为 deepseek 的条目。

## 七、Step 5：配置飞书 Gateway（手机端入口）

### 7.1 为什么是飞书

Telegram 在国内部署需要 Mac Mini 24 小时挂着代理进程。实测 Clash Verge mixed-port 7897、HTTP 代理 CONNECT 隧道与 Python httpx 存在 TLS 握手兼容问题，且 SOCKS5 需要额外装 socksio 依赖。通道选择评估：

| 通道 | 注册门槛 | 代理需求 | 稳定性 |
|---|---|---|
| 飞书 | 扫码创建，零门槛 | 不需要代理 | 企业级 API，长期稳定 |
| Telegram | 需海外号码（+86 成功率低，Fragment 售罄） | 24 小时代理 | Bot API 成熟但国内网络不可达 |
| 微信 iLink | 扫码，零门槛 | 不需要 | 2026 年 4 月新出，群聊不可靠 |

**飞书是这个场景的最优解。**

### 7.2 创建 Bot

```bash
hermes gateway setup
```

选择 **Feishu / Lark** → **扫码创建**。用飞书 App 扫终端显示的二维码，Hermes 自动创建 bot、配置权限、保存凭证。

向导会依次询问：
- Home chat ID：直接回车跳过（后续可配）
- DM policy：选 open
- Group policy：选 disabled（个人使用不需要群聊）

### 7.3 修复白名单（⚠️ 关键步骤）

实测 `hermes gateway setup` 扫码创建后，`FEISHU_ALLOWED_USERS` 默认为空且 `FEISHU_ALLOW_ALL_USERS=false`，导致发了消息也无人授权。

```bash
# 确认当前状态
grep FEISHU_ALLOW_ALL ~/.hermes/.env

# 如果不是 true，改成 true
sed -i '' 's/FEISHU_ALLOW_ALL_USERS=false/FEISHU_ALLOW_ALL_USERS=true/' ~/.hermes/.env
```

### 7.4 启动并验证

```bash
# 前台启动看实时日志
hermes gateway
```

看到 `[Feishu] Sending response` 之后，手机飞书搜 bot 名称发消息，确认能正常回复。

```bash
# Ctrl+C 停掉前台进程，安装为持久化服务
hermes gateway install
```

### 7.5 飞书 Bot 行为

| 场景 | 行为 |
|---|---|
| 私聊 | 回复每一条消息 |
| 群聊 | 仅 @bot 时回复 |

---

## 八、日常使用

### 8.1 在家

```bash
hermes              # 新对话
hermes --continue   # 继续上次
```

| 命令 | 作用 |
|---|---|
| `/model` | 切换模型（DeepSeek ↔ Claude ↔ GPT） |
| `/skills` | 管理技能 |
| `/save` | 保存对话 |
| `/memory` | 管理记忆 |

### 8.2 外出

手机飞书 → bot 私聊 → 发消息。和跟同事聊天体验一致。

### 8.3 关键心法

- 把 Hermes 当**数字同事**，给上下文、目标、约束，让它自己规划路径
- **让它犯错**。你纠正它时，它会把教训存成记忆
- 用 `hermes --continue` 延续对话

---

## 九、快速排查

| 问题 | 检查 |
|---|---|
| `hermes` 找不到 | `source ~/.zshrc` |
| Provider returned empty API key | 检查 config.yaml 顶层 model 的 provider 字段；DEEPSEEK_API_KEY 是否在 ~/.hermes/.env 而非 ~/.zshrc |
| 飞书 bot 不响应 | `grep FEISHU_ALLOW_ALL ~/.hermes/.env` 确认是 true；`hermes gateway restart`；`tail -30 ~/.hermes/logs/gateway.log` |
| Gateway 启动失败 | `tail -30 ~/.hermes/logs/gateway.log` |
| 模型切换不生效 | `/model` 命令确认当前 model；config.yaml 不要有多余的 models: 块 |

---

## 十、完整执行顺序

```
第1步（5分钟）  →  安装 Hermes：curl 一键脚本
第2步（5分钟）  →  手写 config.yaml + .env
第3步（3分钟）  →  CLI 验证三项模型测试
第4步（5分钟）  →  飞书 Bot：hermes gateway setup → 扫码 → 修复白名单
第5步（3分钟）  →  飞书对话验证 → gateway install 持久化
第6步（持续）   →  日常使用，让 agent 积累记忆
```

预计总耗时约 **20 分钟**，比之前少了一半（删除了 CC Switch 的无效操作和 Telegram 的代理调试）。
