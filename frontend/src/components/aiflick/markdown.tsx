import { type ReactNode } from "react";

// Minimal markdown: **bold**, *italic*, `code`, and paragraph/list breaks.
// Deliberately small — the assistant replies use only these.
function renderInline(text: string, keyPrefix: string): ReactNode[] {
  if (typeof text !== "string") return [String(text ?? "")];
  const nodes: ReactNode[] = [];
  const pattern = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g;
  let last = 0;
  let match: RegExpExecArray | null;
  let i = 0;

  while ((match = pattern.exec(text))) {
    if (match.index > last) nodes.push(text.slice(last, match.index));
    const token = match[0];
    const key = `${keyPrefix}-${i++}`;
    if (token.startsWith("**")) {
      nodes.push(
        <strong key={key} className="font-semibold text-foreground">
          {token.slice(2, -2)}
        </strong>,
      );
    } else if (token.startsWith("`")) {
      nodes.push(
        <code
          key={key}
          className="rounded-md bg-secondary px-1.5 py-0.5 font-mono text-[0.85em] text-foreground"
        >
          {token.slice(1, -1)}
        </code>,
      );
    } else {
      nodes.push(
        <em key={key} className="italic">
          {token.slice(1, -1)}
        </em>,
      );
    }
    last = match.index + token.length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

export function Markdown({ content }: { content: string }) {
  const safeContent = typeof content === "string" ? content : (content ? String(content) : "");
  const blocks = safeContent.split(/\n{2,}/);

  return (
    <div className="space-y-3">
      {blocks.map((block, bi) => {
        const lines = block.split("\n");
        const isList = lines.every((l) => /^\s*[-*]\s+/.test(l));

        if (isList) {
          return (
            <ul key={bi} className="space-y-1.5 pl-4">
              {lines.map((line, li) => (
                <li key={li} className="list-disc marker:text-primary">
                  {renderInline(line.replace(/^\s*[-*]\s+/, ""), `${bi}-${li}`)}
                </li>
              ))}
            </ul>
          );
        }

        return (
          <p key={bi} className="leading-relaxed">
            {renderInline(block, String(bi))}
          </p>
        );
      })}
    </div>
  );
}
