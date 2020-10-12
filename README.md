# Redundancy_Scheduling

Simulation of a queueing system, where:
* jobs have _bi-modal_ service time distribution, and
* each job gets _redundantly_ submitted to `r` out of `n` servers, according to some scheduling policy, and
* redundant copies of job get canceled once the first copy _starts the service_.

Scheduling policies are:
* random,
* round-robin,
* BIBD (short for Balanced and Incomplete Block Design).

For results and discussions check [this paper](https://arxiv.org/pdf/1908.02415.pdf).
