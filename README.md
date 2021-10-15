# PLATER

![test batch](https://travis-ci.com/TranslatorSRI/Plater.svg?branch=master)

## About 

Suppose you have constructed a biolink-compliant knowledge graph, and want to deploy it as a TRAPI endpoint with limited fuss.  Plater is a web server that automatically exposes a Neo4j instance through [TRAPI](https://github.com/NCATSTranslator/ReasonerAPI) compliant endpoints. Plater brings several tools together in a web server to achieve this. It Uses [Reasoner Pydantic models](https://github.com/TranslatorSRI/reasoner-pydantic) for frontend validation and [Reasoner transpiler](https://github.com/ranking-agent/reasoner-transpiler) for transforming TRAPI to and from cypher and querying the Neo4j backend. The Neo4j database can be populated by using [KGX](https://github.com/biolink/kgx) upload, which is able to consume numerous graph input formats. By pointing Plater to Neo4j we can easily stand up a Knowledge Provider that provides the “lookup” operation and meta_knowledge_graph, as well as providing a platform to distribute common code implementing future operations across any endpoint built using Plater. In addition, with some configuration (x-trapi parameters etc...) options we can easily register our new instance to [Smart api](https://smart-api.info/). 

Another tool that comes in handy with Plater is [Automat](https://github.com/RENCI-AUTOMAT/Automat-server), which helps expose multiple Plater servers at a single public url and proxies queries towards them. [Here](https://automat.renci.org) is an example of running Automat instance.



## Data Presentation Configuration

### Node and Edge lookup
--------------------

#### Matching a TRAPI query 


PLATER matches nodes in neo4j using node labels. It expects nodes in neo4j to be labeled using [biolink types](https://biolink.github.io/biolink-model/docs/). Nodes in neo4j can have multiple labels. When looking a node from an incoming TRAPI query graph, the node type(s) are extracted for a node, and by traversing the biolink model, all subtypes and mixins that go with the query node type(s) will be used to lookup nodes. 

Similarly for edges, edge labels in neo4j are used to perform edge lookup. Predicate hierarchy in biolink would be consulted to find subclasses of the query predicate type(s) and those would be used in an `OR` combinatorial fashion to find results.  
 

#### Subclass Inference

Plater does subclass inference if subclass edges are encoded into neo4j graph. For eg , let A be a super class of B and C. And let B, C are related to D and E respectively 

```
(A) <- biolink:subclass_of - (B) - biolink:decreases_activity_of -> (D)
    <- biolink:subclass_of - (C) - biolink:decreases_activity_of -> (E)
```

Querying for A - [ biolink:decreases_activity_of] -> (?) would give us back nodes D and E. 


#### Presenting Attributes


Plater tries to resolve attibute types and value types for edges and nodes in the following ways. 

1. [attr_val_map.json](https://github.com/TranslatorSRI/Plater/blob/master/attr_val_map.json): This file has the following structure 
    ```
    {
    "attribute_type_map" : {
       "<attribute_name_in_neo4j>" : "TRAPI_COMPLIANT_ATTRIBUTE_NAME"
        },
    "value_type_map": {
        "<attribute_name_in_neo4j>" : "TRAPI_COMPLIANT_VALUE_TYPE"
        }
    }

    ```
    To explain this a little further, suppose we have an attribute called "equivalent_identifiers" stored in neo4j. Our attr_val_map.json would be : 

    ```
    {
      "attribute_type_map": {     
          "equivalent_identifiers": "biolink:same_as"
      },
      "value_type_map": {
          "equivalent_identifiers": "metatype:uriorcurie"     
      }
    }

    ```
    When Nodes / edges that have equvalent_identifier are returned they would have : 
    ```
      "MONDO:0004969": {
              "categories": [...],
              "name": "acute quadriplegic myopathy",
              "attributes": [
                {
                  "attribute_type_id": "biolink:same_as",
                  "value": [
                    "MONDO:0004969"
                  ],
                  "value_type_id": "metatype:uriorcurie",
                  "original_attribute_name": "equivalent_identifiers",
                  "value_url": null,
                  "attribute_source": null,
                  "description": null,
                  "attributes": null
                }]
            }
    ```
  
 2. In cases where there are attributes in neo4j that are not specified in attr_val_map.json, PLATER will try to resolve a biolink class by using the original attribute name using Biolink model toolkit. 
 3. If the above steps fail the attribute will be presented having `"attribute_type_id": "biolink:Attribute"` and `"value_type_id": "EDAM:data_0006"`
 4. If there are attributes that is not needed for presentation through TRAPI [Skip_attr.json](https://github.com/TranslatorSRI/Plater/blob/master/skip_attr.json) can be used to specify attribute names in neo4j to skip. 
 
### Provenance 
------------
By setting `PROVENANCE_TAG` environment variable to something like `infores:automat.ctd` , edges will contain provenance information on edges and nodes.


## Installation

To run the web server directly:

#### Create a virtual Environment and activate.

    cd <PLATER-ROOT>
    python<version> -m venv venv
    source venv/bin/activate
    
#### Install dependencies
    
    pip install -r PLATER/requirements.txt
    
 
#### Configure PLATER settings
   
   Populate `.env-template` file with settings and save as `.env` in repo root dir.
   
   ```bash   
    WEB_HOST=0.0.0.0
    WEB_PORT=8080
    NEO4J_HOST=neo4j
    NEO4J_USERNAME=neo4j
    NEO4J_PASSWORD=<change_me>    
    NEO4J_HTTP_PORT=7474
    PLATER_TITLE='Plater'
    PLATER_VERSION='1.1.0'
    BL_VERSION='1.6.1'

   ```
   
  
#### Run Script
  
    ./main.sh
 
    
 ### DOCKER 
   Or build an image and run it. 
  
  ```bash
    cd PLATER
    docker build --tag <image_tag> .
    cd ../
  ```
  
  ```bash
   docker run --env-file .env\
    --name plater\
    -p 8080:8080\
    --network <network_where_neo4j_is_running>\
    plater-tst

  ```
 
 ### Clustering with [Automat Server](https://github.com/RENCI-AUTOMAT/Automat-server/) \[Optional\]
 You can also serve several instances of plater through a common gateway(Automat). On specific instructions 
 please refer to [AUTOMAT's readme](https://github.com/RENCI-AUTOMAT/Automat-server/blob/master/README.md)
  
 

 ### Miscellaneous
 ###### `/about` Endpoint 
 The `/about` endpoint can be used to present meta-data about the current PLATER instance. 
 This meta-data is served from `<repo-root>/PLATER/about.json` file. One can edit the contents of
 this file to suite needs. In containerized environment we recommend mounting this file as a volume.
 
 Eg:
 ```bash
docker run -p 0.0.0.0:8999:8080  \
               --env NEO4J_HOST=<your_neo_host> \
               --env NEO4J_HTTP_PORT=<your_neo4j_http_port> \
               --env NEO4J_USERNAME=neo4j\
               --env NEO4J_PASSWORD=<neo4j_password> \
               --env WEB_HOST=0.0.0.0 \
               -v <your-custom-about>:/<path-to-plater-repo-home>/plater/about.json \
               --network=<docker_network_neo4j_is_running_at> \    
                <image_tag>
    
``` 
 
   
    
    
