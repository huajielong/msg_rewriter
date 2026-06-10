<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.0-blue" alt="v1.0"/>
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT"/>
  <img src="https://img.shields.io/badge/python-3.8+-orange" alt="Python 3.8+"/>
  <img src="https://img.shields.io/github/stars/huajielong/msg_rewriter?style=social" alt="Stars"/>
  <img src="https://img.shields.io/badge/LLM-DeepSeek%20%7C%20OpenAI%20%7C%20Local-brightgreen" alt="LLM Support"/>
  <img src="https://img.shields.io/badge/Format%20Safety-100%25%20%F0%9F%94%92-success" alt="Format Safety"/>
</p>

<h1 align="center">✍️ LLM Log Message Rewriter</h1>
<p align="center"><b>Industrial-grade log message rewriting powered by LLM — auto-polish with 100% format specifier protection</b></p>
<p align="center">
  🔒 Format Safety · ⚡ Concurrent Processing · 💰 Smart Dedup · 🔌 Multi-Model Support
</p>

<p align="center">
  <a href="#-quick-start">🚀 Quick Start</a> •
  <a href="#-core-features">⚡ Core Features</a> •
  <a href="#-business-value">💼 Business Value</a> •
  <a href="#-configuration-guide">⚙️ Configuration</a> •
  <a href="#-faq">❓ FAQ</a>
</p>

---

## 🤔 Still manually rewriting thousands of log messages?

Large-scale project refactoring, compliance audits, brand uniformity — each involves rewriting massive amounts of log entries. Manual work is not only time-consuming but also error-prone:

| The Problem | msg_rewriter Solution |
|:------------|:----------------------|
| ❓ Manually rewriting thousands of log lines takes days | ✅ **Minutes-level processing** — LLM-powered batch rewriting vs. 3 days of manual work |
| ❓ Format specifiers like `%s`, `%d`, `%zu` cause runtime crashes if mishandled | ✅ **100% format protection** — regex validation + LLM hard constraints ensure zero errors |
| ❓ API call costs are skyrocketing | ✅ **Smart dedup reduces cost** — saves 90%+ on API expenses |
| ❓ Sensitive logs can't go to public cloud | ✅ **Local model support** — deploy private LLMs, data stays within your network |
| ❓ Rewritten results need manual embedding into code | ✅ **Dual output formats** — standard JSON + Python r-string, ready to use |

### 🔥 Use Cases

> **Codebase Log Normalization** → **Branded Log Unification** → **Compliance Log Review** → **Internationalized Log Polishing**

---

## 🚀 Quick Start

### Requirements

| Dependency | Version |
|:-----------|:-------:|
| Python | 3.8+ |
| requests | latest |

### Installation

```bash
# Clone the repo
git clone https://github.com/huajielong/msg_rewriter.git
cd msg_rewriter

# Install dependencies
pip install requests
```

### Quick Configuration

Configure your API information in `llm_msg_rewriter.py`:

```python
# Config 1: Cloud model (e.g., DeepSeek)
deepseek_config = LLMConfig(
    api_key="your_api_key_here",
    base_url="https://api.deepseek.com/v1/chat/completions",
    model="deepseek-chat"
)

# Config 2: Local private model
local_llm_config = LLMConfig(
    api_key=None,
    base_url="http://192.168.x.x:8000/v1/chat/completions",
    model="qwen3.5:27b"   # Any local model supporting OpenAI format
)
```

### Run

```bash
python llm_msg_rewriter.py
```

---

## ⚡ Core Features

| Feature | Description |
|:--------|:------------|
| 🔒 **Format Safety** | Automatically detects and strictly protects `%s`, `%d`, `%zu`, `%p` and other C/C++ format specifiers — zero risk after rewriting |
| ⚡ **High-Performance Concurrency** | Built-in thread pool scheduler, multi-file concurrent processing, easily handles thousands of log lines |
| 💰 **Smart Dedup Cost Reduction** | Deduplicates input before processing, dramatically reduces LLM API calls (up to 90%+ savings verified) |
| 🔌 **Multi-Model Support** | Compatible with OpenAI-format APIs: DeepSeek / Qwen / any local model |
| 📦 **Industrial-Grade Output** | Dual format: standard JSON + Python `r-string` dictionary, ready for direct code embedding |
| 🛡️ **Format Validation** | Strict before/after format specifier comparison, automatic retry on mismatch |

---

## 💼 Business Value

