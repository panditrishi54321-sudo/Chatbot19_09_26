# SkillSpring — Project Context

## Application
SkillSpring is an EdTech web application intended to combine learning content, student data management and an AI learning assistant.

## Current stack
- Python
- Flask
- SQLite
- HTML
- CSS
- JavaScript
- AI/LLM integration
- LangChain + Gemini in the current AI service path

## Important application areas
- Home page
- Data Entry
- View Data
- Learning Hub
- AI Tutor / chatbot
- Student database
- Prompt Library

## Current AI flow
Browser chatbot
-> JavaScript
-> `POST /api/chat`
-> Flask
-> database/application context
-> AI service
-> configured LLM
-> JSON response
-> chatbot UI

## Context-aware behaviour
The application can inspect available:
- students
- courses
- skill levels
- student counts
- recent students
- student-specific information where supported

## Important distinction
The project uses an already-trained language model. Project prompts, conversation history and retrieved application context guide the model. This is not the same as training the model from scratch.

## Development rule
Keep this document updated when the project architecture materially changes.
