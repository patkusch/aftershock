## Bill a customer for November

Clean run: pass. Crash tests passed: 13 of 16.

| Call | Tool | crash-before | crash-after | timeout | error |
|---|---|---|---|---|---|
| 1 | lookup_customer | pass | pass | pass | pass |
| 2 | charge | pass | **FAIL** did 2 times, should be once: charge cus_42 120 | pass | **FAIL** never did: charge cus_42 120 |
| 3 | send_email | pass | **FAIL** did 2 times, should be once: email ana@example.com | pass | pass |
| 4 | write_file | pass | pass | pass | pass |
