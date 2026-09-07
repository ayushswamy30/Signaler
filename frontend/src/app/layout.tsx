import type { Metadata } from "next";
import { AuthProvider } from "@/lib/auth";
import "./globals.css";

export const metadata: Metadata = {
  title: "Signaler",
  description: "A Signal-inspired messenger.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
          rel="stylesheet" />
        {/* Set the theme before paint so dark mode never flashes light. */}
        <script dangerouslySetInnerHTML={{ __html: `(function(){try{
          var s=localStorage.getItem('signaler-theme');
          var d=window.matchMedia('(prefers-color-scheme: dark)').matches;
          document.documentElement.setAttribute('data-theme', s || (d?'dark':'light'));
        }catch(e){}})();` }} />
      </head>
      <body className="font-sans antialiased">
        <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4
          focus:z-50 focus:rounded-md focus:bg-accent focus:px-4 focus:py-2 focus:text-white">
          Skip to content
        </a>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
