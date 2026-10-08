(() => {
    const content = document.getElementById("live-content");
    const connectionStatus = document.getElementById("connection-status");

    if (!content || !connectionStatus) {
        return;
    }

    let requestRunning = false;
    let lastHtml = content.innerHTML;
    let loginRequired = false;

    // Handle confirmation on forms added by live updates.
    document.addEventListener("submit", (event) => {
        const message = event.target.dataset.confirm;

        if (message && !window.confirm(message)) {
            event.preventDefault();
        }
    });

    async function updateQueue() {
        if (requestRunning || document.hidden || loginRequired) {
            return;
        }

        requestRunning = true;

        const controller = new AbortController();
        const timeout = window.setTimeout(() => {
            controller.abort();
        }, 7000);

        try {
            const response = await fetch(content.dataset.updatesUrl, {
                cache: "no-store",
                credentials: "same-origin",
                signal: controller.signal,
                headers: {
                    Accept: "application/json",
                },
            });

            if (response.status === 401) {
                const result = await response.json();
                loginRequired = true;
                window.location.assign(result.login_url);
                return;
            }

            if (!response.ok) {
                throw new Error("Queue update failed");
            }

            const result = await response.json();

            if (typeof result.html !== "string") {
                throw new Error("Invalid queue response");
            }

            // Avoid replacing a control while a keyboard user is using it.
            const controlHasFocus = content.contains(document.activeElement);

            if (result.html !== lastHtml && !controlHasFocus) {
                content.innerHTML = result.html;
                lastHtml = result.html;
            }

            const checkedAt = new Date().toLocaleTimeString();

            connectionStatus.textContent =
                `Connected · Last checked ${checkedAt}`;
            connectionStatus.className = "muted";
        } catch (error) {
            connectionStatus.textContent =
                "Connection lost · Displayed information may be out of date. Reconnecting…";
            connectionStatus.className = "notice error";
        } finally {
            window.clearTimeout(timeout);
            requestRunning = false;
        }
    }

    connectionStatus.textContent = "Connecting to the queue…";

    updateQueue();
    window.setInterval(updateQueue, 3000);

    // Check immediately when returning to the tab or reconnecting.
    document.addEventListener("visibilitychange", updateQueue);
    window.addEventListener("online", updateQueue);
})();