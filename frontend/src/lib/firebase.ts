import { initializeApp } from "firebase/app";
import { getAuth, onAuthStateChanged, signInAnonymously, type User } from "firebase/auth";

export const app = initializeApp({
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
});

export const auth = getAuth(app);

let ready: Promise<User> | null = null;

/** Anonymous sign-in: zero friction for citizens, but every API call still
 * carries a verifiable Firebase ID token (rate limiting, abuse control). */
export function ensureUser(): Promise<User> {
  if (!ready) {
    ready = new Promise((resolve, reject) => {
      const stop = onAuthStateChanged(auth, (u) => {
        if (u) {
          stop();
          resolve(u);
        }
      });
      signInAnonymously(auth).catch((err) => {
        stop();
        ready = null;
        reject(err);
      });
    });
  }
  return ready;
}

export async function idToken(): Promise<string> {
  const user = await ensureUser();
  return user.getIdToken();
}
