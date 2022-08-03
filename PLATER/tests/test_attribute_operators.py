from PLATER.services.util.constaints import *
from reasoner_pydantic.qgraph import AttributeConstraint


def test_match_operator():
    op = MatchesOperator()
    # Atleast one element matches
    assert op([1,2,3], [3,4,5])
    # matches booleans
    assert op(True, True)
    assert not op(True, False)
    # matches numbers
    assert op(1, 1.0)
    assert op(1, 1)
    assert not op(1, .1)
    # assert regex
    assert op('a*', 'abc')
    assert op('a', 'abc')
    assert op('', 'abc')
    assert op('[^a]', 'bcd')
    # data type mismatch
    assert not op(1, '1')
    assert not op('True', True)
    assert not op('a', ['a'])


def test_equal_operator():
    op = EqualToOperator()
    # Atleast one element matches
    assert op([1, 2, 3], [3, 4, 5])
    # matches booleans
    assert op(True, True)
    assert not op(True, False)
    # matches numbers
    # int vs int
    assert op(1, 1)
    # int vs float
    assert op(1, 1.0)
    assert not op(1, 0.1)
    # assert strings
    assert not op('a', 'abc')
    # data type mismatch
    assert not op(1, '1')
    assert not op('True', True)
    assert not op('a', ['a'])


def test_deep_equal_to():
    op = DeepEqualToOperator()
    # lists
    assert not op([1, 2, 3], [3, 4, 5])
    # order
    assert not op([1, 2, 3], [1, 3, 2])
    assert op([1, 2, 3], [1, 2, 3])
    # matches booleans
    assert op(True, True)
    assert not op(True, False)
    assert op(False , False)
    # matches numbers
    # int vs int
    assert op(1, 1)
    # int vs float
    assert op(1, 1.0)
    assert not op(1, 0.1)
    # assert strings
    assert not op('a', 'abc')
    assert op('ab!', 'ab!')
    # data type mismatch
    assert not op(1, '1')
    assert not op('True', True)
    assert not op('a', ['a'])


def test_lt_operator():
    op = LessThanOperator()
    # lists
    assert op([1, 2, 3], [3, 4, 5])
    assert not op([3, 4, 5], [1, 2, 3])
    # order
    assert op([1, 2, 3], [1, 3, 2])
    assert not op([3], [1, 2, 3])
    assert not op([1, 2, 3], [1, 2, 3])
    # matches booleans
    assert not op(True, True)
    assert not op(True, False)
    assert not op(False, False)
    assert op(False, True)
    # matches numbers
    # int vs int
    assert not op(1, 1)
    # int vs float
    assert not op(1, 1.0)
    assert not op(1, 0.1)
    assert op(0.1 , 1)
    # assert strings
    assert op('a', 'abc')
    assert not op('ab!', 'ab!')
    assert not op('z', 'abc')
    # data type mismatch
    assert not op(1, '1')
    assert not op('True', True)
    assert not op('a', ['a'])


def test_gt_operator():
    op = GreaterThanOperator()
    # lists
    assert not op([1, 2, 3], [3, 4, 5])
    assert op([3, 4, 5], [1, 2, 3])
    # order
    assert not op([1, 2, 3], [1, 3, 2])
    assert op([3], [1, 2, 3])
    assert not op([1, 2, 3], [1, 2, 3])
    # matches booleans
    assert not op(True, True)
    assert op(True, False)
    assert not op(False, False)
    assert not op(False, True)
    # matches numbers
    # int vs int
    assert not op(1, 1)
    # int vs float
    assert not op(1, 1.0)
    assert op(1, 0.1)
    assert not op(0.1, 1)
    # assert strings
    assert not op('a', 'abc')
    assert not op('ab!', 'ab!')
    assert op('z', 'abc')
    # data type mismatch
    assert not op(1, '1')
    assert not op('True', True)
    assert not op('a', ['a'])


def test_check_constraint():
    constraint = AttributeConstraint(**{
        'id': 'EDAM:data_0844',
        'operator': '==',
        'value': 2,
        'name': 'some constraint'
    })
    assert check_attribute_constraint(
        constraint, 2
    )
    constraint = AttributeConstraint(**{
        'id': 'EDAM:data_0844',
        'operator': 'matches',
        'value': 2,
        'name': 'some constraint'
    })
    assert check_attribute_constraint(
        constraint, 2
    )
    constraint = AttributeConstraint(**{
        'id': 'EDAM:data_0844',
        'operator': 'matches',
        'value': "a*",
        'name': 'some constraint'
    })
    assert check_attribute_constraint(
        constraint, "abcd"
    )
    constraint = AttributeConstraint(**{
        'id': 'EDAM:data_0844',
        'operator': '>',
        'value': 2,
        'name': 'some constraint'
    })
    assert check_attribute_constraint(
        constraint, 1
    )
    constraint = AttributeConstraint(**{
        'id': 'EDAM:data_0844',
        'operator': '<',
        'value': 2,
        'name': 'some constraint'
    })
    assert check_attribute_constraint(
        constraint, 3
    )
    constraint = AttributeConstraint(**{
        'id': 'EDAM:data_0844',
        'operator': '===',
        'value': ['a', 'b', 'c'],
        'name': 'some constraint'
    })
    negated_constraint = AttributeConstraint(**{
        'id': 'EDAM:data_0844',
        'operator': '===',
        'value': ['a', 'b', 'c'],
        'name': 'some constraint',
        'not': True
    })
    assert check_attribute_constraint(
        constraint, ['a', 'b', 'c']
    )
    assert check_attribute_constraint(
        negated_constraint, ['b', 'c', 'a']
    )
    # check equals
    constraint.operator = "=="
    negated_constraint.operator = "=="
    assert check_attribute_constraint(
        constraint, ['a']
    )

    assert not check_attribute_constraint(
        negated_constraint, ['c']
    )
    assert not check_attribute_constraint(
        negated_constraint, ['a']
    )