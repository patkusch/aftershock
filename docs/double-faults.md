# Two faults in one run

`aftershock sweep --double` runs every single fault, then every pair: one fault
at each call, and a second fault at each of the calls after it.

The second fault often lands while the agent is recovering from the first.
That is the point: recovery code runs rarely, so it is often the least tested.

Call numbers keep counting across restarts. So after a crash at call 1, the
redo of step 3 might be call 4. The report therefore compares runs by the step
a fault actually hit, not by its number.

The report lists failures that **only** show up with two faults, where each
fault alone on the same step passes. If it says none, single faults already
found every problem, which is good to know too.

A double sweep is slow: for a four-step task, about 160 to 210 runs instead of
16. Use `--faults` to try fewer kinds.
