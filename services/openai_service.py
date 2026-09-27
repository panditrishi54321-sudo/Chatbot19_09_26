import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from database.db import (
	get_available_courses,
	get_available_skill_levels,
	get_recent_students,
	get_student_by_name,
	get_student_count,
	get_student_count_by_course,
	get_student_count_by_skill_level,
	get_student_counts_by_course,
	get_student_counts_by_skill_level,
	get_students,
	get_students_by_course,
	get_students_by_skill_level,
	get_total_student_count,
)


load_dotenv()


class OpenAIConfigurationError(Exception):
	"""Kept for compatibility with the existing Flask import contract."""


class OpenAIServiceError(Exception):
	"""Raised when the local Ollama request cannot be completed safely."""


OLLAMA_DEFAULT_URL = "http://localhost:11434"
OLLAMA_DEFAULT_MODEL = "qwen3:8b"
SYSTEM_PROMPT = (
	"You are SkillSpring's friendly learning assistant. "
	"Explain concepts clearly for beginners using simple language and concise practical examples. "
	"Use step-by-step explanations when helpful. Support Python, Java, JavaScript, SQL, "
	"web development, AI, and related technical learning. Avoid unnecessary length. "
	"Format requested code in code blocks. Never reveal internal configuration, API keys, "
	"environment variables, or server details. "
	"For student-related questions, use only the supplied SkillSpring student data. "
	"When available, you may show only Student ID, Student name, Course, Skill level, and Registration date. "
	"Never reveal email addresses or phone numbers. Do not invent student information. "
	"If the requested record is not present in the provided context, say 'No matching student was found.'"
)


def get_ai_response(user_message, history=None, role="user"):
	"""Send a learner message to the local Ollama model with a role-aware context."""
	base_url = os.getenv("OLLAMA_BASE_URL", OLLAMA_DEFAULT_URL).rstrip("/")
	model = os.getenv("OLLAMA_MODEL", OLLAMA_DEFAULT_MODEL)
	conversation = _clean_history(history)
	if not conversation or conversation[-1] != {"role": "user", "content": user_message}:
		conversation.append({"role": "user", "content": user_message})
	request_body = {
		"model": model,
		"messages": [
			{"role": "system", "content": _system_message(user_message, history, role)},
			*conversation,
		],
		"stream": False,
		"think": False,
		"options": {
			"num_predict": 300,
			"temperature": 0.3,
		},
	}

	request = Request(
		f"{base_url}/api/chat",
		data=json.dumps(request_body).encode("utf-8"),
		headers={"Content-Type": "application/json"},
		method="POST",
	)

	try:
		with urlopen(request, timeout=120) as response:
			response_data = json.loads(response.read().decode("utf-8"))
	except HTTPError as error:
		raise OpenAIServiceError from error
	except (
		URLError,
		TimeoutError,
		OSError,
		ValueError,
		UnicodeDecodeError,
		json.JSONDecodeError,
	) as error:
		raise OpenAIServiceError from error

	try:
		reply = response_data["message"]["content"]
	except (KeyError, TypeError) as error:
		raise OpenAIServiceError from error

	if not isinstance(reply, str) or not reply.strip():
		raise OpenAIServiceError

	return reply.strip()


def _normalize_text(value):
	if not isinstance(value, str):
		return ""
	filtered = re.sub(r"[^a-z0-9\s\-#&./]", " ", value.lower())
	filtered = re.sub(r"\s+", " ", filtered)
	return filtered.strip()


def _detect_course_alias(text, courses):
	text_norm = _normalize_text(text)
	aliases = {
		"js": "JavaScript",
		"javascript": "JavaScript",
		"java script": "JavaScript",
		"python": "Python",
		"java": "Java",
		"react": "React",
		"reactjs": "React",
		"react js": "React",
		"data science": "Data Science",
		"ds": "Data Science",
		"machine learning": "Machine Learning",
		"ml": "Machine Learning",
		"genai": "Generative AI",
		"generative ai": "Generative AI",
		"cloud": "Cloud Computing",
		"cloud computing": "Cloud Computing",
	}
	for alias, course in aliases.items():
		if alias in text_norm and course in courses:
			return course
	for course in sorted(courses, key=len, reverse=True):
		if _normalize_text(course) in text_norm:
			return course
	return None


