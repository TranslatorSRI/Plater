import json
import os

# load the attrib and value mapping file
map_data = json.load(open(os.path.join(os.path.abspath(os.path.dirname(__file__)), "..", "..", "..", "attr_val_map.json")))

# set the value type mappings from the file
VALUE_TYPES = map_data['value_type_map']

# set the attribute type mappings from the file
ATTRIBUTE_TYPES = map_data['attribute_type_map']

# attribute skip list
SKIP_LIST = json.load(open(os.path.join(os.path.abspath(os.path.dirname(__file__)), "..", "..", "..", "skip_attr.json")))
