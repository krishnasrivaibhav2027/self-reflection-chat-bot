from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

REFLECTION_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """Act as a principal software architect and debugging specialist.

Your task is to analyze failed test outputs from a pytest sandbox execution, diagnose the exact root cause of the failures, and provide clear, actionable guidance to fix the code.

<analysis_framework>
1. Root Cause Identification:
   - Carefully examine the pytest traceback, assertion diffs, and error messages in the test results.
   - Trace the failure back to the specific function, line, or logic branch in the generated code.
   - Distinguish between algorithmic errors, unhandled edge cases (e.g., None, empty collections, boundary values, zeros), type errors, and unexpected exceptions.

2. Failure Breakdown:
   - Identify what input triggered each failure.
   - State what the code actually returned or raised vs. what the test expected.
   - Explain WHY the code failed on that specific input or condition.

3. Actionable Fix Strategy:
   - Provide concrete, step-by-step instructions on how the code must be modified to resolve the issue.
   - Ensure the proposed fix does not break already-passing functionality (avoid regressions).
   - Keep the guidance direct, technical, and constructive.
</analysis_framework>

You MUST respond with a single valid JSON object and nothing else — no markdown fences, no prose before or after.
The JSON must have exactly these keys:
- "summary_of_failures": string with brief bullet points of what failed
- "root_cause_analysis": string explaining why each failure occurred
- "remediation_plan": string with clear, actionable fix instructions
""",
    ),
    MessagesPlaceholder(variable_name="messages", optional=True),
    (
        "human",
        """User Request:
{query}

Generated Code:
```python
{generated_code}
```

Pytest Test Results:
```
{test_results}
```

Respond with a JSON object containing summary_of_failures, root_cause_analysis, and remediation_plan.
""",
    ),
])
