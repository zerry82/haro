from app.services.mail_filtering import evaluate_mail_filters, normalize_filter_rules


def test_deny_filter_wins_over_matching_allow_filter() -> None:
    thread = {
        "subject": "Weekly report newsletter",
        "sender": "manager@example.com",
        "recipients": ["team@company.com"],
    }
    filters = [
        {"id": "allow-example", "effect": "allow", "field": "sender", "operator": "domain_equals", "value": "example.com"},
        {"id": "deny-newsletter", "effect": "deny", "field": "subject", "operator": "contains", "value": "newsletter"},
    ]

    result = evaluate_mail_filters(thread, filters)

    assert result.decision == "denied"
    assert result.matched_filter_ids == ["deny-newsletter"]


def test_allow_rules_require_at_least_one_match() -> None:
    thread = {
        "subject": "Weekly report",
        "sender": "manager@example.com",
        "recipients": ["team@company.com"],
    }
    filters = [
        {"effect": "allow", "field": "sender", "operator": "domain_equals", "value": "client.com"},
    ]

    result = evaluate_mail_filters(thread, filters)

    assert result.decision == "denied"


def test_empty_allow_rules_default_to_allowed() -> None:
    thread = {
        "subject": "Weekly report",
        "sender": "manager@example.com",
        "recipients": ["team@company.com"],
    }

    result = evaluate_mail_filters(thread, [])

    assert result.decision == "allowed"


def test_recipient_domain_filter_matches_any_recipient() -> None:
    thread = {
        "subject": "Weekly report",
        "sender": "manager@example.com",
        "recipients": ["owner@company.com", "client@customer.co.kr"],
    }
    filters = [
        {"effect": "allow", "field": "recipient", "operator": "domain_equals", "value": "@customer.co.kr"},
    ]

    result = evaluate_mail_filters(thread, filters)

    assert result.decision == "allowed"


def test_normalize_filter_rules_drops_invalid_rules() -> None:
    rules = normalize_filter_rules([
        {"field": "sender", "operator": "domain_equals", "value": "example.com", "effect": "allow"},
        {"field": "body", "operator": "contains", "value": "secret", "effect": "deny"},
        {"field": "subject", "operator": "regex", "value": ".*", "effect": "deny"},
    ])

    assert rules == [{
        "id": "filter-1",
        "effect": "allow",
        "field": "sender",
        "operator": "domain_equals",
        "value": "example.com",
        "enabled": True,
    }]

