# Operations Guide

## Overview

Day-to-day operational procedures for running Raghvi in production.

---

## Monitoring & Alerting

### Key Metrics to Monitor

| Category | Metrics | Alert Thresholds |
|----------|---------|------------------|
| **API Health** | Request rate, latency (p50/p95/p99), error rate (5xx) | Error rate > 1%, p99 > 5s |
| **AI Providers** | Chain attempts per request, provider success/fail rates | Fallback rate > 30%, all providers failing |
| **Voice** | Synthesis latency, provider failover rate, S3 upload errors | Latency > 10s, S3 errors > 5/min |
| **Database** | Connections, query latency, replication lag, deadlocks | Connections > 80% pool, lag > 30s |
| **Redis** | Memory usage, hit rate, evictions | Memory > 85%, hit rate < 90% |
| **Stripe** | Webhook success rate, subscription events | Webhook failures > 0 |
| **Business** | Active users, messages/day, voice synth/day, subscription conversions | N/A (trend monitoring) |

### Dashboards

- **Grafana**: Infrastructure + Application dashboards
- **Sentry**: Error tracking, performance monitoring
- **Stripe Dashboard**: Revenue, subscriptions, failed payments

### Alert Channels

| Severity | Channel | Response Time |
|----------|---------|---------------|
| Critical (P0) | PagerDuty → SMS + Call | 5 min |
| High (P1) | Slack #alerts + Email | 15 min |
| Medium (P2) | Slack #alerts | 1 hour |
| Low (P3) | Daily digest | 24 hours |

---

## Incident Response

### Severity Definitions

| Level | Definition | Examples |
|-------|------------|----------|
| **SEV-0** | Complete outage, data loss | DB down, all AI providers down, data corruption |
| **SEV-1** | Major feature broken | Chat not working, voice synthesis failing, auth broken |
| **SEV-2** | Degraded performance | High latency, intermittent errors, single provider down |
| **SEV-3** | Minor issue | Non-critical bug, cosmetic issue, docs error |

### Runbooks

#### SEV-0: Database Unavailable

1. Check cloud provider status page
2. Verify connection pooling not exhausted
3. Check for long-running queries: `SELECT * FROM pg_stat_activity WHERE state = 'active'`
4. Failover to replica (if configured)
5. Scale up DB instance if CPU/memory saturated
6. Post-incident: Review connection pool settings, add read replica

#### SEV-1: All AI Providers Failing

1. Check each provider status page
2. Verify API keys not rotated/expired
3. Check network connectivity (egress firewall)
4. Review recent deployments for config changes
5. Temporary: Increase timeouts, reduce `max_tokens`
6. Post-incident: Add more fallback providers, improve circuit breaker

#### SEV-1: Voice Synthesis Failing

1. Check voice provider status pages
2. Verify API keys and quotas
3. Check S3 accessibility for voice samples
4. Fallback: Disable voice features via feature flag
5. Post-incident: Add more voice providers, cache synthesized audio

#### SEV-2: High Latency on `/chat/send`

1. Check AI provider latency (each provider logs response time)
2. Check DB query performance (slow query log)
3. Check memory retrieval performance (TF-IDF on large memory sets)
4. Scale backend replicas (HPA)
5. Consider: Reduce memory candidate limit, add Redis caching

#### SEV-2: Stripe Webhook Failures

1. Check Stripe Dashboard → Webhooks for failed deliveries
2. Verify webhook secret matches
3. Check backend logs for unhandled event types
4. Replay failed events from Stripe Dashboard
5. Post-incident: Add idempotency keys, improve error handling

---

## Routine Operations

### Daily

- [ ] Review error rates and latency dashboards
- [ ] Check failed Stripe webhooks (replay if needed)
- [ ] Verify backup completed successfully
- [ ] Check disk space on all nodes
- [ ] Review Sentry for new error patterns

### Weekly

- [ ] Rotate API keys (quarterly for AI providers, monthly for Stripe)
- [ ] Review slow query log, add indexes if needed
- [ ] Update dependencies (security patches)
- [ ] Review subscription metrics (churn, conversion)
- [ ] Clean up old voice samples (orphaned S3 objects)

