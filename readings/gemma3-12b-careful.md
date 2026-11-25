## Bill a customer for November

Clean run: pass. Crash tests passed: 16 of 24.

| Call | Tool | crash-before | crash-after | timeout | error |
|---|---|---|---|---|---|
| 1 | lookup_customer | pass | pass | pass | pass |
| 2 | find_charges | pass | pass | pass | pass |
| 3 | charge | pass | **FAIL** did 2 times, should be once: charge cus_42 120 | pass | pass |
| 4 | find_emails | **FAIL** did 2 times, should be once: charge cus_42 120 | **FAIL** did 2 times, should be once: charge cus_42 120 | pass | pass |
| 5 | send_email | **FAIL** did 2 times, should be once: charge cus_42 120 | **FAIL** did 2 times, should be once: charge cus_42 120; did 2 times, should be once: email ana@example.com | **FAIL** did 2 times, should be once: email ana@example.com | pass |
| 6 | write_file | **FAIL** did 2 times, should be once: charge cus_42 120; did 2 times, should be once: email ana@example.com | **FAIL** did 2 times, should be once: charge cus_42 120; did 2 times, should be once: email ana@example.com | pass | pass |
