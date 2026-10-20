"use client";

import { AgentAvatar } from "@/components/workspace/agents/agent-avatar";
import { type Agent } from "@/core/agents";
import { cn } from "@/lib/utils";

export function AgentWelcome({
  className,
  agent,
  agentName,
}: {
  className?: string;
  agent: Agent | null | undefined;
  agentName: string;
}) {
  const displayName = agent?.name ?? agentName;
  const description = agent?.description;

  return (
    <div
      className={cn(
        "mx-auto flex w-full flex-col items-center justify-center gap-2 px-8 py-4 text-center",
        className,
      )}
    >
      <AgentAvatar
        name={agentName}
        avatar={agent?.avatar}
        editable
        className="h-12 w-12 rounded-full text-2xl"
      />
      <div className="text-2xl font-bold">{displayName}</div>
      {description && (
        <p className="text-muted-foreground max-w-sm text-sm">{description}</p>
      )}
    </div>
  );
}
