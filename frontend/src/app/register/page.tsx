"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { AuthShell } from "../AuthShell";
import { Avatar, Button, Field } from "@/components/Primitives";
import { Icon } from "@/components/Icon";
import { ApiError } from "@/lib/api";
import { useAuth, useRedirectIfSignedIn } from "@/lib/auth";

/** Mirrors the rules the API enforces, so the common mistakes are caught
 *  before a round trip. The server remains the authority — anything it rejects
 *  still comes back and is shown. */
const USERNAME = /^[a-z][a-z0-9_.]{2,49}$/;
const PHONE = /^\+?[0-9]{7,15}$/;
const MIN_PASSWORD = 8;

export default function RegisterPage() {
  const router = useRouter();
  const { signUp } = useAuth();
  useRedirectIfSignedIn();

  const [form, setForm] = useState({ displayName: "", username: "", phone: "", password: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [failure, setFailure] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const set = (key: keyof typeof form) => (event: React.ChangeEvent<HTMLInputElement>) =>
    setForm((current) => ({ ...current, [key]: event.target.value }));

  async function submit(event: FormEvent) {
    event.preventDefault();
    setFailure(null);

    const next: Record<string, string> = {};
    if (!form.displayName.trim()) next.displayName = "Tell people what to call you.";
    if (!USERNAME.test(form.username.trim().toLowerCase())) {
      next.username = "Start with a letter; 3–50 letters, digits, dots or underscores.";
    }
    if (form.password.length < MIN_PASSWORD) {
      next.password = `At least ${MIN_PASSWORD} characters.`;
    }
    const phone = form.phone.replace(/[\s-]/g, "");
    if (phone && !PHONE.test(phone)) {
      next.phone = "7–15 digits, optionally starting with +.";
    }
    setErrors(next);
    if (Object.keys(next).length) return;

    setLoading(true);
    try {
      await signUp({
        username: form.username.trim().toLowerCase(),
        password: form.password,
        displayName: form.displayName.trim(),
        phoneNumber: phone || null,
      });
      router.replace("/");
    } catch (problem) {
      setFailure(
        problem instanceof ApiError
          ? problem.message
          : "Could not create the account. Please try again.",
      );
      setLoading(false);
    }
  }

  return (
    <AuthShell
      width={440}
      title="Create your account"
      subtitle="Your username is how people find you. It can't be changed later."
      footer={
        <p className="flex justify-center gap-[6px] text-md text-ink-muted">
          Already registered?{" "}
          <Link href="/login" className="font-medium text-ink-link">Sign in</Link>
        </p>
      }
    >
      <form onSubmit={submit} className="flex flex-col gap-lg" noValidate>
        {failure && (
          <p role="alert"
            className="flex items-start gap-sm rounded-md bg-accent-subtle px-md py-[11px]
              text-md font-medium text-ink-danger">
            <Icon name="warn" size={16} strokeWidth={1.9} className="mt-[2px] shrink-0" />
            {failure}
          </p>
        )}

        <div className="flex items-center gap-lg">
          <span className="relative">
            <Avatar name={form.displayName || "New user"} size={64} accent />
            <span className="absolute -bottom-[2px] -right-[2px] flex h-[26px] w-[26px] items-center
              justify-center rounded-full border border-line bg-surface text-ink-muted">
              <Icon name="camera" size={14} strokeWidth={1.7} />
            </span>
          </span>
          <div className="flex flex-col gap-[2px]">
            <span className="text-md font-medium">Profile photo</span>
            <span className="text-sm text-ink-muted">Not yet supported — a placeholder for now.</span>
          </div>
        </div>

        <Field id="displayName" label="Display name" value={form.displayName}
          onChange={set("displayName")} error={errors.displayName} placeholder="Ayush Swamy"
          autoComplete="name" maxLength={100} />
        <Field id="username" label="Username" value={form.username} onChange={set("username")}
          error={errors.username} helper="Lowercase letters, digits, dots and underscores."
          placeholder="ayush" autoComplete="username" />
        <Field id="phone" label="Phone number" value={form.phone} onChange={set("phone")}
          error={errors.phone} helper="Optional. Used only to help friends find you."
          placeholder="+91 98765 43210" autoComplete="tel" />
        <Field id="password" label="Password" type="password" value={form.password}
          onChange={set("password")} error={errors.password}
          helper={`At least ${MIN_PASSWORD} characters.`} autoComplete="new-password" />
        <Button type="submit" loading={loading} className="w-full">Create account</Button>
      </form>
    </AuthShell>
  );
}
