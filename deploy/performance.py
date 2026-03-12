import os
import yaml
import json
import time
import random
import requests

from validate import send_cypher_query, send_trapi_query


def quick_jsonl_file_iterator(json_file):
    with open(json_file, 'r', encoding='utf-8') as fp:
        for line in fp:
            try:
                yield json.loads(line)
            except json.decoder.JSONDecodeError as j:
                yield {}


def run_queries_for_endpoint(endpoint_name, url, performance_spec, results, iterations):
    """Run all queries in performance_spec against a single endpoint URL."""
    print(f'Running performance analysis for: {endpoint_name} ({url})')
    for spec_name, query_details in performance_spec.items():
        if spec_name not in results:
            results[spec_name] = {}
        results[spec_name][endpoint_name] = {}
        query_files = query_details["files"]
        queries = query_details.get("queries")
        for q_file in query_files:
            for performance_query in quick_jsonl_file_iterator(f'./{q_file}'):
                if not performance_query:
                    continue
                query_name = performance_query.pop('query_name')
                if queries and query_name not in queries:
                    continue
                results[spec_name][endpoint_name][query_name] = {'success_duration': [],
                                                                  'num_results': [],
                                                                  'response_size_bytes': [],
                                                                  'errors': []}
                for i in range(iterations):
                    print(f'Sending query {query_name} to {endpoint_name}: {spec_name}, iteration {i+1}')
                    start_time = time.time()
                    try:
                        if query_details["query_type"] == "trapi":
                            trapi_response = send_trapi_query(url,
                                                              performance_query,
                                                              profile=False,
                                                              validate=False)
                            num_results = len(trapi_response['message']['results'])
                            response_size = len(json.dumps(trapi_response, separators=(',', ':')).encode('utf-8'))
                        elif query_details["query_type"] == "cypher":
                            cypher_query = performance_query["cypher_query"]
                            cypher_response = send_cypher_query(url,
                                                                cypher_query)
                            num_results = 1
                            response_size = len(json.dumps(cypher_response, separators=(',', ':')).encode('utf-8'))
                        else:
                            print("huh")
                        duration = time.time() - start_time
                        print(f'Got back {num_results} results ({response_size} bytes) in {duration}s.')
                        results[spec_name][endpoint_name][query_name]['success_duration'].append(duration)
                        results[spec_name][endpoint_name][query_name]['num_results'].append(num_results)
                        results[spec_name][endpoint_name][query_name]['response_size_bytes'].append(response_size)
                    except requests.exceptions.HTTPError as e:
                        duration = time.time() - start_time
                        print(f'Error occured after {duration} seconds: {e}.')
                        results[spec_name][endpoint_name][query_name]['errors'].append(str(e))

                success_durations = results[spec_name][endpoint_name][query_name]['success_duration']
                average = sum(success_durations) / len(success_durations) if success_durations else "N/A"
                print(f'Average time for {query_name} to {endpoint_name}, {spec_name}: {average}')


def run_performance_analysis(deployments_to_validate=None, performance_spec=None, iterations=3,
                             endpoints=None):
    """Run performance analysis.

    Either pass endpoints (a dict of {name: url}) to run TRAPI queries directly,
    or use deployments_to_validate to filter from the deployment_spec.yaml file.
    """
    plater_performance_results = {}

    if endpoints:
        for endpoint_name, url in endpoints.items():
            run_queries_for_endpoint(endpoint_name, url, performance_spec,
                                     plater_performance_results, iterations)
    else:
        graph_deployment_spec_path = os.path.join(os.path.dirname(__file__), 'deployment_spec.yaml')
        with open(graph_deployment_spec_path) as graph_deployment_spec_file:
            deployment_spec = yaml.safe_load(graph_deployment_spec_file)
        for deployment in deployment_spec['deployments']:
            deployment_env = deployment['deployment_environment']
            automat_url = deployment['automat_url']
            if not deployments_to_validate or deployment_env in deployments_to_validate:
                for plater in performance_spec:
                    url = automat_url + plater + "/" if "localhost" not in automat_url else automat_url
                    run_queries_for_endpoint(deployment_env, url, performance_spec,
                                             plater_performance_results, iterations)

    os.makedirs('./performance_results', exist_ok=True)
    with open(f'./performance_results/performance_analysis_results_{random.randrange(100000)}.json', 'w') as p_out:
        p_out.write(json.dumps(plater_performance_results, indent=4))


if __name__ == '__main__':

    # environments = ['exp', 'dev', 'robokop']
    # environments = ['robokop']

    # performance_spec = {
        #"robokopkg": {"files": ["./performance_queries/robokopkg_performance_trapi.jsonl"],
        #              "queries": ["gene_to_chemical_qualifier_1"],
        #              "query_type": "trapi"},
        # "robokopkg": {"files": ["./performance_queries/robokopkg_neo4j_cypher.jsonl"],
        #               "queries": ["gene_to_chemical_1", "gene_to_chemical_1_no_labels_call"],
        #               "query_type": "cypher"}
        # "hmdb": {"files": ["./performance_queries/hmdb_performance_queries.jsonl"]}
    # }

    # using deployment spec environments
    # run_performance_analysis(environments, performance_spec, iterations=2)

    # or all environments from deployment spec
    # run_performance_analysis(performance_spec=performance_spec)

    # or pass TRAPI endpoints directly (no deployment spec needed)
    trapi_endpoints = {
        "neo4j_plater": "https://robokop-automat.apps.renci.org/robokopkg/",
        "memgraph_plater": "https://automat.renci.org/robokopkg-memgraph/",
    }
    trapi_spec = {
        "robokopkg": {"files": ["./performance_queries/robokop_one_hop_trapi.jsonl"],
                      "queries": ["robokop_small_Behavior_affects"],
                      "query_type": "trapi"}
    }
    run_performance_analysis(performance_spec=trapi_spec, endpoints=trapi_endpoints, iterations=1)

