import json
import os
from bmt import Toolkit

bmt_toolkit = Toolkit()
# load the attrib and value mapping file
map_data = json.load(open(os.path.join(os.path.abspath(os.path.dirname(__file__)), "..", "..", "..", "attr_val_map.json")))

# attribute skip list
skip_list = json.load(open(os.path.join(os.path.abspath(os.path.dirname(__file__)), "..", "..", "..", "skip_attr.json")))

# set the value type mappings
VALUE_TYPES = map_data['value_type_map']


def get_attribute_bl_info(attribute_name):
    # set defaults
    new_attr_meta_data = {
        "attribute_type_id": "biolink:Attribute",
        "value_type_id": "EDAM:data_0006",
    }
    # if attribute is meant to b6e skipped return none
    if attribute_name in skip_list or attribute_name in ["name", "id"]:
        return None

    # map the attribute type to the list above, otherwise generic default
    new_attr_meta_data["value_type_id"] = VALUE_TYPES.get(attribute_name, new_attr_meta_data["value_type_id"])
    attr_found = None
    if attribute_name in map_data["attribute_type_map"] or f'`{attribute_name}`' in map_data["attribute_type_map"]:
        attr_found = True
        new_attr_meta_data["attribute_type_id"] = map_data["attribute_type_map"].get(attribute_name) \
                                                  or map_data["attribute_type_map"].get(f"`{attribute_name}`")
    if attribute_name in map_data["value_type_map"]:
        new_attr_meta_data["value_type_id"] = map_data["value_type_map"][attribute_name]
    if attr_found:
        return new_attr_meta_data

    # lookup the biolink info, for qualifiers suffix with _qualifier and do lookup.
    bl_info = bmt_toolkit.get_element(attribute_name) or bmt_toolkit.get_element(attribute_name + "_qualifier")

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
    return new_attr_meta_data


