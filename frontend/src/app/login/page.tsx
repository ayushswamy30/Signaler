"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { AuthShell } from "../AuthShell";
import { Button, Field } from "@/components/Primitives";
import { Icon } from "@/components/Icon";
import { ApiError } from "@/lib/api";
import { useAuth, useRedirectIfSignedIn } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const { signIn } = useAuth();
  useRedirectIfSignedIn();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (!username.trim() || !password) {
      setError("Enter both your username and password.");
      return;
    }

    setLoading(true);
    try {
      await signIn(username.trim(), password);
      router.replace("/");
    } catch (problem) {
      // The backend deliberately gives one message for a wrong username and a
      // wrong password, so it is shown as-is rather than re-worded per field.
      setError(
        problem instanceof ApiError ? problem.message : "Could not sign in. Please try again.",
      );
      setLoading(false);
    }
  }

  return (
    <AuthShell
      title="Sign in"
      subtitle="Use the username and password you registered with."
      footer={
        <p className="flex justify-center gap-[6px] text-md text-ink-muted">
          New here?{" "}
          <Link href="/register" className="font-medium text-ink-link">Create an account</Link>
        </p>
      }
    >
      <form onSubmit={submit} className="flex flex-col gap-lg" noValidate>
        {error && (
          <p role="alert"
            className="flex items-start gap-sm rounded-md bg-accent-subtle px-md py-[11px]
              text-md font-medium text-ink-danger">
            <Icon name="warn" size={16} strokeWidth={1.9} className="mt-[2px] shrink-0" />
            {error}
          </p>
        )}
        <Field id="username" label="Username" autoComplete="username" value={username}
          onChange={(event) => setUsername(event.target.value)} placeholder="ayush" />
        <Field id="password" label="Password" type="password" autoComplete="current-password"
          value={password} onChange={(event) => setPassword(event.target.value)}
          placeholder="••••••••" />
        <Button type="submit" loading={loading} className="w-full">Sign in</Button>
      </form>
    </AuthShell>
  );
}
