/**
 * frontend/src/components/aiflick/social-post-canvas.tsx
 *
 * Production-Grade Interactive Social Post Studio built with Fabric.js.
 *
 * Features & Fixes:
 *  1. Stable callback refs — onTitleChange/onHookChange/onSummaryChange stored in
 *     useRef so Fabric event listeners never capture stale closures, preventing
 *     re-mount/reload cycles when editing directly on canvas.
 *  2. Generation-token anti-overlap guard — renderGenerationRef cancels stale
 *     async background image resolutions.
 *  3. Full canvas object flush before clear to reset Fabric's object registry.
 *  4. Up to 7 bullet points supported with dynamic scaling.
 *  5. Single-click-again to enter text editing on already-selected text.
 *  6. Space + Drag canvas pan when zoomed in.
 *  7. Full creative toolbar: bold, italic, underline, alignment, duplicate (Ctrl+D),
 *     lock/unlock, vector shapes (rect, circle, line), opacity, font family, line height.
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
  ZoomIn,
  ZoomOut,
  Maximize2,
  ALargeSmall,
  Undo2,
  Redo2,
  Paintbrush,
  MoveUp,
  MoveDown,
  Bold,
  Italic,
  Underline,
  AlignLeft,
  AlignCenter,
  AlignRight,
  Copy as CopyIcon,
  Lock,
  Unlock,
  Circle,
  Minus,
  Type,
} from "lucide-react";
import { toast } from "sonner";
import { getImageUrl } from "@/api";
import {
  ASPECT_RATIOS,
  PRESET_THEMES,
  type PostTheme,
  computeAutoLayout,
  generatePresetBackgroundDataUrl,
} from "./canvas-templates";

export interface SocialPostCanvasProps {
  backgroundImageUrl?: string | null | undefined;
  title: string;
  hook?: string | undefined;
  summary?: string[] | string | undefined;
  platform?: string | undefined;
  authorHandle?: string | undefined;
  onRegenerateBg?: (() => void) | undefined;
  isGeneratingBg?: boolean | undefined;
  onTitleChange?: ((newTitle: string) => void) | undefined;
  onHookChange?: ((newHook: string) => void) | undefined;
  onSummaryChange?: ((newSummary: string[]) => void) | undefined;
}

const ZOOM_LEVELS = [0.35, 0.5, 0.65, 0.75, 1.0, 1.25];
const FONT_FAMILIES = [
  "Inter, -apple-system, sans-serif",
  "Georgia, serif",
  "Courier New, monospace",
  "Arial, sans-serif",
  "Trebuchet MS, sans-serif",
];
const FONT_FAMILY_LABELS = ["Inter", "Georgia", "Courier", "Arial", "Trebuchet"];

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
  onSummaryChange,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const fabricCanvasRef = useRef<fabric.Canvas | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // ── Stable callback refs — updated every render so Fabric listeners
  //    always call the latest prop version without triggering re-renders ──
  const onTitleChangeRef = useRef(onTitleChange);
  const onHookChangeRef = useRef(onHookChange);
  const onSummaryChangeRef = useRef(onSummaryChange);
  useEffect(() => { onTitleChangeRef.current = onTitleChange; }, [onTitleChange]);
  useEffect(() => { onHookChangeRef.current = onHookChange; }, [onHookChange]);
  useEffect(() => { onSummaryChangeRef.current = onSummaryChange; }, [onSummaryChange]);

  // Refs to named canvas text objects — updated in-place to avoid full rebuilds
  const titleObjRef = useRef<fabric.Textbox | null>(null);
  const hookObjRef = useRef<fabric.Textbox | null>(null);
  const bulletObjRefs = useRef<fabric.Textbox[]>([]);

  // Generation token: prevents stale async image-load from building on new canvas
  const renderGenerationRef = useRef<number>(0);

  const historyStackRef = useRef<string[]>([]);
  const historyIndexRef = useRef<number>(-1);
  const isHistoryActionRef = useRef<boolean>(false);

  // Pan mode refs
  const isPanningRef = useRef(false);
  const panStartRef = useRef<{ x: number; y: number } | null>(null);
  const panOffsetRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const isSpaceDownRef = useRef(false);

  const [aspectRatioKey, setAspectRatioKey] = useState<string>("4:5");
  const [selectedTheme, setSelectedTheme] = useState<PostTheme>(PRESET_THEMES[0]!);
  const [customBgDataUrl, setCustomBgDataUrl] = useState<string | null>(null);
  const [bgSource, setBgSource] = useState<"ai" | "custom" | "preset" | "solid">("ai");
  const [solidColor, setSolidColor] = useState<string>("#070B1A");
  const [cardOpacity, setCardOpacity] = useState<"subtle" | "medium" | "solid" | "none">("subtle");
  const [showWatermark, setShowWatermark] = useState<boolean>(true);

  const [copied, setCopied] = useState(false);
  const [, setIsReady] = useState(false);
  const [zoom, setZoom] = useState(0.65);
  const [bgLoading, setBgLoading] = useState(false);
  const [hasSelection, setHasSelection] = useState(false);
  const [selectedFontSize, setSelectedFontSize] = useState<number | null>(null);
  const [selectedColor, setSelectedColor] = useState<string>("#FFFFFF");
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);

  // Enhanced toolbar state
  const [selectedFontFamily, setSelectedFontFamily] = useState<string>(FONT_FAMILIES[0]!);
  const [selectedOpacity, setSelectedOpacity] = useState<number>(1);
  const [isLocked, setIsLocked] = useState<boolean>(false);
  const [selectedAlign, setSelectedAlign] = useState<string>("left");

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

  const currentDimensions = ASPECT_RATIOS[aspectRatioKey] ?? ASPECT_RATIOS["4:5"]!;

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
   * without any CORS restrictions.
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
      return fullUrl;
    }
  }, []);

  const undo = useCallback(() => {
    const canvas = fabricCanvasRef.current;
    if (!canvas || historyIndexRef.current <= 0) return;

    isHistoryActionRef.current = true;
    historyIndexRef.current -= 1;
    const targetState = historyStackRef.current[historyIndexRef.current];
    if (!targetState) return;

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
    if (!targetState) return;

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

    // ── Generation token: invalidate any in-flight async resolutions ──
    renderGenerationRef.current += 1;
    const thisGeneration = renderGenerationRef.current;

    // Reset named object refs each time we do a full rebuild
    titleObjRef.current = null;
    hookObjRef.current = null;
    bulletObjRefs.current = [];

    const { width, height } = currentDimensions;
    canvas.setWidth(width);
    canvas.setHeight(height);

    // Flush all objects from Fabric's registry before clear
    canvas.getObjects().forEach((obj) => canvas.remove(obj));
    canvas.clear();
    canvas.discardActiveObject();

    const layout = computeAutoLayout(width, height, title || "", bulletPoints.length);

    const buildForegroundLayers = () => {
      // Guard: abort if canvas was replaced by a newer render
      if (renderGenerationRef.current !== thisGeneration) return;
      if (!fabricCanvasRef.current) return;

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

      const badgeText = new fabric.Textbox(`✨ ${(platform || "instagram").toUpperCase()} GUIDE`, {
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

      // ── TITLE: store ref, wire text:changed with stable ref callback ──
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
      });
      titleFab.on("changed", () => {
        if (onTitleChangeRef.current) onTitleChangeRef.current((titleFab as any).text || "");
      });
      titleObjRef.current = titleFab;
      canvas.add(titleFab);
      currentY += (titleFab.height || 60) + 16;

      // ── HOOK: store ref, wire text:changed with stable ref callback ──
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
          if (onHookChangeRef.current) {
            const raw: string = (hookFab as any).text || "";
            onHookChangeRef.current(raw.replace(/^⚡\s*/, ""));
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

      // ── BULLETS: use real content, up to 7, fallback only when truly empty ──
      const itemsToRender =
        bulletPoints.length > 0
          ? bulletPoints.slice(0, 7)
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
        bulletContent.on("changed", () => {
          if (onSummaryChangeRef.current) {
            const updatedBullets = bulletObjRefs.current.map((b) => (b as any).text || "");
            onSummaryChangeRef.current(updatedBullets);
          }
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
        const base = backgroundImageUrl.split("?")[0];
        activeBgUrl = `${base}?_t=${Date.now()}`;
      } else {
        activeBgUrl = generatePresetBackgroundDataUrl(width, height, selectedTheme);
      }

      setBgLoading(true);
      loadImageAsDataUrl(activeBgUrl).then((resolvedUrl) => {
        // ── Generation guard: abort if this render is stale ──
        if (renderGenerationRef.current !== thisGeneration) {
          setBgLoading(false);
          return;
        }
        fabric.Image.fromURL(resolvedUrl, (img) => {
          setBgLoading(false);
          if (renderGenerationRef.current !== thisGeneration) return;
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
        if (renderGenerationRef.current !== thisGeneration) return;
        canvas.backgroundColor = selectedTheme.bgGradient[0];
        buildForegroundLayers();
      });
    }
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
    title,
    hook,
    bulletPoints,
    saveStateToHistory,
    loadImageAsDataUrl,
  ]);

  // ── Canvas initialization ──
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
      if (obj) {
        if (obj.fontSize !== undefined) setSelectedFontSize(obj.fontSize);
        if (obj.fill) setSelectedColor(obj.fill as string || "#FFFFFF");
        if (obj.fontFamily) setSelectedFontFamily(obj.fontFamily || FONT_FAMILIES[0]!);
        if (obj.opacity !== undefined) setSelectedOpacity(obj.opacity ?? 1);
        if (obj.textAlign) setSelectedAlign(obj.textAlign || "left");
        setIsLocked(!!obj.lockMovementX && !!obj.lockMovementY);
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

    // ── Smart single-click editing: if object already selected, enter edit ──
    fc.on("mouse:down", (opt) => {
      if (isSpaceDownRef.current) {
        isPanningRef.current = true;
        panStartRef.current = { x: opt.e.clientX, y: opt.e.clientY };
        fc.defaultCursor = "grabbing";
        fc.hoverCursor = "grabbing";
        opt.e.preventDefault();
        return;
      }
      const target = opt.target;
      if (
        target &&
        target instanceof fabric.Textbox &&
        (target as any).editable &&
        fc.getActiveObject() === target &&
        !(target as any).isEditing
      ) {
        // Already selected — enter text editing on single click
        setTimeout(() => {
          if (!isPanningRef.current) {
            target.enterEditing();
            fc.renderAll();
          }
        }, 150);
      }
    });

    fc.on("mouse:move", (opt) => {
      if (isPanningRef.current && panStartRef.current) {
        const dx = opt.e.clientX - panStartRef.current.x;
        const dy = opt.e.clientY - panStartRef.current.y;
        panOffsetRef.current.x += dx;
        panOffsetRef.current.y += dy;
        panStartRef.current = { x: opt.e.clientX, y: opt.e.clientY };
        fc.relativePan(new fabric.Point(dx, dy));
      }
    });

    fc.on("mouse:up", () => {
      if (isPanningRef.current) {
        isPanningRef.current = false;
        panStartRef.current = null;
        fc.defaultCursor = "default";
        fc.hoverCursor = "move";
      }
    });

    // Double-click still works for text that isn't selected yet
    fc.on("mouse:dblclick", (opt) => {
      const target = opt.target;
      if (target && target instanceof fabric.Textbox && (target as any).editable) {
        target.enterEditing();
        target.selectAll();
        fc.renderAll();
      }
    });

    fc.on("object:modified", saveStateToHistory);

    const handleKeyDown = (e: KeyboardEvent) => {
      const active = fc.getActiveObject() as any;
      const isEditingText = active && active.isEditing;

      // Space key activates pan mode
      if (e.code === "Space" && !isEditingText) {
        isSpaceDownRef.current = true;
        fc.defaultCursor = "grab";
        fc.hoverCursor = "grab";
        fc.renderAll();
      }

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

      // Ctrl+D to duplicate
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "d" && !isEditingText) {
        e.preventDefault();
        const activeObjs = fc.getActiveObjects();
        if (activeObjs.length > 0) {
          activeObjs.forEach((obj) => {
            obj.clone((cloned: fabric.Object) => {
              cloned.set({ left: (cloned.left || 0) + 20, top: (cloned.top || 0) + 20 });
              fc.add(cloned);
              fc.setActiveObject(cloned);
            });
          });
          fc.renderAll();
          saveStateToHistory();
        }
        return;
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

    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.code === "Space") {
        isSpaceDownRef.current = false;
        fc.defaultCursor = "default";
        fc.hoverCursor = "move";
        fc.renderAll();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);
    renderCanvasComposition();

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
      fc.dispose();
      fabricCanvasRef.current = null;
    };
  }, [renderCanvasComposition, redo, undo, saveStateToHistory]);

  // ── Lightweight title updater: patch the title Fabric object in-place ──
  useEffect(() => {
    const obj = titleObjRef.current;
    const canvas = fabricCanvasRef.current;
    if (!obj || !canvas) return;
    const clean = (title || "").replace(/^#+\s*/gm, "").replace(/\*\*(.*?)\*\*/g, "$1");
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

  // ── Enhanced toolbar handlers ──

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
    toast.success("New text added — click to select, click again to edit");
  };

  const handleAddShape = (shape: "rect" | "circle" | "line") => {
    const canvas = fabricCanvasRef.current;
    if (!canvas) return;
    const { width, height } = currentDimensions;
    let obj: fabric.Object;
    if (shape === "rect") {
      obj = new fabric.Rect({
        left: Math.round(width * 0.3),
        top: Math.round(height * 0.4),
        width: 200,
        height: 100,
        fill: "rgba(99, 102, 241, 0.3)",
        stroke: selectedTheme.containerBorder,
        strokeWidth: 2,
        rx: 12,
        ry: 12,
        selectable: true,
      });
    } else if (shape === "circle") {
      obj = new fabric.Circle({
        left: Math.round(width * 0.4),
        top: Math.round(height * 0.4),
        radius: 60,
        fill: "rgba(99, 102, 241, 0.3)",
        stroke: selectedTheme.containerBorder,
        strokeWidth: 2,
        selectable: true,
      });
    } else {
      obj = new fabric.Line(
        [Math.round(width * 0.2), Math.round(height * 0.5), Math.round(width * 0.8), Math.round(height * 0.5)],
        {
          stroke: selectedTheme.containerBorder,
          strokeWidth: 3,
          selectable: true,
        }
      );
    }
    canvas.add(obj);
    canvas.setActiveObject(obj);
    canvas.renderAll();
    saveStateToHistory();
  };

  const handleDuplicateSelected = () => {
    const canvas = fabricCanvasRef.current;
    if (!canvas) return;
    const activeObjs = canvas.getActiveObjects();
    if (!activeObjs.length) return;
    activeObjs.forEach((obj) => {
      obj.clone((cloned: fabric.Object) => {
        cloned.set({ left: (cloned.left || 0) + 20, top: (cloned.top || 0) + 20 });
        canvas.add(cloned);
        canvas.setActiveObject(cloned);
      });
    });
    canvas.renderAll();
    saveStateToHistory();
    toast.success("Duplicated!");
  };

  const handleToggleLock = () => {
    const canvas = fabricCanvasRef.current;
    if (!canvas) return;
    const obj = canvas.getActiveObject() as any;
    if (!obj) return;
    const newLocked = !isLocked;
    obj.set({
      lockMovementX: newLocked,
      lockMovementY: newLocked,
      lockScalingX: newLocked,
      lockScalingY: newLocked,
      lockRotation: newLocked,
      hasControls: !newLocked,
      selectable: true,
    });
    setIsLocked(newLocked);
    canvas.renderAll();
    toast.success(newLocked ? "Object locked" : "Object unlocked");
  };

  const handleToggleBold = () => {
    const canvas = fabricCanvasRef.current;
    if (!canvas) return;
    const obj = canvas.getActiveObject() as any;
    if (!obj || obj.fontSize === undefined) return;
    const current = obj.fontWeight;
    obj.set("fontWeight", current === "bold" || current === "700" ? "normal" : "bold");
    canvas.renderAll();
    saveStateToHistory();
  };

  const handleToggleItalic = () => {
    const canvas = fabricCanvasRef.current;
    if (!canvas) return;
    const obj = canvas.getActiveObject() as any;
    if (!obj || obj.fontSize === undefined) return;
    obj.set("fontStyle", obj.fontStyle === "italic" ? "normal" : "italic");
    canvas.renderAll();
    saveStateToHistory();
  };

  const handleToggleUnderline = () => {
    const canvas = fabricCanvasRef.current;
    if (!canvas) return;
    const obj = canvas.getActiveObject() as any;
    if (!obj || obj.fontSize === undefined) return;
    obj.set("underline", !obj.underline);
    canvas.renderAll();
    saveStateToHistory();
  };

  const handleTextAlign = (align: string) => {
    const canvas = fabricCanvasRef.current;
    if (!canvas) return;
    const obj = canvas.getActiveObject() as any;
    if (!obj || obj.fontSize === undefined) return;
    obj.set("textAlign", align);
    setSelectedAlign(align);
    canvas.renderAll();
    saveStateToHistory();
  };

  const handleFontFamily = (family: string) => {
    const canvas = fabricCanvasRef.current;
    if (!canvas) return;
    const obj = canvas.getActiveObject() as any;
    if (!obj || obj.fontSize === undefined) return;
    obj.set("fontFamily", family);
    setSelectedFontFamily(family);
    canvas.renderAll();
    saveStateToHistory();
  };

  const handleOpacityChange = (val: number) => {
    const canvas = fabricCanvasRef.current;
    if (!canvas) return;
    const obj = canvas.getActiveObject() as any;
    if (!obj) return;
    obj.set("opacity", val);
    setSelectedOpacity(val);
    canvas.renderAll();
    saveStateToHistory();
  };

  const handleLineHeightChange = (delta: number) => {
    const canvas = fabricCanvasRef.current;
    if (!canvas) return;
    const obj = canvas.getActiveObject() as any;
    if (!obj || obj.lineHeight === undefined) return;
    const newLH = Math.max(0.8, Math.min(3.0, (obj.lineHeight || 1.3) + delta));
    obj.set("lineHeight", Math.round(newLH * 10) / 10);
    canvas.renderAll();
    saveStateToHistory();
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
      a.download = `aiflick-${platform || "post"}-${aspectRatioKey.replace(":", "-")}.png`;
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
      {/* ── Toolbar Row 1: Ratio + Themes + Glass Card + Background ── */}
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

      {/* ── Toolbar Row 2: Edit Tools ── */}
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border/70 bg-surface-raised/70 px-3 py-2">
        {/* Undo / Redo */}
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

        {/* Add: Text / Shapes */}
        <button
          type="button"
          onClick={handleAddText}
          className="flex items-center gap-1 rounded-lg border border-border/70 bg-secondary/60 px-2.5 py-1.5 text-xs font-medium text-foreground hover:bg-secondary transition-colors"
        >
          <Type className="size-3.5" /> Text
        </button>

        {/* Shape group */}
        <div className="flex items-center gap-0.5 border border-border/60 rounded-lg overflow-hidden">
          <button
            type="button"
            onClick={() => handleAddShape("rect")}
            title="Add Rectangle"
            className="flex items-center justify-center px-2 py-1.5 text-xs text-muted-foreground hover:bg-secondary hover:text-foreground"
          >
            <Square className="size-3" />
          </button>
          <button
            type="button"
            onClick={() => handleAddShape("circle")}
            title="Add Circle"
            className="flex items-center justify-center px-2 py-1.5 text-xs text-muted-foreground hover:bg-secondary hover:text-foreground"
          >
            <Circle className="size-3" />
          </button>
          <button
            type="button"
            onClick={() => handleAddShape("line")}
            title="Add Line"
            className="flex items-center justify-center px-2 py-1.5 text-xs text-muted-foreground hover:bg-secondary hover:text-foreground"
          >
            <Minus className="size-3" />
          </button>
        </div>

        {/* Duplicate */}
        <button
          type="button"
          onClick={handleDuplicateSelected}
          disabled={!hasSelection}
          title="Duplicate (Ctrl+D)"
          className="flex items-center gap-1 rounded-lg border border-border/70 bg-secondary/60 px-2.5 py-1.5 text-xs font-medium text-foreground hover:bg-secondary transition-colors disabled:opacity-30"
        >
          <CopyIcon className="size-3.5" /> Dup.
        </button>

        {/* Delete */}
        <button
          type="button"
          onClick={handleDeleteSelected}
          disabled={!hasSelection}
          className="flex items-center gap-1 rounded-lg border border-destructive/40 bg-destructive/10 px-2.5 py-1.5 text-xs font-medium text-destructive hover:bg-destructive/20 transition-colors disabled:opacity-30"
          title="Delete selected (Delete / Backspace)"
        >
          <Trash2 className="size-3.5" /> Del.
        </button>

        {/* Lock / Unlock */}
        <button
          type="button"
          onClick={handleToggleLock}
          disabled={!hasSelection}
          title={isLocked ? "Unlock object" : "Lock object"}
          className={`flex items-center gap-1 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-all disabled:opacity-30 ${
            isLocked
              ? "border-amber-500/40 bg-amber-500/10 text-amber-400"
              : "border-border/60 bg-secondary/40 text-muted-foreground hover:text-foreground"
          }`}
        >
          {isLocked ? <Lock className="size-3.5" /> : <Unlock className="size-3.5" />}
        </button>

        {/* Divider */}
        <div className="h-6 w-px bg-border/60" />

        {/* Text formatting: Bold, Italic, Underline */}
        <div className="flex items-center gap-0.5">
          <button
            type="button"
            onClick={handleToggleBold}
            disabled={!hasSelection || selectedFontSize === null}
            title="Bold"
            className="flex size-7 items-center justify-center rounded text-xs font-bold text-muted-foreground hover:bg-secondary hover:text-foreground disabled:opacity-30"
          >
            <Bold className="size-3.5" />
          </button>
          <button
            type="button"
            onClick={handleToggleItalic}
            disabled={!hasSelection || selectedFontSize === null}
            title="Italic"
            className="flex size-7 items-center justify-center rounded text-xs text-muted-foreground hover:bg-secondary hover:text-foreground disabled:opacity-30"
          >
            <Italic className="size-3.5" />
          </button>
          <button
            type="button"
            onClick={handleToggleUnderline}
            disabled={!hasSelection || selectedFontSize === null}
            title="Underline"
            className="flex size-7 items-center justify-center rounded text-xs text-muted-foreground hover:bg-secondary hover:text-foreground disabled:opacity-30"
          >
            <Underline className="size-3.5" />
          </button>
        </div>

        {/* Alignment */}
        <div className="flex items-center gap-0.5">
          {[
            { align: "left", Icon: AlignLeft },
            { align: "center", Icon: AlignCenter },
            { align: "right", Icon: AlignRight },
          ].map(({ align, Icon }) => (
            <button
              key={align}
              type="button"
              onClick={() => handleTextAlign(align)}
              disabled={!hasSelection || selectedFontSize === null}
              title={`Align ${align}`}
              className={`flex size-7 items-center justify-center rounded text-xs transition-all disabled:opacity-30 ${
                selectedAlign === align
                  ? "bg-primary/20 text-primary"
                  : "text-muted-foreground hover:bg-secondary hover:text-foreground"
              }`}
            >
              <Icon className="size-3.5" />
            </button>
          ))}
        </div>

        {/* Divider */}
        <div className="h-6 w-px bg-border/60" />

        {/* Font Size */}
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

        {/* Line Height */}
        <div className="flex items-center gap-1 rounded-lg border border-border/60 bg-secondary/40 px-2 py-1">
          <span className="text-[10px] text-muted-foreground font-mono">LH</span>
          <button
            type="button"
            onClick={() => handleLineHeightChange(-0.1)}
            disabled={!hasSelection || selectedFontSize === null}
            className="size-5 flex items-center justify-center rounded text-xs font-bold text-muted-foreground hover:text-foreground disabled:opacity-30"
          >
            –
          </button>
          <button
            type="button"
            onClick={() => handleLineHeightChange(0.1)}
            disabled={!hasSelection || selectedFontSize === null}
            className="size-5 flex items-center justify-center rounded text-xs font-bold text-muted-foreground hover:text-foreground disabled:opacity-30"
          >
            +
          </button>
        </div>

        {/* Color */}
        <div className="flex items-center gap-1.5 pl-1">
          <span className="text-xs text-muted-foreground">Color:</span>
          <input
            type="color"
            value={selectedColor}
            onChange={(e) => handleTextColorChange(e.target.value)}
            disabled={!hasSelection}
            className="size-6 rounded cursor-pointer border border-border/60 bg-transparent disabled:opacity-30"
            title="Text / fill color"
          />
        </div>

        {/* Opacity */}
        <div className="flex items-center gap-1.5 pl-1">
          <span className="text-[10px] text-muted-foreground font-mono">Opacity:</span>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={selectedOpacity}
            onChange={(e) => handleOpacityChange(parseFloat(e.target.value))}
            disabled={!hasSelection}
            className="w-16 accent-primary disabled:opacity-30"
            title="Object opacity"
          />
          <span className="text-[10px] font-mono text-muted-foreground w-7">
            {Math.round(selectedOpacity * 100)}%
          </span>
        </div>

        {/* Font Family Picker */}
        <div className="flex items-center gap-1">
          <span className="text-[10px] text-muted-foreground font-mono">Font:</span>
          <select
            value={selectedFontFamily}
            onChange={(e) => handleFontFamily(e.target.value)}
            disabled={!hasSelection || selectedFontSize === null}
            className="rounded-lg border border-border/60 bg-secondary/60 px-1.5 py-1 text-[11px] text-foreground disabled:opacity-30"
            title="Font family"
          >
            {FONT_FAMILIES.map((f, i) => (
              <option key={f} value={f}>
                {FONT_FAMILY_LABELS[i]}
              </option>
            ))}
          </select>
        </div>

        {/* Layer Order */}
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

        {/* Watermark toggle */}
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
          <Sparkles className="size-3" /> WM: {showWatermark ? "ON" : "OFF"}
        </button>

        <div className="flex-1" />

        {/* Zoom Controls */}
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => {
              const prev = [...ZOOM_LEVELS].reverse().find((z) => z < zoom) ?? ZOOM_LEVELS[0]!;
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
              const next = ZOOM_LEVELS.find((z) => z > zoom) ?? ZOOM_LEVELS[ZOOM_LEVELS.length - 1]!;
              setZoom(next);
            }}
            className="flex size-7 items-center justify-center rounded border border-border/60 bg-secondary/40 text-muted-foreground hover:text-foreground"
            title="Zoom In"
          >
            <ZoomIn className="size-3.5" />
          </button>
        </div>
      </div>

      {/* ── Canvas Area ── */}
      <div
        ref={containerRef}
        className="relative flex min-h-[580px] items-center justify-center overflow-auto rounded-2xl border border-border/70 bg-[#070B1A]/80 p-6 shadow-inner"
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
          💡 Click to select • Click again or double-click to edit text • Hold Space + drag to pan • Ctrl+Z Undo • Ctrl+D Duplicate
        </div>
      </div>

      {/* ── Bottom Action Bar ── */}
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
