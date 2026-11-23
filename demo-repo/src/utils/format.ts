// Formatting helpers

export function formatUser(user: { name: string; email: string }): string {
  return `${user.name} <${user.email}>`;
}

export function formatList(items: string[]): string {
  return items.join(", ");
}
