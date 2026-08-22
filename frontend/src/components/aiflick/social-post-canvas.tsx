/**
 * frontend/src/components/aiflick/social-post-canvas.tsx
 *
 * Production-grade Interactive Social Post Studio built with Fabric.js.
 * Combines AI backgrounds / custom uploads / presets with crisp, auto-wrapping
 * typography, glassmorphism contrast scrims, and 1-click 1080x1350 PNG export.
 */

import React, { useEffect, useRef, useState, useCallback } from "react";
import { fabric } from "fabric";
import {
  Download,
  Copy,
  RotateCcw,
  Sparkles,
  Upload,
  Palette,
  Layers,
  Check,
  Smartphone,
  Square,
  MonitorPlay,
  Flame,
} from "lucide-react";
import { toast } from "sonner";
import {
  ASPECT_RATIOS,
  PRESET_THEMES,
  PostTheme,
  computeAutoLayout,
  generatePresetBackgroundDataUrl,
} from "./canvas-templates";

export interface SocialPostCanvasProps {
  backgroundImageUrl?: string | null;
  title: string;
  hook?: string;
  summary?: string[] | string;
  platform?: string;
  authorHandle?: string;
  onRegenerateBg?: () => void;
  isGeneratingBg?: boolean;
}

export const SocialPostCanvas: React.FC<SocialPostCanvasProps> = ({
  backgroundImageUrl,
  title,
  hook = "",
  summary = [],
  platform = "instagram",
  authorHandle = "@trendforge_creator",
  onRegenerateBg,
  isGeneratingBg = false,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const fabricCanvasRef = useRef<fabric.Canvas | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Studio States
  const [aspectRatioKey, setAspectRatioKey] = useState<string>("4:5");
  const [selectedTheme, setSelectedTheme] = useState<PostTheme>(PRESET_THEMES[0]);
  const [customBgDataUrl, setCustomBgDataUrl] = useState<string | null>(null);
  const [bgSource, setBgSource] = useState<"ai" | "custom" | "preset">("ai");
  const [copied, setCopied] = useState(false);
  const [isReady, setIsReady] = useState(false);

  // Normalize summary points
  const bulletPoints: string[] = React.useMemo(() => {
    if (Array.isArray(summary)) {
      return summary.filter(Boolean);
    }
    if (typeof summary === "string") {
      return summary
        .split("\n")
        .map((s) => s.trim().replace(/^[-•*📌🚀]\s*/, ""))
        .filter(Boolean);
    }
    return [];
  }, [summary]);

  const currentDimensions = ASPECT_RATIOS[aspectRatioKey] || ASPECT_RATIOS["4:5"];

  // ───────────────────────────────────────────────────────────────────────────
  // Canvas Composition Renderer
  // ───────────────────────────────────────────────────────────────────────────
  const renderCanvasComposition = useCallback(() => {
    const canvas = fabricCanvasRef.current;
    if (!canvas) return;

    const { width, height } = currentDimensions;
    canvas.setWidth(width);
    canvas.setHeight(height);
    canvas.clear();

    const layout = computeAutoLayout(width, height, title, bulletPoints.length);

    // 1. Determine Background Source
    let activeBgUrl: string;
    if (bgSource === "custom" && customBgDataUrl) {
      activeBgUrl = customBgDataUrl;
    } else if (bgSource === "ai" && backgroundImageUrl) {
      activeBgUrl = backgroundImageUrl;
    } else {
      activeBgUrl = generatePresetBackgroundDataUrl(width, height, selectedTheme);
    }

    // Helper to build elements on top of background
    const buildForegroundLayers = () => {
      // 2. Glassmorphism Contrast Container (Guarantees 100% legibility)
      const container = new fabric.Rect({
        left: layout.horizontalMargin,
        top: layout.topMargin,
        width: layout.containerWidth,
        height: layout.containerHeight,
        rx: 28,
        ry: 28,
        fill: selectedTheme.containerBg,
        stroke: selectedTheme.containerBorder,
        strokeWidth: 1.5,
        selectable: true,
        hoverCursor: "move",
        shadow: new fabric.Shadow({
          color: "rgba(0,0,0,0.45)",
          blur: 35,
          offsetX: 0,
          offsetY: 16,
        }),
      });
      canvas.add(container);

      // Inner padding
      const innerLeft = layout.horizontalMargin + 48;
      const innerWidth = layout.containerWidth - 96;
      let currentY = layout.topMargin + 48;

      // 3. Platform / Category Pill Badge
      const badgeText = new fabric.Text(
        `# ${platform.toUpperCase()} BLUEPRINT`,
        {
          fontSize: 15,
          fontFamily: "Inter, -apple-system, sans-serif",
          fontWeight: "bold",
          fill: selectedTheme.badgeTextColor,
          left: innerLeft + 16,
          top: currentY + 8,
          selectable: false,
        }
      );

      const badgeBg = new fabric.Rect({
        left: innerLeft,
        top: currentY,
        width: (badgeText.width || 120) + 32,
        height: 34,
        rx: 17,
        ry: 17,
        fill: selectedTheme.badgeBg,
        stroke: selectedTheme.containerBorder,
        strokeWidth: 1,
        selectable: false,
      });

      const badgeGroup = new fabric.Group([badgeBg, badgeText], {
        left: innerLeft,
        top: currentY,
        selectable: true,
      });
      canvas.add(badgeGroup);
      currentY += 56;

      // 4. Post Title (Auto-wrapped, crisp vector font)
      const titleObj = new fabric.Textbox(title, {
        left: innerLeft,
        top: currentY,
        width: innerWidth,
        fontSize: layout.titleFontSize,
        fontWeight: "bold",
        fontFamily: "Inter, -apple-system, sans-serif",
        fill: selectedTheme.titleColor,
        lineHeight: 1.25,
        editable: true,
        selectable: true,
        hoverCursor: "text",
        shadow: new fabric.Shadow({
          color: "rgba(0,0,0,0.6)",
          blur: 10,
          offsetX: 0,
          offsetY: 2,
        }),
      });
      canvas.add(titleObj);
      currentY += (titleObj.height || 60) + 16;

      // 5. Hook / Subtitle (if available)
      if (hook) {
        const hookObj = new fabric.Textbox(`⚡ ${hook}`, {
          left: innerLeft,
          top: currentY,
          width: innerWidth,
          fontSize: 20,
          fontWeight: "500",
          fontFamily: "Inter, -apple-system, sans-serif",
          fill: selectedTheme.hookColor,
          lineHeight: 1.35,
          editable: true,
          selectable: true,
        });
        canvas.add(hookObj);
        currentY += (hookObj.height || 30) + 24;
      }

      // Separator line
      const divider = new fabric.Line(
        [innerLeft, currentY, innerLeft + innerWidth, currentY],
        {
          stroke: selectedTheme.containerBorder,
          strokeWidth: 1,
          selectable: false,
        }
      );
      canvas.add(divider);
      currentY += 28;

      // 6. Summary / Roadmap Milestones Bullet Points
      const itemsToRender =
        bulletPoints.length > 0
          ? bulletPoints.slice(0, 5)
          : [
              "Phase 1: Foundations & Architecture",
              "Phase 2: Core Implementation & Workflows",
              "Phase 3: Production Deployment & Scale",
            ];

      itemsToRender.forEach((bulletText, idx) => {
        const numLabel = `${idx + 1}`;
        const numCircle = new fabric.Circle({
          radius: 14,
          fill: selectedTheme.bulletNumBg,
          left: innerLeft,
          top: currentY + 2,
          selectable: false,
        });

        const numText = new fabric.Text(numLabel, {
          fontSize: 14,
          fontFamily: "Inter, sans-serif",
          fontWeight: "bold",
          fill: selectedTheme.bulletNumColor,
          left: innerLeft + (idx >= 9 ? 6 : 9),
          top: currentY + 6,
          selectable: false,
        });

        const bulletContent = new fabric.Textbox(bulletText, {
          left: innerLeft + 42,
          top: currentY,
          width: innerWidth - 46,
          fontSize: layout.bulletFontSize,
          fontFamily: "Inter, -apple-system, sans-serif",
          fontWeight: "400",
          fill: selectedTheme.bulletColor,
          lineHeight: 1.3,
          editable: true,
          selectable: true,
        });

        const rowGroup = new fabric.Group([numCircle, numText, bulletContent], {
          left: innerLeft,
          top: currentY,
          selectable: true,
        });

        canvas.add(rowGroup);
        currentY += Math.max(bulletContent.height || 36, 36) + layout.bulletSpacing;
      });

      // 7. Footer / Creator Branding Signature
      const footerY = layout.topMargin + layout.containerHeight - 48;
      const footerTag = new fabric.Text(`✨ Created with TrendForge  •  ${authorHandle}`, {
        fontSize: 14,
        fontFamily: "Inter, sans-serif",
        fontWeight: "500",
        fill: selectedTheme.badgeTextColor,
        left: innerLeft,
        top: footerY,
        selectable: true,
      });
      canvas.add(footerTag);

      canvas.renderAll();
      setIsReady(true);
    };

    // Load background image onto canvas
    fabric.Image.fromURL(
      activeBgUrl,
      (img) => {
        if (img && img.width && img.height) {
          // Scale to cover aspect fill
          const scale = Math.max(width / img.width, height / img.height);
          img.set({
            scaleX: scale,
            scaleY: scale,
            originX: "center",
            originY: "center",
            left: width / 2,
            top: height / 2,
            selectable: false,
            evented: false,
          });
          canvas.setBackgroundImage(img, () => {
            buildForegroundLayers();
          });
        } else {
          // Fallback solid background
          canvas.backgroundColor = selectedTheme.bgGradient[0];
          buildForegroundLayers();
        }
      },
      { crossOrigin: "anonymous" }
    );
  }, [
    currentDimensions,
    title,
    hook,
    bulletPoints,
    platform,
    authorHandle,
    bgSource,
    customBgDataUrl,
    backgroundImageUrl,
    selectedTheme,
  ]);

  // Initialise Fabric Canvas
  useEffect(() => {
    if (!canvasRef.current) return;

    const fabricInstance = new fabric.Canvas(canvasRef.current, {
      preserveObjectStacking: true,
      selection: true,
    });
    fabricCanvasRef.current = fabricInstance;

    renderCanvasComposition();

    return () => {
      fabricInstance.dispose();
      fabricCanvasRef.current = null;
    };
  }, [renderCanvasComposition]);

  // Handle Custom User Image Upload from PC
  const handleCustomUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith("image/")) {
      toast.error("Please upload a valid image file (PNG/JPEG)");
      return;
    }

    const reader = new FileReader();
    reader.onload = (event) => {
      const dataUrl = event.target?.result as string;
      if (dataUrl) {
        setCustomBgDataUrl(dataUrl);
        setBgSource("custom");
        toast.success("Custom background loaded into studio!");
      }
    };
    reader.readAsDataURL(file);
  };

  // 1-Click High-Res PNG Download
  const handleDownload = () => {
    const canvas = fabricCanvasRef.current;
    if (!canvas) return;

    try {
      const dataUrl = canvas.toDataURL({
        format: "png",
        multiplier: 1,
        quality: 1,
      });

      const a = document.createElement("a");
      a.href = dataUrl;
      a.download = `trendforge-${platform}-${aspectRatioKey.replace(":", "-")}.png`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);

      toast.success("High-resolution post downloaded successfully!");
    } catch (err) {
      console.error("Export error:", err);
      toast.error("Could not export image. Canvas may be tainted.");
    }
  };

  // Copy Image to Clipboard
  const handleCopyToClipboard = async () => {
    const canvas = fabricCanvasRef.current;
    if (!canvas) return;

    try {
      canvas.renderAll();
      const canvasElem = canvas.getElement();
      canvasElem.toBlob(async (blob) => {
        if (!blob) throw new Error("Could not create image blob");
        await navigator.clipboard.write([
          new ClipboardItem({ "image/png": blob }),
        ]);
        setCopied(true);
        toast.success("Graphic copied to clipboard!");
        setTimeout(() => setCopied(false), 2000);
      });
    } catch (err) {
      console.error("Clipboard copy error:", err);
      toast.error("Clipboard copy not supported in this browser");
    }
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Studio Controls Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border/60 bg-surface/80 p-3 backdrop-blur-md">
        {/* Aspect Ratio Switcher */}
        <div className="flex items-center gap-1">
          <span className="text-xs font-semibold text-muted-foreground mr-1">Ratio:</span>
          {Object.entries(ASPECT_RATIOS).map(([key, dim]) => (
            <button
              key={key}
              type="button"
              onClick={() => setAspectRatioKey(key)}
              className={`flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-all ${
                aspectRatioKey === key
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "bg-secondary/60 text-muted-foreground hover:text-foreground"
              }`}
            >
              {key === "4:5" && <Smartphone className="size-3" />}
              {key === "1:1" && <Square className="size-3" />}
              {key === "16:9" && <MonitorPlay className="size-3" />}
              {key === "9:16" && <Flame className="size-3" />}
              {dim.badgeRatio}
            </button>
          ))}
        </div>

        {/* Theme Picker */}
        <div className="flex items-center gap-1.5">
          <Palette className="size-3.5 text-muted-foreground" />
          <div className="flex items-center gap-1">
            {PRESET_THEMES.map((theme) => (
              <button
                key={theme.id}
                type="button"
                onClick={() => setSelectedTheme(theme)}
                title={theme.name}
                className={`relative size-6 rounded-full border transition-all ${
                  selectedTheme.id === theme.id
                    ? "ring-2 ring-primary ring-offset-2 ring-offset-background scale-110 border-white"
                    : "border-border/60 opacity-80 hover:opacity-100"
                }`}
                style={{
                  background: `linear-gradient(135deg, ${theme.bgGradient[0]}, ${theme.accentColor})`,
                }}
              />
            ))}
          </div>
        </div>

        {/* Background Source Selector */}
        <div className="flex items-center gap-1">
          {backgroundImageUrl && (
            <button
              type="button"
              onClick={() => setBgSource("ai")}
              className={`flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-all ${
                bgSource === "ai"
                  ? "bg-primary text-primary-foreground"
                  : "bg-secondary/60 text-muted-foreground hover:text-foreground"
              }`}
            >
              <Sparkles className="size-3" />
              AI Art
            </button>
          )}

          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className={`flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-all ${
              bgSource === "custom"
                ? "bg-primary text-primary-foreground"
                : "bg-secondary/60 text-muted-foreground hover:text-foreground"
            }`}
          >
            <Upload className="size-3" />
            Upload Custom
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={handleCustomUpload}
          />

          <button
            type="button"
            onClick={() => setBgSource("preset")}
            className={`flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-all ${
              bgSource === "preset"
                ? "bg-primary text-primary-foreground"
                : "bg-secondary/60 text-muted-foreground hover:text-foreground"
            }`}
          >
            <Layers className="size-3" />
            Preset Mesh
          </button>
        </div>
      </div>

      {/* Canvas Viewport (Scales smoothly to fit modal) */}
      <div className="relative flex min-h-[460px] items-center justify-center overflow-hidden rounded-2xl border border-border/70 bg-black/40 p-4 shadow-inner">
        <div
          className="relative overflow-hidden rounded-xl shadow-2xl transition-transform"
          style={{
            width: "100%",
            maxWidth: aspectRatioKey === "16:9" ? "620px" : aspectRatioKey === "9:16" ? "320px" : "400px",
            aspectRatio: `${currentDimensions.width} / ${currentDimensions.height}`,
          }}
        >
          <canvas
            ref={canvasRef}
            className="h-full w-full object-contain"
            style={{ width: "100%", height: "100%" }}
          />
        </div>

        {/* Tip Badge */}
        <div className="pointer-events-none absolute bottom-3 left-4 rounded-md bg-black/60 px-2.5 py-1 text-[11px] font-medium text-slate-300 backdrop-blur-md">
          💡 Double-click any title or bullet point to edit text directly
        </div>
      </div>

      {/* Action Footer */}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
        <div className="flex items-center gap-2">
          {onRegenerateBg && (
            <button
              type="button"
              onClick={onRegenerateBg}
              disabled={isGeneratingBg}
              className="flex items-center gap-1.5 rounded-lg border border-border/80 bg-secondary/80 px-3 py-2 text-xs font-medium text-foreground transition-colors hover:bg-secondary disabled:opacity-50"
            >
              <Sparkles className="size-3.5 text-primary" />
              {isGeneratingBg ? "Regenerating AI Art..." : "Regenerate AI Background"}
            </button>
          )}

          <button
            type="button"
            onClick={renderCanvasComposition}
            title="Reset to default text and positioning"
            className="flex items-center gap-1.5 rounded-lg border border-border/60 bg-transparent px-3 py-2 text-xs font-medium text-muted-foreground hover:text-foreground"
          >
            <RotateCcw className="size-3.5" />
            Reset Layout
          </button>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleCopyToClipboard}
            className="flex items-center gap-1.5 rounded-lg border border-border/80 bg-secondary/80 px-3.5 py-2 text-xs font-medium text-foreground transition-all hover:bg-secondary active:scale-95"
          >
            {copied ? <Check className="size-3.5 text-emerald-400" /> : <Copy className="size-3.5" />}
            {copied ? "Copied!" : "Copy Image"}
          </button>

          <button
            type="button"
            onClick={handleDownload}
            className="flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground shadow-md transition-all hover:brightness-110 active:scale-95"
          >
            <Download className="size-3.5" />
            Download Ready-to-Post PNG
          </button>
        </div>
      </div>
    </div>
  );
};
