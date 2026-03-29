# VRT SPACE — Billing & Subscription System Skill

## 🧠 PURPOSE

The billing system controls:

* Access to features
* Usage limits
* Monetization

It is the enforcement layer of the SaaS.

---

## 🎯 OBJECTIVES

* Assign plans to users
* Restrict feature access
* Track usage
* Handle payments securely
* Support upgrades/downgrades

---

## 🏗️ ARCHITECTURE PRINCIPLES

1. Billing logic MUST be separate from business logic
2. All feature access MUST go through plan validation
3. Usage MUST be tracked per user per billing cycle
4. Payment verification MUST rely on webhooks (NOT frontend confirmation)

---

## 🧩 CORE MODELS

### Plan

Defines available plans

Fields:

* name (Free, Pro, Premium)
* audit_limit (integer)
* features (JSON)
* price
* billing_cycle

---

### Subscription

Fields:

* user
* plan
* status (active, canceled, expired)
* start_date
* end_date
* payment_reference

---

### Usage

Tracks usage per billing cycle

Fields:

* user
* audits_used
* seo_checks_used
* aeo_checks_used
* period_start
* period_end

---

## ⚙️ FEATURE GATING SYSTEM

Every protected feature MUST check:

```python
def can_access_feature(user, feature_name):
    plan = get_user_plan(user)
    return plan.features.get(feature_name, False)
```

---

## 📊 USAGE ENFORCEMENT

Before running any audit:

```python
def can_run_audit(user):
    usage = get_current_usage(user)
    plan = get_user_plan(user)
    
    return usage.audits_used < plan.audit_limit
```

---

## 💳 PAYMENT INTEGRATION RULES

* Use Stripe or Paystack
* NEVER trust frontend payment success
* ALWAYS verify via webhook

### Webhook Flow:

1. Payment event received
2. Verify signature
3. Update subscription
4. Activate plan

---

## 🔄 PLAN CHANGE LOGIC

### Upgrade:

* Immediate access
* Reset limits if needed

### Downgrade:

* Apply after billing cycle ends

---

## ⚠️ EDGE CASES

* Expired subscription → downgrade to Free
* Payment failure → restrict premium features
* Abuse → throttle usage

---

## 📤 OUTPUT EXPECTATIONS

* Accurate plan enforcement
* Real-time usage tracking
* Secure payment handling

---

## ❌ DO NOT

* Hardcode plan logic in views
* Allow access without validation
* Skip webhook verification

---

## ✅ SUCCESS CONDITION

The system reliably:

* Controls access
* Tracks usage
* Generates revenue
