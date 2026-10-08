(function () {
    "use strict";

    const root = document.documentElement;
    const themeToggle = document.getElementById("theme-toggle");

    function updateThemeButton() {
        if (!themeToggle) return;

        const dark = root.dataset.theme === "dark";

        themeToggle.setAttribute("aria-pressed", String(dark));
        themeToggle.setAttribute(
            "aria-label",
            dark ? "Switch to light theme" : "Switch to dark theme"
        );
    }

    if (themeToggle) {
        updateThemeButton();

        themeToggle.addEventListener("click", () => {
            const next =
                root.dataset.theme === "dark" ? "light" : "dark";

            root.dataset.theme = next;

            try {
                localStorage.setItem("qb-theme", next);
            } catch {
                // The theme still changes if storage is unavailable.
            }

            updateThemeButton();
        });
    }

    // Keep the theme consistent across open tabs.
    window.addEventListener("storage", (event) => {
        if (
            event.key === "qb-theme" &&
            ["light", "dark"].includes(event.newValue)
        ) {
            root.dataset.theme = event.newValue;
            updateThemeButton();
        }
    });

    // Staff password visibility.
    const password = document.getElementById("password");
    const passwordToggle = document.getElementById("pw-toggle");
    const capsWarning = document.getElementById("caps-warning");

    if (password && passwordToggle) {
        passwordToggle.addEventListener("click", () => {
            const show = password.type === "password";

            password.type = show ? "text" : "password";
            passwordToggle.textContent = show ? "Hide" : "Show";
            passwordToggle.setAttribute("aria-pressed", String(show));
            passwordToggle.setAttribute(
                "aria-label",
                show ? "Hide password" : "Show password"
            );
        });
    }

    if (password && capsWarning) {
        const checkCapsLock = (event) => {
            const active =
                typeof event.getModifierState === "function" &&
                event.getModifierState("CapsLock");

            capsWarning.classList.toggle("show", Boolean(active));
        };

        password.addEventListener("keydown", checkCapsLock);
        password.addEventListener("keyup", checkCapsLock);

        password.addEventListener("blur", () => {
            capsWarning.classList.remove("show");
        });
    }

    // Login loading state, including recovery after browser Back.
    const loginForm = document.getElementById("login-form");
    let loginSubmitting = false;

    function resetLogin() {
        if (!loginForm) return;

        const button = loginForm.querySelector('button[type="submit"]');

        loginSubmitting = false;
        button.disabled = false;
        button.classList.remove("is-loading");
        button.textContent = "Log in";

        if (password && passwordToggle) {
            password.type = "password";
            passwordToggle.textContent = "Show";
            passwordToggle.setAttribute("aria-pressed", "false");
            passwordToggle.setAttribute("aria-label", "Show password");
        }
    }

    if (loginForm) {
        loginForm.addEventListener("submit", (event) => {
            if (loginSubmitting) {
                event.preventDefault();
                return;
            }

            loginSubmitting = true;

            const button = loginForm.querySelector(
                'button[type="submit"]'
            );

            button.disabled = true;
            button.classList.add("is-loading");
            button.textContent = "Signing in…";
        });

        window.addEventListener("pageshow", resetLogin);
    }

    // Copy link with a manual fallback for local HTTP connections.
    const copyButton = document.getElementById("copy-link");
    const copyFeedback = document.getElementById("copy-feedback");
    const manualLink = document.getElementById("manual-link");
    const linkField = document.getElementById("token-link");

    if (copyButton && copyFeedback && manualLink && linkField) {
        copyButton.addEventListener("click", async () => {
            const url = new URL(window.location.href);
            url.hash = "";

            if (window.isSecureContext && navigator.clipboard) {
                try {
                    await navigator.clipboard.writeText(url.href);
                    manualLink.hidden = true;
                    copyFeedback.textContent =
                        "Token link copied. Keep it to return to this page.";
                    return;
                } catch {
                    // Continue to the manual-copy option.
                }
            }

            manualLink.hidden = false;
            linkField.value = url.href;
            linkField.focus();
            linkField.select();
            linkField.setSelectionRange(0, linkField.value.length);

            copyFeedback.textContent =
                "Copy the selected address using Ctrl+C, " +
                "or touch and hold it on your phone.";
        });
    }

    // Update the browser title when the token is called.
    // No automatic sound or vibration is assumed.
    const liveContent = document.getElementById("live-content");

    if (liveContent && document.body.dataset.page === "token") {
        const originalTitle = document.title;
        let previousState = "";

        const watchToken = () => {
            const ticket = liveContent.querySelector("[data-state]");
            const state = ticket ? ticket.dataset.state : "";

            if (state === previousState) return;

            previousState = state;
            document.title =
                state === "serving"
                    ? "Your turn! | Queue Busters"
                    : originalTitle;
        };

        new MutationObserver(watchToken).observe(liveContent, {
            childList: true,
            subtree: true
        });

        watchToken();
    }

    // Staff shortcuts focus controls, rather than submitting actions.
    if (document.body.dataset.page === "staff") {
        document.addEventListener("keydown", (event) => {
            const target = event.target;

            if (
                event.ctrlKey ||
                event.metaKey ||
                event.altKey ||
                event.repeat ||
                target.isContentEditable ||
                target.closest("input, textarea, select, button, a")
            ) {
                return;
            }

            const key = event.key.toLowerCase();
            let selector = null;

            if (key === "n") {
                selector = '[data-action="call-next"]:not(:disabled)';
            } else if (key === "c") {
                selector = '[data-action="complete"]:not(:disabled)';
            }

            const button = selector
                ? document.querySelector(selector)
                : null;

            if (button) {
                event.preventDefault();
                button.focus();
            }
        });
    }
})();