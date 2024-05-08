import requests
import os
import yaml


def validate_plater(url, expected_version, expected_plater_version, expected_trapi_version):
    results = {
        'valid': False,
        'expected_graph_version': expected_version,
        'actual_graph_version': None,
        'expected_number_of_nodes': None,
        'actual_number_of_nodes': None,
        'validation_errors': []
    }

    # get the metadata and check the version, get the number of nodes that should be in the graph
    metadata_response = requests.get(f'{url}metadata')
    if metadata_response.status_code != 200:
        try:
            metadata_response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            results['validation_errors'].append(f'Retrieving metadata failed: {str(e)}')
            return results
    metadata = metadata_response.json()
    metadata_graph_version = metadata['graph_version'] \
        if 'graph_version' in metadata else "Graph version missing from metadata."
    results['actual_graph_version'] = metadata_graph_version
    if metadata_graph_version != expected_version:
        error_message = f'Expected graph version {expected_version} but metadata has: {metadata_graph_version}.'
        results['validation_errors'].append(error_message)
        return results
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


if __name__ == '__main__':

    everything_is_good = True
    graph_deployment_spec_path = os.path.join(os.path.dirname(__file__), 'deployment_spec.yaml')
    with open(graph_deployment_spec_path) as graph_deployment_spec_file:
        deployment_spec = yaml.safe_load(graph_deployment_spec_file)
        plater_validation_results = {}
        for deployment in deployment_spec['deployments']:
            automat_url = deployment['automat_url']
            trapi_version = deployment['trapi_version']
            plater_version = deployment['plater_version']
            for plater_id, graph_version in deployment['platers'].items():
                validation_results = validate_plater(f'{automat_url}{plater_id}/', graph_version, plater_version, trapi_version)
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

