export type Role = "user" | "assistant";

export type PostEdit = {
  id: string;
  instruction: string;
  atLabel: string;
};

export type GeneratedPost = {
  id: string;
  platform: string;
  title: string;
  hook: string;
  caption: string;
  hashtags: string[];
  sourceUrl: string;
  sourceLabel: string;
  edits?: PostEdit[];
};

export type ChatMessage = {
  id: string;
  role: Role;
  content: string;
  posts?: GeneratedPost[];
};

export type Session = {
  id: string;
  title: string;
  updatedLabel: string;
};

export const PLATFORMS = [
  { value: "auto", label: "Auto-detect" },
  { value: "instagram", label: "Instagram" },
  { value: "linkedin", label: "LinkedIn" },
  { value: "x", label: "X / Twitter" },
  { value: "youtube", label: "YouTube" },
  { value: "reddit", label: "Reddit" },
] as const;

export const POST_COUNTS = [1, 3, 5, 8, 10] as const;

export const SOURCES = [
  "GitHub",
  "Reddit",
  "Google Trends",
  "HackerNews",
  "YouTube",
  "Tavily",
  "PapersWithCode",
] as const;

export const SUGGESTED_PROMPTS = [
  {
    title: "5 Instagram posts about Docker deployment",
    hint: "pulls from GitHub + HackerNews",
  },
  {
    title: "3 LinkedIn posts on AI agent frameworks",
    hint: "pulls from PapersWithCode + Reddit",
  },
  {
    title: "What's trending in local-first apps this week?",
    hint: "pulls from Google Trends + Tavily",
  },
  {
    title: "5 X threads about Rust performance wins",
    hint: "pulls from GitHub + YouTube",
  },
];

export const DEMO_SESSIONS: Session[] = [
  { id: "s1", title: "Docker deployment carousel", updatedLabel: "2m ago" },
  { id: "s2", title: "AI agent frameworks roundup", updatedLabel: "Yesterday" },
  { id: "s3", title: "Local-first app trends", updatedLabel: "Tuesday" },
  { id: "s4", title: "Rust performance thread ideas", updatedLabel: "Last week" },
];

export const DEMO_MESSAGES: ChatMessage[] = [
  {
    id: "m1",
    role: "user",
    content: "generate 5 instagram posts about docker deployment",
  },
  {
    id: "m2",
    role: "assistant",
    content:
      "I pulled **14 live items** from GitHub, HackerNews and Reddit and kept the 5 strongest angles. Each post is written for Instagram, hook first, with the source it came from.",
    posts: [
      {
        id: "p1",
        platform: "instagram",
        title: "Multi-stage builds cut our image 82%",
        hook: "Your Docker image is probably 4x bigger than it needs to be.",
        caption:
          "A multi-stage build ships only the final artifact — no compilers, no dev deps, no cache. One team took a 1.2GB Node image down to 210MB by moving the build into a throwaway stage.\n\nThe trick: build in one stage, COPY --from into a slim runtime stage, and never let your toolchain reach production.",
        hashtags: ["#docker", "#devops", "#containers"],
        sourceUrl: "https://github.com",
        sourceLabel: "GitHub",
      },
      {
        id: "p2",
        platform: "instagram",
        title: "Distroless is quietly winning",
        hook: "No shell. No package manager. Nothing to exploit.",
        caption:
          "Distroless images strip the OS down to your runtime. Smaller surface, faster pulls, fewer CVEs in the scan report on Monday morning.\n\nDebugging gets harder — that's the trade. Keep a debug variant around for the days you need a shell.",
        hashtags: ["#docker", "#security", "#platformengineering"],
        sourceUrl: "https://news.ycombinator.com",
        sourceLabel: "HackerNews",
        edits: [
          { id: "e1", instruction: "make the hook shorter", atLabel: "1m ago" },
        ],
      },
      {
        id: "p3",
        platform: "instagram",
        title: "Your layer cache order is backwards",
        hook: "COPY . . before installing deps? That's a rebuild every commit.",
        caption:
          "Copy your lockfile first, install, then copy source. Docker reuses the dependency layer until the lockfile actually changes — minutes back on every CI run.",
        hashtags: ["#docker", "#ci", "#devex"],
        sourceUrl: "https://reddit.com",
        sourceLabel: "Reddit",
      },
    ],
  },
];
