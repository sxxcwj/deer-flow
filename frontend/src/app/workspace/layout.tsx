import { type Metadata } from "next";
import { cookies } from "next/headers";
import type { CSSProperties } from "react";
import { Toaster } from "sonner";

import { QueryClientProvider } from "@/components/query-client-provider";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { CommandPalette } from "@/components/workspace/command-palette";
import { WorkspaceSidebar } from "@/components/workspace/workspace-sidebar";
import "@/components/workspace/workbench-shell.css";

function parseSidebarOpenCookie(
  value: string | undefined,
): boolean | undefined {
  if (value === "true") return true;
  if (value === "false") return false;
  return undefined;
}

export const metadata: Metadata = {
  title: "长伴咨询",
};

export default async function WorkspaceLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const cookieStore = await cookies();
  const initialSidebarOpen = parseSidebarOpenCookie(
    cookieStore.get("sidebar_state")?.value,
  );

  return (
    <QueryClientProvider>
      <SidebarProvider
        className="cb-shell h-screen"
        style={{ "--sidebar-width": "232px" } as CSSProperties}
        defaultOpen={initialSidebarOpen}
      >
        <WorkspaceSidebar />
        <SidebarInset className="min-w-0">{children}</SidebarInset>
      </SidebarProvider>
      <CommandPalette />
      <Toaster position="top-center" />
    </QueryClientProvider>
  );
}
