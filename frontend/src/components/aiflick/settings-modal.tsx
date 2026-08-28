import { useState, useEffect } from "react";
import { motion } from "motion/react";
import {
  Brain,
  Check,
  Crown,
  Flame,
  Layers,
  Loader2,
  Lock,
  Save,
  Settings,
  Shield,
  Sparkles,
  Zap,
} from "lucide-react";
import { toast } from "sonner";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  getPreferences,
  savePreferences,
  getTierPlans,
  upgradeTier,
  type UserPreferences,
  type PlanInfo,
} from "@/api";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentTier?: string;
  onTierChanged?: (newTier: string) => void;
};

export function SettingsModal({
  open,
  onOpenChange,
  currentTier = "free",
  onTierChanged,
}: Props) {
  const [activeTab, setActiveTab] = useState<"tier" | "memory" | "studio">("tier");
  const [loading, setLoading] = useState(false);
  const [savingMemory, setSavingMemory] = useState(false);
  const [upgradingTierId, setUpgradingTierId] = useState<string | null>(null);

  const [plans, setPlans] = useState<PlanInfo[]>([]);
  const [activeTierId, setActiveTierId] = useState(currentTier || "free");

  // User Memory fields
  const [brandName, setBrandName] = useState("");
  const [brandHandle, setBrandHandle] = useState("@aiflick");
  const [targetAudience, setTargetAudience] = useState("");
  const [toneOfVoice, setToneOfVoice] = useState("punchy, authoritative, high-conversion");
  const [customRules, setCustomRules] = useState("");
  const [showWatermark, setShowWatermark] = useState(true);

  useEffect(() => {
    if (open) {
      loadData();
    }
  }, [open]);

  useEffect(() => {
    if (currentTier) {
      setActiveTierId(currentTier);
    }
  }, [currentTier]);

  async function loadData() {
    setLoading(true);
    try {
      const [prefsData, plansData] = await Promise.all([
        getPreferences().catch(() => null),
        getTierPlans().catch(() => null),
      ]);

      if (plansData?.plans) {
        setPlans(plansData.plans);
      }

      if (prefsData) {
        setBrandName(prefsData.brand_name || "");
        setBrandHandle(prefsData.brand_handle || "@aiflick");
        setTargetAudience(prefsData.target_audience || "");
        setToneOfVoice(prefsData.tone_of_voice || "punchy, authoritative, high-conversion");
        setCustomRules(prefsData.custom_rules || "");
        setShowWatermark(prefsData.show_watermark ?? true);
        if (prefsData.preferred_model_tier) {
          setActiveTierId(prefsData.preferred_model_tier);
        }
      }
    } catch {
      // Ignored for guests
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveMemory(e: React.FormEvent) {
    e.preventDefault();
    setSavingMemory(true);
    try {
      await savePreferences({
        brand_name: brandName.trim(),
        brand_handle: brandHandle.trim(),
        target_audience: targetAudience.trim(),
        tone_of_voice: toneOfVoice.trim(),
        custom_rules: customRules.trim(),
        show_watermark: showWatermark,
        preferred_model_tier: activeTierId,
      });
      toast.success("Brand memory & creator preferences saved!");
    } catch (err: any) {
      toast.error(err?.message || "Failed to save preferences (please sign in first)");
    } finally {
      setSavingMemory(false);
    }
  }

  async function handleSwitchTier(tierId: string) {
    setUpgradingTierId(tierId);
    try {
      const res = await upgradeTier(tierId);
      setActiveTierId(res.tier);
      if (onTierChanged) onTierChanged(res.tier);
      toast.success(`Active tier switched to ${res.plan_name}!`);
    } catch (err: any) {
      toast.error(err?.message || "Please sign in to switch tier models");
    } finally {
      setUpgradingTierId(null);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[92vh] flex-col gap-0 overflow-hidden rounded-2xl border-border/70 bg-surface-raised/95 p-0 shadow-2xl backdrop-blur-2xl sm:max-w-4xl">
        {/* Header */}
        <DialogHeader className="border-b border-border/60 px-6 py-4 text-left">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <span className="grid size-8 place-items-center rounded-xl bg-primary/10 text-primary ring-1 ring-primary/25">
                <Settings className="size-4" />
              </span>
              <div>
                <DialogTitle className="text-lg font-bold text-foreground">
                  Workspace Settings & Creator Memory
                </DialogTitle>
                <DialogDescription className="text-xs text-muted-foreground">
                  Configure active AI models, long-term brand tone, and studio defaults.
                </DialogDescription>
              </div>
            </div>

            {/* Tab Pills */}
            <div className="flex items-center gap-1 rounded-xl bg-secondary/60 p-1 border border-border/50">
              <button
                type="button"
                onClick={() => setActiveTab("tier")}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                  activeTab === "tier"
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <Zap className="size-3.5 text-primary" /> Models & Tiers
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("memory")}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                  activeTab === "memory"
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <Brain className="size-3.5 text-primary" /> Brand Memory
              </button>
            </div>
          </div>
        </DialogHeader>

        {/* Content Body */}
        <div className="min-h-0 flex-1 overflow-y-auto scroll-quiet p-6">
          {loading ? (
            <div className="flex h-64 flex-col items-center justify-center gap-2">
              <Loader2 className="size-6 animate-spin text-primary" />
              <span className="text-xs text-muted-foreground">Loading workspace preferences...</span>
            </div>
          ) : activeTab === "tier" ? (
            /* TAB 1: Models & Active Tier */
            <div className="space-y-6">
              <div>
                <h3 className="text-sm font-bold text-foreground">Select Active AI Model Tier</h3>
                <p className="text-xs text-muted-foreground">
                  Test and switch between free open models and high-reasoning creator models.
                </p>
              </div>

              <div className="grid gap-4 md:grid-cols-3">
                {/* 1. Free Explorer */}
                <div
                  className={`relative flex flex-col justify-between rounded-2xl border p-5 transition-all ${
                    activeTierId === "free"
                      ? "border-primary bg-primary/5 ring-2 ring-primary/30 shadow-panel"
                      : "border-border/70 bg-card/60 hover:border-border-strong"
                  }`}
                >
                  {activeTierId === "free" && (
                    <span className="absolute -top-2.5 right-4 rounded-full bg-primary px-2 py-0.5 font-mono text-[10px] font-bold text-primary-foreground">
                      Active Plan
                    </span>
                  )}
                  <div>
                    <div className="flex items-center gap-2">
                      <Sparkles className="size-4 text-emerald-400" />
                      <h4 className="font-bold text-foreground">Free Explorer</h4>
                    </div>
                    <div className="mt-2 flex items-baseline gap-1">
                      <span className="text-2xl font-black text-foreground">$0</span>
                      <span className="text-xs text-muted-foreground">/ month</span>
                    </div>
                    <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                      100% free forever for creators testing AIFlick with open models.
                    </p>

                    <div className="mt-4 space-y-2 border-t border-border/50 pt-3 text-xs text-foreground/90 font-mono">
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">Text Model:</span>
                        <span className="text-primary">Gemini 2.0 Flash</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">Visual Art:</span>
                        <span className="text-foreground">FLUX.1-schnell</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">Daily Limit:</span>
                        <span>15 posts / day</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">Watermark:</span>
                        <span className="text-emerald-400">Optional / Removable</span>
                      </div>
                    </div>
                  </div>

                  <Button
                    size="sm"
                    variant={activeTierId === "free" ? "secondary" : "outline"}
                    disabled={activeTierId === "free" || upgradingTierId === "free"}
                    onClick={() => handleSwitchTier("free")}
                    className="mt-5 w-full rounded-xl"
                  >
                    {activeTierId === "free" ? "Currently Active" : "Select Free Explorer"}
                  </Button>
                </div>

                {/* 2. Creator Pro — Coming Soon */}
                <div
                  className="relative flex flex-col justify-between rounded-2xl border border-border/70 bg-card/60 p-5 transition-all opacity-90"
                >
                  {/* Coming Soon ribbon */}
                  <span className="absolute -top-2.5 right-4 rounded-full bg-amber-500 px-2.5 py-0.5 font-mono text-[10px] font-bold text-black shadow-sm flex items-center gap-1">
                    🚧 Coming Soon
                  </span>

                  <div>
                    <div className="flex items-center gap-2">
                      <Zap className="size-4 text-primary" />
                      <h4 className="font-bold text-foreground">Creator Pro</h4>
                    </div>
                    <div className="mt-2 flex items-baseline gap-1">
                      <span className="text-2xl font-black text-foreground">$9</span>
                      <span className="text-xs text-muted-foreground">/ month</span>
                    </div>
                    <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                      For growing influencers & solo creators requiring clean, fast watermark-free visuals.
                    </p>

                    <div className="mt-4 space-y-2 border-t border-border/50 pt-3 text-xs text-foreground/90 font-mono">
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">Text Model:</span>
                        <span className="text-primary">Gemini 2.5 Flash</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">Visual Art:</span>
                        <span className="text-foreground">FLUX.1-Pro</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">Daily Limit:</span>
                        <span>75 posts / day</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">Carousels:</span>
                        <span>Up to 10 slides</span>
                      </div>
                    </div>
                  </div>

                  <Button
                    size="sm"
                    disabled
                    className="mt-5 w-full rounded-xl bg-amber-500/20 text-amber-400 border border-amber-500/30 cursor-not-allowed font-bold"
                  >
                    🚧 Coming Soon
                  </Button>
                </div>

                {/* 3. Agency Studio — Coming Soon */}
                <div
                  className="relative flex flex-col justify-between rounded-2xl border border-border/70 bg-card/60 p-5 transition-all opacity-90"
                >
                  {/* Coming Soon ribbon */}
                  <span className="absolute -top-2.5 right-4 rounded-full bg-amber-500 px-2.5 py-0.5 font-mono text-[10px] font-bold text-black shadow-sm flex items-center gap-1">
                    🚧 Coming Soon
                  </span>

                  <div>
                    <div className="flex items-center gap-2">
                      <Crown className="size-4 text-amber-400" />
                      <h4 className="font-bold text-foreground">Agency Studio</h4>
                    </div>
                    <div className="mt-2 flex items-baseline gap-1">
                      <span className="text-2xl font-black text-foreground">$29</span>
                      <span className="text-xs text-muted-foreground">/ month</span>
                    </div>
                    <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                      Unlimited generations with deep reasoning and Google Imagen 3 studio visuals.
                    </p>

                    <div className="mt-4 space-y-2 border-t border-border/50 pt-3 text-xs text-foreground/90 font-mono">
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">Text Model:</span>
                        <span className="text-primary">Gemini 2.5 Pro</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">Visual Art:</span>
                        <span className="text-amber-400">Google Imagen 3</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">Daily Limit:</span>
                        <span className="text-emerald-400 font-bold">Unlimited</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">Priority:</span>
                        <span className="text-amber-400">Dedicated Pool</span>
                      </div>
                    </div>
                  </div>

                  <Button
                    size="sm"
                    disabled
                    className="mt-5 w-full rounded-xl bg-amber-500/20 text-amber-400 border border-amber-500/30 cursor-not-allowed font-bold"
                  >
                    🚧 Coming Soon
                  </Button>
                </div>
              </div>
            </div>
          ) : (
            /* TAB 2: Brand Memory & Creator Persona */
            <form onSubmit={handleSaveMemory} className="space-y-4">
              <div>
                <h3 className="text-sm font-bold text-foreground">Creator Brand Memory</h3>
                <p className="text-xs text-muted-foreground">
                  Saved preferences are automatically injected into every post generation prompt.
                </p>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="brandName" className="label-mono text-xs">
                    Brand / Channel Name
                  </Label>
                  <Input
                    id="brandName"
                    value={brandName}
                    onChange={(e) => setBrandName(e.target.value)}
                    placeholder="e.g. Nexus Tech Studio"
                    className="h-10 rounded-xl border-border/80 bg-surface-raised/60"
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="brandHandle" className="label-mono text-xs">
                    Social Handle (@)
                  </Label>
                  <Input
                    id="brandHandle"
                    value={brandHandle}
                    onChange={(e) => setBrandHandle(e.target.value)}
                    placeholder="e.g. @nexus_tech"
                    className="h-10 rounded-xl border-border/80 bg-surface-raised/60"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="targetAudience" className="label-mono text-xs">
                  Target Audience
                </Label>
                <Input
                  id="targetAudience"
                  value={targetAudience}
                  onChange={(e) => setTargetAudience(e.target.value)}
                  placeholder="e.g. Senior Software Engineers, DevOps Leads, Tech Founders"
                  className="h-10 rounded-xl border-border/80 bg-surface-raised/60"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="toneOfVoice" className="label-mono text-xs">
                  Tone of Voice & Style
                </Label>
                <Input
                  id="toneOfVoice"
                  value={toneOfVoice}
                  onChange={(e) => setToneOfVoice(e.target.value)}
                  placeholder="e.g. Punchy, authoritative, witty, high-conversion, analytical"
                  className="h-10 rounded-xl border-border/80 bg-surface-raised/60"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="customRules" className="label-mono text-xs">
                  Custom Rules & Constraints (Long-Term Memory)
                </Label>
                <Textarea
                  id="customRules"
                  rows={4}
                  value={customRules}
                  onChange={(e) => setCustomRules(e.target.value)}
                  placeholder="e.g. Never use buzzwords like 'revolutionize' or 'game-changer'. Always include 1 practical command or code snippet. Keep slide headlines under 8 words."
                  className="rounded-xl border-border/80 bg-surface-raised/60 text-sm leading-relaxed"
                />
              </div>

              <div className="flex items-center justify-between rounded-xl border border-border/60 bg-surface-raised/40 p-3">
                <div>
                  <span className="block text-xs font-semibold text-foreground">Canvas Studio Watermark</span>
                  <span className="block text-[11px] text-muted-foreground">
                    Include "✨ Created with AIFlick" badge by default on post graphics.
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => setShowWatermark((v) => !v)}
                  className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                    showWatermark
                      ? "bg-primary text-primary-foreground shadow-sm"
                      : "bg-secondary text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {showWatermark ? "Enabled" : "Disabled"}
                </button>
              </div>

              <div className="flex justify-end pt-2">
                <Button
                  type="submit"
                  disabled={savingMemory}
                  className="h-10 gap-2 rounded-xl bg-primary px-5 text-xs font-semibold text-primary-foreground hover:bg-primary-hover shadow-ember"
                >
                  {savingMemory ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />}
                  {savingMemory ? "Saving Memory..." : "Save Brand Memory"}
                </Button>
              </div>
            </form>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
