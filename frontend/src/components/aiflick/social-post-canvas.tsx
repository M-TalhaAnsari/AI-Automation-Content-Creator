/**
 * frontend/src/components/aiflick/social-post-canvas.tsx
 *
 * Production-Grade Interactive Social Post Studio built with Fabric.js.
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
  Trash2,
  Plus,
  ZoomIn,
  ZoomOut,
  Maximize2,
  ALargeSmall,
  Undo2,
  Redo2,
  Paintbrush,
  MoveUp,
  MoveDown,
} from "lucide-react";
import { toast } from "sonner";
import { getImageUrl } from "@/api";
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
  onTitleChange?: (newTitle: string) => void;
  onHookChange?: (newHook: string) => void;
}

const ZOOM_LEVELS = [0.35, 0.5, 0.65, 0.75, 1.0, 1.25];

export const SocialPostCanvas: React.FC<SocialPostCanvasProps> = ({
  backgroundImageUrl,
  title,
  hook = "",
  summary = [],
  platform = "instagram",
  authorHandle = "@aiflick",
  onRegenerateBg,
  isGeneratingBg = false,
  onTitleChange,
  onHookChange,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const fabricCanvasRef = useRef<fabric.Canvas | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Refs to named canvas text objects — updated in-place to avoid full rebuilds
  const titleObjRef = useRef<fabric.Textbox | null>(null);
  const hookObjRef = useRef<fabric.Textbox | null>(null);
  const bulletObjRefs = useRef<fabric.Textbox[]>([]);

  const historyStackRef = useRef<string[]>([]);
  const historyIndexRef = useRef<number>(-1);
  const isHistoryActionRef = useRef<boolean>(false);

  const [aspectRatioKey, setAspectRatioKey] = useState<string>("4:5");
  const [selectedTheme, setSelectedTheme] = useState<PostTheme>(PRESET_THEMES[0]);
  const [customBgDataUrl, setCustomBgDataUrl] = useState<string | null>(null);
  const [bgSource, setBgSource] = useState<"ai" | "custom" | "preset" | "solid">("ai");
  const [solidColor, setSolidColor] = useState<string>("#0F172A");
  const [cardOpacity, setCardOpacity] = useState<"subtle" | "medium" | "solid" | "none">("subtle");
  const [showWatermark, setShowWatermark] = useState<boolean>(true);

  const [copied, setCopied] = useState(false);
  const [isReady, setIsReady] = useState(false);
  const [zoom, setZoom] = useState(0.65);
  const [bgLoading, setBgLoading] = useState(false);
  const [hasSelection, setHasSelection] = useState(false);
  const [selectedFontSize, setSelectedFontSize] = useState<number | null>(null);
  const [selectedColor, setSelectedColor] = useState<string>("#FFFFFF");
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);

  useEffect(() => {
    if (backgroundImageUrl) {
      setBgSource("ai");
    }
  }, [backgroundImageUrl]);

  const bulletPoints: string[] = React.useMemo(() => {
    if (Array.isArray(summary)) return summary.filter(Boolean);
    if (typeof summary === "string") {
      return summary
        .split("\n")
        .map((s) => s.trim().replace(/^[-•*📌🚀⚡💡🔴\d.]+\s*/, ""))
        .filter(Boolean);
    }
    return [];
  }, [summary]);

  const currentDimensions = ASPECT_RATIOS[aspectRatioKey] || ASPECT_RATIOS["4:5"];

  const saveStateToHistory = useCallback(() => {
    const canvas = fabricCanvasRef.current;
    if (!canvas || isHistoryActionRef.current) return;

    try {
      const json = JSON.stringify(canvas.toJSON());
      const newStack = historyStackRef.current.slice(0, historyIndexRef.current + 1);
      newStack.push(json);
      if (newStack.length > 25) newStack.shift();
      historyStackRef.current = newStack;
      historyIndexRef.current = newStack.length - 1;
      setCanUndo(historyIndexRef.current > 0);
      setCanRedo(false);
    } catch {
      // Ignore
    }
  }, []);

  /**
   * Fetch an image URL and convert it to a blob: URL so Fabric.js can load it
   * without any CORS restrictions. This bypasses the silent CORS failure that
   * occurs when Fabric uses crossOrigin:"anonymous" against a server returning
   * Access-Control-Allow-Origin: * (wildcard).
   */
  const loadImageAsDataUrl = useCallback(async (url: string): Promise<string> => {
    if (!url) return "";
    if (url.startsWith("data:") || url.startsWith("blob:")) return url;
    const fullUrl = getImageUrl(url, false);
    try {
      const resp = await fetch(fullUrl, { cache: "no-store", mode: "cors" });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const blob = await resp.blob();
      return URL.createObjectURL(blob);
    } catch {
      return fullUrl; // fall back to full URL on error
    }
  }, []);

  const undo = useCallback(() => {
    const canvas = fabricCanvasRef.current;
    if (!canvas || historyIndexRef.current <= 0) return;

    isHistoryActionRef.current = true;
    historyIndexRef.current -= 1;
    const targetState = historyStackRef.current[historyIndexRef.current];

    canvas.loadFromJSON(targetState, () => {
      canvas.renderAll();
      isHistoryActionRef.current = false;
      setCanUndo(historyIndexRef.current > 0);
      setCanRedo(historyIndexRef.current < historyStackRef.current.length - 1);
      toast.info("Undo");
    });
  }, []);

  const redo = useCallback(() => {
    const canvas = fabricCanvasRef.current;
    if (!canvas || historyIndexRef.current >= historyStackRef.current.length - 1) return;

    isHistoryActionRef.current = true;
    historyIndexRef.current += 1;
    const targetState = historyStackRef.current[historyIndexRef.current];

    canvas.loadFromJSON(targetState, () => {
      canvas.renderAll();
      isHistoryActionRef.current = false;
      setCanUndo(true);
      setCanRedo(historyIndexRef.current < historyStackRef.current.length - 1);
      toast.info("Redo");
    });
  }, []);

  const renderCanvasComposition = useCallback(async () => {
    const canvas = fabricCanvasRef.current;
    if (!canvas) return;

    // Reset named object refs each time we do a full rebuild
    titleObjRef.current = null;
    hookObjRef.current = null;
    bulletObjRefs.current = [];

    const { width, height } = currentDimensions;
    canvas.setWidth(width);
    canvas.setHeight(height);
    canvas.clear();

    // Use the current prop values via refs so the callback closure stays stable
    const currentTitle = (titleObjRef.current ? (titleObjRef.current as any).text : title) || title;
    const currentBullets = bulletPoints;

    const layout = computeAutoLayout(width, height, currentTitle, currentBullets.length);

    const buildForegroundLayers = () => {
      let containerFill = selectedTheme.containerBg;
      if (bgSource === "ai" || bgSource === "custom") {
        if (cardOpacity === "subtle") containerFill = "rgba(10, 15, 30, 0.40)";
        else if (cardOpacity === "medium") containerFill = "rgba(10, 15, 30, 0.70)";
        else if (cardOpacity === "none") containerFill = "rgba(0, 0, 0, 0.05)";
        else containerFill = selectedTheme.containerBg;
      } else {
        if (cardOpacity === "subtle") containerFill = "rgba(10, 15, 30, 0.45)";
        else if (cardOpacity === "none") containerFill = "rgba(0, 0, 0, 0.05)";
        else if (cardOpacity === "medium") containerFill = "rgba(10, 15, 30, 0.70)";
        else containerFill = selectedTheme.containerBg;
      }

      const container = new fabric.Rect({
        left: layout.horizontalMargin,
        top: layout.topMargin,
        width: layout.containerWidth,
        height: layout.containerHeight,
        rx: 28,
        ry: 28,
        fill: containerFill,
        stroke: selectedTheme.containerBorder,
        strokeWidth: 1.5,
        selectable: false,
        evented: false,
        shadow: new fabric.Shadow({
          color: "rgba(0,0,0,0.6)",
          blur: 35,
          offsetX: 0,
          offsetY: 16,
        }),
      });
      canvas.add(container);

      const innerLeft = layout.horizontalMargin + 48;
      const innerWidth = layout.containerWidth - 96;
      let currentY = layout.topMargin + 48;

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

      const badgeText = new fabric.Textbox(`✨ ${platform.toUpperCase()} GUIDE`, {
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
      });
      canvas.add(badgeText);
      currentY += 56;

      // --- TITLE: store ref, wire text:changed ---
      const cleanCanvasTitle = (title || "").replace(/^#+\s*/gm, "").replace(/\*\*(.*?)\*\*/g, "$1");
      const titleFab = new fabric.Textbox(cleanCanvasTitle, {
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
      titleFab.on("changed", () => {
        if (onTitleChange) onTitleChange((titleFab as any).text || "");
      });
      titleObjRef.current = titleFab;
      canvas.add(titleFab);
      currentY += (titleFab.height || 60) + 16;

      // --- HOOK: store ref, wire text:changed ---
      if (hook) {
        const cleanHook = (hook || "").replace(/^#+\s*/gm, "").replace(/\*\*(.*?)\*\*/g, "$1");
        const hookFab = new fabric.Textbox(`⚡ ${cleanHook}`, {
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
        hookFab.on("changed", () => {
          if (onHookChange) {
            const raw: string = (hookFab as any).text || "";
            // Strip the leading "⚡ " prefix we added
            onHookChange(raw.replace(/^⚡\s*/, ""));
          }
        });
        hookObjRef.current = hookFab;
        canvas.add(hookFab);
        currentY += (hookFab.height || 30) + 24;
      }

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

      const itemsToRender =
        bulletPoints.length > 0
          ? bulletPoints.slice(0, 5)
          : [
              "1. Core Implementation & Architecture",
              "2. Key Workflow Decisions",
              "3. Production Scale & Outcomes",
            ];

      bulletObjRefs.current = [];
      itemsToRender.forEach((bulletText, idx) => {
        const numCircle = new fabric.Circle({
          radius: 14,
          fill: selectedTheme.bulletNumBg,
          left: innerLeft,
          top: currentY + 2,
          selectable: true,
          hoverCursor: "move",
        });
        canvas.add(numCircle);

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
        bulletObjRefs.current.push(bulletContent);
        canvas.add(bulletContent);

        currentY += Math.max(bulletContent.height || 36, 36) + layout.bulletSpacing;
      });

      if (showWatermark) {
        const footerY = layout.topMargin + layout.containerHeight - 48;
        const footerTag = new fabric.Textbox(
          `✨ Created with AIFlick  •  ${authorHandle}`,
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
      }

      canvas.renderAll();
      setIsReady(true);
      saveStateToHistory();
    };

    if (bgSource === "solid") {
      canvas.setBackgroundColor(solidColor, () => {
        canvas.backgroundImage = undefined;
        buildForegroundLayers();
      });
    } else {
      let activeBgUrl: string;
      if (bgSource === "custom" && customBgDataUrl) {
        activeBgUrl = customBgDataUrl;
      } else if (bgSource === "ai" && backgroundImageUrl) {
        // Strip any existing cache-bust query param before adding a fresh one
        const base = backgroundImageUrl.split("?")[0];
        activeBgUrl = `${base}?_t=${Date.now()}`;
      } else {
        activeBgUrl = generatePresetBackgroundDataUrl(width, height, selectedTheme);
      }

      // Use fetch → blob URL to bypass CORS restrictions completely.
      // fabric.Image.fromURL with crossOrigin:"anonymous" silently fails
      // when the server returns Access-Control-Allow-Origin: * (wildcard).
      setBgLoading(true);
      loadImageAsDataUrl(activeBgUrl).then((resolvedUrl) => {
        fabric.Image.fromURL(resolvedUrl, (img) => {
          setBgLoading(false);
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
        });
      }).catch(() => {
        setBgLoading(false);
        canvas.backgroundColor = selectedTheme.bgGradient[0];
        buildForegroundLayers();
      });
    }
  // ⚠️  title / hook / bulletPoints are NOT in this dep array.
  // Text is updated in-place via the useEffect hooks below to avoid a full rebuild on every keystroke.
  }, [
    currentDimensions,
    platform,
    authorHandle,
    bgSource,
    solidColor,
    cardOpacity,
    showWatermark,
    customBgDataUrl,
    backgroundImageUrl,
    selectedTheme,
    saveStateToHistory,
    loadImageAsDataUrl,
  ]);

  useEffect(() => {
    if (!canvasRef.current) return;

    const fc = new fabric.Canvas(canvasRef.current, {
      preserveObjectStacking: true,
      selection: true,
    });
    fabricCanvasRef.current = fc;

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

    fc.on("object:modified", saveStateToHistory);

    const handleKeyDown = (e: KeyboardEvent) => {
      const active = fc.getActiveObject() as any;
      const isEditingText = active && active.isEditing;

      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z" && !e.shiftKey) {
        if (!isEditingText) {
          e.preventDefault();
          undo();
          return;
        }
      }

      if (
        ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "y") ||
        ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === "z")
      ) {
        if (!isEditingText) {
          e.preventDefault();
          redo();
          return;
        }
      }

      if ((e.key === "Delete" || e.key === "Backspace") && !isEditingText) {
        const activeObjs = fc.getActiveObjects();
        if (activeObjs.length > 0) {
          e.preventDefault();
          fc.discardActiveObject();
          activeObjs.forEach((obj) => fc.remove(obj));
          fc.renderAll();
          setHasSelection(false);
          saveStateToHistory();
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    renderCanvasComposition();

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      fc.dispose();
      fabricCanvasRef.current = null;
    };
  }, []);

  useEffect(() => {
    renderCanvasComposition();
  }, [renderCanvasComposition]);

  // ── Lightweight title updater: patch the title Fabric object in-place ──
  useEffect(() => {
    const obj = titleObjRef.current;
    const canvas = fabricCanvasRef.current;
    if (!obj || !canvas) return;
    const clean = (title || "").replace(/^#+\s*/gm, "").replace(/\*\*(.*?)\*\*/g, "$1");
    // Only update if not currently being edited by the user directly on canvas
    if (!(obj as any).isEditing && (obj as any).text !== clean) {
      obj.set("text", clean);
      canvas.renderAll();
    }
  }, [title]);

  // ── Lightweight hook updater: patch the hook Fabric object in-place ──
  useEffect(() => {
    const obj = hookObjRef.current;
    const canvas = fabricCanvasRef.current;
    if (!obj || !canvas) return;
    const clean = (hook || "").replace(/^#+\s*/gm, "").replace(/\*\*(.*?)\*\*/g, "$1");
    const desired = `⚡ ${clean}`;
    if (!(obj as any).isEditing && (obj as any).text !== desired) {
      obj.set("text", desired);
      canvas.renderAll();
    }
  }, [hook]);

  // ── Lightweight bullet updater: patch bullet Fabric objects in-place ──
  useEffect(() => {
    const canvas = fabricCanvasRef.current;
    if (!canvas || bulletObjRefs.current.length === 0) return;
    const bp: string[] = Array.isArray(bulletPoints) ? bulletPoints : [];
    bulletObjRefs.current.forEach((obj, idx) => {
      const newText = bp[idx] ?? "";
      if (!(obj as any).isEditing && (obj as any).text !== newText) {
        obj.set("text", newText);
      }
    });
    canvas.renderAll();
  }, [bulletPoints]);

  const handleDeleteSelected = () => {
    const canvas = fabricCanvasRef.current;
    if (!canvas) return;
    const activeObjs = canvas.getActiveObjects();
    if (!activeObjs.length) return;
    canvas.discardActiveObject();
    activeObjs.forEach((obj) => canvas.remove(obj));
    canvas.renderAll();
    setHasSelection(false);
    saveStateToHistory();
    toast.success("Deleted selected item");
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
    saveStateToHistory();
    toast.success("New text added -- double-click to edit");
  };

  const handleFontSizeChange = (delta: number) => {
    const canvas = fabricCanvasRef.current;
    if (!canvas) return;
    const obj = canvas.getActiveObject() as any;
    if (!obj || obj.fontSize === undefined) return;
    const newSize = Math.max(8, Math.min(180, (obj.fontSize || 24) + delta));
    obj.set("fontSize", newSize);
    canvas.renderAll();
    setSelectedFontSize(newSize);
    saveStateToHistory();
  };

  const handleTextColorChange = (color: string) => {
    const canvas = fabricCanvasRef.current;
    if (!canvas) return;
    const obj = canvas.getActiveObject() as any;
    if (!obj) return;
    obj.set("fill", color);
    canvas.renderAll();
    setSelectedColor(color);
    saveStateToHistory();
  };

  const handleBringForward = () => {
    const canvas = fabricCanvasRef.current;
    if (!canvas) return;
    const obj = canvas.getActiveObject();
    if (!obj) return;
    canvas.bringForward(obj);
    canvas.renderAll();
    saveStateToHistory();
  };

  const handleSendBackward = () => {
    const canvas = fabricCanvasRef.current;
    if (!canvas) return;
    const obj = canvas.getActiveObject();
    if (!obj) return;
    canvas.sendBackwards(obj);
    canvas.renderAll();
    saveStateToHistory();
  };

  const handleCustomUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      toast.error("Please upload a valid PNG or JPEG image");
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

  const handleDownload = () => {
    const canvas = fabricCanvasRef.current;
    if (!canvas) return;
    try {
      const dataUrl = canvas.toDataURL({ format: "png", multiplier: 1, quality: 1 });
      const a = document.createElement("a");
      a.href = dataUrl;
      a.download = `aiflick-${platform}-${aspectRatioKey.replace(":", "-")}.png`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      toast.success("High-resolution graphic downloaded!");
    } catch {
      toast.error("Could not export image.");
    }
  };

  const handleCopyToClipboard = async () => {
    const canvas = fabricCanvasRef.current;
    if (!canvas) return;
    try {
      canvas.renderAll();
      const canvasElem = canvas.getElement();
      canvasElem.toBlob(async (blob) => {
        if (!blob) throw new Error("Blob error");
        await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
        setCopied(true);
        toast.success("Graphic copied to clipboard!");
        setTimeout(() => setCopied(false), 2000);
      });
    } catch {
      toast.error("Clipboard copy not supported in this browser");
    }
  };

  const canvasDisplayWidth = currentDimensions.width * zoom;
  const canvasDisplayHeight = currentDimensions.height * zoom;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border/70 bg-surface-raised/70 p-2.5 backdrop-blur-md">
        <div className="flex items-center gap-1">
          <span className="text-[11px] font-semibold text-muted-foreground mr-1">Ratio:</span>
          {Object.entries(ASPECT_RATIOS).map(([key, dim]) => (
            <button
              key={key}
              type="button"
              onClick={() => setAspectRatioKey(key)}
              className={`flex items-center gap-1 rounded-lg px-2.5 py-1 text-xs font-medium transition-all ${
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

        <div className="flex items-center gap-1.5">
          <Palette className="size-3.5 text-muted-foreground" />
          <div className="flex items-center gap-1">
            {PRESET_THEMES.map((theme) => (
              <button
                key={theme.id}
                type="button"
                onClick={() => {
                  setSelectedTheme(theme);
                  setBgSource("preset");
                }}
                title={theme.name}
                className={`relative size-5 rounded-full border transition-all ${
                  selectedTheme.id === theme.id && bgSource === "preset"
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

        <div className="flex items-center gap-1">
          <span className="text-[11px] font-semibold text-muted-foreground mr-1">Glass Card:</span>
          {(["subtle", "medium", "solid", "none"] as const).map((op) => (
            <button
              key={op}
              type="button"
              onClick={() => setCardOpacity(op)}
              className={`rounded-lg px-2 py-1 text-[11px] font-medium capitalize transition-all ${
                cardOpacity === op
                  ? "bg-primary text-primary-foreground font-semibold"
                  : "bg-secondary/60 text-muted-foreground hover:text-foreground"
              }`}
            >
              {op === "none" ? "Clear" : op}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-1">
          {backgroundImageUrl && (
            <button
              type="button"
              onClick={() => setBgSource("ai")}
              className={`flex items-center gap-1 rounded-lg px-2.5 py-1 text-xs font-medium transition-all ${
                bgSource === "ai"
                  ? "bg-primary text-primary-foreground"
                  : "bg-secondary/60 text-muted-foreground hover:text-foreground"
              }`}
            >
              <Sparkles className="size-3" /> AI Art
            </button>
          )}

          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className={`flex items-center gap-1 rounded-lg px-2.5 py-1 text-xs font-medium transition-all ${
              bgSource === "custom"
                ? "bg-primary text-primary-foreground"
                : "bg-secondary/60 text-muted-foreground hover:text-foreground"
            }`}
          >
            <Upload className="size-3" /> Upload
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
            onClick={() => setBgSource("solid")}
            className={`flex items-center gap-1 rounded-lg px-2.5 py-1 text-xs font-medium transition-all ${
              bgSource === "solid"
                ? "bg-primary text-primary-foreground"
                : "bg-secondary/60 text-muted-foreground hover:text-foreground"
            }`}
          >
            <Paintbrush className="size-3" /> Solid Color
          </button>

          <button
            type="button"
            onClick={() => setBgSource("preset")}
            className={`flex items-center gap-1 rounded-lg px-2.5 py-1 text-xs font-medium transition-all ${
              bgSource === "preset"
                ? "bg-primary text-primary-foreground"
                : "bg-secondary/60 text-muted-foreground hover:text-foreground"
            }`}
          >
            <Layers className="size-3" /> Preset
          </button>
        </div>
      </div>

      {bgSource === "solid" && (
        <div className="flex items-center gap-2 rounded-xl border border-border/60 bg-surface-raised/50 px-3 py-1.5 text-xs">
          <span className="text-muted-foreground font-medium">Custom Solid Color:</span>
          <input
            type="color"
            value={solidColor}
            onChange={(e) => setSolidColor(e.target.value)}
            className="size-6 cursor-pointer rounded border border-border/60 bg-transparent"
          />
          <span className="font-mono text-[11px] text-muted-foreground">{solidColor}</span>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border/70 bg-surface-raised/70 px-3 py-2">
        <div className="flex items-center gap-0.5 border-r border-border/60 pr-2">
          <button
            type="button"
            onClick={undo}
            disabled={!canUndo}
            title="Undo (Ctrl+Z)"
            className="flex size-7 items-center justify-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground disabled:opacity-30"
          >
            <Undo2 className="size-3.5" />
          </button>
          <button
            type="button"
            onClick={redo}
            disabled={!canRedo}
            title="Redo (Ctrl+Y)"
            className="flex size-7 items-center justify-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground disabled:opacity-30"
          >
            <Redo2 className="size-3.5" />
          </button>
        </div>

        <button
          type="button"
          onClick={handleAddText}
          className="flex items-center gap-1 rounded-lg border border-border/70 bg-secondary/60 px-2.5 py-1.5 text-xs font-medium text-foreground hover:bg-secondary transition-colors"
        >
          <Plus className="size-3.5" /> Add Text
        </button>

        <button
          type="button"
          onClick={handleDeleteSelected}
          disabled={!hasSelection}
          className="flex items-center gap-1 rounded-lg border border-destructive/40 bg-destructive/10 px-2.5 py-1.5 text-xs font-medium text-destructive hover:bg-destructive/20 transition-colors disabled:opacity-30"
          title="Delete selected item (Delete / Backspace)"
        >
          <Trash2 className="size-3.5" /> Delete
        </button>

        <button
          type="button"
          onClick={() => setShowWatermark((prev) => !prev)}
          className={`flex items-center gap-1 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-all ${
            showWatermark
              ? "border-primary/40 bg-primary/10 text-primary hover:bg-primary/20 font-medium"
              : "border-border/60 bg-secondary/40 text-muted-foreground hover:text-foreground"
          }`}
          title="Toggle AIFlick footer watermark on/off"
        >
          <Sparkles className="size-3" /> Watermark: {showWatermark ? "ON" : "OFF"}
        </button>

        <div className="flex items-center gap-1 rounded-lg border border-border/60 bg-secondary/40 px-2 py-1">
          <ALargeSmall className="size-3.5 text-muted-foreground" />
          <button
            type="button"
            onClick={() => handleFontSizeChange(-2)}
            disabled={!hasSelection || selectedFontSize === null}
            className="size-5 flex items-center justify-center rounded text-xs font-bold text-muted-foreground hover:text-foreground disabled:opacity-30"
          >
            –
          </button>
          <span className="text-[11px] font-mono text-muted-foreground w-6 text-center">
            {selectedFontSize ?? "--"}
          </span>
          <button
            type="button"
            onClick={() => handleFontSizeChange(2)}
            disabled={!hasSelection || selectedFontSize === null}
            className="size-5 flex items-center justify-center rounded text-xs font-bold text-muted-foreground hover:text-foreground disabled:opacity-30"
          >
            +
          </button>
        </div>

        <div className="flex items-center gap-1.5 pl-1">
          <span className="text-xs text-muted-foreground">Color:</span>
          <input
            type="color"
            value={selectedColor}
            onChange={(e) => handleTextColorChange(e.target.value)}
            disabled={!hasSelection}
            className="size-6 rounded cursor-pointer border border-border/60 bg-transparent disabled:opacity-30"
            title="Text color"
          />
        </div>

        <div className="flex items-center gap-1 pl-1 border-l border-border/60">
          <button
            type="button"
            onClick={handleBringForward}
            disabled={!hasSelection}
            className="flex items-center gap-0.5 rounded px-2 py-1 text-xs text-muted-foreground hover:bg-secondary hover:text-foreground disabled:opacity-30"
            title="Bring Forward"
          >
            <MoveUp className="size-3" /> Up
          </button>
          <button
            type="button"
            onClick={handleSendBackward}
            disabled={!hasSelection}
            className="flex items-center gap-0.5 rounded px-2 py-1 text-xs text-muted-foreground hover:bg-secondary hover:text-foreground disabled:opacity-30"
            title="Send Backward"
          >
            <MoveDown className="size-3" /> Down
          </button>
        </div>

        <div className="flex-1" />

        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => {
              const prev = [...ZOOM_LEVELS].reverse().find((z) => z < zoom) ?? ZOOM_LEVELS[0];
              setZoom(prev);
            }}
            className="flex size-7 items-center justify-center rounded border border-border/60 bg-secondary/40 text-muted-foreground hover:text-foreground"
            title="Zoom Out"
          >
            <ZoomOut className="size-3.5" />
          </button>
          <button
            type="button"
            onClick={() => setZoom(0.65)}
            className="flex items-center justify-center rounded border border-border/60 bg-secondary/40 px-2.5 py-1 text-xs font-mono text-muted-foreground hover:text-foreground"
            title="Fit to Screen"
          >
            <Maximize2 className="size-3 mr-1" />
            {Math.round(zoom * 100)}%
          </button>
          <button
            type="button"
            onClick={() => {
              const next = ZOOM_LEVELS.find((z) => z > zoom) ?? ZOOM_LEVELS[ZOOM_LEVELS.length - 1];
              setZoom(next);
            }}
            className="flex size-7 items-center justify-center rounded border border-border/60 bg-secondary/40 text-muted-foreground hover:text-foreground"
            title="Zoom In"
          >
            <ZoomIn className="size-3.5" />
          </button>
        </div>
      </div>

      <div
        ref={containerRef}
        className="relative flex min-h-[580px] items-center justify-center overflow-auto rounded-2xl border border-border/70 bg-black/50 p-6 shadow-inner"
      >
        <div
          className="relative overflow-hidden rounded-xl shadow-2xl shrink-0"
          style={{
            width: canvasDisplayWidth,
            height: canvasDisplayHeight,
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

          {/* AI background loading overlay */}
          {bgLoading && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 rounded-xl bg-black/60 backdrop-blur-sm">
              <div className="size-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
              <span className="text-[11px] font-medium text-white/80">Loading AI background…</span>
            </div>
          )}
        </div>

        <div className="pointer-events-none absolute bottom-3 left-4 rounded-md bg-black/75 px-3 py-1.5 text-[11px] font-medium text-slate-300 backdrop-blur-md">
          💡 Double-click any text to edit inline • Click to select + Delete key to remove • Ctrl+Z to Undo
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
        <div className="flex items-center gap-2">
          {onRegenerateBg && (
            <button
              type="button"
              onClick={() => {
                setBgSource("ai");
                onRegenerateBg();
              }}
              disabled={isGeneratingBg}
              className="flex items-center gap-1.5 rounded-lg border border-border/80 bg-secondary/80 px-3.5 py-2 text-xs font-medium text-foreground transition-colors hover:bg-secondary disabled:opacity-50"
            >
              <Sparkles className="size-3.5 text-primary" />
              {isGeneratingBg ? "Regenerating AI Art..." : "Regenerate AI Background"}
            </button>
          )}

          <button
            type="button"
            onClick={renderCanvasComposition}
            title="Reset layout to defaults"
            className="flex items-center gap-1.5 rounded-lg border border-border/60 bg-transparent px-3 py-2 text-xs font-medium text-muted-foreground hover:text-foreground"
          >
            <RotateCcw className="size-3.5" /> Reset
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
            <Download className="size-3.5" /> Download PNG
          </button>
        </div>
      </div>
    </div>
  );
};
