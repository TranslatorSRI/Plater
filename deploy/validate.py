import requests

def validate_plater(url, expected_version):
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
    results['expected_number_of_nodes'] = expected_number_of_nodes

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

    # get the open api spec and the example trapi query from it
    openapi_response = requests.get(f'{url}openapi.json')
    if openapi_response.status_code != 200:
        try:
            cypher_response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            results['validation_errors'].append(f'Retrieving open api spec failed: {str(e)}')
            return results
    openapi_spec = openapi_response.json()
    example_trapi_query = openapi_spec['paths']['/1.4/query']['post']['requestBody']['content']['application/json']['example']

    # send the example trapi query and make sure it works
    trapi_query_response = requests.post(f'{url}1.4/query', json=example_trapi_query)
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

    # NOTE - The automat urls and graph_deployment_spec(s) are hardcoded here, but we should be able to read from
    # any deployment spec and test against the endpoint(s) specified within. This current set up is also wrong because
    # graph versions/deployments are not necessarily the same across the environments.
    automat_urls = ['https://automat.renci.org/',
                    'https://automat.ci.transltr.io/',
                    'https://automat.test.transltr.io/',
                    'https://automat.transltr.io/',
                    'https://robokop-automat.apps.renci.org/']  # TODO get these from a graph deployment spec
    graph_deployment_specs = ['./new_graphs.txt']  # TODO get these from cli input

    everything_is_good = True
    for automat_url in automat_urls:
        print(f'Validating deployments on {automat_url}')
        for graph_deployment_spec_path in graph_deployment_specs:
            with open(graph_deployment_spec_path) as graph_deployment_spec_file:
                plater_validation_results = {}
                for line in graph_deployment_spec_file:
                    split_line = line.split()
                    plater_id = split_line[0]
                    graph_version = split_line[1]
                    validation_results = validate_plater(f'{automat_url}{plater_id}/', graph_version)
                    validation_errors = "\n".join(validation_results['validation_errors'])
                    if validation_errors:
                        everything_is_good = False
                        error_message = f'Validation errors occurred for {plater_id} on {automat_url}: {validation_errors}'
                        print(error_message)
                    # else:
                    #    print(f'{plater_id} ({graph_version}) on {automat_url} looks ok.')
                    plater_validation_results[plater_id] = validation_results
                # TODO - do something with plater_validation_results other than print errors?
    if everything_is_good:
        print(f'Yay. Everything looks good.')
