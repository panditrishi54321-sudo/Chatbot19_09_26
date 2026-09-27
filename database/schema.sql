CREATE TABLE IF NOT EXISTS students (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	name TEXT NOT NULL,
	name_normalized TEXT,
	email TEXT NOT NULL,
	email_normalized TEXT,
	phone TEXT,
	phone_normalized TEXT,
	course TEXT NOT NULL,
	skill_level TEXT NOT NULL,
	created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
	updated_at TEXT,
	status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS users (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	name TEXT NOT NULL,
	username TEXT NOT NULL UNIQUE,
	password_hash TEXT NOT NULL,
	role TEXT NOT NULL CHECK(role IN ('admin', 'user')),
	created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_logs (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	actor_user_id INTEGER,
	action TEXT NOT NULL,
	student_id INTEGER,
	details_json TEXT,
	created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
	FOREIGN KEY(actor_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS learning_notes (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	owner_key TEXT NOT NULL,
	week_number INTEGER NOT NULL CHECK(week_number BETWEEN 1 AND 15),
	title TEXT NOT NULL DEFAULT '',
	note_date TEXT NOT NULL DEFAULT '',
	notes TEXT NOT NULL DEFAULT '',
	important_points TEXT NOT NULL DEFAULT '',
	doubts TEXT NOT NULL DEFAULT '',
	practical_work TEXT NOT NULL DEFAULT '',
	revision_points TEXT NOT NULL DEFAULT '',
	next_goals TEXT NOT NULL DEFAULT '',
	created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
	updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
	UNIQUE(owner_key, week_number)
);

CREATE TABLE IF NOT EXISTS learning_progress (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	owner_key TEXT NOT NULL,
	chapter_slug TEXT NOT NULL,
	status TEXT NOT NULL DEFAULT 'not_started' CHECK(status IN ('not_started', 'in_progress', 'completed')),
	bookmarked INTEGER NOT NULL DEFAULT 0 CHECK(bookmarked IN (0, 1)),
	updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
	UNIQUE(owner_key, chapter_slug)
);

CREATE TABLE IF NOT EXISTS learning_lab_progress (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	owner_key TEXT NOT NULL,
	lab_slug TEXT NOT NULL,
	completed INTEGER NOT NULL DEFAULT 0 CHECK(completed IN (0, 1)),
	updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
	UNIQUE(owner_key, lab_slug)
);

CREATE TABLE IF NOT EXISTS learning_activity (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	owner_key TEXT NOT NULL,
	activity_date TEXT NOT NULL,
	chapter_slug TEXT,
	UNIQUE(owner_key, activity_date)
);
