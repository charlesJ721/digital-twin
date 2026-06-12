---
layer: 手段层
date: "2026-06-12"
tags:
  - 工具
  - 搜索
  - AI
dg-publish: true
---

# 搜索工具对比与调用策略

> 2026-06-09 实测对比 AnySearch、Parallel Search、DDGS，结合社区口碑形成。

## 工具矩阵

| 维度 | AnySearch | Parallel | DDGS |
|------|-----------|----------|------|
| 免费层 | 匿名 per-IP 配额 | **完全免费无注册** | 免费但网络不稳 |
| 中文支持 | **zone=cn + language** | 不支持 | 有限 |
| 结果深度 | 中等（snippet+content） | **极高（结构化 excerpts）** | 弱 |
| 领域过滤 | **22 个垂直领域 + tags** | 无 | 无 |
| 延迟 | ~2-3s | ~3-5s | 不稳定 |
| LLM 优化 | 部分 | **深度优化** | 无 |
| 稳定性 | 新产品（2026.5） | Fortune 500 背书 | API 受限 |

## 调用路由策略

```
收到搜索请求
├─ 中文内容？           → AnySearch (zone=cn)
├─ 特定领域？           → AnySearch (domain=xxx)  
├─ 技术深度查询？       → Parallel (objective+queries)
├─ 通用/日常？          → Parallel（免费、默认）
├─ 深层对比？           → 两者并行，互补深度+覆盖面
└─ 内容抓取补充？       → Firecrawl（已接入）
```

## 社区口碑摘要

- **AnySearch**: 2026.5 上线即登 Skills.sh TOP1，Reddit/X 热议。定位「AI 搜索基础设施」，22 个垂直领域智能路由。解决"Agent 只能搜到 20% 互联网"痛点。
- **Parallel**: Fortune 100/500 使用，专为 LLM 优化的结构化输出。Search MCP 免费无需注册。技术深度查询碾压级优势。
- **DDGS**: 传统 DuckDuckGo，无 LLM 优化，当前网络环境连接不稳定，不推荐作为主方案。

## 已接入的其他搜索相关工具

| 工具 | 用途 | 工具数 |
|------|------|--------|
| Firecrawl MCP | 网页抓取/爬取/监控 | 20 |
| MinerU MCP | 文档解析/OCR | 2 |

## 未接入的备选

- **Tavily**: AI 搜索标杆，LangChain 生态首选，有免费层。和 Parallel 功能重叠，暂不需要。
- **Brave Search**: 独立索引，免费层可能已收紧。用户反馈不支持免费调用，待验证。
- **SearXNG**: 自托管元搜索引擎，完全免费但需运维投入。
