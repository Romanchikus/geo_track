<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import { api, fetchAll } from "../api";
import { auth } from "../auth";

const router = useRouter();
const users = ref([]);
const error = ref("");
const email = ref("");
const password = ref("");
const editEmail = ref(auth.user?.email ?? "");
const editPassword = ref("");
const pending = ref(false);

async function load() {
  error.value = "";
  const result = await fetchAll("/users");
  users.value = result.rows;
}

async function createUser() {
  error.value = "";
  pending.value = true;
  try {
    await api("/users", { method: "POST", body: { email: email.value, password: password.value } });
    email.value = "";
    password.value = "";
    await load();
  } catch (err) {
    error.value = err.message;
  } finally {
    pending.value = false;
  }
}

async function saveSelf() {
  error.value = "";
  const body = {};
  if (editEmail.value !== auth.user.email) body.email = editEmail.value;
  if (editPassword.value) body.password = editPassword.value;
  if (!body.email && !body.password) return;
  pending.value = true;
  try {
    const updated = await api(`/users/${auth.user.id}`, { method: "PATCH", body });
    auth.user = updated;
    editEmail.value = updated.email;
    editPassword.value = "";
    await load();
  } catch (err) {
    error.value = err.message;
  } finally {
    pending.value = false;
  }
}

async function removeSelf() {
  if (!window.confirm("Delete your account? This logs you out.")) return;
  error.value = "";
  pending.value = true;
  try {
    await api(`/users/${auth.user.id}`, { method: "DELETE" });
    auth.user = null;
    await router.push("/login");
  } catch (err) {
    error.value = err.message;
    pending.value = false;
  }
}

onMounted(load);
</script>

<template>
  <section>
    <h1>Users</h1>
    <p class="muted">You can change or delete only your own account. Creating a user does not switch the session.</p>
    <p v-if="error" class="error">{{ error }}</p>

    <form class="card row" @submit.prevent="createUser">
      <label>
        Email
        <input v-model="email" type="email" required />
      </label>
      <label>
        Password
        <input v-model="password" type="password" minlength="8" required />
      </label>
      <button type="submit" class="btn btn-primary" :disabled="pending">Add user</button>
    </form>

    <table>
      <thead>
        <tr>
          <th>Id</th>
          <th>Email</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="user in users" :key="user.id">
          <td>{{ user.id }}</td>
          <td>{{ user.email }}</td>
          <td>{{ user.id === auth.user.id ? "You" : "" }}</td>
        </tr>
        <tr v-if="users.length === 0">
          <td colspan="3">No users yet.</td>
        </tr>
      </tbody>
    </table>

    <form class="card" @submit.prevent="saveSelf">
      <h2>Your account</h2>
      <label>
        Email
        <input v-model="editEmail" type="email" required />
      </label>
      <label>
        New password
        <input v-model="editPassword" type="password" minlength="8" placeholder="Leave blank to keep the current password" />
      </label>
      <div class="actions">
        <button type="submit" class="btn btn-primary" :disabled="pending">Save</button>
        <button type="button" class="btn btn-outline-danger" :disabled="pending" @click="removeSelf">Delete account</button>
      </div>
    </form>
  </section>
</template>
