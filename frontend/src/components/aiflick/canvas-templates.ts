/**
 * frontend/src/components/aiflick/canvas-templates.ts
 *
 * Preset themes, aspect ratio dimensions, and typography layout algorithms
 * for the Fabric.js Social Post Graphic Studio.
 */

export interface CanvasDimensions {
  width: number;
  height: number;
  label: string;
  platform: string;
  badgeRatio: string;
}

export const ASPECT_RATIOS: Record<string, CanvasDimensions> = {
  "4:5": {
    width: 1080,
    height: 1350,
    label: "Instagram Portrait (4:5)",
    platform: "instagram",
    badgeRatio: "4:5",
  },
  "1:1": {
    width: 1080,
    height: 1080,
    label: "Square Post (1:1)",
    platform: "linkedin",
    badgeRatio: "1:1",
  },
  "16:9": {
    width: 1280,
    height: 720,
    label: "Landscape / YouTube (16:9)",
    platform: "youtube",
    badgeRatio: "16:9",
  },
  "9:16": {
    width: 1080,
    height: 1920,
    label: "Story / Reel (9:16)",
    platform: "tiktok",
    badgeRatio: "9:16",
  },
};

export interface PostTheme {
  id: string;
  name: string;
  description: string;
  bgGradient: [string, string];
  containerBg: string;
  containerBorder: string;
  titleColor: string;
  hookColor: string;
  bulletColor: string;
  bulletNumBg: string;
  bulletNumColor: string;
  accentColor: string;
  badgeBg: string;
  badgeTextColor: string;
}

export const PRESET_THEMES: PostTheme[] = [
  {
    id: "obsidian",
    name: "Obsidian Slate",
    description: "Deep dark tech aesthetic with electric cyan glow",
    bgGradient: ["#090D16", "#04060A"],
    containerBg: "rgba(15, 23, 42, 0.85)",
    containerBorder: "rgba(56, 189, 248, 0.25)",
    titleColor: "#FFFFFF",
    hookColor: "#38BDF8",
    bulletColor: "#E2E8F0",
    bulletNumBg: "#0284C7",
    bulletNumColor: "#FFFFFF",
    accentColor: "#38BDF8",
    badgeBg: "rgba(14, 165, 233, 0.2)",
    badgeTextColor: "#38BDF8",
  },
  {
    id: "cyber",
    name: "Cyber Neon",
    description: "Futuristic purple & vibrant pink duotone",
    bgGradient: ["#120826", "#06030F"],
    containerBg: "rgba(24, 12, 44, 0.85)",
    containerBorder: "rgba(236, 72, 153, 0.3)",
    titleColor: "#FFFFFF",
    hookColor: "#F472B6",
    bulletColor: "#F3E8FF",
    bulletNumBg: "#D946EF",
    bulletNumColor: "#FFFFFF",
    accentColor: "#EC4899",
    badgeBg: "rgba(236, 72, 153, 0.2)",
    badgeTextColor: "#F472B6",
  },
  {
    id: "aurora",
    name: "Aurora Mint",
    description: "Clean dark emerald with glowing mint highlights",
    bgGradient: ["#062419", "#020D09"],
    containerBg: "rgba(6, 44, 30, 0.85)",
    containerBorder: "rgba(52, 211, 153, 0.3)",
    titleColor: "#FFFFFF",
    hookColor: "#34D399",
    bulletColor: "#ECFDF5",
    bulletNumBg: "#059669",
    bulletNumColor: "#FFFFFF",
    accentColor: "#10B981",
    badgeBg: "rgba(16, 185, 129, 0.2)",
    badgeTextColor: "#34D399",
  },
  {
    id: "sunset",
    name: "Amber Sunset",
    description: "High-contrast dark copper with fiery orange accents",
    bgGradient: ["#210D12", "#0A0406"],
    containerBg: "rgba(38, 16, 22, 0.85)",
    containerBorder: "rgba(251, 146, 60, 0.3)",
    titleColor: "#FFFFFF",
    hookColor: "#FB923C",
    bulletColor: "#FFF7ED",
    bulletNumBg: "#EA580C",
    bulletNumColor: "#FFFFFF",
    accentColor: "#F97316",
    badgeBg: "rgba(249, 115, 22, 0.2)",
    badgeTextColor: "#FB923C",
  },
  {
    id: "minimal_white",
    name: "Minimal Light",
    description: "Ultra-crisp editorial white paper card",
    bgGradient: ["#F8FAFC", "#E2E8F0"],
    containerBg: "rgba(255, 255, 255, 0.95)",
    containerBorder: "rgba(203, 213, 225, 0.8)",
    titleColor: "#0F172A",
    hookColor: "#2563EB",
    bulletColor: "#334155",
    bulletNumBg: "#2563EB",
    bulletNumColor: "#FFFFFF",
    accentColor: "#2563EB",
    badgeBg: "rgba(37, 99, 235, 0.1)",
    badgeTextColor: "#2563EB",
  },
];

