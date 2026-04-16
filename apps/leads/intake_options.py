BUSINESS_TYPE_CHOICES = (
    ("", "Select business type"),
    ("automotive", "Automotive"),
    ("agency", "Agency / Professional Services"),
    ("saas", "SaaS / Product"),
    ("hotel", "Hotel / Hospitality"),
    ("restaurant_food", "Restaurant / Food / Beverage"),
    ("ecommerce", "Ecommerce"),
    ("healthcare", "Healthcare"),
    ("real_estate", "Real Estate"),
    ("local_service", "Local Service Business"),
    ("legal", "Legal"),
    ("education", "Education"),
    ("finance", "Finance / Fintech"),
    ("beauty_wellness", "Beauty / Wellness"),
    ("construction", "Construction / Trades"),
    ("manufacturing", "Manufacturing / Industrial"),
    ("media", "Media / Publishing"),
    ("travel", "Travel / Tourism"),
    ("events", "Events / Entertainment"),
    ("nonprofit", "Nonprofit / NGO"),
    ("other", "Other"),
)

BUSINESS_TYPE_LABELS = {value: label for value, label in BUSINESS_TYPE_CHOICES if value}

LOCATION_MODE_CHOICES = (
    ("targeted", "Specific market"),
    ("worldwide", "Worldwide / global"),
)

LOCATION_SCOPE_CHOICES = (
    ("city_town", "City / town"),
    ("county", "County"),
    ("state", "State"),
    ("province", "Province"),
    ("region", "Region"),
)

LOCATION_SCOPE_LABELS = {value: label for value, label in LOCATION_SCOPE_CHOICES}

GLOBAL_MARKET_BUSINESS_TYPES = {
    "saas",
    "agency",
    "finance",
    "media",
}


def get_business_type_label(value):
    return BUSINESS_TYPE_LABELS.get(value or "", str(value or "").replace("_", " ").strip().title())
