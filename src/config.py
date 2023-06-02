import yaml
import os

# Default policies
DEFAULT_POLICIES = [{
    'name': 'Default Policy',
    'rules': [
        {'rule': 'DeleteOlderThan', 'days': 7},
        {'rule': 'SaveLastNProdTags', 'regexp': r'^v\d+\.\d+\.\d+$', 'limit': 5},
        {'rule': 'SaveLastNStagingTags', 'regexp': r'^v\d+\.\d+\.\d+.+', 'limit': 5},
        {'rule': 'SaveLastNFeatureTags', 'limit': 10},
        {'rule': 'IgnoreTags', 'tags': []}
    ]
}]


def load_cleanup_policy():
    """
    Load Harbor cleanup policy from .harbor_cleanup_policy.yaml file or return default policies
    """
    # Check if .harbor_cleanup_policy.yaml file exists
    if os.path.exists(".harbor_cleanup_policy.yaml"):
        with open(".harbor_cleanup_policy.yaml", "r") as f:
            cleanup_policy = yaml.safe_load(f)
        # Check if policies key exists in cleanup_policy dict
        if "policies" in cleanup_policy:
            return cleanup_policy["policies"]
    # Return default policies if file doesn't exist or policies key is missing
    return DEFAULT_POLICIES


def validate_rule(rule):
    """
    Validate that rule has the required fields
    """
    if "rule" not in rule:
        raise ValueError("Missing 'rule' field in rule")
    if rule["rule"] not in ["SaveLastNTags", "DeleteOlderThan", "SaveLastNProdTags", "SaveLastNStagingTags",
                            "SaveLastNFeatureTags", "IgnoreTags"]:
        raise ValueError(f"The rule {rule['rule']} is wrong")
    if rule["rule"] == "DeleteOlderThan" and "days" not in rule:
        raise ValueError("Missing 'days' field in rule")
    if rule["rule"] == "SaveLastNProdTags" and "regexp" not in rule:
        raise ValueError("Missing 'regexp' field in rule")
    if rule["rule"] == "SaveLastNProdTags" and "limit" not in rule:
        rule["limit"] = next(
            (d['limit'] for d in DEFAULT_POLICIES[0]["rules"] if 'SaveLastNProdTags' in d.get('rule', '')))
    if rule["rule"] == "SaveLastNProdTags" and rule["limit"] < 1:
        raise ValueError("Missing 'limit' field in rule should be more then 1")
    if rule["rule"] == "SaveLastNStagingTags" and "regexp" not in rule:
        raise ValueError("Missing 'regexp' field in rule")
    if rule["rule"] == "SaveLastNStagingTags" and "limit" not in rule:
        rule["limit"] = next(
            (d['limit'] for d in DEFAULT_POLICIES[0]["rules"] if 'SaveLastNStagingTags' in d.get('rule', '')))
    if rule["rule"] == "SaveLastNStagingTags" and rule["limit"] < 1:
        raise ValueError("Missing 'limit' field in rule should be more then 1")
    if rule["rule"] == "SaveLastNFeatureTags" and "limit" not in rule:
        raise ValueError("Missing 'limit' field in rule")
    if rule["rule"] == "IgnoreTags" and "tags" not in rule:
        raise ValueError("Missing 'tags' field in rule")
    if "limit" in rule and not isinstance(rule["limit"], int):
        raise ValueError("'limit' field in rule must be an integer")
    if "days" in rule and not isinstance(rule["days"], int):
        raise ValueError("'days' field in rule must be an integer")


def validate_policy(policy):
    """
    Validate that policy has the required fields
    """
    if "name" not in policy:
        raise ValueError("Missing 'name' field in policy")
    if "rules" not in policy:
        raise ValueError("Missing 'rules' field in policy")
    for rule in policy["rules"]:
        validate_rule(rule)


def merge_policies(policies):
    # Merge policies with default policies
    for policy in policies:
        for default_policy in DEFAULT_POLICIES[0]['rules']:
            if default_policy['rule'] not in [p['rule'] for p in policy['rules']]:
                policy['rules'].append(default_policy)

    return policies[0]


def get_field_from_rule(policy, rule, field):
    return next(
        (d[f'{field}'] for d in policy["rules"] if rule in d.get('rule', '')))
