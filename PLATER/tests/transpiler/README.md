# Testing reasoner-transpiler

### Content

* [`test_casing.py`](test_casing.py):

  We test the utilities for converting between space case, snake_case, and PascalCase.

* [`test_compounds.py`](test_compounds.py):

  We test transpiling "compound" query graphs that use AND, OR, XOR, and NOT.

* [`test_cypher_expression.py`](test_cypher_expression.py):

  We test the utility for converting Python objects into cypher expressions.

* [`test_edge_cases.py`](test_edge_cases.py):

  We test transpiling various "edge" cases including query graphs with null-valued properties.

* [`test_graph_formats.py`](test_graph_formats.py):

  We test some miscellaneous query graph structures including id/predicate lists.

* [`test_invalid.py`](test_invalid.py):

  We test transpiling several types of invalid query graphs, including those with nonsensical numbers of logical operands (e.g. two operands for NOT).

* [`test_predicates.py`](test_predicates.py):

  We test that edge predicates are handled correctly, including symmetric, invertible, and missing predicates.

* [`test_props.py`](test_props.py):

  We test that query node/edge property constraints are correctly handled, and that knowledge graph node/edge properties are correctly surfaced.

* [`test_query_args.py`](test_query_args.py):

  We test that the transpiler arguments behave correctly, including skip/limit and max_connectivity.

### Workflow

Tests are run automatically via GitHub Actions on each pull request and each push to the `main` branch.