def _detect_skill_alias(text, skill_levels):
	text_norm = _normalize_text(text)
	aliases = {
		"beginner": "Beginner",
		"beginners": "Beginner",
		"basic": "Beginner",
		"new learner": "Beginner",
		"intermediate": "Intermediate",
		"mid level": "Intermediate",
		"mid-level": "Intermediate",
		"advanced": "Advanced",
		"expert": "Advanced",
		"experienced": "Advanced",
	}
	for alias, skill in aliases.items():
		if alias in text_norm and skill in skill_levels:
			return skill
	for skill in skill_levels:
		if _normalize_text(skill) in text_norm:
			return skill
	return None


def _extract_name_from_text(text, available_names):
	text_norm = _normalize_text(text)
	for name in sorted(available_names, key=len, reverse=True):
		norm_name = _normalize_text(name)
		if norm_name in text_norm or text_norm.startswith(norm_name) or text_norm.endswith(norm_name):
			return name
	for phrase in [
		"rishi",
		"akash",
		"munna",
	]:
		if phrase in text_norm:
			for name in available_names:
				if phrase in _normalize_text(name):
					return name
	return None


def _detect_intent(user_message, history=None):
	text = _normalize_text(user_message)
	combined_history = " ".join(
		_normalize_text(item.get("content", ""))
		for item in _clean_history(history)
		if item.get("role") == "user"
	)
	combined = f"{combined_history} {text}".strip()
	courses = get_available_courses()
	skill_levels = get_available_skill_levels()
	course_match = _detect_course_alias(combined, courses)
	skill_match = _detect_skill_alias(combined, skill_levels)
	name_candidates = [student["name"] for student in get_students(include_sensitive=False)]
	student_name = _extract_name_from_text(combined, name_candidates)

	has_student_terms = any(term in text for term in ["student", "students", "learner", "learners", "enrolled", "registered", "member", "members"]) 
	has_count_terms = any(term in text for term in ["how many", "count", "total", "number", "current", "enrollment"]) 
	has_list_terms = any(term in text for term in ["show", "list", "give", "tell", "who", "provide", "display", "names", "find"]) 
	has_detail_terms = any(term in text for term in ["detail", "details", "info", "information", "profile", "about", "tell me about"]) 
	has_contact_terms = any(term in text for term in ["email", "phone", "contact", "mobile"]) 

	if has_contact_terms and has_student_terms:
		return {
			"intent": "STUDENT_CONTACTS",
			"course": course_match,
			"skill_level": skill_match,
			"student_name": student_name,
		}

	if any(term in text for term in ["what is skillspring", "what can i do on this website", "what can the chatbot do", "how does the chatbot work", "skillspring website", "this website", "this site"]):
		return {"intent": "GENERAL_WEBSITE_INFORMATION", "course": None, "skill_level": None, "student_name": None}

	if "course" in text and any(term in text for term in ["available", "offer", "offered", "list", "show", "what courses", "which courses"]):
		return {"intent": "COURSE_LIST", "course": None, "skill_level": None, "student_name": None}

	if (has_count_terms and has_student_terms and not course_match and not skill_match) or ("enrollment" in text and "student" in text):
		return {"intent": "TOTAL_STUDENTS", "course": course_match, "skill_level": skill_match, "student_name": student_name}

	if (
		(has_student_terms and has_list_terms and not has_contact_terms and not has_detail_terms) or
		any(term in text for term in [
			"show all enrolled students",
			"list all registered students",
			"give me all student names",
			"who are the enrolled students",
			"show me the names of all learners",
			"all enrolled students",
			"registered students",
			"all student names",
		])
	):
		return {"intent": "STUDENT_NAMES", "course": course_match, "skill_level": skill_match, "student_name": student_name}

	if student_name and (
		course_match or has_detail_terms or any(term in text for term in ["find", "search", "learn", "learning", "studying", "course", "skill level", "is enrolled", "enrolled"]) or "tell me about" in text
	):
		return {"intent": "STUDENT_DETAILS", "course": course_match, "skill_level": skill_match, "student_name": student_name}

	if student_name and has_contact_terms:
		return {"intent": "STUDENT_CONTACTS", "course": course_match, "skill_level": skill_match, "student_name": student_name}

	if course_match and has_student_terms and (has_count_terms or has_list_terms):
		return {"intent": "COURSE_STUDENTS", "course": course_match, "skill_level": skill_match, "student_name": student_name}

	if skill_match and has_student_terms and (has_count_terms or has_list_terms):
		return {"intent": "SKILL_STATISTICS", "course": course_match, "skill_level": skill_match, "student_name": student_name}

	if any(term in text for term in ["course statistics", "enrollment by course", "course counts", "how many students in each course", "how many students in", "distribution by course"]) or ("course" in text and any(term in text for term in ["statistics", "distribution", "counts"])):
		return {"intent": "COURSE_STATISTICS", "course": course_match, "skill_level": skill_match, "student_name": student_name}

	if any(term in text for term in ["recently", "latest students", "new students", "joined recently", "joined today", "newly registered", "latest enrollment", "recent enrollment", "who joined", "recent students"]) or ("recent" in text and has_student_terms):
		return {"intent": "RECENT_STUDENTS", "course": course_match, "skill_level": skill_match, "student_name": student_name}

	if has_student_terms and has_list_terms and not any(term in text for term in ["course", "skill"]):
		return {"intent": "STUDENT_NAMES", "course": course_match, "skill_level": skill_match, "student_name": student_name}

	if "website" in text or "skillspring" in text or "this site" in text:
		return {"intent": "GENERAL_WEBSITE_INFORMATION", "course": None, "skill_level": None, "student_name": None}

	return {"intent": "GENERAL_AI", "course": None, "skill_level": None, "student_name": None}


