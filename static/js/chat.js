document.addEventListener("DOMContentLoaded", () => {
  const launcher = document.querySelector("#chat-launcher");
  const panel = document.querySelector("#chat-panel");
  const closeButton = document.querySelector("#chat-close");
  const clearButton = document.querySelector("#chat-clear");
  const form = document.querySelector("#chat-form");
  const input = document.querySelector("#chat-input");
  const messages = document.querySelector("#chat-messages");
  const sendButton = document.querySelector(".chat-send");
  const helpToggle = document.querySelector("#chat-help-toggle");
  const helpPanel = document.querySelector("#chat-help-panel");

  if (
    !launcher ||
    !panel ||
    !closeButton ||
    !form ||
    !input ||
    !messages ||
    !sendButton ||
    !helpToggle ||
    !helpPanel
  ) {
    return;
  }

  let conversationHistory = [];
  let activeChatRequest = null;
  const userRole = panel.dataset.userRole || "guest";

  const chatMaximize = document.getElementById("chat-maximize");
  function toggleChatMaximize() {
    const isMaximized = panel.classList.toggle("chat-maximized");

    if (isMaximized) {
      chatMaximize.textContent = "⛶";
      chatMaximize.setAttribute("aria-label", "Restore chat");
      chatMaximize.setAttribute("title", "Restore chat");
    } else {
      chatMaximize.textContent = "⛶";
      chatMaximize.setAttribute("aria-label", "Maximize chat");
      chatMaximize.setAttribute("title", "Maximize chat");
    }
  }
  if (chatMaximize) {
    chatMaximize.addEventListener("click", toggleChatMaximize);
  }

  const welcomeMessage =
    'Hi! I\'m the SkillSpring Learning Assistant. I can help with students, courses, skill levels, enrollment information and questions about this application. Click "Help & Suggestions" to see example questions.';

  const suggestionGroups = [
    {
      title: "Student Information",
      questions: [
        "How many students are enrolled?",
        "Show me all enrolled student names.",
        "Who are the registered students?",
        "Tell me about Rishi Pandit.",
      ],
    },
    {
      title: "Courses",
      questions: [
        "What courses are available?",
        "How many students are learning React?",
        "Which students are enrolled in JavaScript?",
        "Which course has the most students?",
      ],
    },
    {
      title: "Skill Levels",
      questions: [
        "How many beginners are enrolled?",
        "How many advanced students are there?",
        "Which students are at intermediate level?",
        "Show me the skill level of React students.",
      ],
    },
    {
      title: "Application",
      questions: [
        "What is SkillSpring?",
        "What can I do on this website?",
        "What can the chatbot help me with?",
        "How does the chatbot work?",
      ],
    },
  ];

  if (userRole === "admin") {
    suggestionGroups.push({
      title: "Admin",
      questions: [
        "Show me complete student records.",
        "Show me student email addresses.",
        "Show me student phone numbers.",
        "How many records are in the database?",
        "What administrative features are available?",
        "Can I download student data?",
        "Can I manage student records?",
      ],
    });
  }

  const scrollToLatest = () => {
    messages.scrollTop = messages.scrollHeight;
  };

  const hasConversationContent = () =>
    [...messages.querySelectorAll(".chat-message")].some(
      (message) =>
        !message.classList.contains("welcome-message") &&
        !message.classList.contains("loading-message"),
    );

  const updateClearButton = () => {
    if (!clearButton) {
      return;
    }
    const canClear = hasConversationContent();
    clearButton.hidden = !canClear;
    clearButton.disabled = !canClear;
  };

  const addMessage = (text, messageType) => {
    const message = document.createElement("div");
    message.className = `chat-message ${messageType}-message`;
    if (messageType === "assistant") {
      message.innerHTML = formatAssistantResponse(text);
    } else {
      message.textContent = text;
    }
    messages.appendChild(message);
    scrollToLatest();
    updateClearButton();
    return message;
  };

  const escapeHtml = (text) =>
    text.replace(/[&<>"']/g, (character) => {
      const entities = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      };
      return entities[character];
    });

  const renderHelpPanel = () => {
    const groupsHtml = suggestionGroups
      .map(
        (group) => `
          <div class="chat-help-group">
            <h3>${group.title}</h3>
            <div class="chat-help-options">
              ${group.questions
                .map(
                  (question) => `
                    <button
                      class="chat-suggestion"
                      type="button"
                      data-question="${escapeHtml(question)}"
                      title="Use this question in the chat"
                    >
                      ${escapeHtml(question)}
                    </button>
                  `,
                )
                .join("")}
            </div>
          </div>
        `,
      )
      .join("");

    helpPanel.innerHTML = `
      <div class="chat-help-header">
        <h3>How can I help?</h3>
      </div>
      <div class="chat-help-summary">
        <p>You can ask me about:</p>
        <div class="chat-help-tags">
          <span>Students</span>
          <span>Courses</span>
          <span>Skill levels</span>
          <span>Enrollment</span>
          <span>Student counts</span>
          <span>SkillSpring</span>
        </div>
      </div>
      <div class="chat-help-section">
        <h4>About SkillSpring</h4>
        <p>
          SkillSpring is an EdTech learning management application for managing
          learner information, courses and skill levels.
        </p>
        <ul>
          <li>Student registration</li>
          <li>Student data management</li>
          <li>Course information</li>
          <li>Skill-level information</li>
          <li>AI-powered chatbot</li>
          <li>Role-based access</li>
        </ul>
      </div>
      ${groupsHtml}
    `;
  };

  const formatAssistantResponse = (text) => {
    const escapedText = escapeHtml(text);
    const codeBlocks = [];

    const textWithPlaceholders = escapedText.replace(
      /```([^\n]*)\n?([\s\S]*?)```/g,
      (_match, language, code) => {
        const className = language.trim()
          ? ` class="language-${language.trim()}"`
          : "";

        codeBlocks.push(`<pre><code${className}>${code.trim()}</code></pre>`);

        return `CODEBLOCKTOKEN${codeBlocks.length - 1}`;
      },
    );

    const formatInlineMarkdown = (value) => {
      return value
        .replace(/^###\s+(.+)$/gm, "<h3>$1</h3>")
        .replace(/^##\s+(.+)$/gm, "<h2>$1</h2>")
        .replace(/^#\s+(.+)$/gm, "<h1>$1</h1>")
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/__(.+?)__/g, "<strong>$1</strong>")
        .replace(/\*(.+?)\*/g, "<em>$1</em>")
        .replace(/_(.+?)_/g, "<em>$1</em>");
    };

    const formatted = textWithPlaceholders
      .split(/\n{2,}/)
      .map((paragraph) => {
        const trimmedParagraph = paragraph.trim();

        const lines = trimmedParagraph.split("\n");

        if (lines.every((line) => /^\s*(?:[-*]|\d+\.)\s+/.test(line))) {
          const ordered = /^\s*\d+\./.test(lines[0]);

          const listItems = lines
            .map((line) => line.replace(/^\s*(?:[-*]|\d+\.)\s+/, ""))
            .map((line) => `<li>${formatInlineMarkdown(line)}</li>`)
            .join("");

          return `<${ordered ? "ol" : "ul"}>${listItems}</${ordered ? "ol" : "ul"}>`;
        }

        return `<p>${formatInlineMarkdown(
          trimmedParagraph.replace(/\n/g, "<br>"),
        )}</p>`;
      })
      .join("");

    return formatted.replace(
      /CODEBLOCKTOKEN(\d+)/g,
      (_match, index) => codeBlocks[Number(index)],
    );
  };

  const clearChat = () => {
    if (
      !hasConversationContent() ||
      !window.confirm("Clear this conversation?")
    ) {
      return;
    }
    if (activeChatRequest) {
      activeChatRequest.abort();
      activeChatRequest = null;
    }
    conversationHistory = [];
    messages.replaceChildren();
    const welcome = document.createElement("div");
    welcome.className = "chat-message assistant-message welcome-message";
    welcome.textContent = welcomeMessage;
    messages.appendChild(welcome);
    input.value = "";
    sendButton.disabled = false;
    sendButton.textContent = "Send";
    helpPanel.hidden = true;
    helpToggle.setAttribute("aria-expanded", "false");
    updateClearButton();
    input.focus();
    scrollToLatest();
  };

  const toggleChatHelp = () => {
    const isOpen = helpPanel.hidden;
    helpPanel.hidden = !isOpen;
    helpToggle.setAttribute("aria-expanded", String(isOpen));
    if (isOpen) {
      helpPanel.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  };

  const setPanelVisibility = (isOpen) => {
    panel.hidden = !isOpen;
    launcher.setAttribute("aria-expanded", String(isOpen));
    if (isOpen) {
      input.focus();
      scrollToLatest();
    }
  };

  renderHelpPanel();
  launcher.addEventListener("click", () => setPanelVisibility(true));
  closeButton.addEventListener("click", () => setPanelVisibility(false));
  if (clearButton) {
    clearButton.addEventListener("click", clearChat);
  }
  updateClearButton();
  helpToggle.addEventListener("click", toggleChatHelp);

  helpPanel.addEventListener("click", (event) => {
    const suggestion = event.target.closest(".chat-suggestion");
    if (!suggestion) {
      return;
    }

    input.value = suggestion.dataset.question || "";
    input.focus();
    const end = input.value.length;
    input.setSelectionRange(end, end);
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = input.value.trim();

    if (!message || sendButton.disabled) {
      return;
    }

    addMessage(message, "user");
    conversationHistory.push({ role: "user", content: message });
    input.value = "";
    sendButton.disabled = true;
    sendButton.textContent = "Thinking...";
    const requestController = new AbortController();
    activeChatRequest = requestController;
    const loadingMessage = addMessage(
      "SkillSpring is thinking...",
      "assistant",
    );
    loadingMessage.classList.add("loading-message");

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, history: conversationHistory }),
        signal: requestController.signal,
      });

      let result = {};
      try {
        result = await response.json();
      } catch {
        result = {};
      }

      loadingMessage.remove();
      const replyText =
        typeof result.reply === "string"
          ? result.reply
          : typeof result.response === "string"
            ? result.response
            : "";

      if (!response.ok || !result.success || !replyText) {
        throw new Error(result.error || "The AI assistant could not respond.");
      }
      conversationHistory.push({ role: "assistant", content: replyText });
      addMessage(replyText, "assistant");
    } catch (error) {
      if (requestController.signal.aborted) {
        return;
      }
      loadingMessage.remove();
      updateClearButton();
      conversationHistory.pop();
      addMessage(
        error.message || "Please check your connection and try again.",
        "error",
      );
    } finally {
      if (activeChatRequest === requestController) {
        activeChatRequest = null;
        sendButton.disabled = false;
        sendButton.textContent = "Send";
        input.focus();
      }
    }
  });
});
