"""Query nesting tools."""
from functools import reduce
from operator import and_, or_


class Query():
    """Cypher query segment."""

    def __init__(
            self,
            string,
            qids=None,
            references=None,
            qgraph=None,
    ):
        """Initialize."""
        self._string = string
        self._qids = qids
        self._references = references
        self._qgraph = qgraph

    @property
    def qgraph(self):
        """Get qgraph."""
        return self._qgraph

    def logic(self, simple=True):
        """Return whether qid is required."""
        if simple:
            return ""
        conditions = [
            f"{qid} IS NOT null" for qid in self.qids
        ]
        if len(self.qids) > 1:
            conditions = [
                f"({condition})" for condition in conditions
            ]
        return " AND ".join(conditions)

    def compile(self, **kwargs):
        """Wrap hidden _compile method."""
        context = kwargs.get("context", set())
        ext_context = kwargs.get("ext_context", set())

        clauses = []
        imports = ext_context & self.references
        if imports:
            clauses.append("WITH " + ", ".join(imports))
        context = context | ext_context
        kwargs.pop("ext_context", None)
        kwargs["context"] = context

        return_ = kwargs.pop("return_", False)
        wrap = kwargs.pop("wrap", False)

        optional = kwargs.get("optional", False)
        extension = kwargs.pop("extension", [])

        if optional and not isinstance(self, CompoundQuery):
            if len(self.references) >= 5:
                # there are probably at least two edges here
                wrap = True
                kwargs.update(
                    optional=False,
                    extension=[(
                        "WITH CASE WHEN count(*) > 0 "
                        + "THEN collect([{0}]) ".format(
                            ", ".join(self.qids - context)
                        )
                        + "ELSE [[]] "
                        + "END AS results "
                        + "UNWIND results as result "
                        + "WITH {0}".format(", ".join(
                            f"result[{idx}] AS {qid}"
                            for idx, qid in enumerate(self.qids - context)
                        ))
                    )],
                )
            else:
                clauses.append("OPTIONAL")

        if wrap:
            clauses.extend(self._compile_wrapped(**kwargs))
        else:
            clauses.extend(self._compile(**kwargs))

        clauses.extend(extension)

        if return_:
            clauses.append(self.return_clause(**kwargs))

        return clauses

    def _compile_wrapped(self, **kwargs):
        """Compile wrapped query."""
        context = kwargs.pop("context", set())
        inner_context = context & self.references
        return [
            "CALL {{{query}}}".format(
                query=(
                    " ".join(self.compile(
                        ext_context=inner_context,
                        return_=True,
                        **kwargs,
                    ))
                    .replace("\\", "\\\\")
                ),
            ),
        ]

    def _compile(self, **kwargs):  # pylint: disable=unused-argument
        """Return query string."""
        return [self._string] if self._string else []

    @property
    def references(self):
        """Get references."""
        return self._references

    @property
    def qids(self):
        """Get qids."""
        return self._qids

    def where_clause(self):
        """Get WHERE clause."""
        conditions = self.logic()
        return conditions and "WHERE " + conditions

    def with_clause(self, **kwargs):
        """Get WITH clause."""
        context = kwargs.get("context", set())
        return "WITH " + ", ".join(self.qids | context)

    def return_clause(self, **kwargs):
        """Get RETURN clause."""
        context = kwargs.get("context", set())
        return "RETURN " + ", ".join(self.qids - context)

    def __and__(self, other):
        """AND two queries together."""
        return AndQuery(self, other)

    def __invert__(self):
        """NOT query."""
        return NotQuery(self)

    def __or__(self, other):
        """OR queries."""
        return OrQuery(self, other)

    def __xor__(self, other):
        """XOR queries."""
        return XorQuery(self, other)


class CompoundQuery(Query):
    """Compound query."""

    def __init__(self, *subqueries):  # pylint: disable=super-init-not-called
        """Initialize."""
        self.subqueries = subqueries

    @property
    def qids(self):
        """Get qids."""
        return reduce(
            or_,
            [subquery.qids for subquery in self.subqueries]
        )

    @property
    def qgraph(self):
        """Get qgraph."""
        qnodes = dict()
        qedges = dict()
        for subquery in self.subqueries:
            qnodes.update(subquery.qgraph["nodes"])
            qedges.update(subquery.qgraph["edges"])
        return {
            "nodes": qnodes,
            "edges": qedges,
        }

    @property
    def references(self):
        """Get references."""
        return reduce(
            or_,
            (query.references for query in self.subqueries),
        )


class AndQuery(CompoundQuery):
    """Compound query segment."""

    def _compile(self, **kwargs):
        """Get query string."""
        context = kwargs.pop("context", set())
        subquery_strings = []
        for query in self.subqueries:
            subquery_strings.extend(query.compile(context=context, **kwargs))
            context = context | query.qids

        return subquery_strings

    def logic(self, simple=True):
        """Return whether qid is required."""
        conditions = [
            query.logic(simple) for query in self.subqueries
            if query.logic(simple)
        ]
        if len(conditions) > 1:
            conditions = [
                f"({condition})" for condition in conditions
            ]
        return " AND ".join(conditions)


class NotQuery(CompoundQuery):
    """Not query segment."""

    def _compile(self, **kwargs):
        """Return query string."""
        kwargs.update(optional=True)
        return self.subqueries[0].compile(**kwargs)

    def logic(self, simple=True):
        """Return whether qid is required."""
        return f"NOT ({self.subqueries[0].logic(False)})"


class AltQuery(CompoundQuery):
    """Alternative query.

    Superclass for OrQuery and XorQuery.
    """

    def __init__(self, *args):
        """Initialize."""
        assert len(args) == 2
        super().__init__(*args)

    def _compile(self, **kwargs):
        """Get query string."""
        kwargs.update(optional=True)
        if self.subqueries[0].qids & self.subqueries[1].qids:
            return self._compile_union(**kwargs, return_=True)
        else:
            query = AndQuery(self.subqueries[0], self.subqueries[1])
            return query.compile(**kwargs)

    def _compile_union(self, **kwargs):
        """Get query string."""
        query0 = AndQuery(self.subqueries[0], self.subqueries[1])
        query1 = AndQuery(self.subqueries[1], self.subqueries[0])

        query = UnionQuery(query0, query1)
        return query.compile(wrap=True, **kwargs)


class UnionQuery(CompoundQuery):
    """UNION query."""

    def __init__(self, *args, **kwargs):
        """Initialize."""
        super().__init__(*args, **kwargs)
        self.return_ = None
        self.ext_context = None

    def compile(self, **kwargs):
        """Return query string."""
        assert kwargs.get("return_", False)

        # save these things and later pass them, unmodified, to subqueries
        self.return_ = kwargs.pop("return_", set())
        self.ext_context = kwargs.pop("ext_context", set())

        return super().compile(**kwargs)

    def _compile(self, **kwargs):
        """Return query string."""
        kwargs.update(
            ext_context=self.ext_context,
            return_=self.return_,
        )

        return [" UNION ".join(
            " ".join(subquery.compile(
                **kwargs,
            ))
            for subquery in self.subqueries
        )]


class OrQuery(AltQuery):
    """OR query."""

    def logic(self, simple=True):
        """Get conditions."""
        return " OR ".join(
            f"({query.logic(False)})" for query in self.subqueries
        )


class XorQuery(AltQuery):
    """XOR query."""

    def logic(self, simple=True):
        """Get conditions."""
        return " XOR ".join(
            f"({query.logic(False)})" for query in self.subqueries
        )
