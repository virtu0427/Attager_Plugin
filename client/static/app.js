const page = document.body.dataset.page || "login";
const toast = document.getElementById("toast");

function showToast(text, isError = false) {
  if (!toast) return;
  toast.textContent = text;
  toast.classList.toggle("error", isError);
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 2400);
}

function initLoginPage() {
  const loginForm = document.getElementById("login-form");
  const emailInput = document.getElementById("email");
  const passwordInput = document.getElementById("password");
  const loginButton = document.getElementById("login-btn");

  if (!loginForm || !emailInput || !passwordInput || !loginButton) {
    return;
  }

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const email = emailInput.value.trim();
    const password = passwordInput.value;
    if (!email || !password) {
      showToast("이메일과 비밀번호를 입력해 주세요.", true);
      return;
    }

    loginButton.disabled = true;
    loginButton.textContent = "로그인 중...";

    try {
      const response = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ email, password }),
      });
      const data = await response.json();
      if (!response.ok) {
        const detail = data?.detail || "로그인에 실패했습니다.";
        const message = typeof detail === "string" ? detail : "로그인에 실패했습니다.";
        showToast(message, true);
        return;
      }

      showToast("로그인에 성공했습니다.");
      window.location.href = "/chat";
    } catch (error) {
      showToast(`로그인 실패: ${error.message}`, true);
    } finally {
      loginButton.disabled = false;
      loginButton.textContent = "로그인";
      passwordInput.value = "";
    }
  });
}

function initChatPage() {
  const chatLog = document.getElementById("chat-log");
  const chatForm = document.getElementById("chat-form");
  const messageInput = document.getElementById("message");
  const sendButton = document.getElementById("send-btn");
  const userCard = document.getElementById("user-card");
  const userEmail = document.getElementById("user-email");
  const userTenant = document.getElementById("user-tenant");
  const logoutButton = document.getElementById("logout-btn");
  const endpointLabel = document.getElementById("endpoint");

  if (!chatLog || !chatForm || !messageInput || !sendButton) {
    return;
  }

  function addMessage(role, text) {
    const div = document.createElement("div");
    div.className = `message ${role}`;
    div.textContent = text;
    chatLog.appendChild(div);
    chatLog.scrollTop = chatLog.scrollHeight;
  }

  function setChatEnabled(enabled) {
    messageInput.disabled = !enabled;
    sendButton.disabled = !enabled;
    messageInput.placeholder = enabled
      ? "에이전트에게 요청을 입력하세요..."
      : "세션 확인 중...";
  }

  function updateUserCard(user) {
    if (!userCard || !userEmail || !userTenant) {
      return;
    }
    if (!user) {
      userCard.classList.add("inactive");
      userEmail.textContent = "세션 없음";
      userTenant.textContent = "로그인 후 이용해 주세요.";
      return;
    }

    const tenants = Array.isArray(user.tenants) && user.tenants.length > 0
      ? user.tenants.join(", ")
      : "연결된 테넌트 없음";
    userCard.classList.remove("inactive");
    userEmail.textContent = user.email;
    userTenant.textContent = tenants;
  }

  async function fetchEndpointInfo() {
    if (!endpointLabel) return;
    try {
      const response = await fetch("/api/meta");
      const data = await response.json();
      endpointLabel.textContent = data.orchestrator_url || window.location.origin;
    } catch (error) {
      endpointLabel.textContent = "알 수 없음";
    }
  }

  async function bootstrapSession() {
    try {
      const response = await fetch("/api/session", { credentials: "same-origin" });
      if (response.status === 401) {
        window.location.href = "/login";
        return null;
      }
      const data = await response.json();
      if (!response.ok) {
        showToast("세션을 확인하지 못했습니다.", true);
        window.location.href = "/login";
        return null;
      }

      updateUserCard(data.user);
      setChatEnabled(true);
      addMessage("system", `${data.user.email}님 환영합니다.`);
      return data;
    } catch (error) {
      showToast("세션 확인 실패", true);
      window.location.href = "/login";
      return null;
    }
  }

  async function sendMessage(event) {
    event.preventDefault();
    const text = messageInput.value.trim();
    if (!text) return;

    addMessage("user", text);
    messageInput.value = "";
    messageInput.focus();

    sendButton.disabled = true;
    sendButton.textContent = "전송 중...";

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ message: text }),
      });
      const data = await response.json();
      if (response.status === 401) {
        showToast("세션이 만료되었습니다.", true);
        window.location.href = "/login";
        return;
      }
      if (!response.ok) {
        const detail = data?.detail || "오류가 발생했습니다.";
        addMessage("system", typeof detail === "string" ? detail : "오류가 발생했습니다.");
        showToast("요청 실패", true);
        return;
      }
      addMessage("agent", data.reply || "응답 없음");
    } catch (error) {
      addMessage("system", `요청 실패: ${error.message}`);
      showToast(error.message, true);
    } finally {
      sendButton.disabled = false;
      sendButton.textContent = "전송";
    }
  }

  if (logoutButton) {
    logoutButton.addEventListener("click", async () => {
      try {
        await fetch("/api/logout", { method: "POST", credentials: "same-origin" });
      } finally {
        window.location.href = "/login";
      }
    });
  }

  chatForm.addEventListener("submit", sendMessage);
  fetchEndpointInfo();
  bootstrapSession();
}

if (page === "login") {
  initLoginPage();
} else if (page === "chat") {
  initChatPage();
}
