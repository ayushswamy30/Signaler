"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { AuthShell } from "../AuthShell";
import { Button, Field } from "@/components/Primitives";
import { Icon } from "@/components/Icon";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!username.trim() || !password) {
      setError("Enter both your username and password.");
      return;
    }
    setLoading(true);
    // No auth endpoint exists yet (A04); this stands in for the real call.
    await new Promise((r) => setTimeout(r, 700));
    setLoading(false);
    if (password.length < 4) {
      setError("That username and password don't match. Check both and try again.");
      return;
    }
    router.push("/");
  }

  return (
    <AuthShell title="Sign in" subtitle="Use the username and password you registered with."
      footer={
        <p className="flex justify-center gap-[6px] text-md text-ink-muted">
          New here? <Link href="/register" className="font-medium text-ink-link">Create an account</Link>
        </p>
      }>
      <form onSubmit={submit} className="flex flex-col gap-lg" noValidate>
        {error && (
          <p role="alert" className="flex items-start gap-sm rounded-md px-md py-[11px] text-md font-medium"
            style={{ background: "#FBE3E3", color: "#B32B2B" }}>
            <Icon name="warn" size={16} strokeWidth={1.9} />{error}
          </p>
        )}
        <Field id="username" label="Username" autoComplete="username" value={username}
          onChange={(e) => setUsername(e.target.value)} placeholder="ayush" />
        <Field id="password" label="Password" type="password" autoComplete="current-password"
          value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
        <Button type="submit" loading={loading} className="w-full">Sign in</Button>
      </form>
    </AuthShell>
  );
}
