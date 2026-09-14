/**
 * frontend/src/components/aiflick/social-post-canvas.tsx
 *
 * Production-Grade Interactive Social Post Studio built with Fabric.js.
 *
 * Architecture & Features:
 *  1. Vertical Left Toolbar Dock: Sleek, compact rail (~56px) on the left side of the canvas.
 *  2. True Bidirectional Live Text Sync: Listens to Fabric's `text:changed` on the canvas so typing
 *     directly on the canvas updates the right menu and parent post state on every keystroke.
 *  3. In-Place Non-Destructive Style Updates: Toggling watermark, card opacity, solid color,
 *     or preset themes updates existing Fabric objects in-place with ZERO canvas destruction or edit resets.
 *  4. Instant Text Editing & Deletion Protection: Clicking any textbox enters edit mode immediately.
 *     Backspace/Delete inside textboxes edits characters instead of deleting the object.
 *  5. Modular Components: CanvasLeftToolbar, CanvasAssetDrawer, CanvasBottomBar.
 */

import React, { useEffect, useRef, useState, useCallback } from "react";
import { fabric } from "fabric";
import { toast } from "sonner";
import { getImageUrl } from "@/api";
import {
  ASPECT_RATIOS,
  PRESET_THEMES,
  type PostTheme,
  computeAutoLayout,
  generatePresetBackgroundDataUrl,
  shouldInjectAssetForPost,
} from "./canvas-templates";
import type { InjectedAssetSpec } from "@/api/types";
import { CanvasLeftToolbar } from "./canvas/canvas-left-toolbar";
import { CanvasAssetDrawer } from "./canvas/canvas-asset-drawer";
import { CanvasBottomBar } from "./canvas/canvas-bottom-bar";

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
  injectedAsset?: InjectedAssetSpec | null | undefined;
  postNumber?: number | undefined;
  totalPosts?: number | undefined;
  onInjectedAssetChange?: ((asset: InjectedAssetSpec | null) => void) | undefined;
}

