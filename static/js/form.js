document.addEventListener("DOMContentLoaded", () => {
  const studentForm = document.querySelector(".student-form");

  if (!studentForm) {
    return;
  }

  document.querySelectorAll("select[data-selected]").forEach((select) => {
    select.value = select.dataset.selected;
  });

  const formInputs = {
    name: studentForm.querySelector('input[name="name"]'),
    email: studentForm.querySelector('input[name="email"]'),
    phone: studentForm.querySelector('input[name="phone"]'),
  };

  const fieldStatus = {};

  const setStatus = (fieldName, text, tone = "neutral") => {
    const input = formInputs[fieldName];
    if (!input) {
      return;
    }
    let status = fieldStatus[fieldName];
    if (!status) {
      status = document.createElement("div");
      status.className = "field-validation-message";
      status.setAttribute("aria-live", "polite");
      input.parentElement.appendChild(status);
      fieldStatus[fieldName] = status;
    }
    status.textContent = text;
    status.classList.remove("success", "error", "neutral");
    if (tone !== "neutral") {
      status.classList.add(tone);
    }
  };

  const getDuplicatePayload = () => {
    const currentPath = window.location.pathname;
    const match = currentPath.match(/\/admin\/students\/edit\/(\d+)/);
    const excludeId = match ? Number(match[1]) : null;

    return {
      name: (formInputs.name?.value || "").trim(),
      email: (formInputs.email?.value || "").trim(),
      phone: (formInputs.phone?.value || "").trim(),
      exclude_id: excludeId,
    };
  };

  const checkDuplicates = () => {
    const payload = getDuplicatePayload();
    const hasAnyValue = Object.values(payload).some((value) =>
      typeof value === "string" ? value.length > 0 : value !== null,
    );

    if (!hasAnyValue) {
      Object.keys(fieldStatus).forEach((fieldName) =>
        setStatus(fieldName, "", "neutral"),
      );
      return;
    }

    fetch("/api/students/check-duplicate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    })
      .then((response) => response.json())
      .then((result) => {
        if (!result || !result.duplicate) {
          Object.keys(fieldStatus).forEach((fieldName) =>
            setStatus(fieldName, "", "neutral"),
          );
          return;
        }

        if (result.field === "name") {
          setStatus("name", "Student name already registered.", "error");
        }
        if (result.field === "email") {
          setStatus("email", "Email already registered.", "error");
        }
        if (result.field === "phone") {
          setStatus("phone", "Phone number already registered.", "error");
        }
      })
      .catch(() => {
        // Silent failure: backend validation remains authoritative.
      });
  };

  Object.values(formInputs).forEach((input) => {
    if (!input) {
      return;
    }
    input.addEventListener("input", checkDuplicates);
    input.addEventListener("blur", checkDuplicates);
  });

  studentForm.addEventListener("submit", (event) => {
    if (!studentForm.checkValidity()) {
      event.preventDefault();
      studentForm.reportValidity();
    }
  });
});
