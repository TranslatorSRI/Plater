"""Test casing."""
import pytest

from PLATER.transpiler.util import pascal_case, snake_case, space_case


def test_space():
    """Test conversion to space case."""
    assert space_case("ChemicalSubstance") == "chemical substance"
    assert space_case([
        "ChemicalSubstance",
        "biological_process"
    ]) == [
        "chemical substance",
        "biological process",
    ]
    with pytest.raises(ValueError):
        space_case({"a": "ChemicalSubstance"})


def test_snake():
    """Test conversion to snake_case."""
    assert snake_case("ChemicalSubstance") == "chemical_substance"
    assert snake_case([
        "ChemicalSubstance",
        "Biological Process"
    ]) == [
        "chemical_substance",
        "biological_process",
    ]
    with pytest.raises(ValueError):
        snake_case({"a": "ChemicalSubstance"})


def test_pascal():
    """Test conversion to PascalCase."""
    assert pascal_case("chemical_substance") == "ChemicalSubstance"
    assert pascal_case([
        "chemical_substance",
        "biological process",
    ]) == [
        "ChemicalSubstance",
        "BiologicalProcess"
    ]
    with pytest.raises(ValueError):
        pascal_case({"a": "ChemicalSubstance"})
