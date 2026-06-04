import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: vi.fn(() => "/dashboard"),
  useRouter: () => ({ push: mockPush }),
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...rest
  }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

vi.mock("@/hooks/use-command-palette", () => ({
  useCommandPaletteEntry: () => undefined,
}));

import { Sidebar } from "@/components/sidebar";
import { usePathname } from "next/navigation";

const PAGES = [
  { testid: "mobile-nav-dashboard", label: "分析", href: "/dashboard" },
  { testid: "mobile-nav-backtest",  label: "回測", href: "/backtest" },
  { testid: "mobile-nav-data",      label: "資料", href: "/data" },
  { testid: "mobile-nav-active-etf",label: "ETF",  href: "/active-etf" },
  { testid: "mobile-nav-ai",        label: "AI",   href: "/ai" },
  { testid: "mobile-nav-settings",  label: "設定", href: "/settings" },
];

describe("MobileTabBar", () => {
  it("renders 6 mobile nav items", () => {
    render(<Sidebar />);
    const items = screen.getAllByTestId(/mobile-nav-/);
    expect(items.length).toBe(6);
  });

  it.each(PAGES)("renders $testid with shortLabel $label", ({ testid, label }) => {
    render(<Sidebar />);
    const item = screen.getByTestId(testid);
    expect(item).toBeInTheDocument();
    expect(item.textContent).toContain(label);
  });

  it.each(PAGES)("$testid links to $href", ({ testid, href }) => {
    render(<Sidebar />);
    const item = screen.getByTestId(testid);
    expect(item).toHaveAttribute("href", href);
  });

  it("active item has aria-current=page when pathname matches", () => {
    vi.mocked(usePathname).mockReturnValue("/dashboard");
    render(<Sidebar />);
    expect(screen.getByTestId("mobile-nav-dashboard")).toHaveAttribute(
      "aria-current",
      "page"
    );
    expect(screen.getByTestId("mobile-nav-backtest")).not.toHaveAttribute(
      "aria-current"
    );
  });

  it("non-active items do not have aria-current", () => {
    vi.mocked(usePathname).mockReturnValue("/settings");
    render(<Sidebar />);
    const settingsItem = screen.getByTestId("mobile-nav-settings");
    expect(settingsItem).toHaveAttribute("aria-current", "page");
    const dashboardItem = screen.getByTestId("mobile-nav-dashboard");
    expect(dashboardItem).not.toHaveAttribute("aria-current");
  });
});
