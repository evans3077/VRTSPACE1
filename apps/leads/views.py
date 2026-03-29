from django.contrib import messages
from django.core.cache import cache
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.views import View

from apps.core.views import HomePageView, build_home_context

from .forms import AuditRequestForm, LeadCaptureForm
from .services import create_audit_request_from_form, create_lead_from_form


class RateLimitedPostView(View):
    rate_limit = 5
    rate_window = 900
    anchor = ""

    def dispatch(self, request, *args, **kwargs):
        if request.method.lower() == "post":
            ip_address = request.META.get("REMOTE_ADDR", "unknown")
            cache_key = f"rate-limit:{self.__class__.__name__}:{ip_address}"
            attempts = cache.get(cache_key, 0)
            if attempts >= self.rate_limit:
                messages.error(request, "Too many submissions. Try again in a few minutes.")
                return HttpResponseRedirect(f"/#{self.anchor}" if self.anchor else "/")
            cache.set(cache_key, attempts + 1, timeout=self.rate_window)
        return super().dispatch(request, *args, **kwargs)


class ContactLeadCreateView(RateLimitedPostView):
    anchor = "contact"

    def get(self, request, *args, **kwargs):
        # Gracefully handle any GET requests (e.g. from lingering links or old tabs)
        # by redirecting to the actual contact form on the home page.
        return HttpResponseRedirect("/#contact")

    def post(self, request, *args, **kwargs):
        form = LeadCaptureForm(request.POST)
        if form.is_valid():
            source_page = (
                request.POST.get("source_page")
                or request.META.get("HTTP_REFERER")
                or "/"
            )
            create_lead_from_form(form, source_page=source_page)
            messages.success(request, "Strategy request received. We will follow up shortly.")
            return HttpResponseRedirect("/#contact")

        context = build_home_context(
            request,
            lead_form=form,
            audit_form=AuditRequestForm(),
        )
        return render(request, HomePageView.template_name, context, status=400)


class AuditRequestCreateView(RateLimitedPostView):
    anchor = "audit"

    def get(self, request, *args, **kwargs):
        return HttpResponseRedirect("/#audit")

    def post(self, request, *args, **kwargs):
        form = AuditRequestForm(request.POST)
        if form.is_valid():
            create_audit_request_from_form(form)
            messages.success(request, "Audit request received. A strategist will review it.")
            return HttpResponseRedirect("/#audit")

        context = build_home_context(
            request,
            lead_form=LeadCaptureForm(),
            audit_form=form,
        )
        return render(request, HomePageView.template_name, context, status=400)
