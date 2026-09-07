"use client";

/** Phone verification — designed, not built.
 *
 *  Registration completes without it: there is no SMS provider behind this
 *  application, and a code that any client could guess would be worse than no
 *  step at all. The screen is kept because it is part of the intended flow, and
 *  it says plainly that it is inert rather than pretending to verify anything.
 */

import Link from "next/link";
import { useRef, useState } from "react";
import { AuthShell } from "../AuthShell";
import { Button, Chip } from "@/components/Primitives";
import { Icon } from "@/components/Icon";

export default function VerifyPage() {
  const [digits, setDigits] = useState<string[]>(Array(6).fill(""));
  const refs = useRef<Array<HTMLInputElement | null>>([]);

  function setDigit(index: number, value: string) {
    const character = value.replace(/\D/g, "").slice(-1);
    setDigits((current) => {
      const next = [...current];
      next[index] = character;
      return next;
    });
    if (character && index < 5) refs.current[index + 1]?.focus();
  }

  return (
    <AuthShell
      width={420}
      title="Verify your number"
      subtitle="A six-digit code would arrive by SMS."
      footer={
        <p className="flex justify-center gap-[6px] text-md text-ink-muted">
          <Link href="/" className="font-medium text-ink-link">Continue to Signaler</Link>
        </p>
      }
    >
      <div className="flex flex-col gap-lg">
        <p className="flex items-start gap-sm rounded-md bg-hover px-md py-[11px] text-md text-ink-muted">
          <Icon name="info" size={16} strokeWidth={1.8} className="mt-[2px] shrink-0" />
          <span>
            <Chip>Placeholder</Chip> Phone verification is out of scope for this build. Accounts are
            created and signed in without it, so nothing here is checked.
          </span>
        </p>

        <div className="flex gap-[10px]" role="group" aria-label="Verification code">
          {digits.map((digit, index) => (
            <input
              key={index}
              ref={(element) => { refs.current[index] = element; }}
              value={digit}
              inputMode="numeric"
              aria-label={`Digit ${index + 1}`}
              maxLength={1}
              onChange={(event) => setDigit(index, event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Backspace" && !digits[index] && index > 0) {
                  refs.current[index - 1]?.focus();
                }
              }}
              className="h-14 w-12 rounded-lg border border-line bg-surface text-center
                text-[22px] font-semibold outline-none focus:border-2 focus:border-line-focus"
            />
          ))}
        </div>

        <Button disabled className="w-full">Verify</Button>
      </div>
    </AuthShell>
  );
}
