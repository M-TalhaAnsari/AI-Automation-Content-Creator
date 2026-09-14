/**
 * frontend/src/components/aiflick/canvas/canvas-left-toolbar.tsx
 *
 * Sleek, compact vertical editing dock positioned on the left side of the canvas.
 * Provides fast 1-click access to tools and flyout menus for ratio, themes, card glass,
 * background sources, shapes, typography formatting, and watermark.
 */

import React, { useState, useRef, useEffect } from "react";
import {
  Smartphone,
  Square,
  MonitorPlay,
  Flame,
  Palette,
  Layers,
  Sparkles,
  Upload,
  Paintbrush,
  ImageIcon,
  Type,
  Circle,
  Minus,
  Bold,
  Italic,
  AlignLeft,
  AlignCenter,
  AlignRight,
  Copy as CopyIcon,
  Trash2,
  Undo2,
  Redo2,
  PanelLeftOpen,
  PanelLeftClose,
  ChevronLeft,
} from "lucide-react";
import {
  ASPECT_RATIOS,
  PRESET_THEMES,
  type PostTheme,
} from "../canvas-templates";
import type { InjectedAssetSpec } from "@/api/types";

export interface CanvasLeftToolbarProps {
  aspectRatioKey: string;
  setAspectRatioKey: (key: string) => void;
  selectedTheme: PostTheme;
  setSelectedTheme: (theme: PostTheme) => void;
  cardOpacity: "subtle" | "medium" | "solid" | "none";
  setCardOpacity: (op: "subtle" | "medium" | "solid" | "none") => void;
  bgSource: "ai" | "custom" | "preset" | "solid";
  setBgSource: (src: "ai" | "custom" | "preset" | "solid") => void;
  solidColor: string;
  setSolidColor: (c: string) => void;
  backgroundImageUrl?: string | null | undefined;
  activeAsset: InjectedAssetSpec | null;
  onOpenAssetDrawer: () => void;
  onUploadCustomBg: () => void;
  onAddText: () => void;
  onAddShape: (shape: "rect" | "circle" | "line") => void;
  onDuplicate: () => void;
  onDelete: () => void;
  onToggleLock: () => void;
  isLocked: boolean;
  hasSelection: boolean;
  onToggleBold: () => void;
  onToggleItalic: () => void;
  selectedAlign: string;
  onTextAlign: (align: string) => void;
  selectedFontSize: number | null;
  onFontSizeChange: (delta: number) => void;
  selectedColor: string;
  onTextColorChange: (c: string) => void;
  canUndo: boolean;
  canRedo: boolean;
  onUndo: () => void;
  onRedo: () => void;
  showWatermark: boolean;
  onToggleWatermark: () => void;
}

type ActiveFlyout = "ratio" | "theme" | "card" | "bg" | "shape" | "font" | null;

