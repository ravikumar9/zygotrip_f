# 9) Security Design

## Identity and access

- OAuth2/JWT at gateway boundary
- Service-to-service mTLS with short-lived certs
- RBAC by domain and least privilege policies

## Data protection

- TLS 1.2+ in transit
- AES-256 at rest for PostgreSQL, Redis persistence, Kafka disks
- PII tokenization for phone, email where possible
- Key rotation through centralized secrets manager

## Payment security

- No raw card data storage in ZygoTrip services
- PCI scope minimized to gateway integrations
- Webhook signature verification mandatory
- Idempotent payment and refund handling

## API hardening

- WAF + rate limiting + bot mitigation at edge
- Request schema validation and strict allow-list headers
- Replay protection with nonce/idempotency key
- Fraud scoring for IP concentration, account fan-out, failure velocity

## Audit and compliance

- Immutable audit events for booking, payment, refund actions
- Security event stream to SIEM
- Quarterly access reviews and key rotation audit

## Secure SDLC controls

- SAST and dependency scan on every commit
- Container image scan before push
- Runtime policy checks in cluster admission
