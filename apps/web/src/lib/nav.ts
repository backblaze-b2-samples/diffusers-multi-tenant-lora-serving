import {
  FolderOpen,
  Layers,
  LayoutDashboard,
  Library,
  ListChecks,
  Settings,
  Sparkles,
  Wand2,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  title: string;
  href: string;
  icon: LucideIcon;
}

/** Primary navigation, shared by the sidebar, the header and the ⌘K palette. */
export const NAV_ITEMS: NavItem[] = [
  { title: "Dashboard", href: "/", icon: LayoutDashboard },
  { title: "Adapters", href: "/adapters", icon: Layers },
  { title: "Generate", href: "/generate", icon: Wand2 },
  { title: "Runs", href: "/runs", icon: ListChecks },
  { title: "Library", href: "/library", icon: Library },
  { title: "Files", href: "/files", icon: FolderOpen },
  { title: "Settings", href: "/settings", icon: Settings },
];

export const UTIL_ITEMS: NavItem[] = [
  { title: "Design System", href: "/design", icon: Sparkles },
];

/** True when `pathname` is `href` or one of its child pages. */
export function isActivePath(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}
