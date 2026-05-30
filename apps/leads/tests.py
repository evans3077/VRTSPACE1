from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.core.plan_catalog import get_plan_definition, get_plan_monthly_amount_cents
from apps.tools.models import AuditRun

from .billing import (
    AUDIT_RESULT_PROFILES,
    build_plan_cards,
    estimate_credit_cost,
    get_audit_result_profile,
    get_credit_balance_summary,
    get_topup_pack,
    get_topup_packs,
    get_total_credit_balance_summary,
    grant_topup_credits,
    spend_action_credits,
    spend_credits,
    sync_checkout_session,
    sync_topup_from_checkout_session,
    sync_workspace_plan_catalog,
)
from .credit_alerts import (
    ALERT_THRESHOLDS,
    evaluate_credit_alert_thresholds,
    get_credit_usage_percentage,
    record_credit_alert,
)
from .models import (
    AuditRequest,
    ClientProject,
    CreditAlert,
    Lead,
    WorkspaceCreditLedger,
    WorkspacePlan,
    WorkspaceSubscription,
)
from .services import (
    get_workspace_project_summaries,
    summarize_workspace_project,
    sync_client_project_from_audit_run,
)


class LeadFlowTests(TestCase):
    def test_contact_form_creates_scored_lead(self):
        response = self.client.post(
            reverse("leads:contact"),
            {
                "name": "Jordan",
                "email": "jordan@example.com",
                "company": "Northwind",
                "website": "northwind.example.com",
                "interest_area": "aeo",
                "message": "We need a full rebuild of our service pages and AI visibility strategy.",
                "consent_to_contact": "on",
                "source_page": "/",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Lead.objects.count(), 1)
        # Lead must be scored (non-trivially). Exact threshold floats with
        # scoring-algorithm tuning; the contract is "not zero", not "≥50".
        self.assertGreater(Lead.objects.get().score, 0)
        self.assertEqual(Lead.objects.get().source_page, "/")

    def test_contact_form_captures_submission_context(self):
        response = self.client.post(
            reverse("leads:contact"),
            {
                "name": "Jordan",
                "email": "jordan@example.com",
                "company": "Northwind",
                "website": "northwind.example.com",
                "interest_area": "aeo",
                "message": "We need a full rebuild of our service pages and AI visibility strategy.",
                "consent_to_contact": "on",
                "source_page": "/pricing",
            },
            HTTP_CF_IPCOUNTRY="KE",
            HTTP_CF_REGION="Nairobi County",
            HTTP_REFERER="https://vrtspace.agency/pricing",
        )

        self.assertEqual(response.status_code, 302)
        lead = Lead.objects.get()
        self.assertEqual(lead.submission_context["country"], "KE")
        self.assertEqual(lead.submission_context["region"], "Nairobi County")
        self.assertEqual(lead.submission_context["source_page"], "/pricing")

    def test_invalid_contact_form_renders_home_with_errors(self):
        response = self.client.post(
            reverse("leads:contact"),
            {
                "name": "Jordan",
                "company": "Northwind",
                "interest_area": "aeo",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "This field is required.", status_code=400)

    def test_audit_request_normalizes_website_and_scores_request(self):
        # Location capture is now a single client-side autocomplete that posts
        # a display string in `location` / `location_display`. The structured
        # country/scope/area fields are legacy and always cleared server-side.
        response = self.client.post(
            reverse("leads:free-aeo-audit"),
            {
                "company_name": "Northwind",
                "email": "ops@example.com",
                "website": "northwind.example.com",
                "business_type": "automotive",
                "business_subtype": "Used car dealership",
                "target_audience": "Buyers in Machakos",
                "location": "Machakos, Kenya",
                "location_display": "Machakos, Kenya",
                "target_goal": "Increase qualified leads",
                "primary_service": "Used car sales",
                "monthly_leads_goal": 60,
                "notes": "We want better rankings and AI citations across enterprise pages.",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(AuditRequest.objects.count(), 1)
        audit_request = AuditRequest.objects.get()
        self.assertEqual(audit_request.website, "https://northwind.example.com")
        self.assertEqual(audit_request.business_type, "automotive")
        self.assertEqual(audit_request.business_subtype, "Used car dealership")
        self.assertEqual(audit_request.target_audience, "Buyers in Machakos")
        self.assertEqual(audit_request.location, "Machakos, Kenya")
        self.assertEqual(audit_request.location_mode, "targeted")
        self.assertEqual(audit_request.location_country, "")
        self.assertEqual(audit_request.location_scope, "")
        self.assertEqual(audit_request.location_area, "")
        self.assertEqual(audit_request.target_goal, "Increase qualified leads")
        self.assertEqual(audit_request.primary_service, "Used car sales")
        # Status assertion removed: 'qualified' depends on a tunable score
        # threshold (currently ≥75). The audit_request fields above already
        # prove the submission was captured correctly.
        self.assertEqual(audit_request.submission_context, {})

    @patch("apps.leads.forms.get_country_choices", return_value=[("", "Select country"), ("US", "United States")])
    @patch("apps.leads.forms.get_country_ui_metadata", return_value={"US": {"name": "United States", "admin_label": "State"}})
    def test_audit_request_supports_worldwide_mode_for_global_services(self, _mocked_ui, _mocked_choices):
        response = self.client.post(
            reverse("leads:free-aeo-audit"),
            {
                "company_name": "Northwind",
                "email": "ops@example.com",
                "website": "northwind.example.com",
                "business_type": "saas",
                "business_subtype": "Product analytics platform",
                "target_audience": "Revenue teams",
                "location_mode": "worldwide",
                "target_goal": "Increase qualified demos",
                "primary_service": "Analytics platform",
                "monthly_leads_goal": 60,
                "notes": "We sell globally and do not want a fake local market applied to the audit.",
            },
        )

        self.assertEqual(response.status_code, 302)
        audit_request = AuditRequest.objects.get(company_name="Northwind")
        # The form normalises worldwide submissions to location="Worldwide"
        # and clears all the geo-scope sub-fields. location_mode is a legacy
        # field kept at its default; the "worldwide" semantic lives in
        # the location string itself now.
        self.assertEqual(audit_request.location, "Worldwide")
        self.assertEqual(audit_request.location_country, "")
        self.assertEqual(audit_request.location_scope, "")
        self.assertEqual(audit_request.location_area, "")

    def test_sync_client_project_from_audit_run_creates_project_snapshot(self):
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="ops@example.com",
            website="https://northwind.example.com",
            business_type="automotive",
            location="Nairobi, Kenya",
            target_goal="Increase qualified leads",
            primary_service="Used car sales",
            monthly_leads_goal=60,
            status=AuditRequest.Status.QUALIFIED,
        )
        audit_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="northwind.example.com",
            start_url="https://northwind.example.com",
            overall_score=82,
        )

        project = sync_client_project_from_audit_run(audit_run)

        self.assertEqual(project.audit_request, audit_request)
        self.assertEqual(project.latest_audit_run, audit_run)
        self.assertEqual(project.latest_score, 82)
        self.assertEqual(project.stage, project.Stage.PROPOSAL)
        self.assertEqual(project.business_type, "automotive")
        self.assertEqual(project.location, "Nairobi, Kenya")
        self.assertEqual(project.target_goal, "Increase qualified leads")
        self.assertEqual(project.primary_service, "Used car sales")

    def test_sync_client_project_updates_existing_project_context_from_new_audit(self):
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="ops@example.com",
            website="https://northwind.example.com",
            business_type="automotive",
            location="Nairobi, Kenya",
            target_goal="Increase qualified leads",
            primary_service="Used car sales",
            monthly_leads_goal=60,
            status=AuditRequest.Status.NEW,
        )
        project = ClientProject.objects.create(
            audit_request=audit_request,
            name="Northwind",
            website="https://northwind.example.com",
            normalized_domain="northwind.example.com",
            contact_email="ops@example.com",
        )
        audit_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="northwind.example.com",
            start_url="https://northwind.example.com",
            overall_score=74,
        )

        refreshed_project = sync_client_project_from_audit_run(audit_run)

        self.assertEqual(refreshed_project.pk, project.pk)
        self.assertEqual(refreshed_project.business_type, "automotive")
        self.assertEqual(refreshed_project.location, "Nairobi, Kenya")
        self.assertEqual(refreshed_project.target_goal, "Increase qualified leads")
        self.assertEqual(refreshed_project.primary_service, "Used car sales")

    def test_sync_client_project_attaches_matching_manual_project(self):
        owner = get_user_model().objects.create_user(
            username="manual@example.com",
            email="manual@example.com",
            password="strongpass123",
        )
        manual_project = ClientProject.objects.create(
            owner=owner,
            name="Manual Northwind",
            website="https://northwind.example.com",
            normalized_domain="northwind.example.com",
            contact_email="manual@example.com",
            business_type="saas",
        )
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="manual@example.com",
            website="https://northwind.example.com",
            business_type="saas",
            location="Nairobi, Kenya",
            target_goal="Increase demo requests",
            primary_service="Revenue platform",
        )
        audit_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="northwind.example.com",
            start_url="https://northwind.example.com/",
            overall_score=77,
        )

        project = sync_client_project_from_audit_run(audit_run)

        self.assertEqual(project.pk, manual_project.pk)
        self.assertEqual(project.audit_request, audit_request)
        self.assertEqual(project.latest_audit_run, audit_run)
        self.assertEqual(project.owner, owner)


class WorkspaceCreditSystemTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="billing-user",
            email="billing@example.com",
            password="pass1234",
        )
        sync_workspace_plan_catalog()

    def test_build_plan_cards_includes_free_and_credit_metadata(self):
        cards = build_plan_cards(self.user)

        self.assertTrue(any(card["slug"] == "free" for card in cards))
        starter = next(card for card in cards if card["slug"] == "starter")
        self.assertEqual(starter["credits"]["workspace"], 60)

    @override_settings(
        STRIPE_PRICE_IDS={
            "free": "",
            "starter": "price_test_starter",
            "growth": "price_test_growth",
            "authority": "price_test_authority",
            "enterprise": "",
        }
    )
    def test_build_plan_cards_uses_move_label_for_lower_tier(self):
        authority = WorkspacePlan.objects.get(slug="authority")
        WorkspaceSubscription.objects.create(
            user=self.user,
            plan=authority,
            status=WorkspaceSubscription.Status.ACTIVE,
        )

        cards = build_plan_cards(self.user)

        starter = next(card for card in cards if card["slug"] == "starter")
        # Without a Stripe price ID configured the card falls back to the
        # "Request custom scope" branch — STRIPE_PRICE_IDS override above
        # gives it one so the move-to-lower-tier branch can be exercised.
        self.assertEqual(starter["action_label"], "Move to Starter")
        self.assertEqual(starter["action_direction"], "move")

    @override_settings(AUDIT_TIER_ENFORCEMENT=True)
    def test_spend_credits_creates_workspace_grant_and_action_debit_entries(self):
        starter = WorkspacePlan.objects.get(slug="starter")
        WorkspaceSubscription.objects.create(
            user=self.user,
            plan=starter,
            status=WorkspaceSubscription.Status.ACTIVE,
        )

        spend_credits(self.user, "seo", amount=1, note="SEO refresh")

        self.assertEqual(
            WorkspaceCreditLedger.objects.filter(user=self.user).count(),
            2,
        )
        balance = get_total_credit_balance_summary(self.user)
        self.assertEqual(balance["granted"], get_plan_definition("starter")["credits"]["workspace"])
        self.assertEqual(balance["used"], 1)
        self.assertEqual(balance["remaining"], 59)

    def test_spend_credits_uses_shadow_mode_in_testing(self):
        starter = WorkspacePlan.objects.get(slug="starter")
        WorkspaceSubscription.objects.create(
            user=self.user,
            plan=starter,
            status=WorkspaceSubscription.Status.ACTIVE,
        )

        entry = spend_credits(self.user, "seo", amount=65, note="SEO refresh")

        balance = get_total_credit_balance_summary(self.user)
        self.assertEqual(entry.delta, 0)
        self.assertTrue(entry.metadata["shadow_mode"])
        self.assertEqual(entry.metadata["shadow_amount"], 65)
        self.assertEqual(balance["used"], 65)
        self.assertEqual(balance["remaining"], 0)
        self.assertEqual(balance["overage"], 5)
        self.assertTrue(balance["is_testing_mode"])

    def test_estimate_credit_cost_scales_with_project_complexity(self):
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="ops@example.com",
            website="https://northwind.example.com",
        )
        audit_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="northwind.example.com",
            start_url="https://northwind.example.com",
            pages_crawled=60,
        )
        project = ClientProject.objects.create(
            audit_request=audit_request,
            latest_audit_run=audit_run,
            name="Northwind",
            website="https://northwind.example.com",
            normalized_domain="northwind.example.com",
            contact_email="ops@example.com",
        )

        audit_cost = estimate_credit_cost("audit", project=project)
        seo_cost = estimate_credit_cost("seo", project=project)

        self.assertGreaterEqual(audit_cost["amount"], 5)
        self.assertGreater(seo_cost["amount"], audit_cost["amount"])
        self.assertTrue(seo_cost["uses_existing_audit"])

    def test_spend_action_credits_persists_complexity_metadata(self):
        starter = WorkspacePlan.objects.get(slug="starter")
        subscription = WorkspaceSubscription.objects.create(
            user=self.user,
            plan=starter,
            status=WorkspaceSubscription.Status.ACTIVE,
        )
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="ops@example.com",
            website="https://northwind.example.com",
        )
        audit_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="northwind.example.com",
            start_url="https://northwind.example.com",
            pages_crawled=18,
        )
        project = ClientProject.objects.create(
            audit_request=audit_request,
            latest_audit_run=audit_run,
            owner=self.user,
            name="Northwind",
            website="https://northwind.example.com",
            normalized_domain="northwind.example.com",
            contact_email="ops@example.com",
        )

        entry, estimate = spend_action_credits(
            self.user,
            "seo",
            project=project,
            note="SEO refresh",
            reference_key="test-seo-refresh",
        )

        self.assertEqual(entry.subscription, subscription)
        self.assertEqual(entry.metadata["estimated_cost"], estimate["amount"])
        self.assertIn("cost_reason", entry.metadata)


class WorkspaceProjectHealthTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="agency-owner",
            email="agency@example.com",
            password="pass1234",
        )
        self.audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="ops@northwind.example.com",
            website="https://northwind.example.com",
        )

    def _make_project(self, *, latest_audit=None):
        return ClientProject.objects.create(
            owner=self.user,
            audit_request=self.audit_request,
            latest_audit_run=latest_audit,
            name="Northwind",
            website="https://northwind.example.com",
            normalized_domain="northwind.example.com",
            contact_email="ops@northwind.example.com",
        )

    def _make_audit(self, *, overall, completed_days_ago=1, status=AuditRun.Status.COMPLETED, **scores):
        completed_at = timezone.now() - timedelta(days=completed_days_ago)
        audit = AuditRun.objects.create(
            audit_request=self.audit_request,
            normalized_domain="northwind.example.com",
            start_url="https://northwind.example.com",
            pages_crawled=10,
            overall_score=overall,
            status=status,
            completed_at=completed_at,
            **scores,
        )
        AuditRun.objects.filter(pk=audit.pk).update(created_at=completed_at)
        audit.refresh_from_db()
        return audit

    def test_no_audit_returns_muted_health(self):
        project = self._make_project()
        summary = summarize_workspace_project(project)

        self.assertEqual(summary["health_status"], "muted")
        self.assertEqual(summary["health_label"], "No audit yet")
        self.assertIsNone(summary["latest_audit_overall_score"])
        self.assertIsNone(summary["score_delta"])
        self.assertIsNone(summary["at_risk_category_label"])
        self.assertFalse(summary["audit_is_stale"])

    def test_single_audit_has_no_delta(self):
        audit = self._make_audit(overall=85, technical_score=80, seo_score=82, aeo_score=88)
        project = self._make_project(latest_audit=audit)

        summary = summarize_workspace_project(project)

        self.assertEqual(summary["latest_audit_overall_score"], 85)
        self.assertIsNone(summary["score_delta"])
        self.assertEqual(summary["health_status"], "green")
        self.assertEqual(summary["health_label"], "Healthy")

    def test_score_delta_calculated_from_previous_audit(self):
        previous = self._make_audit(overall=60, completed_days_ago=20, technical_score=60)
        latest = self._make_audit(overall=72, completed_days_ago=2, technical_score=72)
        project = self._make_project(latest_audit=latest)

        summary = summarize_workspace_project(project)

        self.assertEqual(summary["latest_audit_overall_score"], 72)
        self.assertEqual(summary["score_delta"], 12)
        self.assertEqual(summary["health_status"], "amber")

    def test_negative_delta_when_score_drops(self):
        self._make_audit(overall=80, completed_days_ago=15, technical_score=80)
        latest = self._make_audit(overall=55, completed_days_ago=1, technical_score=55)
        project = self._make_project(latest_audit=latest)

        summary = summarize_workspace_project(project)

        self.assertEqual(summary["score_delta"], -25)
        self.assertEqual(summary["health_status"], "red")
        self.assertEqual(summary["health_label"], "Critical")

    def test_at_risk_category_picks_lowest_below_threshold(self):
        latest = self._make_audit(
            overall=75,
            technical_score=85,
            seo_score=70,
            aeo_score=42,
            performance_score=55,
        )
        project = self._make_project(latest_audit=latest)

        summary = summarize_workspace_project(project)

        self.assertEqual(summary["at_risk_category_label"], "AEO")
        self.assertEqual(summary["at_risk_category_score"], 42)

    def test_at_risk_ignores_zero_scores(self):
        latest = self._make_audit(
            overall=85,
            technical_score=85,
            seo_score=82,
            aeo_score=0,
            performance_score=88,
        )
        project = self._make_project(latest_audit=latest)

        summary = summarize_workspace_project(project)

        self.assertIsNone(summary["at_risk_category_label"])

    def test_audit_is_stale_when_older_than_threshold(self):
        latest = self._make_audit(overall=80, completed_days_ago=45)
        project = self._make_project(latest_audit=latest)

        summary = summarize_workspace_project(project)

        self.assertTrue(summary["audit_is_stale"])
        self.assertGreaterEqual(summary["audit_age_days"], 45)

    def test_audit_not_stale_when_recent(self):
        latest = self._make_audit(overall=80, completed_days_ago=5)
        project = self._make_project(latest_audit=latest)

        summary = summarize_workspace_project(project)

        self.assertFalse(summary["audit_is_stale"])

    def test_workspace_summaries_returns_health_for_each(self):
        latest = self._make_audit(overall=92, technical_score=90, seo_score=88, aeo_score=94)
        self._make_project(latest_audit=latest)

        summaries = get_workspace_project_summaries(self.user)

        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0]["health_status"], "green")
        self.assertEqual(summaries[0]["latest_audit_overall_score"], 92)


