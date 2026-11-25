#!/bin/sh
# The same job as the safe demo agent, in plain shell, to show any language works.
# Run: aftershock sweep aftershock/demo/invoice.json -- sh examples/curl_agent.sh
set -e
post() { curl -sf -X POST "$AFTERSHOCK_URL/tool/$1" -H "Content-Type: application/json" \
         -H "Idempotency-Key: $AFTERSHOCK_TASK_ID:$1" -d "$2" > /dev/null; }
retry() { post "$1" "$2" || post "$1" "$2" || post "$1" "$2"; }
retry charge     '{"customer":"cus_42","amount":120,"description":"November"}'
retry send_email '{"to":"ana@example.com","subject":"Your November receipt","body":"We charged £120."}'
retry write_file '{"path":"invoices/cus_42-nov.txt","content":"cus_42 November £120"}'
