import React, { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  ArrowRight,
  Brain,
  Check,
  ChevronDown,
  Cpu,
  Flame,
  Globe,
  Layers,
  Lock,
  MessageSquare,
  Palette,
  Shield,
  ShieldCheck,
  Sparkles,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";

type Props = {
  onGetStarted: () => void;
  onOpenSignIn: () => void;
};

export function LandingPage({ onGetStarted, onOpenSignIn }: Props) {
  const [openFaq, setOpenFaq] = useState<number | null>(0);

  const navLinks = [
    { label: "Features", href: "#features" },
    { label: "Visual Studio", href: "#features" },
    { label: "Models & Pricing", href: "#pricing" },
    { label: "FAQ", href: "#faq" },
  ];

  const creatorBadges = [
    "Tech Creators",
    "Indie Hackers",
    "AI Engineers",
    "SaaS Founders",
    "Growth Marketers",
    "Newsletter Authors",
    "Solopreneurs",
  ];

  const features = [
    {
      icon: <Globe className="size-5 text-amber-400" />,
      title: "Real-Time Trend Grounding",
      desc: "Live search across GitHub Trending, Reddit, HackerNews, YouTube, and Google Trends so your posts cite fresh data.",
    },
    {
      icon: <Palette className="size-5 text-pink-400" />,
      title: "Interactive Canvas Studio",
      desc: "Full vector graphic canvas with instant text inline editing, undo/redo, typography scaling, and clean PNG downloads.",
    },
    {
      icon: <Zap className="size-5 text-cyan-400" />,
      title: "Multi-Model Intelligence",
      desc: "Powered by Gemini 2.0 Flash for instant copy and FLUX.1 + Imagen 3 for studio-grade background art.",
    },
    {
      icon: <Brain className="size-5 text-emerald-400" />,
      title: "Long-Term Creator Memory",
      desc: "Remembers your brand name, social handle, target audience, and custom rules for every single post.",
    },
    {
      icon: <Layers className="size-5 text-purple-400" />,
      title: "Multi-Slide Carousels",
      desc: "Sequenced 5 to 15 slide carousels: Hook → Context → Breakdown → Nuance → High-converting CTA.",
    },
    {
      icon: <Flame className="size-5 text-amber-400" />,
      title: "Viral Copy Frameworks",
      desc: "Trained on millions of top-performing social posts with zero ALL-CAPS shouting, punchy 3-bullet slides, and rich captions.",
    },
  ];

  const faqs = [
    {
      q: "Can I use AIFlick completely for free?",
      a: "Yes! The Free Explorer tier is 100% free with no credit card required. It includes Gemini 2.0 Flash for copy generation and FLUX.1 (via Pollinations) for visual art, with full canvas editing and optional watermark removal.",
    },
    {
      q: "How does the Canvas Studio work?",
      a: "Every generated post can be opened in the Studio. You can double-click any headline or bullet point to edit it inline, change colors, adjust font sizes, move elements, toggle the glass card opacity, and export high-resolution PNGs.",
    },
    {
      q: "What makes AIFlick different from basic ChatGPT prompts?",
      a: "AIFlick doesn't guess. It actively fetches live trend data from multiple platforms, uses specialized viral copywriting frameworks (Zero ALL-CAPS, high-contrast hook architecture), and automatically designs matching visual post graphics.",
    },
    {
      q: "How does Brand Memory work?",
      a: "In Workspace Settings, you can define your brand name, handle, target audience, and custom constraints (e.g. 'never use buzzwords'). AIFlick automatically injects this memory into every generation turn.",
    },
  ];

  return (
    <div className="relative min-h-screen bg-[#070B1A] text-foreground font-sans selection:bg-primary/30 selection:text-white overflow-x-hidden">
      {/* ── 1. Fluid Iridescent Ambient Background Glow (Inspired by Reference Image) ── */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden z-0">
        <div
          className="absolute -top-[15%] left-1/2 -translate-x-1/2 w-[1100px] h-[650px] rounded-full blur-[140px] opacity-35"
          style={{
            background: "radial-gradient(ellipse at center, rgba(56, 189, 248, 0.45), rgba(217, 70, 239, 0.35), rgba(245, 158, 11, 0.25), transparent 70%)",
          }}
        />
        <div
          className="absolute top-[35%] -left-[10%] w-[650px] h-[550px] rounded-full blur-[160px] opacity-25"
          style={{
            background: "radial-gradient(circle, rgba(234, 88, 12, 0.4), rgba(168, 85, 247, 0.2), transparent 70%)",
          }}
        />
        <div
          className="absolute top-[60%] -right-[10%] w-[700px] h-[600px] rounded-full blur-[160px] opacity-25"
          style={{
            background: "radial-gradient(circle, rgba(14, 165, 233, 0.35), rgba(59, 130, 246, 0.25), transparent 70%)",
          }}
        />
        {/* Subtle grid texture overlay */}
        <div
          className="absolute inset-0 opacity-[0.035]"
          style={{
            backgroundImage:
              "linear-gradient(to right, #ffffff 1px, transparent 1px), linear-gradient(to bottom, #ffffff 1px, transparent 1px)",
            backgroundSize: "48px 48px",
          }}
        />
      </div>

      {/* ── 2. Top Navigation Bar ── */}
      <header className="sticky top-0 z-50 backdrop-blur-xl border-b border-white/5 bg-black/40">
        <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-6 sm:px-8">
          {/* Logo */}
          <div
            className="flex items-center gap-2.5 cursor-pointer"
            onClick={() => window.location.reload()}
            title="Reload AIFlick"
          >
            <div className="flex size-9 items-center justify-center rounded-xl bg-gradient-to-tr from-primary to-amber-400 shadow-ember ring-1 ring-primary/40">
              <span className="text-sm font-black text-black">△</span>
            </div>
            <span className="text-xl font-bold tracking-tight text-white">
              AIFlick
            </span>
          </div>

          {/* Navigation Links */}
          <nav className="hidden md:flex items-center gap-8 text-sm font-medium text-slate-300">
            {navLinks.map((link) => (
              <a
                key={link.label}
                href={link.href}
                className="transition-colors hover:text-white"
              >
                {link.label}
              </a>
            ))}
          </nav>

          {/* Actions */}
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onOpenSignIn}
              className="text-xs font-semibold text-slate-300 hover:text-white px-3 py-2 transition-colors"
            >
              Sign in
            </button>
            <Button
              onClick={onGetStarted}
              className="h-10 rounded-full bg-white px-5 text-xs font-bold text-black transition-all hover:bg-slate-200 hover:scale-105 active:scale-95 shadow-md"
            >
              Get started
            </Button>
          </div>
        </div>
      </header>

      {/* ── 3. Hero Section (Exact Match to Uploaded Aesthetic) ── */}
      <section className="relative z-10 mx-auto max-w-5xl px-6 pt-20 pb-16 text-center sm:px-8 sm:pt-28">
        {/* Floating Announcement Pill */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 backdrop-blur-md"
        >
          <Sparkles className="size-3.5 text-amber-400" />
          <span className="font-mono text-xs font-medium text-slate-300">
            Announcing AIFlick 2.0 • Live Intelligence Layer
          </span>
        </motion.div>

        {/* Hero Title with Mixed Serif Italic Accent */}
        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="mt-8 text-4xl sm:text-6xl md:text-7xl font-bold tracking-tight text-white leading-[1.12]"
        >
          The intelligence layer <br />
          for clear <span className="font-serif italic font-normal text-slate-200">decisions.</span>
        </motion.h1>

        {/* Subtitle */}
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="mx-auto mt-6 max-w-2xl text-base sm:text-lg leading-relaxed text-slate-400"
        >
          Our platform integrates seamlessly into your workflow to deliver real-time social understanding, grounded in live signals from GitHub, Reddit, and Google Trends — not just predictions.
        </motion.p>

        {/* Dual CTA Buttons */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="mt-10 flex flex-wrap items-center justify-center gap-4"
        >
          <Button
            size="lg"
            onClick={onGetStarted}
            className="h-12 rounded-full bg-white px-8 text-sm font-bold text-black transition-all hover:bg-slate-200 hover:scale-105 active:scale-95 shadow-xl shadow-white/10"
          >
            Get started
          </Button>

          <Button
            size="lg"
            variant="outline"
            onClick={onGetStarted}
            className="h-12 rounded-full border-white/15 bg-white/5 px-8 text-sm font-semibold text-white backdrop-blur-md hover:bg-white/10 hover:border-white/30 transition-all"
          >
            Explore Studio
          </Button>
        </motion.div>

        {/* ── 4. Creator Badges Marquee ── */}
        <div className="mt-24 pt-8 border-t border-white/5">
          <p className="font-mono text-xs uppercase tracking-widest text-slate-500">
            Used by 1,000+ modern creators & growth teams
          </p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-2.5 sm:gap-3">
            {creatorBadges.map((badge) => (
              <span
                key={badge}
                className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.04] px-4 py-1.5 font-mono text-xs text-slate-300 backdrop-blur-md hover:border-primary/40 hover:text-white transition-colors"
              >
                <Sparkles className="size-3 text-primary" />
                {badge}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* ── 5. Features Section ── */}
      <section id="features" className="relative z-10 mx-auto max-w-7xl px-6 py-24 sm:px-8 border-t border-white/5">
        <div className="text-center max-w-2xl mx-auto">
          <h2 className="text-xs font-mono font-bold uppercase tracking-widest text-primary">
            Built For High-Output Creators
          </h2>
          <h3 className="mt-3 text-3xl sm:text-4xl font-bold tracking-tight text-white">
            Everything you need from trend signal to final graphic
          </h3>
        </div>

        <div className="mt-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f, i) => (
            <motion.div
              key={f.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: i * 0.08 }}
              className="group relative rounded-2xl border border-white/10 bg-white/[0.03] p-7 backdrop-blur-md transition-all hover:border-white/20 hover:bg-white/[0.06]"
            >
              <div className="grid size-10 place-items-center rounded-xl bg-white/5 border border-white/10 group-hover:scale-110 transition-transform">
                {f.icon}
              </div>
              <h4 className="mt-4 text-base font-bold text-white">{f.title}</h4>
              <p className="mt-2 text-sm leading-relaxed text-slate-400">{f.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ── 6. Pricing & Models Matrix ── */}
      <section id="pricing" className="relative z-10 mx-auto max-w-6xl px-6 py-24 sm:px-8 border-t border-white/5">
        <div className="text-center max-w-2xl mx-auto">
          <h2 className="text-xs font-mono font-bold uppercase tracking-widest text-primary">
            Transparent Pricing
          </h2>
          <h3 className="mt-3 text-3xl sm:text-4xl font-bold tracking-tight text-white">
            Start completely free. Upgrade when you scale.
          </h3>
        </div>

        <div className="mt-16 grid gap-6 md:grid-cols-3">
          {/* Free Explorer */}
          <div className="flex flex-col justify-between rounded-3xl border border-white/10 bg-white/[0.03] p-8 backdrop-blur-md">
            <div>
              <span className="font-mono text-xs font-bold uppercase tracking-wider text-emerald-400">
                100% Free Forever
              </span>
              <h4 className="mt-2 text-2xl font-bold text-white">Free Explorer</h4>
              <div className="mt-4 flex items-baseline gap-1">
                <span className="text-4xl font-black text-white">$0</span>
                <span className="text-xs text-slate-400">/ month</span>
              </div>
              <p className="mt-3 text-xs leading-relaxed text-slate-400">
                Full access for developers and creators testing AIFlick with open models.
              </p>

              <ul className="mt-6 space-y-3 text-xs text-slate-300 font-mono">
                <li className="flex items-center gap-2">
                  <Check className="size-3.5 text-emerald-400" /> Gemini 2.0 Flash text engine
                </li>
                <li className="flex items-center gap-2">
                  <Check className="size-3.5 text-emerald-400" /> FLUX.1-schnell image generator
                </li>
                <li className="flex items-center gap-2">
                  <Check className="size-3.5 text-emerald-400" /> 15 generations per day
                </li>
                <li className="flex items-center gap-2">
                  <Check className="size-3.5 text-emerald-400" /> Removable watermark
                </li>
              </ul>
            </div>
            <Button
              onClick={onGetStarted}
              variant="outline"
              className="mt-8 w-full rounded-full border-white/15 bg-white/5 text-white hover:bg-white/10"
            >
              Start Free
            </Button>
          </div>

          {/* Creator Pro */}
          <div className="relative flex flex-col justify-between rounded-3xl border border-primary/50 bg-primary/[0.06] p-8 backdrop-blur-md ring-2 ring-primary/30 shadow-2xl">
            <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-primary px-3 py-0.5 font-mono text-[11px] font-bold text-black">
              Most Popular
            </span>
            <div>
              <span className="font-mono text-xs font-bold uppercase tracking-wider text-primary">
                Solo Creators & Influencers
              </span>
              <h4 className="mt-2 text-2xl font-bold text-white">Creator Pro</h4>
              <div className="mt-4 flex items-baseline gap-1">
                <span className="text-4xl font-black text-white">$9</span>
                <span className="text-xs text-slate-400">/ month</span>
              </div>
              <p className="mt-3 text-xs leading-relaxed text-slate-400">
                Enhanced reasoning and studio graphics for daily content workflows.
              </p>

              <ul className="mt-6 space-y-3 text-xs text-slate-300 font-mono">
                <li className="flex items-center gap-2">
                  <Check className="size-3.5 text-primary" /> Gemini 2.5 Flash copy engine
                </li>
                <li className="flex items-center gap-2">
                  <Check className="size-3.5 text-primary" /> FLUX.1-Pro HD visual engine
                </li>
                <li className="flex items-center gap-2">
                  <Check className="size-3.5 text-primary" /> 75 generations per day
                </li>
                <li className="flex items-center gap-2">
                  <Check className="size-3.5 text-primary" /> 10-slide carousels
                </li>
                <li className="flex items-center gap-2">
                  <Check className="size-3.5 text-primary" /> Priority generation queue
                </li>
              </ul>
            </div>
            <Button
              onClick={onGetStarted}
              className="mt-8 w-full rounded-full bg-primary text-black font-bold hover:bg-primary-hover shadow-ember"
            >
              Get Creator Pro
            </Button>
          </div>

          {/* Agency Studio */}
          <div className="flex flex-col justify-between rounded-3xl border border-white/10 bg-white/[0.03] p-8 backdrop-blur-md">
            <div>
              <span className="font-mono text-xs font-bold uppercase tracking-wider text-amber-400">
                Studios & Media Brands
              </span>
              <h4 className="mt-2 text-2xl font-bold text-white">Agency Studio</h4>
              <div className="mt-4 flex items-baseline gap-1">
                <span className="text-4xl font-black text-white">$29</span>
                <span className="text-xs text-slate-400">/ month</span>
              </div>
              <p className="mt-3 text-xs leading-relaxed text-slate-400">
                Unlimited generations with deep reasoning and Google Imagen 3 visual fidelity.
              </p>

              <ul className="mt-6 space-y-3 text-xs text-slate-300 font-mono">
                <li className="flex items-center gap-2">
                  <Check className="size-3.5 text-amber-400" /> Gemini 2.5 Pro deep reasoning
                </li>
                <li className="flex items-center gap-2">
                  <Check className="size-3.5 text-amber-400" /> Google Imagen 3 art engine
                </li>
                <li className="flex items-center gap-2">
                  <Check className="size-3.5 text-amber-400" /> Unlimited generations
                </li>
                <li className="flex items-center gap-2">
                  <Check className="size-3.5 text-amber-400" /> 15-slide master carousels
                </li>
                <li className="flex items-center gap-2">
                  <Check className="size-3.5 text-amber-400" /> Dedicated worker pool
                </li>
              </ul>
            </div>
            <Button
              onClick={onGetStarted}
              variant="outline"
              className="mt-8 w-full rounded-full border-amber-500/30 bg-amber-500/10 text-amber-400 hover:bg-amber-500/20"
            >
              Get Agency Studio
            </Button>
          </div>
        </div>
      </section>

      {/* ── 7. FAQ Section ── */}
      <section id="faq" className="relative z-10 mx-auto max-w-4xl px-6 py-24 sm:px-8 border-t border-white/5">
        <div className="text-center max-w-xl mx-auto">
          <h2 className="text-xs font-mono font-bold uppercase tracking-widest text-primary">
            Frequently Asked Questions
          </h2>
          <h3 className="mt-3 text-3xl font-bold tracking-tight text-white">
            Everything you need to know
          </h3>
        </div>

        <div className="mt-12 space-y-3">
          {faqs.map((faq, idx) => {
            const isOpen = openFaq === idx;
            return (
              <div
                key={faq.q}
                className="rounded-2xl border border-white/10 bg-white/[0.03] backdrop-blur-md overflow-hidden transition-colors"
              >
                <button
                  type="button"
                  onClick={() => setOpenFaq(isOpen ? null : idx)}
                  className="flex w-full items-center justify-between p-5 text-left text-sm font-semibold text-white hover:text-primary transition-colors"
                >
                  <span>{faq.q}</span>
                  <ChevronDown className={`size-4 transition-transform ${isOpen ? "rotate-180 text-primary" : "text-slate-400"}`} />
                </button>
                <AnimatePresence initial={false}>
                  {isOpen && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.2 }}
                      className="px-5 pb-5 text-xs leading-relaxed text-slate-400 border-t border-white/5 pt-3"
                    >
                      {faq.a}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            );
          })}
        </div>
      </section>

      {/* ── 8. Footer ── */}
      <footer className="relative z-10 border-t border-white/5 bg-black/60 py-12 text-center">
        <div className="mx-auto max-w-7xl px-6 sm:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-white">AIFlick</span>
            <span className="text-xs text-slate-500">• AI Social Content & Visual Studio</span>
          </div>

          <div className="flex items-center gap-6 text-xs text-slate-400">
            <a href="#features" className="hover:text-white transition-colors">Features</a>
            <a href="#pricing" className="hover:text-white transition-colors">Pricing</a>
            <a href="#faq" className="hover:text-white transition-colors">FAQ</a>
            <button type="button" onClick={onGetStarted} className="text-primary font-semibold hover:underline">
              Launch Studio →
            </button>
          </div>

          <p className="text-xs text-slate-500">
            © {new Date().getFullYear()} AIFlick. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  );
}
