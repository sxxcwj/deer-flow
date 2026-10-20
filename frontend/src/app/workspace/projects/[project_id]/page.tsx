import { ProjectDetail } from "@/components/workspace/projects/project-detail";

export default async function WorkspaceProjectPage({
  params,
}: {
  params: Promise<{ project_id: string }>;
}) {
  const { project_id } = await params;
  return <ProjectDetail projectId={project_id} />;
}
