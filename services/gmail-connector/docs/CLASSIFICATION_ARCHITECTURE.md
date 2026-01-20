# 9-Layer Hybrid Email Classification Architecture

## Overview

This document explains the architecture and design decisions of the 9-layer hybrid email classification engine.

## Pipeline Flow

```
Raw Email
 ↓
[1] Hard Ignore Filter → IGNORE (if matched, STOP)
 ↓
[2] Thread Context Analyzer → Fetch full thread, analyze history
 ↓
[3] Sender Intelligence → Analyze sender domain, historical behavior
 ↓
[4] Structural Parsing → Extract calendar, dates, CTAs, action verbs
 ↓
[5] Rule-Based Engine → Match explicit rules (REJECTED, INTERVIEW, OFFER, ACTIVE)
 ↓
[6] Statistical Confidence Scoring → Weighted score from all layers
 ↓
[7] Local LLM (if confidence < threshold) → Semantic classification
 ↓
[8] Deterministic Resolver → Resolve conflicts with explicit priority
 ↓
[9] Trace Logger + Explanation → Generate human-readable explanation
 ↓
Final Status
```

## Layer Details

### Layer 1: Hard Ignore Filter

**WHY**: Eliminate noise before any processing. Zero false positives.

**WHAT IT DOES**:
- Filters job board spam (LinkedIn, Indeed, Glassdoor)
- Filters promotional domains (noreply, marketing, offers)
- Detects unsubscribe patterns
- Filters non-job "approved" emails (WiFi, shopping, etc.)

**SHORT-CIRCUIT**: If matched → status = IGNORE → STOP PIPELINE

### Layer 2: Thread Context Analyzer

**WHY**: Single emails are misleading. Full thread context is critical.

**WHAT IT DOES**:
- Fetches full thread via Gmail API
- Sorts messages chronologically
- Analyzes thread for rejections, offers, interviews
- Calculates days since last message

**RULES**:
- If earlier email = REJECTED, future emails cannot be ACTIVE
- If interview happened, later "thanks" ≠ ACTIVE
- Ghosting only applies if no recruiter response for N days

### Layer 3: Sender Intelligence Engine

**WHY**: Sender reputation helps classify ambiguous emails.

**WHAT IT DOES**:
- Analyzes sender domain type (COMPANY, ATS, HUMAN, NOISE)
- Checks historical sender behavior (has sent interviews/rejections before)
- Computes sender confidence score (0.0-1.0)

**DOMAIN TYPES**:
- COMPANY: company.com → high confidence (0.90)
- ATS: greenhouse.io, lever.co → medium confidence (0.85)
- HUMAN: gmail.com, yahoo.com → low confidence (0.60)
- NOISE: unknown domains → very low confidence (0.30)

### Layer 4: Structural Email Parsing

**WHY**: Structure (calendar, dates, CTAs) is more reliable than keywords.

**WHAT IT DOES**:
- Extracts calendar invites (.ics files, calendar links)
- Detects date/time mentions
- Identifies action verbs and CTA phrases
- Cleans HTML to plain text
- Normalizes text

**SIGNALS**:
- Calendar invite → strong INTERVIEW signal
- Date + time mentioned → strong INTERVIEW signal
- Action verbs → helps identify intent

### Layer 5: Rule-Based Engine

**WHY**: Explicit, auditable rules catch obvious cases without LLM.

**WHAT IT DOES**:
- Matches patterns in priority order: REJECTED → OFFER → INTERVIEW → ACTIVE
- Returns matched status with confidence
- Logs which rules triggered

**RULE VERSIONING**:
- Rules are versioned (currently v1.0)
- Updates can be tracked via version field
- Allows A/B testing of rule changes

### Layer 6: Statistical Confidence Scoring

**WHY**: Combine signals from all layers into single confidence score.

**WHAT IT DOES**:
- Computes weighted confidence:
  - Rule score: 40%
  - Sender score: 20%
  - Thread score: 20%
  - Structural score: 20%
- Boosts confidence if multiple signals agree
- Escalates to LLM if confidence < threshold (default 0.7)

**WHY THESE WEIGHTS**:
- Rules are most reliable (40%)
- Sender and thread provide context (20% each)
- Structural signals are supportive (20%)

### Layer 7: Local LLM Semantic Classifier

**WHY**: Handle ambiguous cases that rules can't catch.

**WHAT IT DOES**:
- Only called when confidence < threshold
- Prompt includes: subject, body, thread summary, company, role, structural signals
- Strict JSON output format
- Timeout and fallback handling

**WHY LOCAL LLM**:
- No cloud dependency (privacy, reliability)
- No API costs
- Full control over prompts
- Deterministic with low temperature (0.1)

### Layer 8: Deterministic Resolver

**WHY**: Resolve conflicts explicitly. No random choices.

**WHAT IT DOES**:
- Applies priority order:
  1. Hard Ignore (already handled)
  2. Thread history (REJECTED cannot revert)
  3. Explicit rejection/offer
  4. Interview
  5. Active
  6. Ghosted

**NO CONFLICTS**: Every email gets exactly one status.

### Layer 9: Trace Logger + Explanation

**WHY**: User must understand WHY something was classified.

**WHAT IT DOES**:
- Stores: signals_used, rules_triggered, llm_used, explanation
- Generates human-readable explanation
- Full audit trail for debugging

## Traceability Schema

Every classification stores:

```json
{
  "final_status": "INTERVIEW",
  "confidence": 0.94,
  "signals_used": ["calendar_invite", "sender_intelligence", "thread_context"],
  "rules_triggered": ["INTERVIEW_RULE_1.0"],
  "llm_used": false,
  "explanation": "Matched rules: INTERVIEW_RULE_schedule. Sender type: COMPANY. Thread contains interview",
  "version": "1.0"
}
```

## Performance

- **Batch Processing**: `classify_batch()` processes 1,000+ emails efficiently
- **LLM Batching**: Groups LLM calls to reduce API overhead
- **Short-Circuiting**: Hard ignore stops pipeline early
- **Caching**: Thread context cached per thread

## Deterministic Behavior

- Same email → same classification
- Rules are versioned and logged
- LLM uses low temperature (0.1) for consistency
- No random choices in resolver

## Re-Classification

- Full pipeline re-run on demand
- Audit log tracks all changes
- Version tracking for rule updates
