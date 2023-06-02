from utils import regexp_match, extract_semver


def test_regexp_match():
    assert regexp_match(r'^\d{3}$', '123') == True
    assert regexp_match(r'^\d{3}$', '12a') == False
    assert regexp_match(r'^[a-z]+$', 'hello') == True
    assert regexp_match(r'^[a-z]+$', 'Hello') == False


def test_extract_semver():
    assert extract_semver('v1.2.3') == '1.2.3'
    assert extract_semver('version-1.2.3') == '1.2.3'
    assert extract_semver('2.0') == ''
    assert extract_semver('1.2.3-beta.1') == '1.2.3'
