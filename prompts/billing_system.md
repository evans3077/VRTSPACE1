You are a senior Django SaaS architect with experience in billing systems and subscription-based platforms.

Build a complete billing and subscription system for a SaaS platform that provides SEO, AEO, and Web Optimization tools.

---

## 🎯 OBJECTIVE

Create a system that:

* Manages user subscriptions
* Restricts access based on plan
* Tracks usage
* Integrates payment processing

---

## 🧠 FEATURES

### 1. Subscription Plans

Create plans:

* Free

  * Limited audits (e.g., 1–3 per month)
  * No history
  * Limited recommendations

* Pro

  * More audits
  * Full recommendations
  * Audit history

* Premium

  * Unlimited audits
  * AI insights
  * Competitor tracking

---

### 2. Django Models

Create models:

* Plan
* Subscription
* Usage

Each plan should define:

* audit_limit
* features_enabled (JSONField)

---

### 3. Feature Gating System

Implement logic:

* Restrict access to:

  * SEO engine
  * AEO engine
  * Full reports
* Example:
  If user is Free → limit audit results

---

### 4. Usage Tracking

Track:

* number of audits per user
* tool usage (SEO, AEO, Web)

Reset monthly.

---

### 5. Payment Integration

Support:

* Stripe (global)
* Paystack (for African users)

Implement:

* subscription creation
* webhook handling
* payment verification

---

### 6. Upgrade / Downgrade Flow

Users should:

* upgrade plan easily
* retain data
* see benefits before upgrading

---

### 7. Middleware / Decorators

Create:

* decorators to restrict views based on plan
* middleware for usage limits

---

### 8. UI Integration

Show:

* current plan
* usage stats
* upgrade prompts

---

## ⚠️ RULES

* Never allow unlimited access without plan check
* Always validate payment via webhook
* Keep billing logic separate from business logic
* Make system extensible

---

## 🚀 OUTPUT

Provide:

* Django models
* plan logic
* usage tracking system
* payment integration structure
* middleware/decorators
* example views

---

Build this as a secure, scalable billing system.
