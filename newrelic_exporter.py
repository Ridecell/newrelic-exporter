#!/usr/bin/python

import time
import requests
import click

from prometheus_client import start_http_server
from prometheus_client.core import GaugeMetricFamily, REGISTRY

class NewrelicCollector(object):
  def __init__(self, apikey, account_number):
    self.graphql_base_url = "https://api.newrelic.com/graphql"
    self.api_key = apikey
    self.account_number = account_number

  def collect(self):
    print("Collecting\n")
    
    # The metrics we want to export.
    metrics = {
        # add the metrics
        'errorRate': GaugeMetricFamily('newrelic_application_error_rate',' newrelic application error rate', labels=["appname"]),
        'webResponseTimeAverage': GaugeMetricFamily('newrelic_application_response_time','newrelic application web response time average', labels=["appname"]),
        'webThroughput': GaugeMetricFamily('newrelic_application_web_throughput','newrelic application web throughput', labels=["appname"]),
        'nonWebThroughput': GaugeMetricFamily('newrelic_nonweb_throughput','newrelic application non web throughput', labels=["appname"]),
        'nonWebResponseTimeAverage': GaugeMetricFamily('newrelic_nonweb_response_time','newrelic application non web response time average', labels=["appname"]),
   }

    headers = {'API-Key': self.api_key}

    graphQuery = """{
                        actor {
                          entitySearch(queryBuilder: {domain: APM}) {
                            results {
                              entities {
                              ... on ApmApplicationEntityOutline {
                                    name
                                    apmSummary {
                                    errorRate
                                    webResponseTimeAverage
                                    webThroughput
                                    nonWebThroughput
                                    nonWebResponseTimeAverage
                                  }
                               }
                             }
                          }
                        }
                      }
                    } """

    resp  = requests.post(url=self.graphql_base_url, headers=headers, data=graphQuery)
    if resp.json().get("errors"):
      print("Error getting newrelic entities:", resp.json())
      return
    # Pass the metrics to the prometheus by looping through entity
    for metric in metrics:
      for entity in  resp.json().get("data").get("actor").get("entitySearch").get("results").get("entities"):
        if entity.get("apmSummary"):
          try:
            metric_value = entity.get("apmSummary")[metric]
            if metric == 'webResponseTimeAverage':
              # Currently webResponseTimeAverage is in seconds format 
              # convert webResponseTimeAverage from seconds to miliseconds
              metric_value = metric_value * 1000
            metrics[metric].add_metric([entity["name"]], metric_value)
          except KeyError:
            pass
      yield metrics[metric]

    deploymentMetric = GaugeMetricFamily('newrelic_application_deployment',' newrelic application deployment', labels=["appname", "version"])
    
    timeInSeconds = 3600  # Get list of deployment which happened in last 1 hour

    deploymentGraphQuery = """{{
                                actor{{
                                  nrql(
                                    query: "SELECT * FROM Deployment SINCE {0} seconds AGO "
                                    accounts: {1}
                                  ) {{
                                      nrql 
                                      results
                                      }}
                                  }}
                              }}""".format(timeInSeconds,self.account_number)
    resp  = requests.post(url=self.graphql_base_url, headers=headers, data=deploymentGraphQuery)
    
    if resp.json().get("errors"):
        print("Error getting newrelic deployment response : ", resp.json())
        return

    # Iterate through the deployment result and adding relevant information to depoymentMetric
    for deployments in resp.json().get("data").get("actor").get("nrql").get("results"):
      # Passing timestamp as seconds because prometheus client automatically converts timestamp to milliseconds
      deploymentMetric.add_metric([deployments.get("entity.name"),deployments.get("version")],1, int(deployments.get("timestamp") / 1000))
    yield deploymentMetric
    
    
@click.command()
@click.option('--api-key', '-a', envvar='APIKEY', help='API key for newrelic', required=True)
@click.option('--account-number','-n',envvar='NEWRELIC_ACCOUNT_NUMBER', help='Account Number for newrelic',required=True)
def main(api_key, account_number):   
  collector = NewrelicCollector(api_key, account_number)
  REGISTRY.register(collector)
  start_http_server(9126)
  while True: 
    time.sleep(1)
    
if __name__ == "__main__":
  main()

