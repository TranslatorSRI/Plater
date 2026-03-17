import os
import json

from pydantic import ValidationError
from fastapi.encoders import jsonable_encoder

from PLATER.services.config import config
from PLATER.models.shared import MetaKnowledgeGraph
from PLATER.services.util.logutil import LoggingUtil

logger = LoggingUtil.init_logging(
    __name__,
    config.get('logging_level'),
    config.get('logging_format'),
)


class GraphMetadata:
    """
    Singleton class for retrieving metadata
    """

    class _GraphMetadata:

        METADATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'metadata')

        # Attempt to load a json file from the METADATA_DIR but return default as the content otherwise
        @staticmethod
        def _load_json(filename, default):
            filepath = os.path.join(GraphMetadata._GraphMetadata.METADATA_DIR, filename)
            try:
                with open(filepath) as f:
                    data = json.load(f)
                    if data:
                        return data
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logger.warning(f'Could not load {filename}: {e}, using default')
            return default

        def __init__(self):
            self.metadata = None
            self._retrieve_metadata()
            self.graph_metadata = None
            self._retrieve_graph_metadata()
            self.schema = None
            self._retrieve_schema()
            self.meta_kg = None
            self.meta_kg_response = None
            self.predicates_in_graph = set()
            self.node_categories_in_graph = set()
            self._retrieve_meta_kg()
            self.sri_testing_data = None
            self._retrieve_sri_test_data()
            self.full_simple_spec = None
            self._generate_full_simple_spec()

        def get_metadata(self):
            return self.metadata

        def _retrieve_metadata(self):
            self.metadata = self._load_json('metadata.json', {})

        def get_graph_metadata(self):
            return self.graph_metadata

        def _retrieve_graph_metadata(self):
            self.graph_metadata = self._load_json('graph_metadata.json', {})

        def get_schema(self):
            return self.schema

        def _retrieve_schema(self):
            self.schema = self._load_json('schema.json', {})

        def get_meta_kg(self):
            return self.meta_kg

        def get_meta_kg_response(self):
            return self.meta_kg_response

        def _retrieve_meta_kg(self):
            self.meta_kg = self._load_json('meta_knowledge_graph.json', {"nodes": {}, "edges": []})
            try:
                # validate the meta kg with the pydantic model
                MetaKnowledgeGraph.parse_obj(self.meta_kg)
                logger.info('Successfully validated meta kg')

                self.node_categories_in_graph = set(self.meta_kg['nodes'].keys())
                logger.info(f'Used meta kg to determine node categories in graph: {self.node_categories_in_graph}')

                for edge in self.meta_kg['edges']:
                    self.predicates_in_graph.add(edge['predicate'])
                logger.info(f'Used meta kg to determine predicates in graph: {self.predicates_in_graph}')

                # create an already-encoded object that is ready to be returned quickly
                self.meta_kg_response = jsonable_encoder(self.meta_kg)
            except ValidationError as e:
                logger.error(f'Error validating meta kg: {e}')

        def get_sri_testing_data(self):
            return self.sri_testing_data

        def _retrieve_sri_test_data(self):
            self.sri_testing_data = self._load_json('sri_testing_data.json', {
                "version": "",
                "source_type": "primary",
                "edges": [],
            })

            # version is technically not part of the spec anymore
            # but this ensures validation with the model until it's removed
            if 'version' not in self.sri_testing_data:
                self.sri_testing_data['version'] = config.get('BL_VERSION')

        def get_full_simple_spec(self):
            return self.full_simple_spec

        def _generate_full_simple_spec(self):
            self.full_simple_spec = []
            for edge in self.meta_kg.get('edges', []):
                self.full_simple_spec.append({
                    "source_type": edge["subject"],
                    "target_type": edge["object"],
                    "edge_type": edge["predicate"]
                })

        def get_example_qgraph(self):
            sri_test_data = self.get_sri_testing_data()
            if not sri_test_data['edges']:
                return {'error': 'Could not generate example without edges in sri_testing_data.'}
            test_edge = sri_test_data['edges'][0]
            example_trapi = {
                "message": {
                    "query_graph": {
                        "nodes": {
                            "n0": {
                                "categories": [
                                    test_edge['subject_category']
                                ],
                                "ids": [
                                    test_edge['subject_id']
                                ]
                            },
                            "n1": {
                                "categories": [
                                    test_edge['object_category']
                                ],
                                "ids": [
                                    test_edge['object_id']
                                ]
                            }
                        },
                        "edges": {
                            "e01": {
                                "subject": "n0",
                                "object": "n1",
                                "predicates": [
                                    test_edge['predicate']
                                ]
                            }
                        }
                    }
                },
                "workflow": [
                    {
                        "id": "lookup"
                    }
                ]
            }
            return example_trapi

    def get_example_edge(self):
        example_edge = {"subject_id": "EXAMPLE:1",
                        "subject_category": "biolink:NamedThing",
                        "predicate": "biolink:related_to",
                        "object_id": "EXAMPLE:2",
                        "object_category": "biolink:NamedThing"}
        sri_test_data = self.get_sri_testing_data()
        if not sri_test_data["edges"]:
            return example_edge
        for edge in sri_test_data["edges"]:
            example_edge = edge
            if example_edge["predicate"] == "biolink:subclass_of":
                continue
            else:
                break
        return example_edge

    # the following code implements a singleton pattern so that only one metadata object is ever created
    instance = None

    def __init__(self):
        # create a new instance if not already created.
        if not GraphMetadata.instance:
            GraphMetadata.instance = GraphMetadata._GraphMetadata()

    def __getattr__(self, item):
        # proxy function calls to the inner object.
        return getattr(self.instance, item)


def get_graph_metadata():
    return GraphMetadata()
