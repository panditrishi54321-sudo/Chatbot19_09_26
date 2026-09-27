import json
import re
import sqlite3
from pathlib import Path

from werkzeug.security import generate_password_hash


DATABASE_FOLDER = Path(__file__).resolve().parent
DATABASE_PATH = DATABASE_FOLDER / "skillspring.db"
SCHEMA_PATH = DATABASE_FOLDER / "schema.sql"
AVAILABLE_COURSES = (
	"Python",
	"Java",
	"JavaScript",
	"React",
	"Data Science",
	"Machine Learning",
	"Generative AI",
	"Cloud Computing",
)
AVAILABLE_SKILL_LEVELS = ("Beginner", "Intermediate", "Advanced")


def normalize_student_name(value):
	"""Normalize a student name for duplicate checking and searching."""
	if value is None:
		return ""
	return " ".join(str(value).strip().lower().split())


def normalize_email(value):
	"""Normalize an email address before comparing or storing it."""
	if value is None:
		return ""
	return str(value).strip().lower()


def normalize_phone(value):
	"""Normalize a phone number to a comparable digits-only form."""
	if value is None:
		return ""
	digits = re.sub(r"\D", "", str(value).strip())
	if len(digits) >= 11 and digits.startswith("0"):
		digits = digits[1:]
	return digits


def validate_student_data(name, email, phone, course, skill_level):
	"""Validate all student input on the server before insertion or update."""
	clean_name = (name or "").strip()
	if not clean_name or len(clean_name) < 2 or len(clean_name) > 120:
		raise ValueError("Please enter a valid student name.")
	if not normalize_student_name(clean_name):
		raise ValueError("Please enter a valid student name.")

	clean_email = normalize_email(email)
	if not clean_email or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", clean_email):
		raise ValueError("Please enter a valid email address.")
	if len(clean_email) > 254:
		raise ValueError("Please enter a valid email address.")

	clean_phone = normalize_phone(phone)
	if phone and phone.strip() and not clean_phone:
		raise ValueError("Please enter a valid phone number.")
	if clean_phone and (len(clean_phone) < 7 or len(clean_phone) > 15):
		raise ValueError("Please enter a valid phone number.")

	if course not in AVAILABLE_COURSES:
		raise ValueError("Please choose a valid course.")
	if skill_level not in AVAILABLE_SKILL_LEVELS:
		raise ValueError("Please choose a valid skill level.")

	return {
		"name": clean_name,
		"email": clean_email,
		"phone": clean_phone or None,
		"course": course,
		"skill_level": skill_level,
		"name_normalized": normalize_student_name(clean_name),
		"email_normalized": clean_email,
		"phone_normalized": clean_phone or None,
	}


def get_connection():
	"""Open a database connection and return rows as dictionary-like objects."""
	connection = sqlite3.connect(DATABASE_PATH)
	connection.row_factory = sqlite3.Row
	return connection


def _ensure_student_schema_columns():
	"""Add normalized columns to the existing students table without removing data."""
	with get_connection() as connection:
		columns = {
			row["name"] for row in connection.execute("PRAGMA table_info(students)").fetchall()
		}
		if "name_normalized" not in columns:
			connection.execute(
				"ALTER TABLE students ADD COLUMN name_normalized TEXT"
			)
		if "email_normalized" not in columns:
			connection.execute(
				"ALTER TABLE students ADD COLUMN email_normalized TEXT"
			)
		if "phone_normalized" not in columns:
			connection.execute(
				"ALTER TABLE students ADD COLUMN phone_normalized TEXT"
			)
		if "updated_at" not in columns:
			connection.execute(
				"ALTER TABLE students ADD COLUMN updated_at TEXT"
			)
		if "status" not in columns:
			connection.execute(
				"ALTER TABLE students ADD COLUMN status TEXT NOT NULL DEFAULT 'active'"
			)

		connection.execute(
			"UPDATE students SET name_normalized = ?, email_normalized = ?, phone_normalized = ? WHERE id = ?",
			("", "", "", -1),
		)

		for student in connection.execute(
			"SELECT id, name, email, phone FROM students WHERE status IS NULL OR status = '' OR status = 'active'"
		).fetchall():
			connection.execute(
				"UPDATE students SET name_normalized = ?, email_normalized = ?, phone_normalized = ?, status = 'active', updated_at = COALESCE(updated_at, created_at) WHERE id = ?",
				(
					normalize_student_name(student["name"]),
					normalize_email(student["email"]),
					normalize_phone(student["phone"]),
					student["id"],
				),
			)


