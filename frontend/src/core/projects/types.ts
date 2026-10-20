export interface ProjectOutput {
  id: string;
  title: string;
  note: string;
  created_at: string;
}

export interface ProjectMaterial {
  id: string;
  filename: string;
  size: number;
  created_at: string;
}

export interface Project {
  id: string;
  name: string;
  summary: string;
  thread_ids: string[];
  outputs: ProjectOutput[];
  materials: ProjectMaterial[];
  updated_at: string;
}
