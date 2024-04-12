import json
import os
from functools import cache
from PLATER.services.util.bl_helper import get_biolink_model_toolkit

bmt_toolkit = get_biolink_model_toolkit()

# load the attrib and value mapping file
map_data = json.load(open(os.path.join(os.path.abspath(os.path.dirname(__file__)), "..", "..", "..", "attr_val_map.json")))

# attribute skip list
skip_list = json.load(open(os.path.join(os.path.abspath(os.path.dirname(__file__)), "..", "..", "..", "skip_attr.json")))

# set the value type mappings
VALUE_TYPES = map_data['value_type_map']


@cache
def get_attribute_info(attribute_name, attribute_type_id):
    # set defaults
    new_attr_meta_data = {
        "attribute_type_id": "biolink:Attribute" if (not attribute_type_id) or (attribute_type_id == 'NA') else attribute_type_id,
        "value_type_id": "EDAM:data_0006",
    }

    # lookup the biolink info
    bl_info = bmt_toolkit.get_element(attribute_name)

    # did we get something
    if bl_info is not None:
        # if there are exact mappings use the first on
        if 'slot_uri' in bl_info:
            new_attr_meta_data['attribute_type_id'] = bl_info['slot_uri']
            # was there a range value
            if 'range' in bl_info and bl_info['range'] is not None:
                # try to get the type of data
                new_type = bmt_toolkit.get_element(bl_info['range'])
                # check if new_type is not None. For eg. bl_info['range'] = 'uriorcurie' for things
                # for `relation` .
                if new_type:
                    if 'uri' in new_type and new_type['uri'] is not None:
                        # get the real data type
                        new_attr_meta_data["value_type_id"] = new_type['uri']
        elif 'class_uri' in bl_info:
            new_attr_meta_data['attribute_type_id'] = bl_info['class_uri']

    # possibly overwrite using the custom attribute mapping
    if attribute_name in map_data["attribute_type_map"] or f'`{attribute_name}`' in map_data["attribute_type_map"]:
        new_attr_meta_data["attribute_type_id"] = map_data["attribute_type_map"].get(attribute_name) \
                                                  or map_data["attribute_type_map"].get(f"`{attribute_name}`")
    if attribute_name in VALUE_TYPES:
        new_attr_meta_data["value_type_id"] = VALUE_TYPES[attribute_name]
    return new_attr_meta_data


