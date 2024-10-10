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


def run_performance_analysis(deployments_to_validate=None, performance_spec=None, iterations=3):

    graph_deployment_spec_path = os.path.join(os.path.dirname(__file__), 'deployment_spec.yaml')
    with open(graph_deployment_spec_path) as graph_deployment_spec_file:
        deployment_spec = yaml.safe_load(graph_deployment_spec_file)
        plater_performance_results = {}
        for deployment in deployment_spec['deployments']:
            deployment_env = deployment['deployment_environment']
            automat_url = deployment['automat_url']
            if not deployments_to_validate or deployment_env in deployments_to_validate:
                print(f'Running performance analysis for environment: {deployment_env}')
                for plater, query_details in performance_spec.items():
                    if plater not in plater_performance_results:
                        plater_performance_results[plater] = {}
                    plater_performance_results[plater][deployment_env] = {}
                    url = automat_url + plater + "/" if "localhost" not in automat_url else automat_url
                    query_files = query_details["files"]
                    queries = query_details["queries"] if "queries" in query_details else None
                    for q_file in query_files:
                        for performance_query in quick_jsonl_file_iterator(f'./{q_file}'):
                            if not performance_query:
                                continue
                            query_name = performance_query.pop('name')
                            if queries and query_name not in queries:
                                continue
                            plater_performance_results[plater][deployment_env][query_name] = {'success_duration': [],
                                                                                              'errors': []}
                            for i in range(iterations):
                                print(f'Sending query {query_name} to {deployment_env}: {plater}, iteration {i+1}')
                                start_time = time.time()
                                try:
                                    trapi_response = send_trapi_query(url,
                                                                      performance_query,
                                                                      profile=False,
                                                                      validate=False)
                                    num_results = len(trapi_response['message']['results'])
                                    # print(trapi_response)
                                    duration = time.time() - start_time
                                    print(f'Got back {num_results} in {duration}.')
                                    plater_performance_results[plater][deployment_env][query_name]['success_duration'].append(duration)
                                except requests.exceptions.HTTPError as e:
                                    duration = time.time() - start_time
                                    print(f'Error occured after {duration} seconds: {e}.')
                                    plater_performance_results[plater][deployment_env][query_name]['errors'].append(str(e))

                                average = sum(plater_performance_results[plater][deployment_env][query_name]['success_duration']) \
                                          / len(plater_performance_results[plater][deployment_env][query_name]['success_duration'])
                            print(f'Average time for {query_name} to {deployment_env}, {plater}: {average}')
    with open(f'./performance_results/performance_analysis_results_{random.randrange(100000)}.json', 'w') as p_out:
        p_out.write(json.dumps(plater_performance_results, indent=4))


if __name__ == '__main__':

    # environments = ['exp', 'dev', 'robokop']
    environments = ['robokop']

    performance_spec = {
         "robokopkg": {"files": ["./performance_queries/robokopkg_performance_queries.jsonl"],
                       "queries": ["gene_to_chemical_qualifier_40"]}
        # "hmdb": {"files": ["./performance_queries/hmdb_performance_queries.jsonl"]}
    }

    # to run for only certain environments
    run_performance_analysis(environments, performance_spec, iterations=3)

    # or all of them
    # run_performance_analysis()

