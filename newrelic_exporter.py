#!/usr/bin/python

import time
import requests
import click
import json

from datetime import datetime, timedelta
from prometheus_client import start_http_server
from prometheus_client.core import GaugeMetricFamily, REGISTRY


class NewrelicCollector(object):
  def __init__(self, apikey):
    self.graphql_base_url = "https://api.newrelic.com/graphql"
    self.api_key = apikey

  def collect(self):
    print("Collecting\n")
    
    # The metrics we want to export.
    metrics = {
        'apdexScore': GaugeMetricFamily('newrelic_application_apdex_score',' newrelic application apdex_score', labels=["appname"]),
        'errorRate': GaugeMetricFamily('newrelic_application_error_rate',' newrelic application error_rate', labels=["appname"]),
        'hostCount': GaugeMetricFamily('newrelic_application_host_count','newrelic application host count', labels=["appname"]),
        'instanceCount': GaugeMetricFamily('newrelic_applicaiton_instance_count','newrelic application instance count', labels=["appname"]),
        'nonWebResponseTimeAverage': GaugeMetricFamily('newrelic_application_non_web_response_time_average','newrelica applicationnon web response time average',labels=["appname"]),
        'nonWebThroughput': GaugeMetricFamily('newrelic_application_non_web_throughput','newrelic applicationn on web throughput', labels=["appname"]),
        'responseTimeAverage': GaugeMetricFamily('newrelic_application_response_time',' newrelic application response in sec', labels=["appname"]),
        'throughput': GaugeMetricFamily('newrelic_application_throughput',' newrelic application throughput',labels=["appname"]),
        'webResponseTimeAverage': GaugeMetricFamily('newrelic_application_web_response_time_average','newrelic_application web response time average', labels=["appname"]),
        'webThroughput': GaugeMetricFamily('newrelic_application_web_throughput','newrelic application web throughput', labels=["appname"]),
    }

    # Get all entity Guids
    headers = {'API-Key': self.api_key}
    resp  = requests.post(url=self.graphql_base_url, headers=headers, data="{actor {entitySearch(queryBuilder: {domain: APM}) {results {entities {... on ApmApplicationEntityOutline {name apmSummary {apdexScore errorRate hostCount instanceCount nonWebResponseTimeAverage nonWebThroughput responseTimeAverage throughput webResponseTimeAverage webThroughput}} guid}}}}}")
    if resp.json().get("errors"):
      print("Error getting newrelic entities:", resp.json())
      return
    
    guidDict = {}
    # saving guid and name in dictionary (guidDict)
    for entity in resp.json().get("data").get("actor").get("entitySearch").get("results").get("entities"):
      guidDict[entity["guid"]] = entity["name"]

    # Pass the metrics to the prometheus by looping through entity
    for metric in metrics:
      for entity in  resp.json().get("data").get("actor").get("entitySearch").get("results").get("entities"):
        if entity.get("apmSummary"):
          try:
            metrics[metric].add_metric([entity["name"]], entity.get("apmSummary")[metric])
          except KeyError:
            pass
      yield metrics[metric]

    # We can pass only 25 Guids in one request, so dividing all guids in chunks of 25,
    # and fetching deployments for those 25 guids
    # Get list of deployment which happened in last 1 hour
    t = datetime.today()-timedelta(hours=1)
    deploymentArray = []
    guids = list(guidDict.keys())
    
    chunk_size = 25
    for i in range(0, len(guids), chunk_size):      
      resp  = requests.post(url=self.graphql_base_url, headers=headers, data='{{actor {{entities(guids: {0}) {{deploymentSearch(filter: {{timeWindow: {{startTime: {1} }}}}) {{results {{version timestamp entityGuid}}}}}}}}}}'.format(json.dumps(guids[i:i+chunk_size]),round(t.timestamp()*1000)))
      if resp.json().get("errors"):
        print("Error getting newrelic deployments:", resp.json())
        return

      for entity in resp.json().get("data").get("actor").get("entities"):        
        for deployments in entity.get("deploymentSearch").get("results"):          
          deploymentArray.append({
            "name": guidDict.get(deployments.get("entityGuid")),
            "timestamp": deployments.get("timestamp"),
            "version": deployments.get("version")
          })
        
    print(deploymentArray)
    # Expose deployment metric
    deploymentMetric = GaugeMetricFamily('newrelic_application_deployment',' newrelic application deployment', labels=["appname", "version"])
    for deployment in deploymentArray:
      # Passing timestamp as seconds because prometheus client automatically converts timestamp to milliseconds
      deploymentMetric.add_metric([deployment['name'], deployment['version']], 1, int(deployment['timestamp']/1000))
    yield deploymentMetric

@click.command()
@click.option('--api-key', '-a', envvar='APIKEY', help='API key for newrelic', required=True)
def main(api_key):
  REGISTRY.register(NewrelicCollector(api_key))
  start_http_server(9126)
  while True: 
    time.sleep(1)
    
if __name__ == "__main__":
  main()

