"use client";

import { BotIcon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useUpdateAgent } from "@/core/agents";
import { avatarKind } from "@/core/agents/avatar";
import { useI18n } from "@/core/i18n/hooks";
import { cn } from "@/lib/utils";

const SUGGESTED_AVATARS = ["🦌", "🦊", "🦉", "🌿", "☕", "📚", "🎯", "🧭"];

export function AgentAvatar({
  name,
  avatar,
  className,
  editable = false,
}: {
  name: string;
  avatar?: string | null;
  className?: string;
  editable?: boolean;
}) {
  const { t } = useI18n();
  const updateAgent = useUpdateAgent();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(avatar ?? "");
  const [imageFailed, setImageFailed] = useState(false);

  const face = (
    <AvatarFace
      avatar={avatar}
      imageFailed={imageFailed}
      onImageError={() => setImageFailed(true)}
    />
  );

  if (!editable) {
    return (
      <div
        className={cn(
          "bg-primary/10 text-primary flex shrink-0 items-center justify-center overflow-hidden",
          className,
        )}
      >
        {face}
      </div>
    );
  }

  async function save(next: string) {
    try {
      await updateAgent.mutateAsync({
        name,
        request: { avatar: next },
      });
      setImageFailed(false);
      setOpen(false);
      toast.success(t.agents.avatarSaved);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t.agents.avatarSaveFailed);
    }
  }

  return (
    <>
      <button
        type="button"
        className={cn(
          "bg-primary/10 text-primary flex shrink-0 items-center justify-center overflow-hidden",
          className,
        )}
        aria-label={t.agents.changeAvatar}
        onClick={(event) => {
          event.stopPropagation();
          setDraft(avatar ?? "");
          setOpen(true);
        }}
      >
        {face}
      </button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t.agents.changeAvatar}</DialogTitle>
            <DialogDescription>{t.agents.avatarHint}</DialogDescription>
          </DialogHeader>
          <div className="flex flex-wrap gap-2">
            {SUGGESTED_AVATARS.map((emoji) => (
              <button
                key={emoji}
                type="button"
                className="hover:bg-accent flex h-10 w-10 items-center justify-center rounded-md text-xl"
                onClick={() => setDraft(emoji)}
              >
                {emoji}
              </button>
            ))}
          </div>
          <Input
            value={draft}
            placeholder={t.agents.avatarPlaceholder}
            onChange={(event) => setDraft(event.target.value)}
          />
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => void save("")}
              disabled={updateAgent.isPending}
            >
              {t.agents.avatarUseDefault}
            </Button>
            <Button
              onClick={() => void save(draft.trim())}
              disabled={updateAgent.isPending}
            >
              {t.common.save}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function AvatarFace({
  avatar,
  imageFailed,
  onImageError,
}: {
  avatar?: string | null;
  imageFailed: boolean;
  onImageError: () => void;
}) {
  const kind = avatarKind(avatar);
  if (kind === "image" && avatar && !imageFailed) {
    return (
      // User-supplied image URL. Rendering is limited to http(s) by avatarKind.
      <img
        src={avatar}
        alt=""
        className="h-full w-full object-cover"
        onError={onImageError}
      />
    );
  }
  if (kind === "text" && avatar) {
    return <span className="text-[1.35em] leading-none">{avatar.trim()}</span>;
  }
  return <BotIcon className="h-1/2 w-1/2" />;
}
