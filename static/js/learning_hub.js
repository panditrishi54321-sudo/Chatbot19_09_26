document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector("#learning-hub");
  if (!root) return;

  const csrfToken = root.dataset.csrfToken;
  const byId = (id) => document.getElementById(id);
  let chapters = [];
  let labs = [];
  let state = { notes: [], progress: [], labs: [], activity: [] };
  let activeChapter = null;
  let activeWeek = 1;

  const escapeHtml = (value) =>
    String(value ?? "").replace(/[&<>"']/g, (character) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    })[character]);

  const api = async (url, options = {}) => {
    const headers = new Headers(options.headers || {});
    if (options.method && options.method !== "GET") {
      headers.set("Content-Type", "application/json");
      headers.set("X-CSRFToken", csrfToken);
    }
    const response = await fetch(url, { ...options, headers });
    let result = {};
    try {
      result = await response.json();
    } catch {
      throw new Error("SkillSpring could not read the server response.");
    }
    if (!response.ok || result.success === false) {
      throw new Error(result.error || "The Learning Hub request failed.");
    }
    return result;
  };

  const showMessage = (element, message, isError = false) => {
    element.textContent = message;
    element.classList.toggle("is-error", isError);
  };

  const progressFor = (slug) =>
    state.progress.find((item) => item.chapter_slug === slug) || {
      status: "not_started",
      bookmarked: 0,
    };

  const renderSummary = () => {
    const completed = state.progress.filter((item) => item.status === "completed").length;
    const percent = Math.round((completed / Math.max(chapters.length, 1)) * 100);
    byId("hub-progress-percent").textContent = `${percent}%`;
    byId("hub-progress-bar").value = percent;
    byId("hub-completion-count").textContent = `${completed} / ${chapters.length} chapters completed`;
    byId("hub-streak").textContent = state.streak || 0;
    const completedLabs = state.labs.filter((item) => item.completed).length;
    byId("hub-project-count").textContent = `${completedLabs} / ${labs.length}`;

    const current = chapters.find((item) => item.slug === state.current_chapter);
    const recent = chapters.find((item) => item.slug === state.recent_chapter);
    byId("hub-current-chapter").textContent = current?.title || "Not started";
    byId("hub-recent-chapter").textContent = recent?.title || "None yet";
    byId("hub-resume-label").textContent = current
      ? `Continue: ${current.title}`
      : "Ready when you are";
    const resume = byId("hub-resume");
    resume.hidden = !current;
    resume.dataset.slug = current?.slug || "";
  };

  const matchesChapter = (chapter) => {
    const query = byId("hub-search").value.trim().toLowerCase();
    const level = byId("hub-level-filter").value;
    const topic = byId("hub-topic-filter").value;
    const bookmarkedOnly = byId("hub-bookmarked-filter").checked;
    const content = JSON.stringify(chapter).toLowerCase();
    return (!query || content.includes(query)) &&
      (level === "all" || chapter.level === level) &&
      (topic === "all" || chapter.tags.includes(topic)) &&
      (!bookmarkedOnly || Boolean(progressFor(chapter.slug).bookmarked));
  };

  const renderChapters = () => {
    const grid = byId("hub-chapter-grid");
    const visible = chapters.filter(matchesChapter);
    if (!visible.length) {
      grid.innerHTML = '<p class="hub-empty">No chapters match these filters.</p>';
      return;
    }
    grid.innerHTML = visible.map((chapter) => {
      const progress = progressFor(chapter.slug);
      const bookmark = Boolean(progress.bookmarked);
      const complete = progress.status === "completed";
      const statusLabel = complete ? "Completed" : progress.status === "in_progress" ? "In progress" : "Not started";
      return `
        <article class="hub-chapter-card ${complete ? "is-complete" : ""}">
          <div class="hub-card-topline"><span class="hub-chapter-number">${String(chapters.indexOf(chapter) + 1).padStart(2, "0")}</span>
            <button class="hub-card-bookmark" type="button" data-action="bookmark" data-slug="${escapeHtml(chapter.slug)}" aria-pressed="${bookmark}" title="${bookmark ? "Remove bookmark" : "Bookmark chapter"}">${bookmark ? "★" : "☆"}</button>
          </div>
          <p class="hub-card-meta"><span>${escapeHtml(chapter.level)}</span><span>${chapter.minutes} min</span></p>
          <h3>${escapeHtml(chapter.title)}</h3>
          <p class="hub-card-summary">${escapeHtml(chapter.summary)}</p>
          <div class="hub-card-tags">${chapter.tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join("")}</div>
          <div class="hub-card-progress"><span>${escapeHtml(statusLabel)}</span><span>${complete ? "100%" : progress.status === "in_progress" ? "Started" : "0%"}</span></div>
          <button class="button button-primary hub-card-open" type="button" data-action="open" data-slug="${escapeHtml(chapter.slug)}">${complete ? "Review" : progress.status === "in_progress" ? "Continue" : "Start learning"} <span aria-hidden="true">→</span></button>
        </article>`;
    }).join("");
  };

  const list = (items) => `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;

  const highlightCode = (source) => {
    const keywords = new Set("and as async await break class const continue def else elif export false for from function if import in let new null or pass return true try while with yield".split(" "));
    return escapeHtml(source).replace(
      /(#.*$|\/\/.*$)|("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`)|\b(?:and|as|async|await|break|class|const|continue|def|else|elif|export|false|for|from|function|if|import|in|let|new|null|or|pass|return|true|try|while|with|yield)\b|\b\d+(?:\.\d+)?\b/gm,
      (token) => {
        if (token.startsWith("#") || token.startsWith("//")) return `<span class="hub-token-comment">${token}</span>`;
        if (/^["'`]/.test(token)) return `<span class="hub-token-string">${token}</span>`;
        if (keywords.has(token)) return `<span class="hub-token-keyword">${token}</span>`;
        return `<span class="hub-token-number">${token}</span>`;
      },
    );
  };

  const renderChapter = (chapter) => {
    activeChapter = chapter;
    byId("hub-lesson").hidden = false;
    const progress = progressFor(chapter.slug);
    byId("hub-lesson-heading").innerHTML = `
      <p class="eyebrow">Chapter ${String(chapters.indexOf(chapter) + 1).padStart(2, "0")} / ${escapeHtml(chapter.level)} / ${chapter.minutes} min</p>
      <h2>${escapeHtml(chapter.title)}</h2><p>${escapeHtml(chapter.summary)}</p>`;
    const bookmarkButton = byId("hub-bookmark-button");
    bookmarkButton.setAttribute("aria-pressed", String(Boolean(progress.bookmarked)));
    bookmarkButton.innerHTML = `${progress.bookmarked ? "★" : "☆"} <span>${progress.bookmarked ? "Bookmarked" : "Bookmark"}</span>`;
    bookmarkButton.title = progress.bookmarked ? "Remove bookmark" : "Bookmark this chapter";

    const refs = chapter.references.map(([title, url]) =>
      `<li><a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">${escapeHtml(title)}</a></li>`,
    ).join("");
    byId("hub-lesson-content").innerHTML = `
      <div class="hub-lesson-toolbar">
        <button class="button button-primary" type="button" data-action="complete" data-slug="${escapeHtml(chapter.slug)}">${progress.status === "completed" ? "Completed ✓" : "Mark as complete"}</button>
        <button class="button button-secondary" type="button" data-tutor-mode="section">Ask about this chapter</button>
        <button class="button button-secondary" type="button" data-tutor-mode="simple">Explain simpler</button>
        <button class="button button-secondary" type="button" data-tutor-mode="quiz">Quiz me</button>
      </div>
      <div class="hub-lesson-grid">
        <section class="hub-lesson-block"><h3>Learning objectives</h3>${list(chapter.objectives)}</section>
        <section class="hub-lesson-block"><h3>Why this topic matters</h3><p>${escapeHtml(chapter.why)}</p></section>
      </div>
      <section class="hub-lesson-block"><h3>Beginner-friendly explanation</h3><p>${escapeHtml(chapter.explanation)}</p></section>
      <section class="hub-lesson-block"><h3>Key concepts</h3>${list(chapter.concepts)}</section>
      <section class="hub-lesson-block"><h3>Architecture at a glance</h3><pre class="hub-diagram" role="img" aria-label="Learning architecture diagram">${escapeHtml(chapter.diagram)}</pre></section>
      <section class="hub-lesson-block"><h3>Real-world example</h3><p>${escapeHtml(chapter.example)}</p></section>
      <section class="hub-lesson-block"><div class="hub-code-heading"><h3>Practical code example</h3><button class="hub-copy-code" type="button" data-copy-code>Copy code</button></div><pre class="hub-code"><code>${highlightCode(chapter.code)}</code></pre></section>
      <section class="hub-lesson-block"><h3>Step-by-step</h3>${list(chapter.steps)}</section>
      <section class="hub-lesson-block"><h3>Common mistakes</h3>${list(chapter.mistakes)}</section>
      <section class="hub-lesson-block"><h3>Interview questions</h3>${list(chapter.interviews)}</section>
      <section class="hub-lesson-block"><h3>Mini practice exercise</h3><p>${escapeHtml(chapter.exercise)}</p><button class="button button-secondary" type="button" data-tutor-mode="practice">Ask for a practice hint</button></section>
      <section class="hub-lesson-block hub-quiz" data-correct-answer="${chapter.quiz.answer}"><h3>Quick quiz</h3><p>${escapeHtml(chapter.quiz.question)}</p><div class="hub-quiz-options">${chapter.quiz.choices.map((choice, index) => `<button type="button" data-quiz-choice="${index}">${escapeHtml(choice)}</button>`).join("")}</div><p class="hub-quiz-feedback" aria-live="polite"></p></section>
      <section class="hub-lesson-block"><h3>Key takeaways</h3>${list(chapter.takeaways)}</section>
      <section class="hub-lesson-block"><h3>References &amp; Further Reading</h3><ul>${refs}</ul><p class="hub-original-note">Explanations and examples are original SkillSpring summaries; use the sources for deeper study.</p></section>
      <div class="hub-lesson-footer"><button type="button" class="button button-secondary" data-action="previous">Previous chapter</button><button type="button" class="button button-primary" data-action="next">Next chapter</button></div>`;
    byId("hub-lesson").scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const setTutorChapter = (chapter) => {
    const panel = byId("chat-panel");
    const indicator = byId("chat-chapter-indicator");
    if (!panel || !indicator) return;
    panel.dataset.learningChapter = chapter?.slug || "";
    indicator.textContent = chapter ? `AI Tutor · Chapter ${String(chapters.indexOf(chapter) + 1).padStart(2, "0")}: ${chapter.title}` : "";
    indicator.hidden = !chapter;
  };

  const openChapter = async (slug) => {
    try {
      const result = await api(`/api/learning-hub/chapters/${encodeURIComponent(slug)}`);
      renderChapter(result.chapter);
      setTutorChapter(result.chapter);
      await loadState();
    } catch (error) {
      showMessage(byId("hub-global-status"), error.message, true);
    }
  };

  const renderLabs = () => {
    const done = new Set(state.labs.filter((item) => item.completed).map((item) => item.lab_slug));
    byId("hub-lab-grid").innerHTML = labs.map((lab) => {
      const completed = done.has(lab.slug);
      const safeTitle = escapeHtml(lab.title);
      return `<article class="hub-lab-card ${completed ? "is-complete" : ""}">
        <div class="hub-lab-card-heading"><span class="hub-chapter-number">LAB</span><span class="hub-card-meta">${escapeHtml(lab.level)}</span></div>
        <h3>${safeTitle}</h3><p><strong>Problem &amp; objective</strong><br>${escapeHtml(lab.objective)}</p>
        <p><strong>Architecture</strong></p><pre class="hub-diagram">${escapeHtml(lab.architecture)}</pre>
        <details><summary>Lab brief and starter</summary>
          <p><strong>Prerequisites</strong><br>${lab.level === "Beginner" ? "Basic Python and the foundations chapters." : "Review the related LLM, RAG or agent chapters first."}</p>
          <h4>Steps</h4>${list(lab.steps)}
          <h4>Starter sketch</h4><pre class="hub-code"><code>${highlightCode(`# ${lab.title}\n# TODO: build one small, testable slice\nprint(\"${lab.slug}\")`)}</code></pre>
          <p><strong>Expected output</strong><br>A small working demo that shows: ${escapeHtml(lab.objective.toLowerCase())}</p>
          <p><strong>Challenge</strong><br>${escapeHtml(lab.challenge)}</p>
          <p><strong>Solution hint</strong><br>Keep the first version narrow, log each stage, and validate inputs and outputs.</p>
          <p><strong>Extension idea</strong><br>Add a quality check, a failure case, and a short README diagram.</p>
        </details>
        <button type="button" class="button ${completed ? "button-secondary" : "button-primary"}" data-action="lab-complete" data-slug="${escapeHtml(lab.slug)}" aria-pressed="${completed}">${completed ? "Project completed ✓" : "Mark project complete"}</button>
      </article>`;
    }).join("");
  };

  const loadState = async () => {
    state = await api("/api/learning-hub/state");
    renderSummary();
    renderChapters();
    if (activeChapter) renderChapter(activeChapter);
    renderLabs();
    renderNote();
  };

  const noteFor = (week) => state.notes.find((note) => note.week_number === week);
  const renderNote = () => {
    const note = noteFor(activeWeek);
    const form = byId("hub-note-form");
    for (const field of form.elements) {
      if (field.name && Object.hasOwn(note || {}, field.name)) field.value = note[field.name];
    }
    if (!note) {
      form.elements.note_date.value = "";
    }
    byId("note-save").textContent = note ? "Update notes" : "Save notes";
    byId("note-delete").hidden = !note;
    showMessage(byId("hub-note-status"), note ? `Saved ${note.updated_at}` : `Week ${activeWeek} has no saved notes.`);
  };

  const saveNote = async (event) => {
    event.preventDefault();
    const form = byId("hub-note-form");
    const fields = Object.fromEntries(new FormData(form).entries());
    try {
      await api(`/api/learning-hub/notes/${activeWeek}`, { method: "PUT", body: JSON.stringify(fields) });
      await loadState();
      showMessage(byId("hub-note-status"), `Week ${activeWeek} notes saved.`);
    } catch (error) {
      showMessage(byId("hub-note-status"), error.message, true);
    }
  };

  const updateProgress = async (slug, values) => {
    const previous = progressFor(slug);
    await api(`/api/learning-hub/progress/${encodeURIComponent(slug)}`, {
      method: "PUT",
      body: JSON.stringify({ status: values.status ?? previous.status, bookmarked: values.bookmarked ?? Boolean(previous.bookmarked) }),
    });
    await loadState();
    if (activeChapter?.slug === slug) renderChapter(activeChapter);
  };

  const tutorPrompts = {
    teach: "Teach me this topic step by step, starting with the prerequisite idea and one practical example.",
    code: "Show me a small practical code example for this topic and explain it line by line.",
    simple: "Explain this topic in simpler words, using an everyday analogy and one example.",
    quiz: "Quiz me on this topic with one question at a time. Wait for my answer before explaining.",
    interview: "Give me three interview questions about this topic, then explain what a strong answer should include.",
    practice: "Give me a short hands-on exercise about this topic, with hints before the solution.",
    debug: "Help me debug this code. Ask me to share the code and exact error if I have not included them.",
    section: "Explain the current chapter's key ideas and give one practical example.",
    any: "I want to learn about Generative AI. Ask what I already know, then guide me to the right next concept.",
  };

  const askTutor = (mode) => {
    const input = byId("chat-input");
    const panel = byId("chat-panel");
    const launcher = byId("chat-launcher");
    if (!input || !panel || !launcher) return;
    input.value = tutorPrompts[mode] || tutorPrompts.teach;
    if (panel.hidden) launcher.click();
    input.focus();
  };

  for (let week = 1; week <= 15; week += 1) {
    const option = document.createElement("option");
    option.value = String(week);
    option.textContent = `Week ${week}`;
    byId("notes-week").appendChild(option);
  }

  document.querySelectorAll("[data-hub-tab]").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll("[data-hub-tab]").forEach((item) => item.setAttribute("aria-selected", String(item === tab)));
      document.querySelectorAll("[data-hub-view]").forEach((view) => { view.hidden = view.dataset.hubView !== tab.dataset.hubTab; });
    });
  });

  ["hub-search", "hub-level-filter", "hub-topic-filter", "hub-bookmarked-filter"].forEach((id) => {
    byId(id).addEventListener(id === "hub-search" ? "input" : "change", renderChapters);
  });
  byId("hub-note-form").addEventListener("submit", saveNote);
  byId("notes-week").addEventListener("change", (event) => {
    activeWeek = Number(event.target.value);
    renderNote();
  });
  byId("note-clear").addEventListener("click", () => {
    const week = activeWeek;
    byId("hub-note-form").reset();
    activeWeek = week;
    byId("notes-week").value = String(week);
    showMessage(byId("hub-note-status"), "Editor cleared. Saved notes are unchanged.");
  });
  byId("note-delete").addEventListener("click", async () => {
    if (!window.confirm(`Delete saved notes for Week ${activeWeek}?`)) return;
    try {
      await api(`/api/learning-hub/notes/${activeWeek}`, { method: "DELETE" });
      await loadState();
      showMessage(byId("hub-note-status"), `Week ${activeWeek} notes deleted.`);
    } catch (error) {
      showMessage(byId("hub-note-status"), error.message, true);
    }
  });

  root.addEventListener("click", async (event) => {
    const modeButton = event.target.closest("[data-tutor-mode]");
    if (modeButton) {
      askTutor(modeButton.dataset.tutorMode);
      return;
    }
    if (event.target.closest("[data-copy-code]")) {
      const button = event.target.closest("[data-copy-code]");
      try {
        await navigator.clipboard.writeText(activeChapter?.code || "");
        button.textContent = "Copied";
        window.setTimeout(() => { button.textContent = "Copy code"; }, 1500);
      } catch {
        button.textContent = "Select code to copy";
      }
      return;
    }
    const choice = event.target.closest("[data-quiz-choice]");
    if (choice) {
      const quiz = choice.closest(".hub-quiz");
      const correct = Number(quiz.dataset.correctAnswer) === Number(choice.dataset.quizChoice);
      const explanation = activeChapter.quiz.explanation;
      const feedback = quiz.querySelector(".hub-quiz-feedback");
      feedback.textContent = `${correct ? "Correct. " : "Not quite. "}${explanation}`;
      feedback.classList.toggle("is-correct", correct);
      feedback.classList.toggle("is-error", !correct);
      return;
    }
    const action = event.target.closest("[data-action]");
    if (!action) return;
    const { slug } = action.dataset;
    try {
      if (action.dataset.action === "open") await openChapter(slug);
      if (action.dataset.action === "bookmark") await updateProgress(slug, { bookmarked: action.getAttribute("aria-pressed") !== "true" });
      if (action.dataset.action === "complete") await updateProgress(slug, { status: "completed" });
      if (action.dataset.action === "previous" || action.dataset.action === "next") {
        const index = chapters.findIndex((chapter) => chapter.slug === activeChapter?.slug);
        const nextIndex = index + (action.dataset.action === "next" ? 1 : -1);
        if (chapters[nextIndex]) await openChapter(chapters[nextIndex].slug);
      }
      if (action.dataset.action === "lab-complete") {
        const previous = state.labs.some((item) => item.lab_slug === slug && item.completed);
        await api(`/api/learning-hub/labs/${encodeURIComponent(slug)}`, {
          method: "PUT",
          body: JSON.stringify({ completed: !previous }),
        });
        await loadState();
      }
    } catch (error) {
      showMessage(byId("hub-global-status"), error.message, true);
    }
  });

  byId("hub-bookmark-button").addEventListener("click", async () => {
    if (!activeChapter) return;
    try {
      await updateProgress(activeChapter.slug, { bookmarked: !Boolean(progressFor(activeChapter.slug).bookmarked) });
    } catch (error) {
      showMessage(byId("hub-global-status"), error.message, true);
    }
  });
  byId("hub-resume").addEventListener("click", (event) => openChapter(event.currentTarget.dataset.slug));
  document.querySelectorAll("[data-tutor-mode]").forEach((button) => {
    button.addEventListener("click", () => askTutor(button.dataset.tutorMode));
  });

  const load = async () => {
    try {
      const [chapterResult, labResult] = await Promise.all([
        api("/api/learning-hub/chapters"),
        api("/api/learning-hub/state"),
      ]);
      chapters = chapterResult.chapters;
      labs = window.SKILLSPRING_PRACTICE_LABS || [];
      if (!labs.length) {
        labs = [
          { slug: "prompt-playground", title: "Prompt Engineering Playground", objective: "Compare prompt patterns on a fixed task.", level: "Beginner", architecture: "input -> prompts -> rubric", steps: ["Choose a task", "Compare variants"], challenge: "Add edge cases." },
          { slug: "llm-api-chatbot", title: "LLM API Chatbot", objective: "Build a safe server-side model call.", level: "Beginner", architecture: "browser -> Flask -> model", steps: ["Add a route", "Validate requests"], challenge: "Add bounded history." },
          { slug: "embedding-search", title: "Embedding Search", objective: "Retrieve paragraphs by meaning.", level: "Intermediate", architecture: "text -> vectors -> search", steps: ["Embed passages", "Compare neighbors"], challenge: "Add filters." },
          { slug: "mini-rag", title: "Mini RAG Assistant", objective: "Ground an answer in local sources.", level: "Intermediate", architecture: "documents -> retrieve -> answer", steps: ["Chunk sources", "Cite results"], challenge: "Test missing evidence." },
          { slug: "document-qa", title: "Document Q&A", objective: "Answer questions with document provenance.", level: "Intermediate", architecture: "upload -> parse -> retrieve", steps: ["Validate files", "Show citations"], challenge: "Test tables." },
          { slug: "ai-tutor", title: "AI Tutor", objective: "Teach from selected chapter context.", level: "Intermediate", architecture: "chapter -> context -> tutor", steps: ["Select topic", "Bound history"], challenge: "Measure learning." },
          { slug: "tool-calling", title: "Tool-Calling Agent", objective: "Use one narrow read-only tool.", level: "Advanced", architecture: "request -> check -> tool", steps: ["Define schema", "Authorize inputs"], challenge: "Add approval." },
          { slug: "agentic-workflow", title: "Agentic Workflow", objective: "Build a bounded observe-and-act loop.", level: "Advanced", architecture: "plan -> act -> verify -> stop", steps: ["Define stop", "Test failure"], challenge: "Compare a fixed flow." },
          { slug: "mcp-assistant", title: "MCP-Based Assistant", objective: "Connect to a safe demo capability.", level: "Advanced", architecture: "host -> client -> server", steps: ["Expose read-only search", "Review scopes"], challenge: "Add a resource." },
          { slug: "genai-capstone", title: "Final GenAI Capstone", objective: "Deliver a cited tutor with evaluation.", level: "Advanced", architecture: "UI -> Flask -> RAG -> model", steps: ["Retrieve selectively", "Evaluate privacy"], challenge: "Handle unsupported queries." },
        ];
      }
      state = labResult;
      renderSummary();
      renderChapters();
      renderLabs();
      renderNote();
      const resumeChapter = chapters.find((chapter) => chapter.slug === state.current_chapter);
      if (resumeChapter) setTutorChapter(resumeChapter);
    } catch (error) {
      showMessage(byId("hub-global-status"), error.message, true);
      byId("hub-chapter-grid").innerHTML = '<p class="hub-empty">The curriculum could not be loaded. Refresh to retry.</p>';
    }
  };

  load();
});