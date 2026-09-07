import type { Conversation, Message, User } from "./types";

/** Sample data. The backend exposes no conversation API yet (only /api/health),
 *  so screens render from here until those endpoints land. */
const u = (id: number, username: string, displayName: string, isOnline = false,
           lastSeen: string | null = null): User =>
  ({ id, username, displayName, avatarUrl: null, isOnline, lastSeen });

export const me = u(1, "ayush", "Ayush Swamy", true);
export const priya = u(2, "priya", "Priya Nair", true);
export const maya = u(3, "maya", "Maya Iyer", true);
export const dev = u(4, "devsharma", "Dev Sharma", false, "2h ago");
export const rohan = u(5, "rohan", "Rohan Mehta", false, "yesterday");
export const aditi = u(6, "aditi", "Aditi Rao", false, "yesterday");
export const karan = u(7, "karan", "Karan Singh", false, "Monday");

export const directory: User[] = [priya, maya, dev, rohan, aditi, karan];

export const conversations: Conversation[] = [
  { id: 1, type: "direct", name: null,
    participants: [{ user: me, role: "member" }, { user: priya, role: "member" }],
    lastMessage: "See you at 7 then", lastActivity: "09:24", unreadCount: 0, muted: false },
  { id: 2, type: "group", name: "Design Guild",
    participants: [{ user: me, role: "admin" }, { user: maya, role: "admin" },
                   { user: dev, role: "member" }, { user: priya, role: "member" },
                   { user: rohan, role: "member" }],
    lastMessage: "Maya: pushed the new tokens", lastActivity: "08:55", unreadCount: 3, muted: false },
  { id: 3, type: "direct", name: null,
    participants: [{ user: me, role: "member" }, { user: rohan, role: "member" }],
    lastMessage: "Thanks, that helps", lastActivity: "Yesterday", unreadCount: 0, muted: true },
  { id: 4, type: "direct", name: null,
    participants: [{ user: me, role: "member" }, { user: aditi, role: "member" }],
    lastMessage: "Can you check the draft?", lastActivity: "Yesterday", unreadCount: 1, muted: false },
  { id: 5, type: "direct", name: null,
    participants: [{ user: me, role: "member" }, { user: karan, role: "member" }],
    lastMessage: "Sounds good to me", lastActivity: "Monday", unreadCount: 0, muted: false },
];

const msg = (id: number, conversationId: number, sender: User, content: string,
             createdAt: string, status: Message["status"] = null,
             replyTo: Message["replyTo"] = null, editedAt: string | null = null): Message =>
  ({ id, conversationId, sender, content, createdAt, editedAt, status, replyTo });

export const messages: Record<number, Message[]> = {
  1: [
    msg(1, 1, priya, "Are we still on for dinner tonight?", "09:02"),
    msg(2, 1, me, "Yes — 7pm at the usual place.", "09:03", "read"),
    msg(3, 1, me, "I booked a table under my name.", "09:04", "read", null, "09:05"),
    msg(4, 1, priya, "Perfect. I'll head straight from the office.", "09:06",
        null, { sender: "You", content: "Yes — 7pm at the usual place." }),
    msg(5, 1, priya, "See you at 7 then", "09:24"),
  ],
  2: [
    msg(6, 2, me, "Did the new tokens land?", "08:40", "read"),
    msg(7, 2, maya, "Pushed the new tokens to the shared library.", "08:52"),
    msg(8, 2, maya, "Light and dark both covered.", "08:53"),
    msg(9, 2, dev, "Nice — I'll rebind the components this afternoon.", "08:55"),
  ],
  3: [msg(10, 3, rohan, "Thanks, that helps", "Yesterday")],
  4: [msg(11, 4, aditi, "Can you check the draft?", "Yesterday")],
  5: [msg(12, 5, karan, "Sounds good to me", "Monday")],
};

export function counterpart(c: Conversation): User {
  return c.participants.find((p) => p.user.id !== me.id)?.user ?? priya;
}
export function title(c: Conversation): string {
  return c.type === "group" ? (c.name ?? "Group") : counterpart(c).displayName;
}
export function initials(name: string): string {
  return name.split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase();
}
