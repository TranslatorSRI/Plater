"""Test Python obj -> cypher expression encoding."""
from PLATER.transpiler.cypher_expression import dumps


def test_types():
    """Test various Python types."""
    # number
    assert dumps(1.2) == "1.2"
    # string
    assert dumps("hello") == "\"hello\""
    # list
    assert dumps(["hello", 1.2]) == "[\"hello\", 1.2]"
    # boolean
    assert dumps(True) == "true"
    # None
    assert dumps(None) == "null"
    # dict
    assert dumps({
        "a": 1,
        "b": False,
    }) == "{a: 1, b: false}"