def _ensure_student_indexes():
	"""Create safe indexes for normalized search fields without forcing unique constraints yet."""
	with get_connection() as connection:
		connection.execute(
			"CREATE INDEX IF NOT EXISTS idx_students_name_normalized ON students(name_normalized)"
		)
		connection.execute(
			"CREATE INDEX IF NOT EXISTS idx_students_email_normalized ON students(email_normalized)"
		)
		connection.execute(
			"CREATE INDEX IF NOT EXISTS idx_students_phone_normalized ON students(phone_normalized)"
		)
		connection.execute(
			"CREATE INDEX IF NOT EXISTS idx_students_course ON students(course)"
		)
		connection.execute(
			"CREATE INDEX IF NOT EXISTS idx_students_skill_level ON students(skill_level)"
		)


def init_db():
	"""Create the database tables and seed demo users when the app starts."""
	schema = SCHEMA_PATH.read_text(encoding="utf-8")
	with get_connection() as connection:
		connection.executescript(schema)
	_ensure_student_schema_columns()
	_ensure_student_indexes()
	_ensure_default_users()


def _ensure_default_users():
	"""Create safe development demo accounts if they do not exist."""
	with get_connection() as connection:
		for name, username, password, role in (
			(
				"SkillSpring Admin",
				"admin@skillspring.local",
				"Admin@123",
				"admin",
			),
			(
				"Demo Admin",
				"admin@skillspring.com",
				"Admin@123",
				"admin",
			),
			(
				"Demo User",
				"user@skillspring.local",
				"User@123",
				"user",
			),
		):
			existing = connection.execute(
				"SELECT id FROM users WHERE username = ?",
				(username,),
			).fetchone()
			if existing is None:
				connection.execute(
					"""
					INSERT INTO users (name, username, password_hash, role)
					VALUES (?, ?, ?, ?)
					""",
					(name, username, generate_password_hash(password), role),
				)


def find_duplicate_student(name, email, phone, exclude_id=None):
	"""Return the first duplicate match for name/email/phone without mutating data."""
	with get_connection() as connection:
		return _find_duplicate_student_in_connection(
			connection,
			name,
			email,
			phone,
			exclude_id=exclude_id,
		)


def get_duplicate_report():
	"""Return the existing duplicate-finding report without deleting database rows."""
	with get_connection() as connection:
		duplicate_names = connection.execute(
			"SELECT name, COUNT(*) AS count FROM students WHERE status != 'deleted' GROUP BY name_normalized HAVING COUNT(*) > 1 ORDER BY count DESC, name"
		).fetchall()
		duplicate_emails = connection.execute(
			"SELECT email, COUNT(*) AS count FROM students WHERE status != 'deleted' GROUP BY email_normalized HAVING COUNT(*) > 1 ORDER BY count DESC, email"
		).fetchall()
		duplicate_phones = connection.execute(
			"SELECT phone, COUNT(*) AS count FROM students WHERE status != 'deleted' AND phone_normalized IS NOT NULL GROUP BY phone_normalized HAVING COUNT(*) > 1 ORDER BY count DESC, phone"
		).fetchall()
		return {
			"duplicate_names": [dict(row) for row in duplicate_names],
			"duplicate_emails": [dict(row) for row in duplicate_emails],
			"duplicate_phones": [dict(row) for row in duplicate_phones],
		}


