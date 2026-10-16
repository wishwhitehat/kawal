import { getFirestore } from "firebase/firestore";
import { app } from "./firebase";

/** Firestore is only needed by the Intel Console, so it lives in its own chunk. */
export const db = getFirestore(app);