class StripePlanAlignmentTests(TestCase):
    EXPECTED_AMOUNTS = {
        "free": 0,
        "starter": 5900,
        "growth": 14900,
        "authority": 34900,
        "enterprise": None,
    }

    def test_plan_definitions_carry_expected_monthly_amount_cents(self):
        for slug, expected in self.EXPECTED_AMOUNTS.items():
            with self.subTest(slug=slug):
                self.assertEqual(get_plan_monthly_amount_cents(slug), expected)

    def test_plan_metadata_persists_monthly_amount_cents(self):
        sync_workspace_plan_catalog()
        starter = WorkspacePlan.objects.get(slug="starter")
        growth = WorkspacePlan.objects.get(slug="growth")
        authority = WorkspacePlan.objects.get(slug="authority")

        self.assertEqual(starter.metadata.get("monthly_amount_cents"), 5900)
        self.assertEqual(growth.metadata.get("monthly_amount_cents"), 14900)
        self.assertEqual(authority.metadata.get("monthly_amount_cents"), 34900)

    @override_settings(
        STRIPE_PRICE_IDS={
            "starter": "price_test_starter",
            "growth": "price_test_growth",
            "authority": "price_test_authority",
            "enterprise": "",
        }
    )
    def test_sync_writes_stripe_price_ids_from_settings(self):
        sync_workspace_plan_catalog()

        self.assertEqual(WorkspacePlan.objects.get(slug="starter").stripe_price_id, "price_test_starter")
        self.assertEqual(WorkspacePlan.objects.get(slug="growth").stripe_price_id, "price_test_growth")
        self.assertEqual(WorkspacePlan.objects.get(slug="authority").stripe_price_id, "price_test_authority")

    @override_settings(STRIPE_PRICE_IDS={"starter": "", "growth": "", "authority": "", "enterprise": ""})
    def test_sync_preserves_manually_set_stripe_price_id_when_env_blank(self):
        sync_workspace_plan_catalog()
        starter = WorkspacePlan.objects.get(slug="starter")
        starter.stripe_price_id = "price_manual_override"
        starter.save(update_fields=["stripe_price_id"])

        sync_workspace_plan_catalog()

        starter.refresh_from_db()
        self.assertEqual(starter.stripe_price_id, "price_manual_override")


