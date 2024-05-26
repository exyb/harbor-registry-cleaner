import yaml
import os

# Default policies
DEFAULT_POLICIES = [{
    'name': 'Default Policy',
    'rules': [
        {'type': 'DeleteByTimeInName', 'regexp': r'^.*$', 'limit': 100 },
        {'type': 'DeleteByCreateTime', 'days': 31},
        {'type': 'DeleteByTagName', 'regexp': r'^.*$', 'limit': 100},
        {'type': 'IgnoreTags', 'tags': []}
    ]
}]


def load_cleanup_policy():
    """
    Load Harbor cleanup policy from harbor_cleanup_policy.yaml file or return default policies
    """
    # Check if .harbor_cleanup_policy.yaml file exists
    if os.path.exists("harbor_cleanup_policy.yaml"):
        with open("harbor_cleanup_policy.yaml", "r") as f:
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
    if "type" not in rule:
        raise ValueError("Missing 'type' field in rule")

    if rule["type"] not in ["DeleteByTimeInName", "DeleteByTagName", "DeleteByCreateTime", "IgnoreRepos", "IgnoreTags"]:
        raise ValueError(f"The rule {rule['rule']} is wrong")

    if rule["type"] in ["DeleteByCreateTime"] and "days" not in rule:
        raise ValueError("Missing 'days' field in rule")

    if rule["type"] in ["DeleteByTimeInName", "DeleteByTagName", "DeleteByCreateTime",] and "regexp" not in rule:
        raise ValueError(f"Missing 'regexp' field in rule {rule[type]}")

    if rule["type"] in ["DeleteByTimeInName", "DeleteByTagName"] and rule["limit"] < 1:
        raise ValueError(f"Missing 'limit' field in rule {rule[type]} should be more then 1")

    if rule["type"] in ["DeleteByTimeInName", "DeleteByTagName"] and "limit" not in rule:
        rule["limit"] = next(
            (d['limit'] for d in DEFAULT_POLICIES[0]["rules"] if 'DeleteByTagName' in d.get('rule', '')))

    if rule["type"] == "IgnoreTags" and "tags" not in rule:
        raise ValueError(f"Missing 'tags' field in rule {rule[type]}")

    if rule["type"] == "IgnoreRepos" and "repos" not in rule:
        raise ValueError(f"Missing 'repos' field in rule {rule[type]}")

    if "limit" in rule and not isinstance(rule["limit"], int):
        raise ValueError(f"'limit' field in rule {rule[type]} must be an integer")

    if "days" in rule and not isinstance(rule["days"], int):
        raise ValueError(f"'days' field in rule {rule[type]} must be an integer")


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

def get_one_rule_by_type(rules, type):
    for rule in rules:
        if rule['type'] == type:
            return rule
    return

def merge_policies(policies, args):
    # Merge policies with default policies
    for policy in policies:
        for default_policy in DEFAULT_POLICIES[0]['rules']:
            if default_policy['type'] not in [p['type'] for p in policy['rules']]:
                policy['rules'].append(default_policy)
    # Merge policies with args
    for policy in policies:
        if args.ignore_repos and 'IgnoreRepos' in [p['type'] for p in policy['rules']]:
            for rule in policy['rules']:
                if rule['type'] == 'IgnoreRepos':
                    rule['repos'].extend(args.ignore_repos)
        if args.ignore_tags and 'IgnoreTags' in [p['type'] for p in policy['rules']]:
            for rule in policy['rules']:
                if rule['type'] == 'IgnoreTags':
                    rule['tags'].extend(args.ignore_tags)
    return policies


def get_field_from_rule(policy, rule, field):
    return next(
        (d[f'{field}'] for d in policy["rules"] if rule in d.get('rule', '')))
