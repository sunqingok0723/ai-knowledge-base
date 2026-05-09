# AI 知识库工作流配置

## 工作流概述

本文档定义了 AI 知识库采集系统的完整工作流，包括三个 Agent（Collector → Analyzer → Organizer）的协作方式、数据传递机制和执行策略。

---

## 工作流管道

```mermaid
graph LR
    A[Collector] -->|raw/*.json| B[Analyzer]
    B -->|analyzed/*.json| C[Organizer]
    C -->|articles/{YYYY}/{MM}/*.json| D[知识库]
```

---

## Agent 协作流程

### 阶段 1: 数据采集（Collector）

**触发条件**:
- 定时任务（默认每小时）
- 手动触发

**输入**: 无（自主搜索外部数据源）

**输出**: `knowledge/raw/{source}-{date}.json`

**数据源优先级**:
1. WebFetch: GitHub Trending / Hacker News
2. Bash + curl: 代理降级方案
3. GitHub API: 备用数据源
4. 本地缓存: 兜底方案

**传递给**: Analyzer Agent

---

### 阶段 2: 深度分析（Analyzer）

**触发条件**:
- 检测到 `knowledge/raw/` 新文件
- 手动触发

**输入**: `knowledge/raw/*.json`

**输出**: `knowledge/analyzed/{source}-{date}.json`

**处理步骤**:
1. 读取原始采集数据
2. 调用 LLM 进行深度分析
3. 生成结构化摘要、亮点、评分
4. 推荐技术标签和难度等级
5. 保存分析结果

**传递给**: Organizer Agent

---

### 阶段 3: 整理入库（Organizer）

**触发条件**:
- 检测到 `knowledge/analyzed/` 新文件
- 手动触发

**输入**: `knowledge/analyzed/*.json`

**输出**: `knowledge/articles/{YYYY}/{MM}/*.json`

**处理步骤**:
1. URL 去重检查
2. 标题相似度去重
3. 格式标准化
4. 生成唯一 ID
5. JSON Schema 验证
6. 按日期组织目录
7. 写入知识条目

**最终状态**: `pending`（待审核后改为 `published`）

---

## 数据传递机制

### 文件传递模式（当前实现）

```
Collector → 写入 raw/*.json → Analyzer 读取
                          ↓
Analyzer → 写入 analyzed/*.json → Organizer 读取
                          ↓
Organizer → 写入 articles/{YYYY}/{MM}/*.json
```

**优点**: 简单可靠，易于调试
**缺点**: I/O 开销，需要清理中间文件

### 内存传递模式（未来优化）

```
Collector → 内存管道 → Analyzer → 内存管道 → Organizer
                                      ↓
                                  写入 articles/
```

**优点**: 性能更高，无中间文件
**缺点**: 需要进程间通信机制

---

## 环境配置

### 代理配置（可选）

```bash
# 设置 HTTP 代理
export HTTP_PROXY=http://127.0.0.1:10792
export HTTPS_PROXY=http://127.0.0.1:10792

# Git 代理配置
git config --global http.proxy http://127.0.0.1:10792
git config --global https.proxy http://127.0.0.1:10792
```

### GitHub API 配置（可选）

```bash
# 创建个人访问令牌: https://github.com/settings/tokens
export GITHUB_TOKEN=ghp_xxxxxxxxxxxx
```

### 目录结构

```
ai-knowledge-base/
├── agents/              # Agent 定义
│   ├── collector/
│   ├── analyzer/
│   └── organizer/
├── knowledge/
│   ├── raw/             # 原始采集数据
│   ├── analyzed/        # 分析结果（中间）
│   ├── articles/        # 最终知识条目
│   │   └── {YYYY}/{MM}/
│   └── cache/           # 缓存数据
└── config/              # 配置文件
```

---

## 错误处理

### Collector 错误处理

| 错误类型 | 处理策略 |
|----------|----------|
| WebFetch 超时 | 降级到 Bash + curl |
| 代理连接失败 | 降级到 GitHub API |
| API 限流 | 使用缓存数据 |
| 无数据返回 | 记录错误，发送通知 |

### Analyzer 错误处理

| 错误类型 | 处理策略 |
|----------|----------|
| LLM 调用失败 | 重试 3 次，使用备用模型 |
| 输入解析失败 | 记录原始输入，跳过该条目 |
| 评分异常 | 使用默认评分（5分），记录警告 |

### Organizer 错误处理

| 错误类型 | 处理策略 |
|----------|----------|
| ID 冲突 | 自动生成新序号 |
| JSON 验证失败 | 记录错误，跳过该条目 |
| 目录创建失败 | 检查权限，终止处理 |
| 写入失败 | 记录错误，保留未处理条目 |

---

## 监控与日志

### 执行日志

每个 Agent 执行完成后记录：
- 执行时间
- 处理数量
- 错误信息
- 输出路径

### 质量指标

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 采集成功率 | > 90% | 至少采集到目标数量的 90% |
| 分析完整率 | 100% | 所有条目都应有完整分析 |
| 去重准确率 | > 95% | 误判率低于 5% |
| JSON 有效率 | 100% | 所有入库文件符合 Schema |

---

## 执行策略

### 定时执行

```yaml
schedule:
  collector: "0 * * * *"    # 每小时
  analyzer: "10 * * * *"   # 每小时第10分钟
  organizer: "20 * * * *"  # 每小时第20分钟
```

### 依赖执行

```yaml
pipeline:
  - name: collector
    trigger: cron
  - name: analyzer
    trigger: collector.success
  - name: organizer
    trigger: analyzer.success
```

### 手动执行

```bash
# 单独执行某个 Agent
@collector
@analyzer
@organizer

# 执行完整流程
@workflow:run-all
```

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-05-08 | 初始版本 |
| v1.1 | 2026-05-08 | 根据测试结果调整权限配置，添加降级方案 |
