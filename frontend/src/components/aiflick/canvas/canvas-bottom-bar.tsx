/**
 * frontend/src/components/aiflick/canvas/canvas-bottom-bar.tsx
 *
 * Bottom controls bar for SocialPostCanvas.
 * Includes Zoom controls, pan indicator, Regenerate AI Background, Reset Layout, Copy Image, and Download PNG.
 */

import React from "react";
import {
  Sparkles,
  RotateCcw,
  Copy,
  Check,
  Download,
  ZoomIn,
  ZoomOut,
  Maximize2,
} from "lucide-react";

export interface CanvasBottomBarProps {
  zoom: number;
  setZoom: (z: number) => void;
  zoomLevels: number[];
  onRegenerateBg?: (() => void) | undefined;
  isGeneratingBg?: boolean | undefined;
  onResetLayout: () => void;
  onCopyToClipboard: () => void;
  copied: boolean;
  onDownload: () => void;
}

export const CanvasBottomBar: React.FC<CanvasBottomBarProps> = ({
  zoom,
  setZoom,
  zoomLevels,
  onRegenerateBg,
  isGeneratingBg = false,
  onResetLayout,
  onCopyToClipboard,
  copied,
  onDownload,
}) => {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 pt-2 w-full">
      {/* Left: AI Regenerate & Reset */}
      <div className="flex items-center gap-2">
        {onRegenerateBg && (
          <button
            type="button"
            onClick={onRegenerateBg}
            disabled={isGeneratingBg}
            className="flex items-center gap-1.5 rounded-xl border border-border/80 bg-secondary/80 px-3.5 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-secondary disabled:opacity-50"
          >
            <Sparkles className="size-3.5 text-primary" />
            {isGeneratingBg ? "Regenerating AI Art..." : "Regenerate AI Background"}
          </button>
        )}

        <button
          type="button"
          onClick={onResetLayout}
          title="Reset canvas composition to defaults"
          className="flex items-center gap-1.5 rounded-xl border border-border/60 bg-transparent px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-white/5 transition-colors"
        >
          <RotateCcw className="size-3.5" /> Reset Layout
        </button>
      </div>

      {/* Center: Zoom Controls */}
      <div className="flex items-center gap-1 rounded-xl border border-border/60 bg-[#081028]/80 p-1">
        <button
          type="button"
          onClick={() => {
            const prev = [...zoomLevels].reverse().find((z) => z < zoom) ?? zoomLevels[0]!;
            setZoom(prev);
          }}
          className="flex size-7 items-center justify-center rounded-lg text-muted-foreground hover:bg-white/10 hover:text-foreground"
          title="Zoom Out"
        >
          <ZoomOut className="size-3.5" />
        </button>
        <button
          type="button"
          onClick={() => setZoom(0.65)}
          className="flex items-center justify-center rounded-lg px-2 py-1 text-xs font-mono font-medium text-muted-foreground hover:text-foreground"
          title="Reset Zoom to 65%"
        >
          <Maximize2 className="size-3 mr-1" />
          {Math.round(zoom * 100)}%
        </button>
        <button
          type="button"
          onClick={() => {
            const next = zoomLevels.find((z) => z > zoom) ?? zoomLevels[zoomLevels.length - 1]!;
            setZoom(next);
          }}
          className="flex size-7 items-center justify-center rounded-lg text-muted-foreground hover:bg-white/10 hover:text-foreground"
          title="Zoom In"
        >
          <ZoomIn className="size-3.5" />
        </button>
      </div>

      {/* Right: Copy Graphic & Download */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onCopyToClipboard}
          className="flex items-center gap-1.5 rounded-xl border border-border/80 bg-secondary/80 px-3.5 py-1.5 text-xs font-medium text-foreground transition-all hover:bg-secondary active:scale-95"
        >
          {copied ? (
            <Check className="size-3.5 text-emerald-400" />
          ) : (
            <Copy className="size-3.5" />
          )}
          {copied ? "Copied!" : "Copy Image"}
        </button>

        <button
          type="button"
          onClick={onDownload}
          className="flex items-center gap-1.5 rounded-xl bg-primary px-4 py-1.5 text-xs font-semibold text-primary-foreground shadow-md transition-all hover:brightness-110 active:scale-95"
        >
          <Download className="size-3.5" /> Download PNG
        </button>
      </div>
    </div>
  );
};