def log_audit_event(action, actor_user_id=None, student_id=None, details=None):
	"""Record admin actions against student records for compliance and auditing."""
	payload = json.dumps(details or {}, ensure_ascii=True) if details is not None else None
	with get_connection() as connection:
		connection.execute(
			"""
			INSERT INTO audit_logs (actor_user_id, action, student_id, details_json, created_at)
			VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
			""",
			(actor_user_id, action, student_id, payload),
		)
		return True


def get_audit_logs(limit=20):
	"""Return recent admin activity as a simple audit log for the dashboard."""
	with get_connection() as connection:
		return connection.execute(
			"""
			SELECT a.id, a.action, a.student_id, a.details_json, a.created_at,
			       u.name AS actor_name
			FROM audit_logs a
			LEFT JOIN users u ON u.id = a.actor_user_id
			ORDER BY a.id DESC
			LIMIT ?
			""",
			(limit,),
		).fetchall()


def _find_duplicate_student_in_connection(connection, name, email, phone, exclude_id=None):
	"""Check for duplicate names, emails, and phone numbers inside the current database transaction."""
	name_value = normalize_student_name(name)
	email_value = normalize_email(email)
	phone_value = normalize_phone(phone)
	base_clause = "status != 'deleted'"

	if name_value:
		name_match = connection.execute(
			f"SELECT id, name FROM students WHERE {base_clause} AND name_normalized = ? AND (? IS NULL OR id != ?)",
			(name_value, exclude_id, exclude_id),
		).fetchone()
		if name_match is not None:
			return {
				"field": "name",
				"message": "Student name already exists. Please check the existing student record.",
				"duplicate_id": name_match["id"],
				"duplicate_name": name_match["name"],
			}

	if email_value:
		email_match = connection.execute(
			f"SELECT id, email FROM students WHERE {base_clause} AND email_normalized = ? AND (? IS NULL OR id != ?)",
			(email_value, exclude_id, exclude_id),
		).fetchone()
		if email_match is not None:
			return {
				"field": "email",
				"message": "This email address is already registered.",
				"duplicate_id": email_match["id"],
				"duplicate_email": email_match["email"],
			}

	if phone_value:
		phone_match = connection.execute(
			f"SELECT id, phone FROM students WHERE {base_clause} AND phone_normalized = ? AND (? IS NULL OR id != ?)",
			(phone_value, exclude_id, exclude_id),
		).fetchone()
		if phone_match is not None:
			return {
				"field": "phone",
				"message": "This phone number is already registered.",
				"duplicate_id": phone_match["id"],
				"duplicate_phone": phone_match["phone"],
			}
	return None


def create_student(name, email, phone, course, skill_level):
	"""Save one student only after strong validation and duplicate checks."""
	data = validate_student_data(name, email, phone, course, skill_level)
	with get_connection() as connection:
		duplicate = _find_duplicate_student_in_connection(
			connection,
			data["name"],
			data["email"],
			data["phone"] or "",
		)
		if duplicate is not None:
			raise ValueError(duplicate["message"])
		cursor = connection.execute(
			"""
			INSERT INTO students (
				name, name_normalized, email, email_normalized, phone, phone_normalized,
				course, skill_level, created_at, updated_at, status
			)
			VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'active')
			""",
			(
				data["name"],
				data["name_normalized"],
				data["email"],
				data["email_normalized"],
				data["phone"],
				data["phone_normalized"],
				data["course"],
				data["skill_level"],
			),
		)
		return cursor.lastrowid