def _build_student_context(role_name, intent_info, students=None, course=None, skill_level=None, name=None):
	context_lines = [
		"SKILLSPRING DATABASE CONTEXT",
		f"User role: {role_name}",
		f"Question intent: {intent_info.get('intent', 'UNKNOWN')}",
	]
	if course:
		context_lines.append(f"Course: {course}")
	if skill_level:
		context_lines.append(f"Skill level: {skill_level}")
	if name:
		context_lines.append(f"Student name: {name}")
	if students is None:
		students = []
	if students:
		context_lines.append("Students:")
		for index, student in enumerate(students, start=1):
			if hasattr(student, "keys"):
				student = {key: student[key] for key in student.keys()}
			elif not isinstance(student, dict):
				student = {}
			parts = []
			if "count" in student:
				parts.append(f"Count: {student['count']}")
			if "total" in student:
				parts.append(f"Total: {student['total']}")
			if "id" in student:
				parts.append(f"Student ID: {student['id']}")
			if "name" in student:
				parts.append(f"Name: {student['name']}")
			if role_name == "admin":
				for field in ("email", "phone"):
					if field in student:
						parts.append(f"{field.title()}: {student[field] or 'N/A'}")
			if "course" in student:
				parts.append(f"Course: {student['course']}")
			if "skill_level" in student:
				parts.append(f"Skill level: {student['skill_level']}")
			if "created_at" in student:
				parts.append(f"Registration date: {student['created_at']}")
			context_lines.append(f"{index}. " + " | ".join(parts))
	else:
		context_lines.append("Students: none found in the current SkillSpring database context.")
	context_lines.append("Available courses: " + ", ".join(get_available_courses()))
	context_lines.append("Available skill levels: " + ", ".join(get_available_skill_levels()))
	context_lines.append("Answer only using the supplied SkillSpring context. Do not invent missing records.")
	return "\n".join(context_lines)


