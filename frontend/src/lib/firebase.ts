import { initializeApp } from "firebase/app";
import { getToken, initializeAppCheck, ReCaptchaEnterpriseProvider, type AppCheck } from "firebase/app-check";
import { getAuth, onAuthStateChanged, signInAnonymously, type User } from "firebase/auth";

export const app = initializeApp({
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
});

// App Check (reCAPTCHA Enterprise, invisible): proves requests come from this web
// app, so scripts can't burn the project's AI quota. Initialised before Auth so
// anonymous sign-up is attested too.
const siteKey = import.meta.env.VITE_RECAPTCHA_SITE_KEY as string | undefined;
export const appCheck: AppCheck | null = siteKey
  ? initializeAppCheck(app, { provider: new ReCaptchaEnterpriseProvider(siteKey), isTokenAutoRefreshEnabled: true })
  : null;

export async function appCheckToken(): Promise<string | undefined> {
  if (!appCheck) return undefined;
  try {
    return (await getToken(appCheck, false)).token;
  } catch (e) {
    console.warn("App Check token unavailable", e);
    return undefined;
  }
}

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
