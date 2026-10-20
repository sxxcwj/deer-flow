import { type Metadata } from "next";
import { Fraunces, Noto_Serif_SC } from "next/font/google";

import { PromoPage } from "@/components/changban/promo-page";

const serif = Noto_Serif_SC({
  weight: ["500", "600", "700"],
  subsets: ["latin"],
  display: "swap",
  variable: "--font-cb-serif",
  preload: false,
});

const display = Fraunces({
  weight: ["500", "600"],
  subsets: ["latin"],
  style: ["normal", "italic"],
  display: "swap",
  variable: "--font-cb-display",
});

export const metadata: Metadata = {
  title: "长伴咨询",
  description:
    "每个高成长企业背后，都有长伴相随。组织、激励与人才的长期陪伴。",
};

export default function LandingPage() {
  return (
    <div className={`${serif.variable} ${display.variable}`}>
      <PromoPage />
    </div>
  );
}