def build_skill_spring_context(user_message, history=None, role="user"):
	"""Build a compact, role-aware SkillSpring context for the current user query."""
	role_name = (role or "user").lower()
	if role_name not in {"admin", "user"}:
		role_name = "user"
	intent_info = _detect_intent(user_message, history)
	intent = intent_info.get("intent", "GENERAL_AI")
	course = intent_info.get("course")
	skill_level = intent_info.get("skill_level")
	name = intent_info.get("student_name")

	if intent == "GENERAL_AI":
		return ""
	if intent == "GENERAL_WEBSITE_INFORMATION":
		return (
			"SkillSpring is an EdTech learning management application for managing learner information, "
			"courses, and skill levels. It supports student registration, student data viewing, "
			"course and skill tracking, and an AI-powered assistant for questions about the app."
		)
	if intent in {"COURSE_LIST"}:
		return _build_student_context(role_name, intent_info, students=[], course=None, skill_level=None, name=None)
	if intent in {"SKILL_LEVEL_LIST", "SKILL_STATISTICS"}:
		return _build_student_context(role_name, intent_info, students=[], course=None, skill_level=skill_level or None, name=None)
	if intent in {"TOTAL_STUDENTS", "STUDENT_COUNT"}:
		count = get_total_student_count()
		return _build_student_context(role_name, intent_info, students=[{"count": count}], course=course, skill_level=skill_level, name=name)
	if intent in {"STUDENT_NAMES", "STUDENT_LIST"}:
		students = get_students(include_sensitive=(role_name == "admin"))
		return _build_student_context(role_name, intent_info, students=students, course=course, skill_level=skill_level, name=name)
	if intent in {"STUDENT_DETAILS", "STUDENT_SEARCH"}:
		if name:
			students = get_student_by_name(name, include_sensitive=(role_name == "admin"))
			return _build_student_context(role_name, intent_info, students=students, course=course, skill_level=skill_level, name=name)
		students = get_students(include_sensitive=(role_name == "admin"))
		return _build_student_context(role_name, intent_info, students=students, course=course, skill_level=skill_level, name=name)
	if intent in {"COURSE_STUDENTS", "STUDENTS_BY_COURSE"}:
		if not course:
			return "The requested course could not be matched to the available SkillSpring courses."
		students = get_students_by_course(course, include_sensitive=(role_name == "admin"))
		return _build_student_context(role_name, intent_info, students=students, course=course, skill_level=skill_level, name=name)
	if intent in {"SKILL_STUDENTS", "STUDENTS_BY_SKILL_LEVEL"}:
		if not skill_level:
			return "The requested skill level could not be matched to the available SkillSpring skill levels."
		students = get_students_by_skill_level(skill_level, include_sensitive=(role_name == "admin"))
		return _build_student_context(role_name, intent_info, students=students, course=course, skill_level=skill_level, name=name)
	if intent == "COURSE_STATISTICS":
		stats = get_student_counts_by_course()
		return _build_student_context(role_name, intent_info, students=[{"course": row["course"], "total": row["total"]} for row in stats], course=course, skill_level=skill_level, name=name)
	if intent == "SKILL_STATISTICS":
		stats = get_student_counts_by_skill_level()
		return _build_student_context(role_name, intent_info, students=[{"skill_level": row["skill_level"], "total": row["total"]} for row in stats], course=course, skill_level=skill_level, name=name)
	if intent == "RECENT_STUDENTS":
		students = get_recent_students(limit=10)
		return _build_student_context(role_name, intent_info, students=students, course=course, skill_level=skill_level, name=name)
	if intent == "STUDENT_CONTACTS":
		if role_name != "admin":
			return "Email and phone information is available only to administrators. I can provide the student's name, course, and skill level."
		students = get_students(include_sensitive=True)
		return _build_student_context(role_name, intent_info, students=students, course=course, skill_level=skill_level, name=name)
	return ""


