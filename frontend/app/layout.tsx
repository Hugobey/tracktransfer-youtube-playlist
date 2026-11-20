import type { Metadata } from "next";
import { IBM_Plex_Mono, Outfit, Syne } from "next/font/google";
import "./globals.css";

const outfit = Outfit({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-outfit" });
const syne = Syne({ subsets: ["latin"], weight: ["700"], variable: "--font-syne" });
const plex = IBM_Plex_Mono({ subsets: ["latin"], weight: ["500"], variable: "--font-plex" });

export const metadata: Metadata = {
  title: "TrackTransfer",
  description: "Move a Spotify playlist CSV to YouTube Music.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${outfit.variable} ${syne.variable} ${plex.variable} antialiased`}>{children}</body>
    </html>
  );
}
