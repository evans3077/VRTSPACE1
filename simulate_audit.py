import os
import sys
import django

# Setup Django
sys.path.append('D:\\VRTSPACE')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.tools.models import AuditRun
from apps.tools.services import run_public_site_audit, normalize_url
from apps.leads.models import AuditRequest

def simulate_audit(target_url):
    print(f"Simulating audit for: {target_url}")
    
    # Create a mock audit request
    audit_request = AuditRequest.objects.create(
        email="test@example.com",
        website=target_url,
        company_name="Simulation Corp"
    )
    
    # Create the audit run
    audit_run = AuditRun.objects.create(
        audit_request=audit_request,
        normalized_domain=normalize_url(target_url),
        start_url=target_url
    )
    
    print(f"AuditRun ID: {audit_run.pk}")
    
    try:
        # Run the audit
        run_public_site_audit(audit_run=audit_run)
        
        print(f"Status: {audit_run.status}")
        if audit_run.status == AuditRun.Status.COMPLETED:
            summary = audit_run.summary
            scores = summary.get('scores', {})
            print(f"Scores: {scores}")
            print(f"Has Vitals Failure: {summary.get('has_vitals_failure')}")
            if summary.get('has_vitals_failure'):
                print(f"Vitals Failures: {summary.get('vitals_failures')}")
        else:
            print(f"Error: {audit_run.error_message}")
            
    except Exception as e:
        print(f"FAILED with Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Simulate an audit for a site likely to have some issues
    simulate_audit("https://www.marriott.com")
