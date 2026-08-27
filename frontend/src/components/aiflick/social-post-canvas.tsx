/**
 * frontend/src/components/aiflick/social-post-canvas.tsx
 *
 * Production-grade Viral Social Post Studio built with Fabric.js.
 * 
 * Key fixes from v1:
 *   - ALL text elements (badge, title, hook, bullets, numbers, footer) are
 *     independent fabric.Textbox objects -- NO grouping, 100% double-click editable.
 *   - Keyboard Delete/Backspace listener with isEditing guard.
 *   - Delete Selected button in UI.
 *   - Zoom controls (Fit, 50%, 75%, 100%, 125%).
 *   - Add Text button for custom textbox insertion.
 *   - Font Size +/- controls for selected objects.
 *   - Font color picker for selected text.
 *   - Auto-switch bgSource to "ai" when new backgroundImageUrl arrives.
 *   - Cache-busting appended to AI background images.
 *   - Expanded canvas viewport for comfortable design work.
 */

import React, {
  useEffect,
  useRef,
  useState,
  useCallback,
} from "react";
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
  Trash2,
  Plus,
  ZoomIn,
  ZoomOut,
  Maximize2,
  ALargeSmall,
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

const FONT_SIZES = [12, 14, 16, 18, 20, 22, 24, 28, 32, 36, 40, 46, 52, 60, 72];
const ZOOM_LEVELS = [0.35, 0.5, 0.65, 0.75, 1.0, 1.25];

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
  const containerRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Studio states
  const [aspectRatioKey, setAspectRatioKey] = useState<string>("4:5");
  const [selectedTheme, setSelectedTheme] = useState<PostTheme>(PRESET_THEMES[0]);
  const [customBgDataUrl, setCustomBgDataUrl] = useState<string | null>(null);
  const [bgSource, setBgSource] = useState<"ai" | "custom" | "preset">("ai");
  const [copied, setCopied] = useState(false);
  const [isReady, setIsReady] = useState(false);
  const [zoom, setZoom] = useState(0.5);
  const [hasSelection, setHasSelection] = useState(false);
  const [selectedFontSize, setSelectedFontSize] = useState<number | null>(null);
  const [selectedColor, setSelectedColor] = useState<string>("#FFFFFF");

  // When backgroundImageUrl changes, auto-switch to AI background mode
  useEffect(() => {
    if (backgroundImageUrl) {
      setBgSource("ai");
    }
  }, [backgroundImageUrl]);

  // Normalize summary points
  const bulletPoints: string[] = React.useMemo(() => {
    if (Array.isArray(summary)) return summary.filter(Boolean);
    if (typeof summary === "string") {
      return summary
        .split("\n")
        .map((s) => s.trim().replace(/^[-•*📌🚀⚡💡🔴]\s*/, ""))
        .filter(Boolean);
    }
    return [];
  }, [summary]);

  const currentDimensions = ASPECT_RATIOS[aspectRatioKey] || ASPECT_RATIOS["4:5"];

  // ─────────────────────────────────────────────────────────────────────────────
  // Canvas Composition Renderer
  // ─────────────────────────────────────────────────────────────────────────────
  const renderCanvasComposition = useCallback(() => {
    const canvas = fabricCanvasRef.current;
    if (!canvas) return;

    const { width, height } = currentDimensions;
    canvas.setWidth(width);
    canvas.setHeight(height);
    canvas.clear();

    const layout = computeAutoLayout(width, height, title, bulletPoints.length);

    // Determine background source
    let activeBgUrl: string;
    if (bgSource === "custom" && customBgDataUrl) {
      activeBgUrl = customBgDataUrl;
    } else if (bgSource === "ai" && backgroundImageUrl) {
      // Append cache-busting to force fresh load when regenerated
      const sep = backgroundImageUrl.includes("?") ? "&" : "?";
      activeBgUrl = `${backgroundImageUrl}${sep}_canvas_ts=${Date.now()}`;
    } else {
      activeBgUrl = generatePresetBackgroundDataUrl(width, height, selectedTheme);
    }

    const buildForegroundLayers = () => {
      // ── Glassmorphism container ──────────────────────────────────────────────
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

      const innerLeft = layout.horizontalMargin + 48;
      const innerWidth = layout.containerWidth - 96;
      let currentY = layout.topMargin + 48;

      // ── Platform badge — INDEPENDENT objects (no Group), fully editable ──────
      const badgeBg = new fabric.Rect({
        left: innerLeft,
        top: currentY,
        width: 220,
        height: 34,
        rx: 17,
        ry: 17,
        fill: selectedTheme.badgeBg,
        stroke: selectedTheme.containerBorder,
        strokeWidth: 1,
        selectable: true,
        hoverCursor: "move",
      });
      canvas.add(badgeBg);

      const badgeText = new fabric.Textbox(`# ${platform.toUpperCase()} BLUEPRINT`, {
        left: innerLeft + 12,
        top: currentY + 7,
        width: 196,
        fontSize: 14,
        fontFamily: "Inter, -apple-system, sans-serif",
        fontWeight: "bold",
        fill: selectedTheme.badgeTextColor,
        editable: true,
        selectable: true,
        hoverCursor: "text",
        lockScalingX: false,
        lockScalingY: false,
      });
      canvas.add(badgeText);
      currentY += 56;

      // ── Post title ──────────────────────────────────────────────────────────
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

      // ── Hook / subtitle ──────────────────────────────────────────────────────
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
          hoverCursor: "text",
        });
        canvas.add(hookObj);
        currentY += (hookObj.height || 30) + 24;
      }

      // ── Separator ────────────────────────────────────────────────────────────
      const divider = new fabric.Line(
        [innerLeft, currentY, innerLeft + innerWidth, currentY],
        {
          stroke: selectedTheme.containerBorder,
          strokeWidth: 1,
          selectable: false,
          evented: false,
        }
      );
      canvas.add(divider);
      currentY += 28;

      // ── Bullet points — ALL INDEPENDENT objects, fully editable ─────────────
      const itemsToRender =
        bulletPoints.length > 0
          ? bulletPoints.slice(0, 5)
          : [
              "Phase 1: Foundations & Architecture",
              "Phase 2: Core Implementation & Workflows",
              "Phase 3: Production Deployment & Scale",
            ];

      itemsToRender.forEach((bulletText, idx) => {
        // Number circle (background rect for reliability)
        const numCircle = new fabric.Circle({
          radius: 14,
          fill: selectedTheme.bulletNumBg,
          left: innerLeft,
          top: currentY + 2,
          selectable: true,
          hoverCursor: "move",
        });
        canvas.add(numCircle);

        // Number text — fully selectable, editable
        const numText = new fabric.Textbox(`${idx + 1}`, {
          fontSize: 14,
          fontFamily: "Inter, sans-serif",
          fontWeight: "bold",
          fill: selectedTheme.bulletNumColor,
          left: innerLeft + (idx >= 9 ? 6 : 9),
          top: currentY + 6,
          width: 18,
          editable: true,
          selectable: true,
          hoverCursor: "text",
          textAlign: "center",
        });
        canvas.add(numText);

        // Bullet content text — fully editable Textbox
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
          hoverCursor: "text",
        });
        canvas.add(bulletContent);

        currentY += Math.max(bulletContent.height || 36, 36) + layout.bulletSpacing;
      });

      // ── Footer / creator branding — fully selectable & editable ─────────────
      const footerY = layout.topMargin + layout.containerHeight - 48;
      const footerTag = new fabric.Textbox(
        `✨ Created with TrendForge  •  ${authorHandle}`,
        {
          fontSize: 14,
          fontFamily: "Inter, sans-serif",
          fontWeight: "500",
          fill: selectedTheme.badgeTextColor,
          left: innerLeft,
          top: footerY,
          width: innerWidth,
          editable: true,
          selectable: true,
          hoverCursor: "text",
        }
      );
      canvas.add(footerTag);

      canvas.renderAll();
      setIsReady(true);
    };

    // Load background image
    fabric.Image.fromURL(
      activeBgUrl,
      (img) => {
        if (img && img.width && img.height) {
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

  // ─────────────────────────────────────────────────────────────────────────────
  // Initialise Fabric Canvas + event listeners
  // ─────────────────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!canvasRef.current) return;

    const fc = new fabric.Canvas(canvasRef.current, {
      preserveObjectStacking: true,
      selection: true,
    });
    fabricCanvasRef.current = fc;

    // Track selection for toolbar state
    const onSelChange = () => {
      const obj = fc.getActiveObject() as any;
      setHasSelection(Boolean(obj));
      if (obj && obj.fontSize !== undefined) {
        setSelectedFontSize(obj.fontSize);
        setSelectedColor(obj.fill as string || "#FFFFFF");
      } else {
        setSelectedFontSize(null);
      }
    };
    fc.on("selection:created", onSelChange);
    fc.on("selection:updated", onSelChange);
    fc.on("selection:cleared", () => {
      setHasSelection(false);
      setSelectedFontSize(null);
    });

    // ── Keyboard listener — Delete / Backspace removes selected object ────────
    const handleKeyDown = (e: KeyboardEvent) => {
      // Do not delete if user is typing inside a text box
      const active = fc.getActiveObject() as any;
      if (!active) return;
      if (active.isEditing) return;
      if (e.key === "Delete" || e.key === "Backspace") {
        const activeObjs = fc.getActiveObjects();
        fc.discardActiveObject();
        activeObjs.forEach((obj) => fc.remove(obj));
        fc.renderAll();
        setHasSelection(false);
        e.preventDefault();
      }
    };
    window.addEventListener("keydown", handleKeyDown);

    renderCanvasComposition();

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      fc.dispose();
      fabricCanvasRef.current = null;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Re-render when composition props change
  useEffect(() => {
    renderCanvasComposition();
  }, [renderCanvasComposition]);

  // ─────────────────────────────────────────────────────────────────────────────
  // Zoom helpers
  // ─────────────────────────────────────────────────────────────────────────────
  const applyZoom = useCallback((newZoom: number) => {
    setZoom(newZoom);
  }, []);

  const zoomIn = () => {
    const next = ZOOM_LEVELS.find((z) => z > zoom) ?? ZOOM_LEVELS[ZOOM_LEVELS.length - 1];
    applyZoom(next);
  };
  const zoomOut = () => {
    const prev = [...ZOOM_LEVELS].reverse().find((z) => z < zoom) ?? ZOOM_LEVELS[0];
    applyZoom(prev);
  };
  const zoomFit = () => applyZoom(0.5);

  // ─────────────────────────────────────────────────────────────────────────────
  // Creator toolbar actions
  // ─────────────────────────────────────────────────────────────────────────────
  const handleDeleteSelected = () => {
    const canvas = fabricCanvasRef.current;
    if (!canvas) return;
    const activeObjs = canvas.getActiveObjects();
    if (!activeObjs.length) return;
    canvas.discardActiveObject();
    activeObjs.forEach((obj) => canvas.remove(obj));
    canvas.renderAll();
    setHasSelection(false);
  };

  const handleAddText = () => {
    const canvas = fabricCanvasRef.current;
    if (!canvas) return;
    const { width, height } = currentDimensions;
    const newText = new fabric.Textbox("Double-click to edit", {
      left: Math.round(width * 0.2),
      top: Math.round(height * 0.45),
      width: Math.round(width * 0.6),
      fontSize: 32,
      fontFamily: "Inter, -apple-system, sans-serif",
      fontWeight: "bold",
      fill: selectedTheme.titleColor,
      editable: true,
      selectable: true,
      hoverCursor: "text",
    });
    canvas.add(newText);
    canvas.setActiveObject(newText);
    canvas.renderAll();
    toast.success("New text added — double-click to edit it");
  };

  const handleFontSizeChange = (delta: number) => {
    const canvas = fabricCanvasRef.current;
    if (!canvas) return;
    const obj = canvas.getActiveObject() as any;
    if (!obj || obj.fontSize === undefined) return;
    const newSize = Math.max(8, Math.min(200, (obj.fontSize || 24) + delta));
    obj.set("fontSize", newSize);
    canvas.renderAll();
    setSelectedFontSize(newSize);
  };

  const handleColorChange = (color: string) => {
    const canvas = fabricCanvasRef.current;
    if (!canvas) return;
    const obj = canvas.getActiveObject() as any;
    if (!obj) return;
    obj.set("fill", color);
    canvas.renderAll();
    setSelectedColor(color);
  };

  const handleBringForward = () => {
    const canvas = fabricCanvasRef.current;
    if (!canvas) return;
    const obj = canvas.getActiveObject();
    if (!obj) return;
    canvas.bringForward(obj);
    canvas.renderAll();
  };

  // ─────────────────────────────────────────────────────────────────────────────
  // Custom upload
  // ─────────────────────────────────────────────────────────────────────────────
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

  // ─────────────────────────────────────────────────────────────────────────────
  // Export / Clipboard
  // ─────────────────────────────────────────────────────────────────────────────
  const handleDownload = () => {
    const canvas = fabricCanvasRef.current;
    if (!canvas) return;
    try {
      const dataUrl = canvas.toDataURL({ format: "png", multiplier: 1, quality: 1 });
      const a = document.createElement("a");
      a.href = dataUrl;
      a.download = `trendforge-${platform}-${aspectRatioKey.replace(":", "-")}.png`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      toast.success("High-resolution post downloaded!");
    } catch (err) {
      console.error("Export error:", err);
      toast.error("Could not export image. Canvas may be tainted.");
    }
  };

  const handleCopyToClipboard = async () => {
    const canvas = fabricCanvasRef.current;
    if (!canvas) return;
    try {
      canvas.renderAll();
      const canvasElem = canvas.getElement();
      canvasElem.toBlob(async (blob) => {
        if (!blob) throw new Error("Could not create image blob");
        await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
        setCopied(true);
        toast.success("Graphic copied to clipboard!");
        setTimeout(() => setCopied(false), 2000);
      });
    } catch (err) {
      console.error("Clipboard copy error:", err);
      toast.error("Clipboard copy not supported in this browser");
    }
  };

  // ─────────────────────────────────────────────────────────────────────────────
  // Compute canvas display style (zoom transform)
  // ─────────────────────────────────────────────────────────────────────────────
  const canvasDisplayWidth = currentDimensions.width * zoom;
  const canvasDisplayHeight = currentDimensions.height * zoom;

  return (
    <div className="flex flex-col gap-3">
      {/* ── Controls Header ─────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border/60 bg-surface/80 p-2.5 backdrop-blur-md">
        {/* Aspect ratio */}
        <div className="flex items-center gap-1">
          <span className="text-[10px] font-semibold text-muted-foreground mr-1">Ratio:</span>
          {Object.entries(ASPECT_RATIOS).map(([key, dim]) => (
            <button
              key={key}
              type="button"
              onClick={() => setAspectRatioKey(key)}
              className={`flex items-center gap-1 rounded-lg px-2 py-1 text-[10px] font-medium transition-all ${
                aspectRatioKey === key
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "bg-secondary/60 text-muted-foreground hover:text-foreground"
              }`}
            >
              {key === "4:5" && <Smartphone className="size-2.5" />}
              {key === "1:1" && <Square className="size-2.5" />}
              {key === "16:9" && <MonitorPlay className="size-2.5" />}
              {key === "9:16" && <Flame className="size-2.5" />}
              {dim.badgeRatio}
            </button>
          ))}
        </div>

        {/* Theme picker */}
        <div className="flex items-center gap-1.5">
          <Palette className="size-3 text-muted-foreground" />
          <div className="flex items-center gap-1">
            {PRESET_THEMES.map((theme) => (
              <button
                key={theme.id}
                type="button"
                onClick={() => setSelectedTheme(theme)}
                title={theme.name}
                className={`relative size-5 rounded-full border transition-all ${
                  selectedTheme.id === theme.id
                    ? "ring-2 ring-primary ring-offset-1 ring-offset-background scale-110 border-white"
                    : "border-border/60 opacity-80 hover:opacity-100"
                }`}
                style={{
                  background: `linear-gradient(135deg, ${theme.bgGradient[0]}, ${theme.accentColor})`,
                }}
              />
            ))}
          </div>
        </div>

        {/* Background source */}
        <div className="flex items-center gap-1">
          {backgroundImageUrl && (
            <button
              type="button"
              onClick={() => setBgSource("ai")}
              className={`flex items-center gap-1 rounded-lg px-2 py-1 text-[10px] font-medium transition-all ${
                bgSource === "ai"
                  ? "bg-primary text-primary-foreground"
                  : "bg-secondary/60 text-muted-foreground hover:text-foreground"
              }`}
            >
              <Sparkles className="size-2.5" />AI Art
            </button>
          )}
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className={`flex items-center gap-1 rounded-lg px-2 py-1 text-[10px] font-medium transition-all ${
              bgSource === "custom"
                ? "bg-primary text-primary-foreground"
                : "bg-secondary/60 text-muted-foreground hover:text-foreground"
            }`}
          >
            <Upload className="size-2.5" />Upload
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
            className={`flex items-center gap-1 rounded-lg px-2 py-1 text-[10px] font-medium transition-all ${
              bgSource === "preset"
                ? "bg-primary text-primary-foreground"
                : "bg-secondary/60 text-muted-foreground hover:text-foreground"
            }`}
          >
            <Layers className="size-2.5" />Preset
          </button>
        </div>
      </div>

      {/* ── Creator Toolbar ─────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border/60 bg-surface/80 px-3 py-2">
        {/* Add Text */}
        <button
          type="button"
          onClick={handleAddText}
          className="flex items-center gap-1 rounded-lg border border-border/70 bg-secondary/60 px-2.5 py-1.5 text-[11px] font-medium text-foreground hover:bg-secondary transition-colors"
        >
          <Plus className="size-3" /> Add Text
        </button>

        {/* Delete Selected */}
        <button
          type="button"
          onClick={handleDeleteSelected}
          disabled={!hasSelection}
          className="flex items-center gap-1 rounded-lg border border-destructive/40 bg-destructive/10 px-2.5 py-1.5 text-[11px] font-medium text-destructive hover:bg-destructive/20 transition-colors disabled:opacity-30"
        >
          <Trash2 className="size-3" /> Delete
        </button>

        {/* Font size controls */}
        <div className="flex items-center gap-1 rounded-lg border border-border/60 bg-secondary/40 px-2 py-1">
          <ALargeSmall className="size-3 text-muted-foreground" />
          <button
            type="button"
            onClick={() => handleFontSizeChange(-2)}
            disabled={!hasSelection || selectedFontSize === null}
            className="w-5 h-5 flex items-center justify-center rounded text-xs font-bold text-muted-foreground hover:text-foreground disabled:opacity-30"
          >
            –
          </button>
          <span className="text-[10px] font-mono text-muted-foreground w-6 text-center">
            {selectedFontSize ?? "--"}
          </span>
          <button
            type="button"
            onClick={() => handleFontSizeChange(2)}
            disabled={!hasSelection || selectedFontSize === null}
            className="w-5 h-5 flex items-center justify-center rounded text-xs font-bold text-muted-foreground hover:text-foreground disabled:opacity-30"
          >
            +
          </button>
        </div>

        {/* Color picker */}
        <div className="flex items-center gap-1">
          <span className="text-[10px] text-muted-foreground">Color:</span>
          <input
            type="color"
            value={selectedColor}
            onChange={(e) => handleColorChange(e.target.value)}
            disabled={!hasSelection}
            className="w-7 h-7 rounded cursor-pointer border border-border/60 bg-transparent disabled:opacity-30"
            title="Text color"
          />
        </div>

        {/* Bring forward */}
        <button
          type="button"
          onClick={handleBringForward}
          disabled={!hasSelection}
          className="flex items-center gap-1 rounded-lg border border-border/60 bg-secondary/40 px-2 py-1.5 text-[11px] text-muted-foreground hover:text-foreground disabled:opacity-30"
          title="Bring to front"
        >
          ↑ Forward
        </button>

        <div className="flex-1" />

        {/* Zoom controls */}
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={zoomOut}
            className="flex items-center justify-center size-6 rounded border border-border/60 bg-secondary/40 text-muted-foreground hover:text-foreground"
            title="Zoom out"
          >
            <ZoomOut className="size-3" />
          </button>
          <button
            type="button"
            onClick={zoomFit}
            className="flex items-center justify-center rounded border border-border/60 bg-secondary/40 px-2 py-0.5 text-[10px] font-mono text-muted-foreground hover:text-foreground"
            title="Fit to screen"
          >
            <Maximize2 className="size-2.5 mr-1" />{Math.round(zoom * 100)}%
          </button>
          <button
            type="button"
            onClick={zoomIn}
            className="flex items-center justify-center size-6 rounded border border-border/60 bg-secondary/40 text-muted-foreground hover:text-foreground"
            title="Zoom in"
          >
            <ZoomIn className="size-3" />
          </button>
        </div>
      </div>

      {/* ── Canvas Viewport ─────────────────────────────────────────────── */}
      <div
        ref={containerRef}
        className="relative flex min-h-[520px] items-center justify-center overflow-auto rounded-2xl border border-border/70 bg-black/40 p-6 shadow-inner"
      >
        {/* Canvas scaled via CSS transform for zoom */}
        <div
          className="relative overflow-hidden rounded-xl shadow-2xl flex-shrink-0"
          style={{
            width: canvasDisplayWidth,
            height: canvasDisplayHeight,
            transform: `scale(1)`,
          }}
        >
          <div
            style={{
              transform: `scale(${zoom})`,
              transformOrigin: "top left",
              width: currentDimensions.width,
              height: currentDimensions.height,
            }}
          >
            <canvas ref={canvasRef} />
          </div>
        </div>

        {/* Tip badge */}
        <div className="pointer-events-none absolute bottom-3 left-4 rounded-md bg-black/70 px-2.5 py-1 text-[10px] font-medium text-slate-300 backdrop-blur-md">
          💡 Double-click any text to edit inline · Select + Delete key or 🗑️ button to remove
        </div>
      </div>

      {/* ── Action Footer ────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
        <div className="flex items-center gap-2">
          {onRegenerateBg && (
            <button
              type="button"
              onClick={() => {
                // Auto-switch to AI mode when regenerating
                setBgSource("ai");
                onRegenerateBg();
              }}
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
            title="Reset to default layout"
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
            Download PNG
          </button>
        </div>
      </div>
    </div>
  );
};
