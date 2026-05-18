const providerDefaults = {
  "SiliconFlow": "https://api.siliconflow.cn/v1",
  "OpenRouter": "https://openrouter.ai/api/v1",
  "One API / New API": "https://your-one-api.example.com/v1",
  "LiteLLM": "http://localhost:4000/v1",
  "Custom": ""
};

const recommendedDefaults = {
  AI_TIMEOUT: "45",
  AI_MAX_RETRIES: "0",
  SCAN_INTERVAL_MIN: "90",
  SCAN_INTERVAL_MAX: "180",
  BLOCKED_SLEEP_SECONDS: "1800"
};

const loginView = document.querySelector("#loginView");
const adminView = document.querySelector("#adminView");
const loginForm = document.querySelector("#loginForm");
const modelForm = document.querySelector("#modelForm");
const telegramForm = document.querySelector("#telegramForm");
const logs = document.querySelector("#logs");
const toast = document.querySelector("#toast");
const provider = document.querySelector("#provider");
const baseUrl = document.querySelector("#baseUrl");

let adminSession = sessionStorage.getItem("adminSession") || "";

function setStatus(id, message, type = "info") {
  const el = document.querySelector(id);
  if (!el) return;
  el.textContent = message;
  el.className = `status ${type}`;
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  window.setTimeout(() => toast.classList.remove("show"), 2600);
}

function authHeaders() {
  return {
    "x-admin-session": adminSession
  };
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "content-type": "application/json",
      ...authHeaders(),
      ...(options.headers || {})
    }
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || `请求失败：${response.status}`);
  }
  return response.json();
}

async function login(username, password) {
  const response = await fetch("/api/auth/login", {
    method: "POST",
    headers: {"content-type": "application/json"},
    body: JSON.stringify({username, password})
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || "登录失败");
  }
  return response.json();
}

function viewAdmin() {
  loginView.hidden = true;
  adminView.hidden = false;
}

function viewLogin() {
  adminView.hidden = true;
  loginView.hidden = false;
}

function fillForm(form, config) {
  for (const element of form.elements) {
    if (!element.name || !(element.name in config)) {
      continue;
    }
    element.value = config[element.name] || "";
  }
}

function fillDefaults() {
  for (const [name, value] of Object.entries(recommendedDefaults)) {
    const element = modelForm.elements[name];
    if (element && !element.value) {
      element.value = value;
    }
  }
}

async function loadConfig() {
  const data = await api("/api/config");
  fillForm(modelForm, data.config);
  fillForm(telegramForm, data.config);
  fillDefaults();
}

async function loadLogs() {
  const data = await api("/api/logs?lines=800");
  logs.textContent = data.logs || "暂无日志";
  logs.scrollTop = logs.scrollHeight;
}

function formConfig(form) {
  return Object.fromEntries(new FormData(form).entries());
}

async function loadAdmin() {
  viewAdmin();
  await Promise.all([loadConfig(), loadLogs()]);
}

provider.addEventListener("change", () => {
  const nextUrl = providerDefaults[provider.value];
  if (nextUrl) {
    baseUrl.value = nextUrl;
  }
});

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const username = document.querySelector("#loginUsername").value.trim();
  const password = document.querySelector("#loginPassword").value;
  setStatus("#loginStatus", "正在登录...");
  try {
    const data = await login(username, password);
    adminSession = data.session || "";
    sessionStorage.setItem("adminSession", adminSession);
    setStatus("#loginStatus", data.message || "登录成功", "success");
    await loadAdmin();
    showToast("登录成功");
  } catch (error) {
    setStatus("#loginStatus", error.message, "error");
  }
});

modelForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  setStatus("#modelStatus", "正在保存模型配置...");
  try {
    const data = await api("/api/config", {
      method: "POST",
      body: JSON.stringify({config: formConfig(modelForm)})
    });
    fillForm(modelForm, data.config);
    fillDefaults();
    setStatus("#modelStatus", data.message || "模型配置已保存", "success");
    showToast("模型配置已保存");
  } catch (error) {
    setStatus("#modelStatus", error.message, "error");
    showToast(error.message);
  }
});

telegramForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  setStatus("#telegramStatus", "正在保存 Telegram 配置...");
  try {
    const data = await api("/api/config", {
      method: "POST",
      body: JSON.stringify({config: formConfig(telegramForm)})
    });
    fillForm(telegramForm, data.config);
    setStatus("#telegramStatus", data.message || "Telegram 配置已保存", "success");
    showToast("Telegram 配置已保存");
  } catch (error) {
    setStatus("#telegramStatus", error.message, "error");
    showToast(error.message);
  }
});

document.querySelector("#refreshLogs").addEventListener("click", async () => {
  setStatus("#logsStatus", "正在刷新日志...");
  try {
    await loadLogs();
    setStatus("#logsStatus", "日志已刷新", "success");
    showToast("日志已刷新");
  } catch (error) {
    setStatus("#logsStatus", error.message, "error");
    showToast(error.message);
  }
});

document.querySelector("#clearLogs").addEventListener("click", async () => {
  if (!window.confirm("确定清空运行日志？")) {
    return;
  }
  setStatus("#logsStatus", "正在清空日志...");
  try {
    const data = await api("/api/logs/clear", {method: "POST"});
    await loadLogs();
    setStatus("#logsStatus", data.message || "日志已清空", "success");
    showToast("日志已清空");
  } catch (error) {
    setStatus("#logsStatus", error.message, "error");
    showToast(error.message);
  }
});

document.querySelector("#logoutBtn").addEventListener("click", () => {
  adminSession = "";
  sessionStorage.removeItem("adminSession");
  viewLogin();
});

if (adminSession) {
  loadAdmin().catch((error) => {
    sessionStorage.removeItem("adminSession");
    adminSession = "";
    setStatus("#loginStatus", error.message, "error");
    viewLogin();
  });
} else {
  viewLogin();
}

window.setInterval(() => {
  if (!adminView.hidden) {
    loadLogs().catch(() => {});
  }
}, 10000);
