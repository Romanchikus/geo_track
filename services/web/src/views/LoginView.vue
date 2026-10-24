<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";

import { api } from "../api";
import { login } from "../auth";

const router = useRouter();
const mode = ref("login");
const email = ref("");
const password = ref("");
const error = ref("");
const notice = ref("");
const pending = ref(false);

async function submit() {
  error.value = "";
  notice.value = "";
  pending.value = true;
  try {
    if (mode.value === "register") {
      await api("/users", { method: "POST", body: { email: email.value, password: password.value } });
      mode.value = "login";
      notice.value = "Account created. Log in to continue.";
      return;
    }
    await login(email.value, password.value);
    await router.push("/subscriptions");
  } catch (err) {
    error.value = err.message;
  } finally {
    pending.value = false;
  }
}
</script>

<template>
  <section class="card narrow">
    <h1>{{ mode === "login" ? "Log in" : "Create account" }}</h1>
    <p class="muted">Session stays in a cookie. Password must be at least 8 characters.</p>
    <form @submit.prevent="submit">
      <label>
        Email
        <input v-model="email" type="email" autocomplete="username" required />
      </label>
      <label>
        Password
        <input v-model="password" type="password" autocomplete="current-password" minlength="8" required />
      </label>
      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="notice" class="notice">{{ notice }}</p>
      <button type="submit" class="btn btn-primary" :disabled="pending">
        {{ mode === "login" ? "Log in" : "Register" }}
      </button>
    </form>
    <button type="button" class="btn btn-link" @click="mode = mode === 'login' ? 'register' : 'login'">
      {{ mode === "login" ? "Need an account? Register" : "Already registered? Log in" }}
    </button>
  </section>
</template>
