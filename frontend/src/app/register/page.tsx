"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { AuthShell } from "../AuthShell";
import { Avatar, Button, Field } from "@/components/Primitives";
import { Icon } from "@/components/Icon";

export default function RegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState({ displayName: "", username: "", phone: "", password: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    const next: Record<string, string> = {};
    if (!form.displayName.trim()) next.displayName = "Tell people what to call you.";
    if (!/^[a-z0-9_]{3,50}$/i.test(form.username)) {
      next.username = "3–50 characters: letters, numbers and underscores.";
    }
    if (form.password.length < 10) next.password = "At least 10 characters.";
    setErrors(next);
    if (Object.keys(next).length) return;
    setLoading(true);
    await new Promise((r) => setTimeout(r, 700));
    setLoading(false);
    router.push("/verify");
  }

  return (
    <AuthShell width={440} title="Create your account"
      subtitle="Your username is how people find you. It can't be changed later."
      footer={
        <p className="flex justify-center gap-[6px] text-md text-ink-muted">
          Already registered? <Link href="/login" className="font-medium text-ink-link">Sign in</Link>
        </p>
      }>
      <form onSubmit={submit} className="flex flex-col gap-lg" noValidate>
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
            <span className="text-sm text-ink-muted">Optional. PNG or JPG, up to 2 MB.</span>
          </div>
        </div>
        <Field id="displayName" label="Display name" value={form.displayName}
          onChange={set("displayName")} error={errors.displayName} placeholder="Ayush Swamy" />
        <Field id="username" label="Username" value={form.username} onChange={set("username")}
          error={errors.username} helper="Letters, numbers and underscores." placeholder="ayush" />
        <Field id="phone" label="Phone number" value={form.phone} onChange={set("phone")}
          helper="Optional. Used only to help friends find you." placeholder="+91 98765 43210" />
        <Field id="password" label="Password" type="password" value={form.password}
          onChange={set("password")} error={errors.password} helper="At least 10 characters." />
        <Button type="submit" loading={loading} className="w-full">Create account</Button>
      </form>
    </AuthShell>
  );
}
