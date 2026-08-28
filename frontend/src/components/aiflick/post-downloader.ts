/**
 * frontend/src/components/aiflick/post-downloader.ts
 *
 * Batch post download utility for AIFlick.
 *
 * Renders each post to a PNG using an off-screen Fabric.js canvas and
 * triggers sequential downloads (one per post). This avoids the need for
 * an external ZIP dependency and works natively in all modern browsers.
 */

import { fabric } from "fabric";
import type { GeneratedPost } from "./data";
import {
  ASPECT_RATIOS,
  PRESET_THEMES,
  type PostTheme,
  computeAutoLayout,
  generatePresetBackgroundDataUrl,
} from "./canvas-templates";

export interface DownloadAllOptions {
  theme?: PostTheme | undefined;
  aspectRatioKey?: string | undefined;
  onProgress?: ((downloaded: number, total: number) => void) | undefined;
  delayBetweenMs?: number | undefined;
}

/**
 * Renders a single GeneratedPost to a PNG data URL using an off-screen Fabric canvas.
 */
export async function renderPostToDataUrl(
  post: GeneratedPost,
  theme: PostTheme = PRESET_THEMES[0]!,
  aspectRatioKey = "4:5"
): Promise<string | null> {
  const dimensions = ASPECT_RATIOS[aspectRatioKey] ?? ASPECT_RATIOS["4:5"]!;
  const { width, height } = dimensions;

  // Create an off-screen canvas element
  const canvasEl = document.createElement("canvas");
  canvasEl.width = width;
  canvasEl.height = height;
  canvasEl.style.position = "absolute";
  canvasEl.style.visibility = "hidden";
  canvasEl.style.pointerEvents = "none";
  document.body.appendChild(canvasEl);

  let fc: fabric.Canvas | null = null;

  try {
    fc = new fabric.Canvas(canvasEl, {
      preserveObjectStacking: true,
      selection: false,
      interactive: false,
    });
    fc.setWidth(width);
    fc.setHeight(height);

    // Parse bullets from post summary
    const bulletPoints: string[] = (() => {
      const s: any = post.summary;
      if (Array.isArray(s) && s.length > 0) {
        return s.filter(Boolean).slice(0, 7);
      }
      if (typeof s === "string" && s.trim()) {
        return s
          .split("\n")
          .map((line: string) => line.trim().replace(/^[-•*📌🚀⚡💡🔴\d.]+\s*/, ""))
          .filter(Boolean)
          .slice(0, 7);
      }
      return [
        "Core Implementation & Architecture",
        "Key Workflow Decisions",
        "Production Scale & Outcomes",
      ];
    })();

    const layout = computeAutoLayout(width, height, post.title || "", bulletPoints.length);

    // Set background
    const bgSvgUrl = generatePresetBackgroundDataUrl(width, height, theme);

    await new Promise<void>((resolve) => {
      fabric.Image.fromURL(bgSvgUrl, (img) => {
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
          fc!.setBackgroundImage(img, () => resolve());
        } else {
          fc!.backgroundColor = theme.bgGradient[0];
          resolve();
        }
      });
    });

    // Build foreground
    const innerLeft = layout.horizontalMargin + 48;
    const innerWidth = layout.containerWidth - 96;
    let currentY = layout.topMargin + 48;

    // Card container
    fc.add(new fabric.Rect({
      left: layout.horizontalMargin,
      top: layout.topMargin,
      width: layout.containerWidth,
      height: layout.containerHeight,
      rx: 28, ry: 28,
      fill: "rgba(10, 15, 30, 0.50)",
      stroke: theme.containerBorder,
      strokeWidth: 1.5,
      selectable: false, evented: false,
      shadow: new fabric.Shadow({ color: "rgba(0,0,0,0.6)", blur: 35, offsetX: 0, offsetY: 16 }),
    }));

    // Badge
    fc.add(new fabric.Rect({
      left: innerLeft, top: currentY, width: 220, height: 34,
      rx: 17, ry: 17, fill: theme.badgeBg, stroke: theme.containerBorder,
      strokeWidth: 1, selectable: false, evented: false,
    }));
    fc.add(new fabric.Textbox(`✨ ${(post.platform || "instagram").toUpperCase()} GUIDE`, {
      left: innerLeft + 12, top: currentY + 7, width: 196, fontSize: 14,
      fontFamily: "Inter, sans-serif", fontWeight: "bold",
      fill: theme.badgeTextColor, selectable: false, evented: false,
    }));
    currentY += 56;

    // Title
    const cleanTitle = (post.title || "").replace(/^#+\s*/gm, "").replace(/\*\*(.*?)\*\*/g, "$1");
    const titleFab = new fabric.Textbox(cleanTitle, {
      left: innerLeft, top: currentY, width: innerWidth,
      fontSize: layout.titleFontSize, fontWeight: "bold",
      fontFamily: "Inter, -apple-system, sans-serif",
      fill: theme.titleColor, lineHeight: 1.25,
      selectable: false, evented: false,
    });
    fc.add(titleFab);
    currentY += (titleFab.height || 60) + 16;

    // Hook
    if (post.hook) {
      const cleanHook = (post.hook || "").replace(/^#+\s*/gm, "").replace(/\*\*(.*?)\*\*/g, "$1");
      const hookFab = new fabric.Textbox(`⚡ ${cleanHook}`, {
        left: innerLeft, top: currentY, width: innerWidth,
        fontSize: 20, fontWeight: "500",
        fontFamily: "Inter, -apple-system, sans-serif",
        fill: theme.hookColor, lineHeight: 1.35,
        selectable: false, evented: false,
      });
      fc.add(hookFab);
      currentY += (hookFab.height || 30) + 24;
    }

    // Divider
    fc.add(new fabric.Line([innerLeft, currentY, innerLeft + innerWidth, currentY], {
      stroke: theme.containerBorder, strokeWidth: 1,
      selectable: false, evented: false,
    }));
    currentY += 28;

    // Bullets
    bulletPoints.forEach((bulletText, idx) => {
      fc!.add(new fabric.Circle({
        radius: 14, fill: theme.bulletNumBg,
        left: innerLeft, top: currentY + 2,
        selectable: false, evented: false,
      }));
      fc!.add(new fabric.Textbox(`${idx + 1}`, {
        fontSize: 14, fontFamily: "Inter, sans-serif", fontWeight: "bold",
        fill: theme.bulletNumColor,
        left: innerLeft + (idx >= 9 ? 6 : 9), top: currentY + 6, width: 18,
        textAlign: "center", selectable: false, evented: false,
      }));
      const bulletContent = new fabric.Textbox(bulletText, {
        left: innerLeft + 42, top: currentY, width: innerWidth - 46,
        fontSize: layout.bulletFontSize, fontFamily: "Inter, -apple-system, sans-serif",
        fontWeight: "400", fill: theme.bulletColor, lineHeight: 1.3,
        selectable: false, evented: false,
      });
      fc!.add(bulletContent);
      currentY += Math.max(bulletContent.height || 36, 36) + layout.bulletSpacing;
    });

    // Watermark
    const footerY = layout.topMargin + layout.containerHeight - 48;
    fc.add(new fabric.Textbox(`✨ Created with AIFlick`, {
      fontSize: 14, fontFamily: "Inter, sans-serif", fontWeight: "500",
      fill: theme.badgeTextColor, left: innerLeft, top: footerY, width: innerWidth,
      selectable: false, evented: false,
    }));

    fc.renderAll();

    // Export to data URL
    const dataUrl = fc.toDataURL({ format: "png", multiplier: 1, quality: 1 });
    return dataUrl;
  } catch (err) {
    console.error("[PostDownloader] Failed to render post:", post.id, err);
    return null;
  } finally {
    if (fc) {
      try { fc.dispose(); } catch { /* ignore */ }
    }
    if (canvasEl.parentNode) {
      document.body.removeChild(canvasEl);
    }
  }
}

/**
 * Download all posts as individual PNG files with sequential naming.
 */
export async function downloadAllPosts(
  posts: GeneratedPost[],
  options: DownloadAllOptions = {}
): Promise<{ success: number; failed: number }> {
  const {
    theme = PRESET_THEMES[0]!,
    aspectRatioKey = "4:5",
    onProgress,
    delayBetweenMs = 300,
  } = options;

  if (!posts.length) return { success: 0, failed: 0 };

  let successCount = 0;
  let failedCount = 0;
  const ratioSlug = aspectRatioKey.replace(":", "-");

  for (let i = 0; i < posts.length; i++) {
    const post = posts[i];
    if (!post) continue;

    try {
      const dataUrl = await renderPostToDataUrl(post, theme, aspectRatioKey);

      if (dataUrl) {
        const filename = `aiflick-post-${i + 1}-${post.platform || "post"}-${ratioSlug}.png`;
        const a = document.createElement("a");
        a.href = dataUrl;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        successCount++;
      } else {
        failedCount++;
      }
    } catch {
      failedCount++;
    }

    onProgress?.(i + 1, posts.length);

    // Small delay between downloads so browser doesn't block them
    if (i < posts.length - 1) {
      await new Promise((r) => setTimeout(r, delayBetweenMs));
    }
  }

  return { success: successCount, failed: failedCount };
}
