<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.0-blue" alt="v1.0"/>
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT"/>
  <img src="https://img.shields.io/badge/python-3.8+-orange" alt="Python 3.8+"/>
  <img src="https://img.shields.io/github/stars/huajielong/msg_rewriter?style=social" alt="Stars"/>
  <img src="https://img.shields.io/badge/LLM-DeepSeek%20%7C%20OpenAI%20%7C%20Local-brightgreen" alt="LLM Support"/>
  <img src="https://img.shields.io/badge/Format%20Safety-100%25%20%F0%9F%94%92-success" alt="Format Safety"/>
</p>

<h1 align="center">✍️ LLM Log Message Rewriter</h1>
<p align="center"><b>基于 LLM 的工业级日志改写器 — 自动润色，100% 保护格式占位符</b></p>
<p align="center">
  🔒 格式安全 · ⚡ 并发处理 · 💰 智能去重 · 🔌 多模型兼容
</p>

<p align="center">
  <a href="#-快速开始">🚀 快速开始</a> •
  <a href="#-核心功能">⚡ 核心功能</a> •
  <a href="#-业务价值">💼 业务价值</a> •
  <a href="#-配置指南">⚙️ 配置指南</a> •
  <a href="#-常见问题">❓ 常见问题</a>
</p>

---

## 🤔 还在手动改写成千上万条日志？

大型项目重构、合规检查、品牌化适配——每一样都涉及大量日志的改写。手动操作不仅耗时，还容易出错：

| 你可能遇到的问题 | msg_rewriter 帮你解决 |
|:-----------------|:--------------------|
| ❓ 数千行日志手动改写需要好几天 | ✅ **分钟级处理** — LLM 驱动批量改写，对比 3 天的工作量 |
| ❓ `%s`、`%d`、`%zu` 格式符写错导致运行时崩溃 | ✅ **100% 格式保护** — 正则校验 + LLM 强约束，确保零错误 |
| ❓ API 调用费用居高不下 | ✅ **智能去重降本** — 可节省 90%+ API 费用 |
| ❓ 敏感日志不能传到公有云 | ✅ **本地模型支持** — 接入私有化 LLM，数据不出内网 |
| ❓ 改写结果需要手动嵌入工程代码 | ✅ **双输出格式** — 标准 JSON + Python r-string，即拿即用 |

### 🔥 适用场景

> **代码库日志规范化** → **品牌化日志统一** → **合规性日志审查** → **国际化日志润色**

---

## 🚀 快速开始

### 环境要求

| 依赖 | 版本 |
|:-----|:----:|
| Python | 3.8+ |
| requests | 最新版 |

### 安装

```bash
# 克隆项目
git clone https://github.com/huajielong/msg_rewriter.git
cd msg_rewriter

# 安装依赖
pip install requests
```

### 快速配置

在 `llm_msg_rewriter.py` 中配置你的 API 信息：

```python
# 配置 1: 云端模型 (如 DeepSeek)
deepseek_config = LLMConfig(
    api_key="your_api_key_here",
    base_url="https://api.deepseek.com/v1/chat/completions",
    model="deepseek-chat"
)

# 配置 2: 本地私有化模型
local_llm_config = LLMConfig(
    api_key=None,
    base_url="http://192.168.x.x:8000/v1/chat/completions",
    model="qwen3.5:27b"   # 任何支持 OpenAI 格式的本地模型
)
```

### 运行

```bash
python llm_msg_rewriter.py
```

---

## ⚡ 核心功能

| 功能 | 说明 |
|:-----|:------|
| 🔒 **格式安全保证** | 自动识别并严格保护 `%s`, `%d`, `%zu`, `%p` 等 C/C++ 占位符，改写后直接替换零风险 |
| ⚡ **高性能并发处理** | 内置线程池调度器，多文件并发，轻松应对数千行日志 |
| 💰 **智能去重降本** | 处理前行去重，大幅降低 LLM API 调用成本（实测最高节省 90%+） |
| 🔌 **多模型支持** | 兼容 OpenAI 格式接口：DeepSeek / Qwen / 任意本地模型 |
| 📦 **工业级输出** | 标准 JSON + Python `r-string` 字典双格式，直接嵌入工程代码 |
| 🛡️ **格式验证** | 改写前后格式符严格比对，失败自动重试 |

---

## 💼 业务价值

### 效率提升

