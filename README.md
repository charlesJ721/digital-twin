# Digital Twin v2

[![CI](https://github.com/charlesJ721/digital-twin/actions/workflows/ci.yml/badge.svg)](https://github.com/charlesJ721/digital-twin/actions/workflows/ci.yml)
[![tests](https://img.shields.io/badge/tests-69%20passed-brightgreen)](https://github.com/charlesJ721/digital-twin/actions/workflows/ci.yml)
[![deploy](https://img.shields.io/badge/deploy-GitHub%20Pages-blue)](https://charlesj721.github.io/digital-twin)

数字世界的另一个我——将认知结构与人格特质还原为可交互的数字镜像。

## 是什么

这是一个**通用 Digital Twin 框架**，从 AI 对话中提取人的七层维度（人格、认知、价值观、行为、知识、社会关系、叙事自我），并通过多源整合（Hermes、ChatGPT、Claude 等）持续更新。最终产物是一个静态站点，展示个人维度的完整图谱。

**v2 特性**：多用户支持、框架/实例分离、Phase B 矛盾检测、69 个单元测试 + CI。

## 七层维度

| 层 | 英文 | 中文 | 核心问题 |
|---|------|------|----------|
| 1 | Personality | 人格特质 | 稳定特质、核心动机、恐惧、气质 |
| 2 | Cognitive Architecture | 认知架构 | 推理风格、决策模式、元认知、学习方式 |
| 3 | Values & Beliefs | 价值观与信念 | 伦理、世界观、需求优先级 |
| 4 | Behavioral Patterns | 行为模式 | 习惯、节律、防御机制、能量周期 |
| 5 | Knowledge Structure | 知识结构 | 专长领域、信息食谱、知识组织方式 |
| 6 | Social Relations | 社会关系 | 信任建立、合作模式、影响力、亲密关系 |
| 7 | Narrative Self | 叙事自我 | 自我概念、人生故事、关键转折、身份叙事 |

## 架构

```
┌──────────────────────────────────────────────────────┐
│                     数据来源                           │
│  Hermes (cron job)  │  ChatGPT  │  Claude  │  其他    │
└────────────────────────┬─────────────────────────────┘
                         │ POST /api/user/{u}/insights
                         ▼
┌──────────────────────────────────────────────────────┐
│           Cloudflare Worker API                      │
│      dt-hub.chindowj721.workers.dev                  │
│      接收洞察 → 写入 GitHub → CI 部署                 │
└────────────────────────┬─────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────┐
│           Python 提取管线 (framework/)                │
│   schema → extractors → detectors → quality          │
│   → dimensions.json (私有) + dimensions-public.json  │
└────────────────────────┬─────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────┐
│           Astro 静态站点                             │
│   /u/{user}  │  /dimensions  │  /timeline  │  /notes │
│   部署: GitHub Pages                                 │
└──────────────────────────────────────────────────────┘
```

**关键设计决策**：
- 私有数据 (`dimensions.json`) 和公开投影 (`dimensions-public.json`) 分离
- 多 AI 来源去中心化输入，中心化整合
- Phase B 矛盾检测：当多条洞察互相冲突时标记，而非自动覆盖

## 快速开始

```bash
# 1. 安装 Python 依赖
pip install pyyaml pytest

# 2. 初始化用户
python3 -m framework.cli init --config config.yaml

# 3. 从 Hermes 会话历史引导提取
python3 -m framework.cli bootstrap --from-hermes --days 90

# 4. 运行测试
python3 -m pytest tests/ -v

# 5. 启动 Astro 开发服务器
npm install && npm run dev
```

## 项目结构

```
├── framework/              # Python 提取管线
│   ├── schema.py           # 七层维度模式定义
│   ├── schema/7-layer-schema.yaml  # 模式权威定义
│   ├── extractors.py       # Hermes 会话提取器
│   ├── detectors.py        # 矛盾检测器
│   ├── quality.py          # 质量控制 + 公开投影
│   ├── pipeline.py         # 完整提取管线
│   ├── cli.py              # CLI (init, bootstrap)
│   └── prompts/            # LLM prompt 模板
├── api/                    # Cloudflare Worker
│   ├── src/worker.ts       # API 端点 (GET/POST)
│   └── wrangler.toml       # Worker 配置
├── src/                    # Astro 站点源码
│   └── pages/
│       ├── index.astro     # 首页
│       ├── dimensions/     # 维度展示
│       ├── notes/          # 笔记
│       ├── timeline/       # 时间线
│       ├── tags/           # 标签
│       └── search/         # 搜索 (Pagefind)
├── data/                   # 用户数据
│   └── users/{username}/
│       ├── dimensions.json         # 私有完整数据
│       └── dimensions-public.json  # 公开投影
├── tests/                  # 69 个单元测试
│   ├── test_schema.py
│   ├── test_detectors.py
│   ├── test_quality.py
│   ├── test_extract_insights.py
│   └── test_demo_isolation.py
├── tools/dt                # 提取脚本
├── config.yaml             # 用户配置
├── site.config.json        # 站点配置
└── .github/workflows/
    ├── ci.yml              # CI: 测试 + schema 一致性检查
    └── deploy.yml          # 部署到 GitHub Pages
```

## 开发

```bash
# 运行全部测试
python3 -m pytest tests/ -v

# 运行特定模块
python3 -m pytest tests/test_schema.py -v

# 生成 dimension-map.json（API 使用）
python3 framework/generate_dimension_map.py

# 部署 API
cd api && wrangler deploy
```

## CI

每次 push 到 main 自动运行：
- 全部 69 个 Python 测试
- dimension-map.json 与 schema 一致性检查
- Demo 数据隔离检查

## License

MIT
