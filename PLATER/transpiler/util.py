"""Utilities."""
import re
from typing import List, Union, overload


def _space_case(arg: str):
    """Convert string to space case.

    "ThisCase" is replaced with "this case".
    """
    # replace "_" with " "
    tmp = re.sub("_", " ", arg)
    # replace "xYz" with "x yz"
    tmp = re.sub(
        r"(?<=[a-z])(?=[A-Z][a-z])",
        " ",
        tmp
    )
    # lower-case everything
    return tmp.lower()


def _snake_case(arg: str):
    """Convert string to snake_case.

    "ThisCase" is replaced with "this_case".
    """
    # replace " " with "_"
    tmp = re.sub(
        " ", "_", arg,
    )
    # replace xYz with x_Yz
    tmp = re.sub(
        r"(?<=[a-z])(?=[A-Z][a-z])",
        "_",
        tmp
    )
    # lower-case everything
    return tmp.lower()


def _pascal_case(arg: str):
    """Convert string to PascalCase.

    "this_case" is replaced with "ThisCase".
    """
    # replace "_x" or " x" with "X"
    tmp = re.sub(
        r"(?<=[a-zA-Z])[ _]([a-z])",
        lambda c: c.group(1).upper(),
        arg
    )
    # upper-case first character
    tmp = re.sub(
        r"^[a-z]",
        lambda c: c.group(0).upper(),
        tmp
    )
    return tmp


@overload
def space_case(arg: str) -> str:
    """Convert a string to space case."""


@overload
def space_case(arg: List[str]) -> List[str]:
    """Convert a set of strings to space case."""


def space_case(arg: Union[str, List[str]]) -> Union[str, List[str]]:
    """Convert a string or set of strings to space case."""
    if isinstance(arg, str):
        return _space_case(arg)
    elif isinstance(arg, list):
        return [_space_case(arg) for arg in arg]
    else:
        raise ValueError()


def snake_case(arg: Union[str, List[str]]):
    """Convert each string or set of strings to snake_case."""
    if isinstance(arg, str):
        return _snake_case(arg)
    elif isinstance(arg, list):
        return [_snake_case(arg) for arg in arg]
    else:
        raise ValueError()


def pascal_case(arg: Union[str, List[str]]):
    """Convert each string or set of strings to PascalCase."""
    if isinstance(arg, str):
        return _pascal_case(arg)
    elif isinstance(arg, list):
        return [_pascal_case(arg) for arg in arg]
    else:
        raise ValueError()


def ensure_list(arg: Union[str, List[str]]) -> List[str]:
    """Convert scalar arg to a list of one."""
    if isinstance(arg, list):
        return arg
    return [arg]
