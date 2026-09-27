import csv
import io
import os
import re
import secrets
import sqlite3
import time
from datetime import date, timedelta

from dotenv import load_dotenv
from flask import (
	Flask,
	Response,
	abort,
	flash,
	jsonify,
	redirect,
	render_template,
	request,
	session,
	url_for,
)
from werkzeug.security import check_password_hash

from database.db import (
	count_students,
	create_student,
	delete_student_by_id,
	find_duplicate_student,
	get_audit_logs,
	get_all_students,
	get_deleted_students,
	get_duplicate_report,
	get_public_students,
	get_recent_students,
	get_student_by_id,
	get_student_counts_by_course,
	get_student_counts_by_skill_level,
	get_students,
	get_students_by_course,
	get_students_by_skill_level,
	get_total_courses,
	get_total_students,
	get_user_by_username,
	get_user_by_id,
	delete_learning_note,
	get_learning_state,
	init_db,
	log_audit_event,
	record_learning_activity,
	restore_student_by_id,
	save_learning_lab_progress,
	save_learning_note,
	save_learning_progress,
	validate_student_data,
	update_student,
)
from services.langchain_service import (
	LangChainConfigurationError,
	LangChainServiceError,
	build_skill_spring_context,
	get_langchain_response,
)
from services.learning_hub_content import (
	CHAPTERS,
	PRACTICE_LABS,
	build_chapter_tutor_context,
	get_chapter,
)


load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv(
	"FLASK_SECRET_KEY", "skillspring-development-key"
)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("FLASK_ENV") == "production"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)

RATE_LIMIT_WINDOWS = {
	"login": {"limit": 5, "seconds": 60},
	"chat": {"limit": 20, "seconds": 60},
}
RATE_LIMIT_BUCKETS = {}


def enforce_rate_limit(scope, key, limit, window_seconds):
	"""Simple per-IP or per-user throttling for sensitive routes."""
	bucket_key = f"{scope}:{key}"
	now = time.time()
	bucket = RATE_LIMIT_BUCKETS.setdefault(bucket_key, [])
	bucket[:] = [timestamp for timestamp in bucket if now - timestamp < window_seconds]
	if len(bucket) >= limit:
		raise PermissionError(f"Too many requests. Please wait {window_seconds} seconds and try again.")
	bucket.append(now)


def get_zero_filled_course_counts(rows):
	"""Return a stable course breakdown, including zero-value courses when no students are present."""
	counts = {row["course"]: int(row["total"]) for row in rows}
	return [{"course": course, "total": counts.get(course, 0)} for course in COURSES]


def get_zero_filled_skill_counts(rows):
	"""Return a stable skill-level breakdown, including zero-value levels when no students are present."""
	counts = {row["skill_level"]: int(row["total"]) for row in rows}
	return [{"skill_level": level, "total": counts.get(level, 0)} for level in SKILL_LEVELS]


def generate_csrf_token():
	"""Create a lightweight CSRF token for state-changing forms."""
	if "csrf_token" not in session:
		session["csrf_token"] = secrets.token_hex(32)
	return session["csrf_token"]


@app.before_request
def require_csrf_for_mutating_forms():
	"""Protect form-based state changes without blocking login or AJAX endpoints."""
	if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.path not in {
		"/api/chat",
		"/api/students/check-duplicate",
		"/login",
	}:
		token = request.form.get("csrf_token") or request.headers.get("X-CSRFToken")
		if token != session.get("csrf_token"):
			flash("Your session expired. Please try again.", "error")
			return redirect(url_for("home"))


@app.after_request
def add_security_headers(response):
	"""Add lightweight web security headers without breaking the local app."""
	response.headers["X-Content-Type-Options"] = "nosniff"
	response.headers["X-Frame-Options"] = "SAMEORIGIN"
	response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
	response.headers["Content-Security-Policy"] = (
		"default-src 'self'; script-src 'self' 'unsafe-inline'; "
		"style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
		"connect-src 'self'; frame-ancestors 'self';"
	)
	return response

