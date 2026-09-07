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
import { api, tokens } from "./api";
import { toMe } from "./adapt";
import { socket } from "./socket";
import type { Me } from "./types";

interface AuthValue {
  user: Me | null;
  /** True until the stored token has been checked; screens wait on this rather
   *  than flashing the sign-in page at an already-authenticated user. */
  loading: boolean;
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

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  // On first load, a stored token is only a claim; the server decides whether
  // it is still a session. Failing here is normal (expired, revoked, or none)
  // and simply means signed out.
  useEffect(() => {
    let cancelled = false;

    (async () => {
      if (!tokens.access) {
        setLoading(false);
        return;
      }
      try {
        const me = toMe(await api.me());
        if (!cancelled) {
          setUser(me);
          socket.connect();
        }
      } catch {
        tokens.clear();
      } finally {
        if (!cancelled) setLoading(false);
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
    () => ({ user, loading, signIn, signUp, signOut, setUser }),
    [user, loading, signIn, signUp, signOut],
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
