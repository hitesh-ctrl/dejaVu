// Demo app: a simple user record store
// This file intentionally has a quirky API to trigger agent edits.

export interface User {
  id: number;
  name: string;
  email: string;
  active: boolean;
}

const users: User[] = [
  { id: 1, name: "Alice", email: "alice@example.com", active: true },
  { id: 2, name: "Bob", email: "bob@example.com", active: false },
];

export function getUser(id: number): User | undefined {
  return users.find((u) => u.id === id);
}

export function listActive(): User[] {
  return users.filter((u) => u.active);
}

export function addUser(name: string, email: string): User {
  const user: User = { id: users.length + 1, name, email, active: true };
  users.push(user);
  return user;
}
