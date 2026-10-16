import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "FinPilot",
  description: "Auditable neuro-symbolic financial decision intelligence"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
