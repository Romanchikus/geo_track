import { reactive } from "vue";

import { api, ApiError } from "./api";

export const auth = reactive({
  user: null,
  ready: false,
});

export async function refreshMe() {
  try {
    auth.user = await api("/users/me", { timeoutMs: 500 });
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      auth.user = null;
    } else {
      throw error;
    }
  } finally {
    auth.ready = true;
  }
}

export async function login(email, password) {
  auth.user = await api("/auth/login", { method: "POST", body: { email, password } });
}

export async function logout() {
  await api("/auth/logout", { method: "POST" });
  auth.user = null;
}