def get_all_students(search=None, course=None, skill_level=None, include_deleted=False, status=None, limit=None, offset=0):
	"""Return student rows for admin-only access, optionally filtered."""
	query = """
		SELECT id, name, email, phone, course, skill_level, created_at, status
		FROM students
		WHERE 1 = 1
	"""
	params = []
	if status is not None:
		query += " AND status = ?"
		params.append(status)
	elif not include_deleted:
		query += " AND status != 'deleted'"
	if search:
		normalized_search = " ".join((search or "").strip().split())
		search_pattern = f"%{normalized_search}%"
		query += " AND (name LIKE ? COLLATE NOCASE OR email LIKE ? COLLATE NOCASE OR phone LIKE ? COLLATE NOCASE OR course LIKE ? COLLATE NOCASE)"
		params.extend([search_pattern, search_pattern, search_pattern, search_pattern])
	if course:
		query += " AND course = ?"
		params.append(course)
	if skill_level:
		query += " AND skill_level = ?"
		params.append(skill_level)
	query += " ORDER BY id DESC"
	if limit is not None:
		query += " LIMIT ? OFFSET ?"
		params.extend([limit, offset])
	with get_connection() as connection:
		return connection.execute(query, params).fetchall()


def count_students(search=None, course=None, skill_level=None, include_deleted=False, status=None):
	"""Count rows that match the request filters without loading the full dataset."""
	query = "SELECT COUNT(*) FROM students WHERE 1 = 1"
	params = []
	if status is not None:
		query += " AND status = ?"
		params.append(status)
	elif not include_deleted:
		query += " AND status != 'deleted'"
	if search:
		normalized_search = " ".join((search or "").strip().split())
		search_pattern = f"%{normalized_search}%"
		query += " AND (name LIKE ? COLLATE NOCASE OR email LIKE ? COLLATE NOCASE OR phone LIKE ? COLLATE NOCASE OR course LIKE ? COLLATE NOCASE)"
		params.extend([search_pattern, search_pattern, search_pattern, search_pattern])
	if course:
		query += " AND course = ?"
		params.append(course)
	if skill_level:
		query += " AND skill_level = ?"
		params.append(skill_level)
	with get_connection() as connection:
		return connection.execute(query, params).fetchone()[0]


def get_students(include_sensitive=False, search=None, course=None, skill_level=None, include_deleted=False, status=None, limit=None, offset=0):
	"""Return student rows with a role-aware projection for admin or public use."""
	columns = "id, name, course, skill_level, created_at"
	if include_sensitive:
		columns = "id, name, email, phone, course, skill_level, created_at"
	query = f"SELECT {columns} FROM students WHERE 1 = 1"
	params = []
	if status is not None:
		query += " AND status = ?"
		params.append(status)
	elif not include_deleted:
		query += " AND status != 'deleted'"
	if search:
		normalized_search = " ".join((search or "").strip().split())
		search_pattern = f"%{normalized_search}%"
		query += " AND (name LIKE ? COLLATE NOCASE OR email LIKE ? COLLATE NOCASE OR phone LIKE ? COLLATE NOCASE OR course LIKE ? COLLATE NOCASE)"
		params.extend([search_pattern, search_pattern, search_pattern, search_pattern])
	if course:
		query += " AND course = ?"
		params.append(course)
	if skill_level:
		query += " AND skill_level = ?"
		params.append(skill_level)
	query += " ORDER BY id DESC"
	if limit is not None:
		query += " LIMIT ? OFFSET ?"
		params.extend([limit, offset])
	with get_connection() as connection:
		return connection.execute(query, params).fetchall()


def get_public_students():
	"""Return student rows without contact information for general users."""
	return get_students(include_sensitive=False)


def get_total_student_count():
	"""Compatibility alias for the total number of students."""
	return get_total_students()


def get_course_counts():
	"""Return course-wise student counts."""
	return get_student_counts_by_course()


def get_skill_level_counts():
	"""Return skill-level-wise student counts."""
	return get_student_counts_by_skill_level()


