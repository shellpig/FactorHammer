"use client";

// Sidebar component (Phase 10-B)
// PC (lg+): fixed left sidebar 240px
// Mobile (<lg): fixed bottom tab bar with 5 icons

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BarChart3,
  TrendingUp,
  FolderOpen,
  Bot,
  Settings,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useCommandPaletteEntry } from "@/hooks/use-command-palette";

interface NavItem {
  label: string;
  shortLabel: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
}

const NAV_ITEMS: NavItem[] = [
  { label: "個股分析", shortLabel: "分析",  href: "/dashboard", icon: BarChart3 },
  { label: "回測研究", shortLabel: "回測",  href: "/backtest",  icon: TrendingUp },
  { label: "資料管理", shortLabel: "資料",  href: "/data",      icon: FolderOpen },
  { label: "AI 問答",  shortLabel: "AI",    href: "/ai",        icon: Bot },
  { label: "設定",     shortLabel: "設定",  href: "/settings",  icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();

  useCommandPaletteEntry({
    id: "nav-dashboard",
    group: "pages",
    label: "個股分析",
    action: () => router.push("/dashboard"),
  });
  useCommandPaletteEntry({
    id: "nav-data",
    group: "pages",
    label: "資料管理",
    action: () => router.push("/data"),
  });
  useCommandPaletteEntry({
    id: "nav-backtest",
    group: "pages",
    label: "回測研究",
    action: () => router.push("/backtest"),
  });
  useCommandPaletteEntry({
    id: "nav-ai",
    group: "pages",
    label: "AI 問答",
    action: () => router.push("/ai"),
  });
  useCommandPaletteEntry({
    id: "nav-settings",
    group: "pages",
    label: "設定",
    action: () => router.push("/settings"),
  });

  return (
    <>
      {/* ── PC: left fixed sidebar ── */}
      <aside className="hidden lg:flex lg:flex-col lg:fixed lg:inset-y-0 lg:left-0 lg:w-32 lg:border-r lg:border-border lg:bg-card lg:z-40">
        {/* Logo */}
        <div className="flex h-16 items-center px-3 border-b border-border">
          <div className="flex flex-col">
            <span className="text-base font-bold text-foreground tracking-tight" data-testid="sidebar-app-name">
              FactorHammer
            </span>
            <span className="text-[10px] text-muted-foreground" data-testid="sidebar-app-version">
              v{process.env.NEXT_PUBLIC_APP_VERSION}
            </span>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex flex-col gap-1 p-2 flex-1 overflow-y-auto">
          {NAV_ITEMS.map((item) => (
            <SidebarLink key={item.href} item={item} active={pathname === item.href} />
          ))}
        </nav>
      </aside>

      {/* ── Mobile: bottom tab bar ── */}
      {/* Phase 14-B: bg-background utility currently not emitted; use arbitrary value until @theme ticket. */}
      <nav
        className="lg:hidden fixed bottom-0 left-0 right-0 z-50 h-14 bg-[hsl(var(--background))] border-t border-border"
        aria-label="手機底部導覽"
      >
        <div className="grid grid-cols-5 h-full">
          {NAV_ITEMS.map((item) => (
            <MobileTabItem key={item.href} item={item} active={pathname === item.href} />
          ))}
        </div>
      </nav>
    </>
  );
}

function SidebarLink({ item, active }: { item: NavItem; active: boolean }) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      className={cn(
        "flex flex-col rounded-lg px-2 py-2 text-sm font-medium transition-colors",
        active
          ? "bg-primary/10 text-primary"
          : "text-muted-foreground hover:bg-muted hover:text-foreground",
      )}
      aria-current={active ? "page" : undefined}
      data-testid={`sidebar-nav-${item.href.slice(1)}`}
    >
      <span className="flex items-center gap-2">
        <Icon className="h-5 w-5 shrink-0" />
        {item.label}
      </span>
      {item.badge && (
        <span
          className="mt-0.5 self-start rounded-full bg-slate-700/40 px-1.5 py-px text-[10px] font-normal text-slate-400"
          data-testid={`sidebar-badge-${item.href.slice(1)}`}
        >
          {item.badge}
        </span>
      )}
    </Link>
  );
}

function MobileTabItem({ item, active }: { item: NavItem; active: boolean }) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      className={cn(
        "flex flex-col items-center justify-center gap-0.5 transition-colors",
        active ? "text-primary" : "text-muted-foreground",
      )}
      aria-current={active ? "page" : undefined}
      data-testid={`mobile-nav-${item.href.slice(1)}`}
    >
      <Icon className="h-5 w-5" />
      <span className="text-[10px] font-medium">{item.shortLabel}</span>
    </Link>
  );
}
