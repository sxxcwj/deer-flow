"use client";

import { useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/core/i18n/hooks";
import { useCreateMethod, useDeleteMethod, useMethods } from "@/core/methods/hooks";

export function MethodsPage() {
  const { t } = useI18n();
  const { methods, isLoading } = useMethods();
  const createMethod = useCreateMethod();
  const deleteMethod = useDeleteMethod();
  const fileInput = useRef<HTMLInputElement>(null);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");

  async function handleAdd() {
    const trimmed = title.trim();
    if (!trimmed) {
      toast.error(t.methods.titleRequired);
      return;
    }
    try {
      await createMethod.mutateAsync({
        title: trimmed,
        body: body.trim(),
        file: fileInput.current?.files?.[0],
      });
      setTitle("");
      setBody("");
      if (fileInput.current) fileInput.current.value = "";
      toast.success(t.methods.added);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <div className="cb-page flex size-full flex-col">
      <div className="cb-page-head">
        <h1>{t.methods.title}</h1>
        <p className="cb-kicker">{t.methods.description}</p>
      </div>
      <div className="cb-page-body">
        <form
          className="flex flex-col gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            void handleAdd();
          }}
        >
          <input
            className="cb-field"
            value={title}
            placeholder={t.methods.titlePlaceholder}
            onChange={(event) => setTitle(event.target.value)}
          />
          <textarea
            className="cb-field h-auto min-h-16 py-2"
            value={body}
            placeholder={t.methods.bodyPlaceholder}
            onChange={(event) => setBody(event.target.value)}
          />
          <div className="flex items-center gap-2">
            <input
              ref={fileInput}
              className="cb-meta min-w-0 flex-1"
              type="file"
              accept=".txt,.md,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx"
            />
            <button className="cb-action" type="submit" disabled={createMethod.isPending}>
              {t.methods.add}
            </button>
          </div>
        </form>
        {isLoading ? (
          <p className="cb-meta mt-4">{t.common.loading}</p>
        ) : methods.length === 0 ? (
          <p className="cb-meta mt-4">{t.methods.empty}</p>
        ) : (
          <ul className="cb-list mt-4">
            {methods.map((method) => (
              <li key={method.id} className="cb-row items-start">
                <div className="min-w-0 flex-1">
                  <div>{method.title}</div>
                  {method.body ? <p className="cb-meta mt-0.5">{method.body}</p> : null}
                  {method.filename ? <p className="cb-meta mt-0.5">{method.filename}</p> : null}
                </div>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  disabled={deleteMethod.isPending}
                  onClick={() => {
                    void deleteMethod
                      .mutateAsync(method.id)
                      .then(() => toast.success(t.methods.deleted))
                      .catch((err: unknown) => {
                        toast.error(err instanceof Error ? err.message : String(err));
                      });
                  }}
                >
                  {t.common.delete}
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
