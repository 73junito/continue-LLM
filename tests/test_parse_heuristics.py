import pytest
from autolearnpro_agent import server


@pytest.mark.parametrize(
    "text,expected_ok,expected_value",
    [
        ('{"a": 1}', True, {"a": 1}),
        ('  [1, 2, 3]  ', True, [1, 2, 3]),
        ('prefix text {"k":"v"} suffix', True, {"k": "v"}),
        ('not json at all', False, 'not json at all'),
        ('', False, ''),
    ],
)
def test_try_parse_json_like_cases(text, expected_ok, expected_value):
    ok, val = server._try_parse_json_like(text)
    assert ok == expected_ok
    if ok:
        assert val == expected_value
    else:
        assert val == expected_value
