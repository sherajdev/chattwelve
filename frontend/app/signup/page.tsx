/**
 * Signup page
 * Centered layout with signup form and ChatTwelve branding
 */

import { SignupForm } from "@/components/auth/signup-form"
import Image from "next/image"

export default function SignupPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background p-4">
      <div className="mb-8 flex flex-col items-center gap-2">
        <Image
          src="/logo.png"
          alt="ChatTwelve Logo"
          width={64}
          height={64}
          className="rounded-xl"
        />
        <h1 className="text-2xl font-bold">ChatTwelve</h1>
        <p className="text-sm text-muted-foreground">AI-powered trading assistant</p>
      </div>
      <SignupForm />
    </div>
  )
}
