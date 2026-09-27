# Clear Chat Feature Prompt

Implement Clear Chat in the existing SkillSpring chatbot.

Requirements:
- remove visible conversation messages except the initial assistant greeting;
- clear browser-side conversation history;
- do not delete student database data;
- do not change server-side application data;
- reset any temporary UI state;
- keep the chatbot open after clearing unless current UX explicitly requires otherwise;
- confirm the behaviour in the browser.

Inspect existing `chat.js` before changing it.
Do not introduce a second chat-history implementation.
