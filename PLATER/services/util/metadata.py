import os
import json
from PLATER.services.config import config


class GraphMetadata:

    def __init__(self):
        self.metadata = None
        self.meta_kg = None
        self.sri_testing_data = None

    def get_metadata(self):
        if not self.metadata:
            self.retrieve_metadata()
        return self.metadata

    def retrieve_metadata(self):
        with open(os.path.join(os.path.dirname(__file__), '..', '..', 'metadata', 'metadata.json')) as f:
            self.metadata = json.load(f)

        if not self.metadata:
            with open(os.path.join(os.path.dirname(__file__), '..', '..', 'metadata', 'about.json')) as f:
                self.metadata = json.load(f)

    def get_meta_kg(self):
        if not self.meta_kg:
            self.retrieve_meta_kg()
        return self.meta_kg

    def retrieve_meta_kg(self):
        with open(os.path.join(os.path.dirname(__file__), '..', '..', 'metadata', 'meta_knowledge_graph.json')) as f:
            self.meta_kg = json.load(f)

        # we removed pydantic validation for the meta kg for performance reasons,
        # (and because it is static and should be validated upstream),
        # but this ensures required fields aren't missing from attributes, as can be the case currently
        for node_type, node_properties in self.meta_kg['nodes'].items():
            for attribute_info in node_properties['attributes']:
                if not attribute_info['attribute_type_id']:
                    attribute_info['attribute_type_id'] = 'biolink:Attribute'
                if not attribute_info['attribute_source']:
                    attribute_info['attribute_source'] = None
                if not attribute_info['constraint_use']:
                    attribute_info['constraint_use'] = False
                if not attribute_info['constraint_name']:
                    attribute_info['constraint_name'] = None

    def get_sri_testing_data(self):
        if not self.sri_testing_data:
            self.retrieve_sri_test_data()
        return self.sri_testing_data

    def retrieve_sri_test_data(self):
        with open(os.path.join(os.path.dirname(__file__), '..', '..', 'metadata', 'sri_testing_data.json')) as f:
            self.sri_testing_data = json.load(f)

        # version is technically not part of the spec anymore
        # but this ensures validation with the model until it's removed
        if 'version' not in self.sri_testing_data:
            self.sri_testing_data['version'] = config.get('BL_VERSION')

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
