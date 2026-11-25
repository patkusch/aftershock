"""Does every step in order. Retries on errors. Remembers nothing between restarts."""

import sys
import time

from aftershock.client import ToolError, tool


def retry(name, **args):
    for i in range(3):
        try:
            return tool(name, **args)
        except ToolError as e:
            if e.status < 500 or i == 2:
                raise
            time.sleep(0.05)


c = retry("lookup_customer", customer="cus_42")
retry("charge", customer="cus_42", amount=120, description="November")
retry("send_email", to=c["email"], subject="Your November receipt", body="We charged £120.")
retry("write_file", path="invoices/cus_42-nov.txt", content="cus_42 November £120")
sys.exit(0)
