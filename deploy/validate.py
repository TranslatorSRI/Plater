import requests
import os
import yaml
import click

def get_metadata(url):
    # get the metadata and check the version, get the number of nodes that should be in the graph
    metadata_response = requests.get(f'{url}metadata')
    if metadata_response.status_code != 200:
        metadata_response.raise_for_status()
    metadata = metadata_response.json()
    return metadata


def make_cypher_call(url, cypher):
    # query the graph with cypher
    cypher_query_payload = {"query": cypher}
    cypher_response = requests.post(f'{url}cypher', json=cypher_query_payload)
    if cypher_response.status_code != 200:
        cypher_response.raise_for_status()
    return cypher_response.json()


def validate_plater(url, expected_version, expected_plater_version, expected_trapi_version, run_warmup=False):
    results = {
        'valid': False,
        'expected_graph_version': expected_version,
        'actual_graph_version': None,
        'expected_number_of_nodes': None,
        'actual_number_of_nodes': None,
        'validation_errors': []
    }

    # retrieve the metadata
    try:
        metadata = get_metadata(f'{url}')
    except requests.exceptions.HTTPError as e:
        results['validation_errors'].append(f'Retrieving metadata failed: {str(e)}')
        return results

    # get the graph_version and check that it's what was expected
    metadata_graph_version = metadata['graph_version'] \
        if 'graph_version' in metadata else "Graph version missing from metadata."
    results['actual_graph_version'] = metadata_graph_version
    if metadata_graph_version != expected_version:
        error_message = f'Expected graph version {expected_version} but metadata has: {metadata_graph_version}.'
        results['validation_errors'].append(error_message)
        return results

    # get number of nodes and edges that should be in the graph from the metadata
    expected_number_of_nodes = metadata['final_node_count']
    expected_number_of_edges = metadata['final_edge_count']
    results['expected_number_of_nodes'] = expected_number_of_nodes
    results['expected_number_of_edges'] = expected_number_of_edges

    # query the graph with cypher to check if the neo4j instance is up and has the right number of nodes
    cypher_query_payload = {"query": f"MATCH (n) RETURN count(n)"}
    cypher_response = requests.post(f'{url}cypher', json=cypher_query_payload)
    if cypher_response.status_code != 200:
        try:
            cypher_response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            results['validation_errors'].append(f'Running cypher query failed: {str(e)}')
            return results
    try:
        number_of_nodes = cypher_response.json()['results'][0]['data'][0]['row'][0]
        results['actual_number_of_nodes'] = number_of_nodes
    except KeyError:
        results['validation_errors'].append(f'Cypher query returned an invalid result.')
        return results
    except IndexError:
        results['validation_errors'].append(f'Cypher query returned bad results.')
        return results
    if number_of_nodes != expected_number_of_nodes:
        error_message = f'Metadata said there should be {expected_number_of_nodes} nodes, ' \
                        f'but cypher query returned: {number_of_nodes}.'
        results['validation_errors'].append(error_message)
        return results

    # query the graph with cypher to check if the neo4j instance has the right number of edges
    cypher_query_payload = {"query": f"MATCH (n)-[r]->(m) RETURN count(r)"}
    cypher_response = requests.post(f'{url}cypher', json=cypher_query_payload)
    if cypher_response.status_code != 200:
        try:
            cypher_response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            results['validation_errors'].append(f'Running cypher query failed: {str(e)}')
            return results
    try:
        number_of_edges = cypher_response.json()['results'][0]['data'][0]['row'][0]
        results['actual_number_of_edges'] = number_of_edges
    except KeyError:
        results['validation_errors'].append(f'Cypher query returned an invalid result.')
        return results
    except IndexError:
        results['validation_errors'].append(f'Cypher query returned bad results.')
        return results
    if number_of_edges != expected_number_of_edges:
        error_message = f'Metadata said there should be {expected_number_of_edges} edges, ' \
                        f'but cypher query returned: {number_of_edges}.'
        results['validation_errors'].append(error_message)
        return results

    if run_warmup:
        make_cypher_call(url, 'CALL apoc.warmup.run(True, True, True)')

    # get the open api spec and the example trapi query from it
    openapi_response = requests.get(f'{url}openapi.json')
    if openapi_response.status_code != 200:
        try:
            cypher_response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            results['validation_errors'].append(f'Retrieving open api spec failed: {str(e)}')
            return results

    openapi_spec = openapi_response.json()
    openapi_plater_version = openapi_spec['info']['version']
    if openapi_plater_version != expected_plater_version:
        results['validation_errors'].append(f'Expected plater version {expected_plater_version} but openapi says {openapi_plater_version}')
        return results

    openapi_trapi_version = openapi_spec['info']['x-trapi']['version']
    if openapi_trapi_version != expected_trapi_version:
        results['validation_errors'].append(f'Expected TRAPI version {expected_trapi_version} but openapi says {openapi_trapi_version}')
        return results

    example_trapi_query = openapi_spec['paths']['/query']['post']['requestBody']['content']['application/json']['example']

    # send the example trapi query and make sure it works
    trapi_query_response = requests.post(f'{url}query', json=example_trapi_query)
    if trapi_query_response.status_code != 200:
        try:
            cypher_response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            results['validation_errors'].append(f'Sending a trapi query failed: {str(e)}')
            return results
    trapi_query_results = trapi_query_response.json()['message']
    if 'knowledge_graph' not in trapi_query_results or 'results' not in trapi_query_results:
        results['validation_errors'].append(f'Trapi query results were poorly formatted: {trapi_query_results}')
        return results
    if len(trapi_query_results['results']) == 0:
        results['validation_errors'].append(f'Example trapi query did not yield any results.')
        return results
    results['valid'] = True
    return results


