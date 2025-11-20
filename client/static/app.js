const page = document.body.dataset.page || "login";
const toast = document.getElementById("toast");

function showToast(text, isError = false) {
  if (!toast) return;
  toast.textContent = text;
  toast.classList.toggle("error", isError);
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 2400);
}

function setButtonLoading(button, isLoading, label, loadingLabel) {
  if (!button) return;
  button.disabled = isLoading;
  button.textContent = isLoading ? loadingLabel : label;
}

// -----------------------
// 로그인 페이지 전용 로직
// -----------------------
if (page === "login") {
  const loginForm = document.getElementById("login-form");
  const loginButton = document.getElementById("login-btn");
  const emailInput = document.getElementById("email");
  const passwordInput = document.getElementById("password");
  const sessionHint = document.getElementById("session-hint");

  async function redirectIfAuthenticated() {
    try {
      const response = await fetch("/api/session", { credentials: "include" });
      if (!response.ok) return;
      const data = await response.json();
      if (data.authenticated) {
        window.location.href = "/chat";
        return;
      }
      if (sessionHint) {
        sessionHint.textContent = "로그인 후 채팅 페이지로 이동합니다.";
      }
    } catch (error) {
      console.error("세션 조회 실패", error);
    }
  }

  async function handleLogin(event) {
    event.preventDefault();
    const email = emailInput.value.trim();
    const password = passwordInput.value;
    if (!email || !password) return;

    setButtonLoading(loginButton, true, "로그인", "로그인 중...");

    try {
      const response = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email, password }),
      });
      const data = await response.json();
      if (!response.ok) {
        const detail = data?.detail || "로그인에 실패했습니다.";
        showToast(typeof detail === "string" ? detail : "로그인에 실패했습니다.", true);
        return;
      }

      showToast("로그인에 성공했습니다.");
      window.location.href = "/chat";
    } catch (error) {
      showToast(`로그인 실패: ${error.message}`, true);
    } finally {
      setButtonLoading(loginButton, false, "로그인", "로그인 중...");
      passwordInput.value = "";
    }
  }

  redirectIfAuthenticated();

  if (loginForm) {
    loginForm.addEventListener("submit", handleLogin);
  }
}

// -----------------------
// 채팅 페이지 전용 로직
// -----------------------
if (page === "chat") {
  const chatLog = document.getElementById("chat-log");
  const chatForm = document.getElementById("chat-form");
  const messageInput = document.getElementById("message");
  const sendButton = document.getElementById("send-btn");
  const endpointLabel = document.getElementById("endpoint");
  const logoutButton = document.getElementById("logout-btn");
  const userCard = document.getElementById("user-card");
  const userEmail = document.getElementById("user-email");
  const userTenant = document.getElementById("user-tenant");

  let currentUser = null;

  function addMessage(role, text) {
    if (!chatLog) return;
    const div = document.createElement("div");
    div.className = `message ${role}`;
    div.textContent = text;
    chatLog.appendChild(div);
    chatLog.scrollTop = chatLog.scrollHeight;
  }

  function setChatEnabled(enabled) {
    if (!messageInput || !sendButton) return;
    messageInput.disabled = !enabled;
    sendButton.disabled = !enabled;
    messageInput.placeholder = enabled
      ? "에이전트에게 요청을 입력하세요..."
      : "로그인 후 에이전트에게 요청을 입력하세요...";
  }

  function updateUserCard(user) {
    if (!userCard || !userEmail || !userTenant) return;
    if (!user) {
      userCard.classList.add("inactive");
      userEmail.textContent = "로그인 필요";
      userTenant.textContent = "JWT 인증을 완료해 주세요.";
      return;
    }
    const tenants = Array.isArray(user.tenants) && user.tenants.length > 0
      ? user.tenants.join(", ")
      : "연결된 테넌트 없음";
    userCard.classList.remove("inactive");
    userEmail.textContent = user.email;
    userTenant.textContent = tenants;
  }

  async function ensureSession() {
    try {
      const response = await fetch("/api/session", { credentials: "include" });
      if (!response.ok) {
        window.location.href = "/login";
        return null;
      }
      const data = await response.json();
      if (!data.authenticated) {
        window.location.href = "/login";
        return null;
      }
      currentUser = data.user;
      setChatEnabled(true);
      updateUserCard(currentUser);
      addMessage("system", `${currentUser.email}님 세션이 복구되었습니다.`);
      return currentUser;
    } catch (error) {
      console.error("세션 확인 실패", error);
      window.location.href = "/login";
      return null;
    }
  }

  async function fetchEndpointInfo() {
    try {
      const res = await fetch("/api/meta");
      const data = await res.json();
      if (endpointLabel) {
        endpointLabel.textContent = data.orchestrator_url || window.location.origin;
      }
    } catch (error) {
      if (endpointLabel) {
        endpointLabel.textContent = "알 수 없음";
      }
    }
  }

  async function sendMessage(event) {
    event.preventDefault();
    if (!currentUser) {
      showToast("로그인 후 이용해 주세요.", true);
      window.location.href = "/login";
      return;
    }

    const text = messageInput.value.trim();
    if (!text) return;

    addMessage("user", text);
    messageInput.value = "";
    messageInput.focus();

    setButtonLoading(sendButton, true, "전송", "전송 중...");

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(currentUser?.email ? { "X-User-Email": currentUser.email } : {}),
        },
        body: JSON.stringify({ message: text }),
        credentials: "include",
      });
      const data = await response.json();
      if (!response.ok) {
        const detail = data?.detail || "오류가 발생했습니다.";
        addMessage("system", typeof detail === "string" ? detail : "오류가 발생했습니다.");
        showToast(typeof detail === "string" ? detail : "오류가 발생했습니다.", true);
        if (response.status === 401) {
          window.location.href = "/login";
        }
        return;
      }
      addMessage("agent", data.reply || "응답 없음");
    } catch (error) {
      addMessage("system", `요청 실패: ${error.message}`);
      showToast(error.message, true);
    } finally {
      setButtonLoading(sendButton, false, "전송", "전송 중...");
    }
  }

  async function handleLogout() {
    try {
      await fetch("/api/logout", { method: "POST", credentials: "include" });
    } catch (error) {
      console.error("로그아웃 실패", error);
    } finally {
      window.location.href = "/login";
    }
  }

  fetchEndpointInfo();
  setChatEnabled(false);
  addMessage("system", "JWT 서버 로그인 후 채팅을 시작할 수 있습니다.");
  ensureSession();

  if (chatForm) {
    chatForm.addEventListener("submit", sendMessage);
  }
  if (logoutButton) {
    logoutButton.addEventListener("click", handleLogout);
  }
}
