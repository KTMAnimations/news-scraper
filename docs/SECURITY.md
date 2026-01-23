# Security Documentation

This document outlines the security measures, configurations, and best practices for the Micro-Alpha News Scraper platform.

## Table of Contents

1. [Authentication](#authentication)
2. [API Key Management](#api-key-management)
3. [Rate Limiting](#rate-limiting)
4. [Secrets Management](#secrets-management)
5. [WAF Configuration](#waf-configuration)
6. [Common Attack Patterns](#common-attack-patterns)
7. [Security Headers](#security-headers)
8. [Database Security](#database-security)
9. [Monitoring and Alerting](#monitoring-and-alerting)
10. [Incident Response](#incident-response)

---

## Authentication

### JWT Token Authentication

The platform uses JSON Web Tokens (JWT) for session-based authentication:

```
Authorization: Bearer <jwt_token>
```

**Token Configuration:**
- Access token expiry: 30 minutes
- Refresh token expiry: 7 days
- Algorithm: HS256
- Minimum secret key length: 32 characters

**Best Practices:**
- Always use HTTPS in production
- Store tokens securely (HttpOnly cookies or secure storage)
- Implement token refresh before expiry
- Never log or expose tokens in URLs

### API Key Authentication

For programmatic access, the platform supports API keys:

```
X-API-Key: malf_<api_key>
```

**Key Features:**
- Hashed storage (SHA256)
- Prefix for identification (`malf_`)
- Scope-based permissions (`read`, `write`, `admin`)
- Optional expiration dates
- Usage tracking (request count, last IP)

---

## API Key Management

### Subscription Tier Limits

| Tier | Max API Keys | Available Scopes |
|------|--------------|------------------|
| Free | 1 | read |
| Starter | 2 | read, write |
| Professional | 5 | read, write |
| Team | 20 | read, write |
| Enterprise | 100 | read, write, admin |

### API Key Scopes

| Scope | Permissions |
|-------|-------------|
| `read` | Read events, search, view tickers |
| `write` | Create alerts, manage watchlist |
| `admin` | Full API access, manage other users |

### Key Rotation

Regular key rotation is recommended:
- Rotate keys every 90-365 days
- Use the `/api/v1/api-keys/{key_id}/rotate` endpoint
- Old keys are immediately invalidated upon rotation

**Rotation Procedure:**
1. Call the rotate endpoint with the old key ID
2. Store the new key securely
3. Update all applications using the key
4. Verify new key works before removing old references

---

## Rate Limiting

### Tier-Based Limits

Rate limits are enforced per minute based on subscription tier:

| Tier | Requests/Minute |
|------|-----------------|
| Anonymous | 30 |
| Free | 30 |
| Starter | 60 |
| Professional | 300 |
| Team | 600 |
| Enterprise | 3000 |

### Rate Limit Headers

All responses include rate limit information:

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1706000000
Retry-After: 30 (only on 429 responses)
```

### API Key Custom Rate Limits

Enterprise users can set custom rate limits per API key, overriding the tier default.

---

## Secrets Management

### Required Secrets

| Secret | Min Length | Rotation Period | Criticality |
|--------|------------|-----------------|-------------|
| JWT_SECRET_KEY | 32 chars | 90 days | Critical |
| DATABASE_PASSWORD | 16 chars | 180 days | Critical |
| STRIPE_SECRET_KEY | N/A | 365 days | High |
| STRIPE_WEBHOOK_SECRET | N/A | 365 days | High |

### Generating Secure Secrets

```bash
# Generate a 32-byte hex secret
python -c "import secrets; print(secrets.token_hex(32))"

# Generate a URL-safe secret
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Secrets Validation

The application validates secrets on startup:
- **Development**: Warnings logged for weak/default secrets
- **Production**: Application exits if critical secrets are invalid

### Rotation Procedures

#### JWT Secret Key (90 days)
1. Generate new secret: `python -c "import secrets; print(secrets.token_hex(32))"`
2. Update `JWT_SECRET_KEY` in environment
3. Deploy with rolling restart
4. Note: All users will need to re-authenticate

#### Database Password (180 days)
1. Create new database user with new password
2. Update `DATABASE_URL` and `DATABASE_SYNC_URL`
3. Deploy changes with rolling restart
4. Remove old database user

#### Stripe Keys (365 days)
1. Generate new keys in Stripe Dashboard
2. Update webhook endpoints if needed
3. Update environment variables
4. Verify webhooks still work
5. Roll old keys in Stripe Dashboard

---

## WAF Configuration

### Recommended AWS WAF Rules

Configure these rules in AWS WAF or your preferred WAF solution:

#### 1. AWS Managed Rules

```json
{
  "Name": "AWSManagedRulesCommonRuleSet",
  "Priority": 1,
  "OverrideAction": { "None": {} },
  "Statement": {
    "ManagedRuleGroupStatement": {
      "VendorName": "AWS",
      "Name": "AWSManagedRulesCommonRuleSet"
    }
  },
  "VisibilityConfig": {
    "SampledRequestsEnabled": true,
    "CloudWatchMetricsEnabled": true,
    "MetricName": "CommonRuleSetMetric"
  }
}
```

#### 2. SQL Injection Protection

```json
{
  "Name": "SQLInjectionRule",
  "Priority": 2,
  "Statement": {
    "ManagedRuleGroupStatement": {
      "VendorName": "AWS",
      "Name": "AWSManagedRulesSQLiRuleSet"
    }
  }
}
```

#### 3. Known Bad Inputs

```json
{
  "Name": "KnownBadInputsRule",
  "Priority": 3,
  "Statement": {
    "ManagedRuleGroupStatement": {
      "VendorName": "AWS",
      "Name": "AWSManagedRulesKnownBadInputsRuleSet"
    }
  }
}
```

### Custom WAF Rules

#### Rate Limiting Rule
```json
{
  "Name": "RateLimitRule",
  "Priority": 10,
  "Statement": {
    "RateBasedStatement": {
      "Limit": 2000,
      "AggregateKeyType": "IP"
    }
  },
  "Action": { "Block": {} }
}
```

#### Block Suspicious User Agents
```json
{
  "Name": "BlockSuspiciousUA",
  "Priority": 11,
  "Statement": {
    "ByteMatchStatement": {
      "SearchString": "sqlmap",
      "FieldToMatch": { "SingleHeader": { "Name": "User-Agent" } },
      "TextTransformations": [
        { "Priority": 0, "Type": "LOWERCASE" }
      ],
      "PositionalConstraint": "CONTAINS"
    }
  },
  "Action": { "Block": {} }
}
```

#### Geo-Blocking (Optional)
```json
{
  "Name": "GeoBlockRule",
  "Priority": 20,
  "Statement": {
    "GeoMatchStatement": {
      "CountryCodes": ["XX", "YY"]
    }
  },
  "Action": { "Block": {} }
}
```

### Cloudflare WAF Rules

If using Cloudflare:

1. **Enable Managed Rulesets:**
   - Cloudflare Managed Ruleset
   - Cloudflare OWASP Core Ruleset
   - Cloudflare Leaked Credentials Check

2. **Custom Rules:**
```
# Block known attack patterns
(http.request.uri.path contains "..") or
(http.request.uri.path contains "etc/passwd") or
(http.request.uri.query contains "UNION SELECT") or
(http.request.uri.query contains "<script")
```

3. **Rate Limiting:**
```
# Limit auth endpoints
(http.request.uri.path eq "/api/v1/auth/login")
Rate: 10 requests per minute per IP
Action: Challenge
```

---

## Common Attack Patterns

### Attack Patterns to Block

| Attack Type | Pattern | Mitigation |
|-------------|---------|------------|
| SQL Injection | `' OR 1=1--`, `UNION SELECT` | WAF SQLi rules, parameterized queries |
| XSS | `<script>`, `javascript:` | WAF XSS rules, output encoding |
| Path Traversal | `../`, `..%2f` | Input validation, WAF rules |
| Command Injection | `; ls`, `| cat` | Input validation, avoid shell exec |
| SSRF | Internal IPs, localhost | Allowlist external URLs |
| Credential Stuffing | High volume login attempts | Rate limiting, CAPTCHA |
| API Abuse | Excessive requests | Rate limiting, API keys |

### Suspicious Patterns to Monitor

```
# SQL Injection attempts
.*('|"|;|--|/\*|\*/|xp_|sp_|exec|execute|union|select|insert|update|delete|drop|alter|create).*

# XSS attempts
.*(<script|javascript:|on\w+\s*=|<img|<iframe).*

# Path traversal
.*(\.\.\/|\.\.\\|%2e%2e%2f|%252e%252e%252f).*

# Common scanners
.*(sqlmap|nikto|nmap|masscan|burp|acunetix).*
```

---

## Security Headers

### Recommended Headers

Configure these headers in your reverse proxy or application:

```nginx
# Nginx configuration
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;
```

### CORS Configuration

Production CORS should be restrictive:

```python
# FastAPI CORS configuration
allow_origins = ["https://yourdomain.com", "https://app.yourdomain.com"]
allow_credentials = True
allow_methods = ["GET", "POST", "PUT", "DELETE"]
allow_headers = ["Authorization", "Content-Type", "X-API-Key"]
```

---

## Database Security

### Connection Security

- Use SSL/TLS for all database connections
- Use connection pooling with short timeouts
- Implement query timeouts (30 seconds max)
- Use read replicas for analytics queries

### Access Control

- Principle of least privilege for database users
- Separate users for application, migrations, and analytics
- No direct database access from public internet
- Use VPC/private networking

### Data Protection

- Encrypt sensitive data at rest
- Hash passwords with bcrypt (cost factor 12+)
- Hash API keys with SHA256
- Mask PII in logs

---

## Monitoring and Alerting

### Security Events to Monitor

| Event | Severity | Alert Threshold |
|-------|----------|-----------------|
| Failed login attempts | Medium | >10/min from same IP |
| Invalid API key usage | Medium | >5/min |
| Rate limit exceeded | Low | >100/hour |
| SQL injection attempt | High | Any detection |
| Unusual geographic access | Medium | New country |
| Admin action | Info | All admin actions |

### Log Format

Security events should be logged in structured format:

```json
{
  "timestamp": "2026-01-23T12:00:00Z",
  "event_type": "auth.login.failed",
  "severity": "medium",
  "user_id": null,
  "ip_address": "192.168.1.1",
  "user_agent": "...",
  "details": {
    "reason": "invalid_password",
    "email": "user@example.com"
  }
}
```

### Alerting Rules

Configure alerts for:
- Spike in 4xx/5xx errors
- Unusual traffic patterns
- Failed authentication bursts
- WAF rule triggers
- Secrets validation failures

---

## Incident Response

### Response Procedures

#### 1. Suspected Credential Compromise
1. Immediately rotate affected secrets
2. Invalidate all sessions (if JWT key compromised)
3. Review access logs for unauthorized access
4. Notify affected users
5. Document incident

#### 2. API Key Abuse
1. Immediately deactivate the API key
2. Contact key owner
3. Review actions taken with the key
4. Issue new key after investigation

#### 3. Data Breach
1. Identify scope of breach
2. Contain the breach (revoke access, patch vulnerability)
3. Preserve evidence
4. Notify affected parties as required by law
5. Conduct post-mortem

### Emergency Contacts

Maintain a list of emergency contacts:
- Security team lead
- Infrastructure team
- Legal/compliance
- External security consultants (if applicable)

---

## Security Checklist

### Pre-Deployment

- [ ] All secrets rotated from development values
- [ ] Debug mode disabled
- [ ] HTTPS enforced
- [ ] CORS configured for production domains
- [ ] WAF rules active
- [ ] Rate limiting enabled
- [ ] Security headers configured
- [ ] Logging and monitoring active
- [ ] Backup and recovery tested

### Regular Maintenance

- [ ] Weekly: Review security logs
- [ ] Monthly: Update dependencies
- [ ] Quarterly: Rotate JWT secret
- [ ] Semi-annually: Rotate database passwords
- [ ] Annually: Security audit, rotate API keys

---

## Reporting Security Issues

If you discover a security vulnerability, please report it responsibly:

1. **Do NOT** create a public GitHub issue
2. Email: security@yourdomain.com
3. Include: Description, reproduction steps, impact assessment
4. We aim to respond within 48 hours

---

*Last Updated: January 23, 2026*
