import re


def regexp_match(exp: str, string: str) -> bool:
    return bool(re.match(exp, string))


def extract_semver(tag: str) -> str:
    match = re.search(r'\w+_\d+(?:_\w+)?', tag)
    if match:
        return match.group(0)
    return ""