def get_total_students(include_deleted=False, status=None):
	"""Return the total number of student rows, optionally including deleted records or filtering by status."""
	query = "SELECT COUNT(*) FROM students WHERE 1 = 1"
	params = []
	if status is not None:
		query += " AND status = ?"
		params.append(status)
	elif not include_deleted:
		query += " AND status != 'deleted'"
	with get_connection() as connection:
		return connection.execute(query, params).fetchone()[0]


def get_deleted_students(search=None, course=None, skill_level=None):
	"""Return soft-deleted student records for admin review and restore actions."""
	return get_all_students(search=search, course=course, skill_level=skill_level, status="deleted")


def get_total_courses():
	"""Return the number of available courses configured by the app."""
	return len(AVAILABLE_COURSES)


def get_student_counts_by_course(include_deleted=False):
	"""Return a count of students grouped by course."""
	query = """
		SELECT course, COUNT(*) AS total
		FROM students
		WHERE 1 = 1
	"""
	params = []
	if not include_deleted:
		query += " AND status != 'deleted'"
	query += " GROUP BY course ORDER BY total DESC, course ASC"
	with get_connection() as connection:
		return connection.execute(query, params).fetchall()


def get_student_counts_by_skill_level(include_deleted=False):
	"""Return a count of students grouped by skill level."""
	query = """
		SELECT skill_level, COUNT(*) AS total
		FROM students
		WHERE 1 = 1
	"""
	params = []
	if not include_deleted:
		query += " AND status != 'deleted'"
	query += " GROUP BY skill_level ORDER BY total DESC, skill_level ASC"
	with get_connection() as connection:
		return connection.execute(query, params).fetchall()


def get_recent_students(limit=5, include_deleted=False):
	"""Return the newest student records for the dashboard."""
	query = """
		SELECT id, name, email, phone, course, skill_level, created_at, status
		FROM students
		WHERE 1 = 1
	"""
	params = []
	if not include_deleted:
		query += " AND status != 'deleted'"
	query += " ORDER BY id DESC LIMIT ?"
	params.append(limit)
	with get_connection() as connection:
		return connection.execute(query, params).fetchall()


def delete_student(student_id):
	"""Soft-delete a student row by ID while preserving the record for audit and restore flows."""
	with get_connection() as connection:
		cursor = connection.execute(
			"UPDATE students SET status = 'deleted', updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status != 'deleted'",
			(student_id,),
		)
		return cursor.rowcount


def delete_student_by_id(student_id):
	"""Compatibility wrapper for the admin delete route."""
	return delete_student(student_id)


def soft_delete_student_by_id(student_id):
	"""Alias for the soft-delete action used by the admin workflow."""
	return delete_student_by_id(student_id)


def restore_student_by_id(student_id):
	"""Restore a soft-deleted student record so it returns to the active dataset."""
	with get_connection() as connection:
		cursor = connection.execute(
			"UPDATE students SET status = 'active', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
			(student_id,),
		)
		return cursor.rowcount


def soft_restore_student_by_id(student_id):
	"""Alias for the restore pathway used by the admin workflow."""
	return restore_student_by_id(student_id)


def get_student_count():
	"""Return the total number of registered students."""
	with get_connection() as connection:
		return connection.execute("SELECT COUNT(*) FROM students").fetchone()[0]


def get_student_count_by_course(course):
	"""Return the number of active students enrolled in one course."""
	with get_connection() as connection:
		return connection.execute(
			"SELECT COUNT(*) FROM students WHERE course = ? AND status != 'deleted'", (course,)
		).fetchone()[0]


def get_student_count_by_skill_level(skill_level):
	"""Return the number of active students at one skill level."""
	with get_connection() as connection:
		return connection.execute(
			"SELECT COUNT(*) FROM students WHERE skill_level = ? AND status != 'deleted'", (skill_level,)
		).fetchone()[0]