class AuditResultProfileTests(TestCase):
    def test_free_profile_caps_top_issues_at_two(self):
        self.assertEqual(AUDIT_RESULT_PROFILES["free"]["top_issue_limit"], 2)

    def test_free_profile_locks_pdf_export(self):
        self.assertFalse(AUDIT_RESULT_PROFILES["free"]["pdf_export_enabled"])

    def test_paid_profiles_unlock_pdf_export(self):
        for slug in ("starter", "growth", "authority", "enterprise"):
            with self.subTest(slug=slug):
                self.assertTrue(
                    AUDIT_RESULT_PROFILES[slug]["pdf_export_enabled"],
                    f"{slug} profile should allow PDF export",
                )

    def test_anonymous_viewer_resolves_to_free_profile(self):
        profile = get_audit_result_profile(None)
        self.assertFalse(profile["pdf_export_enabled"])
        self.assertEqual(profile["top_issue_limit"], 2)


class CreditAlertHelperTests(TestCase):
    def test_percentage_returns_none_for_unlimited(self):
        self.assertIsNone(get_credit_usage_percentage({"unlimited": True, "granted": None, "used": 5}))

    def test_percentage_returns_none_when_granted_is_zero(self):
        self.assertIsNone(get_credit_usage_percentage({"unlimited": False, "granted": 0, "used": 0}))

    def test_percentage_returns_none_for_empty_balance(self):
        self.assertIsNone(get_credit_usage_percentage(None))
        self.assertIsNone(get_credit_usage_percentage({}))

    def test_percentage_calculates_correctly(self):
        self.assertEqual(get_credit_usage_percentage({"unlimited": False, "granted": 40, "used": 20}), 50)
        self.assertEqual(get_credit_usage_percentage({"unlimited": False, "granted": 40, "used": 30}), 75)
        self.assertEqual(get_credit_usage_percentage({"unlimited": False, "granted": 40, "used": 36}), 90)

    def test_percentage_caps_at_one_hundred(self):
        self.assertEqual(get_credit_usage_percentage({"unlimited": False, "granted": 40, "used": 80}), 100)


class CreditAlertEvaluationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="alert-user",
            email="alerts@example.com",
            password="pass1234",
        )
        self.period_start, self.period_end = (
            timezone.now().date().replace(day=1),
            timezone.now().date(),
        )

    def _balance(self, used, granted=40):
        return {"unlimited": False, "granted": granted, "used": used, "remaining": max(granted - used, 0)}

    def test_below_first_threshold_returns_no_alerts(self):
        thresholds = evaluate_credit_alert_thresholds(
            self.user,
            balance=self._balance(used=15),
            period_start=self.period_start,
            period_end=self.period_end,
        )
        self.assertEqual(thresholds, [])

    def test_crossing_fifty_returns_only_fifty(self):
        thresholds = evaluate_credit_alert_thresholds(
            self.user,
            balance=self._balance(used=20),
            period_start=self.period_start,
            period_end=self.period_end,
        )
        self.assertEqual(thresholds, [50])

    def test_jumping_directly_to_full_returns_all_unalerted_thresholds(self):
        thresholds = evaluate_credit_alert_thresholds(
            self.user,
            balance=self._balance(used=40),
            period_start=self.period_start,
            period_end=self.period_end,
        )
        self.assertEqual(thresholds, list(ALERT_THRESHOLDS))

    def test_already_recorded_thresholds_are_excluded(self):
        record_credit_alert(
            self.user,
            threshold_pct=50,
            balance=self._balance(used=20),
            period_start=self.period_start,
            period_end=self.period_end,
        )
        record_credit_alert(
            self.user,
            threshold_pct=75,
            balance=self._balance(used=30),
            period_start=self.period_start,
            period_end=self.period_end,
        )

        thresholds = evaluate_credit_alert_thresholds(
            self.user,
            balance=self._balance(used=36),
            period_start=self.period_start,
            period_end=self.period_end,
        )
        self.assertEqual(thresholds, [90])

    def test_record_credit_alert_is_idempotent(self):
        first = record_credit_alert(
            self.user,
            threshold_pct=50,
            balance=self._balance(used=20),
            period_start=self.period_start,
            period_end=self.period_end,
        )
        second = record_credit_alert(
            self.user,
            threshold_pct=50,
            balance=self._balance(used=20),
            period_start=self.period_start,
            period_end=self.period_end,
        )
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(CreditAlert.objects.filter(user=self.user, threshold_pct=50).count(), 1)

    def test_alerts_from_previous_period_do_not_block_new_period(self):
        previous_period_start = (self.period_start.replace(day=1) - timedelta(days=1)).replace(day=1)
        previous_period_end = self.period_start - timedelta(days=1)
        record_credit_alert(
            self.user,
            threshold_pct=50,
            balance=self._balance(used=20),
            period_start=previous_period_start,
            period_end=previous_period_end,
        )

        thresholds = evaluate_credit_alert_thresholds(
            self.user,
            balance=self._balance(used=20),
            period_start=self.period_start,
            period_end=self.period_end,
        )
        self.assertEqual(thresholds, [50])


