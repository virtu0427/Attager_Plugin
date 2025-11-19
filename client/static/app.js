const chatLog = document.getElementById("chat-log");
const chatForm = document.getElementById("chat-form");
const messageInput = document.getElementById("message");
const sendButton = document.getElementById("send-btn");
const endpointLabel = document.getElementById("endpoint");
const toast = document.getElementById("toast");
const loginPanel = document.getElementById("login-panel");
const loginForm = document.getElementById("login-form");
const loginButton = document.getElementById("login-btn");
const emailInput = document.getElementById("email");
const passwordInput = document.getElementById("password");
const userCard = document.getElementById("user-card");
const userEmail = document.getElementById("user-email");
const userTenant = document.getElementById("user-tenant");

let authToken = null;
let currentUser = null;

function showToast(text, isError = false) {
  toast.textContent = text;
  toast.classList.toggle("error", isError);
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 2400);
}

function setChatEnabled(enabled) {
  if (!messageInput || !sendButton) {
    return;
  }
  messageInput.disabled = !enabled;
  sendButton.disabled = !enabled;
  messageInput.placeholder = enabled
    ? "에이전트에게 요청을 입력하세요..."
    : "로그인 후 에이전트에게 요청을 입력하세요...";
}

function updateUserCard(user) {
  if (!userCard || !userEmail || !userTenant) {
    return;
  }
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

function resetAuthState(showMessage = false) {
  authToken = null;
  currentUser = null;
  updateUserCard(null);
  setChatEnabled(false);
  if (loginPanel) {
    loginPanel.classList.remove("logged-in");
  }
  if (showMessage) {
    addMessage("system", "세션이 만료되었습니다. 다시 로그인해 주세요.");
    showToast("세션이 만료되었습니다.", true);
  }
}

function addMessage(role, text) {
  const div = document.createElement("div");
  div.className = `message ${role}`;
  div.textContent = text;
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
}

async function sendMessage(event) {
  event.preventDefault();
  const text = messageInput.value.trim();
  if (!text) return;
  if (!authToken) {
    showToast("로그인 후 이용해 주세요.", true);
    return;
  }

  addMessage("user", text);
  messageInput.value = "";
  messageInput.focus();

  sendButton.disabled = true;
  sendButton.textContent = "전송 중...";

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${authToken}`,
      },
      body: JSON.stringify({ message: text }),
    });

    const data = await response.json();
    if (response.status === 401) {
      resetAuthState(true);
      return;
    }
    if (!response.ok) {
      const detail = data?.detail || "오류가 발생했습니다.";
      addMessage("system", detail);
      showToast(detail, true);
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

async function handleLogin(event) {
  event.preventDefault();
  const email = emailInput.value.trim();
  const password = passwordInput.value;
  if (!email || !password) {
    return;
  }

  loginButton.disabled = true;
  loginButton.textContent = "로그인 중...";

  try {
    const response = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await response.json();
    if (!response.ok) {
      const detail = data?.detail || "로그인에 실패했습니다.";
      showToast(typeof detail === "string" ? detail : "로그인에 실패했습니다.", true);
      return;
    }

    authToken = data.access_token;
    currentUser = data.user;
    updateUserCard(currentUser);
    if (loginPanel) {
      loginPanel.classList.add("logged-in");
    }
    setChatEnabled(true);
    addMessage("system", `${currentUser.email}님 로그인되었습니다.`);
    showToast("로그인에 성공했습니다.");
  } catch (error) {
    showToast(`로그인 실패: ${error.message}`, true);
  } finally {
    loginButton.disabled = false;
    loginButton.textContent = "로그인";
    passwordInput.value = "";
  }
}

function fetchEndpointInfo() {
  fetch("/api/meta")
    .then((res) => res.json())
    .then((data) => {
      endpointLabel.textContent = data.orchestrator_url || window.location.origin;
    })
    .catch(() => {
      endpointLabel.textContent = "알 수 없음";
    });
}

resetAuthState();
addMessage("system", "JWT 서버 로그인 후 채팅을 시작할 수 있습니다.");

if (chatForm) {
  chatForm.addEventListener("submit", sendMessage);
}
if (loginForm) {
  loginForm.addEventListener("submit", handleLogin);
}
fetchEndpointInfo();