def get_students_by_course(course, include_sensitive=False):
	"""Return student entries for one course with a role-aware projection."""
	columns = "name, course, skill_level"
	if include_sensitive:
		columns = "id, name, email, phone, course, skill_level, created_at"
	with get_connection() as connection:
		return connection.execute(
			f"""
			SELECT {columns}
			FROM students
			WHERE course = ? AND status != 'deleted'
			ORDER BY name COLLATE NOCASE
			""",
			(course,),
		).fetchall()


def get_students_by_skill_level(skill_level, include_sensitive=False):
	"""Return student entries for one skill level with a role-aware projection."""
	columns = "name, course, skill_level"
	if include_sensitive:
		columns = "id, name, email, phone, course, skill_level, created_at"
	with get_connection() as connection:
		return connection.execute(
			f"""
			SELECT {columns}
			FROM students
			WHERE skill_level = ? AND status != 'deleted'
			ORDER BY name COLLATE NOCASE
			""",
			(skill_level,),
		).fetchall()


def get_student_by_name(name, include_sensitive=False):
	"""Return student entries matching the given name with role-aware projection."""
	columns = "id, name, course, skill_level, created_at"
	if include_sensitive:
		columns = "id, name, email, phone, course, skill_level, created_at"
	with get_connection() as connection:
		return connection.execute(
			f"""
			SELECT {columns}
			FROM students
			WHERE name LIKE ? COLLATE NOCASE AND status != 'deleted'
			ORDER BY name COLLATE NOCASE
			""",
			(f"%{name}%",),
		).fetchall()


def find_students_by_name(name):
	"""Backward-compatible alias for student name lookups."""
	return get_student_by_name(name, include_sensitive=False)


def get_student_by_id(student_id, include_deleted=False):
	"""Return one complete student row by ID for admin editing."""
	query = """
		SELECT id, name, email, phone, course, skill_level, created_at, status
		FROM students
		WHERE id = ?
	"""
	params = [student_id]
	if not include_deleted:
		query += " AND status != 'deleted'"
	with get_connection() as connection:
		return connection.execute(query, params).fetchone()


def update_student(student_id, name, email, phone, course, skill_level):
	"""Update one student while preserving duplicate checks for the same record."""
	data = validate_student_data(name, email, phone, course, skill_level)
	with get_connection() as connection:
		duplicate = _find_duplicate_student_in_connection(
			connection,
			data["name"],
			data["email"],
			data["phone"] or "",
			exclude_id=student_id,
		)
		if duplicate is not None:
			raise ValueError(duplicate["message"])
		cursor = connection.execute(
			"""
			UPDATE students
			SET name = ?, name_normalized = ?, email = ?, email_normalized = ?, phone = ?, phone_normalized = ?, course = ?, skill_level = ?, updated_at = CURRENT_TIMESTAMP
			WHERE id = ?
			""",
			(
				data["name"],
				data["name_normalized"],
				data["email"],
				data["email_normalized"],
				data["phone"],
				data["phone_normalized"],
				data["course"],
				data["skill_level"],
				student_id,
			),
		)
		return cursor.rowcount


def get_user_by_username(username):
	"""Return a user record by username/email."""
	with get_connection() as connection:
		return connection.execute(
			"""
			SELECT id, name, username, password_hash, role, created_at
			FROM users
			WHERE username = ?
			""",
			(username,),
		).fetchone()


def get_user_by_id(user_id):
	"""Return a user record by user ID."""
	with get_connection() as connection:
		return connection.execute(
			"""
			SELECT id, name, username, password_hash, role, created_at
			FROM users
			WHERE id = ?
			""",
			(user_id,),
		).fetchone()


def get_available_courses():
	"""Return the courses offered by SkillSpring."""
	return AVAILABLE_COURSES


def get_available_skill_levels():
	"""Return the skill levels offered by SkillSpring."""
	return AVAILABLE_SKILL_LEVELS