COURSES = (
	"Python",
	"Java",
	"JavaScript",
	"React",
	"Data Science",
	"Machine Learning",
	"Generative AI",
	"Cloud Computing",
)
SKILL_LEVELS = ("Beginner", "Intermediate", "Advanced")

init_db()


def require_admin():
	"""Ensure only authenticated admins can access protected admin routes."""
	if session.get("role") != "admin":
		log_audit_event(
			"failed_admin_access",
			actor_user_id=session.get("user_id"),
			details={
				"path": request.path,
				"role": session.get("role"),
				"http_method": request.method,
			},
		)
		if session.get("user_id"):
			abort(403)
		return redirect(url_for("login"))
	return None


@app.route("/")
def home():
	return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
	if session.get("user_id"):
		if session.get("role") == "admin":
			return redirect(url_for("admin_panel"))
		return redirect(url_for("home"))

	if request.method == "POST":
		username = (request.form.get("username") or "").strip()
		password = request.form.get("password") or ""
		client_id = request.headers.get("X-Forwarded-For") or request.remote_addr or "local"
		if len(username) > 120 or len(password) > 128:
			flash("Please enter valid login details.", "error")
			return render_template("login.html", csrf_token=generate_csrf_token())
		try:
			enforce_rate_limit("login", client_id, RATE_LIMIT_WINDOWS["login"]["limit"], RATE_LIMIT_WINDOWS["login"]["seconds"])
		except PermissionError as error:
			flash(str(error), "error")
			log_audit_event("login_rate_limited", details={"username": username[:120], "client": client_id})
			return render_template("login.html", csrf_token=generate_csrf_token())

		if not username or not password:
			flash("Please enter both username/email and password.", "error")
			log_audit_event("login_failed", details={"username": username[:120], "reason": "missing_fields"})
			return render_template("login.html", csrf_token=generate_csrf_token())

		user = get_user_by_username(username)
		if user is None or not check_password_hash(user["password_hash"], password):
			flash("Invalid username or password.", "error")
			log_audit_event("login_failed", details={"username": username[:120], "reason": "invalid_credentials"})
			return render_template("login.html", csrf_token=generate_csrf_token())

		session.clear()
		session.permanent = True
		session["user_id"] = user["id"]
		session["user_name"] = user["name"]
		session["role"] = user["role"]
		log_audit_event("login_success", actor_user_id=user["id"], details={"username": user["username"], "role": user["role"]})

		flash(f"Welcome back, {user['name']}.", "success")
		if user["role"] == "admin":
			return redirect(url_for("admin_panel"))
		return redirect(url_for("home"))

	return render_template("login.html", csrf_token=generate_csrf_token())


@app.route("/logout")
def logout():
	actor_id = session.get("user_id")
	username = session.get("user_name")
	session.clear()
	log_audit_event("logout", actor_user_id=actor_id, details={"username": username, "status": "logged_out"})
	flash("You have been logged out.", "success")
	return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard():
	return admin_panel()


@app.route("/admin")
def admin_panel():
	check = require_admin()
	if check is not None:
		return check

	log_audit_event("admin_access", actor_user_id=session.get("user_id"), details={"path": "/admin"})
	students = get_all_students()
	course_counts = get_zero_filled_course_counts(get_student_counts_by_course())
	skill_counts = get_zero_filled_skill_counts(get_student_counts_by_skill_level())
	recent_students = get_recent_students(limit=5)
	deleted_students = get_deleted_students()
	audit_logs = get_audit_logs(limit=5)
	return render_template(
		"admin_panel.html",
		admin_name=session.get("user_name", "Admin"),
		student_count=get_total_students(include_deleted=True),
		active_student_count=get_total_students(),
		deleted_student_count=len(deleted_students),
		total_courses=get_total_courses(),
		course_counts=course_counts,
		skill_level_counts=skill_counts,
		recent_students=recent_students,
		audit_logs=audit_logs,
		courses=COURSES,
		skill_levels=SKILL_LEVELS,
	)


