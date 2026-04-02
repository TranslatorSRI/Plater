import os
import yaml
import json
import time
import random
import threading
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

from validate import send_cypher_query, send_trapi_query


def quick_jsonl_file_iterator(json_file):
    with open(json_file, 'r', encoding='utf-8') as fp:
        for line in fp:
            try:
                yield json.loads(line)
            except json.decoder.JSONDecodeError as j:
                yield {}


def save_results(results, output_path):
    with open(output_path, 'w') as p_out:
        p_out.write(json.dumps(results, indent=4))


def run_queries_for_endpoint(endpoint_name, url, performance_spec, results, iterations, output_path,
                              save_lock=None, save_responses=False):
    """Run all queries in performance_spec against a single endpoint URL."""
    print(f'Running performance analysis for: {endpoint_name} ({url})')
    query_count = 0
    for spec_name, query_details in performance_spec.items():
        if spec_name not in results:
            results[spec_name] = {}
        if endpoint_name not in results[spec_name]:
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
                if query_name in results[spec_name][endpoint_name]:
                    previous = results[spec_name][endpoint_name][query_name]
                    has_forbidden = any('403 Client Error: Forbidden' in e for e in previous.get('errors', []))
                    if not has_forbidden:
                        print(f'Skipping already completed query {query_name} for {endpoint_name}: {spec_name}')
                        query_count += 1
                        continue
                    print(f'Retrying query {query_name} for {endpoint_name}: {spec_name} (had 403 Forbidden)')
                    results[spec_name][endpoint_name].pop(query_name)
                results[spec_name][endpoint_name][query_name] = {'success_duration': [],
                                                                  'num_results': [],
                                                                  'num_kg_nodes': [],
                                                                  'num_kg_edges': [],
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
                            num_kg_nodes = len(trapi_response['message'].get('knowledge_graph', {}).get('nodes', {}))
                            num_kg_edges = len(trapi_response['message'].get('knowledge_graph', {}).get('edges', {}))
                            response_size = len(json.dumps(trapi_response, separators=(',', ':')).encode('utf-8'))
                        elif query_details["query_type"] == "cypher":
                            cypher_query = performance_query["cypher_query"]
                            cypher_response = send_cypher_query(url,
                                                                cypher_query)
                            num_results = 1
                            num_kg_nodes = "N/A"
                            num_kg_edges = "N/A"
                            response_size = len(json.dumps(cypher_response, separators=(',', ':')).encode('utf-8'))
                        else:
                            raise NotImplementedError(f'Query type {query_details["query_type"]} not implemented.')

                        duration = time.time() - start_time
                        print(f'Got back {num_results} results ({response_size} bytes) in {duration}s.')
                        results[spec_name][endpoint_name][query_name]['success_duration'].append(duration)
                        results[spec_name][endpoint_name][query_name]['num_results'].append(num_results)
                        results[spec_name][endpoint_name][query_name]['num_kg_nodes'].append(num_kg_nodes)
                        results[spec_name][endpoint_name][query_name]['num_kg_edges'].append(num_kg_edges)
                        results[spec_name][endpoint_name][query_name]['response_size_bytes'].append(response_size)
                        if save_responses:
                            response_dir = os.path.join('./performance_results', 'responses', endpoint_name)
                            os.makedirs(response_dir, exist_ok=True)
                            response_data = trapi_response if query_details["query_type"] == "trapi" else cypher_response
                            response_file = os.path.join(response_dir, f'{query_name}_iter{i+1}.json')
                            with open(response_file, 'w') as rf:
                                json.dump(response_data, rf, separators=(',', ':'))
                    except requests.exceptions.HTTPError as e:
                        duration = time.time() - start_time
                        print(f'Error occured after {duration} seconds: {e}.')
                        results[spec_name][endpoint_name][query_name]['errors'].append(str(e))

                query_count += 1
                success_durations = results[spec_name][endpoint_name][query_name]['success_duration']
                average = sum(success_durations) / len(success_durations) if success_durations else "N/A"
                print(f'Average time for {query_name} to {endpoint_name}, {spec_name}: {average}')
                if query_count % 10 == 0:
                    print(f'Saving intermediate results ({query_count} queries completed for {endpoint_name})...')
                    if save_lock:
                        with save_lock:
                            save_results(results, output_path)
                    else:
                        save_results(results, output_path)


def run_performance_analysis(deployments_to_validate=None, performance_spec=None, iterations=3,
                             endpoints=None, resume_from=None, save_responses=False):
    """Run performance analysis.

    Either pass endpoints (a dict of {name: url}) to run TRAPI queries directly,
    or use deployments_to_validate to filter from the deployment_spec.yaml file.

    If resume_from is provided (a file number like 10844), load previous results
    from that file and skip any queries that were already completed.
    """
    plater_performance_results = {}
    os.makedirs('./performance_results', exist_ok=True)

    if resume_from is not None:
        resume_path = f'./performance_results/performance_analysis_results_{resume_from}.json'
        if os.path.exists(resume_path):
            with open(resume_path) as f:
                plater_performance_results = json.load(f)
            print(f'Resuming from {resume_path}')
        else:
            print(f'Warning: resume file {resume_path} not found, starting fresh.')

    output_path = f'./performance_results/performance_analysis_results_{resume_from or random.randrange(100000)}.json'

    save_lock = threading.Lock()

    # Build list of (endpoint_name, url) pairs to run in parallel
    endpoint_tasks = []
    if endpoints:
        endpoint_tasks = list(endpoints.items())
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
                    endpoint_tasks.append((deployment_env, url))

    with ThreadPoolExecutor(max_workers=len(endpoint_tasks) or 1) as executor:
        futures = {
            executor.submit(
                run_queries_for_endpoint, name, url, performance_spec,
                plater_performance_results, iterations, output_path, save_lock, save_responses
            ): name
            for name, url in endpoint_tasks
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                future.result()
                print(f'Completed all queries for: {name}')
            except Exception as e:
                print(f'Error running queries for {name}: {e}')

    save_results(plater_performance_results, output_path)


if __name__ == '__main__':

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--resume-from', type=str, default=None,
                        help='File number of a previous run to resume from (e.g. 10844)')
    parser.add_argument('--save-responses', action='store_true',
                        help='Save full response bodies to performance_results/responses/')
    args = parser.parse_args()

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
        #"memgraph_plater": "https://automat.renci.org/robokopkg-memgraph/",
        "gandalf_dev": "https://automat-dev.apps.renci.org/robokopkg/",
        "gandalf_ci": "https://automat.ci.transltr.io/robokopkg/",
        #"gandalf_test": "https://automat.test.transltr.io/robokopkg/",
    }
    trapi_spec = {
        "robokopkg": {"files": ["./performance_queries/robokop_two_hop_trapi.jsonl"],
                      # "queries": [
                      #    "robokop_two_hop_ChemicalEntity_affects",
                      # ],
                      "query_type": "trapi"}
    }
    run_performance_analysis(performance_spec=trapi_spec, endpoints=trapi_endpoints, iterations=1,
                             resume_from=args.resume_from, save_responses=args.save_responses)
