"use client";

import { useQuery } from "@tanstack/react-query";
import {
  BookOpenIcon,
  BotIcon,
  FolderKanbanIcon,
  MessagesSquare,
  MessageSquarePlus,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { useI18n } from "@/core/i18n/hooks";
import { hrefOfHit, searchWorkbench } from "@/core/search/api";
import { useThreads } from "@/core/threads/hooks";
import { pathOfThread, titleOfThread } from "@/core/threads/utils";

const entries = [
  {
    href: "/workspace/chats/new",
    icon: MessageSquarePlus,
    titleKey: "newChat",
    hintKey: "newChatHint",
  },
  {
    href: "/workspace/agents",
    icon: BotIcon,
    titleKey: "agents",
    hintKey: "agentsHint",
  },
  {
    href: "/workspace/chats",
    icon: MessagesSquare,
    titleKey: "chats",
    hintKey: "chatsHint",
  },
  {
    href: "/workspace/projects",
    icon: FolderKanbanIcon,
    titleKey: "projects",
    hintKey: "projectsHint",
  },
  {
    href: "/workspace/methods",
    icon: BookOpenIcon,
    titleKey: "methods",
    hintKey: "methodsHint",
  },
] as const;

export function WorkbenchHome() {
  const { t } = useI18n();
  const [draft, setDraft] = useState("");
  const [submitted, setSubmitted] = useState("");
  const { data: threads = [], isLoading } = useThreads({
    limit: submitted ? 50 : 6,
    sortBy: "updated_at",
    sortOrder: "desc",
    select: ["thread_id", "updated_at", "values", "metadata"],
  });
  const search = useQuery({
    queryKey: ["workbench-search", submitted],
    queryFn: () => searchWorkbench(submitted),
    enabled: submitted.length > 0,
  });
  const matchedThreads = submitted
    ? threads.filter((thread) =>
        titleOfThread(thread).toLowerCase().includes(submitted.toLowerCase()),
      )
    : [];

  const shortcuts = entries.filter((entry) => entry.titleKey !== "newChat");

  return (
    <div className="cb-page flex size-full flex-col">
      <div className="cb-page-head">
        <h1>{t.workbench.title}</h1>
        <p className="cb-kicker">{t.workbench.lede}</p>
        <form
          className="mt-3"
          onSubmit={(event) => {
            event.preventDefault();
            setSubmitted(draft.trim());
          }}
        >
          <input
            className="cb-field w-full max-w-md"
            value={draft}
            placeholder={t.search.placeholder}
            onChange={(event) => setDraft(event.target.value)}
          />
        </form>
        <Link className="cb-action mt-3" href="/workspace/chats/new">
          {t.workbench.newChat}
        </Link>
      </div>
      <div className="cb-page-body">
        {submitted ? (
          <SearchResults
            loading={search.isLoading}
            emptyLabel={t.search.empty}
            hits={(search.data ?? []).map((hit) => ({
              key: `${hit.kind}-${hit.target_id}`,
              href: hrefOfHit(hit),
              label: t.search[hit.kind],
              title: hit.title,
              snippet: hit.snippet,
            }))}
            chats={matchedThreads.map((thread) => ({
              key: thread.thread_id,
              href: pathOfThread(thread),
              label: t.search.chat,
              title: titleOfThread(thread),
              snippet: "",
            }))}
          />
        ) : null}
        <ul className="cb-list">
          {shortcuts.map((entry) => {
            const Icon = entry.icon;
            return (
              <li key={entry.href}>
                <Link href={entry.href} className="cb-row">
                  <span className="flex min-w-0 items-center gap-2">
                    <Icon className="size-4 shrink-0" />
                    <span className="truncate">{t.workbench[entry.titleKey]}</span>
                  </span>
                  <span className="cb-meta hidden truncate sm:block">
                    {t.workbench[entry.hintKey]}
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
        <h2 className="cb-section">{t.workbench.recent}</h2>
        {isLoading ? (
          <p className="cb-meta">{t.common.loading}</p>
        ) : threads.length === 0 ? (
          <p className="cb-meta">{t.workbench.recentEmpty}</p>
        ) : (
          <ul className="cb-list">
            {threads.map((thread) => (
              <li key={thread.thread_id}>
                <Link href={pathOfThread(thread)} className="cb-row">
                  <span className="truncate">{titleOfThread(thread)}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function SearchResults({
  loading,
  emptyLabel,
  hits,
  chats,
}: {
  loading: boolean;
  emptyLabel: string;
  hits: { key: string; href: string; label: string; title: string; snippet: string }[];
  chats: { key: string; href: string; label: string; title: string; snippet: string }[];
}) {
  const rows = [...hits, ...chats];
  if (loading) return null;
  if (rows.length === 0) return <p className="cb-meta mb-4">{emptyLabel}</p>;
  return (
    <ul className="cb-list mb-4">
      {rows.map((row) => (
        <li key={row.key}>
          <Link href={row.href} className="cb-row">
            <span className="min-w-0 flex-1 truncate">
              <span className="cb-meta mr-2">{row.label}</span>
              {row.title}
            </span>
            {row.snippet ? <span className="cb-meta hidden max-w-[40%] truncate sm:block">{row.snippet}</span> : null}
          </Link>
        </li>
      ))}
    </ul>
  );
}
