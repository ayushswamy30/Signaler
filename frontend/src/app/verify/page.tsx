"use client";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { AuthShell } from "../AuthShell";
import { Button } from "@/components/Primitives";
import { Icon } from "@/components/Icon";

export default function VerifyPage() {
  const router = useRouter();
  const [digits, setDigits] = useState<string[]>(Array(6).fill(""));
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const refs = useRef<Array<HTMLInputElement | null>>([]);

  function setDigit(i: number, v: string) {
    const ch = v.replace(/\D/g, "").slice(-1);
    setDigits((d) => { const n = [...d]; n[i] = ch; return n; });
    if (ch && i < 5) refs.current[i + 1]?.focus();
  }

  async function verify() {
    const code = digits.join("");
    if (code.length < 6) { setError("Enter all six digits."); return; }
    setLoading(true);
    await new Promise((r) => setTimeout(r, 700));
    setLoading(false);
    if (code !== "492715") { setError("That code has expired. Request a new one below."); return; }
    router.push("/");
  }

  return (
    <AuthShell width={420} title="Verify your number"
      subtitle="We sent a 6-digit code to +91 98••• ••210."
      footer={
        <p className="flex justify-center gap-[6px] text-md text-ink-muted">
          Didn&apos;t get it?
          <button className="font-medium text-ink-link" onClick={() => setError(null)}>Resend code</button>
        </p>
      }>
      <div className="flex flex-col gap-lg">
        <div className="flex gap-[10px]" role="group" aria-label="Verification code">
          {digits.map((d, i) => (
            <input key={i} ref={(el) => { refs.current[i] = el; }} value={d} inputMode="numeric"
              aria-label={`Digit ${i + 1}`} maxLength={1}
              onChange={(e) => setDigit(i, e.target.value)}
              onKeyDown={(e) => { if (e.key === "Backspace" && !digits[i] && i > 0) refs.current[i - 1]?.focus(); }}
              className={`h-14 w-12 rounded-lg border bg-surface text-center text-[22px] font-semibold
                outline-none focus:border-2 focus:border-line-focus
                ${error ? "border-2 border-status-danger" : "border-line"}`} />
          ))}
        </div>
        {error && (
          <p role="alert" className="flex items-center gap-sm rounded-md px-md py-[10px] text-md font-medium"
            style={{ background: "#FBE3E3", color: "#B32B2B" }}>
            <Icon name="warn" size={16} strokeWidth={1.9} />{error}
          </p>
        )}
        <Button onClick={verify} loading={loading} className="w-full">Verify</Button>
        <p className="text-center text-sm text-ink-faint">Hint for this demo: the code is 492715.</p>
      </div>
    </AuthShell>
  );
}
