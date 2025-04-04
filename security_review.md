# Perera Construction Lead Scraper - Security Review

## Table of Contents
- [Executive Summary](#executive-summary)
- [Scope](#scope)
- [Methodology](#methodology)
- [Findings Overview](#findings-overview)
- [Detailed Analysis](#detailed-analysis)
  - [1. Credential Management](#1-credential-management)
  - [2. Data Security](#2-data-security)
  - [3. Network Security](#3-network-security)
  - [4. Code Security](#4-code-security)
  - [5. Operational Security](#5-operational-security)
- [Vulnerability Assessment](#vulnerability-assessment)
- [Remediation Plan](#remediation-plan)
- [Security Configuration](#security-configuration)
- [Testing Plan](#testing-plan)
- [Conclusion](#conclusion)
- [Appendix A: Security Best Practices](#appendix-a-security-best-practices)
- [Appendix B: Security Test Cases](#appendix-b-security-test-cases)

## Executive Summary

This document presents a comprehensive security review of the Perera Construction Lead Scraper system. The review examines all aspects of the system's security, including credential management, data security, network security, code security, and operational security.

The assessment identified several security concerns of varying severity, with the most critical issues related to credential management and input validation. These findings have been outlined with recommended remediation strategies to enhance the system's overall security posture.

Key recommendations include implementing proper credential encryption, enhancing API authentication mechanisms, implementing secure data handling practices, and establishing robust logging and monitoring procedures.

## Scope

This security review covers the following components of the Perera Construction Lead Scraper:

1. Core application code
2. API interfaces
3. Data storage and handling
4. External integrations (HubSpot CRM)
5. Authentication mechanisms
6. Operational procedures
7. Configuration management
8. Deployment environments (standard and Docker)

## Methodology

The security review was conducted using the following approach:

1. **Code Review**: Manual examination of the codebase to identify security vulnerabilities
2. **Dependency Analysis**: Automated scanning of dependencies for known vulnerabilities 
3. **Configuration Review**: Assessment of configuration patterns and security implications
4. **Threat Modeling**: Identification of potential attack vectors and mitigations
5. **Security Testing**: Testing of specific security controls and mechanisms
6. **Best Practice Analysis**: Comparison against industry security best practices

## Findings Overview

The security review identified multiple issues across different security domains. Below is a summary of findings by severity:

| Severity | Count | Description |
|----------|-------|-------------|
| Critical | 2 | Issues requiring immediate attention that could lead to significant security breaches |
| High | 5 | Important security issues that should be addressed in the short term |
| Medium | 8 | Security concerns that should be addressed to improve the overall security posture |
| Low | 6 | Minor security considerations that represent best practices |

## Detailed Analysis

### 1. Credential Management

#### 1.1 API Key Storage (Severity: Critical)

**Finding**: API keys are stored in plain text in the configuration file (`config.yml`).

**Impact**: If the configuration file is compromised, API keys providing access to the system and third-party services (like HubSpot) would be exposed.

**Recommendation**: 
- Encrypt sensitive configuration values using environment-specific encryption keys
- Use environment variables for API keys in production environments
- Implement a secure secrets management solution

**Code Location**:
```python
# src/perera_lead_scraper/config.py
def load_config(config_path=None):
    # ...
    # API keys loaded directly from YAML without encryption
    config = yaml.safe_load(f)
    # ...
```

#### 1.2 Credential Rotation (Severity: Medium)

**Finding**: The system lacks mechanisms for automatic credential rotation and expiration.

**Impact**: Long-lived credentials increase the risk of unauthorized access if they are compromised.

**Recommendation**: 
- Implement credential rotation policies and mechanisms
- Add expiration dates to API keys
- Create tools to facilitate easy credential rotation

#### 1.3 Authentication Mechanism (Severity: High)

**Finding**: API authentication relies solely on API key in header without additional verification methods.

**Impact**: If an API key is intercepted, an attacker gains full access to the API.

**Recommendation**: 
- Implement multi-factor authentication for critical operations
- Add rate limiting per API key
- Consider implementing key signing or token-based authentication with short-lived tokens

**Code Location**:
```python
# src/perera_lead_scraper/api/api.py
async def get_api_key(api_key_header: str = Depends(api_key_header)):
    if api_key_header is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key header is missing",
        )
    
    valid_api_keys = getattr(config, "api_keys", [])
    
    if api_key_header not in valid_api_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )
    
    return api_key_header
```

#### 1.4 Third-Party Credentials (Severity: High)

**Finding**: Credentials for third-party services like HubSpot are stored in the same configuration file without additional protection.

**Impact**: A configuration file leak would expose multiple credential sets, increasing the attack surface.

**Recommendation**: 
- Use a dedicated secure storage for third-party credentials
- Consider using a secrets management service (like AWS Secrets Manager, Vault)
- Implement separate access controls for third-party credential access

### 2. Data Security

#### 2.1 Data Encryption (Severity: Medium)

**Finding**: The system stores lead data in SQLite database without encryption.

**Impact**: If the database file is accessed by an unauthorized user, sensitive lead information would be exposed.

**Recommendation**: 
- Implement database encryption at rest
- Ensure sensitive fields are encrypted
- Use separate encryption keys for different data types

**Code Location**:
```python
# src/perera_lead_scraper/storage.py
def __init__(self, db_path=None):
    """Initialize the storage with a database path."""
    self.db_path = db_path or os.path.join('data', 'leads.db')
    self.conn = sqlite3.connect(self.db_path)
    # Database is created without encryption
```

#### 2.2 PII Handling (Severity: High)

**Finding**: The system does not specifically identify or handle Personally Identifiable Information (PII) with additional protections.

**Impact**: If PII is present in lead data, it may not receive appropriate protection, potentially violating privacy regulations.

**Recommendation**: 
- Identify and classify fields containing PII
- Implement field-level encryption for PII
- Add data masking for non-essential display of PII
- Implement data access audit logging

#### 2.3 Data Retention (Severity: Medium)

**Finding**: No explicit data retention policies are implemented in the system.

**Impact**: Data may be kept longer than necessary, increasing potential exposure and regulatory compliance issues.

**Recommendation**: 
- Implement configurable data retention policies
- Add automated data purging/archiving mechanisms
- Ensure purged data is securely deleted

#### 2.4 Export Security (Severity: Medium)

**Finding**: Exported lead files (CSV, Excel) are not encrypted or protected.

**Impact**: Exported files containing sensitive lead information could be accessed if the export location is compromised.

**Recommendation**: 
- Encrypt exported files with recipient-specific keys
- Implement access controls on export directories
- Add automatic export expiration/deletion

**Code Location**:
```python
# src/perera_lead_scraper/export/csv_exporter.py
def export_to_csv(self, leads, output_path):
    """Export leads to CSV file."""
    # CSV file is created without encryption
    with open(output_path, 'w', newline='') as csvfile:
        # ...
```

### 3. Network Security

#### 3.1 API Endpoint Security (Severity: Medium)

**Finding**: Some API endpoints lack proper input validation and sanitization.

**Impact**: Malformed input could potentially lead to unexpected behavior or security issues.

**Recommendation**: 
- Implement thorough input validation for all API endpoints
- Use Pydantic models consistently for request validation
- Add content type restrictions and payload size limits

#### 3.2 Rate Limiting (Severity: Low)

**Finding**: Rate limiting is implemented but uses in-memory storage, which doesn't persist across restarts and doesn't scale in multi-instance deployments.

**Impact**: System may be vulnerable to denial of service attacks or brute force authentication attempts.

**Recommendation**: 
- Use a distributed rate limiting solution (Redis, database)
- Implement more granular rate limiting policies
- Add progressive backoff for repeated violations

**Code Location**:
```python
# src/perera_lead_scraper/api/api.py
# Rate limiting configuration
RATE_LIMIT_WINDOW = 60  # 1 minute window
MAX_REQUESTS_PER_WINDOW = 100
rate_limit_storage: Dict[str, Dict[str, Union[int, float]]] = {}  # In-memory storage
```

#### 3.3 HTTPS Configuration (Severity: Medium)

**Finding**: HTTPS is configurable but not enforced, and secure headers are not consistently applied.

**Impact**: Communications could potentially occur over insecure channels, risking data interception.

**Recommendation**: 
- Enforce HTTPS for all communications
- Implement HTTP Strict Transport Security (HSTS)
- Add secure headers (Content-Security-Policy, X-Content-Type-Options)
- Use secure cookies with appropriate flags

#### 3.4 Cross-Origin Resource Sharing (CORS) (Severity: Low)

**Finding**: CORS configuration allows all origins by default.

**Impact**: The API may be accessible from unauthorized web applications, increasing the risk of cross-site attacks.

**Recommendation**: 
- Restrict CORS to specific allowed origins
- Implement strict CORS policies for production environments
- Separate CORS policies for development and production

**Code Location**:
```python
# src/perera_lead_scraper/api/api.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=getattr(config, "cors_allow_origins", ["*"]),  # Default allows all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 4. Code Security

#### 4.1 Dependency Vulnerabilities (Severity: High)

**Finding**: Several project dependencies have known security vulnerabilities, including:
- `requests` older version with CVE-2023-32681
- `pyyaml` older version with CVE-2020-14343
- `sqlalchemy` older version with CVE-2022-32043

**Impact**: Known vulnerabilities in dependencies could potentially be exploited.

**Recommendation**: 
- Update all dependencies to secure versions
- Implement automated dependency scanning
- Establish procedures for addressing dependency vulnerabilities

#### 4.2 Input Validation (Severity: Critical)

**Finding**: Input validation for data from external sources is inconsistent, particularly for web scraping components.

**Impact**: Malicious input from scraped websites could potentially lead to code injection or other attacks.

**Recommendation**: 
- Implement consistent input validation for all external data
- Use secure parsing libraries
- Sanitize all input before processing
- Implement content type verification

**Code Location**:
```python
# Example from a source implementation
def extract_data(self, html_content):
    """Extract data from HTML content."""
    soup = BeautifulSoup(html_content, 'html.parser')
    # Direct extraction without validation
    title = soup.select_one(self.selectors.get('title', '.title')).text
    description = soup.select_one(self.selectors.get('description', '.description')).text
    # ...
```

#### 4.3 Error Handling (Severity: Medium)

**Finding**: Error messages sometimes include sensitive information that could aid attackers.

**Impact**: Detailed error information could provide insights for attackers to exploit system vulnerabilities.

**Recommendation**: 
- Implement sanitized error responses for external interfaces
- Log detailed errors internally but return sanitized messages externally
- Avoid including sensitive data in error messages

**Code Location**:
```python
# Example of overly detailed error messages
@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": str(exc)}  # Detailed exception message exposed
    )
```

#### 4.4 Code Injection Prevention (Severity: Low)

**Finding**: The system generally avoids dangerous patterns like dynamic code execution, but some areas use string formatting that could potentially be improved.

**Impact**: Low risk of code injection due to controlled inputs, but best practices would further reduce risk.

**Recommendation**: 
- Replace string formatting with safe alternatives
- Use parameterized queries consistently
- Avoid using `eval()` or similar functions

### 5. Operational Security

#### 5.1 Logging Sensitive Data (Severity: High)

**Finding**: The logging system occasionally logs sensitive information, including API keys and credentials.

**Impact**: Log files could contain sensitive data, leading to information disclosure if logs are accessed.

**Recommendation**: 
- Implement logging sanitization to remove sensitive data
- Define and enforce logging policies for different data types
- Create specific log levels for different types of information

**Code Location**:
```python
# Example of potentially sensitive logging
def authenticate(self, api_key):
    """Authenticate with the API key."""
    logger.debug(f"Authenticating with API key: {api_key}")  # Logs complete API key
    # ...
```

#### 5.2 Audit Logging (Severity: Medium)

**Finding**: The system lacks comprehensive audit logging for security-relevant actions.

**Impact**: Security incidents or unauthorized actions may be difficult to detect and investigate.

**Recommendation**: 
- Implement detailed audit logging for all sensitive operations
- Include relevant metadata in audit logs (who, what, when, where)
- Ensure audit logs are protected from tampering

#### 5.3 Incident Response (Severity: Low)

**Finding**: The system does not include specific incident response procedures or tooling.

**Impact**: Security incidents may not be handled efficiently or consistently.

**Recommendation**: 
- Develop incident response procedures
- Add tooling to assist with incident detection and response
- Implement security alerting for suspicious activities

#### 5.4 Secure Defaults (Severity: Low)

**Finding**: Some security features are optional and disabled by default.

**Impact**: Systems deployed with default settings may have suboptimal security.

**Recommendation**: 
- Make security features enabled by default
- Provide secure default configurations
- Require explicit opt-out for reducing security measures

## Vulnerability Assessment

The following table summarizes the identified vulnerabilities with severity ratings:

| ID | Vulnerability | Severity | CVSS Score | Description |
|----|--------------|----------|------------|-------------|
| SEC-001 | Plain text credential storage | Critical | 9.0 | API keys and other credentials stored unencrypted |
| SEC-002 | Insufficient input validation | Critical | 8.5 | Inconsistent validation of external data |
| SEC-003 | PII protection | High | 7.5 | Lack of specific protections for personally identifiable information |
| SEC-004 | Dependency vulnerabilities | High | 7.0 | Known vulnerabilities in third-party dependencies |
| SEC-005 | Sensitive data logging | High | 6.8 | Sensitive information potentially exposed in logs |
| SEC-006 | Authentication mechanism | High | 6.5 | Single-factor authentication relying only on API key |
| SEC-007 | Third-party credential management | High | 6.5 | Inadequate protection of third-party service credentials |
| SEC-008 | Unencrypted database | Medium | 5.5 | Database storage without encryption at rest |
| SEC-009 | Data retention | Medium | 5.0 | Lack of explicit data retention policies |
| SEC-010 | Export file security | Medium | 5.0 | Unprotected exported data files |
| SEC-011 | API input validation | Medium | 5.0 | Insufficient validation on some API endpoints |
| SEC-012 | HTTPS enforcement | Medium | 5.0 | HTTPS configurable but not enforced |
| SEC-013 | Error handling | Medium | 4.5 | Detailed error messages potentially exposing information |
| SEC-014 | Audit logging | Medium | 4.5 | Insufficient audit logging for security events |
| SEC-015 | Credential rotation | Medium | 4.0 | Lack of credential rotation mechanisms |
| SEC-016 | Rate limiting implementation | Low | 3.5 | In-memory rate limiting not suitable for all deployments |
| SEC-017 | CORS configuration | Low | 3.0 | Permissive default CORS policy |
| SEC-018 | String formatting | Low | 3.0 | Use of simple string formatting in some areas |
| SEC-019 | Incident response | Low | 2.5 | Lack of incident response procedures |
| SEC-020 | Secure defaults | Low | 2.5 | Some security features not enabled by default |
| SEC-021 | Credential expiration | Low | 2.0 | No expiration mechanism for authentication credentials |

## Remediation Plan

### Immediate Actions (Critical and High Severity)

1. **Implement credential encryption (SEC-001)**
   - Add encryption for sensitive configuration values
   - Move credentials to environment variables
   - Update documentation to reflect secure credential practices

2. **Enhance input validation (SEC-002)**
   - Implement consistent validation for all external inputs
   - Add data sanitization for web scraping content
   - Create helper functions for common validation tasks

3. **Improve PII handling (SEC-003)**
   - Identify and classify PII fields
   - Implement field-level encryption for PII
   - Add access controls for PII data

4. **Update vulnerable dependencies (SEC-004)**
   - Upgrade all dependencies to secure versions
   - Implement automated dependency scanning
   - Document dependency management procedures

5. **Fix sensitive data logging (SEC-005)**
   - Implement log sanitization
   - Create logging guidelines
   - Add log masking for sensitive values

6. **Enhance authentication (SEC-006)**
   - Implement token-based authentication
   - Add support for multi-factor authentication
   - Create more granular access control

7. **Secure third-party credentials (SEC-007)**
   - Move third-party credentials to a secure store
   - Implement separate access controls
   - Add credential rotation procedures

### Short-term Actions (Medium Severity)

1. **Implement database encryption (SEC-008)**
   - Add transparent database encryption
   - Secure database credentials
   - Document database security measures

2. **Add data retention policies (SEC-009)**
   - Implement configurable retention policies
   - Add data archiving and purging
   - Create retention documentation

3. **Secure exported files (SEC-010)**
   - Implement export file encryption
   - Add access controls for exports
   - Create export management procedures

4. **Enhance API validation (SEC-011)**
   - Review and improve all API endpoint validation
   - Implement consistent validation patterns
   - Add payload size limits

5. **Enforce HTTPS (SEC-012)**
   - Make HTTPS mandatory
   - Implement security headers
   - Add HTTPS redirect

6. **Improve error handling (SEC-013)**
   - Sanitize error messages
   - Implement error logging
   - Create error handling guidelines

7. **Enhance audit logging (SEC-014)**
   - Implement comprehensive audit logging
   - Secure audit logs
   - Add audit log review procedures

8. **Add credential rotation (SEC-015)**
   - Implement credential rotation mechanisms
   - Add credential expiration
   - Create rotation documentation

### Long-term Actions (Low Severity)

1. **Improve rate limiting (SEC-016)**
   - Implement distributed rate limiting
   - Add more granular policies
   - Document rate limiting approach

2. **Secure CORS configuration (SEC-017)**
   - Restrict CORS to specific origins
   - Create environment-specific CORS policies
   - Document CORS configuration

3. **Review and fix string formatting (SEC-018)**
   - Audit code for string formatting issues
   - Implement safe alternatives
   - Create secure coding guidelines

4. **Develop incident response (SEC-019)**
   - Create incident response procedures
   - Implement detection mechanisms
   - Document response process

5. **Implement secure defaults (SEC-020)**
   - Review and update default configurations
   - Make security features enabled by default
   - Document security defaults

6. **Add credential expiration (SEC-021)**
   - Implement credential expiration
   - Add renewal processes
   - Document credential lifecycle

## Security Configuration

### Recommended Security Configuration

The following configuration settings are recommended for production deployments:

#### `config.yml` Security Settings

```yaml
security:
  # API Security
  api:
    require_https: true
    api_key_auth:
      enabled: true
      key_expiration_days: 90
      max_keys_per_user: 3
    rate_limiting:
      enabled: true
      storage: "redis"  # Options: memory, redis, database
      max_requests_per_minute: 60
      max_requests_per_hour: 1000
    cors:
      allowed_origins:
        - "https://app.example.com"
        - "https://admin.example.com"
      allow_credentials: true
      allowed_methods:
        - "GET"
        - "POST"
        - "PUT"
        - "DELETE"
      allowed_headers:
        - "X-API-Key"
        - "Content-Type"
    security_headers:
      hsts_enabled: true
      hsts_max_age: 31536000  # 1 year
      content_security_policy: "default-src 'self'"
      x_content_type_options: "nosniff"
      x_frame_options: "DENY"
  
  # Data Security
  data:
    encryption:
      enabled: true
      algorithm: "AES-256-GCM"
      key_rotation_days: 90
    database:
      encrypt_at_rest: true
    pii_fields:
      - "email"
      - "phone"
      - "address"
    retention:
      enabled: true
      retention_days: 365
      archive_enabled: true
      archive_path: "/secure/archives"
    export:
      encrypt_exports: true
      export_expiration_days: 7
  
  # Operational Security
  operations:
    logging:
      sanitize_sensitive_data: true
      audit_logging: true
      log_retention_days: 90
    monitoring:
      security_monitoring: true
      alert_on_suspicious_activity: true
    credentials:
      rotation_reminder_days: 60
      store_encrypted: true
```

### Environment Variables for Sensitive Data

The following environment variables should be used for sensitive configuration instead of including them in config files:

```
# API Security
LEAD_SCRAPER_API_KEY=your_secure_api_key
LEAD_SCRAPER_ENCRYPTION_KEY=your_encryption_key

# Database
LEAD_SCRAPER_DB_PASSWORD=your_database_password

# Third-party Integrations
LEAD_SCRAPER_HUBSPOT_API_KEY=your_hubspot_api_key
LEAD_SCRAPER_SMTP_PASSWORD=your_smtp_password

# Other Sensitive Data
LEAD_SCRAPER_WEBHOOK_SECRET=your_webhook_secret
```

### Docker Security Configuration

For Docker deployments, the following security settings are recommended:

```yaml
# docker-compose.yml
version: '3.8'

services:
  scraper:
    # ...
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
    read_only: true
    tmpfs:
      - /tmp
    volumes:
      - type: volume
        source: lead-data
        target: /app/data
        read_only: false
      - type: volume
        source: lead-exports
        target: /app/exports
        read_only: false
      - type: volume
        source: lead-logs
        target: /app/logs
        read_only: false
    # ...
```

## Testing Plan

### Security-focused Test Cases

1. **Credential Management**
   - Test API key validation
   - Test credential encryption
   - Test credential rotation
   - Test expired credential handling

2. **Data Security**
   - Test PII field encryption
   - Test data retention implementation
   - Test export file security
   - Test database encryption

3. **Network Security**
   - Test API endpoint validation
   - Test rate limiting functionality
   - Test HTTPS enforcement
   - Test CORS policy enforcement

4. **Code Security**
   - Test input validation mechanisms
   - Test for dependency vulnerabilities
   - Test error handling
   - Test for injection vulnerabilities

5. **Operational Security**
   - Test logging sanitization
   - Test audit logging
   - Test security monitoring
   - Test incident response procedures

A detailed list of security test cases is provided in Appendix B.

## Conclusion

The Perera Construction Lead Scraper system has a solid foundation but requires several security enhancements to meet industry best practices. The most critical areas requiring attention are credential management and input validation from external sources.

By implementing the recommended remediation actions, particularly the critical and high-severity items, the system's security posture will be significantly improved. The proposed security configuration provides a template for secure production deployments.

Ongoing security maintenance should include regular dependency updates, security testing, and continued refinement of security practices based on evolving threats and best practices.

## Appendix A: Security Best Practices

### Credential Management Best Practices

1. **Never store credentials in code or configuration files**
   - Use environment variables or a dedicated secrets management service
   - Implement appropriate encryption for any stored credentials

2. **Implement credential rotation**
   - Set expiration dates for all credentials
   - Provide mechanisms to easily rotate credentials
   - Alert before credential expiration

3. **Minimize credential access**
   - Limit access to credentials on a need-to-know basis
   - Log all credential access
   - Use the principle of least privilege

### Data Security Best Practices

1. **Classify data by sensitivity**
   - Identify and label sensitive data
   - Apply appropriate protections based on classification
   - Implement different controls for different data types

2. **Encrypt sensitive data**
   - Use strong encryption for data at rest and in transit
   - Implement proper key management
   - Regularly review encryption implementations

3. **Implement data minimization**
   - Only collect necessary data
   - Apply retention policies to limit data lifetime
   - Securely delete data when no longer needed

### Network Security Best Practices

1. **Secure all API endpoints**
   - Implement strong authentication
   - Validate all inputs
   - Apply rate limiting and other abuse prevention measures

2. **Use HTTPS for all connections**
   - Configure proper TLS settings
   - Implement security headers
   - Regularly review SSL/TLS configuration

3. **Implement defense in depth**
   - Use multiple layers of security controls
   - Do not rely on a single security measure
   - Assume perimeter security will be breached

### Code Security Best Practices

1. **Validate all inputs**
   - Never trust user or external input
   - Implement strict validation
   - Sanitize data before processing

2. **Keep dependencies updated**
   - Regularly scan for vulnerabilities
   - Update dependencies promptly
   - Consider security implications of new dependencies

3. **Follow secure coding guidelines**
   - Use parameterized queries for database access
   - Avoid dangerous functions and patterns
   - Apply the principle of least privilege in code

### Operational Security Best Practices

1. **Implement comprehensive logging**
   - Log security-relevant events
   - Protect logs from tampering
   - Regularly review logs

2. **Prepare for incidents**
   - Develop incident response procedures
   - Train team members on security response
   - Conduct regular security drills

3. **Monitor and alert**
   - Implement security monitoring
   - Create alerts for suspicious activities
   - Regularly review and tune monitoring

## Appendix B: Security Test Cases

### API Security Test Cases

1. **Test API key validation**
   - Submit request with no API key
   - Submit request with invalid API key
   - Submit request with expired API key
   - Submit request with valid API key

2. **Test rate limiting**
   - Submit requests at rate exceeding limits
   - Verify throttling behavior
   - Test rate limit bypass attempts

3. **Test input validation**
   - Submit malformed JSON
   - Submit oversized payloads
   - Test with SQL injection attempts
   - Test with XSS payloads

### Data Security Test Cases

1. **Test PII handling**
   - Verify PII fields are encrypted in database
   - Check PII access controls
   - Verify PII is handled securely in exports

2. **Test data retention**
   - Verify old data is archived/purged according to policy
   - Test retention policy bypass attempts
   - Verify secure deletion of expired data

3. **Test export security**
   - Verify export file encryption
   - Test unauthorized export access attempts
   - Verify export expiration functionality

### Authentication Test Cases

1. **Test authentication mechanisms**
   - Test authentication bypass attempts
   - Verify session handling security
   - Test credential rotation

2. **Test access controls**
   - Verify appropriate authorization checks
   - Test privilege escalation attempts
   - Verify separation of duties

### Operational Security Test Cases

1. **Test logging**
   - Verify sensitive data is not logged
   - Check log integrity
   - Verify audit logging functionality

2. **Test error handling**
   - Verify errors don't expose sensitive information
   - Test error handling for various scenarios
   - Check error logging

3. **Test security monitoring**
   - Verify alerts for suspicious activities
   - Test incident response procedures
   - Check monitoring coverage