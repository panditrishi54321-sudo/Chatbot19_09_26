# Chatbot Debugging Prompt

The SkillSpring chatbot is showing an error such as:
- Failed to fetch
- AI assistant temporarily unavailable
- empty response
- unexpected JSON
- timeout

Debug it systematically.

Check:
1. Is Flask running?
2. Is the expected port listening?
3. Does `/learning-hub` load?
4. Does `POST /api/chat` reach Flask?
5. What HTTP status is returned?
6. What request payload is sent?
7. What response payload is returned?
8. Is the backend exception visible in the terminal?
9. Does the AI service have the required environment variables?
10. Is the configured model/service reachable?
11. Does context building fail before the model call?
12. Does frontend code expect the same JSON property returned by Flask?

Do not replace the error with a mock response.
Use the real terminal and Network evidence.