### Monthly

- [ ] Database vacuum/analyze (autovacuum should handle)
- [ ] Review and update dependency versions
- [ ] Capacity planning: project 3-month growth
- [ ] Security scan: container images, dependencies
- [ ] Disaster recovery drill (restore from backup)

---

## Database Operations

### Backup

```bash
# Automated via managed PG (daily snapshots, 30-day retention)
# Manual backup before major changes:
pg_dump -h <host> -U <user> -d raghvi > backup_$(date +%Y%m%d).sql
```

### Restore

```bash
# Point-in-time recovery (managed PG)
# Or manual:
psql -h <host> -U <user> -d raghvi < backup_20260820.sql
```

### Common Queries

```sql
-- Active connections
SELECT count(*) FROM pg_stat_activity WHERE datname = 'raghvi';

-- Long-running queries
SELECT pid, now() - pg_stat_activity.query_start AS duration, query
FROM pg_stat_activity
WHERE (now() - pg_stat_activity.query_start) > interval '30 seconds';

-- Table sizes
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables WHERE schemaname = 'public' ORDER BY size DESC;

-- Index usage
SELECT * FROM pg_stat_user_indexes WHERE relname IN ('messages', 'memories', 'tasks');
```

### Migration Safety

```bash
# Before deploying migration:
# 1. Test on staging with production data copy
# 2. Verify backward compatibility (old code works with new schema)
# 3. Have rollback plan: alembic downgrade -1

# During deployment:
# 1. Run migration via init container or pre-deploy step
# 2. Verify migration completed: alembic current
# 3. Deploy application
```

---

## Scaling Operations

### Horizontal Scaling (Backend)

```bash
# Kubernetes HPA handles automatically based on CPU/memory
# Manual scale:
kubectl scale deployment raghvi-backend --replicas=10 -n raghvi

# Check HPA status:
kubectl get hpa raghvi-backend-hpa -n raghvi
```

### Vertical Scaling (Database)

```bash
# AWS RDS: Modify instance class (requires reboot)
# Or: Enable storage autoscaling
# Read replicas for read-heavy workloads (chat history, memory retrieval)
```

### Redis Scaling

```bash
# Cluster mode for > 50GB data
# Or: Increase instance size
# Monitor: used_memory, connected_clients, keyspace_hits/misses
```

---

## Security Operations

### Secret Rotation

| Secret | Frequency | Process |
|--------|-----------|---------|
| JWT_SECRET_KEY | Quarterly | Deploy new key, old tokens expire in 14 days (refresh) |
| AI Provider Keys | Quarterly | Update in secret manager, restart pods |
| Stripe Keys | Monthly | Update in Stripe Dashboard + secret manager |
| Database Password | Quarterly | Update in secret manager, rotate via managed PG |
| S3 Access Keys | Quarterly | Create new, update secret manager, delete old |

### Certificate Management