```diff
- 手动改写 10,000 条日志 ≈ 3 天工作量
+ msg_rewriter 处理 10,000 条日志 ≈ 5 分钟
```

### 成本对比

| 方案 | 10,000 条日志费用 | 安全性 | 耗时 |
|:-----|:-----------------:|:------:|:----:|
| **人工改写** | 数天人工成本 | 高 | 3 天 |
| **云端 LLM（无去重）** | ~$50 | 中 | 5 分钟 |
| **云端 LLM（有去重）** | ~$5 | 中 | 5 分钟 |
| **msg_rewriter + 本地 LLM** | **~$0** | **高** | **5 分钟** |

### 商业收益

| 收益 | 说明 |
|:-----|:------|
| 🚀 **研发效率** | 数天工作量缩短至分钟级 |
| 🔒 **技术一致性** | 100% 格式符保护，零运行时错误 |
| 💰 **运营成本** | 去重算法 + 本地模型，节省 90%+ API 费用 |
| 🌐 **国际化加速** | 英文日志统一润色，为本地化奠定基础 |
| 🏛️ **合规避险** | 数据不出内网，满足数据安全合规要求 |

---

## ⚙️ 配置指南

| 参数 | 说明 | 推荐值 |
|:-----|:------|:------:|
| `api_key` | LLM 服务 API 密钥 | 从环境变量读取 |
| `base_url` | API 端点地址 | `https://api.deepseek.com/v1/...` |
| `model` | 模型名称 | `deepseek-chat` / `qwen3.5:27b` |

### 使用本地模型

```python
config = LLMConfig(
    api_key=None,
    base_url="http://localhost:8000/v1/chat/completions",
    model="qwen3.5:27b"
)
```

支持任何兼容 OpenAI 格式的本地部署方案：Ollama、vLLM、llama.cpp 等。

---

## ⚙️ 格式保护原理

```
输入: "Failed to connect to %s on port %d, error: %s"
                                   ↓
       正则扫描 → 提取占位符 → 标记位置 → LLM 改写 → 格式验证 → 还原占位符
                                   ↓
输出: "Unable to establish connection to %s on port %d, error: %s"
                                   ↓
       格式符一致性验证 ✅ 100% 匹配
```

---

## 📁 项目结构

```
msg_rewriter/
├── llm_msg_rewriter.py     # 主程序（核心逻辑）
├── test_log_1.txt          # 测试日志 1
├── test_log_2.txt          # 测试日志 2
├── requirements.txt        # Python 依赖
├── LICENSE                 # MIT 许可证
└── README.md               # 💡 你在这里
```

---

## ❓ 常见问题

<details>
<summary><b>支持哪些 LLM 模型？</b></summary>
任何兼容 OpenAI Chat Completions 格式的模型都支持。推荐 DeepSeek（云端）或 Qwen3.5:27b（本地），也支持 GPT-4o、Claude 等。
</details>

<details>
<summary><b>格式符保护真的 100% 可靠吗？</b></summary>
是的。程序在改写前扫描所有 C/C++ 格式占位符，LLM 改写后进行严格的格式符一致性校验。如果格式符不匹配，会自动重试直到完全一致。
</details>

<details>
<summary><b>如何接入本地模型？</b></summary>
部署方式：Ollama（推荐）、vLLM、llama.cpp 等。只要提供兼容 OpenAI 格式的 HTTP 接口即可。配置示例见上方「使用本地模型」。
</details>

<details>
<summary><b>能处理多少条日志？</b></summary>
没有硬性限制。10,000 条日志处理约 5 分钟（取决于 LLM 响应速度）。建议单次处理条数不超过 50,000 条以免超时。
</details>

<details>
<summary><b>去重机制是怎么工作的？</b></summary>
在处理前对输入的行进行去重，重复日志只改写一次，结果缓存复用。在处理大量重复度高的日志时效果显著，最高可节省 90%+ API 费用。
</details>

---

## 🤝 贡献

欢迎任何形式的贡献——提交 Issue、Pull Request 或改进文档。

<a href="https://github.com/huajielong/msg_rewriter/graphs/contributors">
  <img src="https://img.shields.io/badge/contributions-welcome-brightgreen" alt="Contributions Welcome"/>
</a>

## 📄 License

MIT © [huajielong](https://github.com/huajielong)

---

<p align="center">
  ⭐ 如果这个工具对你有帮助，请点个 Star 支持一下！
</p>