def get_learning_state(owner_key):
	"""Return the current owner's Learning Hub notes and progress."""
	with get_connection() as connection:
		notes = connection.execute(
			"SELECT week_number, title, note_date, notes, important_points, doubts, practical_work, revision_points, next_goals, updated_at FROM learning_notes WHERE owner_key = ? ORDER BY week_number",
			(owner_key,),
		).fetchall()
		progress = connection.execute(
			"SELECT chapter_slug, status, bookmarked, updated_at FROM learning_progress WHERE owner_key = ?",
			(owner_key,),
		).fetchall()
		labs = connection.execute(
			"SELECT lab_slug, completed FROM learning_lab_progress WHERE owner_key = ?",
			(owner_key,),
		).fetchall()
		activity = connection.execute(
			"SELECT activity_date, chapter_slug FROM learning_activity WHERE owner_key = ? ORDER BY activity_date DESC",
			(owner_key,),
		).fetchall()
		return {
			"notes": [dict(row) for row in notes],
			"progress": [dict(row) for row in progress],
			"labs": [dict(row) for row in labs],
			"activity": [dict(row) for row in activity],
		}


def save_learning_note(owner_key, week_number, fields):
	"""Insert or update one private weekly note using bound SQL parameters."""
	with get_connection() as connection:
		connection.execute(
			"""
			INSERT INTO learning_notes (
				owner_key, week_number, title, note_date, notes, important_points,
				doubts, practical_work, revision_points, next_goals
			)
			VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
			ON CONFLICT(owner_key, week_number) DO UPDATE SET
				title = excluded.title,
				note_date = excluded.note_date,
				notes = excluded.notes,
				important_points = excluded.important_points,
				doubts = excluded.doubts,
				practical_work = excluded.practical_work,
				revision_points = excluded.revision_points,
				next_goals = excluded.next_goals,
				updated_at = CURRENT_TIMESTAMP
			""",
			(
				owner_key, week_number, fields["title"], fields["note_date"],
				fields["notes"], fields["important_points"], fields["doubts"],
				fields["practical_work"], fields["revision_points"], fields["next_goals"],
			),
		)
		return True


def delete_learning_note(owner_key, week_number):
	with get_connection() as connection:
		cursor = connection.execute(
			"DELETE FROM learning_notes WHERE owner_key = ? AND week_number = ?",
			(owner_key, week_number),
		)
		return cursor.rowcount > 0


def save_learning_progress(owner_key, chapter_slug, status, bookmarked):
	with get_connection() as connection:
		connection.execute(
			"""
			INSERT INTO learning_progress (owner_key, chapter_slug, status, bookmarked)
			VALUES (?, ?, ?, ?)
			ON CONFLICT(owner_key, chapter_slug) DO UPDATE SET
				status = excluded.status,
				bookmarked = excluded.bookmarked,
				updated_at = CURRENT_TIMESTAMP
			""",
			(owner_key, chapter_slug, status, int(bool(bookmarked))),
		)
		return True


def save_learning_lab_progress(owner_key, lab_slug, completed):
	with get_connection() as connection:
		connection.execute(
			"""
			INSERT INTO learning_lab_progress (owner_key, lab_slug, completed)
			VALUES (?, ?, ?)
			ON CONFLICT(owner_key, lab_slug) DO UPDATE SET
				completed = excluded.completed,
				updated_at = CURRENT_TIMESTAMP
			""",
			(owner_key, lab_slug, int(bool(completed))),
		)
		return True


def record_learning_activity(owner_key, chapter_slug=None):
	"""Record at most one streak day per owner while retaining the latest chapter."""
	with get_connection() as connection:
		connection.execute(
			"""
			INSERT INTO learning_activity (owner_key, activity_date, chapter_slug)
			VALUES (?, date('now', 'localtime'), ?)
			ON CONFLICT(owner_key, activity_date) DO UPDATE SET
				chapter_slug = COALESCE(excluded.chapter_slug, learning_activity.chapter_slug)
			""",
			(owner_key, chapter_slug),
		)
