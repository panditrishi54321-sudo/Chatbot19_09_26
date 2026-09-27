# Tool Calling Prompt

Explain tool calling with a SkillSpring example.

The assistant should:
1. understand the user's intent;
2. determine whether a tool is needed;
3. select an approved tool;
4. provide valid structured arguments;
5. receive the tool result;
6. validate the result;
7. answer the user.

Never pretend a tool was called when it was not.
Never invent tool results.
Separate model-generated reasoning from actual tool output.