@app.route("/admin/students", methods=["GET"])
def admin_students():
	check = require_admin()
	if check is not None:
		return check

	show_deleted = request.args.get("show_deleted") == "true"
	status_filter = request.args.get("status") or ("deleted" if show_deleted else "active")
	search = " ".join((request.args.get("search") or "").strip().split())
	course_filter = (request.args.get("course") or "").strip() or None
	skill_filter = (request.args.get("skill_level") or "").strip() or None
	page = max(1, int(request.args.get("page") or 1))
	per_page = 10
	offset = (page - 1) * per_page
	status_value = status_filter if status_filter in {"active", "deleted"} else None
	students = get_all_students(
		search=search,
		course=course_filter,
		skill_level=skill_filter,
		status=status_value,
		limit=per_page,
		offset=offset,
		include_deleted=show_deleted,
	)
	total_count = count_students(
		search=search,
		course=course_filter,
		skill_level=skill_filter,
		status=status_value,
		include_deleted=show_deleted,
	)
	total_pages = max(1, (total_count + per_page - 1) // per_page) if total_count else 1
	page = min(page, total_pages)
	return render_template(
		"admin_students.html",
		students=students,
		search_value=search,
		selected_course=course_filter,
		selected_skill_level=skill_filter,
		selected_status=status_filter,
		show_deleted=show_deleted,
		current_page=page,
		total_pages=total_pages,
		total_count=total_count,
		courses=COURSES,
		skill_levels=SKILL_LEVELS,
	)


@app.route("/admin/activity")
def admin_activity():
	check = require_admin()
	if check is not None:
		return check
	logs = get_audit_logs(limit=25)
	return render_template("admin_activity.html", logs=logs)


@app.route("/admin/students/edit/<int:student_id>", methods=["GET", "POST"])
def admin_edit_student(student_id):
	check = require_admin()
	if check is not None:
		return check

	student = get_student_by_id(student_id)
	if student is None:
		flash("Student not found.", "error")
		return redirect(url_for("admin_students"))

	if request.method == "POST":
		name = (request.form.get("name") or "").strip()
		email = (request.form.get("email") or "").strip()
		phone = (request.form.get("phone") or "").strip()
		course = (request.form.get("course") or "").strip()
		skill_level = (request.form.get("skill_level") or "").strip()

		if not name or not email or not course or not skill_level:
			flash("Please complete the required fields.", "error")
			return render_template(
				"admin_edit_student.html",
				student={
					"id": student_id,
					"name": name,
					"email": email,
					"phone": phone,
					"course": course,
					"skill_level": skill_level,
				},
				courses=COURSES,
				skill_levels=SKILL_LEVELS,
				csrf_token=generate_csrf_token(),
			)

		if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
			flash("Please enter a valid email address.", "error")
			return render_template(
				"admin_edit_student.html",
				student={
					"id": student_id,
					"name": name,
					"email": email,
					"phone": phone,
					"course": course,
					"skill_level": skill_level,
				},
				courses=COURSES,
				skill_levels=SKILL_LEVELS,
				csrf_token=generate_csrf_token(),
			)

		try:
			validated = validate_student_data(name, email, phone or "", course, skill_level)
			update_student(
				student_id,
				validated["name"],
				validated["email"],
				validated["phone"] or "",
				validated["course"],
				validated["skill_level"],
			)
		except ValueError as error:
			flash(str(error), "error")
			return render_template(
				"admin_edit_student.html",
				student={
					"id": student_id,
					"name": name,
					"email": email,
					"phone": phone,
					"course": course,
					"skill_level": skill_level,
				},
				courses=COURSES,
				skill_levels=SKILL_LEVELS,
				csrf_token=generate_csrf_token(),
			)
		except sqlite3.IntegrityError:
			flash("A student with that information already exists. Please review the record.", "error")
			return render_template(
				"admin_edit_student.html",
				student={
					"id": student_id,
					"name": name,
					"email": email,
					"phone": phone,
					"course": course,
					"skill_level": skill_level,
				},
				courses=COURSES,
				skill_levels=SKILL_LEVELS,
				csrf_token=generate_csrf_token(),
			)
		except sqlite3.Error:
			flash("The student could not be updated.", "error")
			return redirect(url_for("admin_students"))

		flash("Student updated successfully.", "success")
		return redirect(url_for("admin_students"))

	return render_template(
		"admin_edit_student.html",
		student=student,
		courses=COURSES,
		skill_levels=SKILL_LEVELS,
		csrf_token=generate_csrf_token(),
	)


@app.route("/admin/students/<int:student_id>/delete", methods=["POST"])
@app.route("/admin/students/delete/<int:student_id>", methods=["POST"])
@app.route("/admin/delete/<int:student_id>", methods=["POST"])
def admin_delete_student(student_id):
	check = require_admin()
	if check is not None:
		return check

	student = get_student_by_id(student_id, include_deleted=True)
	if student is None:
		flash("Student record not found.", "error")
		return redirect(url_for("admin_students"))

	student_name = student["name"] or "Unknown student"
	deleted = False
	try:
		deleted = delete_student_by_id(student_id)
		if deleted:
			log_audit_event(
				"student_deleted",
				actor_user_id=session.get("user_id"),
				student_id=student_id,
				details={"student_name": student_name, "status": "deleted"},
			)
	except sqlite3.Error:
		flash("The student could not be deleted.", "error")
		return redirect(url_for("admin_students"))

	if deleted:
		app.logger.info("Admin deleted student ID=%s, name=%s", student_id, student_name)
		flash("Student deleted successfully.", "success")
	else:
		flash("Student record not found.", "error")
	return redirect(url_for("admin_students"))


@app.route("/admin/students/<int:student_id>/restore", methods=["POST"])
def admin_restore_student(student_id):
	check = require_admin()
	if check is not None:
		return check

	student = get_student_by_id(student_id, include_deleted=True)
	if student is None:
		flash("Student record not found.", "error")
		return redirect(url_for("admin_students", show_deleted="true"))

	student_name = student["name"] or "Unknown student"
	restored = False
	try:
		restored = restore_student_by_id(student_id)
		if restored:
			log_audit_event(
				"student_restored",
				actor_user_id=session.get("user_id"),
				student_id=student_id,
				details={"student_name": student_name, "status": "active"},
			)
	except sqlite3.Error:
		flash("The student could not be restored.", "error")
		return redirect(url_for("admin_students", show_deleted="true"))

	if restored:
		flash("Student restored successfully.", "success")
	else:
		flash("Student was not archived or could not be restored.", "error")
	return redirect(url_for("admin_students", show_deleted="true"))


@app.route("/admin/export")
@app.route("/admin/students/export")
def admin_export():
	check = require_admin()
	if check is not None:
		return check

	try:
		from openpyxl import Workbook
		students = get_all_students(status="active")
		workbook = Workbook()
		sheet = workbook.active
		sheet.title = "Students"
		sheet.append(["ID", "Name", "Email", "Phone", "Course", "Skill Level", "Created At"])
		for student in students:
			sheet.append(
				[
					student["id"],
					student["name"],
					student["email"],
					student["phone"] or "",
					student["course"],
					student["skill_level"],
					student["created_at"],
				]
			)
		buffer = io.BytesIO()
		workbook.save(buffer)
		buffer.seek(0)
		response = Response(
			buffer.getvalue(),
			mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
		)
		response.headers["Content-Disposition"] = (
			'attachment; filename="skillspring_students.xlsx"'
		)
		log_audit_event(
			"export_generated",
			actor_user_id=session.get("user_id"),
			details={"rows_exported": len(students), "format": "xlsx"},
		)
		return response
	except Exception:
		flash("The Excel export could not be generated.", "error")
		return redirect(url_for("admin_panel"))


@app.route("/api/students/check-duplicate", methods=["POST"])
def check_duplicate_student():
	"""Return duplicate warnings for the frontend before final form submission."""
	payload = request.get_json(silent=True) or {}
	name = (payload.get("name") or "").strip()
	email = (payload.get("email") or "").strip()
	phone = (payload.get("phone") or "").strip()
	exclude_id = payload.get("exclude_id")
	result = find_duplicate_student(name, email, phone, exclude_id=exclude_id)
	if result is None:
		return jsonify({"ok": True, "duplicate": False})
	return jsonify({"ok": False, "duplicate": True, "message": result["message"], "field": result["field"]})


@app.route("/data-entry", methods=["GET", "POST"])
def data_entry():
	form_data = {
		"name": "",
		"email": "",
		"phone": "",
		"course": "",
		"skill_level": "",
	}

	if request.method == "POST":
		form_data = {
			field: request.form.get(field, "").strip()
			for field in form_data
		}

		required_fields = ("name", "email", "course", "skill_level")
		if any(not form_data[field] for field in required_fields):
			flash("Please complete all required fields.", "error")
			return render_template(
				"data_entry.html",
				form_data=form_data,
				courses=COURSES,
				skill_levels=SKILL_LEVELS,
				csrf_token=generate_csrf_token(),
			)

		if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", form_data["email"]):
			flash("Please enter a valid email address.", "error")
			return render_template(
				"data_entry.html",
				form_data=form_data,
				courses=COURSES,
				skill_levels=SKILL_LEVELS,
				csrf_token=generate_csrf_token(),
			)

		try:
			validated = validate_student_data(
				form_data["name"],
				form_data["email"],
				form_data["phone"],
				form_data["course"],
				form_data["skill_level"],
			)
			create_student(
				validated["name"],
				validated["email"],
				validated["phone"] or "",
				validated["course"],
				validated["skill_level"],
			)
		except ValueError as error:
			flash(str(error), "error")
			return render_template(
				"data_entry.html",
				form_data=form_data,
				courses=COURSES,
				skill_levels=SKILL_LEVELS,
				csrf_token=generate_csrf_token(),
			)
		except sqlite3.IntegrityError:
			flash("A student with that information already exists. Please review the record and try again.", "error")
			return render_template(
				"data_entry.html",
				form_data=form_data,
				courses=COURSES,
				skill_levels=SKILL_LEVELS,
				csrf_token=generate_csrf_token(),
			)
		except sqlite3.Error:
			flash("The student could not be saved. Please try again.", "error")
			return render_template(
				"data_entry.html",
				form_data=form_data,
				courses=COURSES,
				skill_levels=SKILL_LEVELS,
				csrf_token=generate_csrf_token(),
			)

		flash("Student registered successfully.", "success")
		return redirect(url_for("data_entry"))

	return render_template(
		"data_entry.html",
		form_data=form_data,
		courses=COURSES,
		skill_levels=SKILL_LEVELS,
		csrf_token=generate_csrf_token(),
	)


@app.route("/view-data")
def view_data():
	try:
		if session.get("role") == "admin":
			students = get_all_students()
		else:
			students = get_public_students()
	except sqlite3.Error:
		flash("Student data could not be loaded. Please try again.", "error")
		students = []

	return render_template(
		"view_data.html",
		students=students,
		is_admin=session.get("role") == "admin",
		logged_in_user=session.get("user_name"),
	)


def get_learning_owner_key():
	"""Isolate Learning Hub data by account or this browser's signed session."""
	if session.get("user_id"):
		return f"user:{session['user_id']}"
	if "learning_guest_id" not in session:
		session["learning_guest_id"] = secrets.token_urlsafe(32)
	return f"guest:{session['learning_guest_id']}"


@app.route("/learning-hub")
def learning_hub():
	owner_key = get_learning_owner_key()
	record_learning_activity(owner_key)
	return render_template("learning_hub.html", csrf_token=generate_csrf_token())


@app.route("/api/learning-hub/chapters")
def learning_hub_chapters():
	return jsonify(chapters=CHAPTERS)


@app.route("/api/learning-hub/labs")
def learning_hub_labs():
	return jsonify(labs=PRACTICE_LABS)


@app.route("/api/learning-hub/chapters/<slug>")
def learning_hub_chapter(slug):
	chapter = get_chapter(slug)
	if chapter is None:
		return jsonify(success=False, error="Chapter not found."), 404
	owner_key = get_learning_owner_key()
	record_learning_activity(owner_key, slug)
	state = next(
		(item for item in get_learning_state(owner_key)["progress"] if item["chapter_slug"] == slug),
		None,
	)
	if state is None or state["status"] == "not_started":
		save_learning_progress(owner_key, slug, "in_progress", bool(state and state["bookmarked"]))
	return jsonify(chapter=chapter)


@app.route("/api/learning-hub/state")
def learning_hub_state():
	state = get_learning_state(get_learning_owner_key())
	activity_dates = [item["activity_date"] for item in state["activity"]]
	streak = 0
	expected = date.today()
	for activity_date in activity_dates:
		try:
			active_day = date.fromisoformat(activity_date)
		except (TypeError, ValueError):
			continue
		if active_day == expected:
			streak += 1
			expected = expected.fromordinal(expected.toordinal() - 1)
		elif active_day < expected:
			break
	state["streak"] = streak
	state["recent_chapter"] = next(
		(item["chapter_slug"] for item in state["activity"] if item["chapter_slug"]),
		None,
	)
	state["current_chapter"] = next(
		(item["chapter_slug"] for item in sorted(state["progress"], key=lambda row: row["updated_at"], reverse=True) if item["status"] == "in_progress"),
		None,
	)
	return jsonify(state)


@app.route("/api/learning-hub/progress/<slug>", methods=["PUT"])
def update_learning_hub_progress(slug):
	if get_chapter(slug) is None:
		return jsonify(success=False, error="Chapter not found."), 404
	payload = request.get_json(silent=True)
	if not isinstance(payload, dict):
		return jsonify(success=False, error="A JSON request body is required."), 400
	owner_key = get_learning_owner_key()
	previous = next(
		(item for item in get_learning_state(owner_key)["progress"] if item["chapter_slug"] == slug),
		{},
	)
	status = payload.get("status", previous.get("status", "not_started"))
	bookmarked = payload.get("bookmarked", bool(previous.get("bookmarked", False)))
	if status not in {"not_started", "in_progress", "completed"} or not isinstance(bookmarked, bool):
		return jsonify(success=False, error="Invalid chapter progress."), 400
	save_learning_progress(owner_key, slug, status, bookmarked)
	record_learning_activity(owner_key, slug)
	return jsonify(success=True, chapter_slug=slug, status=status, bookmarked=bookmarked)


@app.route("/api/learning-hub/labs/<slug>", methods=["PUT"])
def update_learning_hub_lab(slug):
	if not any(lab["slug"] == slug for lab in PRACTICE_LABS):
		return jsonify(success=False, error="Practice lab not found."), 404
	payload = request.get_json(silent=True)
	if not isinstance(payload, dict) or not isinstance(payload.get("completed"), bool):
		return jsonify(success=False, error="A completed boolean is required."), 400
	save_learning_lab_progress(get_learning_owner_key(), slug, payload["completed"])
	record_learning_activity(get_learning_owner_key())
	return jsonify(success=True, lab_slug=slug, completed=payload["completed"])


@app.route("/api/learning-hub/notes/<int:week_number>", methods=["PUT", "DELETE"])
def learning_hub_note(week_number):
	if week_number < 1 or week_number > 15:
		return jsonify(success=False, error="Week number must be between 1 and 15."), 400
	owner_key = get_learning_owner_key()
	try:
		if request.method == "DELETE":
			deleted = delete_learning_note(owner_key, week_number)
			return jsonify(success=True, deleted=deleted)
		payload = request.get_json(silent=True)
		if not isinstance(payload, dict):
			return jsonify(success=False, error="A JSON request body is required."), 400
		fields = {
			"title": str(payload.get("title", "")).strip()[:120],
			"note_date": str(payload.get("note_date", "")).strip()[:10],
			"notes": str(payload.get("notes", ""))[:8000],
			"important_points": str(payload.get("important_points", ""))[:4000],
			"doubts": str(payload.get("doubts", ""))[:4000],
			"practical_work": str(payload.get("practical_work", ""))[:4000],
			"revision_points": str(payload.get("revision_points", ""))[:4000],
			"next_goals": str(payload.get("next_goals", ""))[:4000],
		}
		if fields["note_date"]:
			date.fromisoformat(fields["note_date"])
		save_learning_note(owner_key, week_number, fields)
		record_learning_activity(owner_key)
		return jsonify(success=True, week_number=week_number)
	except (sqlite3.Error, ValueError) as error:
		app.logger.exception("[LEARNING HUB] Weekly note request failed")
		if isinstance(error, ValueError):
			return jsonify(success=False, error="Enter a valid note date."), 400
		return jsonify(success=False, error="The weekly note could not be saved."), 500


@app.route("/chat", methods=["POST"])
@app.route("/api/chat", methods=["POST"])
def chat():
	client_id = request.headers.get("X-Forwarded-For") or request.remote_addr or "local"
	app.logger.info("[CHAT] Request received from %s", client_id)
	try:
		enforce_rate_limit(
			"chat",
			client_id,
			RATE_LIMIT_WINDOWS["chat"]["limit"],
			RATE_LIMIT_WINDOWS["chat"]["seconds"],
		)
	except PermissionError as error:
		return jsonify(success=False, error=str(error)), 429

	data = request.get_json(silent=True)
	message = data.get("message", "").strip() if isinstance(data, dict) else ""
	history = data.get("history", []) if isinstance(data, dict) else []
	chapter_slug = data.get("chapter_slug", "") if isinstance(data, dict) else ""
	role = (session.get("role") or "user").lower()
	if role not in {"admin", "user"}:
		role = "user"

	app.logger.info("[CHAT] Role=%s Message=%s", role, message[:120])
	if len(message) > 4000:
		return jsonify(success=False, error="Please keep your message under 4,000 characters."), 400
	if len(message) == 0:
		return jsonify(success=False, error="Please enter a question first."), 400

	app.logger.info("CHAT QUESTION: %s", message[:200])
	app.logger.info("USER ROLE: %s", role)
	context = build_skill_spring_context(message, history, role)
	app.logger.info("CONTEXT SENT TO MODEL: %s", (context[:350].replace("\n", " ") if context else "NO_CONTEXT"))

	try:
		app.logger.info("[LANGCHAIN] Starting request")
		learning_context = build_chapter_tutor_context(chapter_slug, message)
		reply = get_langchain_response(
			message,
			history,
			role=role,
			learning_context=learning_context,
		)
		app.logger.info("[LANGCHAIN] Response received")
		app.logger.info("[CHAT] Response returned")
		return jsonify(success=True, reply=reply), 200
	except LangChainConfigurationError as error:
		app.logger.error("[LANGCHAIN] Configuration error: %s", str(error))
		return jsonify(success=False, error=str(error)), 503
	except LangChainServiceError as error:
		app.logger.error("[LANGCHAIN] Service error: %s", str(error))
		return jsonify(
			success=False,
			error="The AI assistant is temporarily unavailable. Please try again.",
		), 502
	except Exception as error:
		app.logger.exception("[LANGCHAIN] Unexpected exception while generating response")
		return jsonify(
			success=False,
			error="Something went wrong while contacting the AI assistant.",
		), 500


if __name__ == "__main__":
	app.run(debug=True)
