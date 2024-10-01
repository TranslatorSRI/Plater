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

        def __init__(self):
            self.metadata = None
            self._retrieve_metadata()
            self.meta_kg = None
            self.meta_kg_response = None
            self.predicates_in_graph = set()
            self._retrieve_meta_kg()
            self.sri_testing_data = None
            self._retrieve_sri_test_data()
            self.full_simple_spec = None
            self._generate_full_simple_spec()

        def get_metadata(self):
            return self.metadata

        def _retrieve_metadata(self):
            with open(os.path.join(os.path.dirname(__file__), '..', '..', 'metadata', 'metadata.json')) as f:
                self.metadata = json.load(f)

            if not self.metadata:
                with open(os.path.join(os.path.dirname(__file__), '..', '..', 'metadata', 'about.json')) as f:
                    self.metadata = json.load(f)

        def get_meta_kg(self):
            return self.meta_kg

        def get_meta_kg_response(self):
            return self.meta_kg_response

        def _retrieve_meta_kg(self):
            with open(os.path.join(os.path.dirname(__file__), '..', '..', 'metadata', 'meta_knowledge_graph.json')) as f:
                self.meta_kg = json.load(f)
                try:
                    # validate the meta kg with the pydantic model
                    MetaKnowledgeGraph.parse_obj(self.meta_kg)
                    logger.info('Successfully validated meta kg')

                    for edge in self.meta_kg['edges']:
                        self.predicates_in_graph.add(edge['predicate'])

                    # create an already-encoded object that is ready to be returned quickly
                    self.meta_kg_response = jsonable_encoder(self.meta_kg)
                except ValidationError as e:
                    logger.error(f'Error validating meta kg: {e}')

        def get_sri_testing_data(self):
            return self.sri_testing_data

        def _retrieve_sri_test_data(self):
            with open(os.path.join(os.path.dirname(__file__), '..', '..', 'metadata', 'sri_testing_data.json')) as f:
                self.sri_testing_data = json.load(f)

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
