---
name: vrt-space-scoring
description: Scoring and explanation guidance for VRT SPACE AGENCY. Use when designing or refactoring audit scores, weighted subscores, recommendation ranking, trend tracking, or score explanations across performance, SEO, AEO, and lead qualification flows. Trigger for scoring-engine changes, audit summary logic, score normalization, and priority ranking.
---

# VRT Space Scoring

Use this skill when the task is about how VRT SPACE turns raw signals into scores, priorities, and explanations users can trust.

## Scoring Workflow

1. Read `../../../09_PERFORMANCE_ENGINE.md`, `../../../13_ANALYTICS_TRACKING.md`, and `../../../14_AI_VISIBILITY_SYSTEM.md` before changing scoring logic.
2. Read `../../../06_DATA_MODELS.md` when adding stored score breakdowns or historical trend models.
3. Use `../../../prompts/scoring_system.md`, `../../../prompts/live_intelligent_recommendation_systems.md`, and `../../../prompts/aeo_engine.md` for the intended product direction.
4. Keep raw measurements, normalized scores, and human explanations as separate layers.
5. Make weighting rules explicit and testable.

## Current Repo Reality

- Audit scoring already exists in `apps/tools/services.py`.
- Lead qualification scoring already exists in `apps/leads/services.py`.
- The current audit engine mixes heuristics, issue weights, and Lighthouse-derived scores in one service file.
- Use this skill when extracting that into a clearer, more transparent scoring system instead of bolting on more ad hoc rules.

## Hard Rules

- Normalize user-facing scores to a clear 0-100 scale.
- Keep subscores explainable and traceable to underlying signals.
- Do not mix raw metrics and final scores in the same contract without labels.
- Make weighting and threshold choices visible in code.
- When data is partial, degrade gracefully and explain the missing coverage.

## Product Rules

- Distinguish overall score, category scores, and recommendation priority.
- Pair each score with why it is high or low and what to do next.
- Track score history when trend behavior matters.
- Keep the explanation layer useful for both self-serve users and internal agency review.

## Delivery Checklist

- Confirm weights, thresholds, and fallbacks are explicit.
- Confirm explanations match the final numbers.
- Confirm storage supports historical comparison when needed.
- Confirm new score logic does not break current audit summaries and templates.
- Confirm tests cover edge cases, partial data, and ranking order.

## References

- `../../../06_DATA_MODELS.md`: model and JSON field guidance
- `../../../09_PERFORMANCE_ENGINE.md`: performance measurement expectations
- `../../../13_ANALYTICS_TRACKING.md`: trend and reporting context
- `../../../14_AI_VISIBILITY_SYSTEM.md`: AI visibility signals
- `../../../prompts/scoring_system.md`: target scoring architecture
- `../../../prompts/live_intelligent_recommendation_systems.md`: recommendation priority and UX direction
- `../../../prompts/aeo_engine.md`: AI visibility score direction
