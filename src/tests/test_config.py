import pytest

from config import *


def test_create_file_with_policy():
    # Create .harbor_cleanup_policy.yaml file
    with open(".harbor_cleanup_policy.yaml", "w") as f:
        f.write("""policies:
- name: Test Policy
  rules:
    - rule: DeleteOlderThan
      days: 14
    - rule: SaveLastNProdTags
      regexp: '^v\d+\.\d+\.\d+$'
      limit: 10
    - rule: SaveLastNStagingTags
      regexp: '^v\d+\.\d+\.\d+.+'
      limit: 10
    - rule: SaveLastNFeatureTags
      limit: 10
""")

    assert load_cleanup_policy() == [{
        'name': 'Test Policy',
        'rules': [
            {'rule': 'DeleteOlderThan', 'days': 14},
            {'rule': 'SaveLastNProdTags', 'regexp': '^v\\d+\\.\\d+\\.\\d+$', 'limit': 10},
            {'rule': 'SaveLastNStagingTags', 'regexp': '^v\\d+\\.\\d+\\.\\d+.+', 'limit': 10},
            {'rule': 'SaveLastNFeatureTags', 'limit': 10}
        ]
    }]

    # Remove .harbor_cleanup_policy.yaml file
    os.remove(".harbor_cleanup_policy.yaml")


def test_default_policy_if_file_doesnt_exist():
    # Test default policy if file doesn't exist
    assert load_cleanup_policy() == DEFAULT_POLICIES


def test_validate_rule_save_last_n_prod_tags():
    # Test valid rule
    rule = {'rule': 'SaveLastNProdTags', 'regexp': '^v\\d+\\.\\d+\\.\\d+$', 'limit': 5}
    assert validate_rule(rule) == None


def test_invalid_rule_with_missing_rule_field():
    # Test invalid rule - missing rule field
    rule = {'regexp': '^v\\d+\\.\\d+\\.\\d+$', 'limit': 5}
    with pytest.raises(ValueError):
        validate_rule(rule)


def test_invalid_rule_wrong_rule_field():
    # Test invalid rule - wrong rule field
    rule = {'rule': 'WrongRule', 'regexp': '^v\\d+\\.\\d+\\.\\d+$', 'limit': 5}
    with pytest.raises(ValueError):
        validate_rule(rule)


def test_invalid_rule_with_missing_days_field():
    # Test invalid rule - missing days field in DeleteOlderThan rule
    rule = {'rule': 'DeleteOlderThan'}
    with pytest.raises(ValueError):
        validate_rule(rule)


def test_invalid_rule_with_missing_regexp_field():
    # Test invalid rule - missing regexp field in SaveLastNProdTags rule
    rule = {'rule': 'SaveLastNProdTags', 'limit': 5}
    with pytest.raises(ValueError):
        validate_rule(rule)


def test_invalid_rule_with_missing_limit_field():
    # Test invalid rule - missing limit field in SaveLastNProdTags rule
    rule = {'rule': 'SaveLastNProdTags', 'regexp': '^v\\d+\\.\\d+\\.\\d+$'}
    assert validate_rule(rule) == None


def test_validate_policy_missing_name():
    with pytest.raises(ValueError, match="Missing 'name' field in policy"):
        validate_policy({"rules": []})


def test_validate_policy_missing_rules():
    with pytest.raises(ValueError, match="Missing 'rules' field in policy"):
        validate_policy({"name": "policy name"})


def test_merge_policies():
    policy = [{
        'name': 'Test Policy',
        'rules': [
            {'rule': 'DeleteOlderThan', 'days': 14},
            {'rule': 'SaveLastNProdTags', 'regexp': '^v\\d+\\.\\d+\\.\\d+$', 'limit': 5},
            {'rule': 'SaveLastNStagingTags', 'regexp': '^v\\d+\\.\\d+\\.\\d+.+', 'limit': 10},
            {'rule': 'SaveLastNFeatureTags', 'limit': 10}
        ]
    }]
    expected_policy = {
        'name': 'Test Policy',
        'rules': [
            {'rule': 'DeleteOlderThan', 'days': 14},
            {'rule': 'SaveLastNProdTags', 'regexp': '^v\\d+\\.\\d+\\.\\d+$', 'limit': 5},
            {'rule': 'SaveLastNStagingTags', 'regexp': '^v\\d+\\.\\d+\\.\\d+.+', 'limit': 10},
            {'rule': 'SaveLastNFeatureTags', 'limit': 10},
            {'rule': 'IgnoreTags', 'tags': []}
        ]
    }
    t = merge_policies(policy)
    assert merge_policies(policy) == expected_policy


def test_get_field_from_rule():
    policy = {"name": "policy1",
              "rules": [{"rule": "rule1", "field1": "value1"}, {"rule": "rule2", "field1": "value2"}]}
    assert get_field_from_rule(policy, "rule1", "field1") == "value1"
    assert get_field_from_rule(policy, "rule2", "field1") == "value2"
    with pytest.raises(StopIteration):
        get_field_from_rule(policy, "rule3", "field1")