/**
 * Compute auto-scaled typography dimensions so title & bullets always fit.
 */
export function computeAutoLayout(
  canvasWidth: number,
  canvasHeight: number,
  titleText: string,
  bulletCount: number
) {
  // Padding & margins
  const horizontalMargin = Math.round(canvasWidth * 0.08);
  const topMargin = Math.round(canvasHeight * 0.08);
  const containerWidth = canvasWidth - horizontalMargin * 2;
  const containerHeight = Math.round(canvasHeight * 0.84);

  // Auto-scale title font size
  const titleLen = titleText.length;
  let titleFontSize = 46;
  if (titleLen > 60) {
    titleFontSize = 32;
  } else if (titleLen > 40) {
    titleFontSize = 36;
  } else if (titleLen > 25) {
    titleFontSize = 40;
  }

  // Auto-scale bullet points font size
  let bulletFontSize = 26;
  let bulletSpacing = 28;
  if (bulletCount >= 5) {
    bulletFontSize = 22;
    bulletSpacing = 20;
  } else if (bulletCount === 4) {
    bulletFontSize = 24;
    bulletSpacing = 24;
  } else if (bulletCount <= 2) {
    bulletFontSize = 30;
    bulletSpacing = 36;
  }

  return {
    horizontalMargin,
    topMargin,
    containerWidth,
    containerHeight,
    titleFontSize,
    bulletFontSize,
    bulletSpacing,
  };
}

/**
 * Generate a procedural geometric/mesh SVG data URL for instant zero-latency backgrounds.
 */
export function generatePresetBackgroundDataUrl(
  width: number,
  height: number,
  theme: PostTheme
): string {
  const [c1, c2] = theme.bgGradient;
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
      <defs>
        <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="${c1}" />
          <stop offset="100%" stop-color="${c2}" />
        </linearGradient>
        <radialGradient id="glow1" cx="20%" cy="15%" r="45%">
          <stop offset="0%" stop-color="${theme.accentColor}" stop-opacity="0.25" />
          <stop offset="100%" stop-color="${theme.accentColor}" stop-opacity="0" />
        </radialGradient>
        <radialGradient id="glow2" cx="80%" cy="85%" r="50%">
          <stop offset="0%" stop-color="${theme.hookColor}" stop-opacity="0.2" />
          <stop offset="100%" stop-color="${theme.hookColor}" stop-opacity="0" />
        </radialGradient>
        <pattern id="grid" width="60" height="60" patternUnits="userSpaceOnUse">
          <path d="M 60 0 L 0 0 0 60" fill="none" stroke="rgba(255,255,255,0.03)" stroke-width="1" />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#bgGrad)" />
      <rect width="100%" height="100%" fill="url(#glow1)" />
      <rect width="100%" height="100%" fill="url(#glow2)" />
      <rect width="100%" height="100%" fill="url(#grid)" />
    </svg>
  `.trim();

  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}
