// Tests for Sidebar component (Phase 10-F-1)
// Verifies the "後續開放" badge appears on the AI 問答 nav item.

import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

const mockPush = vi.fn();

// Mock next/navigation (usePathname + useRouter)
vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  useRouter: () => ({ push: mockPush }),
}));

// Mock next/link
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...rest}>{children}</a>
  ),
}));

import { Sidebar } from "@/components/sidebar";

vi.mock("@/hooks/use-command-palette", () => ({
  useCommandPaletteEntry: () => undefined,
}));

describe("Sidebar", () => {
  it("renders all 5 nav items", () => {
    render(<Sidebar />);
    expect(screen.getAllByTestId(/sidebar-nav-/).length).toBeGreaterThanOrEqual(5);
  });

  it("AI 問答 nav item exists", () => {
    render(<Sidebar />);
    expect(screen.getByTestId("sidebar-nav-ai")).toBeInTheDocument();
  });

  it("shows 後續開放 badge on AI 問答 item", () => {
    render(<Sidebar />);
    expect(screen.getByTestId("sidebar-badge-ai")).toBeInTheDocument();
    expect(screen.getByTestId("sidebar-badge-ai").textContent).toBe("後續開放");
  });

  it("does not show badge on other nav items", () => {
    render(<Sidebar />);
    expect(screen.queryByTestId("sidebar-badge-dashboard")).not.toBeInTheDocument();
    expect(screen.queryByTestId("sidebar-badge-settings")).not.toBeInTheDocument();
  });

  it("marks active page with aria-current=page", () => {
    render(<Sidebar />);
    // pathname is /dashboard, so dashboard link should be active
    const dashboardLink = screen.getByTestId("sidebar-nav-dashboard");
    expect(dashboardLink).toHaveAttribute("aria-current", "page");
  });

  it("uses opaque mobile tab bar background class", () => {
    render(<Sidebar />);
    const mobileNav = screen.getByLabelText("手機底部導覽");
    expect(mobileNav).toHaveClass("bg-[hsl(var(--background))]");
    expect(mobileNav).not.toHaveClass("bg-background");
  });
});
