'use client';

import { useMemo } from 'react';
import { ScrollArea } from '../ui/scroll-area';

interface MarkdownViewerProps {
  content: string;
  className?: string;
}

/**
 * Simple markdown viewer for reports.
 * Renders markdown content with basic styling.
 * For Phase 1, uses simple parsing - can be enhanced with a full markdown library later.
 */
export function MarkdownViewer({ content, className = '' }: MarkdownViewerProps) {
  // Basic markdown-to-HTML conversion
  const html = useMemo(() => {
    let processed = content;

    // Headers
    processed = processed.replace(/^### (.+)$/gm, '<h3 class="text-lg font-semibold mt-4 mb-2">$1</h3>');
    processed = processed.replace(/^## (.+)$/gm, '<h2 class="text-xl font-semibold mt-6 mb-3">$1</h2>');
    processed = processed.replace(/^# (.+)$/gm, '<h1 class="text-2xl font-bold mt-8 mb-4">$1</h1>');

    // Bold & Italic
    processed = processed.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    processed = processed.replace(/\*(.+?)\*/g, '<em>$1</em>');

    // Code blocks
    processed = processed.replace(/```(\w+)?\n([\s\S]+?)```/g, (_, lang, code) => {
      return `<pre class="bg-gray-100 p-4 rounded-lg overflow-x-auto my-4"><code class="text-sm font-mono">${escapeHtml(code.trim())}</code></pre>`;
    });

    // Inline code
    processed = processed.replace(/`(.+?)`/g, '<code class="bg-gray-100 px-1.5 py-0.5 rounded text-sm font-mono">$1</code>');

    // Links
    processed = processed.replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" class="text-blue-600 hover:underline">$1</a>');

    // Lists
    processed = processed.replace(/^- (.+)$/gm, '<li class="ml-4">• $1</li>');
    processed = processed.replace(/^(\d+)\. (.+)$/gm, '<li class="ml-4">$1. $2</li>');

    // Blockquotes
    processed = processed.replace(/^> (.+)$/gm, '<blockquote class="border-l-4 border-gray-300 pl-4 italic text-gray-700 my-2">$1</blockquote>');

    // Horizontal rules
    processed = processed.replace(/^---$/gm, '<hr class="my-6 border-t border-gray-300" />');

    // Paragraphs (lines separated by blank lines)
    const lines = processed.split('\n');
    const paragraphs: string[] = [];
    let currentParagraph = '';

    for (const line of lines) {
      if (line.trim() === '') {
        if (currentParagraph) {
          // Don't wrap if it's already an HTML element
          if (currentParagraph.match(/^<(h\d|pre|blockquote|hr|li)/)) {
            paragraphs.push(currentParagraph);
          } else {
            paragraphs.push(`<p class="my-2">${currentParagraph}</p>`);
          }
          currentParagraph = '';
        }
      } else {
        currentParagraph += (currentParagraph ? ' ' : '') + line;
      }
    }
    if (currentParagraph) {
      if (currentParagraph.match(/^<(h\d|pre|blockquote|hr|li)/)) {
        paragraphs.push(currentParagraph);
      } else {
        paragraphs.push(`<p class="my-2">${currentParagraph}</p>`);
      }
    }

    return paragraphs.join('\n');
  }, [content]);

  return (
    <ScrollArea className={`h-full ${className}`}>
      <div
        className="prose prose-sm max-w-none p-4"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </ScrollArea>
  );
}

// Helper to escape HTML
function escapeHtml(text: string): string {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
