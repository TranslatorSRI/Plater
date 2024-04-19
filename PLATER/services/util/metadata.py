import os
import json
from PLATER.services.config import config


class GraphMetadata:

    def __init__(self):
        self.metadata = None
        self.meta_kg = None
        self.sri_testing_data = None
        self.full_simple_spec = None

    def get_metadata(self):
        if self.metadata is None:
            self.retrieve_metadata()
        return self.metadata

    def retrieve_metadata(self):
        with open(os.path.join(os.path.dirname(__file__), '..', '..', 'metadata', 'metadata.json')) as f:
            self.metadata = json.load(f)

        if not self.metadata:
            with open(os.path.join(os.path.dirname(__file__), '..', '..', 'metadata', 'about.json')) as f:
                self.metadata = json.load(f)

    def get_meta_kg(self):
        if self.meta_kg is None:
            self.retrieve_meta_kg()
        return self.meta_kg

    def retrieve_meta_kg(self):
        with open(os.path.join(os.path.dirname(__file__), '..', '..', 'metadata', 'meta_knowledge_graph.json')) as f:
            self.meta_kg = json.load(f)

        try:
            # We removed pydantic model conversion during a response for the meta kg for performance reasons,
            # instead it is validated once on startup. This attempts to populate some optional but preferred
            # fields that may not be coming from upstream tools.
            for node_type, node_properties in self.meta_kg['nodes'].items():
                for attribute_info in node_properties['attributes']:
                    if 'attribute_source' not in attribute_info:
                        attribute_info['attribute_source'] = None
                    if 'constraint_use' not in attribute_info:
                        attribute_info['constraint_use'] = False
                    if 'constraint_name' not in attribute_info:
                        attribute_info['constraint_name'] = None
        except KeyError as e:
            # just move on if a key is missing here, it won't validate but don't crash the rest of the app
            pass

    def get_sri_testing_data(self):
        if self.sri_testing_data is None:
            self.retrieve_sri_test_data()
        return self.sri_testing_data

    def retrieve_sri_test_data(self):
        with open(os.path.join(os.path.dirname(__file__), '..', '..', 'metadata', 'sri_testing_data.json')) as f:
            self.sri_testing_data = json.load(f)

        # version is technically not part of the spec anymore
        # but this ensures validation with the model until it's removed
        if 'version' not in self.sri_testing_data:
            self.sri_testing_data['version'] = config.get('BL_VERSION')

    def get_full_simple_spec(self):
        if self.meta_kg is None:
            self.retrieve_meta_kg()
        if self.full_simple_spec is None:
            self.generate_full_simple_spec()
        return self.full_simple_spec

    def generate_full_simple_spec(self):
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