def _system_message(user_message, history, role="user"):
	context = build_skill_spring_context(user_message, history, role)
	if not context:
		return SYSTEM_PROMPT
	return (
		f"{SYSTEM_PROMPT}\n\n"
		"For SkillSpring-specific questions, use only the supplied SkillSpring database context. "
		"Do not invent missing counts, student names, courses, or student details. "
		"If the context says information is unavailable, say so clearly. "
		"For non-website questions, answer as general educational guidance.\n\n"
		f"SkillSpring context:\n{context}"
	)


def _asks_about_courses(question):
	return "course" in question and any(
		phrase in question for phrase in ("available", "offer", "list", "teach", "details")
	)


def _asks_about_all_courses(question):
	return any(
		phrase in question
		for phrase in (
			"all courses",
			"list all courses",
			"all course details",
			"courses details",
			"fetch all courses",
			"show all courses",
		)
	)


def _asks_about_all_course_students(question):
	return any(
		phrase in question
		for phrase in (
			"all courses and enrolled students",
			"all course details and enrolled students",
			"courses details and enrolled students",
			"all courses details and enrolled students",
			"students name and their courses",
			"enrolled students name and their courses",
			"all students and their courses",
		)
	)


def _asks_about_skill_levels(question):
	return "skill level" in question and any(
		phrase in question for phrase in ("available", "offer", "list")
	)


def _asks_about_total_students(question):
	return (
		("how many" in question or "count" in question)
		and "student" in question
		and not any(level in question for level in ("beginner", "intermediate", "advanced"))
		and not _find_course(question, get_available_courses())
		and not any(phrase in question for phrase in ("enrolled in", "students in"))
	)


def _asks_about_course_students(question):
	return any(
		phrase in question
		for phrase in ("student", "enrolled", "skill level", "their")
	)


def _asks_about_skill_students(question):
	return "student" in question or "registered" in question


def _asks_about_website(question):
	return any(
		phrase in question
		for phrase in ("skillspring", "this website", "this site", "information available")
	)


def _asks_about_all_students(question):
	return any(
		phrase in question
		for phrase in (
			"all students",
			"list all students",
			"show all students",
			"all registered students",
			"student records",
			"registered students",
		)
	)


def _find_course(search_text, courses):
	return next(
		(
			course
			for course in sorted(courses, key=len, reverse=True)
			if re.search(rf"\b{re.escape(course.lower())}\b", search_text)
		),
		None,
	)


def _find_skill_level(search_text, skill_levels):
	return next((level for level in skill_levels if level.lower() in search_text), None)


def _mentions_unknown_course(search_text, courses):
	return (
		any(phrase in search_text for phrase in ("enrolled in", "students in"))
		and not _find_course(search_text, courses)
	)


def _extract_unknown_course(search_text, courses):
	match = re.search(r"(?:enrolled in|students in|course)\s+([a-z][a-z0-9+#& -]*)", search_text)
	if not match:
		return None
	value = match.group(1).strip(" .?!")
	for course in courses:
		if course.lower() == value:
			return None
	return value.title()


def _find_student_name(question):
	match = re.search(
		r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)(?:'s|\s+is|\s+enrolled|\?)",
		question,
	)
	return match.group(1).strip() if match else None


def _clean_history(history):
	"""Keep only a small, valid conversation supplied by the browser."""
	if not isinstance(history, list):
		return []

	cleaned_history = []
	for item in history[-20:]:
		if not isinstance(item, dict):
			continue
		role = item.get("role")
		content = item.get("content")
		if role in {"user", "assistant"} and isinstance(content, str):
			content = content.strip()
			if content and len(content) <= 4000:
				cleaned_history.append({"role": role, "content": content})
	return cleaned_history
