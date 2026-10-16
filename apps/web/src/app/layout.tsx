import type { Metadata, Viewport } from "next";
import { themeBootScript } from "@/lib/theme-boot";
import "./styles.css";

export const metadata: Metadata = {
  title: "FinPilot",
  description: "Auditable neuro-symbolic financial decision intelligence"
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#eef1f8" },
    { media: "(prefers-color-scheme: dark)", color: "#07080d" }
  ]
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBootScript }} />
      </head>
      <body>
        <div className="wallpaper" aria-hidden="true"><i /><i /><i /><i /></div>
        {children}
      </body>
    </html>
  );
}
