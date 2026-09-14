#!/bin/bash
# Initialize Elasticsearch with Jaeger ILM policy and index template
# Run this after Elasticsearch is healthy but before Jaeger starts writing

set -euo pipefail

ES_URL="${ES_URL:-http://localhost:9200}"

echo "Waiting for Elasticsearch to be ready..."
until curl -s "${ES_URL}/_cluster/health" | grep -q '"status":"green"\|"status":"yellow"'; do
  echo "Elasticsearch not ready, waiting..."
  sleep 5
done

echo "Elasticsearch is ready. Creating ILM policy..."

# Create ILM policy
curl -X PUT "${ES_URL}/_ilm/policy/jaeger-ilm-policy" \
  -H 'Content-Type: application/json' \
  -d '{
    "policy": {
      "phases": {
        "hot": {
          "min_age": "0ms",
          "actions": {
            "rollover": {
              "max_age": "1d",
              "max_primary_shard_size": "10gb"
            },
            "set_priority": {
              "priority": 100
            }
          }
        },
        "warm": {
          "min_age": "2d",
          "actions": {
            "set_priority": {
              "priority": 50
            },
            "shrink": {
              "number_of_shards": 1
            },
            "forcemerge": {
              "max_num_segments": 1
            }
          }
        },
        "delete": {
          "min_age": "30d",
          "actions": {
            "delete": {}
          }
        }
      }
    }
  }'

echo ""
echo "Creating index template..."

# Create index template
curl -X PUT "${ES_URL}/_index_template/jaeger-template" \
  -H 'Content-Type: application/json' \
  -d '{
    "index_patterns": ["jaeger-span-*", "jaeger-service-*", "jaeger-dependencies-*"],
    "template": {
      "settings": {
        "index.lifecycle.name": "jaeger-ilm-policy",
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "refresh_interval": "5s"
      }
    },
    "priority": 100
  }'

echo ""
echo "Elasticsearch initialization complete!"
echo "ILM policy 'jaeger-ilm-policy' created with 30-day retention"
echo "Index template 'jaeger-template' created for jaeger-* indices"
