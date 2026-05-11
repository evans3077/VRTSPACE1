"""Affiliate program test placeholder.

Coverage to add next:
  - commission math at 25% and 15% with integer/odd cent rounding
  - same-domain self-referral fraud block
  - same-IP fraud flag
  - cookie set/read flow through /r/<slug>/
  - idempotency of record_commission_for_payment on duplicate stripe_event_id
  - payout assembly + Stripe transfer error handling
"""
