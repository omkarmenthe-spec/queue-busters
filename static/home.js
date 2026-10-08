(function () {
    "use strict";

    const $ = (selector, root = document) =>
        root.querySelector(selector);

    const $$ = (selector, root = document) =>
        Array.from(root.querySelectorAll(selector));

    const reducedMotion = window.matchMedia(
        "(prefers-reduced-motion: reduce)"
    ).matches;

    const form = $("#token-form");

    // This script belongs only on the homepage.
    if (!form) return;

    const cards = $$(".service-option");
    const radios = $$('input[name="service"]');
    const submitButton = $("#submit-btn");
    const submitLabel = $("#submit-label");

    const suggestedDocuments = {
        bonafide: [
            "College ID card",
            "Details of why you need the certificate",
            "Application form, if required by the office"
        ],
        fees: [
            "College ID card",
            "Relevant fee receipt, if available",
            "Details of your payment question"
        ],
        exam: [
            "College ID card",
            "Relevant examination form or notice",
            "Related payment receipt, if applicable"
        ],
        verification: [
            "Documents you want verified",
            "College ID card",
            "Copies, if requested by the office"
        ]
    };

    function readStorage(key, fallback = null) {
        try {
            const value = localStorage.getItem(key);
            return value === null ? fallback : JSON.parse(value);
        } catch {
            return fallback;
        }
    }

    function writeStorage(key, value) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
            return true;
        } catch {
            return false;
        }
    }

    let toastTimer;

    function toast(message) {
        const element = $("#toast");
        if (!element) return;

        element.textContent = message;
        element.classList.add("show");

        clearTimeout(toastTimer);

        toastTimer = setTimeout(() => {
            element.classList.remove("show");
        }, 2800);
    }

    // Make content visible even if later optional effects fail.
    $$("[data-reveal]").forEach((element) => {
        element.classList.add("in");
    });

    // Also keep services visible when JavaScript is disabled.
    // This stylesheet is added only for the current page.
    const visibilityStyle = document.createElement("style");
    visibilityStyle.textContent = `
        .icon-btn {
            min-height: 40px;
            width: 40px;
            padding: 0;
            background: var(--surface);
            color: var(--text);
            border-color: var(--border);
        }
        .icon-btn:hover {
            background: var(--soft);
            color: var(--text);
        }
        .streak[hidden] {
            display: none;
        }
    `;
    document.head.appendChild(visibilityStyle);

    // Theme preference.
    const themeButton = $("#theme-toggle");

    function updateThemeLabel() {
        const dark = document.documentElement.dataset.theme === "dark";

        themeButton.setAttribute(
            "aria-label",
            dark ? "Switch to light theme" : "Switch to dark theme"
        );
        themeButton.setAttribute("aria-pressed", String(dark));
    }

    if (themeButton) {
        updateThemeLabel();

        themeButton.addEventListener("click", () => {
            const next =
                document.documentElement.dataset.theme === "dark"
                    ? "light"
                    : "dark";

            document.documentElement.dataset.theme = next;

            try {
                localStorage.setItem("qb-theme", next);
            } catch {
                // Theme still works when storage is unavailable.
            }

            updateThemeLabel();
        });
    }

    // Office hours have not been confirmed.
    // Do not infer whether the office is open from the device clock.
    const officeText = $("#office-status-text");
    const officeDot = $("#office-status .status-dot");

    if (officeText) {
        officeText.textContent = "College office · Digital token system";
    }

    if (officeDot) {
        officeDot.style.animation = "none";
        officeDot.style.boxShadow = "none";
    }

    // No measured service-time estimates are available yet.
    $$("[data-eta]").forEach((element) => {
        element.textContent = "Time varies by request";
    });

    const ticket = $("#ticket");
    const ticketCode = $("#ticket-code");
    const ticketService = $("#ticket-service");
    const ticketEta = $("#ticket-eta");
    const ticketRowLabel = $(".ticket-row > span");

    if (ticketCode) ticketCode.textContent = "Q-XXX";
    if (ticketEta) ticketEta.textContent = "After submission";
    if (ticketRowLabel) ticketRowLabel.textContent = "Token issued";

    // Rotating headline, respecting reduced-motion preferences.
    const headline = $("#rotator");
    const phrases = [
        "Keep your turn.",
        "Follow your place.",
        "Stay informed."
    ];

    let phraseIndex = 0;

    if (headline && !reducedMotion) {
        setInterval(() => {
            if (document.hidden) return;

            phraseIndex = (phraseIndex + 1) % phrases.length;
            headline.textContent = phrases[phraseIndex];
        }, 3200);
    }

    // Subtle tilt, limited to mouse pointers.
    if (ticket && !reducedMotion) {
        ticket.addEventListener("pointermove", (event) => {
            if (event.pointerType !== "mouse") return;

            const rect = ticket.getBoundingClientRect();

            const x = Math.max(
                -0.5,
                Math.min(0.5, (event.clientX - rect.left) / rect.width - 0.5)
            );

            const y = Math.max(
                -0.5,
                Math.min(0.5, (event.clientY - rect.top) / rect.height - 0.5)
            );

            ticket.style.setProperty("--ry", `${x * 12}deg`);
            ticket.style.setProperty("--rx", `${-y * 12}deg`);
        });

        ticket.addEventListener("pointerleave", () => {
            ticket.style.setProperty("--rx", "0deg");
            ticket.style.setProperty("--ry", "0deg");
        });
    }

    // Hover spotlight on service cards.
    if (!reducedMotion) {
        cards.forEach((card) => {
            card.addEventListener("pointermove", (event) => {
                if (event.pointerType !== "mouse") return;

                const rect = card.getBoundingClientRect();

                card.style.setProperty(
                    "--mx",
                    `${event.clientX - rect.left}px`
                );

                card.style.setProperty(
                    "--my",
                    `${event.clientY - rect.top}px`
                );
            });
        });
    }

    // Suggested preparation checklist.
    const prep = $("#prep");
    const prepList = $("#prep-list");
    const prepBar = $("#prep-bar");
    const prepHeading = $("#prep h3");
    const prepDescription = $("#prep-sub");

    if (prepHeading) {
        prepHeading.textContent = "Suggested preparation";
    }

    if (prepDescription) {
        prepDescription.textContent =
            "These are suggestions, not official requirements. " +
            "Confirm with your college office. Checkmarks are saved " +
            "in this browser when storage is available.";
    }

    function updateProgress() {
        const boxes = $$('input[type="checkbox"]', prepList);
        const checked = boxes.filter((box) => box.checked).length;

        prepBar.style.width =
            `${boxes.length ? (checked / boxes.length) * 100 : 0}%`;
    }

    function renderChecklist(code) {
        if (!prep || !prepList || !prepBar) return;

        const items = suggestedDocuments[code] || [];
        const stored = readStorage(`qb-prep-${code}`, []);
        const saved = Array.isArray(stored) ? stored : [];

        prepList.replaceChildren();

        items.forEach((text, index) => {
            const item = document.createElement("li");
            const label = document.createElement("label");
            const checkbox = document.createElement("input");
            const caption = document.createElement("span");

            checkbox.type = "checkbox";
            checkbox.checked = saved.includes(index);
            caption.textContent = text;

            checkbox.addEventListener("change", () => {
                const selected = $$("input", prepList)
                    .map((box, position) => box.checked ? position : -1)
                    .filter((position) => position >= 0);

                writeStorage(`qb-prep-${code}`, selected);
                updateProgress();

                if (selected.length === items.length) {
                    toast(
                        "Suggested checklist complete. " +
                        "Confirm any additional requirements with the office."
                    );
                }
            });

            label.append(checkbox, caption);
            item.append(label);
            prepList.append(item);
        });

        prep.classList.toggle("show", items.length > 0);
        updateProgress();
    }

    function selectService(code) {
        const radio = radios.find((item) => item.value === code);

        if (!radio) return false;

        radio.checked = true;
        radio.dispatchEvent(new Event("change", { bubbles: true }));
        return true;
    }

    radios.forEach((radio) => {
        radio.addEventListener("change", () => {
            if (!radio.checked) return;

            const card = radio.closest(".service-option");

            if (ticketService) {
                ticketService.textContent = card.dataset.name;
            }

            // Keep the preview visibly separate from real token generation.
            if (ticketCode) ticketCode.textContent = "Q-XXX";

            writeStorage("qb-last-selected-service", radio.value);
            renderChecklist(radio.value);
        });
    });

    // Keyboard shortcuts work outside editable controls.
    document.addEventListener("keydown", (event) => {
        const target = event.target;

        if (
            event.ctrlKey ||
            event.metaKey ||
            event.altKey ||
            event.repeat ||
            target.isContentEditable ||
            target.closest("input, textarea, select, button")
        ) {
            return;
        }

        if (!/^[1-9]$/.test(event.key)) return;

        const index = Number(event.key) - 1;

        if (index >= radios.length) return;

        event.preventDefault();
        selectService(radios[index].value);
        radios[index].focus();
    });

    // Remember a selected service, not an unverified office visit.
    const lastService = readStorage("qb-last-selected-service");
    const previousCard = cards.find(
        (card) => card.dataset.service === lastService
    );

    if (previousCard) {
        $("#welcome-title").textContent = "Welcome back";

        $("#welcome-sub").textContent =
            `Previously selected: ${previousCard.dataset.name}.`;

        const rebook = $("#rebook");
        rebook.textContent = "Choose this service";

        rebook.addEventListener("click", () => {
            selectService(lastService);

            $("#services").scrollIntoView({
                behavior: reducedMotion ? "auto" : "smooth"
            });

            toast("Service selected. Submit when you are ready.");
        });

        $("#welcome").classList.add("show");
    }

    // Do not show visit counts from attempted submissions.
    const streak = $("#streak");
    if (streak) streak.hidden = true;

    let submitting = false;

    form.addEventListener("submit", (event) => {
        if (submitting) {
            event.preventDefault();
            return;
        }

        submitting = true;
        submitButton.disabled = true;
        submitButton.classList.add("loading");
        submitLabel.textContent = "Getting your token…";
    });

    // Restore the form when returning with the browser Back button.
    window.addEventListener("pageshow", () => {
        submitting = false;
        submitButton.disabled = false;
        submitButton.classList.remove("loading");
        submitLabel.textContent = "Get my token";

        const selected = radios.find((radio) => radio.checked);

        if (selected) {
            selected.dispatchEvent(
                new Event("change", { bubbles: true })
            );
        }
    });
})();