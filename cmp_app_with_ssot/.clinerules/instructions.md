**Context Inputs:**

1. Relevant AI Agent from (cmp\knowledge\agents\\)
2. Implementation Plan (cmp\knowledge\engineering\implementation-plan.md)
3. Task Plan (cmp\knowledge\engineering\task-plan.md)

**Rules:**

1. Treat the Relevant AI Agent as the project's implementation authority.
2. The Relevant AI Agent is responsible for consulting and validating against the current SSOT.
3. Execute the Task plan according to the Implementation Plan under the governance of the Relevant AI Agent.
4. Do not bypass or override guidance from the Relevant Agent.
5. If the Relevant AI Agent reports that the SSOT is stale or requires regeneration, suspend implementation until synchronization is restored.
6. Produce implementation artifacts, tests, and implementation reports.
7. Return implementation results for synchronization into the SSOT.
8. Save reports to directory cmp\\
9. Save implementation codes to cmp\src\\
10. Save test codes or scripts to cmp\tests\\
