# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in MCPScout, please report it responsibly.

**DO NOT open a public issue for security vulnerabilities.**

### How to Report

1. Email: [Create an issue on GitHub](https://github.com/JonusNattapong/MCPScout/issues) with label "security"
2. Or contact the maintainer directly

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial assessment**: Within 1 week
- **Fix release**: Depends on severity

## Security Considerations

### MCPScout is a Tool

MCPScout is designed for legitimate web crawling and data extraction. Users are responsible for:

- Respecting website terms of service
- Following robots.txt directives  
- Complying with local laws and regulations
- Not using for malicious purposes

### API Keys

- MCPScout works without API keys for most features
- If you add OpenAI API key for summarization, keep it secure
- Never commit API keys to version control
- Use environment variables for sensitive data

### Network Security

- MCPScout makes outbound HTTP requests
- Be aware of what data is being sent
- Rate limiting is built-in to prevent abuse
- Stealth mode should be used responsibly

## Best Practices

1. Run MCPScout in isolated environments when possible
2. Keep dependencies updated
3. Review crawled content before sharing
4. Use Docker for deployment
5. Monitor rate limiter statistics
