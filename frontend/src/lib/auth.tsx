"use client";

/** Session state, shared by every screen.
 *
 *  One provider at the root holds the signed-in user; `useAuth` reads it and
 *  `useRequireAuth` is what a protected page calls to be sent to /login when
 *  there is no session. */

import { useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { ApiError, api, tokens } from "./api";
import { toMe } from "./adapt";
import { socket } from "./socket";
import type { Me } from "./types";

interface AuthValue {
  user: Me | null;
  /** True until the stored token has been checked; screens wait on this rather
   *  than flashing the sign-in page at an already-authenticated user. */
  loading: boolean;
  /** The session check has already failed to reach the server at least once
   *  and is retrying. Screens use it to say what is happening instead of
   *  showing a loading state that looks identical to a broken page. */
  waking: boolean;
  signIn: (username: string, password: string) => Promise<void>;
  signUp: (input: {
    username: string;
    password: string;
    displayName: string;
    phoneNumber?: string | null;
  }) => Promise<void>;
  signOut: () => Promise<void>;
  /** Replace the cached user after a profile edit. */
  setUser: (user: Me) => void;
}

const AuthContext = createContext<AuthValue | null>(null);

/** How long one session check may take before it is retried. Short, because
 *  the whole UI is held behind it; a sleeping server is answered by retrying,
 *  not by waiting longer on an attempt that is already stuck. */
const BOOT_ATTEMPT_MS = 5_000;
/** How long to keep retrying before rendering anyway, in total wall time.
 *  Comfortably covers a free-tier cold start, and bounds the worst case at
 *  "about a minute", not "forever". Landing on /login at the end of it is not
 *  a dead end: by then the retries have woken the server, so signing in
 *  answers immediately. */
const BOOT_BUDGET_MS = 60_000;
/** The longest gap between retries. */
const BOOT_RETRY_CAP_MS = 8_000;

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [waking, setWaking] = useState(false);

  // On first load, a stored token is only a claim; the server decides whether
  // it is still a session. Failing here is normal (expired, revoked, or none)
  // and simply means signed out.
  //
  // The one failure that is *not* normal is the server not answering. The
  // backend sleeps after 15 minutes without traffic and takes the better part
  // of a minute to wake, and this check used to await it with no timeout: the
  // whole app sat on its loading screen until the request eventually resolved,
  // which for a connection that is accepted and then ignored can be minutes.
  // Nothing moved, nothing said why, and the sign-in page was unreachable --
  // so anyone with an old token in localStorage could not even get to the form
  // that would have fixed it.
  //
  // So each attempt is given a short deadline of its own and retried while the
  // server wakes, and the whole thing is given a budget. When the budget runs
  // out the app stops waiting and renders: `useRequireAuth` then sends the
  // visitor to /login, which is the one screen that works without the session
  // this check could not confirm. The tokens are deliberately kept -- an
  // unreachable server is no evidence that a session has ended, and throwing
  // it away would sign people out over a network blip.
  useEffect(() => {
    let cancelled = false;

    (async () => {
      if (!tokens.access) {
        setLoading(false);
        return;
      }

      // Both the attempt and the pause after it are clamped to what is left of
      // the budget, so the total wait really is the budget. Checking the
      // deadline only after an attempt had already run let the last one
      // overshoot it by its own timeout plus a backoff -- a "60 second" budget
      // that took 100 seconds to give up.
      const deadline = Date.now() + BOOT_BUDGET_MS;
      for (let attempt = 0; !cancelled; attempt += 1) {
        const remaining = deadline - Date.now();
        if (remaining <= 0) break;
        try {
          const me = toMe(await api.me(Math.min(BOOT_ATTEMPT_MS, remaining)));
          if (cancelled) return;
          setUser(me);
          socket.connect();
          break;
        } catch (problem) {
          if (cancelled) return;

          // The server answered, and its answer was no: the token is expired
          // or revoked. That is settled -- retrying cannot change it.
          //
          // Only a 4xx counts as that answer. A 5xx is the server having a
          // problem, not the session having ended -- and a waking instance
          // behind a proxy answers 502 for a moment before it is ready, so
          // treating that as "signed out" would throw away a perfectly good
          // session for having arrived a second too early.
          if (problem instanceof ApiError && problem.status >= 400 && problem.status < 500) {
            tokens.clear();
            break;
          }

          // It said nothing, or nothing useful. Keep trying until the budget
          // is spent, backing off so a genuinely dead server is not hammered.
          setWaking(true);
          const left = deadline - Date.now();
          if (left <= 0) break;
          await new Promise((resume) =>
            setTimeout(resume, Math.min(BOOT_RETRY_CAP_MS, 1000 * 2 ** attempt, left)),
          );
        }
      }

      if (!cancelled) {
        setWaking(false);
        setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  const signIn = useCallback(async (username: string, password: string) => {
    const token = await api.login({ username, password });
    tokens.save(token);
    setUser(toMe(token.user));
    socket.connect();
  }, []);

  const signUp = useCallback<AuthValue["signUp"]>(async (input) => {
    const token = await api.register({
      username: input.username,
      password: input.password,
      display_name: input.displayName,
      phone_number: input.phoneNumber ?? null,
    });
    tokens.save(token);
    setUser(toMe(token.user));
    socket.connect();
  }, []);

  const signOut = useCallback(async () => {
    const refresh = tokens.refresh;
    socket.close();
    // The local session is cleared whatever the server says: a failed logout
    // must not leave someone stuck signed in on a shared machine.
    if (refresh) await api.logout(refresh).catch(() => undefined);
    tokens.clear();
    setUser(null);
  }, []);

  const value = useMemo<AuthValue>(
    () => ({ user, loading, waking, signIn, signUp, signOut, setUser }),
    [user, loading, waking, signIn, signUp, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>.");
  return context;
}

/** Redirect to /login unless signed in. Returns the user once there is one. */
export function useRequireAuth(): Me | null {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  return user;
}

/** The mirror image, for /login and /register: send an already-signed-in user
 *  to the app instead of showing them a form they do not need. */
export function useRedirectIfSignedIn() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && user) router.replace("/");
  }, [loading, user, router]);
}
