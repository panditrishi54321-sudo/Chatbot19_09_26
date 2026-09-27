# Debugging Prompt Templates

## Browser error
I will provide a screenshot/error. Identify what the browser proves and what it does not prove. Then trace the request through Network -> backend -> service -> model.

## Failed fetch
Do not assume the AI provider is the cause. Check server availability, URL/port, request method, payload, HTTP status, response body and JavaScript parsing.

## Backend exception
Use the actual traceback. Identify the first meaningful application-level failure, explain why it occurs, and provide the smallest safe fix.

## Regression
Compare the working flow with the newly changed code. Identify what changed and whether the regression is frontend, backend, data, configuration or integration related.