- **TLS**: Managed by cert-manager (Let's Encrypt), auto-renews 30 days before expiry
- **Monitor**: `kubectl get certificates -A` for expiry dates

### Access Control

- **Production DB**: No direct access. Use bastion/SSM session manager
- **Kubernetes**: RBAC with least privilege
- **GitHub**: Branch protection, required reviews, signed commits

---

## Log Management

### Log Structure

```json
{
  "timestamp": "2026-08-20T10:30:00.123Z",
  "level": "INFO",
  "logger": "app.services.chat",
  "message": "Chat response generated",
  "user_id": "uuid",
  "provider": "gemini",
  "tokens": 156,
  "latency_ms": 1234
}
```

### Log Retention

| Log Type | Retention | Storage |
|----------|-----------|---------|
| Application | 30 days | CloudWatch / Loki |
| Audit (auth, payments) | 7 years | S3 / CloudWatch |
| Access (nginx) | 90 days | S3 |
| Debug | 7 days | Local / CloudWatch |

### Querying Logs

```bash
# CloudWatch Insights
fields @timestamp, @message, user_id, provider, latency_ms
| filter @logStream like /backend/
| filter provider = "gemini"
| stats avg(latency_ms) by bin(5m)

# Sentry
# Search: "chat" "timeout" "user_id:xxx"
```

---

## Feature Flags

### Current Flags

| Flag | Default | Purpose |
|------|---------|---------|
| `voice_enabled` | true | Disable voice synthesis globally |
| `voice_cloning_enabled` | false | Gate cloning until provider ready |
| `proactive_briefing_enabled` | false | M5 feature |
| `android_actions_enabled` | false | M6 feature |
| `memory_embeddings_enabled` | false | Future pgvector retrieval |

### Managing Flags

```bash
# Via environment variable or config service
# Deployment: Update ConfigMap, rollout restart
kubectl set env deployment/raghvi-backend VOICE_CLONING_ENABLED=true -n raghvi
```

---

## Cost Optimization

### Monthly Cost Review

| Component | Optimization |
|-----------|--------------|
| AI Providers | Use cheaper fallbacks (Groq, Gemini) as primary; cache responses |
| Voice Providers | Cache synthesized audio in Redis (30 min TTL) |
| Database | Right-size instance, enable read replicas for reads |
| S3 | Lifecycle policy: move old voice samples to Glacier |
| Kubernetes | Spot instances for non-critical workloads |

### AI Cost Controls (per ADR-013)

- Daily message limits per subscription tier
- Token budget per conversation turn
- Prefer cheaper providers in chain order
- Monitor: `tokens_used` in chat responses

---

## Disaster Recovery

### RPO/RTO Targets

| Component | RPO | RTO |
|-----------|-----|-----|
| PostgreSQL | 5 min (PITR) | 30 min |
| Redis | 1 hour (AOF) | 15 min |
| S3 | 0 (versioning) | 5 min |
| Application | N/A (stateless) | 5 min |

### Recovery Procedures

1. **Database**: Point-in-time restore to new instance, update DNS/connection string
2. **Redis**: Restore from AOF/RDB, or rebuild from DB (sessions, cache)
3. **S3**: Cross-region replication enabled, promote replica
4. **Kubernetes**: Re-deploy from Git (GitOps), secrets from secret manager

### Backup Validation

- Quarterly: Full restore to staging environment
- Verify: Data integrity, application functionality, performance

---

## Communication

### Status Page

- **Internal**: Slack #status-updates
- **External**: status.raghvi.example.com (if public)

### Incident Communication Template

```
**Incident**: [SEV-1] Chat unavailable
**Start**: 2026-08-20 14:32 UTC
**Impact**: Users cannot send messages (500 errors)
**Root Cause**: All AI providers returning rate limit errors
**Mitigation**: Increased timeouts, added Groq as primary
**Resolution**: 2026-08-20 14:45 UTC
**Action Items**: 
  - Add more fallback providers
  - Implement request queuing
  - Review provider quotas
```

---

## On-Call

### Rotation

- Primary: 1 week
- Secondary: 1 week (shadow)
- Handoff: Monday 10:00 UTC via Slack

### On-Call Runbook

1. Acknowledge alert within 5 min
2. Assess severity (runbook above)
3. Communicate in #incidents channel
4. Fix or escalate
5. Post-incident review within 48 hours

### Escalation Contacts

| Role | Contact |
|------|---------|
| Engineering Lead | @lead |
| Database Admin | @dba |
| Security | @security |
| Stripe Support | Dashboard → Support |

---

## Useful Commands

```bash
# Kubernetes
kubectl logs -n raghvi -l app=raghvi-backend --tail=100 -f
kubectl exec -it -n raghvi <pod> -- uv run python -c "import app; print('OK')"
kubectl port-forward -n raghvi svc/raghvi-backend 8000:80

# Database
kubectl exec -it -n raghvi postgresql-0 -- psql -U raghvi -d raghvi

# Redis
kubectl exec -it -n raghvi redis-0 -- redis-cli -a $REDIS_PASSWORD

# Stripe CLI (local testing)
stripe listen --forward-to localhost:8000/webhooks/stripe
stripe trigger checkout.session.completed
```