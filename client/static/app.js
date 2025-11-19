const chatLog = document.getElementById("chat-log");
const chatForm = document.getElementById("chat-form");
const messageInput = document.getElementById("message");
const sendButton = document.getElementById("send-btn");
const endpointLabel = document.getElementById("endpoint");
const toast = document.getElementById("toast");

function showToast(text, isError = false) {
  toast.textContent = text;
  toast.classList.toggle("error", isError);
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 2400);
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

  addMessage("user", text);
  messageInput.value = "";
  messageInput.focus();

  sendButton.disabled = true;
  sendButton.textContent = "전송 중...";

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text }),
    });

    const data = await response.json();
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

chatForm.addEventListener("submit", sendMessage);
fetchEndpointInfo();