export const CanvasLeftToolbar: React.FC<CanvasLeftToolbarProps> = ({
  aspectRatioKey,
  setAspectRatioKey,
  selectedTheme,
  setSelectedTheme,
  cardOpacity,
  setCardOpacity,
  bgSource,
  setBgSource,
  solidColor,
  setSolidColor,
  backgroundImageUrl,
  activeAsset,
  onOpenAssetDrawer,
  onUploadCustomBg,
  onAddText,
  onAddShape,
  onDuplicate,
  onDelete,
  onToggleLock,
  isLocked,
  hasSelection,
  onToggleBold,
  onToggleItalic,
  selectedAlign,
  onTextAlign,
  selectedFontSize,
  onFontSizeChange,
  selectedColor,
  onTextColorChange,
  canUndo,
  canRedo,
  onUndo,
  onRedo,
  showWatermark,
  onToggleWatermark,
}) => {
  const [activeFlyout, setActiveFlyout] = useState<ActiveFlyout>(null);
  const [isExpanded, setIsExpanded] = useState<boolean>(false);
  const toolbarRef = useRef<HTMLDivElement | null>(null);

  // Close flyout when clicking outside the vertical toolbar
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (toolbarRef.current && !toolbarRef.current.contains(e.target as Node)) {
        setActiveFlyout(null);
      }
    };
    window.addEventListener("mousedown", handleClickOutside);
    return () => window.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const toggleFlyout = (name: ActiveFlyout) => {
    setActiveFlyout((prev) => (prev === name ? null : name));
  };

  return (
    <div
      ref={toolbarRef}
      className={`relative z-30 flex flex-col items-center gap-1 rounded-2xl border border-white/15 bg-[#081028]/95 p-1.5 shadow-2xl backdrop-blur-2xl transition-all duration-200 shrink-0 ${
        isExpanded ? "w-44" : "w-14"
      }`}
    >
      {/* ── Expand / Collapse Toggle ── */}
      <button
        type="button"
        onClick={() => setIsExpanded((prev) => !prev)}
        title={isExpanded ? "Collapse Sidebar" : "Expand Sidebar (Show Labels)"}
        className={`flex items-center rounded-xl transition-all ${
          isExpanded
            ? "w-full px-2.5 py-2 bg-white/5 hover:bg-white/10 text-white justify-between"
            : "size-10 justify-center text-muted-foreground hover:bg-white/10 hover:text-foreground"
        }`}
      >
        {isExpanded ? (
          <>
            <span className="text-[11px] font-bold text-primary flex items-center gap-1.5 font-mono uppercase tracking-wider">
              <PanelLeftClose className="size-3.5" /> Collapse
            </span>
            <ChevronLeft className="size-3.5 text-muted-foreground" />
          </>
        ) : (
          <PanelLeftOpen className="size-4 text-primary" />
        )}
      </button>

      <div className="my-0.5 h-px w-full bg-white/10" />

      {/* ── 1. Ratio Selector ── */}
      <div className="relative w-full">
        <button
          type="button"
          onClick={() => toggleFlyout("ratio")}
          title={`Aspect Ratio (${aspectRatioKey})`}
          className={`flex items-center rounded-xl transition-all ${
            isExpanded
              ? "w-full h-10 px-2.5 gap-2.5 justify-start text-xs font-medium"
              : "size-10 flex-col justify-center mx-auto"
          } ${
            activeFlyout === "ratio"
              ? "bg-primary text-primary-foreground shadow-md"
              : "text-muted-foreground hover:bg-white/10 hover:text-foreground"
          }`}
        >
          {aspectRatioKey === "4:5" && <Smartphone className="size-4 shrink-0" />}
          {aspectRatioKey === "1:1" && <Square className="size-4 shrink-0" />}
          {aspectRatioKey === "16:9" && <MonitorPlay className="size-4 shrink-0" />}
          {aspectRatioKey === "9:16" && <Flame className="size-4 shrink-0" />}
          {isExpanded ? (
            <span className="truncate">Ratio ({aspectRatioKey})</span>
          ) : (
            <span className="text-[9px] font-mono font-bold leading-none mt-0.5">
              {aspectRatioKey}
            </span>
          )}
        </button>

        {/* Ratio Flyout Menu */}
        {activeFlyout === "ratio" && (
          <div className="absolute left-full top-0 ml-2.5 z-40 flex flex-col gap-1 rounded-xl border border-border/80 bg-[#0B1535]/98 p-1.5 shadow-2xl backdrop-blur-xl animate-in fade-in-50 zoom-in-95 w-36">
            <span className="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
              Aspect Ratio
            </span>
            {Object.entries(ASPECT_RATIOS).map(([key, dim]) => (
              <button
                key={key}
                type="button"
                onClick={() => {
                  setAspectRatioKey(key);
                  setActiveFlyout(null);
                }}
                className={`flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-all ${
                  aspectRatioKey === key
                    ? "bg-primary text-primary-foreground font-semibold"
                    : "text-muted-foreground hover:bg-white/10 hover:text-foreground"
                }`}
              >
                {key === "4:5" && <Smartphone className="size-3.5 shrink-0" />}
                {key === "1:1" && <Square className="size-3.5 shrink-0" />}
                {key === "16:9" && <MonitorPlay className="size-3.5 shrink-0" />}
                {key === "9:16" && <Flame className="size-3.5 shrink-0" />}
                <span>{key}</span>
                <span className="ml-auto text-[10px] opacity-60 font-mono">
                  {dim.badgeRatio}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ── 2. Color Palette / Themes ── */}
      <div className="relative w-full">
        <button
          type="button"
          onClick={() => toggleFlyout("theme")}
          title={`Theme: ${selectedTheme.name}`}
          className={`flex items-center rounded-xl transition-all ${
            isExpanded
              ? "w-full h-10 px-2.5 gap-2.5 justify-start text-xs font-medium"
              : "size-10 justify-center mx-auto"
          } ${
            activeFlyout === "theme"
              ? "bg-primary text-primary-foreground shadow-md"
              : "text-muted-foreground hover:bg-white/10 hover:text-foreground"
          }`}
        >
          <div
            className="size-5 rounded-full border border-white/60 shadow-sm shrink-0"
            style={{
              background: `linear-gradient(135deg, ${selectedTheme.bgGradient[0]}, ${selectedTheme.accentColor})`,
            }}
          />
          {isExpanded && <span className="truncate">{selectedTheme.name}</span>}
        </button>

        {/* Themes Flyout Menu */}
        {activeFlyout === "theme" && (
          <div className="absolute left-full top-0 ml-2.5 z-40 flex flex-col gap-1.5 rounded-xl border border-border/80 bg-[#0B1535]/98 p-2.5 shadow-2xl backdrop-blur-xl animate-in fade-in-50 zoom-in-95 w-48">
            <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
              Preset Themes
            </span>
            <div className="grid grid-cols-4 gap-2">
              {PRESET_THEMES.map((theme) => (
                <button
                  key={theme.id}
                  type="button"
                  onClick={() => {
                    setSelectedTheme(theme);
                    setBgSource("preset");
                    setActiveFlyout(null);
                  }}
                  title={theme.name}
                  className={`size-9 rounded-xl border transition-all ${
                    selectedTheme.id === theme.id && bgSource === "preset"
                      ? "ring-2 ring-primary ring-offset-2 ring-offset-[#0B1535] scale-110 border-white"
                      : "border-border/60 opacity-80 hover:opacity-100 hover:scale-105"
                  }`}
                  style={{
                    background: `linear-gradient(135deg, ${theme.bgGradient[0]}, ${theme.accentColor})`,
                  }}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ── 3. Glass Card Opacity ── */}
      <div className="relative w-full">
        <button
          type="button"
          onClick={() => toggleFlyout("card")}
          title={`Glass Card Opacity: ${cardOpacity}`}
          className={`flex items-center rounded-xl transition-all ${
            isExpanded
              ? "w-full h-10 px-2.5 gap-2.5 justify-start text-xs font-medium"
              : "size-10 justify-center mx-auto"
          } ${
            activeFlyout === "card"
              ? "bg-primary text-primary-foreground shadow-md"
              : "text-muted-foreground hover:bg-white/10 hover:text-foreground"
          }`}
        >
          <Layers className="size-4 shrink-0" />
          {isExpanded && <span className="truncate capitalize">Card: {cardOpacity}</span>}
        </button>

        {/* Card Flyout Menu */}
        {activeFlyout === "card" && (
          <div className="absolute left-full top-0 ml-2.5 z-40 flex flex-col gap-1 rounded-xl border border-border/80 bg-[#0B1535]/98 p-1.5 shadow-2xl backdrop-blur-xl animate-in fade-in-50 zoom-in-95 w-36">
            <span className="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
              Glass Card
            </span>
            {(["subtle", "medium", "solid", "none"] as const).map((op) => (
              <button
                key={op}
                type="button"
                onClick={() => {
                  setCardOpacity(op);
                  setActiveFlyout(null);
                }}
                className={`rounded-lg px-2.5 py-1.5 text-xs font-medium capitalize text-left transition-all ${
                  cardOpacity === op
                    ? "bg-primary text-primary-foreground font-semibold"
                    : "text-muted-foreground hover:bg-white/10 hover:text-foreground"
                }`}
              >
                {op === "none" ? "Clear (No Card)" : op}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ── 4. Background Source ── */}
      <div className="relative w-full">
        <button
          type="button"
          onClick={() => toggleFlyout("bg")}
          title={`Background: ${bgSource}`}
          className={`flex items-center rounded-xl transition-all ${
            isExpanded
              ? "w-full h-10 px-2.5 gap-2.5 justify-start text-xs font-medium"
              : "size-10 justify-center mx-auto"
          } ${
            activeFlyout === "bg"
              ? "bg-primary text-primary-foreground shadow-md"
              : "text-muted-foreground hover:bg-white/10 hover:text-foreground"
          }`}
        >
          <Paintbrush className="size-4 shrink-0" />
          {isExpanded && <span className="truncate">Background</span>}
        </button>

        {/* Background Flyout Menu */}
        {activeFlyout === "bg" && (
          <div className="absolute left-full top-0 ml-2.5 z-40 flex flex-col gap-1.5 rounded-xl border border-border/80 bg-[#0B1535]/98 p-2 shadow-2xl backdrop-blur-xl animate-in fade-in-50 zoom-in-95 w-44">
            <span className="px-1 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
              Background Style
            </span>
            {backgroundImageUrl && (
              <button
                type="button"
                onClick={() => {
                  setBgSource("ai");
                  setActiveFlyout(null);
                }}
                className={`flex items-center gap-2 rounded-lg px-2 py-1.5 text-xs font-medium transition-all ${
                  bgSource === "ai"
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-white/10 hover:text-foreground"
                }`}
              >
                <Sparkles className="size-3.5 shrink-0" /> AI Artwork
              </button>
            )}

            <button
              type="button"
              onClick={() => {
                onUploadCustomBg();
                setActiveFlyout(null);
              }}
              className={`flex items-center gap-2 rounded-lg px-2 py-1.5 text-xs font-medium transition-all ${
                bgSource === "custom"
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-white/10 hover:text-foreground"
              }`}
            >
              <Upload className="size-3.5 shrink-0" /> Upload File
            </button>

            <button
              type="button"
              onClick={() => {
                setBgSource("preset");
                setActiveFlyout(null);
              }}
              className={`flex items-center gap-2 rounded-lg px-2 py-1.5 text-xs font-medium transition-all ${
                bgSource === "preset"
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-white/10 hover:text-foreground"
              }`}
            >
              <Palette className="size-3.5 shrink-0" /> Preset Gradient
            </button>

            <button
              type="button"
              onClick={() => {
                setBgSource("solid");
                setActiveFlyout(null);
              }}
              className={`flex items-center gap-2 rounded-lg px-2 py-1.5 text-xs font-medium transition-all ${
                bgSource === "solid"
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-white/10 hover:text-foreground"
              }`}
            >
              <Paintbrush className="size-3.5 shrink-0" /> Solid Color
            </button>

            {bgSource === "solid" && (
              <div className="flex items-center gap-2 pt-1 border-t border-white/10">
                <input
                  type="color"
                  value={solidColor}
                  onChange={(e) => setSolidColor(e.target.value)}
                  className="size-6 cursor-pointer rounded border border-white/20 bg-transparent"
                />
                <span className="font-mono text-[10px] text-muted-foreground">
                  {solidColor}
                </span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── 5. Branded Asset / Graphic ── */}
      <button
        type="button"
        onClick={onOpenAssetDrawer}
        title={activeAsset ? `Branded Asset (${activeAsset.role})` : "Attach Graphic / Logo"}
        className={`relative flex items-center rounded-xl transition-all ${
          isExpanded
            ? "w-full h-10 px-2.5 gap-2.5 justify-start text-xs font-medium"
            : "size-10 justify-center mx-auto"
        } ${
          activeAsset
            ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
            : "text-muted-foreground hover:bg-white/10 hover:text-foreground"
        }`}
      >
        <ImageIcon className="size-4 shrink-0" />
        {isExpanded && <span className="truncate">Brand Asset</span>}
        {activeAsset && (
          <span className="absolute top-1.5 right-1.5 size-2 rounded-full bg-amber-400 ring-2 ring-[#081028]" />
        )}
      </button>

      {/* ── Micro Divider ── */}
      <div className="my-1 h-px w-full bg-white/15" />

      {/* ── 6. Add Text ── */}
      <button
        type="button"
        onClick={onAddText}
        title="Add Text Block"
        className={`flex items-center rounded-xl text-muted-foreground hover:bg-white/10 hover:text-foreground transition-all ${
          isExpanded
            ? "w-full h-10 px-2.5 gap-2.5 justify-start text-xs font-medium"
            : "size-10 justify-center mx-auto"
        }`}
      >
        <Type className="size-4 shrink-0" />
        {isExpanded && <span className="truncate">Add Text</span>}
      </button>

      {/* ── 7. Shapes Flyout ── */}
      <div className="relative w-full">
        <button
          type="button"
          onClick={() => toggleFlyout("shape")}
          title="Add Vector Shape"
          className={`flex items-center rounded-xl transition-all ${
            isExpanded
              ? "w-full h-10 px-2.5 gap-2.5 justify-start text-xs font-medium"
              : "size-10 justify-center mx-auto"
          } ${
            activeFlyout === "shape"
              ? "bg-primary text-primary-foreground shadow-md"
              : "text-muted-foreground hover:bg-white/10 hover:text-foreground"
          }`}
        >
          <Square className="size-4 shrink-0" />
          {isExpanded && <span className="truncate">Shapes</span>}
        </button>

        {activeFlyout === "shape" && (
          <div className="absolute left-full top-0 ml-2.5 z-40 flex flex-col gap-1 rounded-xl border border-border/80 bg-[#0B1535]/98 p-1.5 shadow-2xl backdrop-blur-xl animate-in fade-in-50 zoom-in-95 w-36">
            <span className="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
              Shapes
            </span>
            <button
              type="button"
              onClick={() => {
                onAddShape("rect");
                setActiveFlyout(null);
              }}
              className="flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs font-medium text-muted-foreground hover:bg-white/10 hover:text-foreground"
            >
              <Square className="size-3.5 shrink-0" /> Rectangle
            </button>
            <button
              type="button"
              onClick={() => {
                onAddShape("circle");
                setActiveFlyout(null);
              }}
              className="flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs font-medium text-muted-foreground hover:bg-white/10 hover:text-foreground"
            >
              <Circle className="size-3.5 shrink-0" /> Circle
            </button>
            <button
              type="button"
              onClick={() => {
                onAddShape("line");
                setActiveFlyout(null);
              }}
              className="flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs font-medium text-muted-foreground hover:bg-white/10 hover:text-foreground"
            >
              <Minus className="size-3.5 shrink-0" /> Line
            </button>
          </div>
        )}
      </div>

      {/* ── Micro Divider ── */}
      <div className="my-1 h-px w-full bg-white/15" />

      {/* ── 8. Text Formatting & Alignment ── */}
      <button
        type="button"
        onClick={() => onTextAlign(selectedAlign === "center" ? "left" : "center")}
        title={`Text Alignment (${selectedAlign === "center" ? "Center" : "Left"})`}
        className={`flex items-center rounded-xl transition-all ${
          isExpanded
            ? "w-full h-10 px-2.5 gap-2.5 justify-start text-xs font-medium"
            : "size-10 justify-center mx-auto"
        } ${
          selectedAlign === "center"
            ? "bg-primary/20 text-primary border border-primary/40"
            : "text-muted-foreground hover:bg-white/10 hover:text-foreground"
        }`}
      >
        {selectedAlign === "center" ? (
          <AlignCenter className="size-4 shrink-0" />
        ) : selectedAlign === "right" ? (
          <AlignRight className="size-4 shrink-0" />
        ) : (
          <AlignLeft className="size-4 shrink-0" />
        )}
        {isExpanded && <span className="truncate">Align ({selectedAlign})</span>}
      </button>

      {/* Bold, Italic, Color Row in Expanded mode or stacked in collapsed mode */}
      {isExpanded ? (
        <div className="flex w-full items-center justify-between px-1 py-1 gap-1">
          <button
            type="button"
            onClick={onToggleBold}
            title="Toggle Bold"
            className="flex size-9 items-center justify-center rounded-lg text-muted-foreground hover:bg-white/10 hover:text-foreground bg-white/5"
          >
            <Bold className="size-3.5" />
          </button>
          <button
            type="button"
            onClick={onToggleItalic}
            title="Toggle Italic"
            className="flex size-9 items-center justify-center rounded-lg text-muted-foreground hover:bg-white/10 hover:text-foreground bg-white/5"
          >
            <Italic className="size-3.5" />
          </button>
          <div className="relative flex size-9 items-center justify-center rounded-lg bg-white/5" title="Text Color">
            <input
              type="color"
              value={selectedColor}
              onChange={(e) => onTextColorChange(e.target.value)}
              className="size-5 cursor-pointer rounded-full border border-white/30 bg-transparent"
            />
          </div>
        </div>
      ) : (
        <>
          <button
            type="button"
            onClick={onToggleBold}
            title="Toggle Bold"
            className="flex size-10 items-center justify-center rounded-xl text-muted-foreground hover:bg-white/10 hover:text-foreground transition-all"
          >
            <Bold className="size-4" />
          </button>

          <button
            type="button"
            onClick={onToggleItalic}
            title="Toggle Italic"
            className="flex size-10 items-center justify-center rounded-xl text-muted-foreground hover:bg-white/10 hover:text-foreground transition-all"
          >
            <Italic className="size-4" />
          </button>

          <div className="relative flex size-10 items-center justify-center" title="Color Picker">
            <input
              type="color"
              value={selectedColor}
              onChange={(e) => onTextColorChange(e.target.value)}
              className="size-6 cursor-pointer rounded-full border border-white/30 bg-transparent"
            />
          </div>
        </>
      )}

      {/* ── Micro Divider ── */}
      <div className="my-1 h-px w-full bg-white/15" />

      {/* ── 9. Undo / Redo ── */}
      {isExpanded ? (
        <div className="flex w-full items-center justify-between px-1 gap-1">
          <button
            type="button"
            onClick={onUndo}
            disabled={!canUndo}
            title="Undo (Ctrl+Z)"
            className="flex h-8 flex-1 items-center justify-center gap-1.5 rounded-lg text-xs font-medium text-muted-foreground hover:bg-white/10 hover:text-foreground disabled:opacity-20 bg-white/5"
          >
            <Undo2 className="size-3.5" /> Undo
          </button>
          <button
            type="button"
            onClick={onRedo}
            disabled={!canRedo}
            title="Redo (Ctrl+Y)"
            className="flex h-8 flex-1 items-center justify-center gap-1.5 rounded-lg text-xs font-medium text-muted-foreground hover:bg-white/10 hover:text-foreground disabled:opacity-20 bg-white/5"
          >
            <Redo2 className="size-3.5" /> Redo
          </button>
        </div>
      ) : (
        <>
          <button
            type="button"
            onClick={onUndo}
            disabled={!canUndo}
            title="Undo (Ctrl+Z)"
            className="flex size-10 items-center justify-center rounded-xl text-muted-foreground hover:bg-white/10 hover:text-foreground disabled:opacity-20 transition-all"
          >
            <Undo2 className="size-4" />
          </button>

          <button
            type="button"
            onClick={onRedo}
            disabled={!canRedo}
            title="Redo (Ctrl+Y)"
            className="flex size-10 items-center justify-center rounded-xl text-muted-foreground hover:bg-white/10 hover:text-foreground disabled:opacity-20 transition-all"
          >
            <Redo2 className="size-4" />
          </button>
        </>
      )}

      {/* ── 10. Duplicate / Delete ── */}
      {isExpanded ? (
        <div className="flex w-full items-center justify-between px-1 gap-1">
          <button
            type="button"
            onClick={onDuplicate}
            disabled={!hasSelection}
            title="Duplicate (Ctrl+D)"
            className="flex h-8 flex-1 items-center justify-center gap-1.5 rounded-lg text-xs font-medium text-muted-foreground hover:bg-white/10 hover:text-foreground disabled:opacity-20 bg-white/5"
          >
            <CopyIcon className="size-3.5" /> Copy
          </button>
          <button
            type="button"
            onClick={onDelete}
            disabled={!hasSelection}
            title="Delete Item"
            className="flex h-8 flex-1 items-center justify-center gap-1.5 rounded-lg text-xs font-medium text-rose-400 hover:bg-rose-500/20 disabled:opacity-20 bg-rose-500/10"
          >
            <Trash2 className="size-3.5" /> Del
          </button>
        </div>
      ) : (
        <>
          <button
            type="button"
            onClick={onDuplicate}
            disabled={!hasSelection}
            title="Duplicate (Ctrl+D)"
            className="flex size-10 items-center justify-center rounded-xl text-muted-foreground hover:bg-white/10 hover:text-foreground disabled:opacity-20 transition-all"
          >
            <CopyIcon className="size-4" />
          </button>

          <button
            type="button"
            onClick={onDelete}
            disabled={!hasSelection}
            title="Delete Item"
            className="flex size-10 items-center justify-center rounded-xl text-rose-400 hover:bg-rose-500/20 disabled:opacity-20 transition-all"
          >
            <Trash2 className="size-4" />
          </button>
        </>
      )}

      {/* ── Micro Divider ── */}
      <div className="my-1 h-px w-full bg-white/15" />

      {/* ── 11. Watermark Toggle ── */}
      <button
        type="button"
        onClick={onToggleWatermark}
        title={`Watermark: ${showWatermark ? "ON" : "OFF"}`}
        className={`flex items-center rounded-xl transition-all ${
          isExpanded
            ? "w-full h-10 px-2.5 gap-2.5 justify-start text-xs font-medium"
            : "size-10 flex-col justify-center mx-auto"
        } ${
          showWatermark
            ? "bg-primary/20 text-primary border border-primary/40"
            : "text-muted-foreground hover:bg-white/10 hover:text-foreground opacity-60"
        }`}
      >
        <Sparkles className="size-3.5 shrink-0" />
        {isExpanded ? (
          <span className="truncate">Watermark ({showWatermark ? "ON" : "OFF"})</span>
        ) : (
          <span className="text-[8px] font-mono font-bold mt-0.5">
            {showWatermark ? "WM" : "OFF"}
          </span>
        )}
      </button>
    </div>
  );
};
