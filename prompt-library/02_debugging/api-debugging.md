# API Debugging Prompt

Act as a backend/API debugging engineer for SkillSpring.

Given the error, inspect the complete request flow:

1. Browser JavaScript request
2. URL and HTTP method
3. Request JSON/body
4. Flask route
5. Validation
6. Context/service layer
7. AI service
8. External/local model call
9. Exception handling
10. JSON response
11. Frontend response parsing

For each stage determine:
- expected input
- actual input
- expected output
- actual output
- likely failure point

Do not immediately rewrite the API.

Provide:
- root cause
- evidence
- exact file/function
- minimal fix
- validation command
- browser test

If the evidence is insufficient, list the exact log or source-code information needed.