const ZOOM_LEVELS = [0.35, 0.5, 0.65, 0.75, 1.0, 1.25];
const FONT_FAMILIES = [
  "Inter, -apple-system, sans-serif",
  "Georgia, serif",
  "Courier New, monospace",
  "Arial, sans-serif",
  "Trebuchet MS, sans-serif",
];

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
  injectedAsset,
  postNumber = 1,
  totalPosts = 5,
  onInjectedAssetChange,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const fabricCanvasRef = useRef<fabric.Canvas | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Injected asset state for live selective branding
  const [activeAsset, setActiveAsset] = useState<InjectedAssetSpec | null>(injectedAsset || null);
  useEffect(() => {
    setActiveAsset(injectedAsset || null);
  }, [injectedAsset]);
  const [showAssetModal, setShowAssetModal] = useState(false);

  // ── Stable callback refs: Fabric listeners never capture stale closures ──
  const onTitleChangeRef = useRef(onTitleChange);
  const onHookChangeRef = useRef(onHookChange);
  const onSummaryChangeRef = useRef(onSummaryChange);
  useEffect(() => { onTitleChangeRef.current = onTitleChange; }, [onTitleChange]);
  useEffect(() => { onHookChangeRef.current = onHookChange; }, [onHookChange]);
  useEffect(() => { onSummaryChangeRef.current = onSummaryChange; }, [onSummaryChange]);

  // ── Stable content refs: always hold the latest text values ──
  const titleRef = useRef(title);
  const hookRef = useRef(hook);
  const bulletPointsRef = useRef<string[]>([]);
  useEffect(() => { titleRef.current = title; }, [title]);
  useEffect(() => { hookRef.current = hook; }, [hook]);

  // Refs to named canvas objects for lightweight in-place updates
  const titleObjRef = useRef<fabric.Textbox | null>(null);
  const hookObjRef = useRef<fabric.Textbox | null>(null);
  const bulletObjRefs = useRef<fabric.Textbox[]>([]);
  const containerObjRef = useRef<fabric.Rect | null>(null);
  const watermarkObjRef = useRef<fabric.Textbox | null>(null);

  // Generation token: prevents stale async image loads
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
  const [zoom, setZoom] = useState(0.65);
  const [bgLoading, setBgLoading] = useState(false);
  const [hasSelection, setHasSelection] = useState(false);
  const [selectedFontSize, setSelectedFontSize] = useState<number | null>(null);
  const [selectedColor, setSelectedColor] = useState<string>("#FFFFFF");
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);
  const [isLocked, setIsLocked] = useState<boolean>(false);
  const [selectedAlign, setSelectedAlign] = useState<string>("center");

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
  useEffect(() => { bulletPointsRef.current = bulletPoints; }, [bulletPoints]);

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

  // Compute container fill based on opacity and theme
  const getContainerFill = useCallback((op: string, theme: PostTheme, bg: string) => {
    if (bg === "ai" || bg === "custom") {
      if (op === "subtle") return "rgba(10, 15, 30, 0.40)";
      if (op === "medium") return "rgba(10, 15, 30, 0.70)";
      if (op === "none") return "rgba(0, 0, 0, 0.05)";
      return theme.containerBg;
    }
    if (op === "subtle") return "rgba(10, 15, 30, 0.45)";
    if (op === "none") return "rgba(0, 0, 0, 0.05)";
    if (op === "medium") return "rgba(10, 15, 30, 0.70)";
    return theme.containerBg;
  }, []);

  /**
   * Complete canvas composition builder.
   * Called on initial mount and when layout dimensions (aspect ratio) change.
   */
  const renderCanvasComposition = useCallback(async () => {
    const canvas = fabricCanvasRef.current;
    if (!canvas) return;

    renderGenerationRef.current += 1;
    const thisGeneration = renderGenerationRef.current;

    titleObjRef.current = null;
    hookObjRef.current = null;
    bulletObjRefs.current = [];
    containerObjRef.current = null;
    watermarkObjRef.current = null;

    const { width, height } = currentDimensions;
    canvas.setWidth(width);
    canvas.setHeight(height);

    canvas.getObjects().forEach((obj) => canvas.remove(obj));
    canvas.clear();
    canvas.discardActiveObject();

    const shouldInject = shouldInjectAssetForPost(activeAsset, postNumber ?? 1, totalPosts ?? 5);
    const hasHeroInset = Boolean(shouldInject && activeAsset?.role === "hero_inset");
    const layout = computeAutoLayout(width, height, titleRef.current || "", bulletPointsRef.current.length, hasHeroInset);

    const buildForegroundLayers = () => {
      if (renderGenerationRef.current !== thisGeneration) return;
      if (!fabricCanvasRef.current) return;

      const containerFill = getContainerFill(cardOpacity, selectedTheme, bgSource);

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
      containerObjRef.current = container;
      canvas.add(container);

      const innerLeft = layout.horizontalMargin + 48;
      const innerWidth = layout.containerWidth - 96;
      let currentY = layout.topMargin + 48;

      // Platform badge
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

      // Logo injection (top right)
      if (shouldInject && activeAsset?.url && (activeAsset.role === "logo" || activeAsset.role === "custom_sticker")) {
        fabric.Image.fromURL(
          activeAsset.url,
          (img) => {
            if (renderGenerationRef.current !== thisGeneration) return;
            if (!img || !img.width || !img.height) return;
            const maxH = 38;
            const scale = maxH / img.height;
            const logoW = img.width * scale;
            img.set({
              scaleX: scale,
              scaleY: scale,
              left: innerLeft + innerWidth - logoW,
              top: layout.topMargin + 46,
              opacity: activeAsset.opacity ?? 0.95,
              selectable: true,
              hoverCursor: "move",
            });
            canvas.add(img);
            canvas.requestRenderAll();
          },
          { crossOrigin: "anonymous" }
        );
      }

      currentY += 56;

      // Title Textbox
      const cleanCanvasTitle = (titleRef.current || "").replace(/^#+\s*/gm, "").replace(/\*\*(.*?)\*\*/g, "$1");
      const titleFab = new fabric.Textbox(cleanCanvasTitle, {
        left: innerLeft,
        top: currentY,
        width: innerWidth,
        fontSize: layout.titleFontSize,
        fontWeight: "bold",
        fontFamily: "Inter, -apple-system, sans-serif",
        fill: selectedTheme.titleColor,
        lineHeight: 1.25,
        textAlign: selectedAlign,
        editable: true,
        selectable: true,
        hoverCursor: "text",
      });
      titleObjRef.current = titleFab;
      canvas.add(titleFab);
      currentY += (titleFab.height || 60) + 16;

      // Hook Textbox
      if (hookRef.current) {
        const cleanHook = (hookRef.current || "").replace(/^#+\s*/gm, "").replace(/\*\*(.*?)\*\*/g, "$1");
        const hookFab = new fabric.Textbox(`⚡ ${cleanHook}`, {
          left: innerLeft,
          top: currentY,
          width: innerWidth,
          fontSize: 20,
          fontWeight: "500",
          fontFamily: "Inter, -apple-system, sans-serif",
          fill: selectedTheme.hookColor,
          lineHeight: 1.35,
          textAlign: selectedAlign,
          editable: true,
          selectable: true,
          hoverCursor: "text",
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

      // Hero Inset injection
      if (shouldInject && activeAsset?.url && activeAsset.role === "hero_inset") {
        fabric.Image.fromURL(
          activeAsset.url,
          (img) => {
            if (renderGenerationRef.current !== thisGeneration) return;
            if (!img || !img.width || !img.height) return;
            const maxW = innerWidth - 32;
            const maxH = 220;
            const scale = Math.min(maxW / img.width, maxH / img.height);
            img.set({
              scaleX: scale,
              scaleY: scale,
              originX: "center",
              originY: "top",
              left: innerLeft + innerWidth / 2,
              top: currentY,
              selectable: true,
              hoverCursor: "move",
              shadow: new fabric.Shadow({
                color: "rgba(0,0,0,0.55)",
                blur: 24,
                offsetX: 0,
                offsetY: 10,
              }),
            });
            canvas.add(img);
            canvas.requestRenderAll();
          },
          { crossOrigin: "anonymous" }
        );
        currentY += 240;
      }

      // Bullet points
      const itemsToRender =
        bulletPointsRef.current.length > 0
          ? bulletPointsRef.current.slice(0, 7)
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

      // Watermark footer
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
          visible: showWatermark,
          editable: true,
          selectable: true,
          hoverCursor: "text",
        }
      );
      watermarkObjRef.current = footerTag;
      canvas.add(footerTag);

      // Avatar injection
      if (shouldInject && activeAsset?.url && activeAsset.role === "avatar") {
        fabric.Image.fromURL(
          activeAsset.url,
          (img) => {
            if (renderGenerationRef.current !== thisGeneration) return;
            if (!img || !img.width || !img.height) return;
            const avatarSize = 38;
            const scale = avatarSize / Math.min(img.width, img.height);
            const avatarLeft = innerLeft;
            const avatarTop = footerY - 9;

            img.set({
              scaleX: scale,
              scaleY: scale,
              originX: "center",
              originY: "center",
              left: avatarLeft + avatarSize / 2,
              top: avatarTop + avatarSize / 2,
              clipPath: new fabric.Circle({
                radius: (avatarSize / 2) / scale,
                originX: "center",
                originY: "center",
              }),
              selectable: true,
              hoverCursor: "move",
            });

            const borderRing = new fabric.Circle({
              radius: avatarSize / 2 + 1.5,
              originX: "center",
              originY: "center",
              left: avatarLeft + avatarSize / 2,
              top: avatarTop + avatarSize / 2,
              fill: "transparent",
              stroke: activeAsset.borderColor || selectedTheme.accentColor,
              strokeWidth: activeAsset.borderWidth || 2,
              selectable: false,
              evented: false,
            });

            canvas.add(borderRing);
            canvas.add(img);

            footerTag.set({
              left: avatarLeft + avatarSize + 12,
              top: avatarTop + 10,
            });
            canvas.requestRenderAll();
          },
          { crossOrigin: "anonymous" }
        );
      }

      canvas.renderAll();
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
    selectedAlign,
    activeAsset,
    postNumber,
    totalPosts,
    saveStateToHistory,
    loadImageAsDataUrl,
    getContainerFill,
  ]);

  // ── MOUNT FABRIC CANVAS STRICTLY ONCE ──
  useEffect(() => {
    if (!canvasRef.current) return;

    // Direct Fabric's hiddenTextarea to append inside containerRef (inside DialogContent)
    if (containerRef.current) {
      (fabric.IText.prototype as any).hiddenTextareaContainer = containerRef.current;
      (fabric.Textbox.prototype as any).hiddenTextareaContainer = containerRef.current;
    }

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
        if (obj.fill) setSelectedColor((obj.fill as string) || "#FFFFFF");
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

    // ── LIVE BIDIRECTIONAL TEXT SYNC: Every keystroke on canvas updates right menu in real-time ──
    const syncCanvasTextToParent = (target: any) => {
      if (!target) return;

      if (target === titleObjRef.current) {
        const newTitle = (target as fabric.Textbox).text || "";
        titleRef.current = newTitle;
        if (onTitleChangeRef.current) {
          onTitleChangeRef.current(newTitle);
        }
      } else if (target === hookObjRef.current) {
        const raw = (target as fabric.Textbox).text || "";
        const newHook = raw.replace(/^⚡\s*/, "");
        hookRef.current = newHook;
        if (onHookChangeRef.current) {
          onHookChangeRef.current(newHook);
        }
      } else if (bulletObjRefs.current.includes(target as fabric.Textbox)) {
        const updatedBullets = bulletObjRefs.current.map((b) => (b as any).text || "");
        bulletPointsRef.current = updatedBullets;
        if (onSummaryChangeRef.current) {
          onSummaryChangeRef.current(updatedBullets);
        }
      }
      saveStateToHistory();
    };

    fc.on("text:changed", (opt: any) => {
      syncCanvasTextToParent(opt.target);
    });

    // ── Click to enter text editing immediately ──
    fc.on("mouse:down", (opt) => {
      if (isSpaceDownRef.current) {
        isPanningRef.current = true;
        panStartRef.current = { x: opt.e.clientX, y: opt.e.clientY };
        fc.defaultCursor = "grabbing";
        fc.hoverCursor = "grabbing";
        opt.e.preventDefault();
        return;
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

    fc.on("mouse:up", (opt) => {
      if (isPanningRef.current) {
        isPanningRef.current = false;
        panStartRef.current = null;
        fc.defaultCursor = "default";
        fc.hoverCursor = "move";
        return;
      }
      const target = opt.target;
      if (
        target &&
        target instanceof fabric.Textbox &&
        (target as any).editable
      ) {
        if (!(target as any).isEditing) {
          target.enterEditing(opt.e);
          if ((target as any).hiddenTextarea) {
            (target as any).hiddenTextarea.focus();
          }
          fc.renderAll();
        }
      }
    });

    fc.on("mouse:dblclick", (opt) => {
      const target = opt.target;
      if (target && target instanceof fabric.Textbox && (target as any).editable) {
        target.enterEditing(opt.e);
        target.selectAll();
        if ((target as any).hiddenTextarea) {
          (target as any).hiddenTextarea.focus();
        }
        fc.renderAll();
      }
    });

    fc.on("object:modified", saveStateToHistory);

    const handleKeyDown = (e: KeyboardEvent) => {
      const active = fc.getActiveObject() as any;
      const isEditingText = active && active.isEditing;

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

      // Duplicate
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

      // Keystroke in active textbox
      if (active && active instanceof fabric.Textbox && active.editable && !isEditingText) {
        if (e.key === "Backspace" || e.key === "Delete") {
          e.preventDefault();
          active.enterEditing();
          const cur = active.text || "";
          if (cur.length > 0) {
            const nextText = cur.slice(0, -1);
            active.set("text", nextText);
            if (active.hiddenTextarea) {
              active.hiddenTextarea.value = nextText;
              active.hiddenTextarea.focus();
            }
            fc.renderAll();
            active.fire("changed");
            syncCanvasTextToParent(active);
          }
          return;
        }

        if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
          e.preventDefault();
          active.enterEditing();
          const nextText = (active.text || "") + e.key;
          active.set("text", nextText);
          if (active.hiddenTextarea) {
            active.hiddenTextarea.value = nextText;
            active.hiddenTextarea.focus();
          }
          fc.renderAll();
          active.fire("changed");
          syncCanvasTextToParent(active);
          return;
        }
      }

      // Only delete non-textbox objects (shapes, images)
      if ((e.key === "Delete" || e.key === "Backspace") && !isEditingText) {
        const activeObjs = fc.getActiveObjects();
        const nonTextObjs = activeObjs.filter((obj) => !(obj instanceof fabric.Textbox));
        if (nonTextObjs.length > 0) {
          e.preventDefault();
          fc.discardActiveObject();
          nonTextObjs.forEach((obj) => fc.remove(obj));
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

    // Initial render
    renderCanvasComposition();

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
      fc.dispose();
      fabricCanvasRef.current = null;
    };
  }, []); // Run ONCE on mount!

  // Re-render composition when aspect ratio or active injected asset changes
  useEffect(() => {
    if (fabricCanvasRef.current) {
      renderCanvasComposition();
    }
  }, [aspectRatioKey, activeAsset]);

  // ── IN-PLACE NON-DESTRUCTIVE STYLE UPDATES (Never destroys user edits!) ──

  // 1. Watermark Toggle
  useEffect(() => {
    const wm = watermarkObjRef.current;
    const canvas = fabricCanvasRef.current;
    if (!wm || !canvas) return;
    wm.set("visible", showWatermark);
    canvas.renderAll();
  }, [showWatermark]);

  // 2. Card Opacity
  useEffect(() => {
    const container = containerObjRef.current;
    const canvas = fabricCanvasRef.current;
    if (!container || !canvas) return;
    const fill = getContainerFill(cardOpacity, selectedTheme, bgSource);
    container.set("fill", fill);
    canvas.renderAll();
  }, [cardOpacity, selectedTheme, bgSource, getContainerFill]);

  // 3. Solid Background Color
  useEffect(() => {
    const canvas = fabricCanvasRef.current;
    if (!canvas || bgSource !== "solid") return;
    canvas.setBackgroundColor(solidColor, () => canvas.renderAll());
  }, [solidColor, bgSource]);

  // 4. In-Place Title update from side panel
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

  // 5. In-Place Hook update from side panel
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

  // 6. In-Place Bullet points update from side panel
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

  // ── Action Handlers ──

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
    toast.success("New text added");
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

  const handleTextAlign = (align: string) => {
    const canvas = fabricCanvasRef.current;
    if (!canvas) return;
    const obj = canvas.getActiveObject() as any;
    if (obj && obj.fontSize !== undefined) {
      obj.set("textAlign", align);
    } else {
      const allText = canvas.getObjects().filter((o) => o instanceof fabric.Textbox);
      allText.forEach((t) => (t as fabric.Textbox).set("textAlign", align));
    }
    setSelectedAlign(align);
    canvas.renderAll();
    saveStateToHistory();
    toast.success(`Text alignment: ${align}`);
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
        toast.success("Custom background applied");
      }
    };
    reader.readAsDataURL(file);
  };

  const handleDownload = () => {
    const canvas = fabricCanvasRef.current;
    if (!canvas) return;

    try {
      const dataUrl = canvas.toDataURL({
        format: "png",
        quality: 1,
        multiplier: 2,
      });

      const link = document.createElement("a");
      const safeTitle = (titleRef.current || "post").slice(0, 30).replace(/[^a-zA-Z0-9_-]/g, "_");
      link.download = `aiflick_${safeTitle}_${aspectRatioKey.replace(":", "-")}.png`;
      link.href = dataUrl;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      toast.success("Post image downloaded!");
    } catch {
      toast.error("Failed to export image");
    }
  };

  const handleCopyToClipboard = async () => {
    const canvas = fabricCanvasRef.current;
    if (!canvas) return;

    try {
      const dataUrl = canvas.toDataURL({ format: "png", quality: 1, multiplier: 2 });
      const res = await fetch(dataUrl);
      const blob = await res.blob();
      await navigator.clipboard.write([
        new ClipboardItem({ "image/png": blob }),
      ]);
      setCopied(true);
      toast.success("Graphic copied to clipboard!");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("Clipboard copy not supported in this browser");
    }
  };

  const canvasDisplayWidth = currentDimensions.width * zoom;
  const canvasDisplayHeight = currentDimensions.height * zoom;

  return (
    <div className="flex flex-col gap-3 w-full">
      {/* Hidden File Input for Custom Background */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={handleCustomUpload}
      />

      {/* Branded Asset / Graphic Injection Drawer */}
      <CanvasAssetDrawer
        open={showAssetModal}
        onClose={() => setShowAssetModal(false)}
        activeAsset={activeAsset}
        setActiveAsset={setActiveAsset}
        onInjectedAssetChange={onInjectedAssetChange}
        postNumber={postNumber}
        totalPosts={totalPosts}
      />

      {/* Main Studio Area: Left Vertical Toolbar + Center Canvas Preview */}
      <div className="flex flex-row gap-3 items-start w-full">
        {/* ── Left-Side Vertical Editing Dock ── */}
        <CanvasLeftToolbar
          aspectRatioKey={aspectRatioKey}
          setAspectRatioKey={setAspectRatioKey}
          selectedTheme={selectedTheme}
          setSelectedTheme={setSelectedTheme}
          cardOpacity={cardOpacity}
          setCardOpacity={setCardOpacity}
          bgSource={bgSource}
          setBgSource={setBgSource}
          solidColor={solidColor}
          setSolidColor={setSolidColor}
          backgroundImageUrl={backgroundImageUrl}
          activeAsset={activeAsset}
          onOpenAssetDrawer={() => setShowAssetModal((v) => !v)}
          onUploadCustomBg={() => fileInputRef.current?.click()}
          onAddText={handleAddText}
          onAddShape={handleAddShape}
          onDuplicate={handleDuplicateSelected}
          onDelete={handleDeleteSelected}
          onToggleLock={handleToggleLock}
          isLocked={isLocked}
          hasSelection={hasSelection}
          onToggleBold={handleToggleBold}
          onToggleItalic={handleToggleItalic}
          selectedAlign={selectedAlign}
          onTextAlign={handleTextAlign}
          selectedFontSize={selectedFontSize}
          onFontSizeChange={handleFontSizeChange}
          selectedColor={selectedColor}
          onTextColorChange={handleTextColorChange}
          canUndo={canUndo}
          canRedo={canRedo}
          onUndo={undo}
          onRedo={redo}
          showWatermark={showWatermark}
          onToggleWatermark={() => setShowWatermark((v) => !v)}
        />

        {/* ── Center Canvas Viewport & Bottom Action Bar ── */}
        <div className="flex-1 flex flex-col items-center min-w-0 w-full gap-3">
          <div
            ref={containerRef}
            className="relative flex min-h-[560px] w-full items-center justify-center overflow-auto rounded-2xl border border-border/70 bg-[#070B1A]/80 p-6 shadow-inner"
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
                  <span className="text-[11px] font-medium text-white/80">
                    Loading AI background…
                  </span>
                </div>
              )}
            </div>

            <div className="pointer-events-none absolute bottom-3 left-4 rounded-md bg-black/75 px-3 py-1 text-[10px] font-medium text-slate-400 backdrop-blur-md">
              Click text to edit • Space + drag to pan • Ctrl+Z Undo
            </div>
          </div>

          {/* Bottom Action Bar */}
          <CanvasBottomBar
            zoom={zoom}
            setZoom={setZoom}
            zoomLevels={ZOOM_LEVELS}
            onRegenerateBg={onRegenerateBg}
            isGeneratingBg={isGeneratingBg}
            onResetLayout={renderCanvasComposition}
            onCopyToClipboard={handleCopyToClipboard}
            copied={copied}
            onDownload={handleDownload}
          />
        </div>
      </div>
    </div>
  );
};
