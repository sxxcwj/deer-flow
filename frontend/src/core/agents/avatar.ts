export function avatarKind(
  avatar: string | null | undefined,
): "image" | "text" | "empty" {
  const value = avatar?.trim() ?? "";
  if (!value) return "empty";
  if (/^https?:\/\//i.test(value)) return "image";
  return "text";
}
