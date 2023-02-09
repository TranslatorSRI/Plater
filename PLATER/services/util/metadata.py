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
            with open('about.json') as f:
                self.metadata = {
                    'plater': json.load(f)
                }
                self.metadata['plater']['warning'] = 'This section comes from the Plater deployment, not ORION. ' \
                                                     'The rest of the metadata is likely more relevant and specific.'
            metadata_url = config.get('PLATER_METADATA_URL')
            if metadata_url:
                metadata_response = requests.get(metadata_url)
                self.metadata.update(metadata_response.json())
            return self.metadata

        async def get_meta_kg(self):
            if not self.meta_kg:
                self.retrieve_meta_kg()
            return self.meta_kg

        def retrieve_meta_kg(self):
            meta_kg_url = config.get('PLATER_METAKG_URL')
            meta_kg_response = requests.get(meta_kg_url)
            self.meta_kg = meta_kg_response.json()

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
            test_data_url = config.get('PLATER_TEST_DATA_URL')
            test_data_response = requests.get(test_data_url)
            self.sri_testing_data = test_data_response.json()

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
