import requests
import json
from PLATER.services.config import config


class GraphMetadata:
    """
    Singleton class for retrieving metadata
    """
    class _GraphMetadata:

        def __init__(self):
            self.metadata = None
            self.meta_kg = None
            self.sri_testing_data = None

        async def get_metadata(self):
            if not self.metadata:
                self.retrieve_metadata()
            return self.metadata

        def retrieve_metadata(self):
            with open('metadata/metadata.json') as f:
                self.metadata = json.load(f)

            if not self.metadata:
                with open('metadata/about.json') as f:
                    self.metadata = json.load(f)

        async def get_meta_kg(self):
            if not self.meta_kg:
                self.retrieve_meta_kg()
            return self.meta_kg

        def retrieve_meta_kg(self):
            with open('metadata/meta_knowledge_graph.json') as f:
                self.meta_kg = json.load(f)

            # this avoids errors when attribute_type_id is none/null,
            # which should not happen but does currently due to an interaction with the bmt toolkit
            for node_type, node_properties in self.meta_kg['nodes'].items():
                for attribute_info in node_properties['attributes']:
                    if not attribute_info['attribute_type_id']:
                        attribute_info['attribute_type_id'] = 'biolink:Attribute'

        async def get_sri_testing_data(self):
            if not self.sri_testing_data:
                self.retrieve_sri_test_data()
            return self.sri_testing_data

        def retrieve_sri_test_data(self):
            with open('metadata/sri_testing_data.json') as f:
                self.sri_testing_data = json.load(f)

            # version is technically not part of the spec anymore
            # but this ensures validation with the model until it's removed
            if 'version' not in self.sri_testing_data:
                self.sri_testing_data['version'] = config.get('BL_VERSION')


    instance = None

    def __init__(self):
        # create a new instance if not already created.
        if not GraphMetadata.instance:
            GraphMetadata.instance = GraphMetadata._GraphMetadata()

    def __getattr__(self, item):
        # proxy function calls to the inner object.
        return getattr(self.instance, item)
