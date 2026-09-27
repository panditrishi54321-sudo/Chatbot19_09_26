# JavaScript Debugging Prompt

Debug SkillSpring frontend JavaScript using evidence.

Check:
- browser Console
- Network tab
- request URL
- HTTP method
- request headers
- JSON body
- response status
- response body
- `fetch()` handling
- `response.ok`
- `response.json()`
- DOM selectors
- event listeners
- async/await
- loading/error states

For `Failed to fetch`, distinguish:
- server not running
- wrong URL/port
- connection refused
- CORS/network problem
- browser-side JavaScript exception
- server returned an error
- invalid JSON response

Do not assume `Failed to fetch` means the AI provider failed.
Trace the request end-to-end.
