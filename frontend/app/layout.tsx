
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DengueShield AI | Early Warning Intelligence",
  description:
    "Ward-level dengue early warning and risk forecasting platform for public health teams in Bangladesh.",
  applicationName: "DengueShield AI",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