### Efficiency Boost

```diff
- Manually rewriting 10,000 log lines ≈ 3 days of work
+ msg_rewriter processing 10,000 log lines ≈ 5 minutes
```

### Cost Comparison

| Approach | Cost for 10,000 Lines | Security | Time |
|:---------|:---------------------:|:--------:|:----:|
| **Manual Rewriting** | Days of labor cost | High | 3 days |
| **Cloud LLM (no dedup)** | ~$50 | Medium | 5 min |
| **Cloud LLM (with dedup)** | ~$5 | Medium | 5 min |
| **msg_rewriter + Local LLM** | **~$0** | **High** | **5 min** |

### Business Benefits

| Benefit | Description |
|:--------|:------------|
| 🚀 **R&D Efficiency** | Days of work compressed to minutes |
| 🔒 **Technical Consistency** | 100% format specifier protection, zero runtime errors |
| 💰 **Operating Cost** | Dedup algorithm + local models save 90%+ API expenses |
| 🌐 **Internationalization** | Unified English log polishing, laying groundwork for localization |
| 🏛️ **Compliance & Risk Mitigation** | Data stays within internal network, meeting security compliance requirements |

---

## ⚙️ Configuration Guide

| Parameter | Description | Recommended Value |
|:----------|:------------|:-----------------:|
| `api_key` | LLM service API key | Read from environment variable |
| `base_url` | API endpoint URL | `https://api.deepseek.com/v1/...` |
| `model` | Model name | `deepseek-chat` / `qwen3.5:27b` |

### Using a Local Model

```python
config = LLMConfig(
    api_key=None,
    base_url="http://localhost:8000/v1/chat/completions",
    model="qwen3.5:27b"
)
```

Supports any locally deployed solution compatible with the OpenAI format: Ollama, vLLM, llama.cpp, and more.

---

## ⚙️ Format Protection Principle

```
Input:  "Failed to connect to %s on port %d, error: %s"
                                    ↓
       Regex scan → Extract specifiers → Mark positions → LLM rewrite → Validate → Restore specifiers
                                    ↓
Output: "Unable to establish connection to %s on port %d, error: %s"
                                    ↓
       Format specifier consistency check ✅ 100% match
```

---

## 📁 Project Structure

```
msg_rewriter/
├── llm_msg_rewriter.py     # Main program (core logic)
├── test_log_1.txt          # Test log 1
├── test_log_2.txt          # Test log 2
├── requirements.txt        # Python dependencies
├── LICENSE                 # MIT License
└── README.md               # 💡 You are here
```

---

## ❓ FAQ

<details>
<summary><b>Which LLM models are supported?</b></summary>
Any model compatible with the OpenAI Chat Completions format is supported. Recommended: DeepSeek (cloud) or Qwen3.5:27b (local). Also supports GPT-4o, Claude, and others.
</details>

<details>
<summary><b>Is the format specifier protection really 100% reliable?</b></summary>
Yes. The program scans all C/C++ format specifiers before rewriting and performs a strict format specifier consistency check after LLM rewriting. If specifiers don't match, it automatically retries until they are fully aligned.
</details>

<details>
<summary><b>How do I integrate a local model?</b></summary>
Deployment options: Ollama (recommended), vLLM, llama.cpp, etc. Any setup providing an OpenAI-compatible HTTP endpoint works. See the "Using a Local Model" section above for a configuration example.
</details>

<details>
<summary><b>How many log lines can it handle?</b></summary>
No hard limit. Processing 10,000 log lines takes approximately 5 minutes (depending on LLM response speed). We recommend keeping individual batches under 50,000 lines to avoid timeouts.
</details>

<details>
<summary><b>How does the dedup mechanism work?</b></summary>
Input lines are deduplicated before processing — duplicate logs are rewritten only once and the result is cached and reused. This is highly effective on logs with high repetition rates, saving up to 90%+ on API costs.
</details>

---

## 🤝 Contributing

Contributions of all forms are welcome — submit an Issue, a Pull Request, or help improve the documentation.

<a href="https://github.com/huajielong/msg_rewriter/graphs/contributors">
  <img src="https://img.shields.io/badge/contributions-welcome-brightgreen" alt="Contributions Welcome"/>
</a>

## 📄 License

MIT © [huajielong](https://github.com/huajielong)

---

<p align="center">
  ⭐ If this tool helps you, please give it a Star!
</p>

> [中文说明](README.zh.md)