def run_validation(deployments_to_validate=None):
    deployments_to_validate = deployments_to_validate if deployments_to_validate else []
    everything_is_good = True
    graph_deployment_spec_path = os.path.join(os.path.dirname(__file__), 'deployment_spec.yaml')
    with open(graph_deployment_spec_path) as graph_deployment_spec_file:
        deployment_spec = yaml.safe_load(graph_deployment_spec_file)
        plater_validation_results = {}
        for deployment in deployment_spec['deployments']:
            if deployment['deployment_environment'] not in deployments_to_validate:
                print(f"Skipping deployment environment {deployment['deployment_environment']} ({deployment['automat_url']})")
                continue
            else:
                print(f"Validating deployment environment {deployment['deployment_environment']} ({deployment['automat_url']})")
            automat_url = deployment['automat_url']
            trapi_version = deployment['trapi_version']
            plater_version = deployment['plater_version']
            for plater_id, graph_version in deployment['platers'].items():
                validation_results = validate_plater(f'{automat_url}{plater_id}/',
                                                     graph_version,
                                                     plater_version,
                                                     trapi_version,
                                                     run_warmup=False)
                validation_errors = "\n".join(validation_results['validation_errors'])
                if validation_errors:
                    everything_is_good = False
                    error_message = f'Validation errors occurred for {plater_id} on {automat_url}: {validation_errors}'
                    print(error_message)
                # else:
                #    print(f'{plater_id} ({graph_version}) on {automat_url} looks ok.')
                plater_validation_results[plater_id] = validation_results
    if everything_is_good:
        print(f'Yay. Everything looks good.')
    # TODO - do something with plater_validation_results other than print errors?


if __name__ == '__main__':
    # to run for only certain environments
    # run_validation(['dev', 'robokop'])

    # or all of them
    run_validation()




"""
    robo_metadata = get_metadata(f'https://automat.renci.org/robokopkg/')

    edge_counts = {}
    for source in robo_metadata['sources']:
        source_id = source['source_id']
        edge_counts[source_id] = source['normalized_edges.jsonl']['edges']
        if 'supp_norm_edges.jsonl' in source:
            edge_counts[source_id] += source['supp_norm_edges.jsonl']['edges']
    for source in robo_metadata['subgraphs'][0]['graph_metadata']['sources']:
        source_id = source['source_id']
        edge_counts[source_id] = source['normalized_edges.jsonl']['edges']
        if 'supp_norm_edges.jsonl' in source:
            edge_counts[source_id] += source['supp_norm_edges.jsonl']['edges']
    source_counts = [(source, counts) for source, counts in edge_counts.items()]
    source_counts.sort(key=lambda tup: tup[1], reverse=True)
    for source_count in source_counts:
        print(source_count)

    exit()
"""