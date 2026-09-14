/**
 * frontend/src/components/aiflick/canvas/canvas-asset-drawer.tsx
 *
 * Dedicated Branded Asset & Graphic Module Drawer for SocialPostCanvas.
 * Allows uploading avatar rings, logos, hero insets, and stickers with selective targeting.
 */

import React, { useRef } from "react";
import { ImageIcon, X, Upload, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { shouldInjectAssetForPost } from "../canvas-templates";
import type { InjectedAssetSpec, AssetRole, AssetTargetScope } from "@/api/types";

export interface CanvasAssetDrawerProps {
  open: boolean;
  onClose: () => void;
  activeAsset: InjectedAssetSpec | null;
  setActiveAsset: (asset: InjectedAssetSpec | null) => void;
  onInjectedAssetChange?: ((asset: InjectedAssetSpec | null) => void) | undefined;
  postNumber?: number | undefined;
  totalPosts?: number | undefined;
}

export const CanvasAssetDrawer: React.FC<CanvasAssetDrawerProps> = ({
  open,
  onClose,
  activeAsset,
  setActiveAsset,
  onInjectedAssetChange,
  postNumber = 1,
  totalPosts = 5,
}) => {
  const assetFileInputRef = useRef<HTMLInputElement | null>(null);

  if (!open) return null;

  const handleAssetUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      toast.error("Please upload a valid PNG, JPEG, SVG or WebP image");
      return;
    }
    const reader = new FileReader();
    reader.onload = (event) => {
      const dataUrl = event.target?.result as string;
      if (dataUrl) {
        const newAsset: InjectedAssetSpec = {
          id: `ast_${Date.now()}`,
          name: file.name,
          url: dataUrl,
          role: activeAsset?.role || "avatar",
          targetScope: activeAsset?.targetScope || "all",
          cropShape: (activeAsset?.role || "avatar") === "avatar" ? "circle" : "original",
          opacity: 1,
        };
        setActiveAsset(newAsset);
        if (onInjectedAssetChange) onInjectedAssetChange(newAsset);
        toast.success(`Asset "${file.name}" ready for post injection!`);
      }
    };
    reader.readAsDataURL(file);
  };

  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-border/80 bg-[#0B1535]/95 p-4 shadow-xl backdrop-blur-xl animate-in fade-in-50 mb-3">
      <div className="flex items-center justify-between border-b border-border/60 pb-2">
        <div className="flex items-center gap-2">
          <ImageIcon className="size-4 text-primary" />
          <span className="text-xs font-bold text-foreground">
            Post Graphic & Brand Asset Module
          </span>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg p-1 text-muted-foreground hover:bg-secondary hover:text-foreground"
        >
          <X className="size-4" />
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
        {/* 1. Upload or Change Image */}
        <div className="flex flex-col gap-1.5">
          <span className="font-semibold text-muted-foreground">1. Custom Image / Graphic</span>
          <button
            type="button"
            onClick={() => assetFileInputRef.current?.click()}
            className="flex items-center justify-center gap-2 rounded-xl border border-dashed border-primary/50 bg-primary/5 px-3 py-3 text-primary font-medium hover:bg-primary/10 transition-colors"
          >
            <Upload className="size-3.5" />
            {activeAsset ? "Replace Image File" : "Upload Picture (PNG/JPG)"}
          </button>
          <input
            ref={assetFileInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={handleAssetUpload}
          />
          {activeAsset && (
            <span className="text-[11px] text-muted-foreground truncate">
              Attached: {activeAsset.name}
            </span>
          )}
        </div>

        {/* 2. Semantic Role */}
        <div className="flex flex-col gap-1.5">
          <span className="font-semibold text-muted-foreground">2. Graphic Role & Styling</span>
          <div className="grid grid-cols-2 gap-1.5">
            {(
              [
                { id: "avatar", label: "👤 Avatar Ring" },
                { id: "logo", label: "🏷️ Top Logo" },
                { id: "hero_inset", label: "🖼️ Inset Card" },
                { id: "custom_sticker", label: "✨ Sticker" },
              ] as const
            ).map((r) => (
              <button
                key={r.id}
                type="button"
                onClick={() => {
                  if (!activeAsset) return;
                  const updated: InjectedAssetSpec = {
                    ...activeAsset,
                    role: r.id as AssetRole,
                    cropShape: r.id === "avatar" ? "circle" : "original",
                  };
                  setActiveAsset(updated);
                  if (onInjectedAssetChange) onInjectedAssetChange(updated);
                }}
                className={`rounded-lg px-2 py-1.5 text-[11px] font-medium transition-all ${
                  activeAsset?.role === r.id
                    ? "bg-primary text-primary-foreground font-semibold shadow-sm"
                    : "bg-secondary/60 text-muted-foreground hover:text-foreground"
                }`}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>

        {/* 3. Selective Targeting */}
        <div className="flex flex-col gap-1.5">
          <span className="font-semibold text-muted-foreground">3. Selective Post Placement</span>
          <div className="grid grid-cols-3 gap-1.5">
            {(
              [
                { id: "all", label: "✅ All Posts" },
                { id: "custom", label: "🎯 Custom" },
                { id: "none", label: "🚫 None" },
              ] as const
            ).map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => {
                  if (!activeAsset) return;
                  const updated: InjectedAssetSpec = {
                    ...activeAsset,
                    targetScope: s.id as AssetTargetScope,
                  };
                  setActiveAsset(updated);
                  if (onInjectedAssetChange) onInjectedAssetChange(updated);
                }}
                className={`rounded-lg px-2 py-1.5 text-[11px] font-medium transition-all ${
                  activeAsset?.targetScope === s.id
                    ? "bg-primary text-primary-foreground font-semibold shadow-sm"
                    : "bg-secondary/60 text-muted-foreground hover:text-foreground"
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>
          {activeAsset?.targetScope === "custom" && (
            <div className="flex flex-col gap-1 pt-1">
              <span className="text-[10px] text-muted-foreground">
                Post numbers (comma-separated, e.g. 1,3,5):
              </span>
              <input
                type="text"
                placeholder="e.g. 1,3,5"
                defaultValue={activeAsset?.customPostNumbers?.join(",") || ""}
                onBlur={(e) => {
                  if (!activeAsset) return;
                  const nums = e.target.value
                    .split(",")
                    .map((n) => parseInt(n.trim(), 10))
                    .filter((n) => !isNaN(n) && n > 0);
                  const updated: InjectedAssetSpec = {
                    ...activeAsset,
                    customPostNumbers: nums,
                  };
                  setActiveAsset(updated);
                  if (onInjectedAssetChange) onInjectedAssetChange(updated);
                }}
                className="rounded-lg border border-border/60 bg-secondary/40 px-2 py-1 text-[11px] text-foreground placeholder:text-muted-foreground/50"
              />
            </div>
          )}
        </div>
      </div>

      {activeAsset && (
        <div className="flex items-center justify-between border-t border-border/60 pt-2">
          <span className="text-[11px] text-muted-foreground">
            Status: Rendered on{" "}
            {shouldInjectAssetForPost(activeAsset, postNumber, totalPosts)
              ? `Post #${postNumber} (Active)`
              : `Other posts only (${activeAsset.targetScope})`}
          </span>
          <button
            type="button"
            onClick={() => {
              setActiveAsset(null);
              if (onInjectedAssetChange) onInjectedAssetChange(null);
              onClose();
              toast.info("Branded asset removed from canvas");
            }}
            className="flex items-center gap-1 text-[11px] text-rose-400 hover:text-rose-300"
          >
            <Trash2 className="size-3" /> Remove Asset
          </button>
        </div>
      )}
    </div>
  );
};