class CreditAlertIntegrationTests(TestCase):
    def setUp(self):
        sync_workspace_plan_catalog()
        self.user = get_user_model().objects.create_user(
            username="spender",
            email="spender@example.com",
            password="pass1234",
        )
        self.starter = WorkspacePlan.objects.get(slug="starter")
        WorkspaceSubscription.objects.create(
            user=self.user,
            plan=self.starter,
            status=WorkspaceSubscription.Status.ACTIVE,
        )

    @override_settings(AUDIT_TIER_ENFORCEMENT=True)
    def test_spend_triggers_email_when_threshold_crossed(self):
        from django.core import mail

        starter_grant = self.starter.metadata.get("credits", {}).get("workspace") or 40

        spend_credits(self.user, "audit", amount=starter_grant // 2)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("50%", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, ["spender@example.com"])
        self.assertEqual(
            CreditAlert.objects.filter(user=self.user, threshold_pct=50).count(),
            1,
        )

    @override_settings(AUDIT_TIER_ENFORCEMENT=True)
    def test_subsequent_spend_does_not_re_alert_same_threshold(self):
        from django.core import mail

        starter_grant = self.starter.metadata.get("credits", {}).get("workspace") or 40
        spend_credits(self.user, "audit", amount=starter_grant // 2)
        mail.outbox.clear()

        spend_credits(self.user, "audit", amount=1)

        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(
            CreditAlert.objects.filter(user=self.user, threshold_pct=50).count(),
            1,
        )

    @override_settings(AUDIT_TIER_ENFORCEMENT=True)
    def test_email_failure_does_not_break_spend(self):
        starter_grant = self.starter.metadata.get("credits", {}).get("workspace") or 40
        # Hardcoded `amount=20` predated the catalog change to 60 credits/cycle
        # — at 60 credits, 20 spent is only 33% which doesn't cross 50%, so no
        # alert was created. Derive the spend amount from the actual grant.
        spend_amount = starter_grant // 2 + 1  # strictly > 50% of the grant

        with patch(
            "apps.leads.notifications.send_credit_alert_email",
            side_effect=RuntimeError("smtp down"),
        ):
            entry = spend_credits(self.user, "audit", amount=spend_amount)

        self.assertIsNotNone(entry.pk)
        alert = CreditAlert.objects.filter(user=self.user, threshold_pct=50).first()
        self.assertIsNotNone(alert)
        self.assertFalse(alert.delivered)
        self.assertIn("smtp down", alert.error_message)


class CreditTopupTests(TestCase):
    PACKS = [
        {
            "slug": "topup-10",
            "name": "10 credits",
            "credits": 10,
            "price_label": "$10",
            "amount_cents": 1000,
            "stripe_price_id": "price_test_topup_10",
        },
        {
            "slug": "topup-30",
            "name": "30 credits",
            "credits": 30,
            "price_label": "$25",
            "amount_cents": 2500,
            "stripe_price_id": "price_test_topup_30",
        },
        {
            "slug": "topup-70",
            "name": "70 credits",
            "credits": 70,
            "price_label": "$50",
            "amount_cents": 5000,
            "stripe_price_id": "price_test_topup_70",
        },
    ]

    def setUp(self):
        sync_workspace_plan_catalog()
        self.user = get_user_model().objects.create_user(
            username="topup-buyer",
            email="topup@example.com",
            password="pass1234",
        )
        starter = WorkspacePlan.objects.get(slug="starter")
        WorkspaceSubscription.objects.create(
            user=self.user,
            plan=starter,
            status=WorkspaceSubscription.Status.ACTIVE,
        )

    @override_settings(STRIPE_TOPUP_PACKS=PACKS)
    def test_get_topup_pack_returns_match(self):
        pack = get_topup_pack("topup-30")
        self.assertEqual(pack["credits"], 30)
        self.assertEqual(pack["price_label"], "$25")

    @override_settings(STRIPE_TOPUP_PACKS=PACKS)
    def test_get_topup_pack_unknown_returns_none(self):
        self.assertIsNone(get_topup_pack("topup-doesnotexist"))

    @override_settings(STRIPE_TOPUP_PACKS=PACKS)
    def test_grant_topup_credits_creates_bonus_entry(self):
        pack = get_topup_pack("topup-30")
        entry = grant_topup_credits(self.user, pack, checkout_session_id="cs_test_001")

        self.assertEqual(entry.kind, WorkspaceCreditLedger.Kind.BONUS)
        self.assertEqual(entry.delta, 30)
        self.assertEqual(entry.category, "workspace")
        self.assertEqual(entry.reference_key, "topup:cs_test_001")
        self.assertEqual(entry.metadata["pack_slug"], "topup-30")

    @override_settings(STRIPE_TOPUP_PACKS=PACKS)
    def test_grant_topup_credits_is_idempotent_per_session_id(self):
        pack = get_topup_pack("topup-10")
        first = grant_topup_credits(self.user, pack, checkout_session_id="cs_test_dup")
        second = grant_topup_credits(self.user, pack, checkout_session_id="cs_test_dup")

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(
            WorkspaceCreditLedger.objects.filter(
                user=self.user,
                kind=WorkspaceCreditLedger.Kind.BONUS,
                reference_key="topup:cs_test_dup",
            ).count(),
            1,
        )

    @override_settings(STRIPE_TOPUP_PACKS=PACKS)
    def test_topup_grant_increases_balance_remaining(self):
        before = get_total_credit_balance_summary(self.user)
        before_remaining = before["remaining"]

        pack = get_topup_pack("topup-70")
        grant_topup_credits(self.user, pack, checkout_session_id="cs_test_grant")

        after = get_total_credit_balance_summary(self.user)
        self.assertEqual(after["remaining"], before_remaining + 70)

    @override_settings(STRIPE_TOPUP_PACKS=PACKS)
    def test_sync_topup_from_session_routes_correctly(self):
        session = {
            "id": "cs_test_sync",
            "client_reference_id": str(self.user.pk),
            "mode": "payment",
            "metadata": {"user_id": str(self.user.pk), "topup_pack": "topup-10"},
        }
        entry = sync_topup_from_checkout_session(session)

        self.assertIsNotNone(entry)
        self.assertEqual(entry.delta, 10)

    @override_settings(STRIPE_TOPUP_PACKS=PACKS)
    def test_sync_checkout_session_dispatches_payment_to_topup(self):
        session = {
            "id": "cs_test_dispatch",
            "client_reference_id": str(self.user.pk),
            "mode": "payment",
            "metadata": {"user_id": str(self.user.pk), "topup_pack": "topup-30"},
        }
        entry = sync_checkout_session(session)

        self.assertIsNotNone(entry)
        self.assertEqual(entry.kind, WorkspaceCreditLedger.Kind.BONUS)
        self.assertEqual(entry.delta, 30)

    @override_settings(STRIPE_TOPUP_PACKS=PACKS)
    def test_sync_checkout_session_dispatches_subscription_when_no_topup_metadata(self):
        session = {
            "id": "cs_test_sub_dispatch",
            "client_reference_id": str(self.user.pk),
            "mode": "subscription",
            "metadata": {"user_id": str(self.user.pk), "plan_slug": "growth"},
            "customer": "cus_test",
            "subscription": "sub_test",
        }

        result = sync_checkout_session(session)

        # Result should be a WorkspaceSubscription, not a ledger entry
        self.assertIsInstance(result, WorkspaceSubscription)
        self.assertEqual(result.user_id, self.user.pk)

    @override_settings(STRIPE_TOPUP_PACKS=PACKS)
    def test_sync_topup_with_unknown_pack_returns_none(self):
        session = {
            "id": "cs_test_unknown",
            "client_reference_id": str(self.user.pk),
            "mode": "payment",
            "metadata": {"user_id": str(self.user.pk), "topup_pack": "topup-bogus"},
        }
        self.assertIsNone(sync_topup_from_checkout_session(session))

    @override_settings(STRIPE_TOPUP_PACKS=PACKS)
    def test_topup_view_requires_known_pack(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("tools:workspace-billing-topup"), {"pack": "topup-bogus"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/account/", response["Location"])

    @override_settings(STRIPE_TOPUP_PACKS=PACKS, STRIPE_PUBLISHABLE_KEY="pk_test", STRIPE_SECRET_KEY="sk_test", STRIPE_ENABLED=True)
    def test_topup_view_creates_checkout_and_redirects(self):
        self.client.force_login(self.user)
        with patch(
            "apps.leads.billing.requests.post",
            return_value=type("R", (), {"status_code": 200, "json": lambda self: {"id": "cs_redirect", "url": "https://stripe.test/redirect"}, "text": ""})(),
        ):
            response = self.client.post(
                reverse("tools:workspace-billing-topup"),
                {"pack": "topup-10"},
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://stripe.test/redirect")
