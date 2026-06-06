# Security Policy

## Supported Versions

| Version | Supported |
| ------- | --------- |
| 1.0.x   | ✅ Supported |

## 安全注意事项

- **API 密钥**：建议通过环境变量注入，不要硬编码
- **敏感数据**：如涉及机密日志，请使用本地 LLM 部署
- **输出校验**：改写结果建议先在小范围验证再批量替换

## Reporting a Vulnerability

通过 [GitHub Issues](https://github.com/huajielong/msg_rewriter/issues) 报告。
