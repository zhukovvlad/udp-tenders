import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DirectionSwitcher } from "./DirectionSwitcher";

const DIRECTIONS = [
  { code: "concrete", name: "Бетон" },
  { code: "rebar", name: "Арматура" },
];

describe("DirectionSwitcher", () => {
  it("renders «Все направления» first, then directions in order", () => {
    render(<DirectionSwitcher directions={DIRECTIONS} value="all" onChange={() => {}} />);
    const tabs = screen.getAllByRole("tab");
    expect(tabs.map((t) => t.textContent)).toEqual(["Все направления", "Бетон", "Арматура"]);
  });

  it("marks active segment with aria-selected", () => {
    render(<DirectionSwitcher directions={DIRECTIONS} value="rebar" onChange={() => {}} />);
    expect(screen.getByTestId("direction-rebar")).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("direction-all")).toHaveAttribute("aria-selected", "false");
  });

  it("calls onChange with code on click", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<DirectionSwitcher directions={DIRECTIONS} value="all" onChange={onChange} />);
    await user.click(screen.getByTestId("direction-rebar"));
    expect(onChange).toHaveBeenCalledWith("rebar");
  });

  it("renders nothing when directions is empty (legacy mode, ADR #11)", () => {
    const { container } = render(<DirectionSwitcher directions={[]} value="all" onChange={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });
});
