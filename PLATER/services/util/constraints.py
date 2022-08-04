import collections
from collections.abc import Iterable
from reasoner_pydantic.qgraph import AttributeConstraint, Operator as OperatorModel
from reasoner_pydantic.shared import Attribute, HashableSequence
from typing import List
import re
import numbers



class Operator:
    """
    Base class for operators
    """

    def is_number(self, a):
        return isinstance(a, numbers.Number)

    def is_iterable(self, a):
        return isinstance(a, (collections.Iterable, collections.MutableSequence)) and not isinstance(a, str)

    def is_same_data_type(self, a, b):
        """
        returns true if python data types of a and b match
        :param a: any value
        :param b: any value
        :return: bool indicating if the data types match
        """
        return type(a) == type(b) \
               or (self.is_number(a) and self.is_number(b)) \
               or (self.is_iterable(a) and self.is_iterable(b))

    def __call__(self, a, b):
        pass


class EqualToOperator(Operator):
    def __call__(self, a, b):
        """
        Compares equivalence for primitive data types (strings , numbers , booleans).
        For iterables if any elements in a exist in be this operator returns true.
        :param a: Constraint value
        :param b: DB value
        :return: Equivlence
        """
        if not self.is_same_data_type(a, b):
            return False
        if isinstance(a, Iterable) and not isinstance(a, str):
            """
            If any element in b exists in a 
            """
            return any(x in a for x in b)
        else:
            return a == b


class DeepEqualToOperator(Operator):
    def __call__(self, a, b):
        """
        Does deep equivalence, of items.
        For Iterables order should also be equal.
        :param a: Constraint value
        :param b: DB value
        :return: Equivalence
        """
        if not self.is_same_data_type(a, b):
            return False
        return a == b


class MatchesOperator(Operator):
    def __call__(self, a, b):
        """
        For Iterables if any elements in a exists in b returns true.
        For strings parses a as regex expression and does matching.
        For other data types regular equivalence.
        :param a: Constrained Value. This is converted to regex for string types
        :param b: DB values
        :return: Equivalence
        """
        if not self.is_same_data_type(a, b):
            return False

        if isinstance(a, str):
            try:
                expr = re.compile(a)
                return bool(expr.match(b))
            except Exception:
                raise Exception
        if isinstance(a, Iterable):
            return any(x in a for x in b)
        return a == b


class GreaterThanOperator(Operator):
    def __call__(self, a, b):
        if not self.is_same_data_type(a, b):
            return False
        return a > b


class LessThanOperator(Operator):
    def __call__(self, a, b):
        if not self.is_same_data_type(a, b):
            return False
        return a < b


operator_map = {
    OperatorModel.equal_to: EqualToOperator(),
    OperatorModel.deep_equal_to: DeepEqualToOperator(),
    OperatorModel.greater_than: GreaterThanOperator(),
    OperatorModel.less_than: LessThanOperator(),
    OperatorModel.matches: MatchesOperator()
}


def check_attribute_constraint(attribute_constraint: AttributeConstraint, db_value):
    """
    Checks if a constraint is full filled for a value
    :param attribute_constraint: constraint
    :param db_value: value
    :return: boolean indicating if constraint is satisfied
    """
    op = operator_map[attribute_constraint.operator]
    constraint_val = attribute_constraint.value.__root__ if isinstance(attribute_constraint.value, HashableSequence) \
        else attribute_constraint.value
    result = op(constraint_val, db_value)
    # handle negation
    return result if not attribute_constraint.negated else not result


def check_attributes(attribute_constraints: List[AttributeConstraint], db_attributes: List[Attribute]):
    """
    Checks if all attribute constraints pass as True
    :param attribute_constraints: list of constraints
    :param db_attributes: attributes from db
    :return: boolean indicating if constrains are satisfied
    """
    for constraint in attribute_constraints:
        constraint_is_applied = False
        for db_attribute in db_attributes:
            if db_attribute.attribute_type_id == constraint.id:
                constraint_is_applied = True
                # if any constraint fails then no match , i.e `AND`ing constraints
                if not check_attribute_constraint(constraint, db_attribute.value):
                    return False
        # if constraint id doesn't exist in the list of attributes then no match
        if not constraint_is_applied:
            return False
    # All constraints are satisfied
    return True






